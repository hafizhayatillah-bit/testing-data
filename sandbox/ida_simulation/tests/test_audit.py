"""FASE 2 - Audit klaim Ida. DATA SINTETIS / ASUMSI, bukan data lapangan.

Nilai "expected" = HIPOTESIS dari teks notebook/laporan Ida, bukan kebenaran.
Bagian A memakai costmodel.py (ditulis ulang independen, TIDAK mengimpor kode Ida).
Bagian B memakai output Fase 1 (datasets/phase1/run1) + file kiriman Ida (read-only).
Jalankan:  .venv/Scripts/python -m pytest tests/test_audit.py -v
"""
import json
import math
import re

import numpy as np
import pandas as pd
import pytest

import costmodel as cm
from conftest import RUN1, ORIG, V1, WB22, HERE, need

P = cm.IDA


# =============================================================== A. COST MODEL (independen)
def test_A01_rumus_upah_di_grid_ida(catat):
    g = pd.read_csv(need(RUN1 / "data/clean/grid_jarak_hasil.csv"))
    sel = float((g["upah_penuh"] - (3500 + 1500 * g["jarak_rute_km"])).abs().max())
    catat("A01", "upah kurir = 3.500 + 1.500 x jarak_km (grid_jarak_hasil.csv)", "selisih 0", f"selisih maks Rp{sel:.4f}",
          "PASS" if sel < 1e-6 else "FAIL")


def test_A02_biaya_motor_tidak_masuk_kantong_2m(catat):
    g = pd.read_csv(need(RUN1 / "data/clean/grid_jarak_hasil.csv"))
    exp = g["ongkir_disarankan"] * cm.f_ongkir(P) - g["upah_efektif"] - cm.biaya_cabang(P)
    sel = float((g["kantong_2m"] - exp).abs().max())
    # bensin naik 50% tidak boleh mengubah kantong 2M (biaya motor ditanggung kurir)
    k0 = cm.titik(3.0, P)["kantong_2m"]
    k1 = cm.titik(3.0, P.with_(harga_bensin=15000))["kantong_2m"]
    ok = sel <= 1.0 and abs(k0 - k1) < 1e-9          # toleransi 1 rupiah (CSV Ida dibulatkan 2 desimal)
    catat("A02", "biaya motor ditanggung kurir; kantong 2M = ongkir diterima - bayar kurir - overhead/throughput",
          "identitas berlaku; bensin tak mengubah kantong 2M",
          f"selisih identitas maks Rp{sel:.4f}; kantong 3 km bensin 10rb={k0:.2f} vs 15rb={k1:.2f}", "PASS" if ok else "FAIL",
          "kantong 2M memakai ongkir x 0,97 (order gagal 3% tidak ditagih) dan upah x 0,985 (gagal dibayar 50%)")


def test_A03_q1_titik_rugi_klaster_A(catat):
    tr = cm.titik_rugi(P, "A")
    catat("A03", "Q1: titik mulai rugi klaster A", 2.25, tr["mulai"], "PASS" if tr["mulai"] == 2.25 else "FAIL",
          f"grid 0,25 km; {tr['n_titik']}/{tr['n_grid']} titik rugi")


def test_A04_q1_rugi_sampai_10km(catat):
    tr = cm.titik_rugi(P, "A")
    catat("A04", "Q1: rugi terus sampai 10 km", "rugi di semua titik 2,25-10 km",
          f"akhir={tr['akhir']} km, rugi terus={tr['rugi_terus_sampai_akhir']}",
          "PASS" if tr["akhir"] == 10.0 and tr["rugi_terus_sampai_akhir"] else "FAIL")


def test_A05_q1_tarif_lama(catat):
    tr = cm.titik_rugi(P, "A", kolom="kantong_2m_lama")
    catat("A05", "Q1: tarif lama (Rp3.000/km, min Rp8.000) hanya rugi di 2,50-2,75 km", [2.5, 2.75],
          [tr["mulai"], tr["akhir"]], "PASS" if (tr["mulai"], tr["akhir"]) == (2.5, 2.75) else "FAIL")


