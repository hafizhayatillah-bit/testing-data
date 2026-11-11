"""Pembuat log order SINTETIS (dummy) untuk pra-peluncuran.

PENTING: produk belum launch, jadi TIDAK ADA data transaksi asli. Data ini dibuat dari parameter
model tim (Parameter/T2/T7) + derau acak, hanya untuk (1) menguji pipeline wrangling, (2) kontrak
format data bagi Gen AI & Full-Stack. Semua baris berlabel sumber_data = SINTETIS_SIMULASI.
Jangan menarik kesimpulan bisnis dari log ini; ganti dengan log PWA Kurir asli saat tersedia.
Skema kolom mengikuti sheet T1_Skema_Variabel.
"""
import numpy as np
import pandas as pd

from .config import SEED, N_ORDER_SINTETIS, LABEL_SINTETIS, RAW
from .model_biaya import load_params, load_motor, biaya_motor_per_km, pembanding, hitung

CABANG = [f"C{i:02d}" for i in range(1, 8)]   # 7 cabang (nama/kode pos asli menunggu master IT Pusat)
N_KURIR = 28


def _fmt_rp(x):
    return "Rp " + f"{int(x):,}".replace(",", ".")


def generate(n=N_ORDER_SINTETIS, seed=SEED):
    rng = np.random.default_rng(seed)
    P, M = load_params(), load_motor()
    # --- armada kurir
    kurir = pd.DataFrame({"kurir_id": [f"K{i:02d}" for i in range(1, N_KURIR + 1)],
                          "cabang_id": [CABANG[i % 7] for i in range(N_KURIR)],
                          "kode_motor": rng.choice(M["kode"], N_KURIR)})
    kurir = kurir.merge(M[["kode", "klaster", "konsumsi_klaim_kmpl"]], left_on="kode_motor", right_on="kode")
    kk = kurir.sample(n, replace=True, random_state=int(seed % 2**31)).reset_index(drop=True)

    # --- waktu order: 8 minggu, Senin-Sabtu, puncak pagi & sore
    start = pd.Timestamp("2026-12-01")
    hari = rng.integers(0, 56, n)
    tgl = start + pd.to_timedelta(hari, unit="D")
    tgl = tgl.where(tgl.dayofweek != 6, tgl + pd.Timedelta(days=1))
    jam = np.where(rng.random(n) < 0.55, rng.normal(9, 1.3, n), rng.normal(16, 1.5, n))
    jam = np.clip(jam, 7, 19.5)
    t0 = tgl.normalize() + pd.to_timedelta((jam * 60).astype(int), unit="m")

    # --- jarak: sebaran skenario Dasar T7 (40/40/20 pada 0-2, 2-4, >4 km)
    b = rng.choice(3, n, p=[P["sebaran_dasar_0_2"], P["sebaran_dasar_2_4"], P["sebaran_dasar_lebih_4"]])
    d = np.where(b == 0, rng.uniform(0.3, 2, n), np.where(b == 1, rng.uniform(2, 4, n), rng.uniform(4, 8, n)))
    d = np.round(d, 2)
    macet_p = np.where((jam >= 15.5) & (jam <= 18), 0.40, 0.18)
    macet = rng.random(n) < macet_p
    v = np.where(macet, P["kecepatan_rata2_macet_km_jam"], P["kecepatan_rata2_normal_km_jam"]) * rng.lognormal(0, 0.15, n)
    one_way = d / v * 60
    fixed = np.clip(rng.normal(P["waktu_tetap_per_antaran_menit"], 4, n), 6, None)
    berat = np.clip(rng.gamma(4, 3.2, n), 2, 30).round(1)
    gagal = rng.random(n) < (P["tingkat_order_gagal"] + 0.004 * np.clip(d - 3, 0, None))

    # --- timestamp event
    t_ber = t0 + pd.to_timedelta(rng.uniform(2, 8, n), unit="m")
    t_tiba = t_ber + pd.to_timedelta(one_way, unit="m")
    wait = np.where(gagal, rng.uniform(8, 15, n), rng.uniform(3, 10, n))
    t_sel = t_tiba + pd.to_timedelta(wait, unit="m")
    t_kem = t_sel + pd.to_timedelta(one_way, unit="m")

    # --- uang
    upah = (P["upah_dasar_per_antaran"] + P["upah_per_km"] * d).round().astype(int)
    bayar = np.where(gagal, upah * P["bayar_order_gagal_fraksi"], upah).round().astype(int)
    ongkir = np.array([hitung(float(x), "A", P, M)["ongkir_disarankan"] for x in d])
    ongkir = (np.floor(ongkir / P["pembulatan_ongkir"]) * P["pembulatan_ongkir"]).astype(int)  # kelipatan 500
    pemb = np.array([pembanding(float(x), P) for x in d]).round().astype(int)
    kmpl = kk["konsumsi_klaim_kmpl"].to_numpy() * P["faktor_penyesuaian_konsumsi"]
    liter = (2 * d * rng.uniform(0.95, 1.15, n)) / (kmpl * np.where(macet, P["faktor_konsumsi_saat_macet"], 1)) * rng.lognormal(0, 0.08, n)
    tempuh = np.round(2 * d * rng.uniform(0.95, 1.15, n), 2)

    truth = pd.DataFrame({
        "order_id": [f"ORD-{i:05d}" for i in range(1, n + 1)],
        "ditugaskan_at": t0, "cabang_id": kk["cabang_id"], "kurir_id": kk["kurir_id"],
        "kode_motor": kk["kode_motor"], "klaster_motor": kk["klaster"],
        "jarak_rute_km": d, "jarak_tempuh_km": tempuh,
        "kondisi_lalu_lintas": np.where(macet, "Macet", "Normal"),
        "berangkat_at": t_ber, "tiba_at": t_tiba, "selesai_at": t_sel, "kembali_at": t_kem,
        "berat_total_kg": berat,
        "status_order": np.where(gagal, "gagal_pelanggan_tidak_ada", "berhasil"),
        "upah_dasar_rp": int(P["upah_dasar_per_antaran"]), "upah_per_km_rp": int(P["upah_per_km"]),
        "upah_total_rp": upah, "bayar_kurir_rp": bayar, "ongkir_rp": ongkir, "pembanding_rp": pemb,
        "energi_liter": liter.round(3), "skema_upah_versi": "v2.1-hipotesis",
        "sumber_data": LABEL_SINTETIS,
    })

    raw = inject_mess(truth, rng)
    return raw, truth


