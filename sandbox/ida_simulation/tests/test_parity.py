"""FASE 3 - Tes paritas: costmodel.py (independen) vs grid_jarak_hasil.csv dan vs model_biaya.py Ida.
DATA SINTETIS / ASUMSI, bukan data lapangan. Toleransi 1 rupiah; selisih = temuan.

model_biaya.py diimpor dari salinan sandbox (ida_copy), BUKAN dari ida_v2_original.
Tabel paritas ditulis ke datasets/phase3/parity_table.csv.
"""
import importlib
import sys

import numpy as np
import pandas as pd
import pytest

import costmodel as cm
from conftest import RUN1, IDA_COPY, HERE, need

JARAK = [round(0.5 + 0.25 * i, 2) for i in range(39)]            # 0,5 .. 10 km
KOLOM_RP = ["upah_penuh", "upah_efektif", "biaya_motor_per_antaran", "untung_kurir_per_antaran", "biaya_cabang_per_antaran",
            "ongkir_minimum_2m", "pembanding", "batas_ongkir", "ongkir_disarankan", "kantong_2m", "ongkir_lama", "kantong_2m_lama",
            "penghasilan_bulan"]
KOLOM_LAIN = ["waktu_per_antaran_menit", "kapasitas_antaran_hari", "biaya_motor_per_km"]
TOL = 1.0


def mine(klaster, **kw):
    p = cm.IDA.with_(**kw) if kw else cm.IDA
    return pd.DataFrame([cm.titik(d, p, klaster) for d in JARAK])


@pytest.fixture(scope="module")
def ida_mod():
    if not (IDA_COPY / "src" / "model_biaya.py").exists():
        pytest.skip("ida_copy/src/model_biaya.py tidak ada")
    sys.path.insert(0, str(IDA_COPY))
    mb = importlib.import_module("src.model_biaya")
    P = mb.load_params(need(RUN1 / "data/raw/parameter_model_raw.csv"))
    M = mb.load_motor(need(RUN1 / "data/raw/motor_klaster_raw.csv"))
    return mb, P, M


def _maxdiff(a: pd.DataFrame, b: pd.DataFrame, cols):
    return {c: float((a[c].astype(float) - b[c].astype(float)).abs().max()) for c in cols}


@pytest.mark.parametrize("klaster", ["A", "B"])
def test_P1_vs_grid_jarak_hasil(klaster, catat):
    g = pd.read_csv(need(RUN1 / "data/clean/grid_jarak_hasil.csv"))
    g = g[(g.klaster == klaster) & g.jarak_rute_km.isin(JARAK)].sort_values("jarak_rute_km").reset_index(drop=True)
    m = mine(klaster)
    cols = [c for c in KOLOM_RP + KOLOM_LAIN if c in g.columns]
    md = _maxdiff(m, g, cols)
    # kolom versi 'bisa ditagih' (batas dibulatkan ke bawah Rp500)
    mb = mine(klaster, bulatkan_batas=True)
    md["kantong_2m_bayar"] = float((mb["kantong_2m"] - g["kantong_2m_bayar"]).abs().max())
    md["ongkir_disarankan_bayar"] = float((mb["ongkir_disarankan"] - g["ongkir_disarankan_bayar"]).abs().max())
    worst = max(md, key=md.get)
    catat(f"P1-{klaster}", f"costmodel vs grid_jarak_hasil.csv klaster {klaster} ({len(JARAK)} titik x {len(md)} kolom)",
          f"selisih <= Rp{TOL:g}", f"selisih maks {md[worst]:.4f} ({worst})", "PASS" if md[worst] <= TOL else "FAIL",
          "CSV Ida dibulatkan 2 desimal")


