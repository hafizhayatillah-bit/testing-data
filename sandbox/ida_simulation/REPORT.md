# REPORT: Audit & simulasi pipeline DS Ida (v2)

> **DATA SINTETIS / ASUMSI, bukan data lapangan.** Semua angka di bawah berasal dari model skenario dan log order buatan generator. Tidak satu pun boleh dikutip sebagai fakta bisnis.

Tanggal: 11 Nov 2026 · Sumber: Google Drive `DataStash/` (Data_Wrangling_V2, Data_Wrangling_V1, Draft_DS_Kurir_v2.2.xlsx), arsip + SHA-256 di `../_download/` · Python 3.12.6, versi terkunci di `requirements.lock`.

## Ringkasan

- **Pipeline jalan dan deterministik.** `run_all.py` sukses 2/2 dari kondisi bersih (±8 dtk), 39/39 file byte-identik antar-run, `angka_kunci.json` identik dengan kiriman Ida.
- **Aritmetika model biaya benar.** Model yang saya tulis ulang independen cocok dengan `model_biaya.py` Ida (selisih ≤ 6e-10 rupiah) dan dengan semua tabel Q1–Q6. Semua 14 klaim cost model (A01–A14) PASS.
- **Yang lemah adalah fondasi, bukan hitungan:** titik rugi 2,25 km bergantung pada 3 asumsi yang belum diverifikasi; dataset untuk model ETA tidak bisa direproduksi dan bersifat sirkular; metrik klasifikasi `gagal` tidak stabil. 11 dari 17 cek kualitas data/model (B) FAIL.

---

## Fase 1: Reproduksi

| Butir | Run 1 | Run 2 | Catatan |
|---|---|---|---|
| Exit code | 0 | 0 | tanpa error |
| Waktu jalan | 7,85 dtk | 7,67 dtk | README/docs menyebut "±1 detik" |
| File dihasilkan | 39 | 39 | dari input tunggal `Draft_DS_Kurir_v2.xlsx` |
| Deterministik (run1 vs run2, SHA-256) | 39/39 identik | | seed 20261109 dipakai (`config.py:12`) |
| Warning | 4 | 4 | 2× `Pandas4Warning` (`dayofweek` deprecated, `synth_orders.py:37`, `s02:118`); 1× `ResourceWarning` file `angka_kunci.json` tidak ditutup dan ditulis dengan encoding sistem `cp1252` (`s04_analisis.py:245`) |

**Run 1 vs kiriman Ida (46 file):**

| Hasil | Jumlah | Detail |
|---|---|---|
| Identik (setelah CRLF→LF) | 28 | termasuk `angka_kunci.json`, semua `q*.csv`, `order_log_bersih.csv`, `dataset_fitur_target.csv`, `grid_jarak_hasil.csv` |
| Beda isi, hanya derau float | 4 | `motor_klaster_bersih`, `parameter_model_bersih` (≤ 6e-14), `q3_tornado` (≤ 1,5e-11), `cek_akurasi.csv` (teks "selisih maks 1.2e-10" vs "0.0e+00") |
| Biner (PNG, xlsx) | 7 | PNG beda byte (wajar, versi matplotlib); xlsx sama |
| **Tidak dihasilkan oleh kode apa pun** | **7** | seluruh `data/model/*` (lihat Temuan 2) |

**Selisih vs `angka_kunci.json` kiriman:** 0 (identik).

**Portabilitas:**
- Tidak ada path absolut di `src/` atau `run_all.py`, dan pipeline tetap jalan bila dipanggil dari direktori lain.
- `requirements.txt` tidak di-pin (`pandas>=2.0`). Hari ini ter-resolve ke pandas 3.1.1 / numpy 2.5.4, dan hasilnya tetap sama, tapi ini rawan di masa depan: deprecation pandas 4 sudah muncul.
- Notebook kiriman tersimpan dalam keadaan **gagal**: sel pertama `ModuleNotFoundError: No module named 'src'` (Colab), 26 dari 29 sel "aborted".
- Tidak ada file wajib yang hilang untuk `run_all.py`.

---

## Fase 2: Audit klaim (`tests/test_audit.py`)