def inject_mess(truth, rng):
    """Menambahkan masalah kualitas data yang lazim terjadi (untuk menguji tahap assessing/cleaning)."""
    r = truth.copy()
    n = len(r)
    for c in ["ditugaskan_at", "berangkat_at", "tiba_at", "selesai_at", "kembali_at"]:
        r[c] = r[c].dt.strftime("%Y-%m-%d %H:%M:%S")
    # format tanggal campur (dd/mm/yyyy hh:mm) pada 25% baris di kolom ditugaskan_at
    idx = rng.random(n) < 0.25
    r.loc[idx, "ditugaskan_at"] = pd.to_datetime(r.loc[idx, "ditugaskan_at"]).dt.strftime("%d/%m/%Y %H:%M")
    # berangkat & tiba tertukar (1,5%)
    sw = rng.random(n) < 0.015
    r.loc[sw, ["berangkat_at", "tiba_at"]] = r.loc[sw, ["tiba_at", "berangkat_at"]].to_numpy()
    # jarak hilang (3%) dan salah ketik x10 / negatif (1%)
    r["jarak_rute_km"] = r["jarak_rute_km"].astype(float)
    r.loc[rng.random(n) < 0.03, "jarak_rute_km"] = np.nan
    bad = rng.random(n) < 0.01
    r.loc[bad, "jarak_rute_km"] = np.where(rng.random(bad.sum()) < 0.7, r.loc[bad, "jarak_rute_km"] * 10, -r.loc[bad, "jarak_rute_km"])
    # berat hilang (6%)
    r.loc[rng.random(n) < 0.06, "berat_total_kg"] = np.nan
    # label status tidak konsisten
    alias = {"berhasil": ["berhasil", "BERHASIL", "Berhasil", "selesai"],
             "gagal_pelanggan_tidak_ada": ["gagal_pelanggan_tidak_ada", "Gagal", "gagal", "GAGAL - pelanggan tdk ada"]}
    r["status_order"] = [rng.choice(alias[s]) for s in r["status_order"]]
    # kode motor & kurir id tidak rapi
    r["kode_motor"] = [rng.choice([s, s.lower(), s + " ", s[0] + " " + s[1:]]) if rng.random() < 0.06 else s for s in r["kode_motor"]]
    r["kurir_id"] = [s.lower().replace("k", "k-") if rng.random() < 0.03 else s for s in r["kurir_id"]]
    # nominal rupiah sebagai teks pada 15% baris
    t = rng.random(n) < 0.15
    for c in ["ongkir_rp", "pembanding_rp"]:
        r[c] = r[c].astype(object)
        r.loc[t, c] = r.loc[t, c].map(_fmt_rp)
    # klaster tidak ada pada log mentah (harus diturunkan dari master armada)
    r["klaster_motor"] = r["klaster_motor"].where(rng.random(n) > 0.10, None)
    # duplikat persis (2%)
    dup = r.sample(int(n * 0.02), random_state=7)
    return pd.concat([r, dup], ignore_index=True).sample(frac=1, random_state=3).reset_index(drop=True)


def main():
    raw, truth = generate()
    raw.to_csv(RAW / "order_log_sintetis_raw.csv", index=False)
    truth.to_csv(RAW / "order_log_sintetis_kebenaran_uji.csv", index=False)
    print("[sintetis] raw", raw.shape, "| kebenaran_uji", truth.shape)


if __name__ == "__main__":
    main()
