"""Simulator interaktif model biaya kurir 2M Sembako (SANDBOX, bukan fitur produksi).

Jalankan dari sandbox/ida_simulation:   .venv/Scripts/streamlit run app.py
Semua logika ada di costmodel.py (fungsi murni); file ini hanya UI.
DATA SINTETIS / ASUMSI, bukan data lapangan.
"""
import altair as alt
import pandas as pd
import streamlit as st

import costmodel as cm

BANNER = ("SIMULASI DATA SINTETIS. Titik rugi bergantung asumsi tarif pembanding yang belum diverifikasi. "
          "Semua angka = asumsi tim, BUKAN data lapangan.")
TAG = " (DATA SINTETIS / ASUMSI)"
IDA = cm.IDA

st.set_page_config(page_title="Simulator Ongkir 2M (sintetis)", layout="wide")

# ------------------------------------------------------------------ state & reset
DEFAULTS = {
    "upah_dasar": int(IDA.upah_dasar), "upah_per_km": int(IDA.upah_per_km),
    "tarif_min": int(IDA.tarif_min), "tarif_maks": int(IDA.tarif_maks),
    "d_cover": float(IDA.d_cover), "d_maks": float(IDA.d_maks),
    "throughput": int(IDA.throughput), "overhead": int(IDA.overhead_harian),
    "v_normal": float(IDA.v_normal), "v_macet": float(IDA.v_macet), "waktu_tetap": float(IDA.waktu_tetap),
    "umk": int(IDA.umk), "p_gagal": float(IDA.p_gagal), "ongkir_gagal": float(IDA.fraksi_ongkir_ditagih_gagal),
    "bensin": int(IDA.harga_bensin), "s02": int(IDA.sebaran[0] * 100), "s24": int(IDA.sebaran[1] * 100),
    "klaster": "A", "bulat": False, "cap": False,
    "detour": 0.5, "menit_drop": 8.0, "d_batch": 3.0, "metode_q5": "wakil",
}
for k, v in DEFAULTS.items():
    st.session_state.setdefault(k, v)


def reset():
    for k, v in DEFAULTS.items():
        st.session_state[k] = v


st.error("⚠️ " + BANNER)

with st.sidebar:
    st.warning("DATA SINTETIS / ASUMSI")
    st.button("↺ Reset ke nilai Ida", on_click=reset, width="stretch")
    st.subheader("Skema upah kurir")
    st.slider("Upah dasar per antaran (Rp)", 0, 10000, step=250, key="upah_dasar")
    st.slider("Upah per km (Rp/km)", 0, 5000, step=100, key="upah_per_km")
    st.subheader("Tarif pembanding (GoSend, belum terverifikasi)")
    st.slider("Tarif minimum (Rp)", 3000, 15000, step=500, key="tarif_min")
    st.slider("Tarif maksimum (Rp)", 8000, 30000, step=500, key="tarif_maks")
    st.slider("Jarak tercakup tarif min (km) — ASUMSI", 0.5, 8.0, step=0.5, key="d_cover")
    st.slider("Jarak saat tarif maks (km) — KONFIRMASI", 2.0, 20.0, step=0.5, key="d_maks")
    st.checkbox("Batasi tarif di Rp maks (Ida: tidak)", key="cap")
    st.checkbox("Ongkir dibulatkan ke bawah ke Rp500 (harga bisa ditagih)", key="bulat")
    st.subheader("Operasional")
    st.slider("Throughput (antaran/hari)", 5, 40, key="throughput")
    st.slider("Overhead harian cabang (Rp)", 0, 50000, step=1000, key="overhead")
    st.slider("Kecepatan normal (km/jam)", 8.0, 40.0, step=1.0, key="v_normal")
    st.slider("Kecepatan macet (km/jam)", 5.0, 30.0, step=1.0, key="v_macet")
    st.slider("Waktu tetap per antaran (menit)", 0.0, 40.0, step=1.0, key="waktu_tetap")
    st.slider("Tingkat order gagal", 0.0, 0.2, step=0.01, key="p_gagal")
    st.slider("Fraksi ongkir ditagih saat gagal (belum diputuskan)", 0.0, 1.0, step=0.1, key="ongkir_gagal")
    st.slider("Harga Pertalite (Rp/liter)", 7000, 15000, step=500, key="bensin")
    st.subheader("Target & sebaran")
    st.number_input("UMK (Rp/bulan)", 1_000_000, 10_000_000, step=50_000, key="umk")
    st.slider("Order 0–2 km (%)", 0, 100, key="s02")
    st.slider("Order 2–4 km (%)", 0, 100, key="s24")
    if st.session_state["s02"] + st.session_state["s24"] > 100:
        st.error("0–2 km + 2–4 km > 100%; porsi 2–4 km dipotong.")
    st.caption(f"Order >4 km = {max(0, 100 - st.session_state['s02'] - st.session_state['s24'])}% (sisa)")
    st.radio("Klaster motor", ["A", "B"], horizontal=True, key="klaster")

