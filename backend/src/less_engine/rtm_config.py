"""
LESS Analiz Sistemi - RTMPose-WholeBody Konfigürasyonu
COCO-WholeBody 133-keypoint formatı (RTMPose / RTMW, ONNX runtime ile).

YOLO sürümünden farkları:
  - Gövde keypoint'leri 0-16 COCO-17 ile identik.
  - Ayak keypoint'leri (17-22) MEVCUT → heel + big toe var.
    → M4, M9, M10 PROXY OLMADAN tam (exact) hesaplanabilir.
  - Z koordinatı yok (sadece confidence) → test tarafı otomatik belirlenemez.
"""
import uuid
import os

# ── Sporcu ID ──
SPORCU_ID = f"S_{uuid.uuid4().hex[:8].upper()}"

# ── RTMPose-WholeBody Keypoint İndeksleri ──
# Gövde (0-16): COCO-17, YOLO ile birebir aynı sıralama.
NOSE          = 0
LEFT_EYE      = 1
RIGHT_EYE     = 2
LEFT_EAR      = 3
RIGHT_EAR     = 4
LEFT_SHOULDER = 5
RIGHT_SHOULDER= 6
LEFT_ELBOW    = 7
RIGHT_ELBOW   = 8
LEFT_WRIST    = 9
RIGHT_WRIST   = 10
LEFT_HIP      = 11
RIGHT_HIP     = 12
LEFT_KNEE     = 13
RIGHT_KNEE    = 14
LEFT_ANKLE    = 15
RIGHT_ANKLE   = 16

# Ayak (17-22): COCO-WholeBody foot keypoint'leri.
#   17 L_big_toe, 18 L_small_toe, 19 L_heel,
#   20 R_big_toe, 21 R_small_toe, 22 R_heel
# angle_calculator/less_rules'ın beklediği isimlerle eşle:
#   FOOT_INDEX = big toe (MediaPipe 31/32 karşılığı), HEEL = heel (MediaPipe 29/30).
LEFT_FOOT_INDEX  = 17   # sol başparmak
LEFT_SMALL_TOE   = 18
LEFT_HEEL        = 19
RIGHT_FOOT_INDEX = 20   # sağ başparmak
RIGHT_SMALL_TOE  = 21
RIGHT_HEEL       = 22

# Bu backend'de tutulan kompakt keypoint sayısı (0..22 dilimi).
RTM_NUM_KEYPOINTS = 23

# ── RTMPose Model Parametreleri (rtmlib + ONNX) ──
# rtmlib resmi ONNX modellerini ilk çağrıda indirip cache'ler (manuel dosya gerekmez).
#   mode: 'performance' (en doğru, 384x288) | 'balanced' (varsayılan) | 'lightweight' (hız)
#   device: 'cpu' | 'cuda' (onnxruntime-gpu kuruluysa) | 'mps'
RTM_MODE   = os.getenv('RTM_MODE', 'performance')
RTM_DEVICE = os.getenv('RTM_DEVICE', 'cpu')
RTM_BACKEND = os.getenv('RTM_BACKEND', 'onnxruntime')
RTM_KPT_CONF_THRESHOLD = 0.3   # keypoint güvenilirlik eşiği; altı NaN'a çevrilir

# ── Video/Pose Normalizasyonu ──
NORMALIZE_VIDEO_FRAME_COORDS = True
NORMALIZED_FRAME_WIDTH = 1.0
# RTMPose 2D — Z yok, test tarafı otomatik belirlenemez.
DEFAULT_TEST_SIDE = 'right'

# ── Atlayış Tespit Parametreleri ──
# MediaPipe/YOLO ile aynı değerler.
EXPECTED_JUMPS = 3

AIR_ENTER_RATIO = 0.30
AIR_EXIT_RATIO  = 0.18
IC_SEARCH_BEFORE_FRAMES = 8
IC_SEARCH_AFTER_FRAMES  = 18
IC_CONSEC_GROUND_FRAMES = 2

BOX_BASELINE_FRAMES       = 20
BOX_LEVEL_TOLERANCE_NORM  = 0.025
BOX_LEVEL_TOLERANCE_PIXELS= 25
BOX_DROP_MIN_RATIO        = 0.45
BOX_DROP_SEARCH_FRAMES    = 28
BOX_DROP_MIN_DISTANCE     = 45

SAVGOL_WINDOW = 11
SAVGOL_POLY   = 3

PEAK_PROMINENCE = 15
PEAK_DISTANCE   = 25
PEAK_WIDTH      = 5

CONSEC_AIR_FRAMES         = 3
RECOVERY_FLEX_THRESHOLD   = 15
RECOVERY_STABLE_FRAMES    = 10

MIN_TAKEOFF_TO_IC  = 4
MIN_IC_TO_MKF      = 8
MIN_MKF_TO_RECOVERY= 10

MKF_SEARCH_WINDOW = 60

CONF_W_FLIGHT      = 0.35
CONF_W_PROMINENCE  = 0.30
CONF_W_LANDING_VEL = 0.20
CONF_W_TEMPORAL    = 0.15
CONF_MIN_THRESHOLD = 0.25
JUMP_MERGE_TOLERANCE = 20

# ── LESS Eşik Değerleri ──
# Ayak keypoint'leri mevcut → M4/M9/M10 için proxy eşik gerekmez (exact hesap).
M1_KNEE_FLEX_THRESHOLD    = 30
M6_LATERAL_RATIO          = 0.08
M9_M10_ROTATION_THRESHOLD = 30   # derece (heel→toe vektör açı değişimi)
M11_SYMMETRY_RATIO        = 0.04
M12_KNEE_CHANGE_THRESHOLD = 45
M16_SOFT_THRESHOLD        = 90
M16_STIFF_THRESHOLD       = 45

# ── Kamera-Madde Eşlemeleri ──
YAN_KAMERA_MADDELERI = [1, 2, 3, 4, 12, 13, 14, 16]
ON_KAMERA_MADDELERI  = [5, 6, 7, 8, 9, 10, 11, 15]
KOMBINE_MADDE        = [17]

# ── Görselleştirme ──
PAUSE_DURATION_SEC = 3

# ── Dosya Yolları ──
VIDEO_DIR    = 'videos'
OUTPUT_DIR   = 'outputs'
ON_KAMERA_PREFIX  = 'on_kamera'
YAN_KAMERA_PREFIX = 'yan_kamera'
SUPPORTED_EXTENSIONS = ['mp4', 'MOV', 'mov', 'MP4', 'avi', 'AVI']

os.makedirs(OUTPUT_DIR, exist_ok=True)
