# testing-data

> **DATA SINTETIS / ASUMSI, bukan data lapangan.**

Sandbox audit independen pipeline Data Science tim 2M Sembako (capstone Asah 2026): cost model kurir, order log sintetis, analisis Q1–Q6, data ETA.

- Simulator (Streamlit): `sandbox/ida_simulation/app.py`
- Laporan audit: [`sandbox/ida_simulation/REPORT.md`](sandbox/ida_simulation/REPORT.md)
- Cara jalan & isi folder: [`sandbox/ida_simulation/README.md`](sandbox/ida_simulation/README.md)

## Struktur

| Folder | Isi |
|---|---|
| `sandbox/ida_v2_original/` | Pipeline DS v2 kiriman Ida (asli, jangan diedit) |
| `sandbox/ida_v1_original/` | Dataset & notebook V1 |
| `sandbox/ida_workbooks/` | `Draft_DS_Kurir_v2.2.xlsx` |
| `sandbox/_download/` | Arsip unduhan Drive + SHA-256 |
| `sandbox/ida_simulation/` | Audit, model independen, simulator, tes |

## Deploy di Streamlit Community Cloud

share.streamlit.io → **Create app** → repo `hafizhayatillah-bit/testing-data`, branch `main`, main file `sandbox/ida_simulation/app.py`, Advanced settings → Python **3.12**.

## Jalankan lokal

```bash
cd sandbox/ida_simulation
py -3.12 -m venv .venv && .venv/Scripts/python -m pip install -r requirements.lock
.venv/Scripts/streamlit run app.py
```