def test_A06_q2_penghasilan_tertinggi_34persen(catat):
    rows = cm.q2(P)
    best = max(rows, key=lambda r: r["persen_umk"])
    dasar = next(r for r in rows if r["skenario"] == "Dasar" and r["klaster"] == "A")
    ok = abs(best["persen_umk"] - 0.34) <= 0.01
    catat("A06", "Q2: penghasilan kurir paling tinggi ~34% target UMK (Rp5.938.885)", "34% (+/-1 poin)",
          f"{best['persen_umk']:.2%} ({best['skenario']} {best['klaster']}); Dasar A {dasar['persen_umk']:.2%}",
          "PASS" if ok else "FAIL",
          f"Optimis: throughput 18 tapi kapasitas waktu {best['kapasitas']}/hari -> laporan Ida menulis '18 antaran/hari' (salah label)")


def test_A07_q2_kapasitas_vs_kebutuhan(catat):
    k = cm.kebutuhan_target(P, 2.7, "A")
    ok = k["kapasitas"] == 15 and k["antaran_dibutuhkan"] == 50
    catat("A07", "Q2: kapasitas ~15 antaran/hari vs ~50 yang dibutuhkan", "15 vs 50",
          f"{k['kapasitas']} vs {k['antaran_dibutuhkan']}", "PASS" if ok else "FAIL",
          f"ongkir agar kurir capai UMK di 2,7 km = Rp{k['ongkir_target']:,.0f} vs pembanding Rp{k['pembanding']:,.0f}")


def test_A08_q4_cover_ge3_tetap_225(catat):
    q = cm.q4(P)
    sub = [r for r in q if r["d_cover"] >= 3]
    ok = len(q) == 25 and all(r["rugi_mulai"] == 2.25 for r in sub)
    catat("A08", "Q4: 25 kombinasi; bila tarif min mencakup >=3 km, titik rugi tetap 2,25 km", "15/15 sel = 2,25",
          f"{sum(r['rugi_mulai'] == 2.25 for r in sub)}/{len(sub)} sel = 2,25 (total {len(q)} kombinasi)", "PASS" if ok else "FAIL")


def test_A09_q4_cover_1_2_bergeser_575(catat):
    q = cm.q4(P)
    sub = [r for r in q if r["d_cover"] <= 2]
    vals = [r["rugi_mulai"] for r in sub if r["rugi_mulai"] is not None]
    ok = max(vals) == 5.75 and min(vals) >= 2.25
    catat("A09", "Q4: bila tarif min mencakup 1-2 km, titik rugi bergeser sampai 5,75 km", "maks 5,75",
          f"rentang {min(vals)}-{max(vals)} km", "PASS" if ok else "FAIL")


def test_A10_q4_dua_kombinasi_tidak_rugi(catat):
    q = cm.q4(P)
    nr = [(r["d_cover"], r["d_maks"]) for r in q if r["rugi_mulai"] is None]
    catat("A10", "Q4: 2 kombinasi tidak rugi sampai 10 km", 2, f"{len(nr)} {nr}", "PASS" if len(nr) == 2 else "FAIL",
          "keduanya d_maks=6 km (pembanding naik curam); tarif di atas d_maks diekstrapolasi tanpa batas Rp15.500")


def test_A11_q5_O0_rugi_60persen(catat):
    w = {r["opsi"]: r for r in cm.q5(P, metode="wakil")}
    s = {r["opsi"]: r for r in cm.q5(P, metode="seragam")}
    ok = abs(w["O0"]["porsi_order_2m_rugi"] - 0.60) <= 0.02
    catat("A11", "Q5: pada sebaran 40/40/20, O0 rugi untuk ~60% order", "60%",
          f"{w['O0']['porsi_order_2m_rugi']:.1%} (jarak wakil 1/3/5,5 km); {s['O0']['porsi_order_2m_rugi']:.1%} bila jarak merata di bucket",
          "PASS" if ok else "FAIL",
          "angka 60% muncul dari penyederhanaan 1 jarak wakil per bucket; order 2,0-2,25 km sebenarnya tidak rugi")


