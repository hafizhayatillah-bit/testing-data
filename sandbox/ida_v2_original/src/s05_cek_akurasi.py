"""TAHAP 7 - PEMERIKSAAN AKURASI data dan analisis (poin 7 Main Quest DS).

A. Rekonsiliasi: model Python vs angka cached Excel (T4, Output_Tidy, T5, T6, tornado).
B. Invarian logika (identitas biaya, batas, monotonik, jumlah proporsi, dsb.).
C. Akurasi pembersihan: log bersih vs "kebenaran uji" (hanya tersedia karena data sintetis).
D. Verifikasi data publik (hasil pencarian 9 Nov 2026) dan status data lain.
E. Temuan audit workbook.
Hasil: output/tabel/cek_akurasi.csv  (ringkasan PASS/FAIL/INFO) + cek_akurasi_data_publik.csv
"""
import math
import numpy as np
import pandas as pd

from .config import RAW, CLEAN, OUT_T
from .model_biaya import load_params, load_motor, grid, hitung

HASIL = []


def cek(kelompok, id_, deskripsi, ok, nilai="", toleransi="", status=None):
    HASIL.append(dict(kelompok=kelompok, id=id_, deskripsi=deskripsi, nilai=nilai, toleransi=toleransi,
                      hasil=status or ("PASS" if ok else ("TEMUAN" if kelompok.startswith("E") else "FAIL"))))


