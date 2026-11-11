# 01. Masalah UMKM, Peran Data, dan Pertanyaan Bisnis
*Main Quest DS poin 1 dan 2 · Owner: Data Science · Status data: lihat bagian 4*

## 1. Masalah yang diselesaikan
2M Sembako melayani UMKM sembako dengan pengiriman oleh kurir eksternal bermotor sendiri. Ada tiga tekanan yang berjalan bersamaan:

1. **Pelanggan membandingkan ongkir dengan GoSend/GrabExpress.** Ongkir 2M tidak boleh lebih mahal dari pembanding, kalau tidak pelanggan pindah.
2. **Kurir harus mendapat penghasilan yang layak.** Target tim: penghasilan bersih setara UMK (Kab. Bekasi 2026: Rp5.938.885/bulan) setelah biaya motor.
3. **2M tidak boleh menalangi kerugian tanpa batas.** Kantong 2M per antaran = ongkir yang diterima − upah kurir − biaya cabang.

Belum diketahui apakah ketiganya bisa terpenuhi sekaligus, pada jarak berapa, dan tuas apa yang paling efektif bila tidak. Draf Excel yang ada sudah memodelkan hal ini, tetapi belum ada dataset terstruktur, tahapan wrangling, verifikasi akurasi, dan paket data yang bisa dipakai anggota tim lain.

## 2. Peran data
| Keputusan yang harus diambil | Data yang dibutuhkan | Ada sekarang? |
|---|---|---|
| Tarif ongkir per jarak | tarif pembanding per jarak, biaya kurir, biaya cabang | sebagian (rentang harga dari PIC; jarak per harga belum diketahui) |
| Skema upah kurir | biaya motor per km, waktu per antaran, tingkat order gagal | asumsi tim (tingkat D); menunggu log PWA Kurir |
| Radius layanan / batching | sebaran jarak order, kepadatan order per cabang | asumsi 3 skenario; menunggu riwayat pesanan |
| Batas subsidi 2M | contribution margin per order (HPP, harga jual) | belum ada (butuh izin data 2M / IT Pusat) |
| Target penghasilan kurir | UMK, hari dan jam kerja | UMK terverifikasi publik; jam kerja asumsi |

## 3. Pertanyaan bisnis (dapat dijawab dengan data)
| No | Pertanyaan | Metrik | Dijawab di |
|---|---|---|---|
| **Q1** | Pada jarak berapa 2M mulai rugi bila ongkir dibatasi tarif pembanding dan upah memakai skema sekarang? Berapa besarnya? | kantong 2M per antaran (Rp) per jarak 0,25–10 km | Laporan bagian Q1 |
| **Q2** | Apakah skema upah sekarang membuat kurir mencapai penghasilan setara UMK? Jika tidak, berapa kesenjangannya dan berapa ongkir yang dibutuhkan? | penghasilan bersih/bulan, % UMK, untung/jam | Laporan bagian Q2 |
| **Q3** | Variabel apa yang paling menggeser ongkir minimum dan penghasilan kurir? | tornado ±20% | Laporan bagian Q3 |
| **Q4** | Seberapa kokoh kesimpulan Q1 terhadap dua asumsi tarif pembanding yang belum terverifikasi (jarak tercakup tarif minimum, jarak pada harga maksimum)? | jarak mulai rugi pada 25 kombinasi asumsi | Laporan bagian Q4 |
| **Q5** | Opsi kebijakan mana (upah dibatasi amplop, radius layanan, ongkir fleksibel, subsidi, batching) yang menutup kesenjangan, dan apa konsekuensinya? | kantong 2M, % UMK, porsi order terlayani | Laporan bagian Q5 |

## 4. Rencana dan status data
| Prioritas rencana (dari kartu) | Status |
|---|---|
| Data UMKM asli (master SKU, HPP, log pesanan/pengiriman, tanpa data pribadi pelanggan) | **Belum ada.** Produk belum launch; izin data 2M menunggu. |
| Data dummy buatan tim | **Dibuat:** `order_log_sintetis_raw.csv` (3.060 baris mentah, 3.000 order unik). Semua baris berlabel `SINTETIS_SIMULASI`. |
| Data publik | **Dipakai & diverifikasi:** harga Pertalite, UMK 2026 (lihat `04_pemeriksaan_akurasi.md`). |
| Hasil model biaya tim (Excel) | **Dipakai sebagai sumber utama analisis**, dihitung ulang di Python dan cocok. |

> **Batasan penting.** Jawaban Q1–Q5 adalah analisis *skenario* berbasis parameter tim (banyak berstatus "asumsi/tingkat D"), bukan temuan dari transaksi nyata. Log order sintetis dipakai untuk menguji pipeline dan kontrak format data, **bukan** untuk menarik kesimpulan bisnis.