Hasil: **20 PASS · 11 FAIL · 0 SKIPPED** (rincian: `datasets/phase2/audit_results.json`). "Expected" = hipotesis dari teks Ida.

### A. Cost model (diuji dengan `costmodel.py` independen)

| ID | Klaim | Expected | Aktual | Status | Catatan |
|---|---|---|---|---|---|
| A01 | upah = 3.500 + 1.500 × km | selisih 0 | Rp0,0000 | PASS | |
| A02 | biaya motor ditanggung kurir; kantong 2M = ongkir diterima − bayar kurir − overhead/throughput | identitas berlaku | selisih ≤ Rp0,013; bensin +50% tidak mengubah kantong | PASS | memakai ongkir ×0,97 (gagal tak ditagih), upah ×0,985 |
| A03 | Q1 titik rugi klaster A | 2,25 km | 2,25 km | PASS | 32/40 titik grid rugi |
| A04 | Q1 rugi sampai 10 km | rugi terus | rugi terus 2,25–10 | PASS | |
| A05 | tarif lama rugi hanya 2,50–2,75 km | [2,5, 2,75] | [2,5, 2,75] | PASS | |
| A06 | Q2 penghasilan tertinggi ≈34% UMK | 34% ±1 | 33,45% (Optimis A); Dasar A 30,44% | PASS | laporan Ida menulis "18 antaran/hari" untuk Optimis, padahal kapasitas waktu 17 |
| A07 | kapasitas ≈15 vs ≈50 dibutuhkan | 15 vs 50 | 15 vs 50 | PASS | ongkir agar kurir capai UMK di 2,7 km = Rp19.274 vs pembanding Rp7.500 |
| A08 | Q4: tarif min mencakup ≥3 km → tetap 2,25 | 15/15 sel | 15/15 | PASS | 25 kombinasi |
| A09 | Q4: mencakup 1–2 km → bergeser s.d. 5,75 | maks 5,75 | 2,25–5,75 | PASS | |
| A10 | Q4: 2 kombinasi tidak rugi s.d. 10 km | 2 | 2: (1;6), (2;6) | PASS | **hanya karena tarif diekstrapolasi di atas "maks" Rp15.500**; bila dibatasi Rp15.500 → 0 kombinasi |
| A11 | Q5: O0 rugi untuk ±60% order | 60% | 60,0% (jarak wakil); **57,2%** bila jarak merata di bucket | PASS | 60% lahir dari penyederhanaan 1 jarak/bucket |
| A12 | Q5: O2 melayani ±40% order | 40% | 40% | PASS | |
| A13 | parameter = brief (20/12 km/jam, 15 mnt, 50%, 15/hari, 3.000/8.000, UMK) | sama | sama | PASS | |
| A14 | (tambahan) Q1 tetap 2,25 bila ongkir dibulatkan ke Rp500 yang bisa ditagih | 2,25 | 2,25 | PASS | Q4 versi bisa-ditagih: 2,25–5,25 km |

### B. Kualitas data & model

