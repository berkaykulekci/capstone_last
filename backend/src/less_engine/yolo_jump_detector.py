"""
LESS Analiz Sistemi - YOLO Atlayış Tespit Modülü (Backend)
jump_detector.py'nin YOLO COCO-17 keypoint formatı için uyarlanmış versiyonu.
contact_y = min(left_ankle_y, right_ankle_y)  [heel/toe yok]
"""
import numpy as np
from scipy.signal import savgol_filter, find_peaks
from enum import Enum, auto

from .yolo_config import (
    LEFT_ANKLE, RIGHT_ANKLE, LEFT_HIP, RIGHT_HIP,
    EXPECTED_JUMPS, OUTPUT_DIR,
    AIR_ENTER_RATIO, AIR_EXIT_RATIO,
    IC_SEARCH_BEFORE_FRAMES, IC_SEARCH_AFTER_FRAMES, IC_CONSEC_GROUND_FRAMES,
    BOX_BASELINE_FRAMES, BOX_LEVEL_TOLERANCE_NORM, BOX_LEVEL_TOLERANCE_PIXELS,
    BOX_DROP_MIN_RATIO, BOX_DROP_SEARCH_FRAMES, BOX_DROP_MIN_DISTANCE,
    NORMALIZE_VIDEO_FRAME_COORDS,
    SAVGOL_WINDOW, SAVGOL_POLY,
    PEAK_PROMINENCE, PEAK_DISTANCE, PEAK_WIDTH,
    CONSEC_AIR_FRAMES, RECOVERY_FLEX_THRESHOLD, RECOVERY_STABLE_FRAMES,
    MIN_TAKEOFF_TO_IC, MIN_IC_TO_MKF, MIN_MKF_TO_RECOVERY,
    MKF_SEARCH_WINDOW,
    CONF_W_FLIGHT, CONF_W_PROMINENCE, CONF_W_LANDING_VEL, CONF_W_TEMPORAL,
    CONF_MIN_THRESHOLD, JUMP_MERGE_TOLERANCE
)
from .yolo_angle_calculator import knee_flexion


class Phase(Enum):
    READY     = auto()
    TAKEOFF   = auto()
    AIRBORNE  = auto()
    LANDING   = auto()
    FLEXION   = auto()
    MKF_FOUND = auto()
    RECOVERY  = auto()


def _savgol(arr, window=None, poly=None):
    w = window or SAVGOL_WINDOW
    p = poly   or SAVGOL_POLY
    if len(arr) < w:
        w = len(arr) if len(arr) % 2 == 1 else len(arr) - 1
        if w < p + 1:
            return arr.copy()
    return savgol_filter(arr, w, p)


def _compute_signals(poses, test_side):
    n = len(poses)
    ankle_y_raw   = (poses[:, LEFT_ANKLE, 1] + poses[:, RIGHT_ANKLE, 1]) / 2.0
    contact_y_raw = np.minimum(poses[:, LEFT_ANKLE, 1], poses[:, RIGHT_ANKLE, 1])
    hip_y_raw     = (poses[:, LEFT_HIP, 1] + poses[:, RIGHT_HIP, 1]) / 2.0
    flex_raw      = np.array([knee_flexion(poses, f, test_side) for f in range(n)])

    ankle_y   = _savgol(ankle_y_raw)
    contact_y = _savgol(contact_y_raw)
    hip_y     = _savgol(hip_y_raw)
    flex      = _savgol(flex_raw)

    ankle_vel   = np.gradient(ankle_y)
    ankle_acc   = np.gradient(ankle_vel)
    contact_vel = np.gradient(contact_y)
    contact_acc = np.gradient(contact_vel)
    hip_vel     = np.gradient(hip_y)
    flex_deriv  = np.gradient(flex)

    floor_y  = np.percentile(contact_y, 5)
    ceil_y   = np.percentile(contact_y, 95)
    y_range  = ceil_y - floor_y

    baseline_end = min(n, BOX_BASELINE_FRAMES)
    box_y = float(np.nanmedian(contact_y[:baseline_end])) if baseline_end > 0 else float(ceil_y)
    box_drop_range    = max(0.0, box_y - floor_y)
    box_landing_enter = box_y - (box_drop_range * BOX_DROP_MIN_RATIO)
    air_enter = floor_y + y_range * float(np.clip(AIR_ENTER_RATIO, 0.0, 1.0))
    air_exit  = floor_y + y_range * float(np.clip(AIR_EXIT_RATIO,  0.0, 1.0))

    return {
        'ankle_y': ankle_y, 'ankle_y_raw': ankle_y_raw,
        'contact_y': contact_y, 'contact_y_raw': contact_y_raw,
        'hip_y': hip_y, 'hip_vel': hip_vel,
        'flex': flex, 'flex_raw': flex_raw, 'flex_deriv': flex_deriv,
        'ankle_vel': ankle_vel, 'ankle_acc': ankle_acc,
        'contact_vel': contact_vel, 'contact_acc': contact_acc,
        'air_enter': air_enter, 'air_exit': air_exit,
        'air_enter_ratio': float(np.clip(AIR_ENTER_RATIO, 0.0, 1.0)),
        'air_exit_ratio':  float(np.clip(AIR_EXIT_RATIO,  0.0, 1.0)),
        'floor_y': floor_y, 'ceil_y': ceil_y,
        'box_y': box_y, 'box_landing_enter': box_landing_enter,
        'n': n
    }


