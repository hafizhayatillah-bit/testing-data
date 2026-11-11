# Model Prediksi Estimasi Waktu Pengiriman (ETA) 2M Sembako

## Masalah yang Diselesaikan
Saat ini, perhitungan waktu pengiriman kurir 2M Sembako menggunakan asumsi statis (kecepatan konstan 20 km/jam). Hal ini menyebabkan janji SLA sering meleset saat jam sibuk atau ketika kurir membawa muatan berat (bulk). Model ini dibangun untuk memprediksi ETA secara dinamis berdasarkan jarak rute, beban keranjang, dan waktu pemesanan.

## Sumber Data
Dataset (`dataset_pengiriman_2m_clean.csv`) dihasilkan, disimulasikan, dan dibersihkan oleh tim Data Science (Ida & Dian) berdasarkan parameter logistik operasional 2M Sembako.

## Langkah Preprocessing (Telah dilakukan DS, siap masuk model)
1. Penghapusan *Missing Values* (Dropna).
2. Filter anomali: Jarak > 0 km, Waktu Tempuh antara 5 hingga 180 menit.
3. *Feature Engineering*: Ekstraksi status `is_rush_hour` (jam sibuk 16-19) dan `is_heavy` (beban > 15 kg).

## Target Model AI (Untuk Tim Gen AI)
* **Tipe Model:** Regresi (Supervised Learning).
* **Target Variabel:** `waktu_tempuh_menit`.
* **Fitur (Features):** `jarak_km`, `berat_kg`, `is_rush_hour`.
* **Algoritma yang Disarankan:** Random Forest Regressor atau Gradient Boosting.