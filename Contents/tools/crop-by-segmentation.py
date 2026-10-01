#!/usr/bin/env python3
"""Crop a CT series in the DICOM database to the box around chosen segments of a saved segmentation.

WHY. A whole-body CT is 709 slices; a question about one structure -- Ron, 2026-09-20: "I would
like to see the 6th right rib in all the algorithms in haversack" -- needs only the thorax. A
smaller volume runs every network several times faster and loads faster. The box comes from a
segmentation already in the database (the ts.v2:total result names every rib), plus a margin, so
the crop is reproducible from the record rather than drawn by hand.

NOT A ONE-OFF. The series, the segmentation, which segments (a regular expression on the segment
label) and the margin are arguments. The next crop is another invocation.

WHAT IT WRITES. A new CT series in the same study: the original slices inside the box, each with
its rows and columns cut to the box, the pixel data otherwise untouched (same rescale, same
window); new SOP instance UIDs and a new series UID (2.25.<uuid>); ImageType DERIVED;
DerivationDescription says what was cropped from what and how; a provenance edge child -> parent
of kind "crop" so the browser indents it under its source, the way the application's own crop
does. Files go under SlicerAlbula-Derived/<series uid>/ in the database folder and the rows into
ctkDICOM.sql the way nifti_to_dicom.py does it.

    python3 crop-by-segmentation.py --db <ctkDICOM dir> --seg <SEG SeriesInstanceUID> \
        --labels 'rib, (left|right)$' --margin-mm 20 --description 'thorax (ribs + 2 cm)'

Reads only pydicom and numpy. The segmentation must be the Label Map form (one label per voxel);
its frames are matched to the CT slices by position.
"""
from __future__ import annotations
import argparse, datetime, os, re, sqlite3, sys, uuid
from pathlib import Path

import numpy as np
import pydicom
from pydicom.uid import generate_uid


