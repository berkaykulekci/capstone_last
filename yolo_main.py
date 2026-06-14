"""
LESS Analiz Sistemi - YOLO Pose Ana Çalıştırma Scripti
MediaPipe yerine YOLOv8-pose kullanarak aynı analizi yapar.

Kullanım:
    python yolo_main.py                          # varsayılan: test_side=right
    python yolo_main.py --test_side left         # sol dizi test etmek için
    python yolo_main.py --model yolov8n-pose.pt  # hafif model (hız önceliği)

Kısıtlamalar (MediaPipe sürümüne göre):
    - M4  (plantar fleksiyon)   → N/A: YOLO toe landmark içermiyor
    - M9  (ayak iç rotasyon)    → N/A: YOLO toe/heel içermiyor
    - M10 (ayak dış rotasyon)   → N/A: YOLO toe/heel içermiyor
    - Test tarafı otomatik belirlenemiyor (Z yok) → argüman ile verilmeli
"""
import os
import sys
import argparse

from yolo_config import (
    VIDEO_DIR, OUTPUT_DIR, ON_KAMERA_PREFIX, YAN_KAMERA_PREFIX,
    SPORCU_ID, NORMALIZE_VIDEO_FRAME_COORDS, NORMALIZED_FRAME_WIDTH,
    YOLO_MODEL
)
from yolo_pose_extractor import find_video_file, extract_poses, detect_test_side
from yolo_jump_detector import detect_jumps
from yolo_less_rules import (
    evaluate_yan_kamera, evaluate_on_kamera,
    combine_results, compute_total_score, YOLO_NA_MADDE, YOLO_YAKLASIK_MADDE
)


def parse_args():
    p = argparse.ArgumentParser(description='LESS Analizi — YOLO Pose')
    p.add_argument('--test_side', choices=['left', 'right'], default='right',
                   help='Analiz edilecek diz tarafı (varsayılan: right)')
    p.add_argument('--model', default=YOLO_MODEL,
                   help=f'YOLO model dosyası (varsayılan: {YOLO_MODEL})')
    p.add_argument('--no_debug', action='store_true',
                   help='Debug grafikleri oluşturma')
    return p.parse_args()


