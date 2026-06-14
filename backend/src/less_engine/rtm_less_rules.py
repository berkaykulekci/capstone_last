"""
LESS Analiz Sistemi - RTMPose için LESS Kural Modülü
RTMPose-WholeBody heel + toe keypoint'leri içerdiğinden M4, M9, M10
PROXY OLMADAN (exact) hesaplanır → yaklaşık madde YOKTUR.
"""
import numpy as np
from .rtm_config import (
    M1_KNEE_FLEX_THRESHOLD,
    M6_LATERAL_RATIO, M9_M10_ROTATION_THRESHOLD,
    M11_SYMMETRY_RATIO, M12_KNEE_CHANGE_THRESHOLD,
    M16_SOFT_THRESHOLD, M16_STIFF_THRESHOLD,
    LEFT_SHOULDER, RIGHT_SHOULDER, LEFT_ANKLE, RIGHT_ANKLE,
    NORMALIZE_VIDEO_FRAME_COORDS
)
from .rtm_angle_calculator import (
    knee_flexion, hip_flexion, trunk_flexion,
    ankle_contact_type, frontal_knee_valgus_check, lateral_trunk_lean,
    stance_width, shoulder_width, foot_rotation_change,
    foot_contact_symmetry, valgus_at_max_flexion
)

RTM_NA_MADDE       = set()   # hiçbir madde tamamen kullanılamaz değil
RTM_YAKLASIK_MADDE = set()   # hiçbir madde proxy/yaklaşık değil (tümü exact)


def _result(madde_no, olcum, hata, puan, aciklama, kamera, yaklaşık=False):
    return {
        'madde_no': madde_no,
        'olcum':    round(olcum, 2) if isinstance(olcum, float) else olcum,
        'hata':     hata,
        'puan':     puan,
        'aciklama': aciklama,
        'kamera':   kamera,
        'rtm_na':   False,
        'yaklaşık': yaklaşık,
    }


def _distance_unit():
    return "norm" if NORMALIZE_VIDEO_FRAME_COORDS else "px"


# ═══════════════════════════════════════════
#  YAN KAMERA MADDELERİ
# ═══════════════════════════════════════════

def evaluate_m1(poses, ic, side):
    val = knee_flexion(poses, ic, side)
    hata = val <= M1_KNEE_FLEX_THRESHOLD
    return _result(1, val, hata, int(hata),
                   f"Diz flex {val:.1f}° {'≤' if hata else '>'} {M1_KNEE_FLEX_THRESHOLD}°", 'yan')


def evaluate_m2(poses, ic, side):
    val = hip_flexion(poses, ic, side)
    hata = val <= 10
    return _result(2, val, hata, int(hata),
                   f"Kalça flex {val:.1f}° {'≤10' if hata else '>10'}°", 'yan')


def evaluate_m3(poses, ic):
    val = trunk_flexion(poses, ic)
    hata = val <= 10
    return _result(3, val, hata, int(hata),
                   f"Gövde flex {val:.1f}° {'≤10' if hata else '>10'}°", 'yan')


def evaluate_m4(poses, ic, side):
    """M4: Plantar fleksiyon — heel/toe ile EXACT temas tipi (toe-first beklenir)."""
    contact = ankle_contact_type(poses, ic, side)
    hata = contact != 'toe_first'
    return _result(4, contact, hata, int(hata),
                   f"İlk temas: {contact} → {'hata (topuk önce)' if hata else 'doğru (ayak ucu önce)'}", 'yan')


def evaluate_m12(poses, ic, mkf, side):
    kf_ic  = knee_flexion(poses, ic, side)
    kf_mkf = knee_flexion(poses, mkf, side)
    delta  = kf_mkf - kf_ic
    hata   = delta <= M12_KNEE_CHANGE_THRESHOLD
    return _result(12, delta, hata, int(hata),
                   f"ΔDiz flex {delta:.1f}° {'≤' if hata else '>'} {M12_KNEE_CHANGE_THRESHOLD}°", 'yan')


def evaluate_m13(poses, ic, mkf, side):
    hf_ic  = hip_flexion(poses, ic, side)
    hf_mkf = hip_flexion(poses, mkf, side)
    delta  = hf_mkf - hf_ic
    hata   = delta <= 0
    return _result(13, delta, hata, int(hata),
                   f"ΔKalça flex {delta:.1f}° {'≤0' if hata else '>0'}", 'yan')