def _refine_ic(signals, landing_frame):
    contact_vel = signals['contact_vel']
    contact_acc = signals['contact_acc']
    contact_y   = signals['contact_y']
    n           = signals['n']

    search_start = max(0, landing_frame - IC_SEARCH_BEFORE_FRAMES)
    search_end   = min(n, landing_frame + IC_SEARCH_AFTER_FRAMES)
    if search_end <= search_start:
        return landing_frame

    near_ground = contact_y <= signals['air_exit']
    for frame in range(search_start, search_end):
        stable_end     = min(n, frame + IC_CONSEC_GROUND_FRAMES)
        was_airborne   = frame == 0 or np.any(contact_y[max(0, frame-3):frame] > signals['air_exit'])
        stays_grounded = np.all(near_ground[frame:stable_end])
        braking        = contact_vel[frame] <= 0 or contact_acc[frame] > 0
        if near_ground[frame] and was_airborne and stays_grounded and braking:
            return frame

    grounded = [f for f in range(search_start, search_end) if near_ground[f]]
    if grounded:
        return max(grounded, key=lambda f: contact_acc[f])
    return max(0, min(landing_frame, n - 1))


def _find_mkf_after_ic(signals, ic_frame):
    flex = signals['flex']
    n    = signals['n']
    end  = min(n, ic_frame + MKF_SEARCH_WINDOW)
    if end <= ic_frame + MIN_IC_TO_MKF:
        return ic_frame

    window = flex[ic_frame:end]
    peaks, props = find_peaks(
        window,
        prominence=max(8, PEAK_PROMINENCE * 0.5),
        distance=max(5, PEAK_DISTANCE // 3),
        width=max(2, PEAK_WIDTH // 2)
    )
    if len(peaks) == 0:
        mkf_local = np.argmax(window)
        return (ic_frame + mkf_local) if window[mkf_local] > 20 else ic_frame
    return ic_frame + peaks[np.argmax(props['prominences'])]


def _compute_confidence(jump, signals, all_jumps):
    flex        = signals['flex']
    contact_y   = signals['contact_y']
    contact_vel = signals['contact_vel']
    floor_y     = signals['floor_y']
    ceil_y      = signals['ceil_y']
    start, ic, mkf = jump['start'], jump['ic'], jump['mkf']

    flight_quality = (min(1.0, (np.max(contact_y[start:ic]) - floor_y) / (ceil_y - floor_y + 1e-8))
                      if start < ic else 0.3)
    mkf_flex       = flex[mkf] if mkf < len(flex) else 0
    ic_flex        = flex[ic]  if ic  < len(flex) else 0
    peak_prominence= min(1.0, (mkf_flex - ic_flex) / 80.0)
    ic_vel         = abs(contact_vel[ic]) if ic < len(contact_vel) else 10
    max_vel        = np.max(np.abs(contact_vel)) + 1e-8
    landing_vel_q  = 1.0 - min(1.0, ic_vel / (max_vel * 0.5))
    flight_dur     = max(1, ic - start)
    flex_dur       = max(1, mkf - ic)
    t1 = 1.0 if 5 <= flight_dur <= 40 else 0.5
    t2 = 1.0 if 8 <= flex_dur   <= 50 else 0.5
    temporal       = (t1 + t2) / 2.0

    score = (CONF_W_FLIGHT * flight_quality + CONF_W_PROMINENCE * peak_prominence +
             CONF_W_LANDING_VEL * landing_vel_q + CONF_W_TEMPORAL * temporal)
    return round(min(1.0, max(0.0, score)), 3)


def _method_box_baseline(signals, poses, test_side):
    contact_y = signals['contact_y']
    n         = signals['n']
    if n == 0:
        return []
    box_y      = signals['box_y']
    drop_range = box_y - signals['floor_y']
    if drop_range <= 1e-6:
        return []

    box_tol         = BOX_LEVEL_TOLERANCE_NORM if NORMALIZE_VIDEO_FRAME_COORDS else BOX_LEVEL_TOLERANCE_PIXELS
    landing_enter_y = box_y - (drop_range * BOX_DROP_MIN_RATIO)
    jumps, ready_on_box, last_ic, f = [], True, -BOX_DROP_MIN_DISTANCE, 1

    while f < n and len(jumps) < EXPECTED_JUMPS:
        if contact_y[f] >= box_y - box_tol:
            ready_on_box = True
            f += 1
            continue
        if ready_on_box and contact_y[f] <= landing_enter_y and f - last_ic >= BOX_DROP_MIN_DISTANCE:
            window = contact_y[f:min(n, f + BOX_DROP_SEARCH_FRAMES)]
            if not len(window):
                break
            ic_frame  = f + int(np.argmin(window))
            mkf_frame = _find_mkf_after_ic(signals, ic_frame)
            if mkf_frame <= ic_frame:
                mkf_frame = min(n - 1, ic_frame + MIN_IC_TO_MKF)
            jump = {'start': max(0, f-5), 'ic': ic_frame, 'mkf': mkf_frame,
                    'end': min(n-1, mkf_frame+20), 'method': 'box_baseline'}
            jump['confidence'] = _compute_confidence(jump, signals, jumps)
            jumps.append(jump)
            last_ic, ready_on_box = ic_frame, False
            f = min(n, ic_frame + BOX_DROP_MIN_DISTANCE)
            continue
        f += 1
    return jumps


def _run_fsm(signals, test_side, poses):
    contact_y  = signals['contact_y']
    flex       = signals['flex']
    flex_deriv = signals['flex_deriv']
    air_enter  = signals['air_enter']
    air_exit   = signals['air_exit']
    n          = signals['n']

    state = Phase.READY
    jumps = []
    takeoff_frame = air_count = landing_frame = ic_frame = mkf_frame = recovery_count = 0

    for f in range(n):
        ay, kf, kf_d = contact_y[f], flex[f], flex_deriv[f]

        if state == Phase.READY:
            if ay > air_enter:
                state, takeoff_frame, air_count = Phase.TAKEOFF, f, 1
        elif state == Phase.TAKEOFF:
            if ay > air_enter:
                air_count += 1
                if air_count >= CONSEC_AIR_FRAMES:
                    state = Phase.AIRBORNE
            else:
                state = Phase.READY
        elif state == Phase.AIRBORNE:
            if ay < air_exit:
                state, landing_frame = Phase.LANDING, f
        elif state == Phase.LANDING:
            ic_frame = _refine_ic(signals, landing_frame)
            if ic_frame - takeoff_frame < MIN_TAKEOFF_TO_IC:
                state = Phase.READY
                continue
            state = Phase.FLEXION
        elif state == Phase.FLEXION:
            if kf_d < -0.5 and f > ic_frame + MIN_IC_TO_MKF:
                mkf_frame = _find_mkf_after_ic(signals, ic_frame)
                if mkf_frame - ic_frame < MIN_IC_TO_MKF:
                    mkf_frame = ic_frame + MIN_IC_TO_MKF
                    if mkf_frame >= n:
                        state = Phase.READY
                        continue
                state = Phase.MKF_FOUND
        elif state == Phase.MKF_FOUND:
            if f > mkf_frame + MIN_MKF_TO_RECOVERY:
                state, recovery_count = Phase.RECOVERY, 0
        elif state == Phase.RECOVERY:
            recovery_count = recovery_count + 1 if kf < RECOVERY_FLEX_THRESHOLD else 0
            if recovery_count >= RECOVERY_STABLE_FRAMES:
                jump = {'start': takeoff_frame, 'ic': ic_frame, 'mkf': mkf_frame, 'end': f}
                if jumps and ic_frame <= jumps[-1]['end'] + 5:
                    state = Phase.READY
                    continue
                jump['confidence'] = _compute_confidence(jump, signals, jumps)
                jumps.append(jump)
                state = Phase.READY
                if len(jumps) == EXPECTED_JUMPS:
                    break

    if state in (Phase.MKF_FOUND, Phase.RECOVERY) and len(jumps) < EXPECTED_JUMPS:
        jump = {'start': takeoff_frame, 'ic': ic_frame, 'mkf': mkf_frame,
                'end': min(n-1, mkf_frame+20)}
        if not jumps or ic_frame > jumps[-1]['end'] + 5:
            jump['confidence'] = _compute_confidence(jump, signals, jumps)
            jumps.append(jump)
    return jumps


def _method_peak_first(signals, poses, test_side):
    flex = signals['flex']
    n    = signals['n']
    peaks, _ = find_peaks(flex,
                          prominence=max(10, PEAK_PROMINENCE * 0.7),
                          distance=max(15, PEAK_DISTANCE),
                          width=max(3, PEAK_WIDTH))
    if not len(peaks):
        return []
    jumps = []
    for mkf in peaks:
        ic_start = max(0, mkf - 50)
        window   = flex[ic_start:mkf]
        if not len(window):
            continue
        ic_frame = _refine_ic(signals, ic_start + np.argmin(window))
        if mkf - ic_frame < MIN_IC_TO_MKF or n - mkf < 5:
            continue
        if jumps and ic_frame <= jumps[-1]['mkf'] + 10:
            continue
        jump = {'start': max(0, ic_frame-8), 'ic': ic_frame, 'mkf': mkf,
                'end': min(n-1, mkf+20)}
        jump['confidence'] = _compute_confidence(jump, signals, jumps)
        jumps.append(jump)
        if len(jumps) == EXPECTED_JUMPS:
            break
    return jumps


def _merge_jumps(jump_lists):
    all_jumps = [j for jlist in jump_lists for j in jlist]
    if not all_jumps:
        return []
    all_jumps.sort(key=lambda x: x['ic'])
    merged = [all_jumps[0]]
    for j in all_jumps[1:]:
        prev = merged[-1]
        if (j['ic'] - prev['ic']) < JUMP_MERGE_TOLERANCE:
            if j.get('confidence', 0) > prev.get('confidence', 0):
                merged[-1] = j
        elif j['mkf'] - j['ic'] >= MIN_IC_TO_MKF:
            merged.append(j)
    filtered = [j for j in merged if j.get('confidence', 0.5) >= CONF_MIN_THRESHOLD]
    if len(filtered) < EXPECTED_JUMPS and len(merged) >= EXPECTED_JUMPS:
        filtered = sorted(sorted(merged, key=lambda x: x.get('confidence', 0),
                                 reverse=True)[:EXPECTED_JUMPS], key=lambda x: x['ic'])
    return filtered[:EXPECTED_JUMPS]


def detect_jumps(poses, test_side='right', label='', debug=False):
    """
    YOLO pose dizisinden 3 atlayışı tespit eder.
    Backend'de debug=False varsayılan (dosya yazmaz).
    """
    signals = _compute_signals(poses, test_side)

    jumps_box = _method_box_baseline(signals, poses, test_side)
    if len(jumps_box) >= EXPECTED_JUMPS:
        result = jumps_box[:EXPECTED_JUMPS]
        print(f"  [{label}][YOLO] Kutu-referans → {len(result)} iniş ✓")
        return result

    jumps_fsm = _run_fsm(signals, test_side, poses)
    if len(jumps_fsm) >= EXPECTED_JUMPS:
        result = jumps_fsm[:EXPECTED_JUMPS]
        print(f"  [{label}][YOLO] FSM → {len(result)} atlayış ✓")
        return result

    jumps_peak = _method_peak_first(signals, poses, test_side)
    if len(jumps_peak) >= EXPECTED_JUMPS:
        result = jumps_peak[:EXPECTED_JUMPS]
        print(f"  [{label}][YOLO] Peak-first → {len(result)} atlayış ✓")
        return result

    merged = _merge_jumps([jumps_box, jumps_fsm, jumps_peak])
    print(f"  [{label}][YOLO] Birleştirme → {len(merged)} atlayış")
    return merged
