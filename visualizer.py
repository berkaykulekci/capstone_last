"""
LESS Analiz Sistemi - Görselleştirme Modülü
Ön ve yan kamera için ayrı çıktı videoları oluşturur.
Her atlayış sonunda 3 sn duraklama + ölçüm özeti gösterilir.
"""
import cv2
import mediapipe as mp
import numpy as np
import os
from config import OUTPUT_DIR, PAUSE_DURATION_SEC, SPORCU_ID

mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils

# Renk sabitleri (BGR)
WHITE = (255, 255, 255)
GREEN = (0, 255, 0)
RED = (0, 0, 255)
YELLOW = (0, 255, 255)
CYAN = (255, 255, 0)
ORANGE = (0, 165, 255)
BG_DARK = (30, 30, 30)
BG_PANEL = (40, 40, 40)


def _put_text(img, text, pos, scale=0.7, color=WHITE, thick=2):
    cv2.putText(img, text, pos, cv2.FONT_HERSHEY_SIMPLEX, scale, color, thick)


def _draw_madde_line(img, x, y, label, value, puan, is_categorical=False):
    """Tek bir madde satırını videoya çizer."""
    val_str = str(value) if not isinstance(value, float) else f"{value:.1f}"
    text = f"{label}: {val_str}"
    _put_text(img, text, (x, y), 0.65, WHITE, 2)
    (tw, _), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.65, 2)

    if is_categorical:
        status = str(value)
        col = GREEN if puan == 0 else (YELLOW if puan == 1 else RED)
    else:
        status = f"[{puan}p]"
        col = GREEN if puan == 0 else RED
    _put_text(img, f" {status}", (x + tw, y), 0.65, col, 2)