def evaluate_m14(poses, ic, mkf):
    tf_ic  = trunk_flexion(poses, ic)
    tf_mkf = trunk_flexion(poses, mkf)
    delta  = tf_mkf - tf_ic
    hata   = delta <= 0
    return _result(14, delta, hata, int(hata),
                   f"ΔGövde flex {delta:.1f}° {'≤0' if hata else '>0'}", 'yan')


def evaluate_m16(poses, ic, mkf, side):
    dk = knee_flexion(poses, mkf, side) - knee_flexion(poses, ic, side)
    dh = hip_flexion(poses, mkf, side)  - hip_flexion(poses, ic, side)
    dt = trunk_flexion(poses, mkf) - trunk_flexion(poses, ic)
    total_rom = dk + dh + dt

    if total_rom > M16_SOFT_THRESHOLD:
        kategori, puan = "YUMUŞAK", 0
    elif total_rom >= M16_STIFF_THRESHOLD:
        kategori, puan = "ORTA", 1
    else:
        kategori, puan = "SERT", 2

    return _result(16, total_rom, kategori, puan,
                   f"ROM {total_rom:.1f}° → {kategori}", 'yan')


# ═══════════════════════════════════════════
#  ÖN KAMERA MADDELERİ
# ═══════════════════════════════════════════

def evaluate_m5(poses, ic, side):
    valgus = frontal_knee_valgus_check(poses, ic, side)
    puan   = 1 if valgus else 0
    return _result(5, valgus, valgus, puan,
                   f"Diz valgus {'VAR' if valgus else 'YOK'}", 'on')


def evaluate_m6(poses, ic):
    kayma  = lateral_trunk_lean(poses, ic)
    omuz_g = shoulder_width(poses, ic)
    hata   = kayma > omuz_g * M6_LATERAL_RATIO
    puan   = 1 if hata else 0
    return _result(6, kayma, hata, puan,
                   f"Lat. kayma {kayma:.3f}{_distance_unit()}", 'on')


def evaluate_m7(poses, ic):
    sw   = stance_width(poses, ic)
    sh_w = shoulder_width(poses, ic)
    hata = sw > sh_w
    puan = 1 if hata else 0
    return _result(7, sw, hata, puan,
                   f"Ayak arası {sw:.3f} vs omuz {sh_w:.3f}{_distance_unit()}", 'on')


def evaluate_m8(poses, ic):
    sw   = stance_width(poses, ic)
    sh_w = shoulder_width(poses, ic)
    hata = sw < sh_w
    puan = 1 if hata else 0
    return _result(8, sw, hata, puan,
                   f"Ayak arası {sw:.3f} vs omuz {sh_w:.3f}{_distance_unit()}", 'on')


def evaluate_m9(poses, ic, mkf, side):
    """M9: İç rotasyon — heel→toe vektör açısı pozitif yönde > eşik ise (exact)."""
    rot = foot_rotation_change(poses, ic, mkf, side)
    hata = rot > M9_M10_ROTATION_THRESHOLD
    return _result(9, rot, hata, int(hata),
                   f"Ayak rotasyon {rot:.1f}° → "
                   f"{'iç rotasyon' if hata else 'iç rot yok'}", 'on')


def evaluate_m10(poses, ic, mkf, side):
    """M10: Dış rotasyon — heel→toe vektör açısı negatif yönde > eşik ise (exact)."""
    rot = foot_rotation_change(poses, ic, mkf, side)
    hata = rot < -M9_M10_ROTATION_THRESHOLD
    return _result(10, rot, hata, int(hata),
                   f"Ayak rotasyon {rot:.1f}° → "
                   f"{'dış rotasyon' if hata else 'dış rot yok'}", 'on')


def evaluate_m11(poses, ic, video_width):
    y_diff    = foot_contact_symmetry(poses, ic, video_width)
    threshold = video_width * M11_SYMMETRY_RATIO
    hata      = y_diff > threshold
    puan      = 1 if hata else 0
    return _result(11, y_diff, hata, puan,
                   f"Y farkı {y_diff:.3f}{_distance_unit()} (eşik {threshold:.3f})", 'on')


def evaluate_m15(poses, mkf, side):
    valgus = valgus_at_max_flexion(poses, mkf, side)
    puan   = 1 if valgus else 0
    return _result(15, valgus, valgus, puan,
                   f"MKF valgus {'VAR' if valgus else 'YOK'}", 'on')


