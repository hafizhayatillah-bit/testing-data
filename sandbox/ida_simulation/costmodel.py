"""Model biaya kurir & ongkir 2M Sembako, DITULIS ULANG SECARA INDEPENDEN untuk audit.

DATA SINTETIS / ASUMSI, bukan data lapangan. Semua default = nilai di parameter_model_raw.csv kiriman Ida
(diketik ulang di sini supaya modul ini murni: tanpa I/O, tanpa impor kode Ida).

Rumus (dari brief PL + membaca model_biaya.py Ida, bukan menyalin kodenya):
  upah penuh            = upah_dasar + upah_per_km x d                       (d = jarak rute SATU arah, km)
  faktor upah efektif   = 1 - p_gagal x (1 - fraksi_bayar_gagal)            (order gagal dibayar 50%)
  faktor ongkir efektif = 1 - p_gagal x (1 - fraksi_ongkir_ditagih_gagal)   (order gagal: ongkir tidak ditagih)
  biaya cabang/antaran  = overhead_harian / throughput
  kantong 2M            = ongkir x f_ongkir - upah x f_upah - biaya cabang  (biaya motor DITANGGUNG KURIR)
  ongkir minimum        = ceil_500((upah x f_upah + biaya cabang + margin) / f_ongkir)
  ongkir skema baru     = min(ongkir minimum, rasio_batas x pembanding(d))
  pembanding(d)         = tarif_min + (tarif_maks - tarif_min) / (d_maks - d_cover) x max(0, d - d_cover)
  ongkir tarif lama     = max(Rp8.000, Rp3.000 x d)
  biaya motor/km        = rata-rata armada (energi + perawatan + penyusutan) per klaster
  untung kurir          = upah x f_upah - biaya motor/km x 2d
  waktu per antaran     = 2d / kecepatan x 60 + waktu tetap
  kapasitas/hari        = floor(jam kerja x 60 / waktu)
  penghasilan/bulan     = untung kurir x min(throughput, kapasitas) x hari kerja
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace, asdict

LABEL = "SIMULASI DATA SINTETIS / ASUMSI, bukan data lapangan"

# Tabel armada T2 (Draft_DS_Kurir_v2.xlsx). klaim km/l, perawatan Rp/km, harga motor Rp, bobot armada.
ARMADA_DEFAULT = (
    ("M1", "A", 60.6, 90, 19_000_000, 1.0),
    ("M2", "A", 51.7, 95, 24_000_000, 1.0),
    ("M3", "B", 46.9, 105, 29_000_000, 1.0),
    ("M4", "B", 45.0, 125, 36_000_000, 1.0),
    ("M5", "A", 59.8, 75, 18_500_000, 1.0),
    ("M6", "A", 57.2, 80, 20_500_000, 1.0),
    ("M7", "B", 49.5, 100, 26_000_000, 1.0),
)


@dataclass(frozen=True)
class Params:
    # skema upah kurir
    upah_dasar: float = 3500.0
    upah_per_km: float = 1500.0
    p_gagal: float = 0.03
    fraksi_bayar_gagal: float = 0.5
    fraksi_ongkir_ditagih_gagal: float = 0.0
    # 2M
    overhead_harian: float = 10_000.0
    throughput: float = 15.0
    margin_min: float = 0.0
    pembulatan: float = 500.0
    rasio_batas: float = 1.0
    # pembanding (GoSend motor, data PIC belum terverifikasi)
    tarif_min: float = 7500.0
    tarif_maks: float = 15500.0
    d_cover: float = 4.0          # jarak (km) yang tercakup tarif minimum (ASUMSI)
    d_maks: float = 10.0          # jarak (km) saat tarif maksimum (KONFIRMASI)
    batasi_di_maks: bool = False  # Ida: tidak dibatasi (ekstrapolasi linear di atas d_maks)
    bulatkan_batas: bool = False  # Ida (Q1 utama): batas pembanding TIDAK dibulatkan -> ongkir bisa Rp7.833,33 (temuan E2)
    # tarif lama 2M
    tarif_lama_per_km: float = 3000.0
    tarif_lama_min: float = 8000.0
    # waktu
    v_normal: float = 20.0
    v_macet: float = 12.0
    waktu_tetap: float = 15.0
    faktor_pp: float = 2.0
    jam_kerja: float = 8.0
    hari_kerja: float = 26.0
    # target
    umk: float = 5_938_885.0
    persen_target: float = 1.0
    # biaya motor
    harga_bensin: float = 10_000.0
    faktor_konsumsi: float = 0.9
    faktor_macet: float = 0.85
    umur_km: float = 60_000.0
    nilai_sisa: float = 0.3
    armada: tuple = field(default=ARMADA_DEFAULT)
    # sebaran jarak (0-2, 2-4, >4 km) dan jarak wakil tiap bucket
    sebaran: tuple = (0.4, 0.4, 0.2)
    jarak_wakil: tuple = (1.0, 3.0, 5.5)
    rentang_bucket: tuple = ((0.3, 2.0), (2.0, 4.0), (4.0, 8.0))   # rentang generator synth_orders.py

    def with_(self, **kw) -> "Params":
        return replace(self, **kw)

    def as_dict(self) -> dict:
        return asdict(self)


IDA = Params()


# ------------------------------------------------------------------ dasar
def f_upah(p: Params) -> float:
    return 1.0 - p.p_gagal * (1.0 - p.fraksi_bayar_gagal)


def f_ongkir(p: Params) -> float:
    return 1.0 - p.p_gagal * (1.0 - p.fraksi_ongkir_ditagih_gagal)


def biaya_cabang(p: Params) -> float:
    return p.overhead_harian / p.throughput


def upah(d: float, p: Params) -> float:
    return p.upah_dasar + p.upah_per_km * d


def ceil_to(x: float, step: float) -> float:
    if step <= 0:
        return x
    return math.ceil(round(x / step, 9)) * step


def pembanding(d: float, p: Params) -> float:
    span = p.d_maks - p.d_cover
    if span <= 0:
        raise ValueError("d_maks harus > d_cover")
    v = p.tarif_min + (p.tarif_maks - p.tarif_min) / span * max(0.0, d - p.d_cover)
    return min(v, p.tarif_maks) if p.batasi_di_maks else v


def biaya_motor_per_km(p: Params, klaster: str = "A", macet: bool = False) -> float:
    rows = [r for r in p.armada if r[1] == klaster]
    if not rows:
        raise ValueError(f"klaster {klaster!r} tidak ada di armada")
    wsum = sum(r[5] for r in rows)
    tot = 0.0
    for _, _, kmpl, rawat, harga, w in rows:
        energi = p.harga_bensin / (kmpl * p.faktor_konsumsi)
        if macet:
            energi /= p.faktor_macet
        susut = harga * (1 - p.nilai_sisa) / p.umur_km
        tot += w * (energi + rawat + susut)
    return tot / wsum


def ongkir_minimum(d: float, p: Params, upah_penuh: float | None = None, bulat: bool = True) -> float:
    u = upah(d, p) if upah_penuh is None else upah_penuh
    x = (u * f_upah(p) + biaya_cabang(p) + p.margin_min) / f_ongkir(p)
    return ceil_to(x, p.pembulatan) if bulat else x


def batas_ongkir(d: float, p: Params) -> float:
    b = p.rasio_batas * pembanding(d, p)
    if p.bulatkan_batas and p.pembulatan > 0:
        b = math.floor(round(b / p.pembulatan, 9)) * p.pembulatan
    return b


def ongkir_skema_baru(d: float, p: Params, upah_penuh: float | None = None) -> float:
    return min(ongkir_minimum(d, p, upah_penuh), batas_ongkir(d, p))


def ongkir_lama(d: float, p: Params) -> float:
    return max(p.tarif_lama_min, p.tarif_lama_per_km * d)


def kantong_2m(d: float, p: Params, ongkir: float, upah_penuh: float | None = None) -> float:
    u = upah(d, p) if upah_penuh is None else upah_penuh
    return ongkir * f_ongkir(p) - u * f_upah(p) - biaya_cabang(p)


def upah_amplop(d: float, p: Params) -> float:
    """Upah penuh maksimum supaya kantong 2M >= 0 saat ongkir = rasio x pembanding."""
    return (p.rasio_batas * pembanding(d, p) * f_ongkir(p) - biaya_cabang(p)) / f_upah(p)


def waktu_antaran(d: float, p: Params, macet: bool = False, kecepatan: float | None = None) -> float:
    v = kecepatan or (p.v_macet if macet else p.v_normal)
    return p.faktor_pp * d / v * 60.0 + p.waktu_tetap


def kapasitas_harian(waktu_menit: float, p: Params) -> int:
    return int(math.floor(p.jam_kerja * 60.0 / waktu_menit + 1e-9))


def target_bulan(p: Params) -> float:
    return p.umk * p.persen_target


def target_per_jam(p: Params) -> float:
    return target_bulan(p) / p.hari_kerja / p.jam_kerja


# ------------------------------------------------------------------ satu titik jarak
def titik(d: float, p: Params, klaster: str = "A", macet: bool = False, upah_penuh: float | None = None,
          throughput: float | None = None) -> dict:
    pp = p if throughput is None else p.with_(throughput=throughput)
    u = upah(d, pp) if upah_penuh is None else upah_penuh
    bm_km = biaya_motor_per_km(pp, klaster, macet)
    bm = bm_km * pp.faktor_pp * d
    ue = u * f_upah(pp)
    t = waktu_antaran(d, pp, macet)
    kap = kapasitas_harian(t, pp)
    n = min(pp.throughput, kap)
    pemb = pembanding(d, pp)
    o_min = ongkir_minimum(d, pp, u)
    o_baru = min(o_min, batas_ongkir(d, pp))
    o_lama = ongkir_lama(d, pp)
    untung = ue - bm
    return dict(
        klaster=klaster, jarak_rute_km=d, upah_penuh=u, upah_efektif=ue, biaya_motor_per_km=bm_km,
        biaya_motor_per_antaran=bm, untung_kurir_per_antaran=untung, waktu_per_antaran_menit=t,
        untung_kurir_per_jam=untung / t * 60.0, kapasitas_antaran_hari=kap, antaran_hari_realistis=n,
        biaya_cabang_per_antaran=biaya_cabang(pp), ongkir_minimum_2m=o_min, pembanding=pemb,
        batas_ongkir=batas_ongkir(d, pp), ongkir_disarankan=o_baru,
        kantong_2m=kantong_2m(d, pp, o_baru, u), ongkir_lama=o_lama, kantong_2m_lama=kantong_2m(d, pp, o_lama, u),
        penghasilan_bulan=untung * n * pp.hari_kerja, upah_amplop=upah_amplop(d, pp),
    )


def grid(p: Params, klaster: str = "A", start: float = 0.25, stop: float = 10.0, step: float = 0.25, **kw) -> list[dict]:
    n = int(round((stop - start) / step)) + 1
    return [titik(round(start + i * step, 6), p, klaster, **kw) for i in range(n)]


# ------------------------------------------------------------------ Q1
def titik_rugi(p: Params, klaster: str = "A", kolom: str = "kantong_2m", **kw) -> dict:
    g = grid(p, klaster, **kw)
    rugi = [r["jarak_rute_km"] for r in g if r[kolom] < -1e-9]
    if not rugi:
        return dict(mulai=None, akhir=None, n_titik=0, rugi_terus_sampai_akhir=False, n_grid=len(g))
    mulai = rugi[0]
    terus = all(r[kolom] < -1e-9 for r in g if r["jarak_rute_km"] >= mulai)
    return dict(mulai=mulai, akhir=rugi[-1], n_titik=len(rugi), rugi_terus_sampai_akhir=terus, n_grid=len(g))


# ------------------------------------------------------------------ Q2
SKENARIO_Q2 = {
    "Optimis": dict(harga_bensin=9000.0, pengali_kmpl=1.1, throughput=18.0, d=2.05, macet=False),
    "Dasar": dict(harga_bensin=10000.0, pengali_kmpl=1.0, throughput=15.0, d=2.7, macet=False),
    "Pesimis": dict(harga_bensin=11000.0, pengali_kmpl=0.9, throughput=12.0, d=3.6, macet=True),
}


def _p_skenario(p: Params, s: dict) -> Params:
    arm = tuple((k, kl, kmpl * s["pengali_kmpl"], r, h, w) for k, kl, kmpl, r, h, w in p.armada)
    return p.with_(harga_bensin=s["harga_bensin"], throughput=s["throughput"], armada=arm)


def q2(p: Params, skenario: dict | None = None, harga_bensin_relatif: bool = False) -> list[dict]:
    """% target UMK per skenario x klaster. Bila harga_bensin_relatif, skenario memakai pengali dari p.harga_bensin."""
    sk = skenario or SKENARIO_Q2
    rows = []
    for nama, s in sk.items():
        s = dict(s)
        if harga_bensin_relatif:
            s["harga_bensin"] = p.harga_bensin * s["harga_bensin"] / 10000.0
        ps = _p_skenario(p, s)
        for kl in ("A", "B"):
            r = titik(s["d"], ps, kl, macet=s["macet"])
            rows.append(dict(skenario=nama, klaster=kl, jarak_km=s["d"], untung_per_antaran=r["untung_kurir_per_antaran"],
                             antaran_per_hari=r["antaran_hari_realistis"], kapasitas=r["kapasitas_antaran_hari"],
                             penghasilan_bulan=r["penghasilan_bulan"], persen_umk=r["penghasilan_bulan"] / target_bulan(ps),
                             untung_per_jam=r["untung_kurir_per_jam"]))
    for kl in ("A", "B"):
        d = 2.7
        r = titik(d, p, kl, upah_penuh=upah_amplop(d, p))
        rows.append(dict(skenario="Upah maks (2M tidak rugi)", klaster=kl, jarak_km=d, untung_per_antaran=r["untung_kurir_per_antaran"],
                         antaran_per_hari=r["antaran_hari_realistis"], kapasitas=r["kapasitas_antaran_hari"],
                         penghasilan_bulan=r["penghasilan_bulan"], persen_umk=r["penghasilan_bulan"] / target_bulan(p),
                         untung_per_jam=r["untung_kurir_per_jam"]))
    return rows


def kebutuhan_target(p: Params, d: float = 2.7, klaster: str = "A") -> dict:
    """Upah & ongkir per antaran yang dibutuhkan agar kurir capai target pada kapasitas waktu penuh."""
    r = titik(d, p, klaster)
    kap = r["kapasitas_antaran_hari"]
    upah_t = (target_bulan(p) / p.hari_kerja / kap + r["biaya_motor_per_antaran"]) / f_upah(p)
    ongkir_t = (upah_t * f_upah(p) + biaya_cabang(p)) / f_ongkir(p)
    return dict(jarak_km=d, kapasitas=kap,
                antaran_dibutuhkan=math.ceil(target_bulan(p) / p.hari_kerja / r["untung_kurir_per_antaran"]),
                upah_target=upah_t, ongkir_target=ongkir_t, pembanding=r["pembanding"],
                gap_per_order=ongkir_t - r["pembanding"],
                gap_per_kurir_bulan=(ongkir_t - r["pembanding"]) * kap * p.hari_kerja)


# ------------------------------------------------------------------ Q3 (tornado)
SEBARAN_DEKAT = (0.6, 0.3, 0.1)
SEBARAN_JAUH = (0.2, 0.4, 0.4)


def jarak_rata2(p: Params, sebaran: tuple | None = None) -> float:
    w = sebaran or p.sebaran
    return sum(wi * di for wi, di in zip(w, p.jarak_wakil)) / sum(w)


def _skala_kmpl(p: Params, f: float) -> Params:
    return p.with_(armada=tuple((k, kl, kmpl * f, r, h, w) for k, kl, kmpl, r, h, w in p.armada))


def tornado(p: Params, d: float | None = None, klaster: str = "A", rentang: float = 0.2, tambahan_audit: bool = True) -> list[dict]:
    """Q3: geser satu variabel +/- rentang, ukur perubahan ongkir minimum (tanpa pembulatan, seperti T6 Excel),
    penghasilan kurir/bulan, dan titik rugi 2M. Kolom 'minus' = variabel turun (sebaran: skenario Dekat)."""
    d0 = jarak_rata2(p) if d is None else d

    def ukur(pp: Params, dd: float):
        return (ongkir_minimum(dd, pp, bulat=False), titik(dd, pp, klaster)["penghasilan_bulan"], titik_rugi(pp, klaster)["mulai"])

    o0, h0, r0 = ukur(p, d0)
    lo, hi = 1 - rentang, 1 + rentang
    var = [
        ("Upah dasar", p.with_(upah_dasar=p.upah_dasar * lo), p.with_(upah_dasar=p.upah_dasar * hi), d0, d0, False),
        ("Upah per km", p.with_(upah_per_km=p.upah_per_km * lo), p.with_(upah_per_km=p.upah_per_km * hi), d0, d0, False),
        ("Efisiensi km/liter", _skala_kmpl(p, lo), _skala_kmpl(p, hi), d0, d0, False),
        ("Harga bensin", p.with_(harga_bensin=p.harga_bensin * lo), p.with_(harga_bensin=p.harga_bensin * hi), d0, d0, False),
        ("Throughput (antaran/hari)", p.with_(throughput=p.throughput * lo), p.with_(throughput=p.throughput * hi), d0, d0, False),
        ("Sebaran jarak (Dekat vs Jauh)", p, p, jarak_rata2(p, SEBARAN_DEKAT), jarak_rata2(p, SEBARAN_JAUH), False),
    ]
    if tambahan_audit:
        var += [
            ("Overhead harian cabang", p.with_(overhead_harian=p.overhead_harian * lo), p.with_(overhead_harian=p.overhead_harian * hi), d0, d0, True),
            ("Tingkat order gagal", p.with_(p_gagal=p.p_gagal * lo), p.with_(p_gagal=p.p_gagal * hi), d0, d0, True),
            ("Tarif pembanding minimum", p.with_(tarif_min=p.tarif_min * lo), p.with_(tarif_min=p.tarif_min * hi), d0, d0, True),
        ]
    out = []
    for nama, p_lo, p_hi, d_lo, d_hi, tambahan in var:
        a, b = ukur(p_lo, d_lo), ukur(p_hi, d_hi)
        out.append(dict(
            variabel=nama, tambahan_audit=tambahan,
            d_ongkir_minus=a[0] - o0, d_ongkir_plus=b[0] - o0, swing_ongkir=abs(b[0] - a[0]),
            d_hasil_minus=a[1] - h0, d_hasil_plus=b[1] - h0, swing_hasil=abs(b[1] - a[1]),
            rugi_minus=a[2], rugi_plus=b[2], rugi_dasar=r0,
        ))
    return out


# ------------------------------------------------------------------ Q4
def q4(p: Params, covers=(1, 2, 3, 4, 5), dmaxs=(6, 8, 10, 12, 15), klaster: str = "A") -> list[dict]:
    base = titik_rugi(p, klaster)["mulai"]
    out = []
    for c in covers:
        for m in dmaxs:
            pc = p.with_(d_cover=float(c), d_maks=float(m))
            tr = titik_rugi(pc, klaster)
            out.append(dict(d_cover=c, d_maks=m, rugi_mulai=tr["mulai"], n_titik_rugi=tr["n_titik"],
                            rugi_terus=tr["rugi_terus_sampai_akhir"],
                            kesimpulan_q1_berlaku=(tr["mulai"] is not None and base is not None and abs(tr["mulai"] - base) < 1e-9)))
    return out


# ------------------------------------------------------------------ Q5
OPSI = ("O0", "O1", "O2", "O3", "O4")
NAMA_OPSI = {
    "O0": "Skema sekarang", "O1": "Upah dibatasi amplop", "O2": "Radius <= 2 km",
    "O3": "Ongkir fleksibel (= ongkir minimum)", "O4": "Subsidi 2M menutup selisih",
}


def _hasil_opsi(op: str, d: float, p: Params, klaster: str) -> dict:
    if op == "O1":
        return titik(d, p, klaster, upah_penuh=min(upah(d, p), upah_amplop(d, p)))
    if op == "O3":
        return titik(d, p.with_(rasio_batas=1e9), klaster)
    return titik(d, p, klaster)


def q5(p: Params, sebaran: tuple | None = None, klaster: str = "A", metode: str = "wakil", n_sub: int = 200) -> list[dict]:
    """Bandingkan O0-O4.
    metode='wakil'  : seperti Ida, tiap bucket diwakili satu jarak (1 / 3 / 5,5 km).
    metode='seragam': tiap bucket diintegrasikan merata di rentang generator (0,3-2 / 2-4 / 4-8 km)."""
    w = sebaran or p.sebaran
    rows = []
    for op in OPSI:
        layani = (1, 0, 0) if op == "O2" else (1, 1, 1)
        pts = []   # (bobot, hasil)
        for i in range(3):
            if not layani[i] or w[i] <= 0:
                continue
            if metode == "wakil":
                pts.append((w[i], _hasil_opsi(op, p.jarak_wakil[i], p, klaster)))
            else:
                lo, hi = p.rentang_bucket[i]
                for k in range(n_sub):
                    d = lo + (hi - lo) * (k + 0.5) / n_sub
                    pts.append((w[i] / n_sub, _hasil_opsi(op, d, p, klaster)))
        share = sum(b for b, _ in pts)
        avg = lambda key: sum(b * h[key] for b, h in pts) / share  # noqa: E731
        tm = avg("waktu_per_antaran_menit")
        n = min(p.throughput, kapasitas_harian(tm, p))
        net = avg("untung_kurir_per_antaran")
        rows.append(dict(
            opsi=op, nama=NAMA_OPSI[op], order_terlayani=share, kantong_2m_rata2=avg("kantong_2m"),
            subsidi_2m_per_order=sum(b * max(0.0, -h["kantong_2m"]) for b, h in pts) / share,
            porsi_order_2m_rugi=sum(b for b, h in pts if h["kantong_2m"] < -1e-9) / share,
            untung_kurir_per_antaran=net, antaran_per_hari=n, penghasilan_kurir_bulan=net * n * p.hari_kerja,
            persen_umk=net * n * p.hari_kerja / target_bulan(p),
        ))
    return rows


# ------------------------------------------------------------------ Q6 (ILUSTRATIF; detour & menit/drop = ASUMSI)
def q6(p: Params, d: float = 3.0, detour_km: float = 0.5, menit_per_drop: float = 8.0, k_max: int = 8,
       klaster: str = "A", upah_per_order: float | None = None) -> list[dict]:
    um = upah_amplop(d, p) if upah_per_order is None else upah_per_order
    bm = biaya_motor_per_km(p, klaster)
    tgt = target_per_jam(p)
    out = []
    for k in range(1, k_max + 1):
        rute = d + (k - 1) * detour_km
        t = p.faktor_pp * rute / p.v_normal * 60 + p.waktu_tetap + (k - 1) * menit_per_drop
        net = k * um * f_upah(p) - bm * p.faktor_pp * rute
        out.append(dict(order_per_trip=k, waktu_trip_menit=t, untung_kurir_per_trip=net,
                        untung_kurir_per_jam=net / t * 60, target_per_jam=tgt, capai_target=net / t * 60 >= tgt))
    return out
