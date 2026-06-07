# Atlayış Tespit Algoritması v2 — Teknik Dokümantasyon
*(FSM ve Biyomekanik State Machine Mimarisi)*

## Genel Bakış

Eski "sinyal eşiği → olay" (event-based) mantığı yerine, sistemi tamamen **hareket fazı (movement phase) tabanlı Finite State Machine (FSM)** ile yeniden yazdık. Bu sayede sahte sıçramalar, kayan IC frame'leri ve gürültü kaynaklı MKF hataları engellenmiştir.

> **Kaynak dosya:** [jump_detector.py](file:///Users/berkaykulekci/Desktop/capstone_last/jump_detector.py)

---

## 1. Sinyal Ön İşleme (Savitzky-Golay)

Eski sistemdeki *Moving Average* filtrelemesi, "phase lag" (zaman kayması) yarattığı için IC ve MKF anlarını gerçek zamanından birkaç frame ileri atıyordu. 

Yeni sistemde tüm sinyaller `scipy.signal.savgol_filter` ile filtrelenmektedir:
- **Pencere Boyutu:** 11 frame
- **Polinom Derecesi:** 3

**İşlenen Sinyaller:**
- Ayak bileği Y koordinatı (`ankle_y`) ve birinci/ikinci türevleri (velocity, acceleration)
- Kalça merkezi Y koordinatı (`hip_y`) ve türevi
- Diz fleksiyon açısı (`flex`) ve türevi (`flex_deriv`)

Pose landmark x/y koordinatları `pose_extractor.py` içinde 0-1 aralığına normalize edilir. Bu nedenle atlayış tespitindeki yükseklik eşikleri piksel yerine çözünürlükten bağımsız oranlarla çalışır.

---

## 2. IC (Initial Contact) Tespiti

Eski sistem IC'yi sadece "ayak bileği yüksekliğinin minimum olduğu an" olarak hesaplıyordu. Ancak yere temas ettikten sonra ayak bileği hemen yükselmez, bir süre sabit kalır.

Yeni IC mantığı (Velocity/Acceleration tabanlı):
1. **İniş bölgesi (landing phase)** bulunur.
2. Bu bölgede *ankle velocity* (ayak bileği dikey hızı) değerinin **sıfıra yaklaştığı** an bulunur (ayak yere çarpıp durmuştur).
3. Bu an, **acceleration spike** (ivme piki) ile doğrulanır (ani yavaşlama).

---

## 3. MKF (Maximum Knee Flexion) Tespiti

Eski sistemdeki kaba yerel maksimum bulma algoritması yerine `scipy.signal.find_peaks` kullanıldı:
- **Prominence:** 15° (Sadece gerçek derin bükülmeleri alır, diz titremelerini eler)
- **Distance:** 25 frame (İki MKF birbirine çok yakın olamaz)
- **Width:** 5 frame (Çok sivri noise piklerini eler)

---

## 4. Finite State Machine (FSM)

Algoritma 7 farklı state (durum) arasında geçiş yapar. Sadece biyomekanik kurallara uyan geçişlere izin verilir.

| State | Geçiş Kuralı / Biomekanik Karşılığı |
|-------|-------------------------------------|
| `READY` | Kişi kutuda veya yerde stabil duruyor. `ankle_y > AIR_ENTER` olursa `TAKEOFF`'a geçer. |
| `TAKEOFF` | Havalanmaya başladı. Peş peşe 3 frame boyunca eşik üstünde kalırsa `AIRBORNE`'a geçer (Jitter engelleme). |
| `AIRBORNE` | Havada süzülüyor. `ankle_y < AIR_EXIT` olduğunda `LANDING`'e geçer. |
| `LANDING` | Yere temas etti. Velocity bazlı gerçek `ic_frame` hesaplanır. |
| `FLEXION` | Dizler bükülüyor. `flex_deriv < -0.5` olduğunda (bükülme bitip açılmaya başlayınca) `MKF_FOUND`'a geçer. |
| `MKF_FOUND` | Maksimum bükülme noktası kaydedildi. |
| `RECOVERY` | Dizler düzeliyor. `flex < 15°` altına inip 10 frame stabil kalırsa atlayış bitmiş sayılır ve `READY`'e döner. |

### Hysteresis Çift Eşik Sistemi
Zemin ve tavan aralığının %30'u `AIR_ENTER` (havalanma sınırı), %18'i `AIR_EXIT` (yere inme sınırı) olarak belirlendi. Bu oranlar çalışma sırasında 0-1 aralığına çekilir. Böylece sınırda titreyen bir sinyal peş peşe "havada/yerde" state'lerini tetikleyemez.

---

## 5. Temporal Constraints (Zaman Kısıtları)

Biyomekanik olarak imkansız olan süreler filtrelendi:
- Takeoff → IC arası en az **4 frame**
- IC → MKF arası en az **8 frame**
- MKF → Recovery arası en az **10 frame**
Aksi durumlarda FSM iptal edilip `READY` state'ine döner.

---

## 6. Confidence Score (Güvenilirlik Puanı)

Her tespit edilen jump için 0-1 arası bir `confidence` puanı hesaplanır:
- **%35 Uçuş Kalitesi:** Ayak bileği havada ne kadar yükseldi?
- **%30 Peak Prominence:** MKF ne kadar derin bir çömelme?
- **%20 Landing Velocity:** İniş anındaki hız profili mantıklı mı?
- **%15 Temporal Consistency:** Havada kalma ve çömelme süreleri insan fizyolojisine uygun mu?

Puanı 0.25'in altındaki tüm "sahte" sıçramalar elenir.

---

## 7. Merge ve Debug

- FSM 3 atlayış bulamazsa, sadece find_peaks'in kullanıldığı `_method_peak_first` devreye girer.
- Çakışan atlayışlarda her zaman **confidence score'u yüksek olan** tercih edilir.
- `outputs/` klasörüne her analizden sonra `debug_jumps_ön.png` ve `debug_jumps_yan.png` adında 4 grafikli matplotlib dosyaları kaydedilir. Bu grafikler sayesinde IC, MKF noktaları ve FSM state geçişleri görsel olarak doğrulanabilir.
