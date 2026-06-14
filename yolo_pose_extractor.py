"""
LESS Analiz Sistemi - YOLO Pose Extraction Modülü
YOLOv8-pose / YOLO11-pose ile videodan 17-keypoint pose verisi çıkarır.

MediaPipe farkları:
  - 17 keypoint (COCO), MediaPipe'ın 33'ü yerine
  - Heel ve foot_index yok → contact_y sadece ankle tabanlı
  - Z koordinatı yok → test tarafı otomatik belirlenemiyor
  - Her keypoint için x, y, confidence döner; düşük confidence → NaN
"""
import cv2
import numpy as np
import pandas as pd
import os

from yolo_config import (
    YOLO_MODEL, YOLO_CONF_THRESHOLD, YOLO_PERSON_CONF,
    NORMALIZE_VIDEO_FRAME_COORDS, DEFAULT_TEST_SIDE,
    VIDEO_DIR, SUPPORTED_EXTENSIONS,
    LEFT_HIP, RIGHT_HIP, LEFT_KNEE, RIGHT_KNEE,
    LEFT_ANKLE, RIGHT_ANKLE
)


def find_video_file(prefix):
    """Belirtilen prefix ile başlayan video dosyasını bulur."""
    for ext in SUPPORTED_EXTENSIONS:
        path = os.path.join(VIDEO_DIR, f'{prefix}.{ext}')
        if os.path.exists(path):
            return path
    return None


def _load_yolo():
    """YOLO modelini yükler (ilk çağrıda indirir)."""
    try:
        from ultralytics import YOLO
    except ImportError:
        raise ImportError("ultralytics paketi yüklü değil: pip install ultralytics")
    return YOLO(YOLO_MODEL)


def _select_person(result):
    """
    Birden fazla kişi tespitinde en büyük bounding box'ı seçer
    (sporcu genellikle frame'in merkezinde ve büyük görünür).
    Returns: keypoints array (17, 3) veya None
    """
    if result.keypoints is None or result.keypoints.data is None:
        return None

    kp_data = result.keypoints.data.cpu().numpy()  # (N_persons, 17, 3)
    boxes = result.boxes

    if kp_data.shape[0] == 0:
        return None

    if kp_data.shape[0] == 1:
        return kp_data[0]

    # Birden fazla kişi: en büyük bounding box'ı seç
    if boxes is not None and len(boxes.conf) > 0:
        confs = boxes.conf.cpu().numpy()
        areas = []
        for b in boxes.xyxy.cpu().numpy():
            areas.append((b[2] - b[0]) * (b[3] - b[1]))
        # En yüksek güvenilirlikli kişiyi seç
        best = int(np.argmax(confs))
        return kp_data[best]

    return kp_data[0]


def extract_poses(video_path):
    """
    Videodan tüm frame'lerin YOLO pose landmark'larını çıkarır.

    Çıktı formatı:
        poses: np.ndarray (N_frames, 17, 3)
               [:, :, 0] = x (normalize veya piksel)
               [:, :, 1] = y (normalize, Y yukarı = büyük değer)
               [:, :, 2] = confidence (0-1)
        Confidence < YOLO_CONF_THRESHOLD olan keypoint'ler NaN'a çevrilir.

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
    cap.release()

    model = _load_yolo()

    all_poses = []

    results_gen = model.predict(
        source=video_path,
        stream=True,
        verbose=False,
        conf=YOLO_PERSON_CONF
    )

    for result in results_gen:
        kp = _select_person(result)

        lm_array = np.full((17, 3), np.nan)

        if kp is not None:
            for i in range(17):
                x_px, y_px, conf = float(kp[i, 0]), float(kp[i, 1]), float(kp[i, 2])

                if conf < YOLO_CONF_THRESHOLD:
                    # Güvenilir değil → NaN bırak
                    continue

                if NORMALIZE_VIDEO_FRAME_COORDS:
                    x = np.clip(x_px / width,  0.0, 1.0)
                    y = np.clip(1.0 - y_px / height, 0.0, 1.0)  # Y ters çevir
                else:
                    x = x_px
                    y = height - y_px  # Y ters çevir

                lm_array[i] = [x, y, conf]

        all_poses.append(lm_array)

    poses = np.array(all_poses)         # (N, 17, 3)
    total_frames = len(poses)

    # Eksik landmark'lar için linear interpolasyon (her eksen, her keypoint)
    for kp_idx in range(17):
        for c in range(2):             # sadece x, y interpole et; confidence atla
            s = pd.Series(poses[:, kp_idx, c])
            poses[:, kp_idx, c] = s.interpolate(limit_direction='both').to_numpy()

    print(f"  → {total_frames} frame çıkarıldı [YOLO] ({video_path})")
    return poses, width, height, fps, total_frames


def detect_test_side(poses):
    """
    YOLO Pose 2D modeli Z koordinatı vermediğinden test tarafı
    otomatik belirlenemiyor. Her zaman DEFAULT_TEST_SIDE döner.

    Kullanıcı yan kamerada hangi dizi izlemek istediğini biliyorsa
    test_side parametresini açıkça geçebilir.
    """
    return DEFAULT_TEST_SIDE