def _draw_pause_frame(frame, jump_idx, results, kamera_tipi, fps):
    """Atlayış sonunda 3 sn gösterilecek özet frame'i oluşturur."""
    h, w = frame.shape[:2]
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, h), BG_DARK, -1)
    frame_out = cv2.addWeighted(overlay, 0.85, frame, 0.15, 0)

    _put_text(frame_out, f"ATLAYIS {jump_idx + 1} SONUCLARI", (w // 2 - 250, 60), 1.2, CYAN, 3)
    _put_text(frame_out, f"Sporcu: {SPORCU_ID} | {kamera_tipi.upper()} KAMERA",
              (w // 2 - 280, 110), 0.8, YELLOW, 2)

    res = results[jump_idx]
    y_pos = 170

    if kamera_tipi == 'yan':
        madde_keys = ['m1', 'm2', 'm3', 'm4', 'm12', 'm13', 'm14', 'm16', 'm17']
    else:
        madde_keys = ['m5', 'm6', 'm7', 'm8', 'm9', 'm10', 'm11', 'm15', 'm17']

    madde_labels = {
        'm1': 'M1  Diz Flex IC',
        'm2': 'M2  Kalca Flex IC',
        'm3': 'M3  Govde Flex IC',
        'm4': 'M4  Plantar Flex',
        'm5': 'M5  Diz Valgus',
        'm6': 'M6  Lat. Govde Flex',
        'm7': 'M7  Durus Genis',
        'm8': 'M8  Durus Dar',
        'm9': 'M9  Ayak Ic Rot',
        'm10': 'M10 Ayak Dis Rot',
        'm11': 'M11 Ayak Simetrisi',
        'm12': 'M12 Diz Flex Degisim',
        'm13': 'M13 Kalca Flex Degisim',
        'm14': 'M14 Govde Flex Degisim',
        'm15': 'M15 Valgus Degisim',
        'm16': 'M16 Eklem ROM',
        'm17': 'M17 Genel Izlenim',
    }

    for mk in madde_keys:
        if mk in res:
            r = res[mk]
            is_cat = mk in ('m16', 'm17')
            _draw_madde_line(frame_out, 80, y_pos, madde_labels[mk], r['olcum'], r['puan'], is_cat)
            y_pos += 45

    # Toplam puan (bu atlayış)
    jump_score = sum(res[k]['puan'] for k in madde_keys if k in res)
    y_pos += 20
    _put_text(frame_out, f"Atlayis {jump_idx + 1} Toplam: {jump_score}", (80, y_pos), 1.0, YELLOW, 3)

    if jump_idx < 2:
        _put_text(frame_out, f">> Atlayis {jump_idx + 2}'ye geciliyor...",
                  (w // 2 - 200, h - 50), 0.8, ORANGE, 2)

    return frame_out


def _draw_ic_pause_frame(frame, jump_idx, jump, kamera_tipi):
    """Algoritmanın IC olarak seçtiği frame'i belirgin şekilde dondurur."""
    h, w = frame.shape[:2]
    frame_out = frame.copy()

    cv2.rectangle(frame_out, (0, 0), (w, 120), BG_DARK, -1)
    cv2.rectangle(frame_out, (0, 0), (w, 120), RED, 4)
    _put_text(frame_out, "INIS ALGILANDI - IC FRAME", (30, 45), 1.0, RED, 3)
    _put_text(
        frame_out,
        f"Atlayis {jump_idx + 1} | {kamera_tipi.upper()} kamera | Frame: {jump['ic']}",
        (30, 88),
        0.8,
        YELLOW,
        2
    )

    cv2.line(frame_out, (0, h // 2), (w, h // 2), RED, 2)
    cv2.circle(frame_out, (w - 70, 60), 28, RED, -1)
    _put_text(frame_out, "IC", (w - 88, 72), 0.9, WHITE, 3)
    return frame_out


def create_camera_video(video_path, jumps, results, kamera_tipi, output_name):
    """
    Tek bir kamera için görsel analiz videosu oluşturur.

    Args:
        video_path: Kaynak video yolu
        jumps: Bu kameradaki atlayış listesi
        results: Birleşik sonuçlar (tüm maddeler)
        kamera_tipi: 'yan' veya 'on'
        output_name: Çıktı dosya adı
    """
    out_path = os.path.join(OUTPUT_DIR, output_name)
    print(f"\n  Görsel çıktı hazırlanıyor: {out_path}")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"  HATA: Video açılamadı: {video_path}")
        return

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0 or np.isnan(fps):
        fps = 30.0

    fourcc = cv2.VideoWriter_fourcc(*'avc1')
    out = cv2.VideoWriter(out_path, fourcc, fps, (w, h))
    if not out.isOpened():
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(out_path, fourcc, fps, (w, h))
    pause_frames = int(fps * PAUSE_DURATION_SEC)

    madde_labels = {
        'm1': 'M1 Diz Flex', 'm2': 'M2 Kalca Flex', 'm3': 'M3 Govde Flex',
        'm4': 'M4 Plantar', 'm5': 'M5 Valgus', 'm6': 'M6 Lat Govde',
        'm7': 'M7 Genis', 'm8': 'M8 Dar', 'm9': 'M9 Ic Rot',
        'm10': 'M10 Dis Rot', 'm11': 'M11 Simetri', 'm12': 'M12 Diz dFlx',
        'm13': 'M13 Kalca dFlx', 'm14': 'M14 Govde dFlx',
        'm15': 'M15 Valgus MKF', 'm16': 'M16 ROM', 'm17': 'M17 Genel'
    }

    if kamera_tipi == 'yan':
        active_keys = ['m1', 'm2', 'm3', 'm4', 'm12', 'm13', 'm14', 'm16', 'm17']
    else:
        active_keys = ['m5', 'm6', 'm7', 'm8', 'm9', 'm10', 'm11', 'm15', 'm17']

    frame_idx = 0

    with mp_pose.Pose(
        static_image_mode=False, model_complexity=2,
        min_detection_confidence=0.5, min_tracking_confidence=0.5
    ) as pose:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            # İskelet çiz
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pose_res = pose.process(rgb)
            if pose_res.pose_landmarks:
                mp_drawing.draw_landmarks(frame, pose_res.pose_landmarks, mp_pose.POSE_CONNECTIONS)

            # Hangi atlayıştayız?
            current_jump = -1
            for i, j in enumerate(jumps):
                if i + 1 < len(jumps):
                    if j['start'] <= frame_idx < jumps[i + 1]['start']:
                        current_jump = i
                        break
                else:
                    if frame_idx >= j['start']:
                        current_jump = i

            # Üst bilgi barı
            _put_text(frame, f"Sporcu: {SPORCU_ID} | {kamera_tipi.upper()} KAMERA | Frame: {frame_idx}",
                      (20, 35), 0.7, YELLOW, 2)

            if current_jump >= 0 and current_jump < len(results):
                j = jumps[current_jump]

                # Durum bilgisi
                if frame_idx < j['ic']:
                    state = "HAVADA"
                    state_col = ORANGE
                elif frame_idx == j['ic']:
                    state = "IC (ILK TEMAS)"
                    state_col = RED
                elif frame_idx == j['mkf']:
                    state = "MKF (MAX FLEKSIYON)"
                    state_col = RED
                elif frame_idx < j['mkf']:
                    state = "IC -> MKF"
                    state_col = CYAN
                else:
                    state = "TOPARLANMA"
                    state_col = GREEN

                _put_text(frame, f"Atlayis: {current_jump + 1}/{len(jumps)} | {state}",
                          (20, 70), 0.8, state_col, 2)

                # Madde değerlerini göster
                res = results[current_jump]
                y_offset = 120
                for mk in active_keys:
                    if mk in res:
                        r = res[mk]
                        val_str = str(r['olcum']) if not isinstance(r['olcum'], float) else f"{r['olcum']:.1f}"
                        label = f"{madde_labels[mk]}: {val_str}"
                        col = GREEN if r['puan'] == 0 else (YELLOW if r['puan'] == 1 else RED)
                        _put_text(frame, label, (20, y_offset), 0.55, col, 2)
                        y_offset += 30

            out.write(frame)
            frame_idx += 1

            # İniş algılandı mı? → Tam IC frame'inde duraklama ekle.
            for i, j in enumerate(jumps):
                if i < len(results) and frame_idx == j['ic'] + 1:
                    pause = _draw_ic_pause_frame(frame, i, j, kamera_tipi)
                    for _ in range(pause_frames):
                        out.write(pause)

    cap.release()
    out.release()
    print(f"  Kaydedildi: {out_path}")