| ID | Klaim / hipotesis | Expected | Aktual | Status | Catatan |
|---|---|---|---|---|---|
| B01 | generator V2 tanpa efek berat | \|t\| < 2 | koef +0,007 mnt/kg (SE 0,018, t=0,40), n=2.819 | PASS | `synth_orders.py:51` membuat `berat` tapi tidak dipakai di rumus waktu (48–59) |
| B02 | V1 punya efek berat? | koef > 0 | **+0,33 mnt/kg (t=30,6)**, n=1.480 | PASS | mekanisme V1 ≠ V2 |
| B03 | ML > baseline rumus (2d/v·60+15) | ΔR² ≥ 0,02 | GBR R² 0,907 / MAE 3,58 vs 0,877 / 4,43 | PASS | split waktu 80/20 milik Ida |
| B04 | ML > baseline jarak/v **terkalibrasi** | ΔR² ≥ 0,02 | GBR 0,907 vs baseline 1 fitur **0,907**; LinReg semua fitur 0,846 | **FAIL** | keunggulan ML = kalibrasi konstanta saja |
| B05 | skor ETA bukan sirkular | jauh dari plafon | GBR 0,9069 vs plafon generator 0,9074 | **FAIL** | R² ~0,91 = batas derau U(2,8)+U(3,10)+lognormal; Ida mengakui di docs/03 |
| B06 | ETA `data/model` (tiba, split 70/30): ML > baseline | ΔR² ≥ 0,02 | GBR 0,891 vs baseline 0,895 vs plafon 0,895 | **FAIL** | 181 berat NaN (diisi median preprocessor) |
| B07 | Cek C (akurasi cleaning 100%) bukti independen | kunci independen | kunci = `truth` dari generator yang sama; kerusakan disuntik `inject_mess()` di file yang sama; jarak dipulihkan dari upah yang dihitung dari jarak asli | **FAIL** | `s05:103-104`, `synth_orders:86,131`, `s02:88`; Ida mengakui ("Peringatan jujur") |
| B08 | positif `gagal` di test ≥ 30 | ≥ 30 | fitur_target: train 91 / **test 15**; data/model: train 78 / **test 28** | **FAIL** | **TIDAK STABIL** |
| B09 | tidak ada kolom finansial di file fitur | 0 | 0 | PASS | `gagal` ada sebagai target (sesuai docs/03), tapi file tidak memisahkan fitur/target |
| B10 | buang `flag_waktu_aneh` sebelum split tidak mengubah test | 0 terbuang | 0 baris; split benar berbasis waktu (2.400/600) | PASS | filter tetap di depan kuantil (`s02:146-149`): akan menggeser split pada log asli |
| B11 | kolom sesuai WP-45 | 13/13 | 2 persis, 8 beda nama, **hilang: item_count, prep_minutes, travel_minutes** | **FAIL** | tabel di bawah |
| B12 | V1 berlabel sintetis | ada | tidak ada (`order_id, jam_order, jarak_km, berat_kg, waktu_tempuh_menit, is_rush_hour, is_heavy`) | **FAIL** | |
| B13 | pipeline memakai workbook terbaru | v2.2 | membaca v2 (`config.py:10`) | **FAIL** | v2.2: +10 parameter, +T9/T10; parameter bersama identik → Q1–Q6 tidak berubah |
| B14 | semua data kiriman bisa dibangun ulang | 0 file yatim | **7 file `data/model/*` tanpa kode** | **FAIL** | |
| B15 | log sintetis memakai `waktu_tetap`=15 mnt | 15 | variabel `fixed` dibuat tapi tak dipakai; non-perjalanan = 11,5 mnt (gagal 16,5) | **FAIL** | `synth_orders.py:50` |
| B16 | README: 2x run identik | identik | 39/39; angka_kunci identik | PASS | |
| B17 | notebook kiriman sukses dijalankan | 0 error | 3 error tersimpan, 26 sel aborted | **FAIL** | |

**WP-45 vs file Ida** (`datasets/phase2/wp45_kolom.csv`):

| spec | `dataset_fitur_target.csv` | `data/model/dataset_model_order.csv` |
|---|---|---|
| order_id | ADA | ADA |
| split | ADA | ADA |
| branch_id | beda nama: `cabang_id` | beda nama: `cabang_id` |
| distance_km | beda nama: `jarak_rute_km` | beda nama: `jarak_rute_km` |
| weight_kg | beda nama: `berat_total_kg` | beda nama: `berat_total_kg` |
| hour | beda nama: `jam` | beda nama: `jam` |
| dow | beda nama: `hari_minggu` | beda nama: `hari_minggu` |
| motor_cluster | beda nama: `klaster_motor` | beda nama: `klaster_motor` |
| total_minutes | beda nama: `waktu_per_antaran_menit` | **HILANG** |
| source | beda nama: `sumber_data` | beda nama: `sumber_data` |
| item_count | **HILANG** | beda nama: `jumlah_item` (tidak dibuat generator mana pun) |
| travel_minutes | **HILANG** | beda nama: `target_eta_menit` (= tiba − ditugaskan, bukan murni perjalanan) |
| prep_minutes | **HILANG** | **HILANG** |

