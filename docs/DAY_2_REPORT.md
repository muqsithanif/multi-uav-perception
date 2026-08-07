# Laporan Day 2 — VisDrone dan Validasi Training Pipeline

Tanggal pencatatan: 7 Agustus 2026 (Asia/Jakarta)

## Status akhir

**Gate 2A: BELUM LOLOS. Pekerjaan dihentikan pada checkpoint D2.3.**

Tidak ada full fine-tuning, baseline E00, training Colab, tracking, ROS 2,
swarm simulation, atau pekerjaan Day 3+ yang dijalankan. Tidak ada metrik
deteksi, metrik training, atau checkpoint yang diklaim.

## Audit awal

- Repository berada pada branch `main`; pekerjaan Day 1 tidak diubah.
- Gate 1 tetap menggunakan bukti pada `docs/DAY_1_REPORT.md`.
- Environment WSL Ubuntu 24.04 dan venv proyek tersedia.
- Ruang kosong volume proyek yang terukur sebelum unduhan:
  108.679.077.888 byte.
- Dataset, arsip, hasil konversi, dan bobot tetap diabaikan oleh Git.

## Checkpoint yang selesai

### D2.1 — mekanisme akses data

Commit: `6155f78` (`feat: add official VisDrone access mechanism`).

- Sumber resmi, file ID Google Drive, ukuran yang diumumkan, jumlah image yang
  diharapkan, dan status lisensi dicatat.
- Downloader memiliki pemeriksaan ruang kosong, unduhan resumable ke file
  parsial, ekstraksi ZIP aman, SHA-256, jumlah image, dan pairing anotasi.
- `--plan`, kompilasi Python, dry-run dependensi, dan aturan ignore lulus.

### D2.2 — converter dan validator

Commit: `e03dcf2` (`feat: add tested VisDrone conversion pipeline`).

- Mapping proyek dikunci ke pedestrian, car, van, truck, dan bus.
- Kategori ignored dan kelas di luar scope dihitung terpisah.
- Validator mencakup format sumber, range kelas, bbox invalid, clipping,
  normalisasi YOLO, file rusak, pairing, batas bbox, dan overlap split.
- Pemeriksaan konfigurasi lulus.
- Tes fixture sintetis: **11 passed, 0 failed**; waktu pytest 2,03 detik.
- Tes ini bukan validasi dataset resmi dan tidak menghasilkan metrik dataset.

## Checkpoint D2.3 — terblokir

Perintah resmi yang dicoba:

```text
.venv/bin/python scripts/download_visdrone.py --splits train val
```

Hasil aktual:

- Google Drive train gagal dengan
  `gdown.exceptions.FileURLRetrievalError`: kuota publik terlalu banyak
  digunakan.
- Google Drive validation gagal dengan error kuota yang sama.
- Fallback BaiduYun resmi dapat menampilkan metadata file:
  train 1.549.875.511 byte dan validation 81.625.797 byte.
- Permintaan unduhan anonim BaiduYun untuk train ditolak dengan `errno=2`.
- Fallback browser gagal sebelum navigasi karena runtime tidak memiliki izin
  membaca path profil Windows (`EPERM`).
- Direktori raw tidak berisi arsip final, file parsial, atau split hasil
  ekstraksi; checksum tidak tersedia.

Bukti terstruktur berada di:

- `experiments/D00_visdrone_conversion_smoke/summary.json`
- `experiments/D01_visdrone_validation/download_attempts.json`
- `results/day2/gate_2a_status.json`

Karena train/val resmi belum tersedia, struktur aktual, distribusi kelas,
visualisasi anotasi, baseline E00, smoke training 2–3 epoch, penyimpanan
checkpoint, dan resume training berstatus `not_run`. Menjalankan tahap-tahap
tersebut tanpa data yang sudah divalidasi akan melanggar urutan Gate 2A.
