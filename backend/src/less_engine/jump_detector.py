"""
LESS Analiz Sistemi - Atlayış Tespit Modülü v2
Finite State Machine (FSM) tabanlı biyomekanik drop-jump tespiti.

Önceki event-based yaklaşım yerine movement-phase-based mantık kullanır:
  movement phase → biomechanical validation → event

Özellikler:
  - Hysteresis çift-eşik (jitter eliminasyonu)
  - Savitzky-Golay filtre (phase-lag'sız smoothing)
  - scipy.signal.find_peaks ile MKF tespiti
  - Velocity/acceleration tabanlı IC tespiti
  - 7 state'li FSM
  - Temporal biyomekanik kısıtlar
  - Confidence scoring
  - Debug görselleştirme
"""
import numpy as np
from scipy.signal import savgol_filter, find_peaks
from enum import Enum, auto

from .config import (
    LEFT_ANKLE, RIGHT_ANKLE, LEFT_HIP, RIGHT_HIP,
    LEFT_HEEL, RIGHT_HEEL, LEFT_FOOT_INDEX, RIGHT_FOOT_INDEX,
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
from .angle_calculator import knee_flexion


# ═══════════════════════════════════════════
#  FSM STATE TANIMI
# ═══════════════════════════════════════════

class Phase(Enum):
    READY = auto()
    TAKEOFF = auto()
    AIRBORNE = auto()
    LANDING = auto()
    FLEXION = auto()
    MKF_FOUND = auto()
    RECOVERY = auto()


# ═══════════════════════════════════════════
#  SİNYAL İŞLEME
# ═══════════════════════════════════════════

def _savgol(arr, window=None, poly=None):
    """Phase-lag'sız Savitzky-Golay smoothing."""
    w = window or SAVGOL_WINDOW
    p = poly or SAVGOL_POLY
    if len(arr) < w:
        w = len(arr) if len(arr) % 2 == 1 else len(arr) - 1
        if w < p + 1:
            return arr.copy()
    return savgol_filter(arr, w, p)


def _compute_signals(poses, test_side):
    """Tüm sinyalleri bir kerede hesaplar ve cache'ler."""
    n = len(poses)

    # Ham sinyaller
    ankle_y_raw = (poses[:, LEFT_ANKLE, 1] + poses[:, RIGHT_ANKLE, 1]) / 2.0
    foot_points_y = poses[:, [LEFT_ANKLE, RIGHT_ANKLE, LEFT_HEEL, RIGHT_HEEL, LEFT_FOOT_INDEX, RIGHT_FOOT_INDEX], 1]
    contact_y_raw = np.nanmin(foot_points_y, axis=1)
    hip_y_raw = (poses[:, LEFT_HIP, 1] + poses[:, RIGHT_HIP, 1]) / 2.0
    flex_raw = np.array([knee_flexion(poses, f, test_side) for f in range(n)])

    # Savitzky-Golay smoothing
    ankle_y = _savgol(ankle_y_raw)
    contact_y = _savgol(contact_y_raw)
    hip_y = _savgol(hip_y_raw)
    flex = _savgol(flex_raw)

    # Türevler (velocity, acceleration)
    ankle_vel = np.gradient(ankle_y)
    ankle_acc = np.gradient(ankle_vel)
    contact_vel = np.gradient(contact_y)
    contact_acc = np.gradient(contact_vel)
    hip_vel = np.gradient(hip_y)
    flex_deriv = np.gradient(flex)

    # Hysteresis eşikleri
    floor_y = np.percentile(contact_y, 5)
    ceil_y = np.percentile(contact_y, 95)
    y_range = ceil_y - floor_y
    baseline_end = min(n, BOX_BASELINE_FRAMES)
    box_y = float(np.nanmedian(contact_y[:baseline_end])) if baseline_end > 0 else float(ceil_y)
    box_drop_range = max(0.0, box_y - floor_y)
    box_landing_enter = box_y - (box_drop_range * BOX_DROP_MIN_RATIO)
    air_enter_ratio = float(np.clip(AIR_ENTER_RATIO, 0.0, 1.0))
    air_exit_ratio = float(np.clip(AIR_EXIT_RATIO, 0.0, 1.0))
    air_enter = floor_y + y_range * air_enter_ratio
    air_exit = floor_y + y_range * air_exit_ratio

    return {
        'ankle_y': ankle_y, 'ankle_y_raw': ankle_y_raw,
        'contact_y': contact_y, 'contact_y_raw': contact_y_raw,
        'hip_y': hip_y, 'hip_vel': hip_vel,
        'flex': flex, 'flex_raw': flex_raw, 'flex_deriv': flex_deriv,
        'ankle_vel': ankle_vel, 'ankle_acc': ankle_acc,
        'contact_vel': contact_vel, 'contact_acc': contact_acc,
        'air_enter': air_enter, 'air_exit': air_exit,
        'air_enter_ratio': air_enter_ratio, 'air_exit_ratio': air_exit_ratio,
        'floor_y': floor_y, 'ceil_y': ceil_y,
        'box_y': box_y, 'box_landing_enter': box_landing_enter,
        'n': n
    }


# ═══════════════════════════════════════════
#  IC TESPİTİ (Velocity/Acceleration tabanlı)
# ═══════════════════════════════════════════

def _refine_ic(signals, landing_frame):
    """
    Landing frame civarında biyomekanik IC'yi belirler.

    IC = ayağın yere ilk temas anı:
      1. ankle velocity'nin sıfıra yaklaştığı frame
      2. acceleration spike ile doğrulama
    """
    contact_vel = signals['contact_vel']
    contact_acc = signals['contact_acc']
    contact_y = signals['contact_y']
    n = signals['n']

    # Landing frame etrafında arama penceresi
    search_start = max(0, landing_frame - IC_SEARCH_BEFORE_FRAMES)
    search_end = min(n, landing_frame + IC_SEARCH_AFTER_FRAMES)

    if search_end <= search_start:
        return landing_frame

    near_ground = contact_y <= signals['air_exit']

    # İlk temas: havadaki ayak sinyali yere eşik altına iner ve kısa süre yerde kalır.
    for frame in range(search_start, search_end):
        stable_end = min(n, frame + IC_CONSEC_GROUND_FRAMES)
        was_airborne = frame == 0 or np.any(contact_y[max(0, frame - 3):frame] > signals['air_exit'])
        stays_grounded = np.all(near_ground[frame:stable_end])
        descending_or_braking = contact_vel[frame] <= 0 or contact_acc[frame] > 0
        if near_ground[frame] and was_airborne and stays_grounded and descending_or_braking:
            return frame

    # Fallback: yere yakın kareler içinde iniş ivmesi en belirgin olanı seç.
    grounded = [f for f in range(search_start, search_end) if near_ground[f]]
    if grounded:
        return max(grounded, key=lambda f: contact_acc[f])

    return max(0, min(landing_frame, n - 1))


# ═══════════════════════════════════════════
#  MKF TESPİTİ (find_peaks tabanlı)
# ═══════════════════════════════════════════

def _find_mkf_peaks(signals):
    """scipy.find_peaks ile tüm MKF adaylarını bulur."""
    flex = signals['flex']

    peaks, properties = find_peaks(
        flex,
        prominence=PEAK_PROMINENCE,
        distance=PEAK_DISTANCE,
        width=PEAK_WIDTH
    )

    return peaks, properties


def _find_mkf_after_ic(signals, ic_frame):
    """IC'den sonraki pencerede en belirgin MKF'yi find_peaks ile bulur."""
    flex = signals['flex']
    n = signals['n']
    end = min(n, ic_frame + MKF_SEARCH_WINDOW)

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
        # Fallback: basit argmax
        mkf_local = np.argmax(window)
        if window[mkf_local] > 20:
            return ic_frame + mkf_local
        return ic_frame

    # En yüksek prominence'lı peak'i seç
    best_idx = np.argmax(props['prominences'])
    return ic_frame + peaks[best_idx]


# ═══════════════════════════════════════════
#  CONFIDENCE SCORE
# ═══════════════════════════════════════════

def _compute_confidence(jump, signals, all_jumps):
    """
    Her jump için 0-1 arası confidence score hesaplar.

    score = 0.35 * flight_quality
          + 0.30 * peak_prominence
          + 0.20 * landing_velocity_quality
          + 0.15 * temporal_consistency
    """
    flex = signals['flex']
    contact_y = signals['contact_y']
    contact_vel = signals['contact_vel']
    floor_y = signals['floor_y']
    ceil_y = signals['ceil_y']

    start, ic, mkf = jump['start'], jump['ic'], jump['mkf']

    # 1. Flight quality: havadayken ayak temas sinyali yeterince yükseldi mi?
    if start < ic:
        flight_peak = np.max(contact_y[start:ic])
        flight_range = ceil_y - floor_y
        flight_quality = min(1.0, (flight_peak - floor_y) / (flight_range + 1e-8))
    else:
        flight_quality = 0.3

    # 2. Peak prominence: MKF'deki fleksiyon ne kadar belirgin?
    mkf_flex = flex[mkf] if mkf < len(flex) else 0
    ic_flex = flex[ic] if ic < len(flex) else 0
    prom = mkf_flex - ic_flex
    peak_prominence = min(1.0, prom / 80.0)

    # 3. Landing velocity quality: IC anında velocity düşük mü?
    ic_vel = abs(contact_vel[ic]) if ic < len(contact_vel) else 10
    max_vel = np.max(np.abs(contact_vel)) + 1e-8
    landing_vel_quality = 1.0 - min(1.0, ic_vel / (max_vel * 0.5))

    # 4. Temporal consistency: beklenen sürelere ne kadar uyuyor?
    flight_dur = max(1, ic - start)
    flex_dur = max(1, mkf - ic)
    # Normal drop-jump: 5-30 frame flight, 10-40 frame flexion
    t1 = 1.0 if 5 <= flight_dur <= 40 else 0.5
    t2 = 1.0 if 8 <= flex_dur <= 50 else 0.5
    temporal_consistency = (t1 + t2) / 2.0

    score = (CONF_W_FLIGHT * flight_quality +
             CONF_W_PROMINENCE * peak_prominence +
             CONF_W_LANDING_VEL * landing_vel_quality +
             CONF_W_TEMPORAL * temporal_consistency)

    return round(min(1.0, max(0.0, score)), 3)


# ═══════════════════════════════════════════
#  KUTU REFERANSINA GÖRE İNİŞ TESPİTİ
# ═══════════════════════════════════════════

def _method_box_baseline(signals, poses, test_side):
    """
    Başlangıç kutu yüksekliğini 0 kabul eder.
    Ayak temas sinyali bu seviyeden en negatif konuma indiğinde IC olarak işaretler.

    Bu yöntem tarif edilen protokole göre yalnızca kutu seviyesinden başlayan
    düşüşleri yakalar; yerde yapılan ek zıplamaları ayrı LESS atlayışı saymaz.
    """
    contact_y = signals['contact_y']
    n = signals['n']
    if n == 0:
        return []

    box_y = signals['box_y']
    ground_y = signals['floor_y']
    drop_range = box_y - ground_y
    if drop_range <= 1e-6:
        return []

    box_tol = BOX_LEVEL_TOLERANCE_NORM if NORMALIZE_VIDEO_FRAME_COORDS else BOX_LEVEL_TOLERANCE_PIXELS
    landing_enter_y = box_y - (drop_range * BOX_DROP_MIN_RATIO)
    jumps = []
    ready_on_box = True
    last_ic = -BOX_DROP_MIN_DISTANCE
    f = 1

    while f < n and len(jumps) < EXPECTED_JUMPS:
        near_box = contact_y[f] >= box_y - box_tol

        if near_box:
            ready_on_box = True
            f += 1
            continue

        if ready_on_box and contact_y[f] <= landing_enter_y and f - last_ic >= BOX_DROP_MIN_DISTANCE:
            search_end = min(n, f + BOX_DROP_SEARCH_FRAMES)
            window = contact_y[f:search_end]
            if len(window) == 0:
                break

            ic_frame = f + int(np.argmin(window))

            mkf_frame = _find_mkf_after_ic(signals, ic_frame)
            if mkf_frame <= ic_frame:
                mkf_frame = min(n - 1, ic_frame + MIN_IC_TO_MKF)

            start_frame = max(0, f - 5)
            jump = {
                'start': start_frame,
                'ic': ic_frame,
                'mkf': mkf_frame,
                'end': min(n - 1, mkf_frame + 20),
                'method': 'box_baseline'
            }
            jump['confidence'] = _compute_confidence(jump, signals, jumps)
            jumps.append(jump)

            last_ic = ic_frame
            ready_on_box = False
            f = min(n, ic_frame + BOX_DROP_MIN_DISTANCE)
            continue

        f += 1

    return jumps


# ═══════════════════════════════════════════
#  FSM TABANLI ATLAYIŞ TESPİTİ
# ═══════════════════════════════════════════

def _run_fsm(signals, test_side, poses):
    """
    7 state'li Finite State Machine ile atlayış tespiti.

    States: READY → TAKEOFF → AIRBORNE → LANDING → FLEXION → MKF_FOUND → RECOVERY → READY
    """
    contact_y = signals['contact_y']
    flex = signals['flex']
    flex_deriv = signals['flex_deriv']
    air_enter = signals['air_enter']
    air_exit = signals['air_exit']
    n = signals['n']

    state = Phase.READY
    jumps = []

    # Geçici değişkenler
    takeoff_frame = 0
    air_count = 0
    landing_frame = 0
    ic_frame = 0
    mkf_frame = 0
    recovery_count = 0

    for f in range(n):
        ay = contact_y[f]
        kf = flex[f]
        kf_d = flex_deriv[f]

        if state == Phase.READY:
            if ay > air_enter:
                state = Phase.TAKEOFF
                takeoff_frame = f
                air_count = 1

        elif state == Phase.TAKEOFF:
            if ay > air_enter:
                air_count += 1
                if air_count >= CONSEC_AIR_FRAMES:
                    state = Phase.AIRBORNE
            else:
                # Jitter — henüz havalanmadı, geri dön
                state = Phase.READY

        elif state == Phase.AIRBORNE:
            if ay < air_exit:
                state = Phase.LANDING
                landing_frame = f

        elif state == Phase.LANDING:
            # IC'yi refine et
            ic_frame = _refine_ic(signals, landing_frame)

            # Temporal kısıt: takeoff → IC
            if ic_frame - takeoff_frame < MIN_TAKEOFF_TO_IC:
                state = Phase.READY
                continue

            state = Phase.FLEXION

        elif state == Phase.FLEXION:
            # Diz fleksiyonu artıyor mu?
            if kf_d < -0.5 and f > ic_frame + MIN_IC_TO_MKF:
                # Fleksiyon azalmaya başladı → MKF noktasını bul
                mkf_frame = _find_mkf_after_ic(signals, ic_frame)

                # Temporal kısıt: IC → MKF
                if mkf_frame - ic_frame < MIN_IC_TO_MKF:
                    mkf_frame = ic_frame + MIN_IC_TO_MKF
                    if mkf_frame >= n:
                        state = Phase.READY
                        continue

                state = Phase.MKF_FOUND

        elif state == Phase.MKF_FOUND:
            # MKF sonrası fleksiyon azalıyor
            if f > mkf_frame + MIN_MKF_TO_RECOVERY:
                state = Phase.RECOVERY
                recovery_count = 0

        elif state == Phase.RECOVERY:
            if kf < RECOVERY_FLEX_THRESHOLD:
                recovery_count += 1
            else:
                recovery_count = 0

            if recovery_count >= RECOVERY_STABLE_FRAMES:
                # Jump tamamlandı!
                jump = {
                    'start': takeoff_frame,
                    'ic': ic_frame,
                    'mkf': mkf_frame,
                    'end': f
                }

                # Önceki jump ile örtüşme kontrolü
                if jumps and ic_frame <= jumps[-1]['end'] + 5:
                    state = Phase.READY
                    continue

                jump['confidence'] = _compute_confidence(jump, signals, jumps)
                jumps.append(jump)
                state = Phase.READY

                if len(jumps) == EXPECTED_JUMPS:
                    break

    # FSM tamamlanmadan kalan devam eden atlayışı kaydet
    if state in (Phase.MKF_FOUND, Phase.RECOVERY) and len(jumps) < EXPECTED_JUMPS:
        jump = {
            'start': takeoff_frame,
            'ic': ic_frame,
            'mkf': mkf_frame,
            'end': min(n - 1, mkf_frame + 20)
        }
        if not jumps or ic_frame > jumps[-1]['end'] + 5:
            jump['confidence'] = _compute_confidence(jump, signals, jumps)
            jumps.append(jump)

    return jumps


# ═══════════════════════════════════════════
#  PEAK-FIRST YEDEK METOT
# ═══════════════════════════════════════════

def _method_peak_first(signals, poses, test_side):
    """
    FSM bulamazsa yedek: önce find_peaks ile MKF'leri bul, sonra IC'yi türet.
    """
    flex = signals['flex']
    n = signals['n']

    peaks, props = find_peaks(
        flex,
        prominence=max(10, PEAK_PROMINENCE * 0.7),
        distance=max(15, PEAK_DISTANCE),
        width=max(3, PEAK_WIDTH)
    )

    if len(peaks) == 0:
        return []

    jumps = []
    for i, mkf in enumerate(peaks):
        # IC: MKF'den geriye doğru minimum fleksiyon
        ic_start = max(0, mkf - 50)
        window = flex[ic_start:mkf]
        if len(window) == 0:
            continue
        ic_frame = ic_start + np.argmin(window)

        # IC'yi velocity ile refine et
        ic_frame = _refine_ic(signals, ic_frame)

        # Temporal kısıtlar
        if mkf - ic_frame < MIN_IC_TO_MKF:
            continue
        if n - mkf < 5:
            continue

        start = max(0, ic_frame - 8)
        if jumps and ic_frame <= jumps[-1]['mkf'] + 10:
            continue

        jump = {
            'start': start,
            'ic': ic_frame,
            'mkf': mkf,
            'end': min(n - 1, mkf + 20)
        }
        jump['confidence'] = _compute_confidence(jump, signals, jumps)
        jumps.append(jump)

        if len(jumps) == EXPECTED_JUMPS:
            break

    return jumps


# ═══════════════════════════════════════════
#  MERGE SİSTEMİ
# ═══════════════════════════════════════════

def _merge_jumps(jump_lists):
    """
    Birden fazla metodun sonuçlarını birleştirir.
    Kriterler: temporal overlap, confidence score, phase consistency, duration similarity.
    """
    all_jumps = []
    for jlist in jump_lists:
        all_jumps.extend(jlist)

    if not all_jumps:
        return []

    # IC'ye göre sırala
    all_jumps.sort(key=lambda x: x['ic'])

    # Yakın olanları birleştir (yüksek confidence kalır)
    merged = [all_jumps[0]]
    for j in all_jumps[1:]:
        prev = merged[-1]

        # Temporal overlap kontrolü
        overlap = (j['ic'] - prev['ic']) < JUMP_MERGE_TOLERANCE

        if overlap:
            # Yüksek confidence'lı olanı tut
            if j.get('confidence', 0) > prev.get('confidence', 0):
                merged[-1] = j
        else:
            # Duration similarity: aşırı kısa/uzun jump'ları ele
            duration = j['mkf'] - j['ic']
            if duration >= MIN_IC_TO_MKF:
                merged.append(j)

    # Confidence threshold ile filtrele
    filtered = [j for j in merged if j.get('confidence', 0.5) >= CONF_MIN_THRESHOLD]

    # Yeterli sonuç yoksa threshold'u düşür
    if len(filtered) < EXPECTED_JUMPS and len(merged) >= EXPECTED_JUMPS:
        merged.sort(key=lambda x: x.get('confidence', 0), reverse=True)
        filtered = merged[:EXPECTED_JUMPS]
        filtered.sort(key=lambda x: x['ic'])

    return filtered[:EXPECTED_JUMPS]


# ═══════════════════════════════════════════
#  DEBUG GÖRSELLEŞTİRME
# ═══════════════════════════════════════════

def _generate_debug_plots(signals, jumps, label):
    """Her metot için sinyal grafikleri + tespit noktaları çizer."""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        print(f"  [{label}] matplotlib yüklü değil, debug plot atlanıyor.")
        return

    import os
    n = signals['n']
    frames = np.arange(n)

    fig, axes = plt.subplots(4, 1, figsize=(16, 12), sharex=True)
    fig.suptitle(f'Drop-Jump Detection Debug — {label}', fontsize=14, fontweight='bold')

    # 1. Ankle Y + hysteresis eşikleri
    ax = axes[0]
    ax.plot(frames, signals['contact_y'], 'b-', linewidth=0.8, label='contact_y (savgol)')
    ax.plot(frames, signals['contact_y_raw'], 'b-', alpha=0.2, linewidth=0.5, label='contact_y (raw)')
    value_fmt = ".3f" if NORMALIZE_VIDEO_FRAME_COORDS else ".0f"
    y_unit = "0-1" if NORMALIZE_VIDEO_FRAME_COORDS else "px"
    velocity_unit = "norm/frame" if NORMALIZE_VIDEO_FRAME_COORDS else "px/frame"
    ax.axhline(
        signals['air_enter'],
        color='red',
        linestyle='--',
        linewidth=0.8,
        label=f"AIR_ENTER ({signals['air_enter']:{value_fmt}})"
    )
    ax.axhline(
        signals['air_exit'],
        color='orange',
        linestyle='--',
        linewidth=0.8,
        label=f"AIR_EXIT ({signals['air_exit']:{value_fmt}})"
    )
    ax.axhline(
        signals['box_y'],
        color='purple',
        linestyle=':',
        linewidth=1.0,
        label=f"KUTU_SEVIYESI ({signals['box_y']:{value_fmt}})"
    )
    ax.axhline(
        signals['box_landing_enter'],
        color='black',
        linestyle=':',
        linewidth=1.0,
        label=f"KUTU_INIS_ESIGI ({signals['box_landing_enter']:{value_fmt}})"
    )
    for j in jumps:
        ax.axvline(j['ic'], color='green', linewidth=1.5, alpha=0.7)
        ax.axvline(j['mkf'], color='red', linewidth=1.5, alpha=0.7)
    ax.set_ylabel(f'Foot Contact Y ({y_unit})')
    ax.legend(fontsize=8, loc='upper right')
    ax.set_title('Ayak Temas Y Profili + Hysteresis Eşikleri')

    # 2. Velocity
    ax = axes[1]
    ax.plot(frames, signals['contact_vel'], 'g-', linewidth=0.8, label='contact velocity')
    ax.plot(frames, signals['hip_vel'], 'm-', linewidth=0.8, alpha=0.5, label='hip velocity')
    ax.axhline(0, color='gray', linestyle='-', linewidth=0.5)
    for j in jumps:
        ax.axvline(j['ic'], color='green', linewidth=1.5, alpha=0.7, label='IC' if j == jumps[0] else '')
    ax.set_ylabel(f'Velocity ({velocity_unit})')
    ax.legend(fontsize=8, loc='upper right')
    ax.set_title('Velocity Profili')

    # 3. Knee flexion + MKF peaks
    ax = axes[2]
    ax.plot(frames, signals['flex'], 'r-', linewidth=0.8, label='knee flex (savgol)')
    ax.plot(frames, signals['flex_raw'], 'r-', alpha=0.2, linewidth=0.5, label='knee flex (raw)')
    for j in jumps:
        ax.plot(j['mkf'], signals['flex'][j['mkf']], 'rv', markersize=10)
        ax.plot(j['ic'], signals['flex'][j['ic']], 'g^', markersize=10)
        conf = j.get('confidence', 0)
        ax.annotate(f"J{jumps.index(j)+1} c={conf:.2f}",
                    (j['mkf'], signals['flex'][j['mkf']]),
                    textcoords="offset points", xytext=(5, 10), fontsize=8)
    ax.set_ylabel('Knee Flexion (°)')
    ax.legend(fontsize=8, loc='upper right')
    ax.set_title('Diz Fleksiyon + MKF Noktaları')

    # 4. State transitions
    ax = axes[3]
    ax.plot(frames, signals['flex_deriv'], 'k-', linewidth=0.6, label='flex derivative')
    ax.axhline(0, color='gray', linestyle='-', linewidth=0.5)
    for i, j in enumerate(jumps):
        ax.axvspan(j['start'], j['ic'], alpha=0.15, color='blue', label='Flight' if i == 0 else '')
        ax.axvspan(j['ic'], j['mkf'], alpha=0.15, color='red', label='Flexion' if i == 0 else '')
        ax.axvspan(j['mkf'], j['end'], alpha=0.15, color='green', label='Recovery' if i == 0 else '')
    ax.set_ylabel('Flex Derivative')
    ax.set_xlabel('Frame')
    ax.legend(fontsize=8, loc='upper right')
    ax.set_title('Fazlar ve Flex Türevi')

    plt.tight_layout()
    out_path = os.path.join(OUTPUT_DIR, f'debug_jumps_{label.lower()}.png')
    plt.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  [{label}] Debug plot kaydedildi: {out_path}")


# ═══════════════════════════════════════════
#  ANA FONKSİYON
# ═══════════════════════════════════════════

def detect_jumps(poses, test_side='right', label='', debug=True):
    """
    3 atlayışı tespit eder.

    Yaklaşım:
      1. FSM tabanlı tespit (birincil)
      2. Peak-first yedek metot
      3. Birleştirme

    Returns:
        list[dict]: Her biri {'start', 'ic', 'mkf', 'end', 'confidence'} içeren jump listesi.
    """
    # Sinyalleri hesapla
    signals = _compute_signals(poses, test_side)

    # ── Metot 0: Kutu başlangıç seviyesine göre iniş tespiti ──
    jumps_box = _method_box_baseline(signals, poses, test_side)
    if len(jumps_box) >= EXPECTED_JUMPS:
        result = jumps_box[:EXPECTED_JUMPS]
        ics = [str(j['ic']) for j in result]
        print(f"  [{label}] Kutu-referans → {len(result)} iniş (IC: {', '.join(ics)}) ✓")
        if debug:
            _generate_debug_plots(signals, result, label)
        return result

    # ── Metot 1: FSM tabanlı ──
    jumps_fsm = _run_fsm(signals, test_side, poses)
    if len(jumps_fsm) >= EXPECTED_JUMPS:
        result = jumps_fsm[:EXPECTED_JUMPS]
        confs = [f"{j.get('confidence', 0):.2f}" for j in result]
        print(f"  [{label}] FSM → {len(result)} atlayış (conf: {', '.join(confs)}) ✓")
        if debug:
            _generate_debug_plots(signals, result, label)
        return result

    # ── Metot 2: Peak-first yedek ──
    jumps_peak = _method_peak_first(signals, poses, test_side)
    if len(jumps_peak) >= EXPECTED_JUMPS:
        result = jumps_peak[:EXPECTED_JUMPS]
        confs = [f"{j.get('confidence', 0):.2f}" for j in result]
        print(f"  [{label}] Peak-first → {len(result)} atlayış (conf: {', '.join(confs)}) ✓")
        if debug:
            _generate_debug_plots(signals, result, label)
        return result

    # ── Birleştirme ──
    merged = _merge_jumps([jumps_box, jumps_fsm, jumps_peak])
    counts = f"Kutu={len(jumps_box)}, FSM={len(jumps_fsm)}, Peak={len(jumps_peak)}"
    print(f"  [{label}] Birleştirme → {len(merged)} atlayış ({counts})")
    if debug:
        _generate_debug_plots(signals, merged, label)

    return merged
