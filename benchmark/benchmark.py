"""
Pose Estimation Benchmark
=========================
MediaPipe BlazePose, YOLOv8-pose ve kendi pipeline'ımızı
ground-truth gerektirmeyen metriklerle karşılaştırır.

Kullanım
--------
    python benchmark/benchmark.py --videos videos/ [--output benchmark/results/]
    python benchmark/benchmark.py --videos videos/ --yolo-model yolov8n-pose.pt

Çıktılar
--------
    <output>/summary_results.csv
    <output>/per_frame_results.csv
"""
import sys
import os
import time
import argparse
import glob
import shutil
import subprocess
from typing import List, Tuple, Dict, Any, Optional

import cv2
import numpy as np
import pandas as pd

# benchmark/ içinden import edilebilmesi için
_BENCHMARK_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR      = os.path.dirname(_BENCHMARK_DIR)
sys.path.insert(0, _ROOT_DIR)
sys.path.insert(0, _BENCHMARK_DIR)

import mediapipe as mp

from limb_utils import MP_KP_MAP, YOLO_KP_MAP
from metrics import (
    compute_fps_and_latency,
    compute_missing_kp_rate,
    compute_mean_confidence,
    compute_jitter,
    aggregate_jitter,
    compute_limb_series,
    compute_limb_consistency,
    compute_angle_series,
    compute_biomech_plausibility,
)
from reporter import write_summary_csv, write_per_frame_csv


# ── Desteklenen uzantılar ─────────────────────────────────────────────────────
SUPPORTED_EXTENSIONS = ['mp4', 'mov', 'MP4', 'MOV', 'avi', 'AVI', 'mkv', 'MKV']


# ── Video tarama ──────────────────────────────────────────────────────────────

def find_videos(video_dir: str) -> List[str]:
    """video_dir altındaki tüm desteklenen video dosyalarını döner."""
    paths = []
    for ext in SUPPORTED_EXTENSIONS:
        paths.extend(glob.glob(os.path.join(video_dir, f'*.{ext}')))
    return sorted(set(paths))


# ── MediaPipe inference (per-frame timing) ────────────────────────────────────

def _run_mediapipe_inference(
    video_path: str,
    model_complexity: int = 2,
    min_detection_confidence: float = 0.5,
    min_tracking_confidence: float = 0.5,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, List[float], int, int, float]:
    """
    MediaPipe BlazePose ile frame-by-frame inference yapar.

    Returns
    -------
    poses_raw        : (N, 33, 3) — x,y,z; interpolasyon öncesi, NaN içerir
    poses_interp     : (N, 33, 3) — linear interpolasyon sonrası
    conf_array       : (N, 33)   — landmark visibility [0,1]
    frame_times_ms   : Her frame'in `pose.process()` süresi (ms)
    width, height    : Video çözünürlüğü (piksel)
    video_fps        : Kaynak video FPS
    """
    mp_pose = mp.solutions.pose

    cap = cv2.VideoCapture(video_path)
    width      = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height     = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    video_fps  = cap.get(cv2.CAP_PROP_FPS)
    if video_fps <= 0 or np.isnan(video_fps):
        video_fps = 30.0

    all_poses_raw: List[np.ndarray] = []
    all_conf:      List[np.ndarray] = []
    frame_times_ms: List[float]     = []

    with mp_pose.Pose(
        static_image_mode=False,
        model_complexity=model_complexity,
        enable_segmentation=False,
        min_detection_confidence=min_detection_confidence,
        min_tracking_confidence=min_tracking_confidence,
    ) as pose:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            t0 = time.perf_counter()
            results = pose.process(rgb)
            t1 = time.perf_counter()
            frame_times_ms.append((t1 - t0) * 1000.0)

            lm_array  = np.full((33, 3), np.nan)
            conf_row  = np.full(33, np.nan)

            if results.pose_landmarks:
                for i, lm in enumerate(results.pose_landmarks.landmark):
                    # x/y normalize (0-1), Y ters çevrilir (yukarı = büyük)
                    lm_array[i] = [
                        np.clip(lm.x, 0.0, 1.0),
                        np.clip(1.0 - lm.y, 0.0, 1.0),
                        lm.z,
                    ]
                    conf_row[i] = lm.visibility

            all_poses_raw.append(lm_array)
            all_conf.append(conf_row)

    cap.release()

    # Boş video kontrolü — np.array([]) 1D döner, bunu önle
    if not all_poses_raw:
        empty_raw    = np.empty((0, 33, 3), dtype=np.float64)
        empty_conf   = np.empty((0, 33),    dtype=np.float64)
        return empty_raw, empty_raw.copy(), empty_conf, [], width, height, video_fps

    poses_raw = np.array(all_poses_raw)   # (N, 33, 3)
    conf      = np.array(all_conf)        # (N, 33)

    # Linear interpolasyon (pose_extractor.py ile aynı mantık)
    poses_interp = poses_raw.copy()
    for lm_idx in range(33):
        for c in range(3):
            s = pd.Series(poses_interp[:, lm_idx, c])
            poses_interp[:, lm_idx, c] = s.interpolate(limit_direction='both').to_numpy()

    return poses_raw, poses_interp, conf, frame_times_ms, width, height, video_fps


