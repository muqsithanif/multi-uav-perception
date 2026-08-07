# Menjalankan smoke training Day 2 di Google Colab

Status pembaruan 7 Agustus 2026: **Gate 2A sudah lulus** melalui run Colab
`E01S_20260807_001` dan bukti resume terpisah `E01R_20260807_001`. Run yang
diterima memakai dataset penuh, bukan subset runner historis yang dijelaskan di
bawah. Bukti aktual berada di `experiments/E01_20260807_001/smoke_summary.json`,
`resume_summary.json`, dan `handoff_receipt.json`; dokumen ini sendiri tetap
bukan bukti training.

## Workflow subset yang disiapkan di repository

## Prasyarat

1. Simpan dua ZIP resmi yang sudah diverifikasi ke Google Drive:

   ```text
   MyDrive/multi-uav-perception/data/raw/visdrone2019_det/VisDrone2019-DET-train.zip
   MyDrive/multi-uav-perception/data/raw/visdrone2019_det/VisDrone2019-DET-val.zip
   ```

2. Di Colab, buka **Secrets** dan tambahkan `GITHUB_TOKEN` dengan akses read/write
   ke repository private. Aktifkan akses secret untuk notebook. Jangan tempel
   token ke cell atau output.
3. Buka [notebook smoke training Day 2](https://colab.research.google.com/github/muqsithanif/multi-uav-perception/blob/main/notebooks/day2_visdrone_smoke_colab.ipynb).
4. Pilih runtime GPU, lalu jalankan **Run all**. Google tetap meminta otorisasi
   mount Drive; langkah keamanan akun ini harus disetujui pemilik akun.

## Pemeriksaan yang dilakukan notebook

- menolak runtime tanpa CUDA;
- mengkloning repository private tanpa mencetak token;
- memeriksa SHA-256 ZIP train dan val;
- mengekstrak dan memvalidasi pasangan image/anotasi;
- menjalankan suite Day 2;
- membuat subset deterministik 256 train dan 64 val;
- menjalankan epoch 1-2, menyalin checkpoint mentah sebelum optimizer dihapus;
- memeriksa epoch, optimizer, dan target epoch di checkpoint;
- memuat checkpoint tersebut dengan `resume=True` dan mengamati epoch mulai;
- menyelesaikan epoch 3 dan mensyaratkan tiga baris `results.csv`;
- menyimpan checkpoint/log ke Google Drive;
- menyimpan artefak ringkas ke `experiments/` dan `results/`;
- mendorong artefak ke branch `colab/day2-S01_20260807_colab_smoke`.

Runner menolak full fine-tuning. Metrik tiga epoch diberi scope
`subset_smoke_only` dan tidak boleh dibandingkan langsung dengan E00 karena
validation subset-nya berbeda.

## Kondisi lulus

Gate 2A hanya dapat dinyatakan lulus setelah artefak aktual menunjukkan:

- `status: passed`;
- `resume_proof.status: passed`;
- checkpoint epoch 2 memiliki optimizer dan benar-benar dipakai untuk memulai
  epoch 3;
- `results.csv` memiliki tiga epoch;
- `last.pt`, `best.pt`, dan checkpoint resume tersimpan di Google Drive dengan
  ukuran serta SHA-256 aktual.
