# Data Science Ongkir, Upah Kurir, dan Jarak Berisiko (2M Sembako)

## Status terhadap acceptance criteria

| Kriteria | Status | Bukti |
| :---- | :---- | :---- |
| Dokumen masalah \+ 3–5 pertanyaan bisnis | ✅ Selesai (5 pertanyaan) | `docs/01_masalah_dan_pertanyaan_bisnis.md` |
| Notebook/skrip wrangling yang bisa dijalankan ulang | ✅ Selesai (diuji: dua kali jalan dari nol, hasil identik) | `run_all.py`, `src/` |
| Hasil analisis \+ rekomendasi ringkas (laporan/visual) | ✅ Selesai | `docs/02_laporan_analisis_dan_rekomendasi.md`, `output/grafik/` |
| Dataset bersih \+ cara pakai untuk Gen AI dan Full-Stack | ✅ Selesai, **dengan data dummy berlabel** | `data/clean/`, `docs/03_panduan_dataset_GenAI_dan_FullStack.md` |
| Hasil pengecekan akurasi tercatat | ✅ Selesai (28 PASS, 2 INFO, 3 TEMUAN) | `docs/04_pemeriksaan_akurasi.md`, `output/tabel/cek_akurasi.csv` |

**Syarat status "selesai":** dataset order berisi data **sintetis** (produk belum launch), dan analisis bisnis berbasis asumsi tim. Validasi pada data asli menunggu hal-hal di `docs/05_kebutuhan_dan_keputusan.md`.

## Masalah yang diselesaikan

Menentukan ongkir dan upah kurir sehingga (1) ongkir tidak melebihi GoSend/GrabExpress, (2) kurir bermotor sendiri mendapat penghasilan layak (target UMK), dan (3) 2M tidak menalangi kerugian. Temuan utama: dengan skema upah sekarang, 2M mulai rugi pada jarak 2,25 km dan kurir hanya mencapai ±30% target UMK.

## Cara menjalankan

```sh
pip install -r requirements.txt
python run_all.py
```

Tahapan: `1 gathering` (Excel → CSV mentah) → `2 data sintetis` → `3 assessing + cleaning` → `4 analisis` → `5 cek akurasi`. Setiap tahap bisa dijalankan sendiri, mis. `python -m src.s02_assessing_cleaning`.

## Struktur

```
data/raw/     Excel asli, CSV hasil gathering, log sintetis mentah (+ kunci jawaban uji)
data/clean/   log bersih, dataset fitur-target, kamus data, grid hasil, parameter, motor
src/          s01_gathering, synth_orders, s02_assessing_cleaning, model_biaya, s04_analisis, s05_cek_akurasi
output/       tabel (q1–q6, cek akurasi, log pembersihan), grafik (g1, g3–g7)
docs/         01 masalah · 02 laporan · 03 panduan dataset · 04 akurasi · 05 kebutuhan
```

## Sumber data dan library

| Data | Sumber | Status |
| :---- | :---- | :---- |
| Model biaya, parameter, motor, sebaran jarak | `Draft_DS_Kurir_v2.xlsx` (tim) | Asumsi tim; direkonsiliasi dengan Python |
| Tarif GoSend motor Rp7.500–15.500, GrabExpress Rp9.000–20.000 | Aplikasi, dicatat PIC, Okt 2026 | Belum terverifikasi independen |
| Harga Pertalite Rp10.000 | Pertamina; diberitakan Bisnis.com, detikOto, Fortune Indonesia, Okezone (1–2 Nov 2026\) | Terverifikasi 9 Nov 2026 |
| UMK 2026 (Kab. Bekasi Rp5.938.885, dll.) | Kepgub Jabar 561.7/Kep.862-Kesra/2025; Bisnis.com, Katadata, MetroTV, Dealls, detik | Terverifikasi |
| Tarif ojol Zona II, potongan aplikasi | KP 667/2022 jo. KP 1001/2022 (dari workbook) | Referensi saja |
| Konsumsi BBM motor | Brosur Honda dan uji media (detikOto, Gridoto, Bisnis.com), dari workbook | Klaim pabrikan, faktor koreksi 0,90 |
| **Log order** | **Dibuat oleh `src/synth_orders.py` (seed tetap)** | **SINTETIS\_SIMULASI, bukan data asli** |

Library: pandas, numpy, openpyxl, matplotlib (Python 3.12).

## Aturan label data

Semua baris data buatan memuat kolom `sumber_data = SINTETIS_SIMULASI`, dan file buatan bernama mengandung `sintetis`. Jangan mengutip angka dari log sintetis sebagai fakta bisnis.