def test_A12_q5_O2_melayani_40persen(catat):
    w = {r["opsi"]: r for r in cm.q5(P)}
    ok = abs(w["O2"]["order_terlayani"] - 0.40) < 1e-9
    catat("A12", "Q5: O2 (radius <=2 km) melayani ~40% order", "40%", f"{w['O2']['order_terlayani']:.0%}", "PASS" if ok else "FAIL")


def test_A13_parameter_sesuai_brief(catat):
    par = pd.read_csv(need(RUN1 / "data/raw/parameter_model_raw.csv")).set_index("parameter")["nilai_num"]
    exp = {"kecepatan_rata2_normal_km_jam": 20, "kecepatan_rata2_macet_km_jam": 12, "waktu_tetap_per_antaran_menit": 15,
           "bayar_order_gagal_fraksi": 0.5, "throughput_antaran_per_hari": 15, "tarif_per_km_2M_lama": 3000,
           "ongkir_minimum_2M_lama": 8000, "UMK Kabupaten Bekasi 2026": 5938885, "upah_dasar_per_antaran": 3500, "upah_per_km": 1500}
    beda = {k: (v, float(par.get(k, np.nan))) for k, v in exp.items() if not math.isclose(float(par.get(k, np.nan)), v)}
    catat("A13", "Parameter (kecepatan 20/12, waktu tetap 15, bayar gagal 50%, throughput 15, tarif lama 3.000/8.000, UMK)",
          "semua sama", beda or "semua sama", "PASS" if not beda else "FAIL")


def test_A14_q1_bila_ongkir_bisa_ditagih(catat):
    tr = cm.titik_rugi(P.with_(bulatkan_batas=True), "A")
    catat("A14", "(uji tambahan) Q1 tetap 2,25 km bila ongkir dibulatkan ke bawah ke kelipatan Rp500 (harga yang bisa ditagih)",
          2.25, tr["mulai"], "PASS" if tr["mulai"] == 2.25 else "FAIL",
          "Ida memakai batas pembanding tak dibulatkan (mis. Rp7.833,33) untuk angka utama; temuan E2 miliknya sendiri")


# =============================================================== B. KUALITAS DATA & MODEL
def _ols(y, X):
    X = np.column_stack([np.ones(len(y)), X])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    res = y - X @ beta
    s2 = res @ res / (len(y) - X.shape[1])
    se = np.sqrt(np.diag(s2 * np.linalg.inv(X.T @ X)))
    return beta, se


def test_B01_berat_tidak_berefek_di_V2(catat):
    b = pd.read_csv(need(RUN1 / "data/clean/order_log_bersih.csv"))
    b = b[~b["berat_estimasi"]]
    X = np.column_stack([b["berat_total_kg"], b["jarak_rute_km"], b["kondisi_lalu_lintas"].eq("Macet")])
    beta, se = _ols(b["waktu_per_antaran_menit"].to_numpy(), X.astype(float))
    t = beta[1] / se[1]
    catat("B01", "Kecurigaan: generator V2 tidak punya efek berat (koef waktu~berat ~ 0)", "|t| < 2",
          f"koef berat {beta[1]:+.4f} menit/kg (SE {se[1]:.4f}, t={t:.2f}), kontrol jarak & macet; n={len(b)}",
          "PASS" if abs(t) < 2 else "FAIL",
          "synth_orders.py:51 membuat `berat` tapi tidak dipakai di rumus waktu (baris 48-59) -> efek berat mustahil dipelajari")