**Workbook v2 vs v2.2:** tidak ada parameter yang berubah nilainya. v2.2 menambah `basket_referensi` 150.000, `margin_barang_referensi` 0,1, `fee_payment_persen` 0,015, `expected_refund_persen` 0,01, `jarak_antar_drop_batch_km` 1, dan 5 parameter bernilai 0 (`fee_service`, `voucher`, `kemasan`, `target_contribution`, `biaya_tetap_cabang_lain`), plus sheet `T9_Opsi_Keputusan` dan `T10_BEP_Basket`. Rincian: `datasets/phase2/workbook_v2_vs_v22.json`.

---

## Fase 3: Paritas (`tests/test_parity.py`): 8/8 PASS

| Uji | Selisih maks | Status |
|---|---|---|
| costmodel vs `grid_jarak_hasil.csv` klaster A / B (39 titik × 18 kolom, termasuk kolom "bisa ditagih") | Rp0,005 (pembulatan 2 desimal CSV) | PASS |
| costmodel vs `model_biaya.hitung()` klaster A / B | 1,8e-12 / 5,8e-10 | PASS |
| Q3 tornado 6 variabel × 2 arah × 2 metrik | ≤ Rp1 | PASS |
| Q4 heatmap 25 sel | 25/25 sama | PASS |
| Q5 O0–O4 (kantong, subsidi, penghasilan, porsi rugi) | ≤ 3,4e-13 | PASS |
| Q6 batching (Ida membulatkan ke rupiah) | Rp0,49 | PASS |

Kantong 2M per antaran, klaster A (lengkap 39 titik: `datasets/phase3/parity_table.csv`):

| Jarak (km) | Model Ida | Model independen | Selisih |
|---|---|---|---|
| 0,5 | 482,08 | 482,08 | 0,00 |
| 1,0 | 228,33 | 228,33 | 0,00 |
| 1,5 | 459,58 | 459,58 | 0,00 |
| 2,0 | 205,83 | 205,83 | 0,00 |
| **2,25** | **−163,54** | **−163,54** | 0,00 |
| 2,5 | −532,92 | −532,92 | 0,00 |
| 3,0 | −1.271,67 | −1.271,67 | 0,00 |
| 4,0 | −2.749,17 | −2.749,17 | 0,00 |
| 5,0 | −2.933,33 | −2.933,33 | 0,00 |
| 6,0 | −3.117,50 | −3.117,50 | 0,00 |
| 8,0 | −3.485,83 | −3.485,83 | 0,00 |
| 10,0 | −3.854,17 | −3.854,17 | 0,00 |

---

## 5 temuan teratas (urut dampak ke project)

**1. Titik rugi "2,25 km" benar secara hitungan, tapi bertumpu pada 3 asumsi yang belum diverifikasi. Tornado Ida tidak memuat dua di antaranya.** Keyakinan: **tinggi**
- Bukti (titik rugi, dari `costmodel.py`, paritas ≤ 1e-9 dengan Ida):

  | Perubahan parameter | Titik rugi |
  |---|---|
  | `overhead_harian_cabang` 0 / 10.000 / 20.000 (status "Perlu diuji") | 2,75 / 2,25 / 1,75 km |
  | `ongkir_ditagih_saat_gagal` 0 → 1 ("Belum diputuskan") | 2,25 → 2,5 km |
  | tarif min GoSend 7.000 / 8.000 | 2,0 / 2,5 km |
  | tarif min GoSend ±20% (6.000 / 9.000) | 1,25 / 3,25 km, variabel paling berpengaruh ke titik rugi tapi tidak ada di tornado Q3 Ida karena tidak mengubah ongkir minimum |
  | asumsi cakupan tarif min (Q4) | 2,25–5,75 km |

- Klaim Q4 "2 kombinasi tidak rugi s.d. 10 km" hanya muncul karena tarif pembanding diekstrapolasi **di atas** maksimum Rp15.500 (mis. Rp21.900 di 10 km, `model_biaya.py:49-50`). Dengan batas Rp15.500, semua 25 kombinasi rugi.
- Dampak: keputusan ongkir/upah. 3–4 simulasi order di aplikasi GoSend (rekomendasi Ida sendiri) + angka overhead nyata menyelesaikan sebagian besar ketidakpastian.

