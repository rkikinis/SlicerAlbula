#!/usr/bin/env python3
"""Fetch the public test corpus from NCI Imaging Data Commons into a DICOM folder.

    uv run --python 3.12 --with idc-index==0.10.2 Contents/data/fetch-idc.py [--into DIR] [--case CASE_ID]...
    uv run --python 3.12 --with idc-index==0.10.2 Contents/data/fetch-idc.py --list

There is no data in this repository. `Contents/data/series.tsv` names each series by its
SeriesInstanceUID -- the identifier IDC indexes it under -- and this fetches them. No login, no
API key, no TCIA account: IDC serves these from public storage.

WHY IDC RATHER THAN TCIA'S DOWNLOADER: a series resolves from a single stable identifier a reader
can paste, instead of a collection name plus a hunt through a portal, and it is the same route
haversack already takes an input by. Where a case is genuinely not in IDC this script says so and
skips it rather than growing a second mechanism.

AFTER FETCHING, point 3D Slicer's DICOM module at the folder and import it, or start
SlicerAlbula and add the folder as a database. Nothing here writes to a Slicer database
directly: indexing belongs to the code that owns it.

THE COLLECTION IS RECORDED AS IT IS FETCHED. The DICOM files do not carry it -- TCIA's
de-identified headers have no ClinicalTrialProtocolID -- and the manifest does. So each series'
collection goes into the provenance store (Contents/Slicer/provenance.sqlite, SlicerAlbula's own, created
if absent) as it lands, source "fetch", where the application's browser shows it and where a
person can overrule it. Ron, 2026-09-11: "for future fetches, record it at fetch time."
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "series.tsv"
PROVENANCE = HERE.parent / "Slicer" / "provenance.sqlite"
COLUMNS = ("case_id", "collection", "modality", "instances", "purpose", "series_instance_uid")


def read_manifest() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with MANIFEST.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) != len(COLUMNS):
                sys.exit(f"{MANIFEST.name}: expected {len(COLUMNS)} tab-separated fields, got "
                         f"{len(parts)} in:\n  {line}")
            rows.append(dict(zip(COLUMNS, parts)))
    return rows


def record_collection(uid: str, collection: str) -> None:
    """One row per series in the provenance store. A person's answer outranks this one."""
    import sqlite3, time
    PROVENANCE.parent.mkdir(parents=True, exist_ok=True)
    pv = sqlite3.connect(PROVENANCE)
    pv.execute("""CREATE TABLE IF NOT EXISTS SeriesAttributes (
        SeriesInstanceUID TEXT NOT NULL, Key TEXT NOT NULL, Value TEXT NOT NULL,
        Source TEXT NOT NULL, Recorded TEXT NOT NULL, PRIMARY KEY (SeriesInstanceUID, Key))""")
    cur = pv.execute("SELECT Source FROM SeriesAttributes WHERE SeriesInstanceUID=? AND Key='collection'", (uid,)).fetchone()
    if not (cur and cur[0] == "user"):
        pv.execute("INSERT OR REPLACE INTO SeriesAttributes VALUES (?, 'collection', ?, 'fetch', ?)",
                   (uid, collection, time.strftime("%Y-%m-%dT%H:%M:%S")))
    pv.commit(); pv.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--into", default=str(HERE / "dicom"), metavar="DIR",
                    help="where to write the DICOM files (default: Contents/data/dicom)")
    ap.add_argument("--case", action="append", metavar="CASE_ID",
                    help="fetch only this case; repeatable. Default: all of them")
    ap.add_argument("--list", action="store_true", help="print the corpus and exit, fetching nothing")
    args = ap.parse_args()

    rows = read_manifest()
    if args.case:
        wanted = set(args.case)
        unknown = wanted - {r["case_id"] for r in rows}
        if unknown:
            sys.exit(f"not in {MANIFEST.name}: {', '.join(sorted(unknown))}")
        rows = [r for r in rows if r["case_id"] in wanted]

    if args.list:
        for r in rows:
            print(f'{r["case_id"]:<16} {r["collection"]:<28} {r["modality"]:<4} '
                  f'{r["instances"]:>4} instances   {r["purpose"]}')
        return 0

    try:
        from idc_index import IDCClient
    except ImportError:
        sys.exit("idc-index is not installed. Run this as:\n"
                 "    uv run --python 3.12 --with idc-index==0.10.2 Contents/data/fetch-idc.py")

    dest = Path(args.into)
    dest.mkdir(parents=True, exist_ok=True)
    client = IDCClient()

    missing: list[dict[str, str]] = []
    for r in rows:
        label = f'{r["case_id"]} {r["modality"]} ({r["instances"]} instances)'
        print(f"fetching {label} ...", flush=True)
        try:
            client.download_dicom_series(r["series_instance_uid"], downloadDir=str(dest), quiet=True)
            record_collection(r["series_instance_uid"], r["collection"])
        except Exception as e:                                  # noqa: BLE001 - report, do not stop
            # NOT FATAL, AND SAID OUT LOUD. One series IDC cannot serve should not cost the other
            # five; a silent skip would leave a corpus that is quietly incomplete.
            print(f"  SKIPPED {label}: {e}", file=sys.stderr)
            missing.append(r)

    got = len(rows) - len(missing)
    print(f"\n{got} of {len(rows)} series fetched into {dest}")
    if missing:
        print("\nIDC did not serve these:")
        for r in missing:
            print(f'  {r["case_id"]:<16} {r["collection"]:<28} {r["series_instance_uid"]}')
        print("\nThey are still public: look the UID up at https://portal.imaging.datacommons.cancer.gov")
        return 1
    print("\nNext: import this folder in 3D Slicer's DICOM module, or add it as a database in "
          "SlicerAlbula.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