def test_B02_berat_berefek_di_V1(catat):
    v1 = pd.read_csv(need(V1 / "dataset_pengiriman_2m_clean.csv"))
    beta, se = _ols(v1["waktu_tempuh_menit"].to_numpy(), v1[["berat_kg", "jarak_km", "is_rush_hour"]].to_numpy(float))
    catat("B02", "Pembanding V1: apakah V1 punya efek berat?", "koef > 0 bermakna",
          f"koef berat {beta[1]:+.4f} menit/kg (SE {se[1]:.4f}, t={beta[1] / se[1]:.1f}); n={len(v1)}",
          "PASS" if beta[1] / se[1] > 2 else "FAIL",
          "V1 & V2 punya mekanisme berat berbeda: model ETA dari V2 tidak bisa menangkap 'muatan bulk' yang jadi alasan proyek ETA di README V1")


def _eta_frame():
    f = pd.read_csv(need(RUN1 / "data/clean/dataset_fitur_target.csv"))
    d = pd.get_dummies(f, columns=["klaster_motor", "cabang_id"], dtype=float)
    feat = [c for c in d.columns if c not in ("order_id", "split", "waktu_per_antaran_menit", "gagal", "sumber_data")]
    return d, feat


def _eta_scores():
    from sklearn.ensemble import GradientBoostingRegressor
    from sklearn.linear_model import LinearRegression
    from sklearn.metrics import mean_absolute_error, r2_score
    d, feat = _eta_frame()
    tr, te = d[d.split == "train"], d[d.split == "test"]
    y = "waktu_per_antaran_menit"
    ev = lambda p: (r2_score(te[y], p), mean_absolute_error(te[y], p))  # noqa: E731
    v_tr, v_te = np.where(tr.is_macet == 1, 12, 20), np.where(te.is_macet == 1, 12, 20)
    out = {"baseline_rumus": ev(2 * te.jarak_rute_km / v_te * 60 + 15)}
    lr1 = LinearRegression().fit((tr.jarak_rute_km / v_tr).to_frame(), tr[y])
    out["baseline_kalibrasi"] = ev(lr1.predict((te.jarak_rute_km / v_te).to_frame()))
    out["linreg"] = ev(LinearRegression().fit(tr[feat], tr[y]).predict(te[feat]))
    out["gbr"] = ev(GradientBoostingRegressor(random_state=0).fit(tr[feat], tr[y]).predict(te[feat]))
    # plafon: ekspektasi bersyarat generator (synth_orders.py baris 48-59), tanpa tahu 'gagal'
    el = math.exp(0.15 ** 2 / 2)
    pg = 0.03 + 0.004 * np.clip(te.jarak_rute_km - 3, 0, None)
    out["plafon_generator"] = ev(5 + 2 * te.jarak_rute_km * 60 / v_te * el + 6.5 + 5 * pg)
    return {k: (round(a, 4), round(b, 3)) for k, (a, b) in out.items()}


@pytest.fixture(scope="module")
def eta():
    return _eta_scores()


def test_B03_ml_vs_baseline_rumus(eta, catat):
    g, b = eta["gbr"], eta["baseline_rumus"]
    ok = g[0] - b[0] >= 0.02 or g[1] <= 0.95 * b[1]
    catat("B03", "ETA: ML mengalahkan baseline jarak/kecepatan (rumus parameter: 2d/v x 60 + 15)", "dR2 >= 0,02 atau MAE turun >= 5%",
          f"GBR R2={g[0]} MAE={g[1]} | baseline R2={b[0]} MAE={b[1]}", "PASS" if ok else "FAIL",
          "split berbasis waktu (kolom split Ida, 80/20; train maks < test min)")


