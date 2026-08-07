# Laporan Day 2 — VisDrone dan Validasi Training Pipeline

Tanggal pembaruan: 7 Agustus 2026 (Asia/Jakarta)

## 1. Objective

Membangun jalur data VisDrone2019-DET yang resmi, dapat direproduksi, dan aman
untuk training YOLO lima kelas. Milestone ini mencakup unduhan, checksum,
konversi, validasi programatik, sanitasi cacat sumber yang terukur, analisis
distribusi kelas, dan audit visual.

## Status

**Checkpoint data Day 2: LULUS DENGAN SANITASI
(`passed_with_sanitization`).**

**E00 pretrained baseline: LULUS pada subset validation terkunci.**

**Colab smoke training: BELUM DIJALANKAN (`not_run`).** Runner dan notebook
sudah diuji, tetapi belum ada checkpoint atau bukti resume aktual.

**Gate 2A keseluruhan: BELUM LOLOS.** Smoke training, penyimpanan checkpoint
persisten, dan resume training belum dibuktikan. Full fine-tuning tidak
dijalankan.

## 2. Files dan konfigurasi

- `configs/visdrone_sources.yaml` mengunci sumber resmi dan split train/val.
- `configs/visdrone_conversion.yaml` mengunci mapping lima kelas serta lokasi
  input/output dan laporan.
- `scripts/download_visdrone.py` mengunduh, memeriksa SHA-256, dan mengekstrak
  ZIP secara aman.
- `scripts/visdrone_dataset.py` mengonversi dan memvalidasi anotasi.
- `scripts/prepare_visdrone.py` menghasilkan manifest dan laporan validasi.
- `scripts/render_visdrone_audit.py` memilih dan merender sampel validation
  secara deterministik.
- `scripts/analyze_visdrone_distribution.py` menghasilkan ringkasan JSON/CSV
  dan plot distribusi kelas.
- `scripts/evaluate_pretrained_baseline.py` mengunci subset, mapping kelas,
  inferensi, matching IoU, metrik, timing, dan kurva E00.
- `configs/e00_pretrained_baseline.yaml` menyimpan protokol E00 aktual.
- `scripts/run_visdrone_smoke_training.py` menyiapkan subset smoke, memisahkan
  training menjadi dua phase, mempertahankan optimizer checkpoint, dan
  memverifikasi resume aktual.
- `configs/visdrone_smoke_train.yaml` membatasi scope ke 256 train, 64 val, dan
  tiga epoch; `full_fine_tuning` dikunci `false`.
- `notebooks/day2_visdrone_smoke_colab.ipynb` mengotomasi setup Colab, validasi
  dataset, smoke training, persistensi Google Drive, dan push artefak ringkas.
- Tiga modul test mencakup parser, konversi, sanitasi, validator, pemilihan
  sampel, rendering, perhitungan distribusi, checksum artefak, mapping baseline,
  konversi bbox, dan matching prediksi.

Kebijakan sanitasi bbox dan trailing comma dikomit pada `0725378`
(`fix: sanitize measured VisDrone annotation defects`).

## 3. Verification dan hasil aktual

### Akses dan integritas sumber

Manifest unduhan mencatat pasangan image/anotasi lengkap:

| Split | Image | Anotasi | Ukuran ZIP | SHA-256 |
|---|---:|---:|---:|---|
| train | 6.471 | 6.471 | 1.549.875.511 byte | `86a77eba93137bfc16e4993860de9245b0675c0dba0d3ab98fb458699e256f84` |
| val | 548 | 548 | 81.638.851 byte | `abeea063037e5d20398837deb11084e652402a34ddf4f207bdf541a6f2a35ef9` |

Unduhan awal melalui Google Drive sempat terblokir kuota publik; data kemudian
tersedia dari mekanisme resmi/authorized yang sama dan diverifikasi terhadap
metadata sumber sebelum konversi.

### Konversi dan validasi

Perintah yang lulus:

```text
.venv/bin/python scripts/prepare_visdrone.py --check-config
.venv/bin/python -m pytest -q tests/test_visdrone_dataset.py tests/test_visdrone_audit.py tests/test_visdrone_distribution.py
.venv/bin/python scripts/prepare_visdrone.py
.venv/bin/python scripts/render_visdrone_audit.py --split val --samples 6
.venv/bin/python scripts/analyze_visdrone_distribution.py
.venv/bin/python scripts/evaluate_pretrained_baseline.py --config configs/e00_pretrained_baseline.yaml
```

