"""
LESS Analiz Sistemi - 17 Madde Kural Tabanlı Puanlama
Her madde bağımsız fonksiyon, her kamera kendi maddelerini hesaplar.
"""
import numpy as np
from .config import (
    M1_KNEE_FLEX_THRESHOLD, M6_LATERAL_RATIO,
    M9_M10_ROTATION_THRESHOLD, M11_SYMMETRY_RATIO,
    M12_KNEE_CHANGE_THRESHOLD,
    M16_SOFT_THRESHOLD, M16_STIFF_THRESHOLD,
    LEFT_SHOULDER, RIGHT_SHOULDER, LEFT_ANKLE, RIGHT_ANKLE,
    NORMALIZE_VIDEO_FRAME_COORDS
)
from .angle_calculator import (
    knee_flexion, hip_flexion, trunk_flexion,
    ankle_contact_type, frontal_knee_valgus_check,
    lateral_trunk_lean, stance_width, shoulder_width,
    foot_rotation_change, foot_contact_symmetry,
    valgus_at_max_flexion
)


def _result(madde_no, olcum, hata, puan, aciklama, kamera):
    """Standart madde sonuç sözlüğü."""
    return {
        'madde_no': madde_no,
        'olcum': round(olcum, 2) if isinstance(olcum, float) else olcum,
        'hata': hata,
        'puan': puan,
        'aciklama': aciklama,
        'kamera': kamera
    }


def _distance_unit():
    """Koordinat ölçeğine göre rapor birimi."""
    return "norm" if NORMALIZE_VIDEO_FRAME_COORDS else "px"


# ═══════════════════════════════════════════
#  YAN KAMERA MADDELERİ (M1, M2, M3, M4, M12, M13, M14, M16)
# ═══════════════════════════════════════════

def evaluate_m1(poses, ic, side):
    """M1: İlk temasta diz fleksiyon açısı. >30° → EVET(0), ≤30° → HAYIR(1)."""
    val = knee_flexion(poses, ic, side)
    hata = val <= M1_KNEE_FLEX_THRESHOLD
    return _result(1, val, hata, int(hata),
                   f"Diz flex {val:.1f}° {'≤' if hata else '>'} {M1_KNEE_FLEX_THRESHOLD}°", 'yan')


def evaluate_m2(poses, ic, side):
    """M2: İlk temasta kalça fleksiyon açısı. Fleksiyonda → EVET(0), değilse → HAYIR(1)."""
    val = hip_flexion(poses, ic, side)
    # Kalça fleksiyonu > ~10° → fleksiyonda (iyi), yoksa hata
    hata = val <= 10
    return _result(2, val, hata, int(hata),
                   f"Kalça flex {val:.1f}° {'≤10' if hata else '>10'}°", 'yan')


def evaluate_m3(poses, ic):
    """M3: İlk temasta gövde fleksiyon açısı. Fleksiyonda → EVET(0), dik/ext → HAYIR(1)."""
    val = trunk_flexion(poses, ic)
    hata = val <= 10  # Gövde dik veya ekstansiyonda
    return _result(3, val, hata, int(hata),
                   f"Gövde flex {val:.1f}° {'≤10' if hata else '>10'}°", 'yan')


def evaluate_m4(poses, ic, side):
    """M4: Plantar fleksiyon. Ayak ucundan iniş → EVET(0), topuk/taban → HAYIR(1)."""
    contact = ankle_contact_type(poses, ic, side)
    hata = contact != 'toe_first'
    label = 'topuk/taban' if hata else 'ayak ucu'
    return _result(4, contact, hata, int(hata),
                   f"İlk temas: {label}", 'yan')


def evaluate_m12(poses, ic, mkf, side):
    """M12: Diz fleksiyon değişimi IC→MKF. >45° → EVET(0), ≤45° → HAYIR(1)."""
    kf_ic = knee_flexion(poses, ic, side)
    kf_mkf = knee_flexion(poses, mkf, side)
    delta = kf_mkf - kf_ic
    hata = delta <= M12_KNEE_CHANGE_THRESHOLD
    return _result(12, delta, hata, int(hata),
                   f"ΔDiz flex {delta:.1f}° {'≤' if hata else '>'} {M12_KNEE_CHANGE_THRESHOLD}°", 'yan')