def test_B04_ml_vs_baseline_kalibrasi(eta, catat):
    g, b = eta["gbr"], eta["baseline_kalibrasi"]
    ok = g[0] - b[0] >= 0.02 or g[1] <= 0.95 * b[1]
    catat("B04", "ETA: ML mengalahkan baseline jarak/kecepatan yang dikalibrasi (regresi 1 fitur)", "dR2 >= 0,02 atau MAE turun >= 5%",
          f"GBR R2={g[0]} MAE={g[1]} | LinReg semua fitur R2={eta['linreg'][0]} | baseline kalibrasi R2={b[0]} MAE={b[1]}",
          "PASS" if ok else "FAIL", "keunggulan ML atas rumus hanya berasal dari kalibrasi konstanta, bukan pola baru")


def test_B05_eta_sirkular_mentok_plafon(eta, catat):
    g, c = eta["gbr"], eta["plafon_generator"]
    gap = c[0] - g[0]
    catat("B05", "ETA tidak sirkular (skor bukan sekadar membalik rumus generator)", "ML jauh dari plafon derau generator",
          f"GBR R2={g[0]} vs plafon generator R2={c[0]} (selisih {gap:.4f}); MAE {g[1]} vs {c[1]}",
          "FAIL" if gap < 0.01 else "PASS",
          "target = fungsi jarak, macet + derau U(2,8)+U(3,10)+lognormal(0,0.15); skor R2~0,91 adalah batas derau, bukan kualitas model. "
          "Ida sendiri mengakui ini di docs/03 ('mudah ditebak')")


def test_B06_eta_data_model_target_tiba(catat):
    from sklearn.ensemble import GradientBoostingRegressor
    from sklearn.linear_model import LinearRegression
    from sklearn.metrics import r2_score
    mo = pd.read_csv(need(ORIG / "data/model/dataset_model_order.csv"))
    pre = json.loads((ORIG / "data/model/preprocessor.json").read_text(encoding="utf-8"))
    n_nan = int(mo["berat_total_kg"].isna().sum())
    mo["berat_total_kg"] = mo["berat_total_kg"].fillna(pre["median_berat"])   # sesuai preprocessor.json Ida
    v = np.where(mo.is_macet == 1, 12, 20)
    mo["jv"] = mo.jarak_rute_km / v
    feat = ["jarak_rute_km", "berat_total_kg", "jumlah_item", "jam", "hari_minggu", "is_macet", "jarak_log1p", "jam_sin", "jam_cos",
            "is_jam_puncak", "is_sabtu", "kelas_jarak"]
    tr, te = mo[mo.split == "train"], mo[mo.split == "test"]
    y = "target_eta_menit"
    r_b = r2_score(te[y], LinearRegression().fit(tr[["jv"]], tr[y]).predict(te[["jv"]]))
    r_g = r2_score(te[y], GradientBoostingRegressor(random_state=0).fit(tr[feat], tr[y]).predict(te[feat]))
    r_c = r2_score(te[y], 5 + te.jarak_rute_km * 60 / v[mo.split == "test"] * math.exp(0.15 ** 2 / 2))
    catat("B06", "ETA (data/model, target = tiba - ditugaskan, split 70/30): ML > baseline kalibrasi", "dR2 >= 0,02",
          f"GBR R2={r_g:.4f} | baseline jarak/v R2={r_b:.4f} | plafon generator R2={r_c:.4f}",
          "PASS" if r_g - r_b >= 0.02 else "FAIL",
          f"{n_nan} berat NaN di file model diisi median {pre['median_berat']} dari preprocessor.json; jumlah_item tidak ada di generator")


