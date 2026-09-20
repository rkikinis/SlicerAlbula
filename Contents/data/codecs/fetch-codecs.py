#!/usr/bin/env python3
"""Fetch the compressed-pixel-data samples named in codecs.tsv, and their uncompressed truths.

    python3 Contents/data/codecs/fetch-codecs.py [--into DIR]        (default: Contents/data/dicom/codecs)

Every file comes from the pydicom project (MIT license), at a pinned tag or commit, so the same
bytes arrive every time. Each downloaded file is opened and its transfer syntax checked against
the manifest; a mismatch is reported and the file removed. The real clinical series with
compressed pixel data (NLST, MIDRC, TCGA-UCEC, DBT) are in ../series.tsv and come via fetch-idc.py.
"""
from __future__ import annotations
import argparse, csv, sys, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "codecs.tsv"
SOURCES = {
    "pydicom": "https://raw.githubusercontent.com/pydicom/pydicom/v3.0.1/src/pydicom/data/test_files/",
    "pydicom-data": "https://raw.githubusercontent.com/pydicom/pydicom-data/abc42b90985fb6cf385aa4af766d2c9c94a257a4/data_store/data/",
}
COLUMNS = ("transfer_syntax", "name", "file", "source", "what", "truth_file")


def rows() -> list[dict[str, str]]:
    out = []
    with MANIFEST.open() as f:
        for line in f:
            if not line.strip() or line.startswith("#"): continue
            out.append(dict(zip(COLUMNS, line.rstrip("\n").split("\t"))))
    return out


def fetch(url: str, dest: Path) -> bool:
    if dest.exists(): return True
    try:
        with urllib.request.urlopen(url, timeout=60) as r: data = r.read()
    except Exception as e:
        print(f"  could not fetch {url}: {e}"); return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return True


def transfer_syntax(path: Path) -> str:
    try:
        import pydicom
        return str(pydicom.dcmread(path, stop_before_pixels=True, force=True).file_meta.get("TransferSyntaxUID", ""))
    except ImportError:
        return "?"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--into", default=str(HERE.parent / "dicom" / "codecs"))
    a = ap.parse_args()
    into = Path(a.into)
    ok = bad = 0
    for r in rows():
        d = into / r["transfer_syntax"]
        dest = d / r["file"]
        # the same file may be in either source tree; try the named one first, then the other
        sources = [r["source"]] + [s for s in SOURCES if s != r["source"]]
        got = any(fetch(SOURCES[s] + r["file"], dest) for s in sources)
        if not got: bad += 1; continue
        ts = transfer_syntax(dest)
        if ts not in ("?", r["transfer_syntax"]):
            print(f"  {r['file']}: transfer syntax {ts}, manifest says {r['transfer_syntax']} -- removed"); dest.unlink(); bad += 1; continue
        if r["truth_file"] != "-":
            got_truth = any(fetch(SOURCES[s] + r["truth_file"], d / r["truth_file"]) for s in sources)
            if not got_truth: print(f"  truth {r['truth_file']} for {r['file']} not fetched")
        ok += 1
        print(f"  {r['transfer_syntax']:26} {r['file']:40} {dest.stat().st_size // 1024:6} KB{'  + ' + r['truth_file'] if r['truth_file'] != '-' else ''}")
    print(f"{ok} files, {bad} problems, in {into}")
    record_collections(into)
    return 1 if bad else 0


def record_collections(into: Path) -> None:
    """Name each sample in SlicerAlbula's Collection column, so the DICOM browser says what a
    row like "5MR2" or "8NM1" is: "codec sample · JPEG 2000 lossless · MR 1024x1024 12-bit".
    Written to the provenance store the way fetch-idc.py records a collection. Ron, 2026-09-19:
    "The studies that you added are very cryptic. How would I know what is what?" """
    store = HERE.parent.parent / "Slicer" / "provenance.sqlite"
    if not store.exists(): return
    try:
        import pydicom, sqlite3, datetime
    except ImportError:
        return
    con = sqlite3.connect(store)
    con.execute("CREATE TABLE IF NOT EXISTS SeriesAttributes (SeriesInstanceUID TEXT NOT NULL, Key TEXT NOT NULL, Value TEXT NOT NULL, Source TEXT NOT NULL, Recorded TEXT NOT NULL, PRIMARY KEY (SeriesInstanceUID, Key))")
    now = datetime.datetime.now().isoformat(timespec="seconds")
    n = 0
    for r in rows():
        for f in [r["file"]] + ([r["truth_file"]] if r["truth_file"] != "-" else []):
            path = into / r["transfer_syntax"] / f
            if not path.exists(): continue
            try: uid = str(pydicom.dcmread(path, stop_before_pixels=True, force=True).get("SeriesInstanceUID", ""))
            except Exception: continue
            if not uid: continue
            what = r["what"].split(";")[0].split(" (")[0]
            label = f"codec sample · {r['name']} · {what}" if f == r["file"] else f"codec sample · uncompressed truth for {r['file']}"
            con.execute("INSERT OR REPLACE INTO SeriesAttributes VALUES (?, 'collection', ?, 'fetch', ?)", (uid, label, now))
            n += 1
    con.commit(); con.close()
    print(f"{n} rows named in the Collection column ({store})")


if __name__ == "__main__":
    sys.exit(main())
