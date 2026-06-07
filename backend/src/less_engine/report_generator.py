"""
LESS Analiz Sistemi - CSV Rapor Üretimi
"""
import pandas as pd
import os
from .config import OUTPUT_DIR, SPORCU_ID
from .less_rules import karar_m1_to_m15, karar_m16_m17

MADDE_ISIMLERI = {
    'm1': ('İlk temasta diz fleksiyon açısı', 'Yan'),
    'm2': ('İlk temasta kalça fleksiyon açısı', 'Yan'),
    'm3': ('İlk temasta gövde fleksiyon açısı', 'Yan'),
    'm4': ('İlk temasta ayak bileği plantar fleksiyon', 'Yan'),
    'm5': ('İlk temasta diz valgus açısı', 'Ön'),
    'm6': ('İlk temasta lateral gövde fleksiyon', 'Ön'),
    'm7': ('Duruş genişliği: Geniş', 'Ön'),
    'm8': ('Duruş genişliği: Dar', 'Ön'),
    'm9': ('Ayak pozisyonu: Parmak ucu içeride', 'Ön'),
    'm10': ('Ayak pozisyonu: Parmak ucu dışarıda', 'Ön'),
    'm11': ('İlk temasta ayak simetrisi', 'Ön'),
    'm12': ('Diz fleksiyonundaki değişim', 'Yan'),
    'm13': ('MKF kalça fleksiyonu değişimi', 'Yan'),
    'm14': ('MKF gövde fleksiyonu değişimi', 'Yan'),
    'm15': ('Dizde valgus değişimi', 'Ön'),
    'm16': ('Eklem hareketi değişimi', 'Yan'),
    'm17': ('Genel izlenim', 'Yan+Ön'),
}

MADDE_SIRASI = ['m1','m2','m3','m4','m5','m6','m7','m8',
                'm9','m10','m11','m12','m13','m14','m15','m16','m17']


def generate_csv(combined_results, output_path=None):
    """
    CSV raporu oluşturur.
    Her madde bir satır, her atlayış ayrı kolonlarda.
    """
    if output_path is None:
        output_path = os.path.join(OUTPUT_DIR, 'less_sonuclar.csv')

    rows = []
    toplam = 0

    for m_key in MADDE_SIRASI:
        m_name, kamera = MADDE_ISIMLERI[m_key]
        m_no = int(m_key[1:])

        puanlar = []
        row = {
            'sporcu_id': SPORCU_ID,
            'madde_no': m_no,
            'madde_adi': m_name,
            'kamera': kamera,
        }

        for idx, jump_res in enumerate(combined_results):
            if m_key in jump_res:
                r = jump_res[m_key]
                row[f'atlayis_{idx+1}_deger'] = r['olcum']
                row[f'atlayis_{idx+1}_puan'] = r['puan']
                puanlar.append(r['puan'])
            else:
                row[f'atlayis_{idx+1}_deger'] = '-'
                row[f'atlayis_{idx+1}_puan'] = '-'
                puanlar.append(0)

        # Eksik atlayışlar için doldur
        for missing in range(len(combined_results), 3):
            row[f'atlayis_{missing+1}_deger'] = '-'
            row[f'atlayis_{missing+1}_puan'] = '-'
            puanlar.append(0)

        if m_key in ['m16', 'm17']:
            karar = karar_m16_m17(puanlar[:3])
        else:
            karar = karar_m1_to_m15(puanlar[:3])

        row['karar_puani'] = karar
        toplam += karar
        rows.append(row)

    # Toplam satırı
    toplam_row = {
        'sporcu_id': SPORCU_ID,
        'madde_no': '',
        'madde_adi': 'TOPLAM LESS PUANI',
        'kamera': '',
        'atlayis_1_deger': '', 'atlayis_1_puan': '',
        'atlayis_2_deger': '', 'atlayis_2_puan': '',
        'atlayis_3_deger': '', 'atlayis_3_puan': '',
        'karar_puani': toplam,
    }
    rows.append(toplam_row)

    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"\n  CSV kaydedildi: {output_path}")
    print(f"  TOPLAM LESS PUANI: {toplam} / 19")
    return toplam
