"""Model biaya kurir & ongkir 2M Sembako, ditulis ulang dalam Python.

Sumber logika: Draft_DS_Kurir_v2.xlsx (sheet Parameter, T2-T7). Modul ini dapat dipakai tim Gen AI
dan Full-Stack (mis. untuk pricing engine / fitur simulasi). Semua angka berasal dari
data/raw/parameter_model_raw.csv sehingga mengubah parameter = mengubah hasil.
"""
import math
import numpy as np
import pandas as pd

from .config import RAW


def load_params(path=None):
    df = pd.read_csv(path or RAW / "parameter_model_raw.csv")
    P = {}
    for _, r in df.iterrows():
        if pd.notna(r["nilai_num"]):
            P[r["parameter"]] = float(r["nilai_num"])
        elif pd.notna(r["nilai"]):
            P[r["parameter"]] = r["nilai"]
    return P


def load_motor(path=None):
    return pd.read_csv(path or RAW / "motor_klaster_raw.csv")


def biaya_motor_per_km(motor, P, klaster, macet=False, harga_bensin=None, pengali_kmpl=1.0):
    """Rata-rata tertimbang armada: energi + perawatan + penyusutan (Rp/km)."""
    m = motor[motor["klaster"] == klaster]
    hb = P["harga_pertalite_per_liter"] if harga_bensin is None else harga_bensin
    kmpl = m["konsumsi_klaim_kmpl"] * P["faktor_penyesuaian_konsumsi"] * pengali_kmpl
    energi = hb / kmpl
    if macet:
        energi = energi / P["faktor_konsumsi_saat_macet"]
    susut = m["harga_motor"] * (1 - P["nilai_sisa_motor"]) / P["umur_ekonomis_motor_km"]
    w = m["bobot_armada"]
    f = lambda s: float((s * w).sum() / w.sum())
    return f(energi) + f(m["perawatan_rp_km"]) + f(susut)


def pembanding(d, P, cover=None, dmax=None, acuan=None):
    """Tarif pembanding GoSend/GrabExpress (Rp) pada jarak d. Turunan dari rentang harga data PIC."""
    cover = P["pembanding_jarak_tercakup_km"] if cover is None else cover
    dmax = P["jarak_tarif_maks_km"] if dmax is None else dmax
    acuan = P["pembanding_acuan"] if acuan is None else acuan

    def f(mn, mx):
        return mn + (mx - mn) / (dmax - cover) * max(0.0, d - cover)

    g = f(P["gosend_motor_tarif_min"], P["gosend_motor_tarif_maks"])
    r = f(P["grabexpress_tarif_min"], P["grabexpress_tarif_maks"])
    return {"GoSend": g, "GrabExpress": r}.get(acuan, min(g, r))


def _ceil(x, step):
    return math.ceil(x / step - 1e-9) * step