# ═══════════════════════════════════════════
#  KOMBİNE MADDE (M17)
# ═══════════════════════════════════════════

def evaluate_m17(m16_result, m15_result):
    m16_puan       = m16_result['puan']
    m15_has_valgus = m15_result['hata']

    if m16_puan == 0 and not m15_has_valgus:
        kategori, puan = "MÜKEMMEL", 0
    elif m16_puan == 2 and m15_has_valgus:
        kategori, puan = "KÖTÜ", 2
    else:
        kategori, puan = "ORTA", 1

    return _result(17, kategori, kategori, puan,
                   f"Genel: {kategori}", 'yan+on')


# ═══════════════════════════════════════════
#  KARAR FONKSİYONLARI
# ═══════════════════════════════════════════

def karar_m1_to_m15(puanlar):
    """3 atlayıştan ≥2 hata → 1, aksi → 0."""
    return 1 if sum(puanlar) >= 2 else 0


def karar_m16_m17(puanlar):
    """En az 1 Sert/Kötü(2) → 2, ≥2 Orta(1) → 1, diğer → 0."""
    if any(p == 2 for p in puanlar):
        return 2
    if sum(1 for p in puanlar if p >= 1) >= 2:
        return 1
    return 0


# ═══════════════════════════════════════════
#  TOPLU DEĞERLENDİRME
# ═══════════════════════════════════════════

def evaluate_yan_kamera(poses, jumps, test_side):
    """Yan kamera maddelerini tüm atlayışlar için hesaplar."""
    all_results = []
    for j in jumps:
        ic, mkf = j['ic'], j['mkf']
        res = {
            'm1':  evaluate_m1(poses, ic, test_side),
            'm2':  evaluate_m2(poses, ic, test_side),
            'm3':  evaluate_m3(poses, ic),
            'm4':  evaluate_m4(poses, ic, test_side),
            'm12': evaluate_m12(poses, ic, mkf, test_side),
            'm13': evaluate_m13(poses, ic, mkf, test_side),
            'm14': evaluate_m14(poses, ic, mkf),
            'm16': evaluate_m16(poses, ic, mkf, test_side),
        }
        all_results.append(res)
    return all_results


def evaluate_on_kamera(poses, jumps, test_side, video_width):
    """Ön kamera maddelerini tüm atlayışlar için hesaplar."""
    all_results = []
    for j in jumps:
        ic, mkf = j['ic'], j['mkf']
        res = {
            'm5':  evaluate_m5(poses, ic, test_side),
            'm6':  evaluate_m6(poses, ic),
            'm7':  evaluate_m7(poses, ic),
            'm8':  evaluate_m8(poses, ic),
            'm9':  evaluate_m9(poses, ic, mkf, test_side),
            'm10': evaluate_m10(poses, ic, mkf, test_side),
            'm11': evaluate_m11(poses, ic, video_width),
            'm15': evaluate_m15(poses, mkf, test_side),
        }
        all_results.append(res)
    return all_results


def combine_results(yan_results, on_results):
    """Yan ve ön kamera sonuçlarını birleştirip M17 ekler."""
    n = max(len(yan_results), len(on_results))
    combined = []
    for i in range(n):
        res = {}
        if i < len(yan_results):
            res.update(yan_results[i])
        if i < len(on_results):
            res.update(on_results[i])
        m16 = res.get('m16', {'puan': 0, 'hata': False})
        m15 = res.get('m15', {'puan': 0, 'hata': False})
        res['m17'] = evaluate_m17(m16, m15)
        combined.append(res)
    return combined


def compute_total_score(combined):
    """Tüm 17 madde dahil toplam skor (max 19). RTMPose'da tümü exact."""
    tum_maddeler = ['m1','m2','m3','m4','m5','m6','m7','m8',
                    'm9','m10','m11','m12','m13','m14','m15','m16','m17']

    skorlar = {}
    for mk in tum_maddeler:
        puanlar = [j[mk]['puan'] for j in combined if mk in j]
        if not puanlar:
            skorlar[mk] = 0
            continue
        skorlar[mk] = karar_m16_m17(puanlar) if mk in ('m16', 'm17') else karar_m1_to_m15(puanlar)

    toplam = sum(v for v in skorlar.values() if v is not None)
    return toplam, skorlar, sorted(RTM_YAKLASIK_MADDE)