def evaluate_m13(poses, ic, mkf, side):
    """M13: MKF'de kalça fleksiyonu IC'ye göre artmış mı? Artmış → EVET(0), artmamış → HAYIR(1)."""
    hf_ic = hip_flexion(poses, ic, side)
    hf_mkf = hip_flexion(poses, mkf, side)
    delta = hf_mkf - hf_ic
    hata = delta <= 0
    return _result(13, delta, hata, int(hata),
                   f"ΔKalça flex {delta:.1f}° {'≤0' if hata else '>0'}", 'yan')


def evaluate_m14(poses, ic, mkf):
    """M14: MKF'de gövde fleksiyonu IC'ye göre artmış mı? Artmış → EVET(0), artmamış → HAYIR(1)."""
    tf_ic = trunk_flexion(poses, ic)
    tf_mkf = trunk_flexion(poses, mkf)
    delta = tf_mkf - tf_ic
    hata = delta <= 0
    return _result(14, delta, hata, int(hata),
                   f"ΔGövde flex {delta:.1f}° {'≤0' if hata else '>0'}", 'yan')


def evaluate_m16(poses, ic, mkf, side):
    """M16: Eklem hareketi değişimi. ROM toplamı: >90→Yumuşak(0), 45-90→Orta(1), <45→Sert(2)."""
    dk = knee_flexion(poses, mkf, side) - knee_flexion(poses, ic, side)
    dh = hip_flexion(poses, mkf, side) - hip_flexion(poses, ic, side)
    dt = trunk_flexion(poses, mkf) - trunk_flexion(poses, ic)
    total_rom = dk + dh + dt

    if total_rom > M16_SOFT_THRESHOLD:
        kategori = "YUMUŞAK"
        puan = 0
    elif total_rom >= M16_STIFF_THRESHOLD:
        kategori = "ORTA"
        puan = 1
    else:
        kategori = "SERT"
        puan = 2

    return _result(16, total_rom, kategori, puan,
                   f"ROM {total_rom:.1f}° → {kategori}", 'yan')


# ═══════════════════════════════════════════
#  ÖN KAMERA MADDELERİ (M5, M6, M7, M8, M9, M10, M11, M15)
# ═══════════════════════════════════════════

def evaluate_m5(poses, ic, side):
    """M5: İlk temasta diz valgus. Medial → EVET(1), değilse → HAYIR(0)."""
    valgus = frontal_knee_valgus_check(poses, ic, side)
    puan = 1 if valgus else 0
    return _result(5, valgus, valgus, puan,
                   f"Diz valgus {'VAR' if valgus else 'YOK'}", 'on')


def evaluate_m6(poses, ic):
    """M6: İlk temasta lateral gövde fleksiyonu. Var → EVET(1), yok → HAYIR(0)."""
    kayma = lateral_trunk_lean(poses, ic)
    omuz_g = shoulder_width(poses, ic)
    hata = kayma > omuz_g * M6_LATERAL_RATIO
    puan = 1 if hata else 0
    return _result(6, kayma, hata, puan,
                   f"Lat. kayma {kayma:.3f}{_distance_unit()} (eşik {omuz_g * M6_LATERAL_RATIO:.3f}{_distance_unit()})", 'on')


def evaluate_m7(poses, ic):
    """M7: Duruş genişliği geniş. Ayak arası > omuz genişliği → EVET(1)."""
    sw = stance_width(poses, ic)
    sh_w = shoulder_width(poses, ic)
    hata = sw > sh_w
    puan = 1 if hata else 0
    return _result(7, sw, hata, puan,
                   f"Ayak arası {sw:.3f}{_distance_unit()} vs omuz {sh_w:.3f}{_distance_unit()}", 'on')


def evaluate_m8(poses, ic):
    """M8: Duruş genişliği dar. Ayak arası < omuz genişliği → EVET(1)."""
    sw = stance_width(poses, ic)
    sh_w = shoulder_width(poses, ic)
    hata = sw < sh_w
    puan = 1 if hata else 0
    return _result(8, sw, hata, puan,
                   f"Ayak arası {sw:.3f}{_distance_unit()} vs omuz {sh_w:.3f}{_distance_unit()}", 'on')


def evaluate_m9(poses, ic, mkf, side):
    """M9: Ayak iç rotasyonu >30° → EVET(1)."""
    rot = foot_rotation_change(poses, ic, mkf, side)
    hata = rot > M9_M10_ROTATION_THRESHOLD  # Pozitif = iç rotasyon
    puan = 1 if hata else 0
    return _result(9, abs(rot), hata, puan,
                   f"İç rot {rot:.1f}° {'>' if hata else '≤'} {M9_M10_ROTATION_THRESHOLD}°", 'on')


