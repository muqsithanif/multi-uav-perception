# Laporan Day 2 — VisDrone dan Validasi Training Pipeline

Tanggal pembaruan: 7 Agustus 2026 (Asia/Jakarta)

## 1. Objective

Membangun jalur data VisDrone2019-DET yang resmi, dapat direproduksi, dan aman
untuk training YOLO lima kelas. Milestone ini mencakup unduhan, checksum,
konversi, validasi programatik, sanitasi cacat sumber yang terukur, dan visual
audit.

## Status

**Gate 2A data: LULUS DENGAN SANITASI (`passed_with_sanitization`).**

**Gate 2 keseluruhan: BELUM LOLOS.** Baseline E00 dan fine-tuning nano belum
dijalankan, sehingga belum ada metrik deteksi, log training, atau checkpoint
fine-tuned yang diklaim.

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
- `tests/test_visdrone_dataset.py` dan `tests/test_visdrone_audit.py` mencakup
  parser, konversi, sanitasi, validator, pemilihan sampel, dan rendering.

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
.venv/bin/python -m pytest -q tests/test_visdrone_dataset.py tests/test_visdrone_audit.py
.venv/bin/python scripts/prepare_visdrone.py
.venv/bin/python scripts/render_visdrone_audit.py --split val --samples 6
```

Hasil unit test: **15 passed, 0 failed** dalam 4,15 detik.

| Split | Input image/label | Anotasi sumber | Output object | Output image/label |
|---|---:|---:|---:|---:|
| train | 6.471 / 6.471 | 353.550 | 267.960 | 6.471 / 6.471 |
| val | 548 / 548 | 40.169 | 25.884 | 548 / 548 |

Distribusi object lima kelas setelah konversi:

| Split | pedestrian | car | van | truck | bus |
|---|---:|---:|---:|---:|---:|
| train | 79.337 | 144.866 | 24.956 | 12.875 | 5.926 |
| val | 8.844 | 14.064 | 1.975 | 750 | 251 |

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

## 4. Artifacts

- `data/metadata/visdrone2019_det_download_manifest.json`
- `data/metadata/visdrone5_manifest.json`
- `experiments/D01_visdrone_validation/summary.json`
- `results/day2/visual_audit/summary.json`
- enam overlay di `results/day2/visual_audit/`

Dataset mentah, ZIP, dan hasil konversi tetap diabaikan Git. Manifest, laporan,
dan sampel visual audit berukuran terbatas dapat disimpan sebagai bukti.

## 5. Known limitations / blocker

- Repository resmi tidak menyertakan lisensi dataset eksplisit; proyek tidak
  mengklaim hak redistribusi atau penggunaan komersial.
- Visual audit enam image adalah pemeriksaan sampel, bukan audit manual seluruh
  7.019 image. Scene padat menyebabkan teks overlay bertumpuk dan beberapa
  anotasi jauh/teroklusi tetap ambigu.
- Gate 2 belum selesai karena baseline E00, smoke training, checkpoint
  fine-tuned, log, dan kurva training belum ada.
- Tidak ada metrik precision, recall, mAP, latency, atau FPS yang dilaporkan
  pada milestone data ini.

## 6. Next smallest milestone

Jalankan E00 pretrained baseline pada split validation dengan konfigurasi dan
raw output yang tersimpan. Setelah E00 terverifikasi, jalankan smoke training
2–3 epoch untuk membuktikan checkpoint dan resume path sebelum training utama.
