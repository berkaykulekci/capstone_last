"""
LESS Analiz Sistemi - YOLO Pose Konfigürasyonu
COCO 17-keypoint formatı (YOLOv8-pose / YOLO11-pose).
"""
import uuid
import os

# ── Sporcu ID ──
SPORCU_ID = f"S_{uuid.uuid4().hex[:8].upper()}"

# ── YOLO Pose Keypoint İndeksleri (COCO 17) ──
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

# YOLO'da heel ve foot_index YOK (MediaPipe 29-32 arası).
# contact_y hesaplamasında sadece ankle kullanılır.
# ankle_contact_type (M4) ve foot_rotation_change (M9/M10) hesaplanamaz.

# ── YOLO Model Parametreleri ──
YOLO_MODEL = 'yolov8x-pose.pt'   # 'yolov8n-pose.pt' hız, 'yolov8x-pose.pt' doğruluk
YOLO_CONF_THRESHOLD = 0.5         # keypoint güvenilirlik eşiği; altı NaN'a çevrilir
YOLO_PERSON_CONF = 0.5            # kişi tespiti güvenilirlik eşiği

# ── Video/Pose Normalizasyonu ──
NORMALIZE_VIDEO_FRAME_COORDS = True
NORMALIZED_FRAME_WIDTH = 1.0
# YOLO 2D only — Z koordinatı yok, test tarafı otomatik belirlenemez.
DEFAULT_TEST_SIDE = 'right'

# ── Atlayış Tespit Parametreleri ──
# MediaPipe ile aynı değerler; sinyal tipleri aynı.
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
M1_KNEE_FLEX_THRESHOLD    = 30
M4_TIBIA_ANGLE_THRESHOLD  = 15
M6_LATERAL_RATIO          = 0.08
M9_M10_ROTATION_THRESHOLD = 30
M9_M10_OFFSET_THRESHOLD   = 0.04
M11_SYMMETRY_RATIO        = 0.04
M12_KNEE_CHANGE_THRESHOLD = 45
M16_SOFT_THRESHOLD        = 90
M16_STIFF_THRESHOLD       = 45

# ── Kamera-Madde Eşlemeleri ──
YAN_KAMERA_MADDELERI = [1, 2, 3, 4, 12, 13, 14, 16]
ON_KAMERA_MADDELERI  = [5, 6, 7, 8, 9, 10, 11, 15]
KOMBINE_MADDE        = [17]

# ── Dosya Yolları ──
VIDEO_DIR    = 'videos'
OUTPUT_DIR   = 'outputs'
ON_KAMERA_PREFIX  = 'on_kamera'
YAN_KAMERA_PREFIX = 'yan_kamera'
SUPPORTED_EXTENSIONS = ['mp4', 'MOV', 'mov', 'MP4', 'avi', 'AVI']

os.makedirs(OUTPUT_DIR, exist_ok=True)
