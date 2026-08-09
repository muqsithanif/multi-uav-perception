# Laporan Tracking — ByteTrack vs BoT-SORT

Tanggal pembaruan: 9 Agustus 2026 (Asia/Jakarta)

## Objective dan status

Gate tracking dinyatakan lulus melalui comparison T01_20260809_002. ByteTrack dan BoT-SORT menjalankan checkpoint E01 yang sama pada seluruh frame dari video aerial yang sama. Kedua tracker menghasilkan trajectory CSV, video preview beranotasi, key frame deterministik, serta metrik timing machine-readable.

ByteTrack dipilih sebagai default tracker proyek. Pilihan ini berlaku untuk prototipe software/2D simulation ini dan dapat diubah melalui YAML; bukan klaim kualitas tracking umum atau jaminan produksi.

## Video sumber dan lisensi

- Provider: Pexels
- Asset: 3978617, drone footage of traffic on a road
- Halaman sumber: https://www.pexels.com/video/drone-footage-of-a-traffic-in-the-road-3978617/
- Lisensi: https://www.pexels.com/license/
- Video lokal: data/raw/tracking/pexels_3978617_traffic.mp4
- SHA-256: 5e257a6a2c2ebd1c9320e595847d4c6e652978e440117c3bb2eab453858be5d4
- Ukuran/durasi: 7.767.712 byte, 1.920x1.080, 24 FPS, 270 frame, 11,25 detik

Pexels menyatakan video dapat diunduh dan digunakan gratis; atribusi tidak wajib. File mentah dan video preview tidak dimasukkan ke Git. Sumber, hash, dan syarat lisensi dicatat agar input lokal dapat diverifikasi.

## Protokol yang dikunci

- Checkpoint: E01_20260807_001/best.pt, SHA-256 d5fcbeab43dc5706ea743d834094495be241836da2b25910c1cd1757f84faea5.
- Input: seluruh 270 frame dengan stride 1; tidak ada warm-up yang dikeluarkan dari pengukuran.
- Detector: CPU, image size 640, confidence 0,25, NMS IoU 0,7, maximum 300 detection, square preprocessing (rect=false).
- ByteTrack dan BoT-SORT memakai parameter YAML masing-masing. BoT-SORT memakai sparse optical-flow global motion compensation dan ReID dimatikan.
- Batas waktu: satu pemanggilan model.track per decoded frame, meliputi preprocess, detector, association tracker, postprocess, dan wrapper.
- Lingkungan: WSL2 Ubuntu 24.04, CPU Intel Core Ultra 7 155H, Python 3.12.3, PyTorch 2.13.0+cpu, Ultralytics 8.4.115, lap 0.5.13.
- Source revision: 9e01d3f dengan tracked worktree bersih.

Run T01_20260809_001 dieksekusi sebelumnya, tetapi tidak digunakan untuk perbandingan timing karena Ultralytics memasang lap pada pemanggilan ByteTrack pertama. Rekam eksekusi dan review kegagalannya tetap disimpan. T01_20260809_002 dijalankan setelah lap dipin dan tersedia sebelum frame pertama.

## Hasil aktual

| Tracker | Mean wall latency | Median | P95 | FPS | Track unik | Observasi track | Rata-rata observasi/track | Total gap frame |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ByteTrack | 77,208 ms | 67,205 ms | 94,388 ms | 12,952 | 95 | 2.108 | 22,189 | 663 |
| BoT-SORT | 111,093 ms | 89,044 ms | 218,774 ms | 9,001 | 88 | 2.208 | 25,091 | 839 |

BoT-SORT menghasilkan rata-rata observasi per track yang sedikit lebih panjang, tetapi ByteTrack memiliki mean latency sekitar 30,5% lebih rendah, p95 jauh lebih kecil, FPS lebih tinggi, dan total gap frame lebih sedikit. Karena keduanya memakai detector/input sama dan tidak tersedia ground truth identitas, default dipilih berdasarkan efisiensi serta continuity proxy tersebut, bukan klaim IDF1/MOTA.

## Kegagalan dan peninjauan kualitatif

Frame awal, tengah, dan akhir disimpan deterministik untuk masing-masing tracker. Pada frame tengah, objek kecil serta tumpang-tindih di sekitar bus menciptakan label yang rapat; preview menunjukkan kedua tracker tetap mengeluarkan ID, tetapi visual ini tidak dapat membuktikan identitas sebenarnya.

CSV juga menunjukkan fragmentasi yang dapat diaudit tanpa menganggapnya ID-switch ground truth:

- ByteTrack: track lokal 119 (truck) memiliki 63 gap frame pada span 107 frame; track 312 (bus) memiliki 49 gap frame.
- BoT-SORT: track lokal 336 (van) memiliki 69 gap frame pada span 110 frame; track 95 (car) memiliki 63 gap frame.
- Track dengan paling banyak dua observasi: 18 untuk ByteTrack dan 19 untuk BoT-SORT.

ID tersebut hanya lokal untuk masing-masing tracker. Tanpa anotasi identitas per frame, MOTA, IDF1, HOTA, dan jumlah ID switch ditandai tidak tersedia, bukan nol.

## Artefak

- Config aktif: configs/e01_tracking_comparison.yaml
- Config tracker: configs/tracker_bytetrack.yaml dan configs/tracker_botsort.yaml
- Summary: experiments/T01_20260809_002/summary.json
- Trajectory ByteTrack: results/day3/T01_20260809_002/bytetrack/tracks.csv
- Trajectory BoT-SORT: results/day3/T01_20260809_002/botsort/tracks.csv
- Per-frame timing: results/day3/T01_20260809_002/bytetrack/frames.csv dan results/day3/T01_20260809_002/botsort/frames.csv
- Preview lokal: results/day3/T01_20260809_002/<tracker>/annotated.mp4
- Key frame: results/day3/T01_20260809_002/<tracker>/key_frames/

## Batasan dan langkah berikutnya

Video sumber adalah stock footage tanpa ground-truth tracking. Hasil ini membuktikan jalur tracker dan perbandingan operasional pada satu clip; hasilnya tidak dapat digeneralisasi menjadi benchmark MOT atau real-time perangkat produksi.

Milestone berikutnya adalah priority, assignment, dan mission-state software yang menerima internal target schema dari trajectory tracker.
