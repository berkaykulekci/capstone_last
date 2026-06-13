"""
LESS Analiz Sistemi - YOLO için LESS Kural Modülü (Backend)
M4, M9, M10: toe/heel landmark olmadığından proxy yöntemle yaklaşık hesaplanır.
"""
import numpy as np
from .yolo_config import (
    M1_KNEE_FLEX_THRESHOLD, M4_TIBIA_ANGLE_THRESHOLD,
    M6_LATERAL_RATIO, M9_M10_ROTATION_THRESHOLD,
    M9_M10_OFFSET_THRESHOLD, M11_SYMMETRY_RATIO,
    M12_KNEE_CHANGE_THRESHOLD,
    M16_SOFT_THRESHOLD, M16_STIFF_THRESHOLD,
    NORMALIZE_VIDEO_FRAME_COORDS
)
from .yolo_angle_calculator import (
    knee_flexion, hip_flexion, trunk_flexion,
    frontal_knee_valgus_check, lateral_trunk_lean,
    stance_width, shoulder_width, foot_contact_symmetry,
    valgus_at_max_flexion, tibia_angle_from_vertical,
    foot_rotation_proxy
)

YOLO_NA_MADDE      = set()        # artık N/A yok
YOLO_YAKLASIK_MADDE = {4, 9, 10}  # proxy ile yaklaşık hesaplanan maddeler


def _result(madde_no, olcum, hata, puan, aciklama, kamera, yaklaşık=False):
    return {
        'madde_no': madde_no,
        'olcum':    round(olcum, 2) if isinstance(olcum, float) else olcum,
        'hata':     hata,
        'puan':     puan,
        'aciklama': aciklama,
        'kamera':   kamera,
        'yolo_na':  False,
        'yaklaşık': yaklaşık or (madde_no in YOLO_YAKLASIK_MADDE),
    }


def _du():
    return "norm" if NORMALIZE_VIDEO_FRAME_COORDS else "px"


def evaluate_m1(poses, ic, side):
    val  = knee_flexion(poses, ic, side)
    hata = val <= M1_KNEE_FLEX_THRESHOLD
    return _result(1, val, hata, int(hata), f"Diz flex {val:.1f}°", 'yan')

def evaluate_m2(poses, ic, side):
    val  = hip_flexion(poses, ic, side)
    hata = val <= 10
    return _result(2, val, hata, int(hata), f"Kalça flex {val:.1f}°", 'yan')

def evaluate_m3(poses, ic):
    val  = trunk_flexion(poses, ic)
    hata = val <= 10
    return _result(3, val, hata, int(hata), f"Gövde flex {val:.1f}°", 'yan')

def evaluate_m4(poses, ic, side):
    """Plantar fleksiyon proxy: tibia açısı dikeyden küçükse toe-first iniş tahmini."""
    angle = tibia_angle_from_vertical(poses, ic, side)
    hata  = angle < M4_TIBIA_ANGLE_THRESHOLD
    return _result(4, angle, hata, int(hata),
                   f"Tibia açısı {angle:.1f}° (eşik {M4_TIBIA_ANGLE_THRESHOLD}°) → "
                   f"{'plantar fleksiyon tahmini' if hata else 'normal iniş tahmini'}", 'yan')

def evaluate_m12(poses, ic, mkf, side):
    delta = knee_flexion(poses, mkf, side) - knee_flexion(poses, ic, side)
    hata  = delta <= M12_KNEE_CHANGE_THRESHOLD
    return _result(12, delta, hata, int(hata), f"ΔDiz flex {delta:.1f}°", 'yan')

def evaluate_m13(poses, ic, mkf, side):
    delta = hip_flexion(poses, mkf, side) - hip_flexion(poses, ic, side)
    hata  = delta <= 0
    return _result(13, delta, hata, int(hata), f"ΔKalça flex {delta:.1f}°", 'yan')

def evaluate_m14(poses, ic, mkf):
    delta = trunk_flexion(poses, mkf) - trunk_flexion(poses, ic)
    hata  = delta <= 0
    return _result(14, delta, hata, int(hata), f"ΔGövde flex {delta:.1f}°", 'yan')

def evaluate_m16(poses, ic, mkf, side):
    dk = knee_flexion(poses, mkf, side) - knee_flexion(poses, ic, side)
    dh = hip_flexion(poses, mkf, side)  - hip_flexion(poses, ic, side)
    dt = trunk_flexion(poses, mkf) - trunk_flexion(poses, ic)
    rom = dk + dh + dt
    if rom > M16_SOFT_THRESHOLD:
        cat, puan = "YUMUŞAK", 0
    elif rom >= M16_STIFF_THRESHOLD:
        cat, puan = "ORTA", 1
    else:
        cat, puan = "SERT", 2
    return _result(16, rom, cat, puan, f"ROM {rom:.1f}° → {cat}", 'yan')

def evaluate_m5(poses, ic, side):
    valgus = frontal_knee_valgus_check(poses, ic, side)
    return _result(5, valgus, valgus, int(valgus),
                   f"Diz valgus {'VAR' if valgus else 'YOK'}", 'on')

def evaluate_m6(poses, ic):
    kayma  = lateral_trunk_lean(poses, ic)
    omuz_g = shoulder_width(poses, ic)
    hata   = kayma > omuz_g * M6_LATERAL_RATIO
    return _result(6, kayma, hata, int(hata), f"Lat. kayma {kayma:.3f}{_du()}", 'on')

