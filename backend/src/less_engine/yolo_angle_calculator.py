"""
LESS Analiz Sistemi - YOLO Açı Hesaplama Modülü (Backend)
COCO 17-keypoint için biyomekanik hesaplamalar — heel/toe landmark yok.
"""
import numpy as np
from .yolo_config import (
    LEFT_HIP, RIGHT_HIP, LEFT_KNEE, RIGHT_KNEE,
    LEFT_ANKLE, RIGHT_ANKLE, LEFT_SHOULDER, RIGHT_SHOULDER
)


def _side(side):
    if side == 'left':
        return dict(hip=LEFT_HIP, knee=LEFT_KNEE, ankle=LEFT_ANKLE, shoulder=LEFT_SHOULDER)
    return dict(hip=RIGHT_HIP, knee=RIGHT_KNEE, ankle=RIGHT_ANKLE, shoulder=RIGHT_SHOULDER)


def angle_3pt(a, b, c):
    ba = a - b
    bc = c - b
    cos_val = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-8)
    return np.degrees(np.arccos(np.clip(cos_val, -1.0, 1.0)))


def knee_flexion(poses, frame, side):
    s = _side(side)
    return 180.0 - angle_3pt(poses[frame, s['hip'], :2],
                              poses[frame, s['knee'], :2],
                              poses[frame, s['ankle'], :2])


def hip_flexion(poses, frame, side):
    s = _side(side)
    return 180.0 - angle_3pt(poses[frame, s['shoulder'], :2],
                              poses[frame, s['hip'], :2],
                              poses[frame, s['knee'], :2])


def trunk_flexion(poses, frame):
    hip_c = (poses[frame, LEFT_HIP, :2] + poses[frame, RIGHT_HIP, :2]) / 2.0
    sho_c = (poses[frame, LEFT_SHOULDER, :2] + poses[frame, RIGHT_SHOULDER, :2]) / 2.0
    trunk_vec = sho_c - hip_c
    vertical  = np.array([0.0, 1.0])
    cos_val   = np.dot(trunk_vec, vertical) / (np.linalg.norm(trunk_vec) + 1e-8)
    return np.degrees(np.arccos(np.clip(cos_val, -1.0, 1.0)))


def tibia_angle_from_vertical(poses, frame, side):
    """
    Tibia (knee→ankle) vektörünün dikeyden açısı (°). M4 plantar fleksiyon proxy.
    Küçük açı (<eşik) → tibia neredeyse dik → toe-first iniş tahmini.
    Büyük açı (≥eşik) → tibia öne eğik → heel-first iniş tahmini.
    """
    s = _side(side)
    knee  = poses[frame, s['knee'],  :2]
    ankle = poses[frame, s['ankle'], :2]
    tibia = ankle - knee
    norm  = np.linalg.norm(tibia)
    if norm < 1e-6:
        return 0.0
    vertical = np.array([0.0, 1.0])  # normalize coords: Y aşağıya doğru
    return np.degrees(np.arccos(np.clip(np.dot(tibia / norm, vertical), -1.0, 1.0)))


def ankle_contact_type(poses, frame, side):
    """YOLO'da toe/heel yok → 'unknown' döner (geriye dönük uyumluluk için)."""
    return 'unknown'


def frontal_knee_valgus_check(poses, frame, side):
    s = _side(side)
    knee_x = poses[frame, s['knee'],  0]
    foot_x = poses[frame, s['ankle'], 0]
    if side == 'left':
        return knee_x > foot_x
    return knee_x < foot_x


def lateral_trunk_lean(poses, frame):
    hip_cx = (poses[frame, LEFT_HIP,      0] + poses[frame, RIGHT_HIP,      0]) / 2.0
    sho_cx = (poses[frame, LEFT_SHOULDER, 0] + poses[frame, RIGHT_SHOULDER, 0]) / 2.0
    return abs(sho_cx - hip_cx)


def stance_width(poses, frame):
    return abs(poses[frame, LEFT_ANKLE, 0] - poses[frame, RIGHT_ANKLE, 0])


def shoulder_width(poses, frame):
    return abs(poses[frame, LEFT_SHOULDER, 0] - poses[frame, RIGHT_SHOULDER, 0])


def knee_ankle_frontal_offset(poses, frame, side):
    """
    Önden kamerada ankle_x - knee_x farkı.
    Sağ bacak: pozitif → dış rotasyon proxy, negatif → iç rotasyon proxy.
    Sol bacak: işaret ters.
    """
    s = _side(side)
    raw = poses[frame, s['ankle'], 0] - poses[frame, s['knee'], 0]
    return raw if side == 'right' else -raw


def foot_rotation_proxy(poses, frame_ic, frame_mkf, side):
    """
    IC→MKF arasında knee-ankle frontal offset değişimi.
    Pozitif delta → dış rotasyon, negatif delta → iç rotasyon. M9/M10 proxy.
    """
    return knee_ankle_frontal_offset(poses, frame_mkf, side) - \
           knee_ankle_frontal_offset(poses, frame_ic,  side)


def foot_rotation_change(poses, frame_ic, frame_mkf, side):
    """Geriye dönük uyumluluk aliası."""
    return foot_rotation_proxy(poses, frame_ic, frame_mkf, side)


def foot_contact_symmetry(poses, frame, video_width):
    return abs(poses[frame, LEFT_ANKLE, 1] - poses[frame, RIGHT_ANKLE, 1])


def valgus_at_max_flexion(poses, frame_mkf, side):
    s = _side(side)
    knee_x = poses[frame_mkf, s['knee'],  0]
    toe_x  = poses[frame_mkf, s['ankle'], 0]
    if side == 'left':
        return knee_x > toe_x
    return knee_x < toe_x
