# 03. Panduan Dataset untuk Gen AI dan Full-Stack
*Main Quest DS poin 6 · Semua data buatan berlabel `sumber_data = SINTETIS_SIMULASI`*

## 1. Peringatan sebelum memakai
Produk belum launch, jadi **tidak ada data transaksi asli**. `order_log_bersih.csv` dibuat dari parameter model tim ditambah derau acak. Akibatnya:
- Cocok untuk: membangun dan menguji pipeline, kontrak format data, prototipe UI/API.
- **Tidak cocok** untuk: menyimpulkan perilaku nyata kurir/pelanggan. Model ML yang dilatih di sini pada dasarnya mempelajari ulang aturan pembuat data (jarak → waktu, dst.), jadi skornya tidak mencerminkan performa di dunia nyata. Wajib dilatih ulang pada log PWA Kurir asli.

## 2. Peta file
| File | Isi | Untuk siapa |
|---|---|---|
| `data/clean/order_log_bersih.csv` | 3.000 order bersih, 40 kolom (skema T1) + kolom turunan | Full-Stack (skema), Gen AI (eksplorasi) |
| `data/clean/dataset_fitur_target.csv` | 3.000 baris: fitur + target + kolom `split` (train 2.400 / test 600, menurut waktu) | Gen AI |
| `data/clean/kamus_data.csv` | Nama kolom, tipe, satuan, arti, asal | semua |
| `data/clean/grid_jarak_hasil.csv` | Hasil model per jarak 0,25–10 km, klaster A dan B (ongkir minimum/disarankan, kantong kurir & 2M, status) | Full-Stack (tabel ongkir), Gen AI (konteks) |
| `data/clean/parameter_model_bersih.csv` | 96 parameter model + tingkat keyakinan + sumber | semua |
| `data/clean/motor_klaster_bersih.csv` | 7 motor → klaster A/B, biaya per km | Gen AI, Full-Stack |
| `src/model_biaya.py` | Logika biaya & ongkir dalam Python (sudah cocok dengan Excel) | Full-Stack (pricing engine), Gen AI |
| `output/tabel/q*.csv` | Hasil analisis per pertanyaan bisnis | PM |

## 3. Cara memakai
```bash
pip install -r requirements.txt
python run_all.py            # membangun ulang seluruh data & hasil (±1 detik)
```
```python
import pandas as pd
df = pd.read_csv("data/clean/order_log_bersih.csv", parse_dates=["ditugaskan_at"])
X = pd.read_csv("data/clean/dataset_fitur_target.csv")
train, test = X[X.split == "train"], X[X.split == "test"]
```
Menghitung ongkir/upah satu order (Full-Stack, pricing engine):
```python
from src.model_biaya import load_params, load_motor, hitung
P, M = load_params(), load_motor()
r = hitung(3.2, "A", P, M)                       # jarak rute satu arah 3,2 km, klaster A
r["ongkir_disarankan"], r["upah_penuh"], r["kantong_2m"]
```
Catatan: `ongkir_disarankan` pada baris yang dibatasi pembanding tidak kelipatan Rp500 (temuan E2). Gunakan kolom `ongkir_disarankan_bayar` di `grid_jarak_hasil.csv`, yang dibulatkan **ke bawah** ke kelipatan Rp500 agar tidak melewati pembanding.

## 4. Kontrak format data (log asli dari PWA Kurir)
Gunakan skema sama dengan `kamus_data.csv`. Aturan penting:
- `jarak_rute_km`: jarak rute **satu arah** (desimal, titik), disimpan saat order dibuat.
- 5 timestamp (`ditugaskan_at`…`kembali_at`) berformat ISO `YYYY-MM-DD HH:MM:SS`, berzona waktu tetap (WIB).
- Uang: integer rupiah tanpa "Rp" dan pemisah ribuan. Snapshot upah & ongkir disimpan per order (jangan dihitung ulang).
- `status_order`: hanya `berhasil` atau `gagal_pelanggan_tidak_ada`.
- `kode_motor` M1–M7; `cabang_id` mengikuti master cabang IT Pusat; **tanpa data pribadi pelanggan**.
- Bila format asli berbeda, cukup ubah `src/s02_assessing_cleaning.py` (aturan tercatat di `log_pembersihan.csv`); tahap analisis tidak perlu diubah.

## 5. Untuk tim Gen AI: kandidat target model
Format fitur sudah siap di `dataset_fitur_target.csv`. Usulan target (diputuskan bersama, lihat `05_kebutuhan_dan_keputusan.md`):
| Target | Jenis | Fitur | Catatan |
|---|---|---|---|
| `waktu_per_antaran_menit` | regresi | jarak, macet, jam, hari, klaster, berat | berguna untuk estimasi waktu & kapasitas kurir; di data sintetis mudah ditebak |
| `gagal` | klasifikasi | jarak, jam, hari, cabang | kelas sangat tidak seimbang (±3,5% gagal); butuh data asli |
| permintaan per cabang per hari | forecasting | tanggal, cabang | **belum tersedia**; butuh riwayat pesanan asli |

Preprocessing yang **sudah** dilakukan DS: pembersihan, penyeragaman kategori, imputasi berat (ditandai), perbaikan jarak/waktu, pembagian train/test menurut waktu. Yang masih dilakukan di sisi model: encoding `klaster_motor` dan `cabang_id`, penskalaan bila perlu. Jangan memakai kolom turunan keuangan (`untung_*`, `kantong_*`) sebagai fitur, karena bocor dari target/upah.
