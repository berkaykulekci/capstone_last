"""
LESS Analiz Sistemi - YOLO Pose Extraction Modülü (Backend)
YOLOv8-pose / YOLO11-pose ile videodan 17-keypoint pose verisi çıkarır.
"""
import cv2
import numpy as np
import pandas as pd
import os

from .yolo_config import (
    YOLO_MODEL, YOLO_CONF_THRESHOLD, YOLO_PERSON_CONF,
    NORMALIZE_VIDEO_FRAME_COORDS, DEFAULT_TEST_SIDE,
    VIDEO_DIR, SUPPORTED_EXTENSIONS,
)


def find_video_file(prefix):
    for ext in SUPPORTED_EXTENSIONS:
        path = os.path.join(VIDEO_DIR, f'{prefix}.{ext}')
        if os.path.exists(path):
            return path
    return None


def _load_yolo():
    try:
        from ultralytics import YOLO
    except ImportError:
        raise ImportError("ultralytics paketi yüklü değil: pip install ultralytics")
    return YOLO(YOLO_MODEL)


def _select_person(result):
    """En büyük/yüksek güvenilirlikli kişiyi seçer."""
    if result.keypoints is None or result.keypoints.data is None:
        return None
    kp_data = result.keypoints.data.cpu().numpy()
    if kp_data.shape[0] == 0:
        return None
    if kp_data.shape[0] == 1:
        return kp_data[0]
    boxes = result.boxes
    if boxes is not None and len(boxes.conf) > 0:
        best = int(np.argmax(boxes.conf.cpu().numpy()))
        return kp_data[best]
    return kp_data[0]


def extract_poses(video_path):
    """
    Videodan YOLO pose landmark'larını çıkarır.

    Returns:
        poses: np.ndarray (N_frames, 17, 3)  — x, y (normalize, Y↑), confidence
        width, height, fps, total_frames
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

    for result in model.predict(source=video_path, stream=True,
                                verbose=False, conf=YOLO_PERSON_CONF):
        kp = _select_person(result)
        lm_array = np.full((17, 3), np.nan)
        if kp is not None:
            for i in range(17):
                x_px, y_px, conf = float(kp[i, 0]), float(kp[i, 1]), float(kp[i, 2])
                if conf < YOLO_CONF_THRESHOLD:
                    continue
                if NORMALIZE_VIDEO_FRAME_COORDS:
                    lm_array[i] = [np.clip(x_px / width, 0, 1),
                                   np.clip(1.0 - y_px / height, 0, 1),
                                   conf]
                else:
                    lm_array[i] = [x_px, height - y_px, conf]
        all_poses.append(lm_array)

    poses = np.array(all_poses)
    total_frames = len(poses)

    for kp_idx in range(17):
        for c in range(2):
            s = pd.Series(poses[:, kp_idx, c])
            poses[:, kp_idx, c] = s.interpolate(limit_direction='both').to_numpy()

    print(f"  → {total_frames} frame çıkarıldı [YOLO] ({video_path})")
    return poses, width, height, fps, total_frames


def detect_test_side(poses):
    """YOLO 2D — Z yok, DEFAULT_TEST_SIDE döner."""
    return DEFAULT_TEST_SIDE
