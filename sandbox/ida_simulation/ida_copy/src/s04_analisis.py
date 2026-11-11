"""TAHAP 4-5 - ANALISIS untuk menjawab 5 pertanyaan bisnis + grafik + angka kunci.

Dasar: model biaya (model_biaya.py) yang sudah direkonsiliasi dengan Excel (s05).
Catatan: ini analisis SKENARIO berbasis asumsi tim, bukan hasil data transaksi asli.
"""
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .config import RAW, CLEAN, OUT_T, OUT_G
from .model_biaya import load_params, load_motor, grid, hitung, pembanding, upah_maks_amplop

C = {"merah": "#C0392B", "biru": "#1F5FA8", "hijau": "#2E8B57", "abu": "#7F8C8D", "oranye": "#E08A1E", "ungu": "#7D5BA6"}
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
                     "grid.alpha": .25, "figure.dpi": 130})
BUCKET = {"d": [1.0, 3.0, 5.5], "nama": ["0-2 km", "2-4 km", ">4 km"]}
SEBARAN = {"Dekat": [.6, .3, .1], "Dasar": [.4, .4, .2], "Jauh": [.2, .4, .4]}


def rupiah(x):
    return f"Rp{x:,.0f}".replace(",", ".")


def run():
    P, M = load_params(), load_motor()
    K = {}
    # ---------------- grid dasar
    gA, gB = grid(P, M, "A"), grid(P, M, "B")
    for g in (gA, gB):
        g["ongkir_disarankan_bayar"] = np.minimum(g["ongkir_minimum_2m"], np.floor(g["batas_ongkir"] / 500) * 500)
        f_ong = 1 - P["tingkat_order_gagal"] * (1 - P["ongkir_ditagih_saat_gagal_fraksi"])
        g["kantong_2m_bayar"] = g["ongkir_disarankan_bayar"] * f_ong - g["biaya_2m_sebelum_ongkir"]
    pd.concat([gA, gB]).round(2).to_csv(CLEAN / "grid_jarak_hasil.csv", index=False)

    # ---------------- Q1: di jarak berapa 2M rugi?
    rugi = gA[gA["kantong_2m"] < -1e-9]["jarak_rute_km"]
    rugi_lama = gA[gA["kantong_2m_lama"] < -1e-9]["jarak_rute_km"]
    K["q1_rugi_mulai_km"] = float(rugi.min())
    K["q1_titik_rugi_skema_baru"] = int(len(rugi))
    K["q1_rugi_lama_km"] = [float(rugi_lama.min()), float(rugi_lama.max())]
    for d in (3, 5, 8, 10):
        r = gA[gA["jarak_rute_km"] == d].iloc[0]
        K[f"q1_kantong_{d}km"] = round(float(r["kantong_2m"]), 0)
    amp = []
    for d in (1, 2, 3, 4, 5, 6, 8, 10):
        r = hitung(float(d), "A", P, M)
        um = upah_maks_amplop(d, P)
        rr = hitung(float(d), "A", P, M, upah_override=um)
        amp.append(dict(jarak_km=d, pembanding_rp=round(r["pembanding"]), upah_skema_sekarang=r["upah_penuh"],
                        upah_maks_agar_2m_tidak_rugi=round(um), selisih=round(um - r["upah_penuh"]),
                        biaya_motor_kurir=round(r["biaya_motor_per_antaran"]),
                        untung_kurir_di_upah_maks=round(rr["untung_kurir_per_antaran"]),
                        untung_kurir_per_jam_di_upah_maks=round(rr["untung_kurir_per_jam"])))
    amp = pd.DataFrame(amp)
    amp.to_csv(OUT_T / "q1_amplop_upah_per_jarak.csv", index=False)

    # G1/G2
    fig, ax = plt.subplots(1, 2, figsize=(11, 4))
    ax[0].plot(gA["jarak_rute_km"], gA["kantong_2m"], color=C["merah"], lw=2, label="Skema baru (ongkir <= pembanding)")
    ax[0].plot(gA["jarak_rute_km"], gA["kantong_2m_lama"], color=C["abu"], lw=1.5, ls="--", label="Tarif lama (Rp3.000/km, min Rp8.000)")
    ax[0].axhline(0, color="k", lw=.8)
    ax[0].fill_between(gA["jarak_rute_km"], gA["kantong_2m"], 0, where=gA["kantong_2m"] < 0, color=C["merah"], alpha=.12)
    ax[0].axvline(K["q1_rugi_mulai_km"], color=C["merah"], ls=":", lw=1)
    ax[0].annotate(f"2M mulai rugi\n{K['q1_rugi_mulai_km']:.2f} km", (K["q1_rugi_mulai_km"], 0), (3.3, 2200), arrowprops=dict(arrowstyle="->"), color=C["merah"])
    ax[0].set(title="Kantong 2M per antaran vs jarak (klaster A)", xlabel="Jarak rute satu arah (km)", ylabel="Rp per antaran")
    ax[0].legend(fontsize=8, loc="lower left")
    ax[1].plot(gA["jarak_rute_km"], gA["ongkir_minimum_2m"], color=C["merah"], lw=2, label="Ongkir minimum agar 2M tidak rugi")
    ax[1].plot(gA["jarak_rute_km"], gA["pembanding"], color=C["biru"], lw=2, label="Pembanding GoSend (turunan data PIC)")
    ax[1].plot(gA["jarak_rute_km"], gA["ongkir_lama"], color=C["abu"], ls="--", label="Ongkir tarif lama")
    ax[1].set(title="Ongkir minimum vs pembanding", xlabel="Jarak rute satu arah (km)", ylabel="Rp")
    ax[1].legend(fontsize=8)
    fig.tight_layout(); fig.savefig(OUT_G / "g1_kantong_2m_dan_ongkir_vs_jarak.png"); plt.close(fig)

    # ---------------- Q2: penghasilan kurir vs UMK
    rows = []
    kasus = {"Optimis": dict(harga_bensin=9000, pengali_kmpl=1.1, throughput=18, d=2.05, macet=False),
             "Dasar": dict(harga_bensin=10000, pengali_kmpl=1.0, throughput=15, d=2.7, macet=False),
             "Pesimis": dict(harga_bensin=11000, pengali_kmpl=0.9, throughput=12, d=3.6, macet=True)}
    for nama, kw in kasus.items():
        for kl in "AB":
            d = kw.pop("d") if "d" in kw else dasar_d
            dasar_d = d
            r = hitung(d, kl, P, M, **kw)
            rows.append(dict(skenario=nama, klaster=kl, jarak_km=d, untung_per_antaran=r["untung_kurir_per_antaran"],
                             antaran_per_hari=r["antaran_hari_realistis"], penghasilan_bulan=r["penghasilan_bulan"],
                             persen_umk=r["penghasilan_bulan"] / r["target_bersih_bulan"], untung_per_jam=r["untung_kurir_per_jam"]))
            kw["d"] = d
    # upah maksimum yang masih dalam batas pembanding (kapasitas penuh)
    for kl in "AB":
        um = upah_maks_amplop(2.7, P)
        r = hitung(2.7, kl, P, M, upah_override=um)
        rows.append(dict(skenario="Upah maks (2M tidak rugi)", klaster=kl, jarak_km=2.7, untung_per_antaran=r["untung_kurir_per_antaran"],
                         antaran_per_hari=r["antaran_hari_realistis"], penghasilan_bulan=r["penghasilan_bulan"],
                         persen_umk=r["penghasilan_bulan"] / r["target_bersih_bulan"], untung_per_jam=r["untung_kurir_per_jam"]))
    q2 = pd.DataFrame(rows)
    q2.to_csv(OUT_T / "q2_penghasilan_kurir_vs_umk.csv", index=False)
    dasarA = q2[(q2.skenario == "Dasar") & (q2.klaster == "A")].iloc[0]
    K["q2_dasarA_persen_umk"] = round(float(dasarA.persen_umk), 4)
    K["q2_dasarA_penghasilan"] = round(float(dasarA.penghasilan_bulan))
    K["q2_dasarA_per_jam"] = round(float(dasarA.untung_per_jam))
    K["q2_dasarB_persen_umk"] = round(float(q2[(q2.skenario == "Dasar") & (q2.klaster == "B")].persen_umk.iloc[0]), 4)
    K["q2_target_per_jam"] = round(P["UMK_DIPAKAI"] / P["hari_kerja_per_bulan"] / P["jam_kerja_per_hari"])
    K["q2_antaran_dibutuhkan_dasarA"] = int(np.ceil(P["UMK_DIPAKAI"] / P["hari_kerja_per_bulan"] / dasarA.untung_per_antaran))
    K["q2_kapasitas_per_hari"] = int(hitung(2.7, "A", P, M)["kapasitas_antaran_hari"])
    K["q2_pesimis_A_persen_umk"] = round(float(q2[(q2.skenario == "Pesimis") & (q2.klaster == "A")].persen_umk.iloc[0]), 4)
    K["q2_optimis_A_persen_umk"] = round(float(q2[(q2.skenario == "Optimis") & (q2.klaster == "A")].persen_umk.iloc[0]), 4)
    K["q2_upahmaks_A_persen_umk"] = round(float(q2[(q2.skenario.str.startswith("Upah maks")) & (q2.klaster == "A")].persen_umk.iloc[0]), 4)
    # kebutuhan ongkir bila ingin capai UMK pada jarak rata-rata 2,7 km, kapasitas waktu
    r27 = hitung(2.7, "A", P, M)
    f_up = 1 - P["tingkat_order_gagal"] * (1 - P["bayar_order_gagal_fraksi"])
    f_og = 1 - P["tingkat_order_gagal"] * (1 - P["ongkir_ditagih_saat_gagal_fraksi"])
    upah_t = (P["UMK_DIPAKAI"] / P["hari_kerja_per_bulan"] / r27["kapasitas_antaran_hari"] + r27["biaya_motor_per_antaran"]) / f_up
    ong_t = (upah_t * f_up + r27["biaya_cabang_per_antaran"]) / f_og
    K["q2_upah_target_2_7km"] = round(upah_t)
    K["q2_ongkir_target_2_7km"] = round(ong_t)
    K["q2_pembanding_2_7km"] = round(r27["pembanding"])
    K["q2_gap_per_order"] = round(ong_t - r27["pembanding"])
    K["q2_gap_per_kurir_bulan"] = round((ong_t - r27["pembanding"]) * r27["kapasitas_antaran_hari"] * P["hari_kerja_per_bulan"])

    fig, ax = plt.subplots(figsize=(8.5, 4))
    lab = [f"{r.skenario}\n(klaster {r.klaster})" for r in q2.itertuples()]
    col = [C["biru"] if r.klaster == "A" else C["ungu"] for r in q2.itertuples()]
    ax.bar(range(len(q2)), q2["persen_umk"] * 100, color=col)
    ax.axhline(100, color=C["merah"], ls="--"); ax.text(len(q2) - .5, 102, "target = 100% UMK", ha="right", color=C["merah"], fontsize=8)
    for i, v in enumerate(q2["persen_umk"] * 100): ax.text(i, v + 1.5, f"{v:.0f}%", ha="center", fontsize=8)
    ax.set_xticks(range(len(q2))); ax.set_xticklabels(lab, fontsize=7)
    ax.set(ylim=(0, 115), ylabel="% dari target penghasilan bersih (UMK Kab. Bekasi)", title="Penghasilan bersih kurir per bulan vs target UMK")
    fig.tight_layout(); fig.savefig(OUT_G / "g3_penghasilan_kurir_vs_umk.png"); plt.close(fig)

    # ---------------- Q3: sensitivitas (tornado dari Excel T6, divalidasi di s05)
    tor = pd.read_csv(RAW / "tornado_excel_raw.csv")
    tor.columns = ["variabel", "d_ongkir_minus", "d_ongkir_plus", "swing_ongkir", "d_hasil_minus", "d_hasil_plus", "swing_hasil"]
    tor.to_csv(OUT_T / "q3_tornado.csv", index=False)
    fig, ax = plt.subplots(1, 2, figsize=(11, 3.8))
    t1 = tor.sort_values("swing_ongkir"); t2 = tor.sort_values("swing_hasil")
    for a, t, m, p_, ttl in ((ax[0], t1, "d_ongkir_minus", "d_ongkir_plus", "Perubahan ongkir minimum (Rp)"),
                             (ax[1], t2, "d_hasil_minus", "d_hasil_plus", "Perubahan penghasilan kurir/bulan (Rp)")):
        a.barh(t["variabel"], t[m], color=C["biru"], label="variabel turun / skenario Dekat")
        a.barh(t["variabel"], t[p_], color=C["oranye"], label="variabel naik / skenario Jauh")
        a.axvline(0, color="k", lw=.8); a.set_title(ttl, fontsize=10); a.tick_params(axis="y", labelsize=8)
    ax[0].legend(fontsize=7, loc="lower right")
    fig.tight_layout(); fig.savefig(OUT_G / "g4_tornado_sensitivitas.png"); plt.close(fig)
    K["q3_top_ongkir"] = t1["variabel"].iloc[-1]; K["q3_top_hasil"] = t2["variabel"].iloc[-1]

    # ---------------- Q4: seberapa kokoh terhadap asumsi pembanding?
    covers, dmaxs = [1, 2, 3, 4, 5], [6, 8, 10, 12, 15]
    rob = pd.DataFrame(index=covers, columns=dmaxs, dtype=object)
    robnum = np.full((len(covers), len(dmaxs)), np.nan)
    for i, cv in enumerate(covers):
        for j, dm in enumerate(dmaxs):
            g = grid(P, M, "A", cover=cv, dmax=dm)
            neg = g[g["kantong_2m"] < -1e-9]["jarak_rute_km"]
            robnum[i, j] = neg.min() if len(neg) else np.nan
            rob.loc[cv, dm] = f"{neg.min():.2f}" if len(neg) else ">10"
    rob.index.name = "jarak_tercakup_tarif_min_km"; rob.columns.name = "jarak_pada_harga_maks_km"
    rob.to_csv(OUT_T / "q4_robustness_asumsi_pembanding.csv")
    K["q4_rugi_range"] = [float(np.nanmin(robnum)), float(np.nanmax(robnum))]
    K["q4_n_tidak_rugi"] = int(np.isnan(robnum).sum())
    fig, ax = plt.subplots(figsize=(6.2, 4))
    im = ax.imshow(np.where(np.isnan(robnum), 11, robnum), cmap="RdYlGn", vmin=1, vmax=8, origin="lower")
    for i in range(len(covers)):
        for j in range(len(dmaxs)):
            ax.text(j, i, rob.iloc[i, j], ha="center", va="center", fontsize=9)
    ax.set_xticks(range(len(dmaxs))); ax.set_xticklabels(dmaxs); ax.set_yticks(range(len(covers))); ax.set_yticklabels(covers)
    ax.set(xlabel="Jarak (km) pada harga maks Rp15.500", ylabel="Jarak (km) yang tercakup harga min Rp7.500",
           title="Jarak mulai 2M rugi (km), klaster A\nmenurut asumsi tarif pembanding"); ax.grid(False)
    fig.tight_layout(); fig.savefig(OUT_G / "g5_robustness_asumsi_pembanding.png"); plt.close(fig)

    # ---------------- Q5: opsi kebijakan (sebaran Dasar 40/40/20; klaster A)
    w = np.array(SEBARAN["Dasar"]); ds = BUCKET["d"]
    UMK = P["UMK_DIPAKAI"]

    def ringkas(nama, hasil_per_bucket, layani=(1, 1, 1), catatan=""):
        ww = w * np.array(layani); share = ww.sum()
        kant = sum(ww[i] * hasil_per_bucket[i]["kantong_2m"] for i in range(3) if ww[i] > 0) / share
        net = sum(ww[i] * hasil_per_bucket[i]["untung_kurir_per_antaran"] for i in range(3) if ww[i] > 0) / share
        tm = sum(ww[i] * hasil_per_bucket[i]["waktu_per_antaran_menit"] for i in range(3) if ww[i] > 0) / share
        kap = int(np.floor(P["jam_kerja_per_hari"] * 60 / tm + 1e-9))
        n = min(P["throughput_antaran_per_hari"], kap)
        subsidi = sum(ww[i] * max(0, -hasil_per_bucket[i]["kantong_2m"]) for i in range(3) if ww[i] > 0) / share
        return dict(opsi=nama, order_terlayani=share, kantong_2m_rata2=kant, subsidi_2m_per_order=subsidi,
                    porsi_order_2m_rugi=sum(ww[i] for i in range(3) if hasil_per_bucket[i]["kantong_2m"] < -1e-9) / share,
                    untung_kurir_per_antaran=net, antaran_per_hari=n, penghasilan_kurir_bulan=net * n * P["hari_kerja_per_bulan"],
                    persen_umk=net * n * P["hari_kerja_per_bulan"] / UMK, catatan=catatan)

    opsi = []
    base = [hitung(d, "A", P, M) for d in ds]
    opsi.append(ringkas("O0 Skema sekarang (upah 3.500+1.500/km, ongkir <= pembanding)", base))
    ampl = [hitung(d, "A", P, M, upah_override=min(P["upah_dasar_per_antaran"] + P["upah_per_km"] * d, upah_maks_amplop(d, P))) for d in ds]
    opsi.append(ringkas("O1 Upah dibatasi amplop (2M tak rugi di semua jarak)", ampl, catatan="kurir menanggung: upah di >2 km lebih kecil"))
    opsi.append(ringkas("O2 Radius layanan <= 2 km (skema upah sekarang)", base, layani=(1, 0, 0), catatan="order >2 km tidak dilayani (60% order pada sebaran Dasar)"))
    ong_f = [hitung(d, "A", P, M, ratio_batas=10) for d in ds]      # ongkir bebas = ongkir minimum
    r_o3 = ringkas("O3 Ongkir fleksibel di atas pembanding (2M tak rugi)", ong_f)
    prem = [ong_f[i]["ongkir_disarankan"] / base[i]["pembanding"] - 1 for i in range(3)]
    r_o3["catatan"] = "premi vs pembanding per bucket: " + " / ".join(f"{x:+.0%}" for x in prem)
    opsi.append(r_o3)
    r_o4 = ringkas("O4 Subsidi 2M menutup selisih (skema sekarang)", base)
    r_o4["catatan"] = f"butuh subsidi rata-rata {rupiah(r_o4['subsidi_2m_per_order'])}/order ({rupiah(r_o4['subsidi_2m_per_order']*1000)} per 1.000 order)"
    opsi.append(r_o4)
    q5 = pd.DataFrame(opsi)
    q5.to_csv(OUT_T / "q5_opsi_kebijakan.csv", index=False)
    K["q5"] = {r.opsi[:2]: dict(kantong=round(r.kantong_2m_rata2), subsidi=round(r.subsidi_2m_per_order), rugi=round(r.porsi_order_2m_rugi, 2),
                               persen_umk=round(r.persen_umk, 3), terlayani=round(r.order_terlayani, 2)) for r in q5.itertuples()}
    K["q5_premi_o3"] = [round(x, 3) for x in prem]
    fig, ax = plt.subplots(1, 2, figsize=(11, 3.8), sharey=True)
    nm = [o[:2] for o in q5["opsi"]]
    warna = [C["hijau"] if v >= 0 else C["merah"] for v in q5["kantong_2m_rata2"]]
    warna[-1] = C["oranye"]   # O4: selisih negatif ditutup anggaran subsidi
    ax[0].barh(nm, q5["kantong_2m_rata2"], color=warna)
    ax[0].text(-1000, 4.38, "O4: selisih ini ditutup subsidi\n(anggaran, bukan nol)", fontsize=7, color=C["oranye"], va="top")
    ax[0].axvline(0, color="k", lw=.8); ax[0].set(title="Kantong 2M rata-rata per order, sebelum subsidi (Rp)"); ax[0].invert_yaxis()
    ax[1].barh(nm, q5["persen_umk"] * 100, color=C["biru"]); ax[1].axvline(100, color=C["merah"], ls="--")
    ax[1].set(title="Penghasilan bersih kurir (% UMK)", xlim=(0, 105))
    fig.suptitle("Perbandingan opsi (sebaran jarak Dasar, klaster A)  |  O0 sekarang, O1 amplop upah, O2 radius 2 km, O3 ongkir fleksibel, O4 subsidi", fontsize=8)
    fig.tight_layout(); fig.savefig(OUT_G / "g6_opsi_kebijakan.png"); plt.close(fig)

    # ---------------- Q6 (tambahan): berapa antaran per trip (batching) agar kurir capai target per jam?
    d, delta, extra_menit = 3.0, 0.5, 8.0
    um = upah_maks_amplop(d, P)
    bm = hitung(d, "A", P, M)["biaya_motor_per_km"]
    tgt_jam = K["q2_target_per_jam"]
    bat = []
    for k in range(1, 9):
        rute = d + (k - 1) * delta
        waktu = 2 * rute / P["kecepatan_rata2_normal_km_jam"] * 60 + P["waktu_tetap_per_antaran_menit"] + (k - 1) * extra_menit
        net = k * um * (1 - P["tingkat_order_gagal"] * (1 - P["bayar_order_gagal_fraksi"])) - bm * 2 * rute
        bat.append(dict(order_per_trip=k, waktu_trip_menit=round(waktu, 1), untung_kurir_per_trip=round(net), untung_kurir_per_jam=round(net / waktu * 60), target_per_jam=tgt_jam))
    bat = pd.DataFrame(bat); bat.to_csv(OUT_T / "q6_batching_ilustratif.csv", index=False)
    K["q6_k_capai_target"] = int(bat[bat.untung_kurir_per_jam >= tgt_jam].order_per_trip.min()) if (bat.untung_kurir_per_jam >= tgt_jam).any() else None
    K["q6_per_jam_k3"] = int(bat[bat.order_per_trip == 3].untung_kurir_per_jam.iloc[0])
    K["q6_per_jam_k1"] = int(bat[bat.order_per_trip == 1].untung_kurir_per_jam.iloc[0])

    # ---------------- kualitas data (G7)
    lg = pd.read_csv(OUT_T / "log_pembersihan.csv")
    lg = lg[(lg.baris_terdampak > 0) & ~lg.masalah.str.contains("jumlah baris|sisa|setelah|masih")]
    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    lg = lg.sort_values("baris_terdampak")
    ax.barh(lg["masalah"].str.slice(0, 48), lg["baris_terdampak"], color=C["oranye"]); ax.tick_params(axis="y", labelsize=7)
    ax.set(title="Masalah kualitas data pada log order mentah (3.060 baris)", xlabel="Baris terdampak")
    fig.tight_layout(); fig.savefig(OUT_G / "g7_kualitas_data_mentah.png"); plt.close(fig)

    json.dump(K, open(OUT_T / "angka_kunci.json", "w"), indent=1, ensure_ascii=False, default=float)
    return K, amp, q2, q5, bat


if __name__ == "__main__":
    K, amp, q2, q5, bat = run()
    print(json.dumps(K, indent=1, ensure_ascii=False, default=float))
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
    print(amp.to_string(index=False)); print(q2.round(3).to_string(index=False)); print(q5.round(3).drop(columns=["catatan"]).to_string(index=False)); print(q5.catatan.tolist()); print(bat.to_string(index=False))