@pytest.mark.parametrize("klaster", ["A", "B"])
def test_P2_vs_model_biaya_ida(klaster, ida_mod, catat):
    mb, P, M = ida_mod
    ida = pd.DataFrame([mb.hitung(d, klaster, P, M) for d in JARAK])
    m = mine(klaster)
    cols = [c for c in KOLOM_RP + KOLOM_LAIN if c in ida.columns]
    md = _maxdiff(m, ida, cols)
    worst = max(md, key=md.get)
    if klaster == "A":
        out = HERE / "datasets" / "phase3"
        out.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"jarak_km": JARAK, "kantong_2m_ida": ida["kantong_2m"], "kantong_2m_independen": m["kantong_2m"],
                      "selisih_kantong": m["kantong_2m"] - ida["kantong_2m"], "untung_kurir_ida": ida["untung_kurir_per_antaran"],
                      "untung_kurir_independen": m["untung_kurir_per_antaran"],
                      "selisih_untung": m["untung_kurir_per_antaran"] - ida["untung_kurir_per_antaran"],
                      "label": cm.LABEL}).round(4).to_csv(out / "parity_table.csv", index=False)
    catat(f"P2-{klaster}", f"costmodel vs model_biaya.hitung() Ida klaster {klaster}", f"selisih <= Rp{TOL:g}",
          f"selisih maks {md[worst]:.2e} ({worst})", "PASS" if md[worst] <= TOL else "FAIL")


def test_P3_q4_vs_tabel_ida(catat):
    t = pd.read_csv(need(RUN1 / "output/tabel/q4_robustness_asumsi_pembanding.csv"), index_col=0)
    q = {(r["d_cover"], r["d_maks"]): r["rugi_mulai"] for r in cm.q4(cm.IDA)}
    beda = []
    for c in t.index:
        for m in t.columns:
            ida = str(t.loc[c, m])
            ida_v = None if ida.strip() == ">10" else float(ida)
            mine_v = q[(int(c), int(m))]
            if (ida_v is None) != (mine_v is None) or (ida_v is not None and abs(ida_v - mine_v) > 1e-9):
                beda.append((c, m, ida, mine_v))
    catat("P3", "Q4 heatmap 25 sel: costmodel vs q4_robustness_asumsi_pembanding.csv", "25/25 sama", f"{25 - len(beda)}/25 sama {beda}",
          "PASS" if not beda else "FAIL")


def test_P4_q5_vs_tabel_ida(catat):
    t = pd.read_csv(need(RUN1 / "output/tabel/q5_opsi_kebijakan.csv"))
    t["opsi"] = t["opsi"].str.slice(0, 2)
    m = pd.DataFrame(cm.q5(cm.IDA, metode="wakil"))
    j = t.merge(m, on="opsi", suffixes=("_ida", "_ind"))
    cols = ["kantong_2m_rata2", "subsidi_2m_per_order", "penghasilan_kurir_bulan"]
    md = {c: float((j[c + "_ida"] - j[c + "_ind"]).abs().max()) for c in cols}
    md["porsi_order_2m_rugi"] = float((j["porsi_order_2m_rugi_ida"] - j["porsi_order_2m_rugi_ind"]).abs().max())
    worst = max(cols, key=md.get)
    ok = md[worst] <= TOL and md["porsi_order_2m_rugi"] < 1e-9
    catat("P4", "Q5 O0-O4: costmodel vs q5_opsi_kebijakan.csv", f"selisih <= Rp{TOL:g}", md, "PASS" if ok else "FAIL")


def test_P5_q6_vs_tabel_ida(catat):
    t = pd.read_csv(need(RUN1 / "output/tabel/q6_batching_ilustratif.csv"))
    m = pd.DataFrame(cm.q6(cm.IDA))
    sel = float((t["untung_kurir_per_jam"] - m["untung_kurir_per_jam"]).abs().max())
    catat("P5", "Q6 batching: costmodel vs q6_batching_ilustratif.csv (Ida membulatkan ke rupiah)", "selisih <= Rp1",
          f"selisih maks Rp{sel:.3f}", "PASS" if sel <= TOL else "FAIL")
