# Data VisDrone2019-DET

## Ruang lingkup Day 2

Proyek memakai hanya task **object detection in images** dari
VisDrone2019-DET. Split resmi `train` dan `val` dipertahankan; test-dev dan
test-challenge tidak dipakai pada Gate 2A.

Sumber resmi:

- Repository dataset: <https://github.com/VisDrone/VisDrone-Dataset>
- Halaman unduh AISKYEYE: <https://aiskyeye.com/download/>
- Toolkit anotasi/evaluasi DET:
  <https://github.com/VisDrone/VisDrone2018-DET-toolkit>

Tautan Google Drive dan file ID di `configs/visdrone_sources.yaml` berasal dari
repository resmi. Dataset mentah, arsip ZIP, hasil konversi, dan checkpoint
tidak boleh masuk Git. Hanya source/config, manifest checksum, laporan, dan
contoh visual audit berukuran kecil yang disimpan.

## Status penggunaan dan redistribusi

Pada pemeriksaan 2026-08-07, repository resmi tidak menyertakan file lisensi
dataset yang eksplisit. Toolkit resminya menyatakan kode untuk tujuan riset.
Karena itu repository ini tidak mengklaim VisDrone sebagai data berlisensi
terbuka untuk penggunaan komersial dan tidak mendistribusikan ulang dataset.
Penggunaan publik atau komersial harus memeriksa ketentuan terbaru dan, bila
perlu, meminta izin pemilik dataset.

## Struktur sumber yang diharapkan

```text
data/raw/visdrone2019_det/
  VisDrone2019-DET-train.zip
  VisDrone2019-DET-val.zip
  VisDrone2019-DET-train/
    images/*.jpg
    annotations/*.txt
  VisDrone2019-DET-val/
    images/*.jpg
    annotations/*.txt
```

Mekanisme akses:

```bash
.venv/bin/python -m pip install -r requirements-day2.txt
.venv/bin/python scripts/download_visdrone.py --plan
.venv/bin/python scripts/download_visdrone.py --splits train val
```

Downloader menghitung SHA-256, ukuran arsip, jumlah image/annotation, dan waktu
akses aktual ke `data/metadata/visdrone2019_det_download_manifest.json`.
Ekstraksi menolak path ZIP yang keluar dari direktori tujuan.

## Konversi dan validasi

Kebijakan konversi berada di `configs/visdrone_conversion.yaml`, sedangkan
konfigurasi dataset portabel untuk Ultralytics berada di
`configs/visdrone_5class.yaml`. Jalankan pemeriksaan konfigurasi tanpa data,
tes fixture D00, lalu konversi aktual dengan urutan berikut:

```bash
.venv/bin/python scripts/prepare_visdrone.py --check-config
.venv/bin/python -m pytest -q tests/test_visdrone_dataset.py
.venv/bin/python scripts/prepare_visdrone.py
```

Hasil lokal yang diabaikan Git menggunakan layout berikut:

```text
data/processed/visdrone5/
  images/train/*.jpg
  images/val/*.jpg
  labels/train/*.txt
  labels/val/*.txt
```

Mode default menggunakan hardlink untuk image agar tidak menggandakan byte
dataset di volume yang sama, dengan fallback otomatis ke copy bila filesystem
tidak mendukung hardlink. Label YOLO selalu ditulis terpisah. Converter
mempertahankan split resmi dan validator memeriksa format delapan field, nilai
field kategorikal, bbox positif, hasil clipping/normalisasi, file rusak,
pairing image-label, range kelas YOLO, batas bbox, serta overlap nama file
antar-split.

## Format anotasi resmi

Setiap baris memiliki delapan field:

```text
bbox_left,bbox_top,bbox_width,bbox_height,score,object_category,truncation,occlusion
```

- `score=0` berarti region diabaikan; `score=1` berarti instance dievaluasi.
- Kategori asli: ignored region (0), pedestrian (1), people (2), bicycle (3),
  car (4), van (5), truck (6), tricycle (7), awning-tricycle (8), bus (9),
  motor (10), dan others (11).
- Truncation: 0 tidak terpotong, 1 terpotong sebagian.
- Occlusion: 0 tidak tertutup, 1 tertutup sebagian, 2 tertutup berat.
- Toolkit resmi menyatakan ignored region dan `others` tidak dihitung dalam
  evaluasi.

## Mapping kelas proyek

Gate 2A memakai lima kelas yang dikunci blueprint:

| YOLO ID | Nama proyek | VisDrone ID asli |
|---:|---|---:|
| 0 | pedestrian | 1 |
| 1 | car | 4 |
| 2 | van | 5 |
| 3 | truck | 6 |
| 4 | bus | 9 |

Kategori 0 dan 11 selalu diabaikan. Kategori 2, 3, 7, 8, dan 10 tidak masuk
scope model lima kelas dan dicatat sebagai `excluded_unselected_class`, bukan
sebagai anotasi negatif yang hilang diam-diam.
