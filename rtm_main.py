"""
LESS Analiz Sistemi - RTMPose-WholeBody Ana Çalıştırma Scripti
MediaPipe/YOLO yerine RTMPose-WholeBody (ONNX) kullanarak aynı analizi yapar.

Kullanım:
    python rtm_main.py                        # varsayılan: test_side=right
    python rtm_main.py --test_side left       # sol dizi test etmek için

RTMPose-WholeBody avantajı (YOLO'ya göre):
    - heel + big toe keypoint'leri MEVCUT
    - M4 (plantar fleksiyon), M9 (iç rot), M10 (dış rot) PROXY OLMADAN exact hesaplanır
    - Yaklaşık madde YOKTUR; tüm 17 madde tam, max skor 19

Kısıtlama:
    - Test tarafı otomatik belirlenemiyor (Z yok) → argüman ile verilmeli
    - models/ dizininde rtm_det.onnx + rtmw-x.onnx gereklidir (bkz. README)
"""
import os
import sys
import argparse

from rtm_config import (
    VIDEO_DIR, OUTPUT_DIR, ON_KAMERA_PREFIX, YAN_KAMERA_PREFIX,
    SPORCU_ID, NORMALIZE_VIDEO_FRAME_COORDS, NORMALIZED_FRAME_WIDTH,
    RTM_MODE
)
from rtm_pose_extractor import find_video_file, extract_poses, detect_test_side
from rtm_jump_detector import detect_jumps
from rtm_less_rules import (
    evaluate_yan_kamera, evaluate_on_kamera,
    combine_results, compute_total_score, RTM_NA_MADDE, RTM_YAKLASIK_MADDE
)


def parse_args():
    p = argparse.ArgumentParser(description='LESS Analizi — RTMPose-WholeBody')
    p.add_argument('--test_side', choices=['left', 'right'], default='right',
                   help='Analiz edilecek diz tarafı (varsayılan: right)')
    p.add_argument('--no_debug', action='store_true',
                   help='Debug grafikleri oluşturma')
    return p.parse_args()


def main():
    args = parse_args()

    print("=" * 65)
    print("  LESS - İniş Hata Puanlama Sistemi [RTMPose-WholeBody]")
    print(f"  Sporcu ID  : {SPORCU_ID}")
    print(f"  Model      : RTMPose-WholeBody (rtmlib, mode={RTM_MODE})")
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

    # ── 2. RTMPose Extraction ──
    print("\n[1/5] RTMPose-WholeBody çıkarılıyor...")
    print("  Yan kamera:")
    yan_poses, yan_w, yan_h, yan_fps, yan_total = extract_poses(yan_path)
    print("  Ön kamera:")
    on_poses, on_w, on_h, on_fps, on_total = extract_poses(on_path)

    test_side = args.test_side
    print(f"\n[2/5] Test tarafı: {test_side.upper()} (kullanıcı tarafından belirtildi)")
    print("  Not: RTMPose 2D modeli Z koordinatı vermediğinden otomatik tespit yapılamıyor.")

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
                print(f"    {mk.upper()}: {r['aciklama']} → Puan: {r['puan']}")

    # ── 5. Skor Hesaplama & Rapor ──
    print("\n[5/5] Skor hesaplanıyor...")
    toplam, skorlar, yaklasik_maddeler = compute_total_score(combined)

    # CSV raporu
    csv_path = os.path.join(OUTPUT_DIR, 'rtm_less_sonuclar.csv')
    _write_csv(csv_path, combined, skorlar, toplam, test_side, yaklasik_maddeler)

    # ── Özet ──
    print("\n" + "=" * 65)
    print(f"  TAMAMLANDI! [RTMPose-WholeBody] Sporcu: {SPORCU_ID}")
    print(f"  TOPLAM LESS PUANI: {toplam} / 19")
    if yaklasik_maddeler:
        print(f"  (~Yaklaşık maddeler: M{', M'.join(str(m) for m in yaklasik_maddeler)})")
    else:
        print("  Tüm 17 madde exact hesaplandı (yaklaşık madde yok).")
    basarili = "EVET (≤5 puan)" if toplam <= 5 else "HAYIR (>5 puan)"
    print(f"  Başarılı mı: {basarili}")
    print(f"\n  Çıktılar: {csv_path}")
    if debug_flag:
        print(f"  Debug: {OUTPUT_DIR}/debug_rtm_yan.png, debug_rtm_on.png")
    print("=" * 65)


def _write_csv(path, combined, skorlar, toplam, test_side, yaklasik_maddeler=None):
    """Basit CSV raporu."""
    import csv
    if yaklasik_maddeler is None:
        yaklasik_maddeler = []
    tum_maddeler = ['m1','m2','m3','m4','m5','m6','m7','m8',
                    'm9','m10','m11','m12','m13','m14','m15','m16','m17']

    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['RTMPose-WholeBody LESS Analiz Raporu'])
        w.writerow(['Model', f'RTMPose-WholeBody (rtmlib, {RTM_MODE})', 'Test Tarafı', test_side])
        w.writerow(['Not', 'Tüm maddeler exact hesaplandı (heel + toe keypoint mevcut).'])
        w.writerow([])
        w.writerow(['Madde', 'Atlayış 1', 'Atlayış 2', 'Atlayış 3', 'Final Puan'])

        for mk in tum_maddeler:
            row = [mk.upper()]
            for j in combined:
                row.append(j[mk]['puan'] if mk in j else '-')
            while len(row) < 4:
                row.append('-')
            row.append(skorlar.get(mk, '-'))
            w.writerow(row)

        w.writerow([])
        w.writerow(['TOPLAM', '', '', '', toplam])
        w.writerow(['MAX', '', '', '', 19])

    print(f"  CSV kaydedildi: {path}")


if __name__ == '__main__':
    main()
