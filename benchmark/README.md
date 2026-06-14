# Pose Estimation Benchmark

Ground-truth etiketli veri seti gerektirmeyen metriklerle **MediaPipe BlazePose**, **YOLOv8-pose** ve **kendi pipeline'ımızı** karşılaştırır.

## Kurulum

Benchmark için ek paket gerekmez; mevcut `requirements.txt` yeterlidir.
YOLO testleri için `ultralytics` paketi gerekir:

```bash
pip install ultralytics
```

## Kullanım

Proje kök dizininden çalıştırın:

```bash
# Tüm modeller, varsayılan yollar
python benchmark/benchmark.py

# Özel video dizini ve çıktı klasörü
python benchmark/benchmark.py --videos videos/ --output benchmark/results/

# Hızlı model ile YOLO testi
python benchmark/benchmark.py --yolo-model yolov8n-pose.pt

# Sadece MediaPipe
python benchmark/benchmark.py --skip-yolo --skip-ourmodel
```

### Argümanlar

| Argüman | Varsayılan | Açıklama |
|---------|-----------|----------|
| `--videos` | `videos/` | Video dosyalarının bulunduğu klasör |
| `--output` | `benchmark/results/` | CSV çıktı klasörü |
| `--yolo-model` | `yolov8x-pose.pt` | YOLO model dosyası |
| `--skip-yolo` | — | YOLO modelini atla |
| `--skip-ourmodel` | — | OurModel pipeline'ını atla |

## Video Formatı

`videos/` klasörüne düz liste şeklinde ekleyin:

```
videos/
├── on_kamera.mp4
├── yan_kamera.mp4
├── sporcu2_on.mp4
└── sporcu2_yan.mp4
```

Desteklenen uzantılar: `.mp4`, `.mov`, `.avi`, `.mkv` (büyük/küçük harf fark etmez)

## Çıktılar

```
benchmark/results/
├── summary_results.csv     # Video × model bazında özet
└── per_frame_results.csv   # Her frame için detay
```

### `summary_results.csv` Sütunları

| Sütun | Açıklama |
|-------|----------|
| `video` | Video dosya adı |
| `model` | `MediaPipe` / `YOLO` / `OurModel` |
| `total_frames` | İşlenen frame sayısı |
| `fps` | `total_frames / toplam_inference_süresi` |
| `latency_ms` | `mean(frame_inference_ms)` — ortalama gecikme |
| `missing_kp_pct` | NaN keypoint oranı (interpolasyon öncesi) |
| `jitter_coord_std` | Frame-to-frame koordinat değişimi std'si |
| `jitter_accel_mean` | İkinci türev ortalaması (titreme proxy'si) |
| `limb_self_std` | Femur/tibia oranının kendi baseline'ından sapması |
| `limb_anthropo_pct` | Oran [0.75, 1.05] dışında kalan frame % |
| `biomech_self_std` | Diz açısının kendi baseline'ından sapması |
| `biomech_anthropo_pct` | Biyomekanik sınır dışı frame % |
| `mean_confidence` | Ortalama keypoint confidence/visibility |

### `per_frame_results.csv` Sütunları

| Sütun | Açıklama |
|-------|----------|
| `frame_idx` | Frame indeksi (0'dan başlar) |
| `inference_time_ms` | O frame'in inference süresi |
| `n_missing_kp` | O frame'deki NaN keypoint sayısı |
| `jitter_coord` | Frame-to-frame ortalama konum değişimi |
| `jitter_accel` | İkinci türev (ivme proxy) |
| `femur_len` | Normalize femur uzunluğu (sol+sağ ort.) |
| `tibia_len` | Normalize tibia uzunluğu (sol+sağ ort.) |
| `knee_angle` | Diz fleksiyon açısı (derece) |
| `hip_angle` | Kalça fleksiyon açısı (derece) |
| `mean_confidence` | O frame'in ortalama confidence'ı |

## Model Notları

### MediaPipe BlazePose
- 33 keypoint, `model_complexity=2` (Heavy)
- Visibility skoru confidence olarak kullanılır

### YOLO Pose
- 17 keypoint (COCO formatı)
- `yolov8x-pose.pt` varsayılan; `--yolo-model yolov8n-pose.pt` ile hız/doğruluk değişimi
- Model ilk çalışmada indirilir (~160 MB)
- **Not:** `backend/yolov8x-pose.pt` mevcutsa otomatik kullanılabilir

### OurModel
- MediaPipe inference + `jump_detector.detect_jumps()` post-processing
- Jump detector süresi her frame'e orantılı olarak eklenir
- `fps` ve `latency_ms` değerleri MediaPipe'tan düşük beklenir (beklenen davranış)

## Limb & Açı Hesaplama Detayları

**Ortak keypoint seti** (her iki model için):

| Bölge | MediaPipe indeks | YOLO (COCO) indeks |
|-------|-----------------|-------------------|
| Sol omuz | 11 | 5 |
| Sağ omuz | 12 | 6 |
| Sol kalça | 23 | 11 |
| Sağ kalça | 24 | 12 |
| Sol diz | 25 | 13 |
| Sağ diz | 26 | 14 |
| Sol bilek | 27 | 15 |
| Sağ bilek | 28 | 16 |

**Femur/Tibia oranı anthropometrik normu:** 0.9 ± 0.15 → [0.75, 1.05]  
**Biyomekanik açı sınırları:** Diz [0°, 170°], Kalça [−20°, 140°]
