"""TAHAP 2 & 3 - ASSESSING dan CLEANING log order (sintetis / nanti log PWA Kurir asli).

Input : data/raw/order_log_sintetis_raw.csv  (ganti dengan log asli berskema sama bila sudah ada)
Output: data/clean/order_log_bersih.csv, dataset_fitur_target.csv, kamus_data.csv,
        output/tabel/profil_data_mentah.csv, output/tabel/log_pembersihan.csv
Setiap aturan dicatat di log_pembersihan.csv (jumlah baris terdampak) agar bisa diaudit.
"""
import numpy as np
import pandas as pd

from .config import RAW, CLEAN, OUT_T
from .model_biaya import load_params, load_motor, biaya_motor_per_km

MAX_RADIUS_KM = 15.0      # di atas ini dianggap salah ketik (di luar radius layanan; asumsi, ubah bila beda)
TOL_JARAK_UPAH = 0.05     # toleransi selisih jarak vs jarak turunan dari snapshot upah (km)
WAKTU_MIN, WAKTU_MAX = 5, 240  # batas wajar waktu per antaran (menit)
TS = ["ditugaskan_at", "berangkat_at", "tiba_at", "selesai_at", "kembali_at"]


def profil(df):
    p = pd.DataFrame({"tipe": df.dtypes.astype(str), "kosong": df.isna().sum(),
                      "persen_kosong": (df.isna().mean() * 100).round(2), "nilai_unik": df.nunique()})
    p.index.name = "kolom"
    return p.reset_index()


def parse_ts(s, fmt_utama, fmt_alt):
    a = pd.to_datetime(s, format=fmt_utama, errors="coerce")
    b = pd.to_datetime(s, format=fmt_alt, errors="coerce")
    return a.fillna(b)


def rp_ke_int(s):
    return pd.to_numeric(s.astype(str).str.replace(r"[^\d\-]", "", regex=True), errors="coerce")