S = st.session_state
s02, s24 = S["s02"] / 100, min(S["s24"], 100 - S["s02"]) / 100
d_maks = max(S["d_maks"], S["d_cover"] + 0.5)
if d_maks != S["d_maks"]:
    st.sidebar.info(f"Jarak tarif maks dinaikkan ke {d_maks} km (harus > jarak tercakup).")
P = IDA.with_(
    upah_dasar=float(S["upah_dasar"]), upah_per_km=float(S["upah_per_km"]), tarif_min=float(S["tarif_min"]),
    tarif_maks=float(S["tarif_maks"]), d_cover=float(S["d_cover"]), d_maks=float(d_maks), throughput=float(S["throughput"]),
    overhead_harian=float(S["overhead"]), v_normal=float(S["v_normal"]), v_macet=float(S["v_macet"]),
    waktu_tetap=float(S["waktu_tetap"]), umk=float(S["umk"]), p_gagal=float(S["p_gagal"]),
    fraksi_ongkir_ditagih_gagal=float(S["ongkir_gagal"]), harga_bensin=float(S["bensin"]),
    sebaran=(s02, s24, max(0.0, 1 - s02 - s24)), bulatkan_batas=bool(S["bulat"]), batasi_di_maks=bool(S["cap"]),
)
KL = S["klaster"]
berubah = {k: (DEFAULTS[k], S[k]) for k in DEFAULTS if S[k] != DEFAULTS[k]}
if berubah:
    st.info("Parameter berbeda dari nilai Ida: " + ", ".join(f"{k} {a}→{b}" for k, (a, b) in berubah.items()))

rp = lambda x: "Rp" + f"{x:,.0f}".replace(",", ".")  # noqa: E731

st.title("Simulator ongkir, upah kurir & kantong 2M")
st.caption("Sandbox audit pipeline DS (Ida v2). Logika: `costmodel.py` (ditulis ulang independen, paritas ≤ Rp1 vs model Ida).")

t1, t2, t3, t4, t5, t6, tinfo = st.tabs(["Q1 Titik rugi", "Q2 Kurir vs UMK", "Q3 Sensitivitas", "Q4 Kekokohan asumsi",
                                         "Q5 Opsi kebijakan", "Q6 Batching (ilustratif)", "Asumsi & sumber"])

