# 05. Yang Dibutuhkan dari Tim untuk Menutup Celah
Urutan menurut dampak terhadap kesimpulan. Pipeline sudah siap: begitu data asli masuk, `python run_all.py` menghitung ulang semuanya.

## Prioritas 1 — mengubah kesimpulan utama
| # | Kebutuhan | Dari siapa | Mengapa |
|---|---|---|---|
| 1 | **3–4 simulasi order GoSend dan GrabExpress di aplikasi** dari lokasi cabang (Tambun) ke tujuan berjarak sekitar 1, 3, 5, dan 8 km. Catat tarif dan jarak yang ditampilkan. | PIC / siapa pun yang punya akses aplikasi | Menggantikan dua asumsi yang belum terverifikasi (tarif minimum mencakup 4 km; harga maks pada 10 km). Hasil Q1 bergeser antara 2,25 dan 5,75 km tergantung ini. |
| 2 | **Keputusan PM:** opsi mana yang dipilih untuk pilot (O1–O4, batching) dan **definisi target kurir** (100% UMK, atau target per jam setara pendapatan driver pembanding, atau paruh waktu). | PM | Dengan ongkir ≤ pembanding, target 100% UMK tidak tercapai di skenario mana pun; ini keputusan bisnis, bukan analisis. |
| 3 | **Izin data 2M dan ekspor dari IT Pusat:** master SKU, HPP, log pesanan/pengiriman (order_id, tanggal, cabang, jarak atau kode pos tujuan, berat, nilai belanja, ongkir). **Tanpa data pribadi pelanggan.** | Pimpinan 2M / IT Pusat | Contribution margin per order menentukan batas subsidi (O4); sebaran jarak asli menggantikan asumsi 40/40/20. |

## Prioritas 2 — melengkapi paket
| # | Kebutuhan | Dari siapa |
|---|---|---|
| 4 | **Sheet `T8_Data_dari_Ops`** yang dirujuk di Panduan tetapi tidak ada di file (temuan E1). Kirim atau konfirmasi belum dibuat. | Penyusun Draft_DS_Kurir_v2 |
| 5 | **Master cabang** (7 cabang: nama, kode pos, koordinat) dan **master armada kurir** (jenis motor aktual). Saat ini cabang hanya C01–C07 dummy. | IT Pusat / Ops |
| 6 | **Kesepakatan format & target model dengan tim Gen AI:** target apa yang dilatih (waktu antaran, order gagal, atau forecasting permintaan)? Apakah skema kolom di `kamus_data.csv` cocok? | Hafizh, Noval |
| 7 | **Data lapangan pilot:** timestamp PWA Kurir, struk bensin, nota servis, harga motor dari dealer, tingkat order gagal. | Ops / kurir pilot |

## Prioritas 3 — konfirmasi kecil
| # | Pertanyaan | Asumsi saya sekarang |
|---|---|---|
| 8 | Radius layanan maksimum? | 15 km dipakai hanya untuk mendeteksi salah ketik jarak (`MAX_RADIUS_KM` di `s02`) |
| 9 | Wilayah UMK default? | Kab. Bekasi (ikut Parameter). Mengubahnya di Parameter Excel dan menjalankan ulang `s01` cukup. |
| 10 | Format ekspor log asli dari PWA Kurir? | Sama dengan `kamus_data.csv`; bila beda, hanya `s02` yang disesuaikan. |

## Hal yang tidak bisa dilakukan dari sisi saya
- Mengecek tarif aplikasi (GoSend/GrabExpress) secara langsung.
- Menyatakan hasil analisis sebagai temuan nyata sebelum ada data transaksi.
- Menyelesaikan kartu Gen AI (model terlatih) secara bermakna sebelum target model dan data asli disepakati. Paket ini sudah menyiapkan masukannya.
