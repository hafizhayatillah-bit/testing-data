"""Fixture bersama audit. DATA SINTETIS / ASUMSI, bukan data lapangan.

Setiap tes memanggil `catat(...)` agar hasilnya (PASS/FAIL/SKIPPED + nilai aktual) tersimpan ke
datasets/phase2/audit_results.json dan datasets/phase3/parity_results.json untuk REPORT.md.
"""
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]          # sandbox/ida_simulation
sys.path.insert(0, str(HERE))

RUN1 = HERE / "datasets" / "phase1" / "run1"        # output Fase 1 (pipeline Ida dijalankan ulang)
ORIG = HERE.parent / "ida_v2_original"              # kiriman Ida (read-only)
V1 = HERE.parent / "ida_v1_original"
WB22 = HERE.parent / "ida_workbooks" / "Draft_DS_Kurir_v2.2.xlsx"
IDA_COPY = HERE / "ida_copy"

_HASIL: dict[str, list] = {"audit": [], "parity": []}


def _json(x):
    try:
        json.dumps(x)
        return x
    except TypeError:
        return str(x)


@pytest.fixture
def catat(request):
    grup = "parity" if "parity" in request.node.fspath.basename else "audit"

    def _catat(id_, klaim, expected, aktual, status, catatan=""):
        _HASIL[grup].append(dict(id=id_, klaim=klaim, expected=_json(expected), aktual=_json(aktual),
                                 status=status, catatan=catatan, test=request.node.name))
        if status == "SKIPPED":
            pytest.skip(f"{id_}: {catatan}")
        assert status == "PASS", f"{id_} {klaim}: expected={expected!r} aktual={aktual!r}. {catatan}"
    return _catat


def need(path: Path):
    if not path.exists():
        pytest.skip(f"file tidak ada: {path}")
    return path


def pytest_sessionfinish(session, exitstatus):
    for grup, sub in (("audit", "phase2"), ("parity", "phase3")):
        if _HASIL[grup]:
            out = HERE / "datasets" / sub
            out.mkdir(parents=True, exist_ok=True)
            (out / f"{grup}_results.json").write_text(
                json.dumps({"label": "DATA SINTETIS / ASUMSI, bukan data lapangan", "hasil": _HASIL[grup]},
                           indent=1, ensure_ascii=False), encoding="utf-8")