# ------------------------------------------------------------------ Q1
with t1:
    g = pd.DataFrame(cm.grid(P, KL))
    tr = cm.titik_rugi(P, KL)
    tl = cm.titik_rugi(P, KL, kolom="kantong_2m_lama")
    c1, c2, c3 = st.columns(3)
    c1.metric("2M mulai rugi (skema baru)", f"{tr['mulai']:.2f} km" if tr["mulai"] else "tidak rugi ≤10 km",
              delta=None if tr["mulai"] is None else f"{tr['mulai'] - 2.25:+.2f} km vs Ida (2,25)", delta_color="off")
    c2.metric("Titik grid rugi", f"{tr['n_titik']}/{tr['n_grid']}")
    c3.metric("Tarif lama rugi di", f"{tl['mulai']}–{tl['akhir']} km" if tl["mulai"] else "tidak ada")
    long = g.melt(id_vars="jarak_rute_km", value_vars=["kantong_2m", "kantong_2m_lama"], var_name="skema", value_name="rp")
    long["skema"] = long["skema"].map({"kantong_2m": "Skema baru (ongkir ≤ pembanding)", "kantong_2m_lama": "Tarif lama (Rp3.000/km, min Rp8.000)"})
    base = alt.Chart(long).mark_line(point=True).encode(
        x=alt.X("jarak_rute_km:Q", title="Jarak rute satu arah (km)"), y=alt.Y("rp:Q", title="Kantong 2M per antaran (Rp)"),
        color=alt.Color("skema:N", legend=alt.Legend(orient="bottom", title=None)),
        tooltip=["jarak_rute_km", "skema", alt.Tooltip("rp:Q", format=",.0f")])
    layers = [base, alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color="black").encode(y="y:Q")]
    if tr["mulai"]:
        layers.append(alt.Chart(pd.DataFrame({"x": [tr["mulai"]]})).mark_rule(color="red", strokeDash=[4, 4]).encode(x="x:Q"))
    st.altair_chart(alt.layer(*layers).properties(title="Kantong 2M per antaran vs jarak" + TAG, height=340), width="stretch")

    env = g.melt(id_vars="jarak_rute_km", value_vars=["upah_penuh", "upah_amplop"], var_name="seri", value_name="rp")
    env["seri"] = env["seri"].map({"upah_penuh": "Upah skema sekarang", "upah_amplop": "Amplop upah (maks agar 2M tak rugi)"})
    st.altair_chart(alt.Chart(env).mark_line().encode(
        x=alt.X("jarak_rute_km:Q", title="Jarak (km)"), y=alt.Y("rp:Q", title="Rp per antaran"),
        color=alt.Color("seri:N", legend=alt.Legend(orient="bottom", title=None)), tooltip=["jarak_rute_km", "seri", alt.Tooltip("rp:Q", format=",.0f")]
    ).properties(title="Amplop upah vs upah skema" + TAG, height=260), width="stretch")
    with st.expander("Tabel grid"):
        st.dataframe(g[["jarak_rute_km", "upah_penuh", "pembanding", "ongkir_minimum_2m", "ongkir_disarankan", "kantong_2m",
                        "ongkir_lama", "kantong_2m_lama", "untung_kurir_per_antaran", "upah_amplop"]].round(0), hide_index=True)

# ------------------------------------------------------------------ Q2
with t2:
    q = pd.DataFrame(cm.q2(P, harga_bensin_relatif=True))
    k = cm.kebutuhan_target(P, 2.7, KL)
    c1, c2, c3, c4 = st.columns(4)
    dasar = q[(q.skenario == "Dasar") & (q.klaster == KL)].iloc[0]
    c1.metric(f"Dasar klaster {KL}", f"{dasar.persen_umk:.1%} UMK", delta=f"{rp(dasar.penghasilan_bulan)}/bln", delta_color="off")
    c2.metric("Kapasitas vs dibutuhkan", f"{k['kapasitas']} vs {k['antaran_dibutuhkan']} antaran/hari")
    c3.metric("Ongkir agar kurir capai target (2,7 km)", rp(k["ongkir_target"]), delta=f"pembanding {rp(k['pembanding'])}", delta_color="off")
    c4.metric("Kesenjangan per kurir/bulan", rp(k["gap_per_kurir_bulan"]))
    q["label"] = q["skenario"] + " · " + q["klaster"]
    q["persen"] = q["persen_umk"] * 100
    bars = alt.Chart(q).mark_bar().encode(
        x=alt.X("label:N", sort=None, title=None, axis=alt.Axis(labelAngle=-30)), y=alt.Y("persen:Q", title="% target UMK"),
        color=alt.Color("klaster:N"), tooltip=["skenario", "klaster", alt.Tooltip("persen:Q", format=".1f"),
                                               alt.Tooltip("penghasilan_bulan:Q", format=",.0f"), "antaran_per_hari", "kapasitas"])
    rule = alt.Chart(pd.DataFrame({"y": [100]})).mark_rule(color="red", strokeDash=[4, 4]).encode(y="y:Q")
    st.altair_chart((bars + rule).properties(title="Penghasilan bersih kurir (% UMK) per skenario" + TAG, height=340), width="stretch")
    st.caption("Skenario Optimis/Dasar/Pesimis memakai pengali bensin 0,9/1,0/1,1 dari slider, km/l 1,1/1,0/0,9, throughput 18/15/12 "
               "(dibatasi kapasitas waktu), jarak 2,05/2,7/3,6 km. Catatan audit: laporan Ida menulis '18 antaran/hari' untuk Optimis, "
               "padahal kapasitas waktu hanya 17.")
    st.dataframe(q.drop(columns=["label", "persen"]).round(3), hide_index=True)