def bersihkan(raw, P, M):
    log = []
    add = lambda langkah, masalah, n, aturan: log.append(dict(langkah=langkah, masalah=masalah, baris_terdampak=int(n), aturan=aturan))
    df = raw.copy()
    add("0 awal", "jumlah baris mentah", len(df), "-")

    # 1. duplikat
    n = df.duplicated().sum()
    df = df.drop_duplicates().reset_index(drop=True)
    add("1 duplikat", "baris duplikat persis", n, "drop_duplicates (pertahankan kemunculan pertama)")
    sisa = df["order_id"].duplicated().sum()
    add("1 duplikat", "order_id ganda dengan isi berbeda (sisa)", sisa, "harus 0; bila >0 telusuri manual")

    # 2. kategori
    k0 = df["kode_motor"].copy()
    df["kode_motor"] = df["kode_motor"].astype(str).str.upper().str.replace(r"\s+", "", regex=True)
    add("2 kategori", "kode_motor tidak rapi (spasi/huruf kecil)", (k0 != df["kode_motor"]).sum(), "strip + upper + hapus spasi")
    tak_valid = (~df["kode_motor"].isin(M["kode"])).sum()
    add("2 kategori", "kode_motor di luar M1-M7", tak_valid, "harus 0; bila >0 minta master armada")
    k0 = df["kurir_id"].copy()
    df["kurir_id"] = df["kurir_id"].astype(str).str.upper().str.replace("-", "", regex=False)
    add("2 kategori", "kurir_id format beda (k-07 vs K07)", (k0 != df["kurir_id"]).sum(), "upper + hapus '-'")
    s0 = df["status_order"].copy()
    df["status_order"] = np.where(df["status_order"].astype(str).str.lower().str.contains("gagal"),
                                  "gagal_pelanggan_tidak_ada", "berhasil")
    add("2 kategori", "label status_order tidak seragam", (s0 != df["status_order"]).sum(), "mengandung 'gagal' -> gagal_pelanggan_tidak_ada; lainnya -> berhasil")
    kl = df["klaster_motor"].isna().sum()
    df["klaster_motor"] = df["kode_motor"].map(M.set_index("kode")["klaster"])
    add("2 kategori", "klaster_motor kosong di log", kl, "diturunkan dari master armada T2 (kode_motor -> klaster)")

    # 3. rupiah teks -> angka
    for c in ["ongkir_rp", "pembanding_rp"]:
        n = df[c].astype(str).str.contains("Rp").sum()
        df[c] = rp_ke_int(df[c])
        add("3 tipe data", f"{c} berupa teks 'Rp x.xxx'", n, "buang non-angka lalu cast ke integer")

    # 4. timestamp
    n = df["ditugaskan_at"].astype(str).str.contains("/").sum()
    df["ditugaskan_at"] = parse_ts(df["ditugaskan_at"], "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M")
    for c in TS[1:]:
        df[c] = pd.to_datetime(df[c], format="%Y-%m-%d %H:%M:%S", errors="coerce")
    add("4 waktu", "format tanggal campuran (dd/mm/yyyy)", n, "parse dua format; yang gagal -> NaT")
    add("4 waktu", "timestamp tidak terbaca (NaT)", df[TS].isna().sum().sum(), "harus 0")
    sw = df["tiba_at"] < df["berangkat_at"]
    df.loc[sw, ["berangkat_at", "tiba_at"]] = df.loc[sw, ["tiba_at", "berangkat_at"]].to_numpy()
    add("4 waktu", "berangkat_at & tiba_at tertukar", sw.sum(), "tukar kembali bila tiba < berangkat")
    df["ts_diperbaiki"] = sw
    urut = (df[TS].diff(axis=1).iloc[:, 1:] >= pd.Timedelta(0)).all(axis=1)
    add("4 waktu", "urutan event masih salah setelah perbaikan", (~urut).sum(), "ditandai; dikeluarkan dari analisis waktu bila ada")

    # 5. jarak: validasi silang dengan snapshot upah (upah_total = dasar + per_km x jarak)
    d_upah = ((df["upah_total_rp"] - df["upah_dasar_rp"]) / df["upah_per_km_rp"]).round(2)
    j = df["jarak_rute_km"]
    kosong = j.isna()
    luar = (j <= 0) | (j > MAX_RADIUS_KM)
    selisih = (~kosong & ~luar) & ((j - d_upah).abs() > TOL_JARAK_UPAH)
    perlu = kosong | luar | selisih
    add("5 jarak", "jarak_rute_km kosong", kosong.sum(), "diturunkan dari snapshot upah")
    add("5 jarak", f"jarak <=0 atau > {MAX_RADIUS_KM:g} km (salah ketik)", luar.sum(), "diturunkan dari snapshot upah")
    add("5 jarak", "jarak tidak cocok dengan snapshot upah", selisih.sum(), "diturunkan dari snapshot upah")
    df["jarak_diperbaiki"] = perlu
    df.loc[perlu, "jarak_rute_km"] = d_upah[perlu]
    add("5 jarak", "jarak masih tidak valid setelah perbaikan", ((df["jarak_rute_km"] <= 0) | df["jarak_rute_km"].isna()).sum(), "harus 0")

    # 6. berat
    miss = df["berat_total_kg"].isna()
    med = df["berat_total_kg"].median()
    df["berat_estimasi"] = miss
    df.loc[miss, "berat_total_kg"] = med
    add("6 berat", "berat_total_kg kosong", miss.sum(), f"imputasi median ({med:.1f} kg) + berat_estimasi=True (sesuai T1 no.9)")

    # 7. konsistensi uang
    exp_bayar = np.where(df["status_order"] == "gagal_pelanggan_tidak_ada",
                         df["upah_total_rp"] * P["bayar_order_gagal_fraksi"], df["upah_total_rp"]).round()
    mism = (df["bayar_kurir_rp"] - exp_bayar).abs() > 1
    add("7 uang", "bayar_kurir_rp tidak sesuai aturan (gagal=50% upah)", mism.sum(), "ditandai saja")
    df["bayar_tidak_sesuai"] = mism

    # 8. turunan
    df["tanggal"] = df["ditugaskan_at"].dt.date
    df["jam"] = df["ditugaskan_at"].dt.hour + df["ditugaskan_at"].dt.minute / 60
    df["hari_minggu"] = df["ditugaskan_at"].dt.dayofweek       # 0=Senin
    df["waktu_per_antaran_menit"] = ((df["kembali_at"] - df["ditugaskan_at"]).dt.total_seconds() / 60).round(2)
    df["waktu_tempuh_satu_arah_menit"] = ((df["tiba_at"] - df["berangkat_at"]).dt.total_seconds() / 60).round(2)
    wajar = df["waktu_per_antaran_menit"].between(WAKTU_MIN, WAKTU_MAX)
    add("8 outlier", f"waktu_per_antaran di luar {WAKTU_MIN}-{WAKTU_MAX} menit", (~wajar).sum(), "ditandai (flag_waktu_aneh), tidak dibuang")
    df["flag_waktu_aneh"] = ~wajar
    gagal = df["status_order"] == "gagal_pelanggan_tidak_ada"
    df["gagal"] = gagal.astype(int)
    df["ongkir_diterima_rp"] = np.where(gagal, df["ongkir_rp"] * P["ongkir_ditagih_saat_gagal_fraksi"], df["ongkir_rp"]).round()
    bm = np.array([biaya_motor_per_km(M, P, k, m == "Macet") for k, m in zip(df["klaster_motor"], df["kondisi_lalu_lintas"])])
    df["biaya_motor_rp"] = (bm * df["jarak_tempuh_km"]).round(0)
    df["untung_kurir_rp"] = (df["bayar_kurir_rp"] - df["biaya_motor_rp"]).round(0)
    cab = P["overhead_harian_cabang"] / P["throughput_antaran_per_hari"]
    df["kantong_2m_rp"] = (df["ongkir_diterima_rp"] - df["bayar_kurir_rp"] - cab).round(0)
    df["untung_kurir_per_jam_rp"] = (df["untung_kurir_rp"] / df["waktu_per_antaran_menit"] * 60).round(0)
    add("9 akhir", "jumlah baris bersih", len(df), "-")

    kolom = ["order_id", "tanggal", "jam", "hari_minggu", "cabang_id", "kurir_id", "kode_motor", "klaster_motor",
             "jarak_rute_km", "jarak_tempuh_km", "kondisi_lalu_lintas", "berat_total_kg", "berat_estimasi",
             "status_order", "gagal", "upah_dasar_rp", "upah_per_km_rp", "upah_total_rp", "bayar_kurir_rp",
             "ongkir_rp", "ongkir_diterima_rp", "pembanding_rp", "energi_liter"] + TS + \
            ["waktu_per_antaran_menit", "waktu_tempuh_satu_arah_menit", "biaya_motor_rp", "untung_kurir_rp",
             "untung_kurir_per_jam_rp", "kantong_2m_rp", "jarak_diperbaiki", "ts_diperbaiki", "flag_waktu_aneh",
             "bayar_tidak_sesuai", "skema_upah_versi", "sumber_data"]
    return df[kolom].sort_values("ditugaskan_at").reset_index(drop=True), pd.DataFrame(log)


