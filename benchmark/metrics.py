"""
Benchmark - Metrics
Ground-truth gerektirmeyen pose kalitesi metrikleri.

FPS / Latency
-------------
  fps          = total_processed_frames / total_inference_time_s
  latency_ms   = mean(per_frame_inference_time_ms)

Missing Keypoint Rate
---------------------
  missing_kp_pct = NaN_count / (N_frames × N_keypoints) × 100
  (interpolasyon öncesi ham poses üzerinde hesaplanır)

Jitter
------
  coord_std  : frame-to-frame koordinat değişimlerinin std'si
  accel_mean : ikinci türevin ortalama mutlak değeri (jerk proxy)

Limb-Length Consistency
-----------------------
  self_std      : femur/tibia oranının kendi baseline'ından sapmasının std'si
  anthropo_pct  : femur/tibia oranı [0.75, 1.05] dışında kalan frame yüzdesi

Biomechanical Plausibility
--------------------------
  self_std      : diz açısının kendi baseline'ından sapmasının std'si
  anthropo_pct  : diz [0°,170°] veya kalça [-20°,140°] dışında kalan frame %

Mean Confidence
---------------
  MediaPipe : landmark.visibility
  YOLO      : keypoint confidence skoru
"""
import numpy as np
from typing import Dict, List, Tuple

from limb_utils import compute_limb_lengths, compute_joint_angles

# ── Sabitler ─────────────────────────────────────────────────────────────────
LIMB_RATIO_LOW  = 0.75   # femur/tibia alt sınır  (0.9 - 0.15)
LIMB_RATIO_HIGH = 1.05   # femur/tibia üst sınır  (0.9 + 0.15)
BASELINE_FRAMES = 20     # self-consistency referans frame sayısı
KNEE_MIN, KNEE_MAX = 0.0,  170.0   # derece
HIP_MIN,  HIP_MAX  = -20.0, 140.0  # derece


# ── FPS / Latency ─────────────────────────────────────────────────────────────

def compute_fps_and_latency(frame_times_ms: List[float]) -> Tuple[float, float]:
    """
    Parameters
    ----------
    frame_times_ms : Her frame'in inference süresi (ms cinsinden).

    Returns
    -------
    fps        : total_processed_frames / total_inference_time_s
    latency_ms : mean(per_frame_inference_time_ms)
    """
    if not frame_times_ms:
        return 0.0, 0.0
    total_ms = float(sum(frame_times_ms))
    n = len(frame_times_ms)
    fps = n / (total_ms / 1000.0) if total_ms > 0 else 0.0
    latency_ms = total_ms / n
    return fps, latency_ms


# ── Missing Keypoint Rate ─────────────────────────────────────────────────────

def compute_missing_kp_rate(poses_raw: np.ndarray) -> float:
    """
    Parameters
    ----------
    poses_raw : (N_frames, N_kp, ≥2) — interpolasyon ÖNCESİ ham dizi (NaN içerir).

    Returns
    -------
    missing_kp_pct : NaN_count / (N_frames × N_kp) × 100
    """
    xy = poses_raw[:, :, :2]
    nan_count = int(np.sum(np.isnan(xy[:, :, 0])))  # x NaN ise nokta eksik
    total     = xy.shape[0] * xy.shape[1]
    return float(nan_count) / float(total) * 100.0 if total > 0 else 0.0


# ── Mean Confidence ───────────────────────────────────────────────────────────

def compute_mean_confidence(conf_array: np.ndarray) -> float:
    """
    Parameters
    ----------
    conf_array : (N_frames, N_kp) — visibility (MediaPipe) veya kp conf (YOLO).
                 NaN değerler hariç tutulur.
    """
    valid = conf_array[~np.isnan(conf_array)]
    return float(np.mean(valid)) if len(valid) > 0 else 0.0


# ── Jitter ────────────────────────────────────────────────────────────────────