def test_B07_cek_C_tautologis(catat):
    s05 = (need(ORIG / "src/s05_cek_akurasi.py")).read_text(encoding="utf-8")
    syn = (ORIG / "src/synth_orders.py").read_text(encoding="utf-8")
    s02 = (ORIG / "src/s02_assessing_cleaning.py").read_text(encoding="utf-8")
    bukti = {
        "s05 membandingkan dgn order_log_sintetis_kebenaran_uji.csv": "order_log_sintetis_kebenaran_uji.csv" in s05,
        "synth_orders menulis file itu dari `truth` generator yang sama": bool(re.search(r"truth\.to_csv\(RAW / \"order_log_sintetis_kebenaran_uji\.csv\"", syn)),
        "kerusakan disuntik oleh inject_mess() di file yang sama": "def inject_mess" in syn,
        "jarak dipulihkan dari upah_total yang dihitung dari jarak asli": "d_upah = ((df[\"upah_total_rp\"]" in s02 and "upah = (P[\"upah_dasar_per_antaran\"] + P[\"upah_per_km\"] * d)" in syn,
    }
    tautologis = all(bukti.values())
    catat("B07", "Cek C (akurasi cleaning 100%) adalah bukti independen", "kunci jawaban dari sumber independen",
          "kunci = output generator yang sama; " + "; ".join(k for k, v in bukti.items() if v),
          "FAIL" if tautologis else "PASS",
          "s05_cek_akurasi.py:103-104; synth_orders.py:86,131; s02:88. 100% hanya membuktikan aturan cleaning = kebalikan inject_mess. "
          "Ida mengakui ini di docs/04 ('Peringatan jujur')")


def test_B08_positif_gagal_test(catat):
    f = pd.read_csv(need(RUN1 / "data/clean/dataset_fitur_target.csv"))
    pos = f.groupby("split")["gagal"].sum().to_dict()
    man = json.loads((ORIG / "data/model/manifest_split.json").read_text(encoding="utf-8"))["acuan_baseline"]
    ok = pos.get("test", 0) >= 30 and man["gagal_positif_test"] >= 30
    catat("B08", "Kelas positif `gagal` di test >= 30 (metrik klasifikasi stabil)", ">= 30",
          f"dataset_fitur_target: train={pos.get('train')} test={pos.get('test')}; data/model: train={man['gagal_positif_train']} test={man['gagal_positif_test']}",
          "PASS" if ok else "FAIL", "TIDAK STABIL: recall/precision bergeser 3-7 poin per 1 order salah prediksi")


def test_B09_tidak_ada_bocoran_keuangan(catat):
    f = pd.read_csv(need(RUN1 / "data/clean/dataset_fitur_target.csv"))
    mo = pd.read_csv(need(ORIG / "data/model/dataset_model_order.csv"))
    pola = re.compile(r"(untung|kantong|ongkir|upah|bayar|biaya|pembanding|energi)")
    bocor = [c for c in list(f.columns) + list(mo.columns) if pola.search(c)]
    catat("B09", "Tidak ada kolom turunan finansial di file fitur", "0 kolom", bocor or "0 kolom", "PASS" if not bocor else "FAIL",
          "`gagal` ada di dataset_fitur_target sebagai TARGET klasifikasi (docs/03), bukan fitur ETA -> aman bila dipakai sesuai panduan; "
          "tapi file tidak memisahkan fitur vs target secara eksplisit")


def test_B10_flag_waktu_aneh_sebelum_split(catat):
    b = pd.read_csv(need(RUN1 / "data/clean/order_log_bersih.csv"))
    f = pd.read_csv(RUN1 / "data/clean/dataset_fitur_target.csv")
    n_flag = int(b["flag_waktu_aneh"].sum())
    m = f.merge(b[["order_id", "ditugaskan_at"]], on="order_id")
    t = pd.to_datetime(m["ditugaskan_at"])
    berbasis_waktu = t[m.split == "train"].max() < t[m.split == "test"].min()
    catat("B10", "Baris flag_waktu_aneh yang dibuang sebelum split tidak mengubah distribusi test", "0 baris terbuang",
          f"{n_flag} baris dibuang; split berbasis waktu={berbasis_waktu} ({(m.split == 'train').sum()}/{(m.split == 'test').sum()})",
          "PASS" if n_flag == 0 and berbasis_waktu else "FAIL",
          "s02:146 filter dilakukan SEBELUM kuantil waktu (s02:149); pada log asli ini akan menggeser batas split")