def hitung(d, klaster, P, motor, macet=False, upah_dasar=None, upah_km=None, throughput=None,
           harga_bensin=None, pengali_kmpl=1.0, ratio_batas=None, bulat=True, cover=None, dmax=None,
           ongkir_override=None, kecepatan=None, upah_override=None):
    """Satu titik jarak (km, satu arah) -> semua metrik kantong kurir dan kantong 2M."""
    a = P["upah_dasar_per_antaran"] if upah_dasar is None else upah_dasar
    b = P["upah_per_km"] if upah_km is None else upah_km
    thr = P["throughput_antaran_per_hari"] if throughput is None else throughput
    ratio = P["batas_ongkir_vs_pembanding"] if ratio_batas is None else ratio_batas
    gagal = P["tingkat_order_gagal"]
    f_upah = 1 - gagal * (1 - P["bayar_order_gagal_fraksi"])
    f_ongkir = 1 - gagal * (1 - P["ongkir_ditagih_saat_gagal_fraksi"])

    bm_km = biaya_motor_per_km(motor, P, klaster, macet, harga_bensin, pengali_kmpl)
    tempuh = d * P["faktor_pulang_pergi"]
    bm = bm_km * tempuh
    upah_penuh = a + b * d if upah_override is None else upah_override
    upah_eff = upah_penuh * f_upah
    untung = upah_eff - bm
    v = kecepatan or (P["kecepatan_rata2_macet_km_jam"] if macet else P["kecepatan_rata2_normal_km_jam"])
    waktu = tempuh / v * 60 + P["waktu_tetap_per_antaran_menit"]
    kapasitas = math.floor(P["jam_kerja_per_hari"] * 60 / waktu + 1e-9)
    biaya_cab = P["overhead_harian_cabang"] / thr
    biaya_2m = upah_eff + biaya_cab
    ong_min_raw = (biaya_2m + P["margin_2M_minimum_per_antaran"]) / f_ongkir
    ong_min = _ceil(ong_min_raw, P["pembulatan_ongkir"]) if bulat else ong_min_raw
    pemb = pembanding(d, P, cover, dmax)
    batas = pemb * ratio
    ong_saran = min(ong_min, batas) if ongkir_override is None else ongkir_override
    kantong_2m = ong_saran * f_ongkir - biaya_2m
    n_real = min(thr, kapasitas)
    ong_lama = max(P["ongkir_minimum_2M_lama"], P["tarif_per_km_2M_lama"] * d)
    target_jam = P["UMK_DIPAKAI"] * P["persen_target_dari_umk"] / P["hari_kerja_per_bulan"] / P["jam_kerja_per_hari"]
    untung_jam = untung / waktu * 60
    if untung_jam <= 0:
        st_kurir = "RUGI"
    elif untung_jam >= target_jam:
        st_kurir = "LAYAK"
    elif untung_jam >= P["ambang_kurir_tipis"] * target_jam:
        st_kurir = "TIPIS"
    else:
        st_kurir = "KURANG"
    return dict(
        klaster=klaster, jarak_rute_km=d, jarak_tempuh_pp_km=tempuh, biaya_motor_per_km=bm_km,
        biaya_motor_per_antaran=bm, upah_penuh=upah_penuh, upah_efektif=upah_eff,
        untung_kurir_per_antaran=untung, waktu_per_antaran_menit=waktu, untung_kurir_per_jam=untung_jam,
        status_kurir=st_kurir, biaya_cabang_per_antaran=biaya_cab, biaya_2m_sebelum_ongkir=biaya_2m,
        ongkir_minimum_2m=ong_min, pembanding=pemb, batas_ongkir=batas, ongkir_disarankan=ong_saran,
        subsidi_2m=max(0.0, -kantong_2m), kantong_2m=kantong_2m,
        status_2m="AMAN" if kantong_2m >= -1e-9 else "RUGI",
        ongkir_lama=ong_lama, kantong_2m_lama=ong_lama * f_ongkir - biaya_2m,
        status_lama="AMAN" if ong_lama * f_ongkir - biaya_2m >= -1e-9 else "RUGI",
        kapasitas_antaran_hari=kapasitas, antaran_hari_realistis=n_real,
        penghasilan_bulan=untung * n_real * P["hari_kerja_per_bulan"],
        target_bersih_bulan=P["UMK_DIPAKAI"] * P["persen_target_dari_umk"],
    )


def grid(P, motor, klaster, jarak=None, **kw):
    jarak = np.arange(0.25, 10.0001, 0.25) if jarak is None else jarak
    return pd.DataFrame([hitung(float(d), klaster, P, motor, **kw) for d in jarak])


def upah_maks_amplop(d, P, ratio=None, cover=None, dmax=None):
    """Upah penuh maksimum per antaran agar kantong 2M >= 0 bila ongkir = batas pembanding."""
    ratio = P["batas_ongkir_vs_pembanding"] if ratio is None else ratio
    f_upah = 1 - P["tingkat_order_gagal"] * (1 - P["bayar_order_gagal_fraksi"])
    f_ong = 1 - P["tingkat_order_gagal"] * (1 - P["ongkir_ditagih_saat_gagal_fraksi"])
    cab = P["overhead_harian_cabang"] / P["throughput_antaran_per_hari"]
    return (pembanding(d, P, cover, dmax) * ratio * f_ong - cab) / f_upah
