"""
LESS Analiz Sistemi - YOLO Açı Hesaplama Modülü
COCO 17-keypoint için uyarlanmış biyomekanik hesaplamalar.

MediaPipe sürümünden farklar:
  - HEEL ve FOOT_INDEX landmark'ları yok → ankle_contact_type döner 'unknown'
  - foot_rotation_change → hesaplanamaz, 0.0 döner
  - Diğer açılar (knee, hip, trunk, valgus, lateral lean, stance) aynı mantık
"""
import numpy as np
from yolo_config import (
    LEFT_HIP, RIGHT_HIP, LEFT_KNEE, RIGHT_KNEE,
    LEFT_ANKLE, RIGHT_ANKLE,
    LEFT_SHOULDER, RIGHT_SHOULDER
)


def _side(side):
    """Verilen taraf için YOLO landmark indekslerini döndürür."""
    if side == 'left':
        return dict(hip=LEFT_HIP, knee=LEFT_KNEE, ankle=LEFT_ANKLE,
                    shoulder=LEFT_SHOULDER)
    return dict(hip=RIGHT_HIP, knee=RIGHT_KNEE, ankle=RIGHT_ANKLE,
                shoulder=RIGHT_SHOULDER)


def angle_3pt(a, b, c):
    """B noktasındaki açı (derece). BA ve BC vektörleri arasındaki açı."""
    ba = a - b
    bc = c - b
    cos_val = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-8)
    return np.degrees(np.arccos(np.clip(cos_val, -1.0, 1.0)))


# ─── Sagittal Düzlem (Yan Kamera) ───

def knee_flexion(poses, frame, side):
    """Diz fleksiyon açısı = 180 - (Kalça-Diz-Ayak bileği açısı)."""
    s = _side(side)
    a = poses[frame, s['hip'],   :2]
    b = poses[frame, s['knee'],  :2]
    c = poses[frame, s['ankle'], :2]
    return 180.0 - angle_3pt(a, b, c)


def hip_flexion(poses, frame, side):
    """Kalça fleksiyon açısı = 180 - (Omuz-Kalça-Diz açısı)."""
    s = _side(side)
    a = poses[frame, s['shoulder'], :2]
    b = poses[frame, s['hip'],      :2]
    c = poses[frame, s['knee'],     :2]
    return 180.0 - angle_3pt(a, b, c)


def trunk_flexion(poses, frame):
    """Gövde fleksiyon açısı: gövde vektörünün dikey eksenden sapması (derece)."""
    hip_c = (poses[frame, LEFT_HIP,   :2] + poses[frame, RIGHT_HIP,   :2]) / 2.0
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
    vertical = np.array([0.0, 1.0])
    return np.degrees(np.arccos(np.clip(np.dot(tibia / norm, vertical), -1.0, 1.0)))


def ankle_contact_type(poses, frame, side):
    """Geriye dönük uyumluluk aliası."""
    return 'unknown'


# ─── Frontal Düzlem (Ön Kamera) ───

def frontal_knee_valgus_check(poses, frame, side):
    """
    M5: Diz X'i ayak merkezi X'ine göre mediale kayıyorsa → valgus var.
    YOLO'da toe yok, ankle merkez olarak kullanılır.
    """
    s = _side(side)
    knee_x   = poses[frame, s['knee'],   0]
    foot_x   = poses[frame, s['ankle'],  0]  # toe yoksa ankle kullan

    if side == 'left':
        return knee_x > foot_x
    else:
        return knee_x < foot_x


def lateral_trunk_lean(poses, frame):
    """M6: Gövde orta hattının frontal düzlemde lateral sapması."""
    hip_cx = (poses[frame, LEFT_HIP,      0] + poses[frame, RIGHT_HIP,      0]) / 2.0
    sho_cx = (poses[frame, LEFT_SHOULDER, 0] + poses[frame, RIGHT_SHOULDER, 0]) / 2.0
    return abs(sho_cx - hip_cx)


def stance_width(poses, frame):
    """M7/M8: İki ayak arası mesafe (X ekseni)."""
    return abs(poses[frame, LEFT_ANKLE, 0] - poses[frame, RIGHT_ANKLE, 0])


def shoulder_width(poses, frame):
    """Omuz genişliği."""
    return abs(poses[frame, LEFT_SHOULDER, 0] - poses[frame, RIGHT_SHOULDER, 0])


def knee_ankle_frontal_offset(poses, frame, side):
    """
    Önden kamerada ankle_x - knee_x farkı. İşaret sağ bacak referanslıdır:
    pozitif → dış rotasyon proxy, negatif → iç rotasyon proxy.
    """
    s = _side(side)
    raw = poses[frame, s['ankle'], 0] - poses[frame, s['knee'], 0]
    return raw if side == 'right' else -raw


def foot_rotation_proxy(poses, frame_ic, frame_mkf, side):
    """
    IC→MKF arası knee-ankle frontal offset değişimi. M9/M10 proxy.
    Pozitif delta → dış rotasyon, negatif delta → iç rotasyon.
    """
    return (knee_ankle_frontal_offset(poses, frame_mkf, side)
            - knee_ankle_frontal_offset(poses, frame_ic,  side))


def foot_rotation_change(poses, frame_ic, frame_mkf, side):
    """Geriye dönük uyumluluk aliası."""
    return foot_rotation_proxy(poses, frame_ic, frame_mkf, side)


def foot_contact_symmetry(poses, frame, video_width):
    """M11: İki ayağın Y farkı — asimetrik iniş kontrolü."""
    left_y  = poses[frame, LEFT_ANKLE,  1]
    right_y = poses[frame, RIGHT_ANKLE, 1]
    return abs(left_y - right_y)


def valgus_at_max_flexion(poses, frame_mkf, side):
    """
    M15: MKF anında valgus. YOLO'da toe yok, ankle kullanılır.
    MediaPipe toe bazlı hesapla karşılaştırıldığında yaklaşık sonuç verir.
    """
    s = _side(side)
    knee_x = poses[frame_mkf, s['knee'],  0]
    toe_x  = poses[frame_mkf, s['ankle'], 0]  # proxy

    if side == 'left':
        return knee_x > toe_x
    else:
        return knee_x < toe_x