def evaluate_m10(poses, ic, mkf, side):
    """M10: Ayak dış rotasyonu >30° → EVET(1)."""
    rot = foot_rotation_change(poses, ic, mkf, side)
    hata = rot < -M9_M10_ROTATION_THRESHOLD  # Negatif = dış rotasyon
    puan = 1 if hata else 0
    return _result(10, abs(rot), hata, puan,
                   f"Dış rot {rot:.1f}° {'>' if hata else '≤'} {M9_M10_ROTATION_THRESHOLD}°", 'on')


def evaluate_m11(poses, ic, video_width):
    """M11: Ayak simetrisi. Simetrik → EVET(0), asimetrik → HAYIR(1)."""
    y_diff = foot_contact_symmetry(poses, ic, video_width)
    threshold = video_width * M11_SYMMETRY_RATIO
    hata = y_diff > threshold  # Asimetrik
    puan = 1 if hata else 0
    return _result(11, y_diff, hata, puan,
                   f"Y farkı {y_diff:.3f}{_distance_unit()} (eşik {threshold:.3f}{_distance_unit()})", 'on')


def evaluate_m15(poses, mkf, side):
    """M15: MKF'de diz valgus değişimi. Patella medial/başparmak → EVET(1)."""
    valgus = valgus_at_max_flexion(poses, mkf, side)
    puan = 1 if valgus else 0
    return _result(15, valgus, valgus, puan,
                   f"MKF valgus {'VAR' if valgus else 'YOK'}", 'on')


# ═══════════════════════════════════════════
#  KOMBİNE MADDE (M17)
# ═══════════════════════════════════════════

def evaluate_m17(m16_result, m15_result):
    """
    M17: Genel izlenim.
    Yumuşak iniş + frontal diz hareketi yok → MÜKEMMEL(0)
    Sert iniş + frontal diz hareketi var → KÖTÜ(2)
    Diğer → ORTA(1)
    """
    m16_puan = m16_result['puan']
    m15_has_valgus = m15_result['hata']

    if m16_puan == 0 and not m15_has_valgus:
        kategori = "MÜKEMMEL"
        puan = 0
    elif m16_puan == 2 and m15_has_valgus:
        kategori = "KÖTÜ"
        puan = 2
    else:
        kategori = "ORTA"
        puan = 1

    return _result(17, kategori, kategori, puan,
                   f"Genel: {kategori}", 'yan+on')


# ═══════════════════════════════════════════
#  KARAR FONKSİYONLARI (3 ATLAYIŞ → TEK PUAN)
# ═══════════════════════════════════════════

def karar_m1_to_m15(puanlar):
    """M1-M15: 3 atlayıştan ≥2 hata → 1, aksi → 0."""
    return 1 if sum(puanlar) >= 2 else 0


def karar_m16_m17(puanlar):
    """M16-M17: En az 1 Sert/Kötü(2) → 2, ≥2 Orta(1) → 1, diğer → 0."""
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
            'm1': evaluate_m1(poses, ic, test_side),
            'm2': evaluate_m2(poses, ic, test_side),
            'm3': evaluate_m3(poses, ic),
            'm4': evaluate_m4(poses, ic, test_side),
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
            'm5': evaluate_m5(poses, ic, test_side),
            'm6': evaluate_m6(poses, ic),
            'm7': evaluate_m7(poses, ic),
            'm8': evaluate_m8(poses, ic),
            'm9': evaluate_m9(poses, ic, mkf, test_side),
            'm10': evaluate_m10(poses, ic, mkf, test_side),
            'm11': evaluate_m11(poses, ic, video_width),
            'm15': evaluate_m15(poses, mkf, test_side),
        }
        all_results.append(res)
    return all_results


def combine_results(yan_results, on_results):
    """Yan ve ön kamera sonuçlarını birleştirip M17'yi hesaplar."""
    num = min(len(yan_results), len(on_results))
    combined = []
    for i in range(num):
        merged = {}
        merged.update(yan_results[i])
        merged.update(on_results[i])
        merged['m17'] = evaluate_m17(merged['m16'], merged['m15'])
        combined.append(merged)
    return combined
