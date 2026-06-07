# LESS - İniş Hata Puanlama Sistemi

Kutunun üzerinden atlayan sporcuların iniş mekaniklerini **17 maddelik LESS** çerçevesiyle otomatik değerlendiren kural tabanlı biyomekanik analiz sistemi.

Bu klasör artık aynı zamanda SportsMD full-stack uygulamasını da içerir:

- `backend/` - FastAPI API, kullanıcı girişi, athlete kayıtları, video upload ve LESS analiz servisi
- `frontend/` - React dashboard, athlete oluşturma, yan/ön video yükleme ve çıktı linkleri
- `mobile/` - Expo mobil uygulama, giriş ve athlete dashboard
- Kök dizindeki Python dosyaları - LESS analiz motorunun standalone sürümü

## Kurulum

Standalone analiz için:

```bash
pip install -r requirements.txt
```

Full-stack backend için:

```bash
cd backend
pip install -r requirements.txt
uvicorn src.main:app --reload --port 8000
```

Frontend için ayrı terminalde:

```bash
cd frontend
npm install
npm start
```

Mobil için:

```bash
cd mobile
npm install
npx expo start
```

## Kullanım

### Standalone analiz

1. `videos/` dizinine iki video koyun:
   - `on_kamera.mp4` (veya .MOV) — Önden çekilmiş video
   - `yan_kamera.mp4` (veya .MOV) — Yandan çekilmiş video

2. Her videoda **3 adet drop-jump** bulunmalıdır.

3. Analizi çalıştırın:
```bash
python main.py
```

### Dashboard üzerinden analiz

1. Backend'i `http://localhost:8000` üzerinde çalıştırın.
2. Frontend'i `http://localhost:3000` üzerinde açın.
3. Kullanıcı oluşturup giriş yapın.
4. `+ Add Athlete` ile athlete oluşturun.
5. Athlete detayında yan kamera ve ön kamera videolarını yükleyin.
6. Analiz bitince CSV ve iki işaretlenmiş video çıktı linki ekranda görünür.

Athlete ID'leri `ATH_...` formatında unique üretilir ve backend veritabanına kaydedilir. `.env` içinde `DATABASE_URL` yoksa backend otomatik olarak `backend/sportsmd.db` SQLite dosyasını kullanır.

## Normalizasyon

Pose çıkarımı sırasında video landmark x/y koordinatları varsayılan olarak **0-1 aralığına** normalize edilir. Böylece atlayış tespitindeki `AIR_ENTER_RATIO` ve `AIR_EXIT_RATIO` eşikleri video çözünürlüğünden bağımsız çalışır.

## Mimari

| Modül | Görev |
|-------|-------|
| `config.py` | Sabitler, eşikler, kamera-madde eşlemeleri |
| `pose_extractor.py` | MediaPipe BlazePose ile pose çıkarma |
| `jump_detector.py` | Hibrit 3-katmanlı atlayış tespiti |
| `angle_calculator.py` | Biyomekanik açı hesaplamaları |
| `less_rules.py` | 17 madde kural tabanlı puanlama |
| `visualizer.py` | Ayrı ön/yan görsel çıktı videoları |
| `report_generator.py` | CSV rapor üretimi |
| `main.py` | Ana orkestrasyon |

## Çıktılar

```
outputs/
├── less_sonuclar.csv       # 17 madde + karar puanları
├── gorsel_analiz_yan.mp4   # Yan kamera iskelet + canlı metrikler
└── gorsel_analiz_on.mp4    # Ön kamera iskelet + canlı metrikler
```

## Kamera-Madde Eşlemesi

| Madde | Açıklama | Kamera |
|-------|----------|--------|
| M1 | İlk temasta diz fleksiyon açısı | Yan |
| M2 | İlk temasta kalça fleksiyon açısı | Yan |
| M3 | İlk temasta gövde fleksiyon açısı | Yan |
| M4 | İlk temasta ayak bileği plantar fleksiyon | Yan |
| M5 | İlk temasta diz valgus açısı | Ön |
| M6 | İlk temasta lateral gövde fleksiyon | Ön |
| M7 | Duruş genişliği: Geniş | Ön |
| M8 | Duruş genişliği: Dar | Ön |
| M9 | Ayak pozisyonu: Parmak ucu içeride | Ön |
| M10 | Ayak pozisyonu: Parmak ucu dışarıda | Ön |
| M11 | İlk temasta ayak simetrisi | Ön |
| M12 | Diz fleksiyonundaki değişim | Yan |
| M13 | MKF kalça fleksiyonu değişimi | Yan |
| M14 | MKF gövde fleksiyonu değişimi | Yan |
| M15 | Dizde valgus değişimi | Ön |
| M16 | Eklem hareketi değişimi | Yan |
| M17 | Genel izlenim | Yan + Ön |

## Puanlama

- **M1-M15**: 3 sıçramadan ≥2'sinde hata → 1 puan
- **M16-M17**: En az 1 Sert/Kötü → 2, ≥2 Orta → 1, Diğer → 0
- **Toplam**: Min 0 – Max 19
