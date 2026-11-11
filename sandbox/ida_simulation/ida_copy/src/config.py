"""Konfigurasi path dan konstanta bersama untuk paket DS 2M Sembako."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
CLEAN = ROOT / "data" / "clean"
OUT_T = ROOT / "output" / "tabel"
OUT_G = ROOT / "output" / "grafik"
DOCS = ROOT / "docs"
XLSX = RAW / "Draft_DS_Kurir_v2.xlsx"

SEED = 20261109          # seed tetap -> data sintetis identik setiap dijalankan
N_ORDER_SINTETIS = 3000  # jumlah baris order sintetis
LABEL_SINTETIS = "SINTETIS_SIMULASI"   # label wajib pada semua data buatan

for _d in (RAW, CLEAN, OUT_T, OUT_G, DOCS):
    _d.mkdir(parents=True, exist_ok=True)
