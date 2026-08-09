# Laporan Day 3 — Export dan Agreement Deployment

Tanggal pembaruan: 9 Agustus 2026 (Asia/Jakarta)

## Objective dan status

Milestone ini mengekspor checkpoint E01_20260807_001/best.pt ke ONNX FP32 dan OpenVINO FP16, lalu membuktikan kedua backend memuat, menjalankan inferensi pada input identik, dan memenuhi toleransi agreement terhadap reference PyTorch.

**Gate deployment: LULUS (passed).** Run B01_20260809_005 menghasilkan dan memvalidasi kedua format serta memenuhi seluruh toleransi agreement pada 16 image validation yang dipilih deterministik.

## Konfigurasi dan verifikasi

- Config: configs/e01_deployment_export.yaml
- Checkpoint: models/checkpoints/E01_20260807_001/best.pt (5.363.845 byte, SHA-256 d5fcbeab43dc5706ea743d834094495be241836da2b25910c1cd1757f84faea5)
- Perintah: YOLO_CONFIG_DIR=/tmp .venv/bin/python scripts/export_and_validate_detector.py --config configs/e01_deployment_export.yaml
- Lingkungan: WSL2 Ubuntu 24.04, Python 3.12.3, PyTorch 2.13.0+cpu, Ultralytics 8.4.115, ONNX 1.22.0, ONNX Runtime 1.28.0, dan OpenVINO 2026.3.0. Artefak final merekam source revision ba6be91 dengan tracked worktree bersih.
- Perangkat yang benar-benar tersedia: CPU Intel Core Ultra 7 155H; OpenVINO hanya diuji pada CPU.
- Protokol: 16 image evenly-spaced dari locked subset E01 (128 image), imgsz=640, confidence 0,25, NMS IoU 0,7, max_det=300, square padding (rect=false), dua warm-up, dan satu pengukuran per image/backend.

Rect=false diperlukan karena export ONNX/OpenVINO ber-input statis 640×640. Dengan rect=true, PyTorch dapat memakai padding persegi-panjang sehingga masukan antar-backend berbeda dan agreement bukan lagi uji export yang adil.

## Hasil export dan agreement

| Backend | Validasi format | Ukuran artefak | Agreement terhadap PyTorch | Status |
|---|---|---:|---|---|
| ONNX Runtime FP32 | ONNX checker dan CPUExecutionProvider lulus | 9.760.468 byte | 498/498 reference dan candidate match; mean box IoU 0,999999; maks. selisih confidence 0,000014 | Lulus |
| OpenVINO FP16 | XML/BIN dibaca dan dikompilasi pada CPU | XML 492.606 + BIN 4.802.358 byte | 496/498 reference match (99,598%); 496/496 candidate match; mean box IoU 0,999026; maks. selisih confidence 0,014266 | Lulus |

Toleransi ONNX: minimum 99,5% match pada kedua arah, mean box IoU 0,999, dan selisih confidence maksimum 0,005. Toleransi OpenVINO: minimum 98% match pada kedua arah, mean box IoU 0,99, dan selisih confidence maksimum 0,02. Semua pemeriksaan lulus.

## Benchmark CPU lokal

| Backend | Mean wall latency | Median | P95 | FPS dari mean wall |
|---|---:|---:|---:|---:|
| PyTorch FP32 | 79,057 ms | 71,446 ms | 109,434 ms | 12,649 |
| ONNX Runtime FP32 | 69,123 ms | 69,224 ms | 83,913 ms | 14,467 |
| OpenVINO FP16 | 118,826 ms | 86,693 ms | 285,092 ms | 8,416 |

Timing mencakup satu pemanggilan model.predict per image, termasuk preprocess, inference, postprocess, dan wrapper setelah dua warm-up. Ini observasi CPU WSL lokal dengan satu timed repetition, bukan klaim real-time atau benchmark perangkat produksi.

## Riwayat recovery

- B01_20260807_001 menyelesaikan export, tetapi berhenti karena output OpenVINO tidak memiliki nama tensor. Bukti tercatat pada experiments/B01_20260807_001_failed_tensor_names/.
- B01_20260807_002 memakai fallback nama tensor dan memuat kedua format, tetapi agreement gagal karena rect=true menghasilkan preprocessing PyTorch berbeda dari input statis export. Bukti ada di experiments/B01_20260807_002/ dan results/day3/B01_20260807_002/.
- B01_20260809_003 memakai fallback nama tensor dan square padding identik tanpa mengubah ambang toleransi. Run ini lulus.
- B01_20260809_004 mengonfirmasi hasil yang sama, tetapi metadata dirty-worktree dari Git WSL salah mendeteksi file CRLF host sebagai perubahan. Runner kemudian diperbaiki untuk memakai Git host bila tersedia.
- B01_20260809_005 adalah rerun final: source revision ba6be91, tracked worktree bersih, dan semua agreement tetap lulus.

## Artefak dan batasan

- experiments/B01_20260809_005/config.yaml
- experiments/B01_20260809_005/environment.json
- experiments/B01_20260809_005/sample_manifest.json
- experiments/B01_20260809_005/summary.json
- results/day3/B01_20260809_005/agreement.csv
- results/day3/B01_20260809_005/benchmark.csv
- results/day3/B01_20260809_005/summary.json

Agreement diperiksa pada final detection di confidence 0,25, bukan setiap raw tensor atau seluruh validation split. Benchmark hanya 16 image dengan satu timed repetition. GPU, Jetson, TensorRT, dan perangkat produksi belum diuji.

Milestone berikutnya adalah Gate 6: menjalankan ByteTrack dan BoT-SORT pada video aerial yang sama, lalu menyimpan perbandingan latency/FPS dan contoh kegagalan kualitatif.