# ------------------------------------------------------------------ Q3
with t3:
    rentang = st.slider("Rentang perubahan tiap variabel (±%)", 5, 50, 20, step=5, key="rentang_q3") / 100
    d0 = cm.jarak_rata2(P)
    tor = pd.DataFrame(cm.tornado(P, d=d0, klaster=KL, rentang=rentang))
    tor["nama"] = tor["variabel"] + tor["tambahan_audit"].map({True: " *", False: ""})
    st.markdown(f"Satu variabel digeser **±{rentang:.0%}**, variabel lain tetap. Titik acuan: jarak rata-rata **{d0:.2f} km** "
                f"(dari sebaran di sidebar), klaster {KL}. Sebaran jarak: kiri = skenario Dekat (60/30/10), kanan = Jauh (20/40/40). "
                "Tanda * = variabel tambahan audit, tidak ada di tornado Ida.")

    def tornado_chart(kol_minus, kol_plus, judul, fmt):
        t = tor.assign(swing=(tor[kol_plus] - tor[kol_minus]).abs()).sort_values("swing", ascending=False)
        long = t.melt(id_vars=["nama", "swing"], value_vars=[kol_minus, kol_plus], var_name="arah", value_name="delta")
        long["arah"] = long["arah"].map({kol_minus: "variabel turun / Dekat", kol_plus: "variabel naik / Jauh"})
        return alt.Chart(long).mark_bar().encode(
            y=alt.Y("nama:N", sort=list(t["nama"]), title=None), x=alt.X("delta:Q", title=judul),
            color=alt.Color("arah:N", scale=alt.Scale(range=["#1f5fa8", "#e08a1e"]), legend=alt.Legend(orient="bottom", title=None)),
            tooltip=["nama", "arah", alt.Tooltip("delta:Q", format=fmt)]).properties(height=300)

    c1, c2 = st.columns(2)
    c1.altair_chart(tornado_chart("d_ongkir_minus", "d_ongkir_plus", "Perubahan ongkir minimum (Rp/order)", ",.0f")
                    .properties(title="Ongkir minimum agar 2M tidak rugi" + TAG), width="stretch")
    c2.altair_chart(tornado_chart("d_hasil_minus", "d_hasil_plus", "Perubahan penghasilan kurir (Rp/bulan)", ",.0f")
                    .properties(title="Penghasilan bersih kurir per bulan" + TAG), width="stretch")

    r0 = tor["rugi_dasar"].iloc[0]
    rg = tor[["nama", "rugi_minus", "rugi_plus"]].copy()
    rg["swing"] = (rg["rugi_plus"].fillna(10.25) - rg["rugi_minus"].fillna(10.25)).abs()
    rg = rg.sort_values("swing", ascending=False)
    seg = alt.Chart(rg.assign(a=rg.rugi_minus.fillna(10.25), b=rg.rugi_plus.fillna(10.25))).encode(y=alt.Y("nama:N", sort=list(rg["nama"]), title=None))
    st.altair_chart((seg.mark_rule(strokeWidth=3, color="#7f8c8d").encode(x=alt.X("a:Q", title="Jarak mulai 2M rugi (km)", scale=alt.Scale(domain=[0, 10.5])), x2="b:Q")
                     + seg.mark_point(filled=True, size=90, color="#1f5fa8").encode(x="a:Q", tooltip=["nama", "rugi_minus"])
                     + seg.mark_point(filled=True, size=90, color="#e08a1e").encode(x="b:Q", tooltip=["nama", "rugi_plus"])
                     + alt.Chart(pd.DataFrame({"x": [r0 or 10.25]})).mark_rule(color="red", strokeDash=[4, 4]).encode(x="x:Q"))
                    .properties(title="Titik rugi 2M bila variabel digeser (biru = turun/Dekat, oranye = naik/Jauh)" + TAG, height=300),
                    width="stretch")
    top = rg.iloc[0]
    st.write(f"Titik rugi saat ini: **{r0 if r0 else '>10'} km**. Variabel yang paling menggeser titik rugi: **{top['nama']}** "
             f"({top['rugi_minus'] if pd.notna(top['rugi_minus']) else '>10'} → {top['rugi_plus'] if pd.notna(top['rugi_plus']) else '>10'} km). "
             "Harga bensin dan efisiensi motor tidak mengubah ongkir minimum maupun titik rugi karena biaya motor ditanggung kurir.")
    with st.expander("Tabel tornado"):
        st.dataframe(tor.drop(columns=["nama"]).round(2), hide_index=True)

