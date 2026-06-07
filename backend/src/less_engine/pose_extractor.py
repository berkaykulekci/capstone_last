"""
LESS Analiz Sistemi - Pose Extraction Modülü
MediaPipe BlazePose Heavy ile videodan pose verilerini çıkarır.
"""
import cv2
import mediapipe as mp
import numpy as np
import pandas as pd
import os
from .config import (
    POSE_MODEL_COMPLEXITY, MIN_DETECTION_CONFIDENCE,
    MIN_TRACKING_CONFIDENCE, SUPPORTED_EXTENSIONS, VIDEO_DIR,
    LEFT_HIP, RIGHT_HIP, LEFT_KNEE, RIGHT_KNEE,
    LEFT_ANKLE, RIGHT_ANKLE, DEFAULT_TEST_SIDE,
    NORMALIZE_VIDEO_FRAME_COORDS, TEST_SIDE_Z_EPS_NORMALIZED,
    TEST_SIDE_Z_EPS_PIXELS
)

mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils


def find_video_file(prefix):
    """Belirtilen prefix ile başlayan video dosyasını bulur."""
    for ext in SUPPORTED_EXTENSIONS:
        path = os.path.join(VIDEO_DIR, f'{prefix}.{ext}')
        if os.path.exists(path):
            return path
    return None


def extract_poses(video_path):
    """
    Videodan tüm frame'lerin pose landmark'larını çıkarır.

    X/Y koordinatları varsayılan olarak 0-1 aralığında normalize edilir.
    Y koordinatı ters çevrilir: yukarı = büyük değer (fizik konvansiyonu).

    Returns:
        poses: np.ndarray (N_frames, 33, 3)
        width, height: int
        fps: float
        total_frames: int
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video bulunamadı: {video_path}")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Video açılamadı: {video_path}")

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0 or np.isnan(fps):
        fps = 30.0

    all_poses = []

    with mp_pose.Pose(
        static_image_mode=False,
        model_complexity=POSE_MODEL_COMPLEXITY,
        min_detection_confidence=MIN_DETECTION_CONFIDENCE,
        min_tracking_confidence=MIN_TRACKING_CONFIDENCE
    ) as pose:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = pose.process(rgb)

            lm_array = np.full((33, 3), np.nan)
            if results.pose_landmarks:
                for i, lm in enumerate(results.pose_landmarks.landmark):
                    if NORMALIZE_VIDEO_FRAME_COORDS:
                        lm_array[i] = [
                            np.clip(lm.x, 0.0, 1.0),
                            np.clip(1.0 - lm.y, 0.0, 1.0),  # Y ters çevir
                            lm.z
                        ]
                    else:
                        lm_array[i] = [
                            lm.x * width,
                            height - (lm.y * height),  # Y ters çevir
                            lm.z * width
                        ]
            all_poses.append(lm_array)

    cap.release()
    poses = np.array(all_poses)
    total_frames = len(poses)

    # Eksik landmark'lar için linear interpolasyon
    for lm_idx in range(33):
        for c in range(3):
            s = pd.Series(poses[:, lm_idx, c])
            poses[:, lm_idx, c] = s.interpolate(limit_direction='both').to_numpy()

    print(f"  → {total_frames} frame çıkarıldı ({video_path})")
    return poses, width, height, fps, total_frames


def detect_test_side(poses):
    """
    Z koordinatlarını kullanarak kameraya yakın tarafı (test tarafı) belirler.
    Daha negatif z = kameraya daha yakın.
    Fark küçükse DEFAULT_TEST_SIDE döner.
    """
    left_ids = [LEFT_HIP, LEFT_KNEE, LEFT_ANKLE]
    right_ids = [RIGHT_HIP, RIGHT_KNEE, RIGHT_ANKLE]

    left_z = np.nanmedian([poses[:, i, 2] for i in left_ids])
    right_z = np.nanmedian([poses[:, i, 2] for i in right_ids])

    z_eps = TEST_SIDE_Z_EPS_NORMALIZED if NORMALIZE_VIDEO_FRAME_COORDS else TEST_SIDE_Z_EPS_PIXELS
    if abs(left_z - right_z) < z_eps:
        return DEFAULT_TEST_SIDE

    return 'left' if left_z < right_z else 'right'
