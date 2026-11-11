"""FASE 1 - Reproduksi pipeline Ida (DATA SINTETIS / ASUMSI, bukan data lapangan).

Jalankan dari folder sandbox/ida_simulation:
    .venv/Scripts/python phase1/reproduce.py

Langkah:
  1. Kondisi bersih: hapus semua file hasil (data/raw/*.csv, data/clean/*, data/model/*, output/*) di ida_copy,
     sisakan hanya kode + data/raw/Draft_DS_Kurir_v2.xlsx (satu-satunya input).
  2. Jalankan `python run_all.py` (subprocess, -W default agar warning terlihat), catat waktu, stdout, stderr.
  3. Hash SHA-256 semua output; salin ke datasets/phase1/run{N}/.
  4. Ulangi; bandingkan run1 vs run2 dan run vs file kiriman Ida (ida_v2_original, read-only).
Hasil ringkas: datasets/phase1/phase1_result.json
"""
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]           # sandbox/ida_simulation
COPY = HERE / "ida_copy"
ORIG = HERE.parent / "ida_v2_original"               # read-only, hanya dibaca
OUT = HERE / "datasets" / "phase1"
INPUT_KEEP = {"data/raw/Draft_DS_Kurir_v2.xlsx"}
GEN_DIRS = ["data/raw", "data/clean", "data/model", "output/tabel", "output/grafik"]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def files_under(root: Path, rel_dirs):
    out = {}
    for d in rel_dirs:
        for p in sorted((root / d).glob("*")):
            if p.is_file():
                out[p.relative_to(root).as_posix()] = p
    return out


def clean_state():
    removed = []
    for rel, p in files_under(COPY, GEN_DIRS).items():
        if rel not in INPUT_KEEP:
            p.unlink()
            removed.append(rel)
    for pyc in COPY.rglob("__pycache__"):
        shutil.rmtree(pyc)
    return removed


def run_once(n: int):
    removed = clean_state()
    t = time.time()
    proc = subprocess.run([sys.executable, "-W", "default", "run_all.py"], cwd=COPY,
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    dt = time.time() - t
    dest = OUT / f"run{n}"
    if dest.exists():
        shutil.rmtree(dest)
    produced = files_under(COPY, GEN_DIRS)
    hashes = {}
    for rel, p in produced.items():
        hashes[rel] = sha(p)
        (dest / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dest / rel)
    (dest / "stdout.txt").write_text(proc.stdout, encoding="utf-8")
    (dest / "stderr.txt").write_text(proc.stderr, encoding="utf-8")
    warnings = [l for l in proc.stderr.splitlines() if "Warning" in l]
    return dict(run=n, returncode=proc.returncode, detik=round(dt, 2), n_file_dihapus_sebelum=len(removed),
                n_file_dihasilkan=len(produced), warnings=warnings, stderr_tail=proc.stderr[-2000:],
                hashes=hashes)


def compare(h1: dict, h2: dict):
    keys = sorted(set(h1) | set(h2))
    rows = []
    for k in keys:
        a, b = h1.get(k), h2.get(k)
        rows.append(dict(file=k, sama=(a == b and a is not None), hanya_di=("kiri" if b is None else "kanan" if a is None else "")))
    return rows


def content_compare(run_dir: Path, orig_root: Path):
    """Bandingkan isi (bukan byte): CRLF dinormalisasi; CSV yang masih beda dibandingkan numerik (pandas)."""
    import pandas as pd
    rows = []
    for rel, p in files_under(orig_root, GEN_DIRS).items():
        q = run_dir / rel
        if not q.exists():
            rows.append(dict(file=rel, status="TIDAK DIHASILKAN pipeline", detail="ada di kiriman Ida, tidak ada kode yang membuatnya"))
            continue
        if rel.endswith(".png") or rel.endswith(".xlsx"):
            rows.append(dict(file=rel, status="BINER", detail="byte sama" if sha(p) == sha(q) else "byte beda (wajar utk PNG beda versi matplotlib)"))
            continue
        a = p.read_bytes().replace(b"\r\n", b"\n")
        b = q.read_bytes().replace(b"\r\n", b"\n")
        if a == b:
            rows.append(dict(file=rel, status="IDENTIK (setelah CRLF->LF)", detail=""))
            continue
        detail = ""
        if rel.endswith(".csv"):
            try:
                x, y = pd.read_csv(p), pd.read_csv(q)
                if x.shape != y.shape or list(x.columns) != list(y.columns):
                    detail = f"bentuk/kolom beda {x.shape} vs {y.shape}"
                else:
                    num = x.select_dtypes("number").columns
                    mx = float((x[num] - y[num]).abs().max().max()) if len(num) else 0.0
                    oth = [c for c in x.columns if c not in num and not x[c].astype(str).equals(y[c].astype(str))]
                    detail = f"selisih numerik maks {mx:.3g}; kolom non-numerik beda: {oth}"
            except Exception as e:  # noqa: BLE001
                detail = f"tidak bisa dibaca: {e}"
        rows.append(dict(file=rel, status="BEDA ISI", detail=detail))
    return rows


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    r1 = run_once(1)
    r2 = run_once(2)
    orig = {rel: sha(p) for rel, p in files_under(ORIG, GEN_DIRS).items()}
    res = dict(
        label="DATA SINTETIS / ASUMSI, bukan data lapangan",
        python=sys.version,
        run1={k: v for k, v in r1.items() if k != "hashes"},
        run2={k: v for k, v in r2.items() if k != "hashes"},
        run1_vs_run2=compare(r1["hashes"], r2["hashes"]),
        run1_vs_kiriman_ida=compare(r1["hashes"], orig),
        run1_vs_kiriman_ida_isi=content_compare(OUT / "run1", ORIG),
        hashes_run1=r1["hashes"], hashes_run2=r2["hashes"], hashes_kiriman_ida=orig,
    )
    (OUT / "phase1_result.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    for nm in ("run1", "run2"):
        r = res[nm]
        print(nm, "rc", r["returncode"], "detik", r["detik"], "file", r["n_file_dihasilkan"], "warnings", len(r["warnings"]))
    same12 = sum(x["sama"] for x in res["run1_vs_run2"])
    print(f"run1 vs run2: {same12}/{len(res['run1_vs_run2'])} identik")
    diff = [x for x in res["run1_vs_kiriman_ida"] if not x["sama"]]
    print(f"run1 vs kiriman Ida: {len(res['run1_vs_kiriman_ida']) - len(diff)}/{len(res['run1_vs_kiriman_ida'])} identik")
    print("Perbandingan ISI vs kiriman Ida:")
    for x in res["run1_vs_kiriman_ida_isi"]:
        print(f"  {x['status']:<28} {x['file']}  {x['detail']}")


if __name__ == "__main__":
    main()