def compute_jitter(poses: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Interpolasyon SONRASI poses üzerinde hesaplanır.

    Parameters
    ----------
    poses : (N_frames, N_kp, ≥2)

    Returns
    -------
    coord_diff   : (N_frames,) — frame-to-frame ortalama |Δxy| (frame 0 = NaN)
    accel_series : (N_frames,) — |Δ²xy| ivme proxy (frame 0,1 = NaN)
    """
    xy = poses[:, :, :2].astype(float)  # (N, K, 2)

    # Hız (1. türev)
    diff1 = np.diff(xy, axis=0)         # (N-1, K, 2)
    speed = np.nanmean(np.linalg.norm(diff1, axis=2), axis=1)  # (N-1,)

    # İvme (2. türev)
    diff2 = np.diff(diff1, axis=0)      # (N-2, K, 2)
    accel = np.nanmean(np.linalg.norm(diff2, axis=2), axis=1)  # (N-2,)

    N = poses.shape[0]
    coord_series = np.full(N, np.nan)
    coord_series[1:] = speed

    accel_series = np.full(N, np.nan)
    accel_series[2:] = accel

    return coord_series, accel_series


def aggregate_jitter(poses: np.ndarray) -> Tuple[float, float]:
    """Per-video özet: coord_std ve accel_mean."""
    coord_s, accel_s = compute_jitter(poses)
    coord_std  = float(np.nanstd(coord_s))
    accel_mean = float(np.nanmean(accel_s))
    return coord_std, accel_mean


# ── Limb-Length Consistency ───────────────────────────────────────────────────

def compute_limb_series(
    poses: np.ndarray,
    kp_map: Dict[str, int],
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Returns femur, tibia uzunluğu ve ratio serileri (her frame için).
    """
    femur, tibia = compute_limb_lengths(poses, kp_map)
    with np.errstate(invalid='ignore', divide='ignore'):
        ratio = np.where(tibia > 1e-9, femur / tibia, np.nan)
    return femur, tibia, ratio


def compute_limb_consistency(
    poses: np.ndarray,
    kp_map: Dict[str, int],
    baseline_frames: int = BASELINE_FRAMES,
) -> Tuple[float, float]:
    """
    Returns
    -------
    self_std     : ratio'nun kendi baseline ortalamasından sapmasının std'si
    anthropo_pct : ratio [LIMB_RATIO_LOW, LIMB_RATIO_HIGH] dışında kalan frame %
    """
    _, _, ratio = compute_limb_series(poses, kp_map)

    # Self-consistency
    n_ref = min(baseline_frames, len(ratio))
    ref_mean = float(np.nanmean(ratio[:n_ref]))
    deviation = ratio - ref_mean
    self_std = float(np.nanstd(deviation))

    # Anthropometric
    valid = ratio[~np.isnan(ratio)]
    if len(valid) == 0:
        anthropo_pct = 0.0
    else:
        out = np.sum((valid < LIMB_RATIO_LOW) | (valid > LIMB_RATIO_HIGH))
        anthropo_pct = float(out) / float(len(valid)) * 100.0

    return self_std, anthropo_pct


# ── Biomechanical Plausibility ────────────────────────────────────────────────

def compute_angle_series(
    poses: np.ndarray,
    kp_map: Dict[str, int],
) -> Tuple[np.ndarray, np.ndarray]:
    """Her frame için knee ve hip açı serilerini döner."""
    return compute_joint_angles(poses, kp_map)


def compute_biomech_plausibility(
    poses: np.ndarray,
    kp_map: Dict[str, int],
    baseline_frames: int = BASELINE_FRAMES,
) -> Tuple[float, float]:
    """
    Returns
    -------
    self_std     : diz açısının kendi baseline'ından sapmasının std'si
    anthropo_pct : diz veya kalça açısı biyomekanik sınır dışında kalan frame %
    """
    knee_angle, hip_angle = compute_joint_angles(poses, kp_map)

    # Self-consistency (diz açısı üzerinden)
    n_ref = min(baseline_frames, len(knee_angle))
    ref_knee = float(np.nanmean(knee_angle[:n_ref]))
    self_std = float(np.nanstd(knee_angle - ref_knee))

    # Anthropometric
    kv = knee_angle[~np.isnan(knee_angle)]
    hv = hip_angle[~np.isnan(hip_angle)]

    knee_out = int(np.sum((kv < KNEE_MIN) | (kv > KNEE_MAX))) if len(kv) > 0 else 0
    hip_out  = int(np.sum((hv < HIP_MIN)  | (hv > HIP_MAX)))  if len(hv) > 0 else 0

    total_valid = len(kv) + len(hv)
    anthropo_pct = (float(knee_out + hip_out) / float(total_valid) * 100.0
                    if total_valid > 0 else 0.0)

    return self_std, anthropo_pct