**2. Dataset model (`data/model/*`, 7 file) tidak bisa direproduksi dan bertentangan dengan dataset fitur resmi.** Keyakinan: **tinggi**
- Bukti: tidak ada skrip di `src/`, `run_all.py`, atau notebook yang menulis file ini (B14; grep `dataset_model_order|manifest|jumlah_item` = 0).
- Split-nya 70/30 (`manifest_split.json`) vs 80/20 di `dataset_fitur_target.csv` (`s02:149`).
- Kolom `jumlah_item` tidak dibuat generator mana pun (korelasi 0,91 dengan berat).
- 181 berat dibiarkan NaN.
- File ini yang paling mungkin dipakai tim Gen AI, padahal provenansinya tidak bisa diaudit.

**3. ETA pada data sintetis V2 tidak bisa mengukur apa-apa: target sirkular, berat tanpa efek.** Keyakinan: **tinggi**
- Bukti: GBR R² 0,907 = baseline jarak/kecepatan 1 fitur terkalibrasi 0,907 = plafon derau generator 0,907 (B04–B06).
- Koefisien berat di V2 = +0,007 mnt/kg (t=0,4), sementara V1 = +0,33 mnt/kg (t=30,6) (B01–B02).
- Alasan proyek ETA di README V1 ("muatan berat/bulk") tidak bisa dipelajari dari V2.
- Angka akurasi ETA apa pun dari data ini tidak boleh masuk laporan/demo sebagai performa model. Ida sudah memperingatkan ini di docs/03, tetapi `data/model` tetap disiapkan seolah siap latih.

**4. Klasifikasi `gagal` tidak punya cukup kasus positif untuk dievaluasi.** Keyakinan: **tinggi**
- Bukti: positif di test = 15 (`dataset_fitur_target`) dan 28 (`data/model`), keduanya < 30 (B08).
- Dengan 15 positif, satu order salah tebak menggeser recall ±7 poin. Metrik klasifikasi = **TIDAK STABIL**.

**5. Bukti validasi lebih lemah daripada yang tertulis di README ("28 PASS").** Keyakinan: **sedang** (tiap butir terbukti; dampaknya ke keputusan kecil)
- Cek C "akurasi 100%" bersifat tautologis (B07).
- Cek E4 ditulis hardcoded `True, status="PASS"` (`s05_cek_akurasi.py:144`), tidak menghitung apa pun. Isinya kebetulan benar (saya cocokkan ke sheet Ringkasan), tapi tidak akan menangkap regresi.
- Notebook tersimpan dalam keadaan error (B17).
- Pipeline membaca workbook v2, bukan v2.2 (B13).
- V1 tanpa label sintetis (B12).
- Generator mengabaikan `waktu_tetap` 15 mnt (B15).
- Laporan Q2 salah label "18 antaran/hari" (kapasitas 17).

---

## Tidak bisa diuji

| Butir | Alasan |
|---|---|
| Kebenaran tarif GoSend/GrabExpress, overhead, kecepatan, sebaran jarak | butuh data lapangan / aplikasi; aturan sandbox melarang API eksternal |
| Performa ETA/klasifikasi di dunia nyata | tidak ada log PWA Kurir asli |
| Model ML milik Ida | **SKIPPED**: tidak ada kode model atau artefak terlatih di kiriman; hanya dataset & baseline rerata di `manifest_split.json` |
| Asal `data/model/*` dan kolom `jumlah_item` | kode pembuat tidak dikirim (Temuan 2) |
| Spesifikasi WP-45 asli | dokumen spec tidak ada di kiriman; dipakai daftar kolom dari brief PL |
| Rekalkulasi rumus Excel | `s01` membaca nilai cache (`data_only=True`); tidak ada Excel/LibreOffice di sandbox |
| Sheet `T8_Data_dari_Ops` | tidak ada di workbook (temuan E1 milik Ida) |
| Notebook di Colab | tidak dijalankan ulang (butuh Colab + Drive mount); status tersimpan dibaca saja |
| Cek visual simulator di browser | preview butuh `.claude/launch.json` di root project (di luar sandbox); app diuji headless dengan `streamlit.testing.AppTest` (render, slider, reset: 0 exception) |
| Branch git `sandbox/ida-sim` | folder project bukan repo git; tidak ada yang di-commit |
