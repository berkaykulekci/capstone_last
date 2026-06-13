"""
Benchmark - Limb Utils
Femur/tibia uzunluğu ve diz/kalça açısı hesaplamaları.
Her iki model (MediaPipe 33 kp, YOLO 17 kp) için kp_map dict'i ile çalışır.
"""
import numpy as np
from typing import Dict, Tuple


# ── Keypoint Haritaları ──────────────────────────────────────────────────────

MP_KP_MAP = {
    'left_shoulder':  11,
    'right_shoulder': 12,
    'left_hip':       23,
    'right_hip':      24,
    'left_knee':      25,
    'right_knee':     26,
    'left_ankle':     27,
    'right_ankle':    28,
}

YOLO_KP_MAP = {
    'left_shoulder':  5,
    'right_shoulder': 6,
    'left_hip':       11,
    'right_hip':      12,
    'left_knee':      13,
    'right_knee':     14,
    'left_ankle':     15,
    'right_ankle':    16,
}


# ── Yardımcı Fonksiyonlar ────────────────────────────────────────────────────

def _xy(poses: np.ndarray, idx: int) -> np.ndarray:
    """poses[:, idx, :2] → (N, 2)"""
    return poses[:, idx, :2].astype(float)


def _vec_angle_degrees(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> np.ndarray:
    """
    b noktasındaki açıyı hesaplar (a→b→c üçgeni, derece).
    Tüm diziler (N, 2) şeklindedir; NaN içeren satırlar NaN döner.
    """
    ba = a - b  # (N, 2)
    bc = c - b
    dot = np.sum(ba * bc, axis=1)
    norm_ba = np.linalg.norm(ba, axis=1)
    norm_bc = np.linalg.norm(bc, axis=1)
    denom = norm_ba * norm_bc
    with np.errstate(invalid='ignore', divide='ignore'):
        cos_a = np.where(denom > 1e-9, dot / denom, np.nan)
    cos_a = np.clip(cos_a, -1.0, 1.0)
    return np.degrees(np.arccos(cos_a))


# ── Ana Fonksiyonlar ─────────────────────────────────────────────────────────

def compute_limb_lengths(
    poses: np.ndarray,
    kp_map: Dict[str, int],
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Her frame için femur (hip→knee) ve tibia (knee→ankle) uzunluklarını döner.
    Sol ve sağ tarafın ortalaması alınır.

    Parameters
    ----------
    poses   : (N, K, 3) — x, y, [z veya conf]; x/y normalize (0-1)
    kp_map  : keypoint adı → indeks eşleşmesi

    Returns
    -------
    femur_lengths : (N,) — normalize birimde
    tibia_lengths : (N,) — normalize birimde
    """
    lh = _xy(poses, kp_map['left_hip'])
    rh = _xy(poses, kp_map['right_hip'])
    lk = _xy(poses, kp_map['left_knee'])
    rk = _xy(poses, kp_map['right_knee'])
    la = _xy(poses, kp_map['left_ankle'])
    ra = _xy(poses, kp_map['right_ankle'])

    femur_l = np.linalg.norm(lh - lk, axis=1)
    femur_r = np.linalg.norm(rh - rk, axis=1)
    femur = np.where(
        np.isnan(femur_l) | np.isnan(femur_r),
        np.nanmean(np.stack([femur_l, femur_r], axis=1), axis=1),
        (femur_l + femur_r) / 2.0
    )

    tibia_l = np.linalg.norm(lk - la, axis=1)
    tibia_r = np.linalg.norm(rk - ra, axis=1)
    tibia = np.where(
        np.isnan(tibia_l) | np.isnan(tibia_r),
        np.nanmean(np.stack([tibia_l, tibia_r], axis=1), axis=1),
        (tibia_l + tibia_r) / 2.0
    )

    return femur, tibia


def compute_joint_angles(
    poses: np.ndarray,
    kp_map: Dict[str, int],
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Her frame için diz fleksiyon ve kalça fleksiyon açılarını döner (derece).
    Sol/sağ tarafın ortalaması alınır.

    Returns
    -------
    knee_angle : (N,) — hip→knee→ankle açısı (0° = tam düzgün, 180° = tam bükülü)
    hip_angle  : (N,) — shoulder→hip→knee açısı; omuz yoksa NaN
    """
    lh = _xy(poses, kp_map['left_hip'])
    rh = _xy(poses, kp_map['right_hip'])
    lk = _xy(poses, kp_map['left_knee'])
    rk = _xy(poses, kp_map['right_knee'])
    la = _xy(poses, kp_map['left_ankle'])
    ra = _xy(poses, kp_map['right_ankle'])

    knee_l = _vec_angle_degrees(lh, lk, la)
    knee_r = _vec_angle_degrees(rh, rk, ra)
    knee_angle = np.nanmean(np.stack([knee_l, knee_r], axis=1), axis=1)

    if 'left_shoulder' in kp_map and 'right_shoulder' in kp_map:
        ls = _xy(poses, kp_map['left_shoulder'])
        rs = _xy(poses, kp_map['right_shoulder'])
        hip_l = _vec_angle_degrees(ls, lh, lk)
        hip_r = _vec_angle_degrees(rs, rh, rk)
        hip_angle = np.nanmean(np.stack([hip_l, hip_r], axis=1), axis=1)
    else:
        hip_angle = np.full(len(poses), np.nan)

    return knee_angle, hip_angle