def dataset_fitur_target(bersih):
    d = bersih[~bersih["flag_waktu_aneh"]].copy()
    d["is_macet"] = (d["kondisi_lalu_lintas"] == "Macet").astype(int)
    d["berat_estimasi"] = d["berat_estimasi"].astype(int)
    cut = d["ditugaskan_at"].quantile(0.8)
    d["split"] = np.where(d["ditugaskan_at"] <= cut, "train", "test")   # split menurut waktu, bukan acak
    cols = ["order_id", "split", "jarak_rute_km", "is_macet", "jam", "hari_minggu", "klaster_motor", "cabang_id",
            "berat_total_kg", "berat_estimasi", "waktu_per_antaran_menit", "gagal", "sumber_data"]
    return d[cols]


KAMUS = [
 ("order_id", "teks", "-", "ID unik order", "log"), ("tanggal", "tanggal", "-", "Tanggal penugasan", "turunan"),
 ("jam", "desimal", "jam (0-24)", "Jam penugasan (mis. 9.5 = 09:30)", "turunan"),
 ("hari_minggu", "integer", "0=Senin..6=Minggu", "Hari dalam seminggu", "turunan"),
 ("cabang_id", "teks", "-", "Kode cabang C01-C07 (dummy; kode pos asli dari master cabang IT Pusat)", "log"),
 ("kurir_id", "teks", "-", "ID kurir (K01..)", "log"), ("kode_motor", "teks", "M1-M7", "Jenis motor kurir (T2)", "log"),
 ("klaster_motor", "teks", "A/B", "A=110-125cc, B=150-160cc", "master armada"),
 ("jarak_rute_km", "desimal", "km", "Jarak rute SATU ARAH (routing API) - dasar upah per km", "log"),
 ("jarak_tempuh_km", "desimal", "km", "Jarak tempuh pulang-pergi (odometer/GPS)", "log"),
 ("kondisi_lalu_lintas", "teks", "Normal/Macet", "Kondisi lalu lintas saat antar", "log"),
 ("berat_total_kg", "desimal", "kg", "Berat total barang", "log / imputasi"),
 ("berat_estimasi", "boolean", "-", "True bila berat diimputasi", "turunan"),
 ("status_order", "teks", "berhasil/gagal_pelanggan_tidak_ada", "Status akhir", "log"),
 ("gagal", "0/1", "-", "1 = gagal (pelanggan tidak ada)", "turunan"),
 ("upah_dasar_rp", "integer", "Rp", "Snapshot upah dasar per antaran", "log"),
 ("upah_per_km_rp", "integer", "Rp/km", "Snapshot upah per km", "log"),
 ("upah_total_rp", "integer", "Rp", "Upah penuh = dasar + per km x jarak", "log"),
 ("bayar_kurir_rp", "integer", "Rp", "Yang dibayar ke kurir (gagal = 50% upah)", "log"),
 ("ongkir_rp", "integer", "Rp", "Ongkir saat checkout (snapshot pricing engine)", "log"),
 ("ongkir_diterima_rp", "desimal", "Rp", "Ongkir yang benar-benar diterima 2M (gagal = tidak ditagih)", "turunan"),
 ("pembanding_rp", "integer", "Rp", "Tarif GoSend/GrabExpress pembanding", "log"),
 ("energi_liter", "desimal", "liter", "BBM terpakai (uji kecukupan upah)", "log"),
 ("ditugaskan_at..kembali_at", "timestamp", "-", "5 event pengiriman (T1 no.2)", "log"),
 ("waktu_per_antaran_menit", "desimal", "menit", "kembali_at - ditugaskan_at", "turunan"),
 ("waktu_tempuh_satu_arah_menit", "desimal", "menit", "tiba_at - berangkat_at", "turunan"),
 ("biaya_motor_rp", "desimal", "Rp", "Biaya motor per order = biaya/km klaster x jarak tempuh", "turunan"),
 ("untung_kurir_rp", "desimal", "Rp", "bayar_kurir - biaya_motor", "turunan"),
 ("untung_kurir_per_jam_rp", "desimal", "Rp/jam", "untung_kurir / waktu x 60", "turunan"),
 ("kantong_2m_rp", "desimal", "Rp", "ongkir_diterima - bayar_kurir - biaya cabang per antaran", "turunan"),
 ("jarak_diperbaiki / ts_diperbaiki / flag_waktu_aneh / bayar_tidak_sesuai", "boolean", "-", "Penanda hasil cleaning", "turunan"),
 ("skema_upah_versi", "teks", "-", "Versi skema upah", "log"),
 ("sumber_data", "teks", "-", "SINTETIS_SIMULASI = data buatan, BUKAN transaksi asli", "label wajib"),
]


def main():
    P, M = load_params(), load_motor()
    raw = pd.read_csv(RAW / "order_log_sintetis_raw.csv")
    profil(raw).to_csv(OUT_T / "profil_data_mentah.csv", index=False)
    bersih, log = bersihkan(raw, P, M)
    bersih.to_csv(CLEAN / "order_log_bersih.csv", index=False)
    log.to_csv(OUT_T / "log_pembersihan.csv", index=False)
    dataset_fitur_target(bersih).to_csv(CLEAN / "dataset_fitur_target.csv", index=False)
    pd.DataFrame(KAMUS, columns=["kolom", "tipe", "satuan", "deskripsi", "asal"]).to_csv(CLEAN / "kamus_data.csv", index=False)
    # tabel rujukan bersih untuk anggota lain
    par = pd.read_csv(RAW / "parameter_model_raw.csv")
    par["jenis"] = np.where(par["status"].isin(["Rumus", "Cek"]), "turunan_rumus", "input")
    par.to_csv(CLEAN / "parameter_model_bersih.csv", index=False)
    M.to_csv(CLEAN / "motor_klaster_bersih.csv", index=False)
    print(log.to_string(index=False))
    print("[bersih]", bersih.shape)


if __name__ == "__main__":
    main()
