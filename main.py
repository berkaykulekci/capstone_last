"""
LESS Analiz Sistemi - Ana Çalıştırma Scripti
Ön ve yan kamerayı bağımsız işleyerek 17 maddelik LESS değerlendirmesi yapar.
"""
import os
import sys
from config import (
    VIDEO_DIR, OUTPUT_DIR, ON_KAMERA_PREFIX, YAN_KAMERA_PREFIX, SPORCU_ID,
    NORMALIZE_VIDEO_FRAME_COORDS, NORMALIZED_FRAME_WIDTH
)
from pose_extractor import find_video_file, extract_poses, detect_test_side
from jump_detector import detect_jumps
from less_rules import evaluate_yan_kamera, evaluate_on_kamera, combine_results
from report_generator import generate_csv
from visualizer import create_camera_video


def main():
    print("=" * 60)
    print("  LESS - İniş Hata Puanlama Sistemi")
    print(f"  Sporcu ID: {SPORCU_ID}")
    print("=" * 60)

    # ── 1. Video Dosyalarını Bul ──
    on_path = find_video_file(ON_KAMERA_PREFIX)
    yan_path = find_video_file(YAN_KAMERA_PREFIX)

    if not on_path:
        print(f"\nHATA: '{VIDEO_DIR}/' dizininde '{ON_KAMERA_PREFIX}' bulunamadı!")
        sys.exit(1)
    if not yan_path:
        print(f"\nHATA: '{VIDEO_DIR}/' dizininde '{YAN_KAMERA_PREFIX}' bulunamadı!")
        sys.exit(1)

    print(f"\n  Ön kamera : {on_path}")
    print(f"  Yan kamera: {yan_path}")

    # ── 2. Pose Extraction (Ayrı Ayrı) ──
    print("\n[1/6] Pose çıkarılıyor...")
    print("  Yan kamera:")
    yan_poses, yan_w, yan_h, yan_fps, yan_total = extract_poses(yan_path)
    print("  Ön kamera:")
    on_poses, on_w, on_h, on_fps, on_total = extract_poses(on_path)

    # ── 3. Test Tarafını Belirle ──
    print("\n[2/6] Test tarafı belirleniyor...")
    test_side = detect_test_side(yan_poses)
    print(f"  Test edilen taraf: {test_side.upper()}")

    # ── 4. Atlayış Tespiti (Bağımsız) ──
    print("\n[3/6] Atlayışlar tespit ediliyor...")
    jumps_yan = detect_jumps(yan_poses, test_side, label='YAN')
    jumps_on = detect_jumps(on_poses, test_side, label='ÖN')

    print(f"\n  Yan kamera: {len(jumps_yan)} atlayış")
    for i, j in enumerate(jumps_yan):
        method = j.get('method', 'fsm/peak')
        print(f"    Atlayış {i+1}: IC={j['ic']}, MKF={j['mkf']} ({method})")

    print(f"  Ön kamera : {len(jumps_on)} atlayış")
    for i, j in enumerate(jumps_on):
        method = j.get('method', 'fsm/peak')
        print(f"    Atlayış {i+1}: IC={j['ic']}, MKF={j['mkf']} ({method})")

    if len(jumps_yan) == 0:
        print("\nHATA: Yan kamerada atlayış tespit edilemedi!")
        sys.exit(1)
    if len(jumps_on) == 0:
        print("\nHATA: Ön kamerada atlayış tespit edilemedi!")
        sys.exit(1)

    # ── 5. LESS Madde Değerlendirmesi ──
    print("\n[4/6] LESS maddeleri hesaplanıyor...")
    yan_results = evaluate_yan_kamera(yan_poses, jumps_yan, test_side)
    on_analysis_width = NORMALIZED_FRAME_WIDTH if NORMALIZE_VIDEO_FRAME_COORDS else on_w
    on_results = evaluate_on_kamera(on_poses, jumps_on, test_side, on_analysis_width)

    # Sonuçları birleştir + M17 hesapla
    combined = combine_results(yan_results, on_results)

    # Terminale yazdır
    print("\n  ── Atlayış Detayları ──")
    for i, res in enumerate(combined):
        print(f"\n  ATLAYIŞ {i+1}:")
        for mk in ['m1','m2','m3','m4','m5','m6','m7','m8','m9','m10',
                    'm11','m12','m13','m14','m15','m16','m17']:
            if mk in res:
                r = res[mk]
                print(f"    {mk.upper()}: {r['aciklama']} → Puan: {r['puan']}")

    # ── 6. Çıktılar ──
    print("\n[5/6] CSV raporu oluşturuluyor...")
    toplam = generate_csv(combined)

    print("\n[6/6] Görsel çıktılar oluşturuluyor...")
    create_camera_video(yan_path, jumps_yan, combined, 'yan', 'gorsel_analiz_yan.mp4')
    create_camera_video(on_path, jumps_on, combined, 'on', 'gorsel_analiz_on.mp4')

    # ── Özet ──
    print("\n" + "=" * 60)
    print(f"  TAMAMLANDI! Sporcu: {SPORCU_ID}")
    print(f"  TOPLAM LESS PUANI: {toplam} / 19")
    basarili = "EVET (≤5 puan)" if toplam <= 5 else "HAYIR (>5 puan)"
    print(f"  Başarılı mı: {basarili}")
    print(f"\n  Çıktılar:")
    print(f"    {OUTPUT_DIR}/less_sonuclar.csv")
    print(f"    {OUTPUT_DIR}/gorsel_analiz_yan.mp4")
    print(f"    {OUTPUT_DIR}/gorsel_analiz_on.mp4")
    print("=" * 60)


if __name__ == '__main__':
    main()