WP45 = ["order_id", "branch_id", "distance_km", "weight_kg", "item_count", "hour", "dow", "motor_cluster", "prep_minutes",
        "travel_minutes", "total_minutes", "source", "split"]
PADANAN = {  # nama spec -> kemungkinan nama di file Ida (padanan semantik, hasil membaca kamus_data)
    "order_id": ["order_id"], "branch_id": ["cabang_id"], "distance_km": ["jarak_rute_km"], "weight_kg": ["berat_total_kg"],
    "item_count": ["jumlah_item"], "hour": ["jam"], "dow": ["hari_minggu"], "motor_cluster": ["klaster_motor"],
    "prep_minutes": [], "travel_minutes": ["waktu_tempuh_satu_arah_menit", "target_eta_menit"],
    "total_minutes": ["waktu_per_antaran_menit"], "source": ["sumber_data"], "split": ["split"],
}


def wp45_tabel(cols):
    rows = []
    for s in WP45:
        if s in cols:
            rows.append((s, "ADA", s))
        else:
            alt = [c for c in PADANAN[s] if c in cols]
            rows.append((s, "BEDA NAMA" if alt else "HILANG", alt[0] if alt else "-"))
    return rows


def test_B11_kolom_wp45(catat):
    f = pd.read_csv(need(RUN1 / "data/clean/dataset_fitur_target.csv"), nrows=1)
    mo = pd.read_csv(need(ORIG / "data/model/dataset_model_order.csv"), nrows=1)
    t1, t2 = wp45_tabel(list(f.columns)), wp45_tabel(list(mo.columns))
    out = HERE / "datasets" / "phase2"
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([dict(spec=a, fitur_target_status=b, fitur_target_kolom=c, model_order_status=e, model_order_kolom=g)
                  for (a, b, c), (_, e, g) in zip(t1, t2)]).to_csv(out / "wp45_kolom.csv", index=False)
    ada = sum(s == "ADA" for _, s, _ in t1)
    hilang = [a for a, s, _ in t1 if s == "HILANG"]
    catat("B11", "dataset_fitur_target.csv sesuai spec WP-45 (13 kolom)", "13/13 ADA",
          f"{ada} ADA persis, {sum(s == 'BEDA NAMA' for _, s, _ in t1)} beda nama, hilang: {hilang}",
          "PASS" if ada == len(WP45) else "FAIL", "tabel lengkap: datasets/phase2/wp45_kolom.csv")


def test_B12_v1_berlabel_sintetis(catat):
    v1 = pd.read_csv(need(V1 / "dataset_pengiriman_2m_clean.csv"), nrows=5)
    lab = [c for c in v1.columns if "sumber" in c.lower() or "sintetis" in c.lower() or "source" in c.lower()]
    catat("B12", "V1 punya kolom sumber_data / label sintetis", "ada", lab or f"tidak ada; kolom={list(v1.columns)}",
          "PASS" if lab else "FAIL", "nama file V1 juga tidak mengandung 'sintetis' (melanggar aturan label di README V2)")


def test_B13_workbook_v2_vs_v22(catat):
    from openpyxl import load_workbook
    need(WB22)

    def params(p):
        wb = load_workbook(p, data_only=True)
        ws = wb["Parameter"]
        d = {str(ws.cell(r, 1).value).strip(): ws.cell(r, 2).value for r in range(3, ws.max_row + 1)
             if ws.cell(r, 1).value is not None and ws.cell(r, 2).value is not None}
        return wb.sheetnames, d
    s2, p2 = params(ORIG / "data/raw/Draft_DS_Kurir_v2.xlsx")
    s22, p22 = params(WB22)
    berubah = {k: (p2[k], p22[k]) for k in set(p2) & set(p22) if p2[k] != p22[k]}
    baru = {k: p22[k] for k in set(p22) - set(p2)}
    hilang = sorted(set(p2) - set(p22))
    out = HERE / "datasets" / "phase2"
    out.mkdir(parents=True, exist_ok=True)
    (out / "workbook_v2_vs_v22.json").write_text(json.dumps(dict(sheet_baru=sorted(set(s22) - set(s2)), param_baru=baru,
                                                                 param_berubah=berubah, param_hilang=hilang), indent=1, default=str), encoding="utf-8")
    catat("B13", "Pipeline memakai workbook terbaru (v2.2)", "config.XLSX = v2.2",
          f"pipeline membaca v2 (config.py:10). v2.2: +{len(baru)} parameter baru {sorted(baru)}, {len(berubah)} berubah, "
          f"sheet baru {sorted(set(s22) - set(s2))}", "FAIL",
          "parameter bersama identik -> angka Q1-Q6 tidak berubah; tapi T10_BEP_Basket (margin barang) & jarak_antar_drop_batch_km=1 "
          "(Q6 Ida memakai detour 0,5 km) tidak dipakai")