def main():
    args = parse_args()

    print("=" * 65)
    print("  LESS - İniş Hata Puanlama Sistemi [YOLO Pose]")
    print(f"  Sporcu ID  : {SPORCU_ID}")
    print(f"  Model      : {args.model}")
    print(f"  Test tarafı: {args.test_side.upper()}")
    print("=" * 65)

    # ── 1. Video Dosyalarını Bul ──
    on_path  = find_video_file(ON_KAMERA_PREFIX)
    yan_path = find_video_file(YAN_KAMERA_PREFIX)

    if not on_path:
        print(f"\nHATA: '{VIDEO_DIR}/' dizininde '{ON_KAMERA_PREFIX}' bulunamadı!")
        sys.exit(1)
    if not yan_path:
        print(f"\nHATA: '{VIDEO_DIR}/' dizininde '{YAN_KAMERA_PREFIX}' bulunamadı!")
        sys.exit(1)

    print(f"\n  Ön kamera : {on_path}")
    print(f"  Yan kamera: {yan_path}")

    # ── 2. YOLO Pose Extraction ──
    print("\n[1/5] YOLO Pose çıkarılıyor...")
    print("  Yan kamera:")
    yan_poses, yan_w, yan_h, yan_fps, yan_total = extract_poses(yan_path)
    print("  Ön kamera:")
    on_poses, on_w, on_h, on_fps, on_total = extract_poses(on_path)

    test_side = args.test_side
    print(f"\n[2/5] Test tarafı: {test_side.upper()} (kullanıcı tarafından belirtildi)")
    print("  Not: YOLO 2D modeli Z koordinatı vermediğinden otomatik tespit yapılamıyor.")

    # ── 3. Atlayış Tespiti ──
    print("\n[3/5] Atlayışlar tespit ediliyor...")
    debug_flag = not args.no_debug
    jumps_yan = detect_jumps(yan_poses, test_side, label='YAN', debug=debug_flag)
    jumps_on  = detect_jumps(on_poses,  test_side, label='ÖN',  debug=debug_flag)

    print(f"\n  Yan kamera: {len(jumps_yan)} atlayış")
    for i, j in enumerate(jumps_yan):
        method = j.get('method', 'fsm/peak')
        conf   = j.get('confidence', 0)
        print(f"    Atlayış {i+1}: IC={j['ic']}, MKF={j['mkf']}, conf={conf:.2f} ({method})")

    print(f"  Ön kamera : {len(jumps_on)} atlayış")
    for i, j in enumerate(jumps_on):
        method = j.get('method', 'fsm/peak')
        conf   = j.get('confidence', 0)
        print(f"    Atlayış {i+1}: IC={j['ic']}, MKF={j['mkf']}, conf={conf:.2f} ({method})")

    if len(jumps_yan) == 0:
        print("\nHATA: Yan kamerada atlayış tespit edilemedi!")
        sys.exit(1)
    if len(jumps_on) == 0:
        print("\nHATA: Ön kamerada atlayış tespit edilemedi!")
        sys.exit(1)

    # ── 4. LESS Madde Değerlendirmesi ──
    print("\n[4/5] LESS maddeleri hesaplanıyor...")
    on_analysis_width = NORMALIZED_FRAME_WIDTH if NORMALIZE_VIDEO_FRAME_COORDS else on_w

    yan_results = evaluate_yan_kamera(yan_poses, jumps_yan, test_side)
    on_results  = evaluate_on_kamera(on_poses, jumps_on, test_side, on_analysis_width)
    combined    = combine_results(yan_results, on_results)

    # Terminale yazdır
    print("\n  ── Atlayış Detayları ──")
    for i, res in enumerate(combined):
        print(f"\n  ATLAYIŞ {i+1}:")
        for mk in ['m1','m2','m3','m4','m5','m6','m7','m8','m9','m10',
                   'm11','m12','m13','m14','m15','m16','m17']:
            if mk in res:
                r = res[mk]
                tag = " [~yaklaşık]" if r.get('yaklaşık') else ""
                print(f"    {mk.upper()}: {r['aciklama']}{tag} → Puan: {r['puan']}")

    # ── 5. Skor Hesaplama & Rapor ──
    print("\n[5/5] Skor hesaplanıyor...")
    toplam, skorlar, yaklasik_maddeler = compute_total_score(combined)

    # CSV raporu
    csv_path = os.path.join(OUTPUT_DIR, 'yolo_less_sonuclar.csv')
    _write_csv(csv_path, combined, skorlar, toplam, test_side, args.model, yaklasik_maddeler)

    # ── Özet ──
    print("\n" + "=" * 65)
    print(f"  TAMAMLANDI! [YOLO Pose] Sporcu: {SPORCU_ID}")
    print(f"  TOPLAM LESS PUANI: {toplam} / 19")
    print(f"  (~Yaklaşık maddeler: M{', M'.join(str(m) for m in yaklasik_maddeler)})")
    basarili = "EVET (≤5 puan)" if toplam <= 5 else "HAYIR (>5 puan)"
    print(f"  Başarılı mı: {basarili}")
    print(f"\n  Çıktılar: {csv_path}")
    if debug_flag:
        print(f"  Debug: {OUTPUT_DIR}/debug_yolo_yan.png, debug_yolo_on.png")
    print("=" * 65)


def _write_csv(path, combined, skorlar, toplam, test_side, model, yaklasik_maddeler=None):
    """Basit CSV raporu."""
    import csv
    if yaklasik_maddeler is None:
        yaklasik_maddeler = []
    tum_maddeler = ['m1','m2','m3','m4','m5','m6','m7','m8',
                    'm9','m10','m11','m12','m13','m14','m15','m16','m17']

    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['YOLO LESS Analiz Raporu'])
        w.writerow(['Model', model, 'Test Tarafı', test_side])
        w.writerow(['Not', f'M{yaklasik_maddeler} maddeleri proxy yöntemle yaklaşık hesaplanmıştır.'])
        w.writerow([])
        w.writerow(['Madde', 'Atlayış 1', 'Atlayış 2', 'Atlayış 3', 'Final Puan', 'Not'])

        for mk in tum_maddeler:
            madde_no = int(mk[1:])
            row = [mk.upper()]
            for j in combined:
                row.append(j[mk]['puan'] if mk in j else '-')
            while len(row) < 4:
                row.append('-')
            note = '~yaklaşık (proxy)' if madde_no in yaklasik_maddeler else ''
            row.extend([skorlar.get(mk, '-'), note])
            w.writerow(row)

        w.writerow([])
        w.writerow(['TOPLAM', '', '', '', toplam])
        w.writerow(['MAX', '', '', '', 19])
        w.writerow(['Yaklaşık Maddeler', f"M{yaklasik_maddeler} (proxy hesaplama)"])

    print(f"  CSV kaydedildi: {path}")


if __name__ == '__main__':
    main()
