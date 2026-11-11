# Sandbox audit & simulasi pipeline DS Ida (v2)

> **SIMULASI DATA SINTETIS / ASUMSI, bukan data lapangan.** Sandbox uji, BUKAN fitur produksi.

## Jalankan simulator (satu perintah, dari folder ini)

```bash
.venv/Scripts/streamlit run app.py
```

Venv belum ada? Buat dulu: `py -3.12 -m venv .venv && .venv/Scripts/python -m pip install -r requirements.lock`

## Perintah lain

| Tujuan | Perintah |
|---|---|
| Fase 1: jalankan pipeline Ida 2x dari kondisi bersih + bandingkan hash | `.venv/Scripts/python -X utf8 phase1/reproduce.py` |
| Fase 2: audit klaim (PASS/FAIL/SKIPPED + nilai aktual) | `.venv/Scripts/python -X utf8 -m pytest tests/test_audit.py -v` |
| Fase 3: paritas model independen vs Ida (toleransi Rp1) | `.venv/Scripts/python -X utf8 -m pytest tests/test_parity.py -v` |

Fase 2 dan 3 membaca output Fase 1 (`datasets/phase1/run1`), jadi jalankan Fase 1 dulu. FAIL di `test_audit.py` adalah **temuan**, bukan error tes.

## Isi folder

| Path | Isi |
|---|---|
| `REPORT.md` | Laporan audit (Fase 1–3, 5 temuan teratas, yang tidak bisa diuji) |
| `costmodel.py` | Model biaya **independen**, fungsi murni tanpa I/O (siap dipindah ke `data-science/dashboard/`) |
| `app.py` | UI Streamlit (hanya tampilan; semua logika di `costmodel.py`) |
| `phase1/reproduce.py` | Skrip reproduksi Fase 1 |
| `tests/` | `test_audit.py` (Fase 2), `test_parity.py` (Fase 3), `conftest.py` (pencatat hasil) |
| `ida_copy/` | Salinan pipeline Ida yang dijalankan (aslinya `../ida_v2_original/`, read-only, tidak disentuh) |
| `datasets/` | Semua output: `phase1/run1`, `phase1/run2`, `phase1_result.json`, `phase2/*`, `phase3/*` |
| `requirements.lock` | Versi terkunci (Python 3.12.6). `requirements.phase1.lock` = hanya dependensi Ida |

Asal file Ida: folder Google Drive `DataStash` (diunduh 11 Nov 2026), arsip + SHA-256 di `../_download/`.
