"""
LESS Analiz Sistemi - RTMPose Açı Hesaplama Modülü
Biyomekanik açı ve ölçüm fonksiyonları.

RTMPose-WholeBody heel + big toe keypoint'leri içerdiğinden M4/M9/M10
PROXY OLMADAN, MediaPipe ile aynı exact yöntemle hesaplanır.

MediaPipe sürümünden tek fark:
  - foot_rotation_change MediaPipe'ta X-Z düzlemini kullanıyordu (kanal [0,2]=X,Z).
    RTMPose'da Z yok → frontal X-Y düzleminde (kanal [0,1]) heel→toe vektörü kullanılır.
"""
import numpy as np
from .rtm_config import (
    LEFT_HIP, RIGHT_HIP, LEFT_KNEE, RIGHT_KNEE,
    LEFT_ANKLE, RIGHT_ANKLE, LEFT_HEEL, RIGHT_HEEL,
    LEFT_FOOT_INDEX, RIGHT_FOOT_INDEX,
    LEFT_SHOULDER, RIGHT_SHOULDER
)


def _side(side):
    """Verilen taraf için landmark indekslerini döndürür."""
    if side == 'left':
        return dict(hip=LEFT_HIP, knee=LEFT_KNEE, ankle=LEFT_ANKLE,
                    heel=LEFT_HEEL, foot=LEFT_FOOT_INDEX, shoulder=LEFT_SHOULDER)
    return dict(hip=RIGHT_HIP, knee=RIGHT_KNEE, ankle=RIGHT_ANKLE,
                heel=RIGHT_HEEL, foot=RIGHT_FOOT_INDEX, shoulder=RIGHT_SHOULDER)


def angle_3pt(a, b, c):
    """B noktasındaki açı (derece). BA ve BC vektörleri arasında."""
    ba = a - b
    bc = c - b
    cos_val = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-8)
    return np.degrees(np.arccos(np.clip(cos_val, -1.0, 1.0)))


# ─── Sagittal Düzlem (Yan Kamera) ───

def knee_flexion(poses, frame, side):
    """Diz fleksiyon açısı = 180 - (Kalça-Diz-Ayak bileği açısı)."""
    s = _side(side)
    a = poses[frame, s['hip'], :2]
    b = poses[frame, s['knee'], :2]
    c = poses[frame, s['ankle'], :2]
    return 180.0 - angle_3pt(a, b, c)


def hip_flexion(poses, frame, side):
    """Kalça fleksiyon açısı = 180 - (Omuz-Kalça-Diz açısı)."""
    s = _side(side)
    a = poses[frame, s['shoulder'], :2]
    b = poses[frame, s['hip'], :2]
    c = poses[frame, s['knee'], :2]
    return 180.0 - angle_3pt(a, b, c)


def trunk_flexion(poses, frame):
    """Gövde fleksiyon açısı: gövde vektörünün dikey eksenden sapması (derece)."""
    hip_c = (poses[frame, LEFT_HIP, :2] + poses[frame, RIGHT_HIP, :2]) / 2.0
    sho_c = (poses[frame, LEFT_SHOULDER, :2] + poses[frame, RIGHT_SHOULDER, :2]) / 2.0
    trunk_vec = sho_c - hip_c  # kalçadan omuza
    vertical = np.array([0.0, 1.0])  # yukarı (y ters çevrildi)
    cos_val = np.dot(trunk_vec, vertical) / (np.linalg.norm(trunk_vec) + 1e-8)
    return np.degrees(np.arccos(np.clip(cos_val, -1.0, 1.0)))


def ankle_contact_type(poses, frame, side):
    """
    Ayak bileği temas tipi: ayak ucu mu topuk mu önce yere temas ediyor.
    Y ters çevrilmiş: düşük Y = yere yakın.
    """
    s = _side(side)
    heel_y = poses[frame, s['heel'], 1]
    toe_y = poses[frame, s['foot'], 1]
    # Düşük y = yere daha yakın
    if toe_y < heel_y:
        return 'toe_first'  # Ayak ucu yere daha yakın → doğru iniş
    else:
        return 'heel_first'  # Topuk yere daha yakın → hata