Hasil akhir suite Day 2: **27 passed, 0 failed** dalam 32,55 detik. Pada
checkpoint distribusi, satu percobaan test sempat gagal karena konstanta
SHA-256 fixture baru salah; konstanta dikoreksi ke digest fixture aktual dan
suite kemudian lulus.

| Split | Input image/label | Anotasi sumber | Output object | Output image/label |
|---|---:|---:|---:|---:|
| train | 6.471 / 6.471 | 353.550 | 267.960 | 6.471 / 6.471 |
| val | 548 / 548 | 40.169 | 25.884 | 548 / 548 |

Distribusi object lima kelas setelah konversi:

| Split | pedestrian | car | van | truck | bus |
|---|---:|---:|---:|---:|---:|
| train | 79.337 | 144.866 | 24.956 | 12.875 | 5.926 |
| val | 8.844 | 14.064 | 1.975 | 750 | 251 |

Kelas dominan pada kedua split adalah `car` (54,062547% train dan 54,334724%
val), sedangkan kelas minoritas adalah `bus` (2,211524% train dan 0,969711%
val). Rasio jumlah kelas terbesar terhadap terkecil adalah 24,445832 pada
train dan 56,031873 pada val. Pergeseran proporsi terbesar terjadi pada
`pedestrian`: +4,560049 poin persentase pada val terhadap train.

Validator output menemukan **0 bbox invalid**, **0 overlap nama file antar
split**, dan jumlah object hasil parsing ulang sama dengan jumlah hasil
konversi pada kedua split.

Laporan final merekam `source_revision=0725378` dan
`tracked_source_dirty=true`. Dirty tracked files pada saat snapshot hanya
README/dokumentasi milestone yang sedang diperbarui; converter dan validator
sesuai dengan revision tersebut.

### Sanitasi sumber

- Tiga bbox train memiliki height `0`; tidak ada kasus serupa di val.
- Dua bbox invalid adalah ignored region dengan `score=0`.
- Satu bbox invalid adalah class sumber 4 (`car`) dengan `score=1`; baris ini
  dikeluarkan dari label training dan dicatat sebagai
  `invalid_selected_source_box_count=1`.
- Sebanyak 34 baris train memiliki satu trailing comma kosong dan dinormalisasi
  menjadi delapan field. Val tidak memiliki kasus tersebut.
- Sanitasi tidak membuat ukuran bbox buatan dan tidak menghasilkan bbox output
  invalid.

### Visual audit

Enam overlay validation diperiksa pada resolusi asli. Sampel mencakup seluruh
lima kelas. Kotak tidak menunjukkan offset/skala sistematis, tetap di dalam
frame, dan mapping kelas konsisten dengan object beranotasi yang terlihat.
Status visual audit: **passed**.

### E00 pretrained baseline

Run yang diterima adalah `E00_20260807_003` pada revision `9e5727e`. Protokol
memakai 128 dari 548 image validation (23,36%) yang dipilih merata berdasarkan
urutan nama file. Selection SHA-256 adalah
`7e1bd549153bea5fa2d6f1e17a4e7f29f57f11157c6c277441a6d00520c265bd`.
Subset memuat 6.090 object: 1.946 pedestrian, 3.417 car, 487 van, 187 truck,
dan 53 bus.

Checkpoint `yolo26n.pt` berukuran 5.544.453 byte dengan SHA-256
`9b09cc8bf347f0fc8a5f7657480587f25db09b34bf33b0652110fb03a8ad4fef`.
Evaluasi berjalan di CPU/FP32 dengan image size 640, confidence 0,001, NMS IoU
0,7, maksimum 300 deteksi, batch 4, dan IoU evaluasi 0,50-0,95.

| Scope | Instances | Precision | Recall | mAP50 | mAP50-95 |
|---|---:|---:|---:|---:|---:|
| macro 5 kelas | 6.090 | 0,289228 | 0,173370 | 0,154190 | 0,096881 |
| pedestrian | 1.946 | 0,392821 | 0,124358 | 0,119576 | 0,049120 |
| car | 3.417 | 0,634277 | 0,379865 | 0,408989 | 0,246381 |
| van | 487 | 0,000000 | 0,000000 | 0,000000 | 0,000000 |
| truck | 187 | 0,171500 | 0,155080 | 0,095931 | 0,072219 |
| bus | 53 | 0,247544 | 0,207547 | 0,146452 | 0,116683 |