def series_files(db: Path, series_uid: str) -> list[Path]:
    con = sqlite3.connect(db / "ctkDICOM.sql")
    rows = con.execute("SELECT Filename FROM Images WHERE SeriesInstanceUID=?", (series_uid,)).fetchall()
    con.close()
    return [db / r[0] for r in rows]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True, help="the ctkDICOM database directory")
    ap.add_argument("--seg", required=True, help="SeriesInstanceUID of the Label Map segmentation that defines the box")
    ap.add_argument("--labels", required=True, help="regular expression on the segment labels that make the box")
    ap.add_argument("--margin-mm", type=float, default=20.0)
    ap.add_argument("--description", required=True, help="SeriesDescription of the crop, e.g. 'thorax (ribs + 2 cm)'")
    ap.add_argument("--series-number", type=int, default=9001)
    ap.add_argument("--dry-run", action="store_true", help="report the box and stop")
    a = ap.parse_args()
    db = Path(a.db)

    seg_files = series_files(db, a.seg)
    if len(seg_files) != 1:
        print(f"expected one file for the SEG series, found {len(seg_files)}", file=sys.stderr); return 2
    seg = pydicom.dcmread(seg_files[0])
    if str(getattr(seg, "SegmentationType", "")) != "LABELMAP":
        print(f"the segmentation is {getattr(seg, 'SegmentationType', '?')}, not LABELMAP", file=sys.stderr); return 2
    labels = {int(s.SegmentNumber): str(s.SegmentLabel) for s in seg.SegmentSequence}
    chosen = {n for n, l in labels.items() if re.search(a.labels, l)}
    if not chosen:
        print("no segment label matches", a.labels, file=sys.stderr); return 2
    arr = seg.pixel_array
    zz, yy, xx = np.nonzero(np.isin(arr, list(chosen)))
    if not len(zz):
        print("the chosen segments are empty", file=sys.stderr); return 2
    pm = seg.SharedFunctionalGroupsSequence[0].PixelMeasuresSequence[0]
    row_mm, col_mm = float(pm.PixelSpacing[0]), float(pm.PixelSpacing[1])
    frames = seg.PerFrameFunctionalGroupsSequence
    seg_z = np.array([float(f.PlanePositionSequence[0].ImagePositionPatient[2]) for f in frames])
    mr, mc = int(round(a.margin_mm / row_mm)), int(round(a.margin_mm / col_mm))
    r0, r1 = max(0, yy.min() - mr), min(arr.shape[1] - 1, yy.max() + mr)
    c0, c1 = max(0, xx.min() - mc), min(arr.shape[2] - 1, xx.max() + mc)
    z_lo, z_hi = seg_z[zz.min()] - a.margin_mm, seg_z[zz.max()] + a.margin_mm
    print(f"{len(chosen)} segments match; box rows {r0}-{r1}, cols {c0}-{c1}, z {min(z_lo, z_hi):.1f}..{max(z_lo, z_hi):.1f} mm")

    parent_uid = str(seg.ReferencedSeriesSequence[0].SeriesInstanceUID)
    ct_files = series_files(db, parent_uid)
    if not ct_files:
        print("the segmentation's source series is not in the database:", parent_uid, file=sys.stderr); return 2
    heads = []
    for f in ct_files:
        d = pydicom.dcmread(f, stop_before_pixels=True)
        heads.append((float(d.ImagePositionPatient[2]), f))
    inside = [f for z, f in sorted(heads) if min(z_lo, z_hi) <= z <= max(z_lo, z_hi)]
    print(f"{len(inside)} of {len(ct_files)} slices inside the box; {r1 - r0 + 1} x {c1 - c0 + 1} pixels each")
    if a.dry_run:
        return 0

    series_uid = "2.25." + str(uuid.uuid4().int)
    out_dir = db / "SlicerAlbula-Derived" / series_uid
    out_dir.mkdir(parents=True)
    now = datetime.datetime.now()
    first = pydicom.dcmread(inside[0], stop_before_pixels=True)
    derivation = (f"Cropped from series {parent_uid} to the box around segments matching '{a.labels}' of "
                  f"segmentation {a.seg} ({', '.join(sorted(labels[n] for n in chosen))[:200]}) plus {a.margin_mm:g} mm; "
                  f"rows {r0}-{r1}, columns {c0}-{c1}, {len(inside)} of {len(ct_files)} slices. "
                  f"crop-by-segmentation.py, SlicerAlbula, {now:%Y-%m-%d}.")
    written = []
    for i, f in enumerate(inside):
        d = pydicom.dcmread(f)
        px = d.pixel_array[r0:r1 + 1, c0:c1 + 1]
        # The pixel origin moves with the corner that is kept: ImagePositionPatient is the center of
        # the first pixel, so the new corner is the old one plus the row/column offsets along the
        # image axes.
        iop = [float(v) for v in d.ImageOrientationPatient]
        rowdir, coldir = np.array(iop[:3]), np.array(iop[3:])
        ipp = np.array([float(v) for v in d.ImagePositionPatient]) + coldir * (r0 * row_mm) + rowdir * (c0 * col_mm)
        d.ImagePositionPatient = [f"{v:.6f}" for v in ipp]
        d.Rows, d.Columns = px.shape
        d.PixelData = np.ascontiguousarray(px).tobytes()
        d.SeriesInstanceUID = series_uid
        d.SOPInstanceUID = generate_uid()
        d.file_meta.MediaStorageSOPInstanceUID = d.SOPInstanceUID
        d.SeriesDescription = a.description[:64]
        d.SeriesNumber = a.series_number
        d.InstanceNumber = i + 1
        d.ImageType = ["DERIVED", "SECONDARY", "AXIAL"]
        d.DerivationDescription = derivation[:1024]
        d.SeriesDate, d.SeriesTime = now.strftime("%Y%m%d"), now.strftime("%H%M%S")
        # A cropped slice is no longer the original instance; say what it came from.
        d.SourceImageSequence = [pydicom.Dataset()]
        d.SourceImageSequence[0].ReferencedSOPClassUID = d.SOPClassUID
        d.SourceImageSequence[0].ReferencedSOPInstanceUID = pydicom.dcmread(f, stop_before_pixels=True).SOPInstanceUID
        out = out_dir / f"{d.SOPInstanceUID}.dcm"
        d.save_as(out, write_like_original=False)
        written.append(out)

    # Register the way the database's own rows are shaped (nifti_to_dicom.py does the same).
    con = sqlite3.connect(db / "ctkDICOM.sql")
    stamp = now.strftime("%Y-%m-%dT%H:%M:%S.000")
    study_uid = str(first.StudyInstanceUID)
    con.execute(
        "INSERT OR REPLACE INTO Series (SeriesInstanceUID,StudyInstanceUID,SeriesNumber,SeriesDate,SeriesTime,"
        "SeriesDescription,Modality,BodyPartExamined,FrameOfReferenceUID,AcquisitionNumber,ContrastAgent,"
        "ScanningSequence,EchoNumber,TemporalPosition,InsertTimestamp,DisplayedCount,DisplayedSize,DisplayedNumberOfFrames) "
        "VALUES (?,?,?,?,?,?,?,?,?,1,'','',1,1,?,?,?,?)",
        (series_uid, study_uid, a.series_number, now.strftime("%Y%m%d"), now.strftime("%H%M%S"), a.description[:64],
         str(first.Modality), str(getattr(first, "BodyPartExamined", "")), str(getattr(first, "FrameOfReferenceUID", "")),
         stamp, len(written), f"{c1 - c0 + 1}x{r1 - r0 + 1}", len(written)))
    for out in written:
        con.execute("INSERT OR REPLACE INTO Images (SOPInstanceUID,Filename,URL,SeriesInstanceUID,InsertTimestamp) VALUES (?,?,?,?,?)",
                    (out.stem, os.path.relpath(out, db), "", series_uid, stamp))
    con.commit(); con.close()

    prov = db.parent / "provenance.sqlite"
    con = sqlite3.connect(prov)
    con.execute("DELETE FROM ProvenanceEdges WHERE child_series_uid=?", (series_uid,))
    con.execute("INSERT INTO ProvenanceEdges (child_series_uid,parent_series_uid,kind,label,detail,author,created_at) VALUES (?,?,?,?,?,?,?)",
                (series_uid, parent_uid, "crop", a.description, derivation, "crop-by-segmentation.py", now.isoformat(timespec="seconds")))
    con.commit(); con.close()
    print(f"wrote {len(written)} slices to {out_dir}\nseries {series_uid} registered under study {study_uid}, indented under {parent_uid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