# ------------------------------------------------------------------ Q4
with t4:
    q4 = pd.DataFrame(cm.q4(P, klaster=KL))
    base_tr = cm.titik_rugi(P, KL)["mulai"]
    q4["label"] = q4["rugi_mulai"].map(lambda v: ">10" if pd.isna(v) else f"{v:.2f}")
    q4["Q1 berlaku?"] = q4["kesimpulan_q1_berlaku"].map({True: "✓", False: "✗"})
    q4["teks"] = q4["label"] + " " + q4["Q1 berlaku?"]
    q4["nilai"] = q4["rugi_mulai"].fillna(11)
    st.markdown(f"Titik rugi dihitung ulang untuk 25 kombinasi asumsi pembanding (tarif min {rp(P.tarif_min)} → maks {rp(P.tarif_maks)}). "
                f"**✓ = sama dengan titik rugi saat ini ({base_tr if base_tr else '>10'} km)**, artinya kesimpulan Q1 tidak bergantung pada sel itu.")
    heat = alt.Chart(q4).encode(x=alt.X("d_maks:O", title="Jarak saat tarif maks (km)"),
                                y=alt.Y("d_cover:O", title="Jarak tercakup tarif min (km)", sort="descending"))
    st.altair_chart((heat.mark_rect().encode(color=alt.Color("nilai:Q", scale=alt.Scale(scheme="redyellowgreen", domain=[1, 11]),
                                                                 title="mulai rugi (km)"),
                                              tooltip=["d_cover", "d_maks", "label", "n_titik_rugi", "Q1 berlaku?"])
                     + heat.mark_text(fontSize=13).encode(text="teks:N"))
                    .properties(title="Jarak mulai 2M rugi menurut asumsi tarif pembanding" + TAG, height=330), width="stretch")
    n_ok = int(q4["kesimpulan_q1_berlaku"].sum())
    st.write(f"Kesimpulan Q1 berlaku di **{n_ok}/25** sel; tidak rugi sampai 10 km di **{int(q4['rugi_mulai'].isna().sum())}** sel.")