Mapping output pretrained adalah COCO `person -> pedestrian`, `car -> car`,
`truck -> truck`, dan `bus -> bus`. Ground truth `van` tetap dihitung, tetapi
checkpoint COCO tidak memiliki kelas van terpisah; karena itu prediction count
dan seluruh metrik van adalah nol.

Waktu wall untuk bagian evaluasi adalah 13,223372 detik atau 103,307593
ms/image. Total tahap inference yang dilaporkan Ultralytics adalah 8,285059
detik. Angka ini adalah satu run CPU untuk validasi pipeline, bukan benchmark
performa; loading model dan pembuatan manifest terjadi sebelum timer evaluasi.

Dua percobaan sebelumnya gagal sebelum metrik dihitung karena sumber berupa
list path dikonversi loader menjadi nama sintetis `image0.jpg`. Keduanya
disimpan sebagai `E00_20260807_001_failed_order` dan
`E00_20260807_002_failed_synthetic_names` dengan `metrics: null`. Run ketiga
memakai file-list `.txt` yang mempertahankan identitas filename.

### Persiapan smoke training Colab

Runner telah diuji untuk validasi config, pembuatan subset, pemeriksaan
checkpoint mentah, penolakan checkpoint yang sudah di-strip, jumlah baris
hasil, dan kompilasi seluruh code cell notebook. Preflight read-only pada data
aktual menghasilkan cakupan berikut:

| Split smoke | Image | pedestrian | car | van | truck | bus |
|---|---:|---:|---:|---:|---:|---:|
| train | 256 | 4.196 | 5.951 | 1.074 | 481 | 305 |
| val | 64 | 1.075 | 1.548 | 198 | 107 | 40 |

Tidak ada training lokal atau Colab yang dijalankan saat persiapan ini.
`training_metrics` dan `checkpoint` tetap `null` pada status Gate 2A.

## 4. Artifacts

- `data/metadata/visdrone2019_det_download_manifest.json`
- `data/metadata/visdrone5_manifest.json`
- `experiments/D01_visdrone_validation/summary.json`
- `experiments/D02_visdrone_dataset_audit/summary.json`
- `experiments/E00_20260807_003/summary.json`
- `experiments/E00_20260807_003/subset_manifest.json`
- `results/day2/dataset_analysis/class_distribution.json`
- `results/day2/dataset_analysis/class_distribution.csv`
- `results/day2/dataset_analysis/class_distribution.png`
- `results/day2/visual_audit/summary.json`
- `results/day2/E00_20260807_003/metrics.csv`
- empat kurva E00 di `results/day2/E00_20260807_003/curves/`
- `results/day2/gate_2a_status.json`
- `notebooks/day2_visdrone_smoke_colab.ipynb`
- enam overlay di `results/day2/visual_audit/`

Dataset mentah, ZIP, dan hasil konversi tetap diabaikan Git. Manifest, laporan,
dan sampel visual audit berukuran terbatas dapat disimpan sebagai bukti.

## 5. Known limitations / blocker

- Repository resmi tidak menyertakan lisensi dataset eksplisit; proyek tidak
  mengklaim hak redistribusi atau penggunaan komersial.
- Visual audit enam image adalah pemeriksaan sampel, bukan audit manual seluruh
  7.019 image. Scene padat menyebabkan teks overlay bertumpuk dan beberapa
  anotasi jauh/teroklusi tetap ambigu.
- E00 memakai subset 128 image; hasilnya tidak mewakili evaluasi full validation.
- Kelas van tidak tersedia pada label COCO checkpoint pretrained dan tidak
  dipetakan secara heuristik ke car/truck.
- Timing E00 adalah satu validasi pipeline CPU tanpa protokol benchmark penuh;
  tidak ada klaim FPS atau real-time.
- Gate 2A belum selesai karena smoke training, checkpoint persisten, dan bukti
  resume belum ada. Tidak ada metrik fine-tuned yang dilaporkan.
- Runtime Colab private memerlukan otorisasi Google Drive dan secret GitHub dari
  pemilik akun; notebook belum pernah dijalankan pada GPU Colab.