def evaluate_m7(poses, ic):
    sw, sh = stance_width(poses, ic), shoulder_width(poses, ic)
    hata   = sw > sh
    return _result(7, sw, hata, int(hata), f"Ayak {sw:.3f} vs omuz {sh:.3f}{_du()}", 'on')

def evaluate_m8(poses, ic):
    sw, sh = stance_width(poses, ic), shoulder_width(poses, ic)
    hata   = sw < sh
    return _result(8, sw, hata, int(hata), f"Ayak {sw:.3f} vs omuz {sh:.3f}{_du()}", 'on')

def evaluate_m9(poses, ic, mkf, side):
    """İç rotasyon proxy: IC→MKF arası knee-ankle x-offset negatif yönde değiştiyse."""
    delta = foot_rotation_proxy(poses, ic, mkf, side)
    hata  = delta < -M9_M10_OFFSET_THRESHOLD
    return _result(9, delta, hata, int(hata),
                   f"Rotasyon Δoffset {delta:.3f} → "
                   f"{'iç rot tahmini' if hata else 'iç rot yok'}", 'on')

def evaluate_m10(poses, ic, mkf, side):
    """Dış rotasyon proxy: IC→MKF arası knee-ankle x-offset pozitif yönde değiştiyse."""
    delta = foot_rotation_proxy(poses, ic, mkf, side)
    hata  = delta > M9_M10_OFFSET_THRESHOLD
    return _result(10, delta, hata, int(hata),
                   f"Rotasyon Δoffset {delta:.3f} → "
                   f"{'dış rot tahmini' if hata else 'dış rot yok'}", 'on')

def evaluate_m11(poses, ic, video_width):
    y_diff = foot_contact_symmetry(poses, ic, video_width)
    thr    = video_width * M11_SYMMETRY_RATIO
    hata   = y_diff > thr
    return _result(11, y_diff, hata, int(hata), f"Y farkı {y_diff:.3f}{_du()}", 'on')

def evaluate_m15(poses, mkf, side):
    valgus = valgus_at_max_flexion(poses, mkf, side)
    return _result(15, valgus, valgus, int(valgus),
                   f"MKF valgus {'VAR' if valgus else 'YOK'}", 'on')

def evaluate_m17(m16_result, m15_result):
    p16    = m16_result['puan']
    valgus = m15_result['hata']
    if p16 == 0 and not valgus:
        cat, puan = "MÜKEMMEL", 0
    elif p16 == 2 and valgus:
        cat, puan = "KÖTÜ", 2
    else:
        cat, puan = "ORTA", 1
    return _result(17, cat, cat, puan, f"Genel: {cat}", 'yan+on')


def karar_m1_to_m15(puanlar):
    return 1 if sum(puanlar) >= 2 else 0

def karar_m16_m17(puanlar):
    if any(p == 2 for p in puanlar):
        return 2
    if sum(1 for p in puanlar if p >= 1) >= 2:
        return 1
    return 0


def evaluate_yan_kamera(poses, jumps, test_side):
    results = []
    for j in jumps:
        ic, mkf = j['ic'], j['mkf']
        results.append({
            'm1':  evaluate_m1(poses, ic, test_side),
            'm2':  evaluate_m2(poses, ic, test_side),
            'm3':  evaluate_m3(poses, ic),
            'm4':  evaluate_m4(poses, ic, test_side),
            'm12': evaluate_m12(poses, ic, mkf, test_side),
            'm13': evaluate_m13(poses, ic, mkf, test_side),
            'm14': evaluate_m14(poses, ic, mkf),
            'm16': evaluate_m16(poses, ic, mkf, test_side),
        })
    return results


def evaluate_on_kamera(poses, jumps, test_side, video_width):
    results = []
    for j in jumps:
        ic, mkf = j['ic'], j['mkf']
        results.append({
            'm5':  evaluate_m5(poses, ic, test_side),
            'm6':  evaluate_m6(poses, ic),
            'm7':  evaluate_m7(poses, ic),
            'm8':  evaluate_m8(poses, ic),
            'm9':  evaluate_m9(poses, ic, mkf, test_side),
            'm10': evaluate_m10(poses, ic, mkf, test_side),
            'm11': evaluate_m11(poses, ic, video_width),
            'm15': evaluate_m15(poses, mkf, test_side),
        })
    return results


def combine_results(yan_results, on_results):
    n = max(len(yan_results), len(on_results))
    combined = []
    for i in range(n):
        res = {}
        if i < len(yan_results):
            res.update(yan_results[i])
        if i < len(on_results):
            res.update(on_results[i])
        res['m17'] = evaluate_m17(
            res.get('m16', {'puan': 0, 'hata': False}),
            res.get('m15', {'puan': 0, 'hata': False})
        )
        combined.append(res)
    return combined


def compute_total_score(combined):
    """Toplam skor. Tüm 17 madde dahil → max 19 (M4/M9/M10 proxy ile yaklaşık)."""
    tum = ['m1','m2','m3','m4','m5','m6','m7','m8',
           'm9','m10','m11','m12','m13','m14','m15','m16','m17']
    skorlar = {}
    for mk in tum:
        puanlar = [j[mk]['puan'] for j in combined if mk in j]
        if not puanlar:
            skorlar[mk] = 0
            continue
        skorlar[mk] = karar_m16_m17(puanlar) if mk in ('m16', 'm17') else karar_m1_to_m15(puanlar)

    toplam = sum(v for v in skorlar.values() if v is not None)
    yaklaşık_maddeler = sorted(YOLO_YAKLASIK_MADDE)
    return toplam, skorlar, yaklaşık_maddeler
