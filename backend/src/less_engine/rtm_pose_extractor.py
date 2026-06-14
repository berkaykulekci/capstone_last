"""
LESS Analiz Sistemi - RTMPose-WholeBody Pose Extraction Modülü
rtmlib (Tau-J) + ONNX Runtime ile videodan COCO-WholeBody pose verisi çıkarır.

rtmlib, RTMPose'un yazarı tarafından mmcv/mmpose/mmdet bağımlılığı OLMADAN
yazılmış resmi ONNX sarmalayıcısıdır. Kişi tespiti (YOLOX), SimCC çözümü ve
affine geri-dönüşümü doğru şekilde içeride yapar; modelleri ilk çağrıda
indirip cache'ler.

Çıktı yalnızca 0..22 keypoint dilimini (gövde + ayak) tutar (RTM_NUM_KEYPOINTS):
COCO-WholeBody sıralamasında 0-16 gövde (COCO-17), 17-22 ayak (toe/heel).

MediaPipe/YOLO farkları:
  - Ayak (heel + big toe) MEVCUT → M4/M9/M10 exact.
  - Z koordinatı yok → kanal 2 = confidence; test tarafı otomatik belirlenemez.
  - rtmlib + onnxruntime YALNIZCA bu modül kullanıldığında (lazy) import edilir;
    diğer backend'leri kırmaz.
"""
import os
import cv2
import numpy as np
import pandas as pd

from .rtm_config import (
    RTM_MODE, RTM_DEVICE, RTM_BACKEND,
    RTM_KPT_CONF_THRESHOLD, RTM_NUM_KEYPOINTS,
    NORMALIZE_VIDEO_FRAME_COORDS, DEFAULT_TEST_SIDE,
    VIDEO_DIR, SUPPORTED_EXTENSIONS,
)

# Modül seviyesinde cache (her video için modeli tekrar yüklememek adına).
_WHOLEBODY = None


def find_video_file(prefix):
    """Belirtilen prefix ile başlayan video dosyasını bulur."""
    for ext in SUPPORTED_EXTENSIONS:
        path = os.path.join(VIDEO_DIR, f'{prefix}.{ext}')
        if os.path.exists(path):
            return path
    return None


def _load_model():
    """
    rtmlib Wholebody modelini yükler (ilk çağrıda; ONNX'leri indirip cache'ler).
    rtmlib ve onnxruntime burada lazy import edilir.
    """
    global _WHOLEBODY
    if _WHOLEBODY is not None:
        return _WHOLEBODY
    try:
        from rtmlib import Wholebody
    except ImportError:
        raise ImportError(
            "rtmlib paketi yüklü değil: pip install rtmlib onnxruntime "
            "(RTMPose backend için gereklidir)"
        )
    _WHOLEBODY = Wholebody(mode=RTM_MODE, backend=RTM_BACKEND, device=RTM_DEVICE)
    return _WHOLEBODY


def _select_person(keypoints, scores):
    """
    Birden fazla kişi tespitinde en yüksek ortalama güvenilirlikli kişiyi seçer.
    keypoints: (n_persons, 133, 2), scores: (n_persons, 133)
    Returns: kp (133, 2), sc (133,) veya (None, None)
    """
    if keypoints is None or len(keypoints) == 0:
        return None, None
    if len(keypoints) == 1:
        return keypoints[0], scores[0]
    mean_scores = np.nanmean(scores, axis=1)
    best = int(np.argmax(mean_scores))
    return keypoints[best], scores[best]


def extract_poses(video_path):
    """
    Videodan tüm frame'lerin RTMPose-WholeBody pose landmark'larını çıkarır.

    Çıktı formatı:
        poses: np.ndarray (N_frames, RTM_NUM_KEYPOINTS, 3)
               [:, :, 0] = x (normalize veya piksel)
               [:, :, 1] = y (normalize, Y yukarı = büyük değer)
               [:, :, 2] = confidence (0-1)
        Confidence < RTM_KPT_CONF_THRESHOLD olan keypoint'ler NaN'a çevrilir.

    Returns:
        poses, width, height, fps, total_frames
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video bulunamadı: {video_path}")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Video açılamadı: {video_path}")

    width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps    = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0 or np.isnan(fps):
        fps = 30.0

    model = _load_model()

    all_poses = []
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        lm_array = np.full((RTM_NUM_KEYPOINTS, 3), np.nan)

        keypoints, scores = model(frame)  # (n,133,2), (n,133) — orijinal piksel
        kp, sc = _select_person(keypoints, scores)

        if kp is not None:
            for i in range(RTM_NUM_KEYPOINTS):
                x_px, y_px, conf = float(kp[i, 0]), float(kp[i, 1]), float(sc[i])
                if conf < RTM_KPT_CONF_THRESHOLD:
                    continue  # NaN bırak
                if NORMALIZE_VIDEO_FRAME_COORDS:
                    x = np.clip(x_px / width, 0.0, 1.0)
                    y = np.clip(1.0 - y_px / height, 0.0, 1.0)  # Y ters çevir
                else:
                    x = x_px
                    y = height - y_px  # Y ters çevir
                lm_array[i] = [x, y, conf]

        all_poses.append(lm_array)

    cap.release()
    poses = np.array(all_poses)         # (N, K, 3)
    total_frames = len(poses)

    # Eksik landmark'lar için linear interpolasyon (yalnızca x, y; confidence atla).
    for kp_idx in range(RTM_NUM_KEYPOINTS):
        for c in range(2):
            s = pd.Series(poses[:, kp_idx, c])
            poses[:, kp_idx, c] = s.interpolate(limit_direction='both').to_numpy()

    print(f"  → {total_frames} frame çıkarıldı [RTMPose] ({video_path})")
    return poses, width, height, fps, total_frames


def detect_test_side(poses):
    """
    RTMPose 2D modeli Z koordinatı vermediğinden test tarafı otomatik
    belirlenemiyor. Her zaman DEFAULT_TEST_SIDE döner.

    Kullanıcı yan kamerada hangi dizi izlemek istediğini biliyorsa
    test_side parametresini açıkça geçebilir.
    """
    return DEFAULT_TEST_SIDE