# ── YOLO inference (per-frame timing) ────────────────────────────────────────

def _select_yolo_person(result) -> Optional[np.ndarray]:
    """Birden fazla kişi varsa en yüksek güvenilirlikli bbox'ı seçer."""
    if result.keypoints is None or result.keypoints.data is None:
        return None
    kp_data = result.keypoints.data.cpu().numpy()  # (P, 17, 3)
    if kp_data.shape[0] == 0:
        return None
    if kp_data.shape[0] == 1:
        return kp_data[0]
    boxes = result.boxes
    if boxes is not None and len(boxes.conf) > 0:
        best = int(np.argmax(boxes.conf.cpu().numpy()))
        return kp_data[best]
    return kp_data[0]


def _run_yolo_inference(
    video_path: str,
    yolo_model_name: str = 'yolov8x-pose.pt',
    conf_threshold: float = 0.5,
    person_conf: float = 0.5,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, List[float], int, int, float]:
    """
    YOLO Pose ile frame-by-frame inference yapar.
    Her frame cv2 ile okunup tek tek predict edilir → doğru per-frame timing.

    Returns
    -------
    poses_raw, poses_interp, conf_array, frame_times_ms, width, height, video_fps
    """
    try:
        from ultralytics import YOLO
    except ImportError:
        raise ImportError(
            'ultralytics paketi bulunamadı. '
            'Yüklemek için: pip install ultralytics'
        )

    cap = cv2.VideoCapture(video_path)
    width     = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height    = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    video_fps = cap.get(cv2.CAP_PROP_FPS)
    if video_fps <= 0 or np.isnan(video_fps):
        video_fps = 30.0

    model = YOLO(yolo_model_name)

    # Model warmup (yükleme süresini ölçüme dahil etme)
    dummy = np.zeros((64, 64, 3), dtype=np.uint8)
    model.predict(source=dummy, verbose=False, conf=person_conf)

    all_poses_raw: List[np.ndarray] = []
    all_conf:      List[np.ndarray] = []
    frame_times_ms: List[float]     = []

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        t0 = time.perf_counter()
        results = model.predict(source=frame, verbose=False, conf=person_conf)
        t1 = time.perf_counter()
        frame_times_ms.append((t1 - t0) * 1000.0)

        result   = results[0] if results else None
        kp       = _select_yolo_person(result) if result is not None else None
        lm_array = np.full((17, 3), np.nan)
        conf_row = np.full(17, np.nan)

        if kp is not None:
            for i in range(17):
                x_px, y_px, conf = float(kp[i, 0]), float(kp[i, 1]), float(kp[i, 2])
                if conf >= conf_threshold:
                    x = np.clip(x_px / width,  0.0, 1.0)
                    y = np.clip(1.0 - y_px / height, 0.0, 1.0)  # Y ters çevir
                    lm_array[i] = [x, y, conf]
                    conf_row[i] = conf

        all_poses_raw.append(lm_array)
        all_conf.append(conf_row)

    cap.release()

    # Boş video kontrolü
    if not all_poses_raw:
        empty_raw  = np.empty((0, 17, 3), dtype=np.float64)
        empty_conf = np.empty((0, 17),    dtype=np.float64)
        return empty_raw, empty_raw.copy(), empty_conf, [], width, height, video_fps

    poses_raw = np.array(all_poses_raw)   # (N, 17, 3)
    conf      = np.array(all_conf)        # (N, 17)

    # Linear interpolasyon
    poses_interp = poses_raw.copy()
    for kp_idx in range(17):
        for c in range(2):
            s = pd.Series(poses_interp[:, kp_idx, c])
            poses_interp[:, kp_idx, c] = s.interpolate(limit_direction='both').to_numpy()

    return poses_raw, poses_interp, conf, frame_times_ms, width, height, video_fps