def test_B14_data_model_bisa_direproduksi(catat):
    ph = json.loads(need(HERE / "datasets/phase1/phase1_result.json").read_text(encoding="utf-8"))
    tidak = [x["file"] for x in ph["run1_vs_kiriman_ida_isi"] if x["status"].startswith("TIDAK DIHASILKAN")]
    catat("B14", "Semua file data kiriman dihasilkan ulang oleh run_all.py", "0 file yatim",
          f"{len(tidak)} file tanpa kode pembuat: {tidak}", "PASS" if not tidak else "FAIL",
          "data/model/* (split 70/30, jumlah_item, target_eta) tidak punya skrip; split beda dari dataset_fitur_target (80/20)")


def test_B15_waktu_tetap_generator_vs_model(catat):
    syn = need(ORIG / "src/synth_orders.py").read_text(encoding="utf-8")
    dipakai = len(re.findall(r"\bfixed\b", syn))
    catat("B15", "Log sintetis memakai parameter waktu_tetap_per_antaran_menit=15 dari model", "waktu non-perjalanan rata2 15 menit",
          f"variabel `fixed` dibuat tapi muncul {dipakai}x (tidak dipakai); waktu non-perjalanan = U(2,8)+U(3,10) = 11,5 menit (gagal: 16,5)",
          "PASS" if dipakai > 1 else "FAIL", "synth_orders.py:50 vs 55-58; kapasitas di log sintetis tidak konsisten dgn model biaya")


def test_B16_klaim_readme_identik_dua_run(catat):
    ph = json.loads(need(HERE / "datasets/phase1/phase1_result.json").read_text(encoding="utf-8"))
    same = all(x["sama"] for x in ph["run1_vs_run2"])
    ak = next(x for x in ph["run1_vs_kiriman_ida_isi"] if x["file"].endswith("angka_kunci.json"))
    catat("B16", "README: dua kali jalan dari nol, hasil identik; angka_kunci.json sama dengan kiriman", "identik",
          f"run1 vs run2 {sum(x['sama'] for x in ph['run1_vs_run2'])}/{len(ph['run1_vs_run2'])} byte-identik; angka_kunci: {ak['status']}",
          "PASS" if same and ak["status"].startswith("IDENTIK") else "FAIL")


def test_B17_notebook_tereksekusi(catat):
    nb = json.loads(need(ORIG / "notebooks/wrangling_dan_analisis.ipynb").read_text(encoding="utf-8"))
    code = [c for c in nb["cells"] if c["cell_type"] == "code"]
    err = [o.get("ename", "") + ": " + o.get("evalue", "")[:60] for c in code for o in c.get("outputs", []) if o.get("output_type") == "error"]
    catat("B17", "Notebook kiriman sudah dijalankan sukses (output tersimpan)", "0 error",
          f"{len(code)} sel kode, {len(err)} error tersimpan: {err[:1]}", "PASS" if not err else "FAIL",
          "sel pertama gagal 'No module named src' di Colab; 26 sel 'aborted'. run_all.py lokal tetap jalan")
