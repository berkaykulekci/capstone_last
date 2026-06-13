"""
LESS Analiz Sistemi - YOLO Görsel Video Üretici (Backend)
Pre-computed (N,17,3) poses kullanır — YOLO yeniden çalıştırılmaz.
"""
import cv2
import numpy as np

from .yolo_config import (
    LEFT_SHOULDER, RIGHT_SHOULDER,
    LEFT_ELBOW, RIGHT_ELBOW,
    LEFT_WRIST, RIGHT_WRIST,
    LEFT_HIP, RIGHT_HIP,
    LEFT_KNEE, RIGHT_KNEE,
    LEFT_ANKLE, RIGHT_ANKLE,
    NOSE, LEFT_EYE, RIGHT_EYE, LEFT_EAR, RIGHT_EAR,
)

# (start, end, BGR color)
SKELETON_COLORED = [
    # Kafa
    (NOSE, LEFT_EYE,        (200, 200, 0)),
    (NOSE, RIGHT_EYE,       (200, 200, 0)),
    (LEFT_EYE, LEFT_EAR,   (200, 200, 0)),
    (RIGHT_EYE, RIGHT_EAR, (200, 200, 0)),
    # Omuzlar arası
    (LEFT_SHOULDER, RIGHT_SHOULDER, (255, 255, 255)),
    # Sol kol — mavi
    (LEFT_SHOULDER, LEFT_ELBOW,  (255, 120, 40)),
    (LEFT_ELBOW,    LEFT_WRIST,  (255, 160, 80)),
    # Sağ kol — turuncu
    (RIGHT_SHOULDER, RIGHT_ELBOW,  (40, 120, 255)),
    (RIGHT_ELBOW,    RIGHT_WRIST,  (80, 160, 255)),
    # Gövde
    (LEFT_SHOULDER,  LEFT_HIP,  (180, 255, 180)),
    (RIGHT_SHOULDER, RIGHT_HIP, (180, 255, 180)),
    (LEFT_HIP, RIGHT_HIP,       (180, 255, 180)),
    # Sol bacak — açık mavi
    (LEFT_HIP,   LEFT_KNEE,   (255, 200, 80)),
    (LEFT_KNEE,  LEFT_ANKLE,  (255, 230, 120)),
    # Sağ bacak — sarı
    (RIGHT_HIP,  RIGHT_KNEE,  (80, 200, 255)),
    (RIGHT_KNEE, RIGHT_ANKLE, (120, 230, 255)),
]

MADDE_LABELS = {
    'm1':  'M1  Diz Flex',
    'm2':  'M2  Kalca Flex',
    'm3':  'M3  Govde Flex',
    'm4':  'M4  Plantar ~',
    'm5':  'M5  Valgus',
    'm6':  'M6  Lat.Govde',
    'm7':  'M7  Genis',
    'm8':  'M8  Dar',
    'm9':  'M9  Ic Rot ~',
    'm10': 'M10 Dis Rot ~',
    'm11': 'M11 Simetri',
    'm12': 'M12 dDiz',
    'm13': 'M13 dKalca',
    'm14': 'M14 dGovde',
    'm15': 'M15 Valgus MKF',
    'm16': 'M16 ROM',
    'm17': 'M17 Genel',
}

YAN_MADDELER = ['m1', 'm2', 'm3', 'm4', 'm12', 'm13', 'm14', 'm16', 'm17']
ON_MADDELER  = ['m5', 'm6', 'm7', 'm8', 'm9', 'm10', 'm11', 'm15', 'm17']

PAUSE_DURATION_SEC = 2.0
CONF_THR = 0.25


def _to_px(kp, w, h):
    """
    Normalize (x,y) → piksel.
    Pose extractor Y'yi tersler (0=alt,1=üst); frame'de 0=üst olduğundan (1-y) kullanılır.
    """
    return int(np.clip(kp[0], 0, 1) * w), int(np.clip(1.0 - kp[1], 0, 1) * h)


def _draw_skeleton(frame, kps, w, h):
    """Renk kodlu COCO-17 skeleton."""
    for a, b, color in SKELETON_COLORED:
        if kps[a, 2] > CONF_THR and kps[b, 2] > CONF_THR:
            pa, pb = _to_px(kps[a], w, h), _to_px(kps[b], w, h)
            cv2.line(frame, pa, pb, color, 3, cv2.LINE_AA)

    for idx, kp in enumerate(kps):
        if kp[2] > CONF_THR:
            px = _to_px(kp, w, h)
            cv2.circle(frame, px, 6, (255, 255, 255), -1, cv2.LINE_AA)
            cv2.circle(frame, px, 6, (0, 0, 0), 1, cv2.LINE_AA)


def _blend_rect(frame, x1, y1, x2, y2, color=(15, 15, 15), alpha=0.65):
    """Yarı saydam dikdörtgen."""
    roi = frame[y1:y2, x1:x2]
    overlay = np.full_like(roi, color, dtype=np.uint8)
    cv2.addWeighted(overlay, alpha, roi, 1 - alpha, 0, roi)
    frame[y1:y2, x1:x2] = roi