# ── OurModel inference ────────────────────────────────────────────────────────

def _run_our_model_inference(
    video_path: str,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, List[float], int, int, float]:
    """
    Kendi pipeline'ımız: MediaPipe inference + jump_detector post-processing.
    frame_times_ms = MediaPipe per-frame süre + jump_detector toplam süresinin
                     frame'e düşen payı.
    """
    from jump_detector import detect_jumps

    poses_raw, poses_interp, conf, mp_times, width, height, video_fps = \
        _run_mediapipe_inference(video_path)

    if len(poses_interp) == 0:
        return poses_raw, poses_interp, conf, mp_times, width, height, video_fps

    # jump_detector toplam süresini ölç
    t0 = time.perf_counter()
    try:
        detect_jumps(poses_interp, test_side='right', label='BENCH')
    except Exception:
        pass  # Kısa / geçersiz videolarda graceful degrade
    t1 = time.perf_counter()

    jd_per_frame_ms = (t1 - t0) * 1000.0 / len(mp_times)
    frame_times_ms  = [t + jd_per_frame_ms for t in mp_times]

    return poses_raw, poses_interp, conf, frame_times_ms, width, height, video_fps


# ── Metrik toplama ────────────────────────────────────────────────────────────

def _build_results(
    video_name: str,
    model_name: str,
    poses_raw: np.ndarray,
    poses_interp: np.ndarray,
    conf_array: np.ndarray,
    frame_times_ms: List[float],
    kp_map: Dict[str, int],
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Tüm metrikleri hesaplar; özet dict ve per-frame satır listesi döner.
    """
    # Boyut kontrolü: boş veya yanlış şekilli array
    if poses_interp.ndim != 3 or poses_interp.shape[0] == 0:
        empty_summary = {
            'video': video_name, 'model': model_name, 'total_frames': 0,
        }
        return empty_summary, []
    N = poses_interp.shape[0]

    # ── Özet metrikler ──
    fps, latency_ms     = compute_fps_and_latency(frame_times_ms)
    missing_kp_pct      = compute_missing_kp_rate(poses_raw)
    mean_conf           = compute_mean_confidence(conf_array)
    coord_std, ac_mean  = aggregate_jitter(poses_interp)
    limb_self, limb_ap  = compute_limb_consistency(poses_interp, kp_map)
    bm_self,   bm_ap    = compute_biomech_plausibility(poses_interp, kp_map)

    summary = {
        'video':               video_name,
        'model':               model_name,
        'total_frames':        N,
        'fps':                 fps,
        'latency_ms':          latency_ms,
        'missing_kp_pct':      missing_kp_pct,
        'jitter_coord_std':    coord_std,
        'jitter_accel_mean':   ac_mean,
        'limb_self_std':       limb_self,
        'limb_anthropo_pct':   limb_ap,
        'biomech_self_std':    bm_self,
        'biomech_anthropo_pct': bm_ap,
        'mean_confidence':     mean_conf,
    }

    # ── Per-frame veriler ──
    coord_series, accel_series  = compute_jitter(poses_interp)
    femur_arr, tibia_arr, _     = compute_limb_series(poses_interp, kp_map)
    knee_arr, hip_arr           = compute_angle_series(poses_interp, kp_map)

    # Pre-interpolation missing kp sayısı per frame
    missing_per_frame = np.sum(np.isnan(poses_raw[:, :, 0]), axis=1).astype(int)

    # Per-frame confidence (her frame'in ortalaması)
    conf_per_frame = np.nanmean(conf_array, axis=1)

    # frame_times_ms uzunluğu bazen N'den farklı olabilir (stream kayıpları)
    times_padded = list(frame_times_ms) + [np.nan] * max(0, N - len(frame_times_ms))
    times_padded = times_padded[:N]

    frame_rows = []
    for i in range(N):
        frame_rows.append({
            'video':            video_name,
            'model':            model_name,
            'frame_idx':        i,
            'inference_time_ms': times_padded[i],
            'n_missing_kp':     int(missing_per_frame[i]),
            'jitter_coord':     coord_series[i],
            'jitter_accel':     accel_series[i],
            'femur_len':        femur_arr[i],
            'tibia_len':        tibia_arr[i],
            'knee_angle':       knee_arr[i],
            'hip_angle':        hip_arr[i],
            'mean_confidence':  conf_per_frame[i],
        })

    return summary, frame_rows


# ── Ana fonksiyon ─────────────────────────────────────────────────────────────

def run_benchmark(
    video_dir: str,
    output_dir: str,
    yolo_model: str = 'yolov8x-pose.pt',
    skip_yolo: bool = False,
    skip_ourmodel: bool = False,
) -> None:
    videos = find_videos(video_dir)
    if not videos:
        print(f'[HATA] {video_dir} altında desteklenen video bulunamadı.')
        print(f'       Desteklenen uzantılar: {SUPPORTED_EXTENSIONS}')
        return

    print(f'\n{"="*60}')
    print(f'  Pose Estimation Benchmark')
    print(f'  Video dizini : {video_dir}')
    print(f'  Bulunan video: {len(videos)} adet')
    print(f'  Çıktı dizini : {output_dir}')
    print(f'{"="*60}\n')

    os.makedirs(output_dir, exist_ok=True)

    all_summary:    List[Dict[str, Any]] = []
    all_frame_rows: List[Dict[str, Any]] = []

    for video_path in videos:
        video_name = os.path.basename(video_path)
        print(f'\n▶ Video: {video_name}')
        print(f'  {"─"*50}')

        # ── MediaPipe ──────────────────────────────────────────────────────
        print('  [1/3] MediaPipe BlazePose (Heavy, complexity=2)...')
        try:
            poses_raw, poses_i, conf, times, w, h, vfps = \
                _run_mediapipe_inference(video_path)
            summary, rows = _build_results(
                video_name, 'MediaPipe', poses_raw, poses_i, conf, times, MP_KP_MAP
            )
            all_summary.append(summary)
            all_frame_rows.extend(rows)
            print(f'     → {summary.get("total_frames", 0)} frame | '
                  f'FPS={summary.get("fps", 0):.1f} | '
                  f'Latency={summary.get("latency_ms", 0):.1f} ms | '
                  f'Missing={summary.get("missing_kp_pct", 0):.2f}%')
        except Exception as e:
            print(f'     [HATA] MediaPipe başarısız: {e}')

        # ── YOLO ──────────────────────────────────────────────────────────
        if not skip_yolo:
            print(f'  [2/3] YOLO Pose ({yolo_model})...')
            try:
                poses_raw, poses_i, conf, times, w, h, vfps = \
                    _run_yolo_inference(video_path, yolo_model_name=yolo_model)
                summary, rows = _build_results(
                    video_name, 'YOLO', poses_raw, poses_i, conf, times, YOLO_KP_MAP
                )
                all_summary.append(summary)
                all_frame_rows.extend(rows)
                print(f'     → {summary.get("total_frames", 0)} frame | '
                      f'FPS={summary.get("fps", 0):.1f} | '
                      f'Latency={summary.get("latency_ms", 0):.1f} ms | '
                      f'Missing={summary.get("missing_kp_pct", 0):.2f}%')
            except ImportError as e:
                print(f'     [ATLA] ultralytics yüklü değil: {e}')
            except Exception as e:
                print(f'     [HATA] YOLO başarısız: {e}')
        else:
            print('  [2/3] YOLO: --skip-yolo ile atlandı.')

        # ── OurModel ──────────────────────────────────────────────────────
        if not skip_ourmodel:
            print('  [3/3] OurModel (MediaPipe + jump_detector)...')
            try:
                poses_raw, poses_i, conf, times, w, h, vfps = \
                    _run_our_model_inference(video_path)
                summary, rows = _build_results(
                    video_name, 'OurModel', poses_raw, poses_i, conf, times, MP_KP_MAP
                )
                all_summary.append(summary)
                all_frame_rows.extend(rows)
                print(f'     → {summary.get("total_frames", 0)} frame | '
                      f'FPS={summary.get("fps", 0):.1f} | '
                      f'Latency={summary.get("latency_ms", 0):.1f} ms | '
                      f'Missing={summary.get("missing_kp_pct", 0):.2f}%')
            except Exception as e:
                print(f'     [HATA] OurModel başarısız: {e}')
        else:
            print('  [3/3] OurModel: --skip-ourmodel ile atlandı.')

    # ── CSV çıktıları ──────────────────────────────────────────────────────
    print(f'\n{"="*60}')
    print('  CSV yazılıyor...')
    summary_path    = os.path.join(output_dir, 'summary_results.csv')
    per_frame_path  = os.path.join(output_dir, 'per_frame_results.csv')
    write_summary_csv(all_summary, summary_path)
    write_per_frame_csv(all_frame_rows, per_frame_path)

    # ── Downloads klasörüne kopyala (Mac) ─────────────────────────────────
    downloads_dir = os.path.join(os.path.expanduser('~'), 'Downloads', 'pose_benchmark')
    try:
        os.makedirs(downloads_dir, exist_ok=True)
        dl_summary   = os.path.join(downloads_dir, 'summary_results.csv')
        dl_per_frame = os.path.join(downloads_dir, 'per_frame_results.csv')
        shutil.copy2(summary_path,   dl_summary)
        shutil.copy2(per_frame_path, dl_per_frame)
        print(f'  ✓ Downloads → {downloads_dir}')
        # Finder'da klasörü aç
        subprocess.Popen(['open', downloads_dir])
    except Exception as e:
        print(f'  [UYARI] Downloads kopyalanamadı: {e}')

    print(f'\n  TAMAMLANDI.')
    print(f'  Özet      : {summary_path}')
    print(f'  Per-frame : {per_frame_path}')
    print(f'{"="*60}\n')


# ── CLI ───────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Pose Estimation Benchmark — MediaPipe vs YOLO vs OurModel'
    )
    parser.add_argument(
        '--videos', '-v',
        default='videos/',
        help='Video dosyalarının bulunduğu klasör (varsayılan: videos/)',
    )
    parser.add_argument(
        '--output', '-o',
        default='benchmark/results/',
        help='CSV çıktılarının kaydedileceği klasör (varsayılan: benchmark/results/)',
    )
    parser.add_argument(
        '--yolo-model',
        default='yolov8x-pose.pt',
        help='YOLO model dosyası (varsayılan: yolov8x-pose.pt)',
    )
    parser.add_argument(
        '--skip-yolo',
        action='store_true',
        help='YOLO modelini atla',
    )
    parser.add_argument(
        '--skip-ourmodel',
        action='store_true',
        help='OurModel pipeline\'ını atla',
    )
    return parser.parse_args()


if __name__ == '__main__':
    args = _parse_args()
    # Göreceli yolları script'in çalıştırıldığı dizine göre çöz
    video_dir  = args.videos  if os.path.isabs(args.videos)  else os.path.join(_ROOT_DIR, args.videos)
    output_dir = args.output  if os.path.isabs(args.output)  else os.path.join(_ROOT_DIR, args.output)
    run_benchmark(
        video_dir=video_dir,
        output_dir=output_dir,
        yolo_model=args.yolo_model,
        skip_yolo=args.skip_yolo,
        skip_ourmodel=args.skip_ourmodel,
    )
