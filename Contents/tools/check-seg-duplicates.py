#!/usr/bin/env python3
"""Are any two DICOM SEGs in the database carrying the same voxels?

    uv run --python 3.12 --with pydicom Contents/tools/check-seg-duplicates.py

Why this exists: on 2026-09-11 the application's decoded-volume cache could hand the DICOM writer
another segmentation's labelmap, so three MOOSE SEGs were saved with the bones network's voxels
under their own names (fixed in Contents/src/SlicerLive f45dc6f). Two different segmentations never share a
whole frame at the same segment number and slice position, so a pair that does is a copy. This
compares every pair of SEGs on the same study, frame by frame. A pair where 90% or more of the
smaller one's frames are in the other is a copy. Pass --all to also see pairs that share a few
frames, which two honest results of one task can (IDC's NLST analyses do, by a handful).
"""
from __future__ import annotations
import glob, hashlib, itertools, os, sys, warnings
warnings.filterwarnings("ignore")
import pydicom

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Slicer", "SlicerDICOMDatabase")

def frames(path):
    d = pydicom.dcmread(path)
    fb = (d.Rows * d.Columns + 7) // 8
    raw = d.PixelData
    out = {}
    for i, fg in enumerate(d.PerFrameFunctionalGroupsSequence):
        seg = int(fg.SegmentIdentificationSequence[0].ReferencedSegmentNumber)
        pos = tuple(round(float(x), 1) for x in fg.PlanePositionSequence[0].ImagePositionPatient)
        out[(seg, pos)] = hashlib.sha1(raw[i * fb:(i + 1) * fb]).hexdigest()
    return out

segs = []
for f in sorted(glob.glob(os.path.join(ROOT, "**", "*.dcm"), recursive=True)):
    try:
        d = pydicom.dcmread(f, stop_before_pixels=True)
    except Exception:
        continue
    if d.Modality != "SEG" or "NumberOfFrames" not in d or "PerFrameFunctionalGroupsSequence" not in d:
        continue
    segs.append((str(d.StudyInstanceUID), str(d.SeriesDescription), str(d.ContentDate), str(d.ContentTime)[:6], f))
print(f"{len(segs)} SEG files with frames under {os.path.relpath(ROOT)}")

bad = 0
by_study = {}
for s in segs: by_study.setdefault(s[0], []).append(s)
for study, items in by_study.items():
    if len(items) < 2: continue
    fr = {s[4]: frames(s[4]) for s in items}
    for a, b in itertools.combinations(items, 2):
        fa, fb = fr[a[4]], fr[b[4]]
        same = sum(1 for k, v in fa.items() if fb.get(k) == v)
        smaller = min(len(fa), len(fb))
        if not same: continue
        # A COPY is one whose every frame is in the other. Two genuine results of one task on two
        # reconstructions of the same study (IDC's NLST analyses) share a few frames -- a tiny
        # structure that came out identical -- and that is not a copy; it is printed, not counted.
        if same >= 0.9 * smaller:
            bad += 1
            print(f"COPY: {a[1]} ({a[2]} {a[3]}) and {b[1]} ({b[2]} {b[3]}): {same} of {smaller} frames identical")
        elif "--all" in sys.argv:
            print(f"share {same} of {smaller} frames: {a[1]} ({a[2]} {a[3]}) and {b[1]} ({b[2]} {b[3]})")
print("no SEG is a copy of another" if not bad else f"{bad} pair(s) are copies: one of each must be re-saved")
sys.exit(1 if bad else 0)
