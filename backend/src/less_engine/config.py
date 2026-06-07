"""
LESS Analiz Sistemi - Konfigürasyon
Sabitler, eşik değerleri, keypoint indeksleri ve kamera-madde eşlemeleri.
"""
import uuid
import os

# ── Sporcu ID ──
SPORCU_ID = f"S_{uuid.uuid4().hex[:8].upper()}"

# ── MediaPipe Keypoint İndeksleri (33 landmark) ──
NOSE = 0
LEFT_EAR = 7
RIGHT_EAR = 8
LEFT_SHOULDER = 11
RIGHT_SHOULDER = 12
LEFT_ELBOW = 13
RIGHT_ELBOW = 14
LEFT_WRIST = 15
RIGHT_WRIST = 16
LEFT_HIP = 23
RIGHT_HIP = 24
LEFT_KNEE = 25
RIGHT_KNEE = 26
LEFT_ANKLE = 27
RIGHT_ANKLE = 28
LEFT_HEEL = 29
RIGHT_HEEL = 30
LEFT_FOOT_INDEX = 31
RIGHT_FOOT_INDEX = 32

# ── MediaPipe Model Parametreleri ──
POSE_MODEL_COMPLEXITY = 2  # 0=Lite, 1=Full, 2=Heavy
MIN_DETECTION_CONFIDENCE = 0.5
MIN_TRACKING_CONFIDENCE = 0.5

# ── Video/Pose Normalizasyonu ──
# True iken x/y landmark koordinatları video çözünürlüğünden bağımsız 0-1 aralığında tutulur.
NORMALIZE_VIDEO_FRAME_COORDS = True
NORMALIZED_FRAME_WIDTH = 1.0
TEST_SIDE_Z_EPS_NORMALIZED = 0.01
TEST_SIDE_Z_EPS_PIXELS = 10

# ── Atlayış Tespit Parametreleri ──
EXPECTED_JUMPS = 3

# Hysteresis çift-eşik (zemin-tavan aralığı oranı)
AIR_ENTER_RATIO = 0.30     # GROUND→AIR geçişi
AIR_EXIT_RATIO = 0.18      # AIR→GROUND geçişi
IC_SEARCH_BEFORE_FRAMES = 8
IC_SEARCH_AFTER_FRAMES = 18
IC_CONSEC_GROUND_FRAMES = 2

# Kutu üstünden yere iniş tespiti
BOX_BASELINE_FRAMES = 20
BOX_LEVEL_TOLERANCE_NORM = 0.025
BOX_LEVEL_TOLERANCE_PIXELS = 25
BOX_DROP_MIN_RATIO = 0.45
BOX_DROP_SEARCH_FRAMES = 28
BOX_DROP_MIN_DISTANCE = 45

# Savitzky-Golay filtre parametreleri
SAVGOL_WINDOW = 11
SAVGOL_POLY = 3

# find_peaks parametreleri (MKF tespiti)
PEAK_PROMINENCE = 15       # derece
PEAK_DISTANCE = 25         # frame
PEAK_WIDTH = 5             # frame

# FSM geçiş parametreleri
CONSEC_AIR_FRAMES = 3      # TAKEOFF→AIRBORNE için ardışık havada frame
RECOVERY_FLEX_THRESHOLD = 15  # derece (RECOVERY→READY geçişi)
RECOVERY_STABLE_FRAMES = 10  # READY'e dönmek için stabil frame sayısı

# Temporal biyomekanik kısıtlar (frame)
MIN_TAKEOFF_TO_IC = 4
MIN_IC_TO_MKF = 8
MIN_MKF_TO_RECOVERY = 10

# MKF arama penceresi
MKF_SEARCH_WINDOW = 60

# Confidence score ağırlıkları
CONF_W_FLIGHT = 0.35
CONF_W_PROMINENCE = 0.30
CONF_W_LANDING_VEL = 0.20
CONF_W_TEMPORAL = 0.15
CONF_MIN_THRESHOLD = 0.25  # Bu altındaki jump'lar elenir

# Merge parametreleri
JUMP_MERGE_TOLERANCE = 20  # frame

# ── LESS Eşik Değerleri ──
M1_KNEE_FLEX_THRESHOLD = 30      # derece
M6_LATERAL_RATIO = 0.08          # omuz genişliği oranı
M9_M10_ROTATION_THRESHOLD = 30   # derece
M11_SYMMETRY_RATIO = 0.04        # video genişliği oranı
M12_KNEE_CHANGE_THRESHOLD = 45   # derece
M16_SOFT_THRESHOLD = 90          # toplam ROM derece
M16_STIFF_THRESHOLD = 45         # toplam ROM derece

# ── Kamera-Madde Eşlemeleri ──
YAN_KAMERA_MADDELERI = [1, 2, 3, 4, 12, 13, 14, 16]
ON_KAMERA_MADDELERI = [5, 6, 7, 8, 9, 10, 11, 15]
KOMBINE_MADDE = [17]

# ── Görselleştirme ──
PAUSE_DURATION_SEC = 3

# ── Dosya Yolları ──
VIDEO_DIR = 'videos'
OUTPUT_DIR = 'outputs'
ON_KAMERA_PREFIX = 'on_kamera'
YAN_KAMERA_PREFIX = 'yan_kamera'
SUPPORTED_EXTENSIONS = ['mp4', 'MOV', 'mov', 'MP4', 'avi', 'AVI']
DEFAULT_TEST_SIDE = 'right'

os.makedirs(OUTPUT_DIR, exist_ok=True)
