# 04. Pemeriksaan Akurasi Data dan Analisis
*Main Quest DS poin 7 · Diulang otomatis oleh `src/s05_cek_akurasi.py` → `output/tabel/cek_akurasi.csv`*

## Ringkasan
**33 pemeriksaan: 28 PASS, 2 INFO, 3 TEMUAN, 0 FAIL.** "TEMUAN" berarti masalah pada draf Excel/asumsi, bukan kegagalan pipeline.

## A. Rekonsiliasi model Python vs Excel (semua PASS)
| ID | Yang dicek | Hasil |
|---|---|---|
| A1 | T4 grid: 80 baris × 19 kolom numerik | selisih maks 1,8e-12 |
| A2 | T4: label status kurir / 2M / tarif lama | 100% sama |
| A3 | Output_Tidy T4: 400 nilai (5 metrik × 80 titik) | selisih maks 1,8e-12 |
| A4 | T6: 3 skenario × 2 klaster | selisih maks 2,3e-10 |
| A5 | T5: 16 baris (untung, kapasitas, antaran dibutuhkan, penghasilan) | selisih maks 1,2e-10 |
| A6 | Tornado T6: 6 variabel × 2 arah × 2 metrik | selisih maks 7,0e-10 |

Artinya rumus Excel dan reimplementasi Python identik. Ini menunjukkan **konsistensi logika**, bukan kebenaran asumsi.

## B. Invarian logika (semua PASS)
Identitas kantong 2M, ongkir ≤ batas pembanding, ongkir minimum naik monoton terhadap jarak, tanpa nilai kosong/tak hingga, tiga sebaran jarak berjumlah 100%, biaya motor klaster cocok acuan instruksi (A Rp518,75 vs 519; B Rp699,99 vs 700), 7 motor unik.

## C. Akurasi pembersihan (data sintetis punya "kunci jawaban")
Log bersih dibandingkan dengan nilai sebenarnya sebelum "dikotori".
| Kolom | Akurasi pemulihan |
|---|---|
| Jumlah baris unik | 3.000 = 3.000 |
| jarak_rute_km (hilang 110, salah ketik 23, tidak cocok 6) | 100% |
| status_order, kode_motor, klaster_motor, kurir_id | 100% |
| ongkir_rp, pembanding_rp (teks "Rp x.xxx") | 100% |
| ditugaskan_at (format campur), berangkat_at/tiba_at (tertukar 45) | 100% |
| berat_total_kg yang tidak diimputasi | tidak berubah |
| berat yang diimputasi (181 baris, ditandai) | galat rata-rata 4,9 kg (INFO) |

**Peringatan jujur:** 100% ini tercapai karena masalah yang disuntikkan memang bisa dipulihkan (jarak dari snapshot upah, dsb.). Pada data asli, tingkat pemulihan akan lebih rendah dan masalah yang tak terduga akan muncul. Aturan cleaning dan `log_pembersihan.csv` dibuat agar kasus baru terlihat (aturan "harus 0").

## D. Verifikasi data publik (pencarian 9 Nov 2026)
| Data | Nilai | Status |
|---|---|---|
| Harga Pertalite | Rp10.000/liter | **Terverifikasi** (harga Nov 2026 tidak berubah) |
| UMK Kab. Bekasi 2026 | Rp5.938.885 | **Terverifikasi** (banyak sumber, Kepgub Jabar 561.7/Kep.862-Kesra/2025) |
| UMK Kota Bekasi 2026 | Rp5.999.443 | Terverifikasi; Rp5.992.931 adalah angka rekomendasi Des 2025 yang masih muncul di sebagian media; tidak berdampak pada hasil |
| UMK Kota & Kab. Bogor | Rp5.437.203 / Rp5.161.769 | Terverifikasi |
| Tarif GoSend/GrabExpress | Rp7.500–15.500 / 9.000–20.000 | **Belum terverifikasi** (data PIC dari aplikasi; jarak per harga tidak diketahui) |
| Potongan aplikasi 20% | KP 667/2022 | Tidak diverifikasi ulang (berlaku ojol penumpang) |
| Konsumsi BBM, harga motor, perawatan, kecepatan, waktu tetap, gagal 3%, throughput 15, sebaran jarak | lihat Parameter | **Asumsi tim (tingkat D)** |

Rincian dan sumber: `output/tabel/cek_akurasi_data_publik.csv`. **5 dari 10 butir data eksternal terverifikasi**; sisanya asumsi atau dari PIC.

## E. Temuan audit workbook `Draft_DS_Kurir_v2.xlsx`
| ID | Temuan | Dampak | Usulan |
|---|---|---|---|
| E1 | **Sheet `T8_Data_dari_Ops` tidak ada di file** (12 sheet), padahal dirujuk di Panduan dan Catatan_Perubahan no. 4, 29, 31, 34 | Daftar 11 butir data yang diminta ke Ops tidak bisa diperiksa; angka "Rp83,3/Rp95,7" yang disebut sudah diganti rumus tidak ditemukan | Kirim sheet T8, atau pastikan memang belum dibuat |
| E2 | `ongkir_disarankan` **tidak kelipatan Rp500** pada 32 dari 80 baris (mis. Rp7.833,33; Rp8.833,33), semuanya baris yang dibatasi pembanding, padahal parameter pembulatan = Rp500 | Harga yang tampil tidak bisa ditagihkan; ongkir minimum sudah dibulatkan tetapi batas pembanding tidak | Bulatkan batas ke bawah ke Rp500 (sudah dilakukan di `grid_jarak_hasil.csv`, kolom `ongkir_disarankan_bayar`) |
| E3 | Parameter `jarak_tarif_maks_km` (10 km) masih bertanda KONFIRMASI; hasil Q1 bergeser 2,25–5,75 km menurut asumsi | Kesimpulan utama bergantung pada asumsi ini | Konfirmasi lewat simulasi order di aplikasi |

Pemeriksaan tambahan: angka kunci pada sheet Ringkasan (30,4% UMK; 50 antaran/hari; kapasitas 15; rugi mulai 2,25 km; dead zone tarif lama 2,50–2,75 km) sama dengan hitungan ulang.

## F. Yang belum bisa diperiksa
- Kebenaran asumsi tingkat D (butuh data lapangan).
- Kewajaran sebaran jarak dan tingkat order gagal (butuh log asli).
- Keakuratan tarif pembanding terhadap harga aplikasi aktual.