# ─── Frontal Düzlem (Ön Kamera) ───

def frontal_knee_valgus_check(poses, frame, side):
    """
    M5: Patella merkezinden yere çizgi → orta ayak hattından geçiyor mu?
    Diz X'i ayak merkezi X'ine göre mediale kayıyorsa → valgus var.
    Returns: True = valgus var (hata), False = yok.
    """
    s = _side(side)
    knee_x = poses[frame, s['knee'], 0]
    foot_mid_x = (poses[frame, s['heel'], 0] + poses[frame, s['foot'], 0]) / 2.0

    # Diz, ayak merkezine göre iç tarafta mı?
    if side == 'left':
        # Sol taraf: valgus = diz sağa kayar (merkeze doğru)
        return knee_x > foot_mid_x
    else:
        # Sağ taraf: valgus = diz sola kayar (merkeze doğru)
        return knee_x < foot_mid_x


def lateral_trunk_lean(poses, frame):
    """
    M6: Gövde orta hattının frontal düzlemde lateral sapması.
    Returns: sapma miktarı (normalize/piksel).
    """
    hip_cx = (poses[frame, LEFT_HIP, 0] + poses[frame, RIGHT_HIP, 0]) / 2.0
    sho_cx = (poses[frame, LEFT_SHOULDER, 0] + poses[frame, RIGHT_SHOULDER, 0]) / 2.0
    return abs(sho_cx - hip_cx)


def stance_width(poses, frame):
    """M7/M8: İki ayak arası mesafe (X ekseni)."""
    return abs(poses[frame, LEFT_ANKLE, 0] - poses[frame, RIGHT_ANKLE, 0])


def shoulder_width(poses, frame):
    """Omuz genişliği."""
    return abs(poses[frame, LEFT_SHOULDER, 0] - poses[frame, RIGHT_SHOULDER, 0])


def foot_rotation_change(poses, frame_ic, frame_mkf, side):
    """
    M9/M10: IC ile MKF arasında ayak rotasyon değişimi (derece).
    Pozitif = iç rotasyon, Negatif = dış rotasyon.

    NOT: MediaPipe sürümü X-Z düzlemini kullanır; RTMPose'da Z yok,
    bu yüzden frontal X-Y düzleminde heel→toe vektörünün açısı ölçülür.
    """
    s = _side(side)
    # IC'deki ayak vektörü (topuk→ayak ucu, X-Y düzlemi)
    vec_ic = poses[frame_ic, s['foot'], :2] - poses[frame_ic, s['heel'], :2]
    # MKF'deki ayak vektörü
    vec_mkf = poses[frame_mkf, s['foot'], :2] - poses[frame_mkf, s['heel'], :2]

    angle_ic = np.arctan2(vec_ic[1], vec_ic[0])
    angle_mkf = np.arctan2(vec_mkf[1], vec_mkf[0])

    rotation_deg = np.degrees(angle_mkf - angle_ic)
    # -180 ~ 180 aralığına normalize et
    if rotation_deg > 180:
        rotation_deg -= 360
    elif rotation_deg < -180:
        rotation_deg += 360
    return rotation_deg


def foot_contact_symmetry(poses, frame, video_width):
    """
    M11: İki ayağın yer temasının simetrik olup olmadığı.
    Returns: y_farki (normalize/piksel).
    """
    left_y = poses[frame, LEFT_ANKLE, 1]
    right_y = poses[frame, RIGHT_ANKLE, 1]
    return abs(left_y - right_y)


def valgus_at_max_flexion(poses, frame_mkf, side):
    """
    M15: MKF anında patella merkezinden yere çizgi → başparmak hattı.
    Çizgi başparmaktan veya medialinden geçerse → valgus var.
    """
    s = _side(side)
    knee_x = poses[frame_mkf, s['knee'], 0]
    toe_x = poses[frame_mkf, s['foot'], 0]

    if side == 'left':
        return knee_x > toe_x  # Sol: diz sağa (mediale) kaymış
    else:
        return knee_x < toe_x  # Sağ: diz sola (mediale) kaymış