def _draw_score_panel(frame, jump_results, active_keys, jump_idx, total_jumps, w, h):
    """Sol alt köşede compact skor paneli."""
    pad   = 10
    lh    = 20          # satır yüksekliği
    rows  = len(active_keys)
    ph    = rows * lh + 54   # panel yüksekliği
    pw    = 210
    x1, y1 = pad, h - ph - pad
    x2, y2 = x1 + pw, h - pad

    _blend_rect(frame, x1, y1, x2, y2)

    ty = y1 + 16
    cv2.putText(frame, f'YOLO | Atlayis {jump_idx+1}/{total_jumps}',
                (x1 + 6, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (220, 220, 220), 1, cv2.LINE_AA)
    ty += 14
    cv2.putText(frame, '~ proxy hesaplama',
                (x1 + 6, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.34, (120, 160, 255), 1, cv2.LINE_AA)
    ty += 14

    cv2.line(frame, (x1 + 4, ty), (x2 - 4, ty), (80, 80, 80), 1)
    ty += 10

    if jump_results is None:
        cv2.putText(frame, 'Analiz verisi yok', (x1 + 6, ty),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.36, (150, 150, 150), 1, cv2.LINE_AA)
        return

    for mk in active_keys:
        if mk not in jump_results:
            ty += lh
            continue
        r     = jump_results[mk]
        label = MADDE_LABELS.get(mk, mk.upper())
        puan  = r['puan']
        is_approx = r.get('yaklaşık', False)
        color = (80, 80, 240) if r['hata'] else (80, 210, 80)
        text  = f'{label}: {puan}'
        cv2.putText(frame, text, (x1 + 6, ty),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.36, color, 1, cv2.LINE_AA)
        if is_approx:
            tw = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.36, 1)[0][0]
            cv2.putText(frame, '~', (x1 + 6 + tw + 2, ty),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.3, (100, 160, 255), 1, cv2.LINE_AA)
        ty += lh


def _draw_event_marker(frame, label, border_color, w, h):
    """IC / MKF olayı — kenarda renkli çerçeve + sağ üstte metin."""
    cv2.rectangle(frame, (3, 3), (w - 3, h - 3), border_color, 4)
    # Metin için yarı saydam arka plan
    tw, th = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.75, 2)[0]
    tx, ty = w - tw - 16, 36
    _blend_rect(frame, tx - 6, ty - th - 4, tx + tw + 6, ty + 4, alpha=0.6)
    cv2.putText(frame, label, (tx, ty),
                cv2.FONT_HERSHEY_SIMPLEX, 0.75, border_color, 2, cv2.LINE_AA)


def create_yolo_camera_video(video_path: str, poses: np.ndarray, jumps: list,
                              results: list, kamera_tipi: str, output_path: str):
    """
    Args:
        video_path:   Kaynak video dosyası
        poses:        (N,17,3) — normalize koordinatlar (Y terslenmiş, 0=alt)
        jumps:        detect_jumps() çıktısı
        results:      evaluate_yan/on_kamera() çıktısı
        kamera_tipi:  'yan' veya 'on'
        output_path:  Çıktı MP4 yolu
    """
    active_keys = YAN_MADDELER if kamera_tipi == 'yan' else ON_MADDELER

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"  [YOLO-VIS] HATA: Video açılamadı: {video_path}")
        return

    w   = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h   = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0 or np.isnan(fps):
        fps = 30.0

    fourcc = cv2.VideoWriter_fourcc(*'avc1')
    out = cv2.VideoWriter(output_path, fourcc, fps, (w, h))
    if not out.isOpened():
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (w, h))

    pause_frames = int(fps * PAUSE_DURATION_SEC)

    # Her frame → atlayış indeksi
    frame_to_jump: dict[int, int] = {}
    for j_idx, j in enumerate(jumps):
        for f in range(j.get('ic', 0), j.get('recovery', j.get('mkf', 0)) + 1):
            frame_to_jump[f] = j_idx

    # IC / MKF frame seti
    ic_frames  = {j.get('ic'):  j_idx for j_idx, j in enumerate(jumps)}
    mkf_frames = {j.get('mkf'): j_idx for j_idx, j in enumerate(jumps)}

    frame_idx = 0
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        j_idx    = frame_to_jump.get(frame_idx)
        jump_res = results[j_idx] if (j_idx is not None and j_idx < len(results)) else None

        # Skeleton
        if frame_idx < len(poses):
            _draw_skeleton(frame, poses[frame_idx], w, h)

        # IC / MKF olayı
        event_drawn = False
        if frame_idx in ic_frames:
            ji = ic_frames[frame_idx]
            _draw_event_marker(frame, f'IC  J{ji+1}', (60, 60, 255), w, h)
            event_drawn = True
        elif frame_idx in mkf_frames:
            ji = mkf_frames[frame_idx]
            _draw_event_marker(frame, f'MKF J{ji+1}', (40, 210, 255), w, h)
            event_drawn = True

        # Skor paneli
        _draw_score_panel(frame, jump_res, active_keys,
                          (j_idx if j_idx is not None else 0),
                          len(jumps), w, h)

        # Üst etiket
        _blend_rect(frame, 0, 0, 260, 30, alpha=0.55)
        cv2.putText(frame, f'YOLO | {kamera_tipi.upper()} KAMERA',
                    (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)

        out.write(frame)

        # IC anında duraklat
        if event_drawn and frame_idx in ic_frames:
            for _ in range(pause_frames):
                out.write(frame)

        frame_idx += 1

    cap.release()
    out.release()
    print(f"  [YOLO-VIS] Kaydedildi: {output_path}")