# ------------------------------------------------------------------ Q5
with t5:
    st.radio("Cara menghitung sebaran", ["wakil", "seragam"], horizontal=True, key="metode_q5",
             format_func=lambda m: "1 jarak wakil per bucket (1/3/5,5 km, cara Ida)" if m == "wakil" else "merata di bucket (0,3–2 / 2–4 / 4–8 km)")
    q5 = pd.DataFrame(cm.q5(P, klaster=KL, metode=S["metode_q5"]))
    q5["opsi_nama"] = q5["opsi"] + " " + q5["nama"]
    c1, c2 = st.columns(2)
    c1.altair_chart(alt.Chart(q5).mark_bar().encode(
        y=alt.Y("opsi_nama:N", sort=None, title=None), x=alt.X("kantong_2m_rata2:Q", title="Kantong 2M rata-rata per order (Rp)"),
        color=alt.condition("datum.kantong_2m_rata2 < 0", alt.value("#c0392b"), alt.value("#2e8b57")),
        tooltip=["opsi", alt.Tooltip("kantong_2m_rata2:Q", format=",.0f"), alt.Tooltip("porsi_order_2m_rugi:Q", format=".0%")]
    ).properties(title="Kantong 2M (sebelum subsidi)" + TAG, height=260), width="stretch")
    c2.altair_chart(alt.Chart(q5.assign(p=q5.persen_umk * 100)).mark_bar(color="#1f5fa8").encode(
        y=alt.Y("opsi_nama:N", sort=None, title=None), x=alt.X("p:Q", title="% UMK kurir"), tooltip=["opsi", alt.Tooltip("p:Q", format=".1f")]
    ).properties(title="Penghasilan kurir (% UMK)" + TAG, height=260), width="stretch")
    show = q5[["opsi", "nama", "order_terlayani", "porsi_order_2m_rugi", "kantong_2m_rata2", "subsidi_2m_per_order",
               "penghasilan_kurir_bulan", "persen_umk"]].copy()
    st.dataframe(show.style.format({"order_terlayani": "{:.0%}", "porsi_order_2m_rugi": "{:.1%}", "kantong_2m_rata2": "{:,.0f}",
                                    "subsidi_2m_per_order": "{:,.0f}", "penghasilan_kurir_bulan": "{:,.0f}", "persen_umk": "{:.1%}"}),
                 hide_index=True)
    st.caption("O4 = O0 dengan selisih negatif ditutup subsidi (anggaran, bukan nol). O3 premi tiap bucket belum diuji ke pelanggan.")

# ------------------------------------------------------------------ Q6
with t6:
    st.warning("ILUSTRATIF. Detour per drop dan menit per drop adalah ASUMSI, bukan data. Workbook v2.2 memakai jarak antar drop 1 km.")
    c1, c2, c3 = st.columns(3)
    c1.slider("Detour per drop tambahan (km) — ASUMSI", 0.0, 3.0, step=0.1, key="detour")
    c2.slider("Waktu per drop tambahan (menit) — ASUMSI", 0.0, 20.0, step=0.5, key="menit_drop")
    c3.slider("Jarak trip (km)", 0.5, 8.0, step=0.5, key="d_batch")
    b = pd.DataFrame(cm.q6(P, d=S["d_batch"], detour_km=S["detour"], menit_per_drop=S["menit_drop"], klaster=KL))
    line = alt.Chart(b).mark_line(point=True).encode(x=alt.X("order_per_trip:O", title="Order per trip"),
                                                     y=alt.Y("untung_kurir_per_jam:Q", title="Untung kurir per jam (Rp)"),
                                                     tooltip=[alt.Tooltip("untung_kurir_per_jam:Q", format=",.0f"), alt.Tooltip("waktu_trip_menit:Q", format=".1f")])
    tgt = alt.Chart(pd.DataFrame({"y": [cm.target_per_jam(P)]})).mark_rule(color="red", strokeDash=[4, 4]).encode(y="y:Q")
    st.altair_chart((line + tgt).properties(title="Batching: untung kurir/jam vs target (garis merah)" + TAG, height=320), width="stretch")
    capai = b[b.capai_target]
    st.write("Mencapai target per jam pada " + (f"**{int(capai.order_per_trip.min())} order/trip**" if len(capai) else "**tidak ada k ≤ 8**")
             + f" (target {rp(cm.target_per_jam(P))}/jam; upah per order = amplop di {S['d_batch']} km).")

with tinfo:
    st.markdown(f"""
**Label:** {cm.LABEL}.

- Model: `costmodel.py`, ditulis ulang dari rumus brief + membaca `model_biaya.py` Ida. Paritas vs Ida ≤ Rp1 (lihat `REPORT.md`).
- Kantong 2M = ongkir × (1 − gagal × (1 − ongkir ditagih saat gagal)) − upah × (1 − gagal × 0,5) − overhead/throughput. Biaya motor ditanggung kurir.
- Tarif pembanding = garis lurus dari (jarak tercakup, tarif min) ke (jarak maks, tarif maks); tarif GoSend Rp7.500–15.500 dari PIC, **belum terverifikasi**.
- Parameter tingkat D (kecepatan, waktu tetap, gagal 3%, throughput, sebaran 40/40/20) = asumsi tim, menunggu log PWA Kurir.
""")
    st.json(P.as_dict(), expanded=False)
