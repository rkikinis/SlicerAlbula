#!/usr/bin/env python3
"""Which IDC collection is each series in the DICOM database from?

    uv run --python 3.12 --with idc-index==0.10.2 Contents/data/collections-from-idc.py [--write]

The DICOM files do not say. TCIA's de-identified headers carry no ClinicalTrialProtocolID or
SponsorName, InstitutionName is blank, and the ctkDICOM index has no column for it -- checked on
four public cases on 2026-09-11. So the collection is looked up from IDC's own index, by
SeriesInstanceUID, for every series in the database except the locally made ones (2.25.* UIDs,
which have no collection). Not only TCIA-rooted UIDs: NLST's series keep their own root
(1.2.840.113654.2.55.), which a filter on TCIA's root missed on 2026-09-11. IDC's index is the
judge of what it holds; the script asks about everything.

Without --write this only prints. With --write the answers go into the provenance store
(Contents/Slicer/provenance.sqlite, Ron's own database, never Slicer's index) in a SeriesAttributes table,
source "idc", where the application's browser reads them and where a person can overrule them.
"""
from __future__ import annotations
import sqlite3, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CTK = ROOT / "Contents/Slicer/SlicerDICOMDatabase/ctkDICOM.sql"
PROV = ROOT / "Contents/Slicer/provenance.sqlite"
LOCAL_ROOT = "2.25."

write = "--write" in sys.argv
db = sqlite3.connect(CTK)
rows = db.execute("""
    SELECT p.PatientID, se.SeriesInstanceUID, se.Modality, se.SeriesDescription
    FROM Patients p JOIN Studies st ON st.PatientsUID = p.UID JOIN Series se ON se.StudyInstanceUID = st.StudyInstanceUID
    WHERE se.SeriesInstanceUID NOT LIKE ? ORDER BY p.PatientID""", (LOCAL_ROOT + "%",)).fetchall()
print(f"{len(rows)} series in {CTK.name} (2.25.* local UIDs left out); loading IDC's index (first run downloads it)…", flush=True)

t0 = time.perf_counter()
from idc_index import IDCClient
client = IDCClient()
# The documented way in: DuckDB SQL over the `index` table (idc-index 0.10.2). collection_id is
# the collection; license_short_name is its license, which every result carries and which the
# browser should show beside the collection -- a segmentation of CC BY data inherits the credit.
uids = ",".join("'" + uid + "'" for _, uid, _, _ in rows)
df = client.sql_query(f"SELECT SeriesInstanceUID, collection_id, PatientID, license_short_name FROM index WHERE SeriesInstanceUID IN ({uids})")
print(f"  index queried in {time.perf_counter()-t0:.1f}s", flush=True)
answer = {r.SeriesInstanceUID: r for r in df.itertuples(index=False)}

found, missing = [], []
for pid, uid, mod, desc in rows:
    r = answer.get(uid)
    if r is not None: found.append((pid, uid, mod, str(r.collection_id), str(r.PatientID), str(r.license_short_name)))
    else: missing.append((pid, uid, mod, desc))

print(f"\n{len(found)} resolved, {len(missing)} not in IDC\n")
print(f"{'patient (ours)':<18} {'collection':<28} {'license':<11} {'IDC patient':<14} mod")
last = None
for pid, uid, mod, coll, idcpid, lic in found:
    if pid != last: print(f"{pid:<18} {coll:<28} {lic:<11} {idcpid:<14} {mod}"); last = pid
if missing:
    print("\nNOT IN IDC (a person has to say, or it stays blank):")
    for pid, uid, mod, desc in missing: print(f"  {pid:<18} {mod:<4} {desc[:40]:<40} {uid[-24:]}")

if write:
    pv = sqlite3.connect(PROV)
    pv.execute("""CREATE TABLE IF NOT EXISTS SeriesAttributes (
        SeriesInstanceUID TEXT NOT NULL, Key TEXT NOT NULL, Value TEXT NOT NULL,
        Source TEXT NOT NULL, Recorded TEXT NOT NULL, PRIMARY KEY (SeriesInstanceUID, Key))""")
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    n = 0
    for pid, uid, mod, coll, _, lic in found:
        for key, val in (("collection", coll), ("license", lic)):
            # A person's answer outranks IDC's: never overwrite Source = 'user'.
            cur = pv.execute("SELECT Source FROM SeriesAttributes WHERE SeriesInstanceUID=? AND Key=?", (uid, key)).fetchone()
            if cur and cur[0] == "user": continue
            pv.execute("INSERT OR REPLACE INTO SeriesAttributes VALUES (?, ?, ?, 'idc', ?)", (uid, key, val, now)); n += 1
    pv.commit()
    print(f"\nwrote {n} attributes (collection, license) to {PROV.name} (SeriesAttributes, source idc)")
else:
    print("\n(dry run; add --write to record these in Contents/Slicer/provenance.sqlite)")