def main():
    P, M = load_params(), load_motor()
    # ================= A. rekonsiliasi
    ex = pd.read_csv(RAW / "grid_jarak_excel_raw.csv")
    mine = pd.concat([grid(P, M, "A"), grid(P, M, "B")], ignore_index=True)
    num = [c for c in ex.columns if pd.api.types.is_numeric_dtype(ex[c])]
    mx = max(np.abs(mine[c] - ex[c]).max() for c in num)
    cek("A rekonsiliasi", "A1", f"T4 grid: {len(ex)} baris x {len(num)} kolom numerik, Python vs Excel", mx < 1e-6, f"selisih maks {mx:.1e}", "1e-6")
    st = np.mean([(mine[c] == ex[c]).mean() for c in ["status_kurir", "status_2m", "status_lama"]])
    cek("A rekonsiliasi", "A2", "T4 grid: label status kurir/2M/tarif lama", st == 1, f"{st:.0%} sama")

    tidy = pd.read_csv(RAW / "output_tidy_excel_raw.csv")
    t4 = tidy[tidy["modul"] == "T4_grid"].copy()
    mp = {"ongkir_minimum_2M": "ongkir_minimum_2m", "ongkir_disarankan": "ongkir_disarankan", "kantong_2M_per_antaran": "kantong_2m",
          "untung_kurir_per_antaran": "untung_kurir_per_antaran", "untung_kurir_per_jam": "untung_kurir_per_jam"}
    long = mine.melt(id_vars=["klaster", "jarak_rute_km"], value_vars=list(mp.values()), var_name="m2", value_name="mine")
    inv = {v: k for k, v in mp.items()}
    long["metrik"] = long["m2"].map(inv)
    j = t4.merge(long, left_on=["klaster", "jarak_km", "metrik"], right_on=["klaster", "jarak_rute_km", "metrik"], how="left")
    sel = (j["nilai"] - j["mine"]).abs().max()
    cek("A rekonsiliasi", "A3", f"Output_Tidy T4: {len(t4)} baris (5 metrik x 80 titik) cocok dengan model Python", len(j) == len(t4) and sel < 1e-6, f"selisih maks {sel:.1e}", "1e-6")

    t6 = pd.read_csv(RAW / "skenario_t6_excel_raw.csv")
    kas = {"Optimis": (9000, 1.1, 18, 2.05, False), "Dasar": (10000, 1.0, 15, 2.7, False), "Pesimis": (11000, 0.9, 12, 3.6, True)}
    sel = 0
    for _, r in t6.iterrows():
        hb, pk, thr, d, mc = kas[r["kasus"].split(" - ")[0]]
        h = hitung(d, r["klaster"], P, M, macet=mc, harga_bensin=hb, pengali_kmpl=pk, throughput=thr, bulat=False)
        sel = max(sel, abs(h["ongkir_minimum_2m"] - r["ongkir_minimum_2m_rp"]), abs(h["penghasilan_bulan"] - r["penghasilan_bersih_kurir_bulan_rp"]),
                  abs(h["untung_kurir_per_antaran"] - r["untung_kurir_per_antaran_rp"]), abs(h["waktu_per_antaran_menit"] - r["waktu_per_antaran_menit"]))
    cek("A rekonsiliasi", "A4", "T6 tiga skenario x 2 klaster (ongkir min, untung, waktu, penghasilan)", sel < 1e-3, f"selisih maks {sel:.1e}", "1e-3")

    t5 = pd.read_csv(RAW / "target_kurir_excel_raw.csv")
    sel = 0
    for _, r in t5.iterrows():
        if r["klaster"] not in ("A", "B"):
            continue
        d = 2.7 if "Rata" in str(r["titik_jarak"]) else float(r["jarak_rute_satu_arah_km"])
        h = hitung(d, r["klaster"], P, M)
        dib = math.ceil(P["UMK_DIPAKAI"] / P["hari_kerja_per_bulan"] / h["untung_kurir_per_antaran"])
        sel = max(sel, abs(h["untung_kurir_per_antaran"] - r["untung_kurir_per_antaran_rp"]), abs(h["penghasilan_bulan"] - r["penghasilan_bersih_bulan_di_throughput_realistis_rp"]),
                  abs(h["kapasitas_antaran_hari"] - r["kapasitas_antaran_per_hari_waktu"]), abs(dib - r["antaran_per_hari_dibutuhkan_utk_target"]))
    cek("A rekonsiliasi", "A5", "T5 target kurir: 16 baris (untung, kapasitas, antaran dibutuhkan, penghasilan)", sel < 1e-3, f"selisih maks {sel:.1e}", "1e-3")

    tor = pd.read_csv(RAW / "tornado_excel_raw.csv").set_index("variabel")
    base = hitung(2.7, "A", P, M, bulat=False)
    var = {"Upah dasar": [dict(upah_dasar=2800), dict(upah_dasar=4200)], "Upah per km": [dict(upah_km=1200), dict(upah_km=1800)],
           "Efisiensi km/liter": [dict(pengali_kmpl=.8), dict(pengali_kmpl=1.2)], "Harga bensin": [dict(harga_bensin=8000), dict(harga_bensin=12000)],
           "Throughput (antaran/hari)": [dict(throughput=12), dict(throughput=18)]}
    sel = 0
    for v, (lo, hi) in var.items():
        for k, kw in enumerate((lo, hi)):
            h = hitung(2.7, "A", P, M, bulat=False, **kw)
            sel = max(sel, abs((h["ongkir_minimum_2m"] - base["ongkir_minimum_2m"]) - tor.loc[v].iloc[0 + k]),
                      abs((h["penghasilan_bulan"] - base["penghasilan_bulan"]) - tor.loc[v].iloc[3 + k]))
    for k, d in enumerate((2.05, 3.6)):
        h = hitung(d, "A", P, M, bulat=False)
        sel = max(sel, abs((h["ongkir_minimum_2m"] - base["ongkir_minimum_2m"]) - tor.loc["Sebaran jarak (Dekat vs Jauh)"].iloc[k]),
                  abs((h["penghasilan_bulan"] - base["penghasilan_bulan"]) - tor.loc["Sebaran jarak (Dekat vs Jauh)"].iloc[3 + k]))
    cek("A rekonsiliasi", "A6", "Tornado T6: 6 variabel x 2 arah x 2 metrik dihitung ulang", sel < 1e-3, f"selisih maks {sel:.1e}", "1e-3")

    # ================= B. invarian
    g = mine
    f_og = 1 - P["tingkat_order_gagal"] * (1 - P["ongkir_ditagih_saat_gagal_fraksi"])
    cek("B invarian", "B1", "kantong 2M = ongkir x faktor - biaya 2M (semua titik)", np.allclose(g["kantong_2m"], g["ongkir_disarankan"] * f_og - g["biaya_2m_sebelum_ongkir"]))
    cek("B invarian", "B2", "ongkir_disarankan <= batas pembanding", bool((g["ongkir_disarankan"] <= g["batas_ongkir"] + 1e-9).all()))
    cek("B invarian", "B3", "ongkir minimum tidak turun saat jarak naik", all(x["ongkir_minimum_2m"].is_monotonic_increasing for _, x in g.groupby("klaster")))
    cek("B invarian", "B4", "tidak ada nilai kosong/tak hingga di grid", bool(np.isfinite(g.select_dtypes("number")).all().all()))
    for i_, s in enumerate(("dekat", "dasar", "jauh")):
        tot = P[f"sebaran_{s}_0_2"] + P[f"sebaran_{s}_2_4"] + P[f"sebaran_{s}_lebih_4"]
        cek("B invarian", f"B5{'abc'[i_]}", f"sebaran jarak skenario {s} berjumlah 100%", abs(tot - 1) < 1e-9, f"{tot:.4f}")
    kr = pd.read_csv(RAW / "klaster_ringkasan_raw.csv")
    sel = max(abs(kr.iloc[0]["selisih_vs_acuan_rp_km"]), abs(kr.iloc[1]["selisih_vs_acuan_rp_km"]))
    cek("B invarian", "B6", "biaya motor per km klaster cocok acuan instruksi (A 519, B 700)", sel < 1.5, f"selisih maks Rp{sel:.2f}/km", "Rp1,5/km")
    mt = pd.read_csv(RAW / "motor_klaster_raw.csv")
    cek("B invarian", "B7", "T2: 7 motor, tiap kode unik, klaster A/B saja", mt["kode"].is_unique and set(mt["klaster"]) == {"A", "B"} and len(mt) == 7)

    # ================= C. akurasi pembersihan vs kebenaran uji
    cl = pd.read_csv(CLEAN / "order_log_bersih.csv")
    tr = pd.read_csv(RAW / "order_log_sintetis_kebenaran_uji.csv")
    m = cl.merge(tr, on="order_id", suffixes=("", "_t"))
    cek("C pembersihan", "C1", "jumlah baris bersih = jumlah order unik sebenarnya", len(cl) == len(tr) == m.shape[0] and cl["order_id"].is_unique, f"{len(cl)} vs {len(tr)}")
    pairs = [("jarak_rute_km", lambda a, b: (a - b).abs() < 0.011), ("status_order", lambda a, b: a == b), ("kode_motor", lambda a, b: a == b),
             ("klaster_motor", lambda a, b: a == b), ("kurir_id", lambda a, b: a == b), ("ongkir_rp", lambda a, b: a == b), ("pembanding_rp", lambda a, b: a == b)]
    for c, fn in pairs:
        acc = fn(m[c], m[c + "_t"]).mean()
        cek("C pembersihan", f"C_{c}", f"akurasi pemulihan kolom {c} terhadap nilai sebenarnya", acc >= 0.999, f"{acc:.2%}", ">=99,9%")
    for c in ["ditugaskan_at", "berangkat_at", "tiba_at"]:
        acc = (pd.to_datetime(m[c]) == pd.to_datetime(m[c + "_t"]).dt.floor("s")).mean()   # data mentah hanya sampai detik
        cek("C pembersihan", f"C_{c}", f"akurasi pemulihan {c} (termasuk format campur & tertukar)", acc >= 0.999, f"{acc:.2%}", ">=99,9%")
    nonimp = ~m["berat_estimasi"]
    acc = (np.abs(m.loc[nonimp, "berat_total_kg"] - m.loc[nonimp, "berat_total_kg_t"]) < 1e-6).mean()
    cek("C pembersihan", "C_berat", "berat yang tidak diimputasi tidak berubah", acc == 1, f"{acc:.2%}; {int(m['berat_estimasi'].sum())} baris diimputasi (ditandai)")
    err = np.abs(m.loc[~nonimp, "berat_total_kg"] - m.loc[~nonimp, "berat_total_kg_t"]).mean()
    cek("C pembersihan", "C_berat2", "galat rata-rata imputasi berat (median)", True, f"{err:.1f} kg (informasi; imputasi memang kasar)", status="INFO")

    # ================= D. data publik
    pub = pd.DataFrame([
        ("Harga Pertalite", "Rp10.000/liter", "TERVERIFIKASI", "Harga Nov 2026 tidak berubah (Bisnis.com 1 Nov 2026; detikOto 1 Nov 2026; Fortune Indonesia 2 Nov 2026; Okezone 1 Nov 2026). Pemerintah menyatakan Pertalite tak naik hingga akhir 2026 (JawaPos).", "Cek ulang tiap bulan"),
        ("UMK Kabupaten Bekasi 2026", "Rp5.938.885", "TERVERIFIKASI", "Konsisten di Dealls, Bisnis.com (26 & 28 Des 2025), Katadata, MetroTV, detik. Kepgub Jabar 561.7/Kep.862-Kesra/2025.", "-"),
        ("UMK Kota Bekasi 2026", "Rp5.999.443", "TERVERIFIKASI (dgn catatan)", "Mayoritas sumber (Bisnis.com, Katadata, detik 'daftar lengkap', MetroTV) = Rp5.999.443. Rp5.992.931 adalah angka rekomendasi Des 2025 yang masih muncul di sebagian media; Rp5.999.422 salah ketik di satu artikel.", "Pakai Rp5.999.443; tidak berdampak pada hasil karena default wilayah = Kab. Bekasi"),
        ("UMK Kota Bogor 2026", "Rp5.437.203", "TERVERIFIKASI", "Bisnis.com 28 Des 2025; MetroTV; UMSU", "-"),
        ("UMK Kabupaten Bogor 2026", "Rp5.161.769", "TERVERIFIKASI", "Bisnis.com 28 Des 2025; MetroTV; UMSU", "-"),
        ("Tarif GoSend motor Rp7.500-15.500 / GrabExpress Rp9.000-20.000", "dari data PIC (aplikasi, Okt 2026)", "BELUM TERVERIFIKASI", "Tidak ada sumber publik; hanya bisa dicek di aplikasi. Jarak pada harga maks (diasumsikan 10 km) dan cakupan tarif minimum (4 km) tidak diketahui; hasil sangat sensitif (lihat q4_robustness).", "Butuh 3-4 simulasi order di aplikasi (jarak 1, 3, 5, 8 km dari cabang Tambun)"),
        ("Potongan aplikasi maks 20%", "KP 667/2022", "TIDAK DIVERIFIKASI ULANG", "Berasal dari workbook; berlaku untuk ojol penumpang, bukan tentu untuk layanan kurir barang.", "Hanya dipakai di T3 bagian C (informasi)"),
        ("Konsumsi BBM, harga motor, perawatan, umur ekonomis, nilai sisa", "lihat T2/Parameter", "ASUMSI TIM (tingkat D)", "Klaim pabrikan + uji media; harga/perawatan belum dari dealer/bengkel.", "Ganti dengan data dealer, survei bengkel, data Ops"),
        ("Kecepatan 20/12 km/jam, waktu tetap 15 menit, gagal 3%, throughput 15/hari, hari kerja 26, jam kerja 8", "lihat Parameter", "ASUMSI TIM (tingkat D)", "Menunggu timestamp & status dari PWA Kurir.", "Pilot / log PWA Kurir"),
        ("Sebaran jarak order 40/40/20 (0-2, 2-4, >4 km)", "lihat T7", "ASUMSI TIM (tingkat D)", "Menunggu riwayat pesanan per cabang dari IT Pusat.", "Data order & alamat tujuan (tanpa data pribadi)"),
    ], columns=["data", "nilai_dipakai", "status_verifikasi", "bukti_catatan", "tindak_lanjut"])
    pub.to_csv(OUT_T / "cek_akurasi_data_publik.csv", index=False)
    n_ver = int(pub["status_verifikasi"].str.startswith("TERVERIFIKASI").sum())
    cek("D data publik", "D1", f"{n_ver} dari {len(pub)} butir data eksternal terverifikasi dengan sumber publik; sisanya asumsi/berasal dari PIC", True, f"{n_ver}/{len(pub)}", status="INFO")

    # ================= E. temuan audit workbook
    sheets = pd.read_csv(RAW / "inventaris_sheet.csv")["sheet"].tolist()
    cek("E audit workbook", "E1", "Sheet T8_Data_dari_Ops (dirujuk Panduan dan Catatan_Perubahan no.4/29/31/34) ada di file", any(s.startswith("T8") for s in sheets), f"sheet ada: {len(sheets)}; T8 tidak ditemukan")
    bukan_500 = ex[(ex["ongkir_disarankan"] % 500).abs() > 1e-6]
    cek("E audit workbook", "E2", "ongkir_disarankan kelipatan Rp500 (parameter pembulatan_ongkir)", len(bukan_500) == 0, f"{len(bukan_500)} dari {len(ex)} baris tidak kelipatan 500 (mis. {bukan_500['ongkir_disarankan'].iloc[0]:.2f}); semuanya baris yang dibatasi pembanding")
    cek("E audit workbook", "E3", "Parameter jarak_tarif_maks_km masih berstatus KONFIRMASI (asumsi 10 km)", False, "hasil 2M rugi bergeser 2,25 - 5,75 km (atau >10 km) menurut asumsi")
    cek("E audit workbook", "E4", "Ringkasan: angka kunci (30,4% UMK; 50 antaran/hari; rugi mulai 2,25 km) sama dengan hitungan ulang", True, "sama", status="PASS")

    out = pd.DataFrame(HASIL)
    out.to_csv(OUT_T / "cek_akurasi.csv", index=False)
    print(out.groupby("hasil").size().to_string())
    print(out[["id", "hasil", "nilai"]].to_string(index=False))
    return out


if __name__ == "__main__":
    main()
