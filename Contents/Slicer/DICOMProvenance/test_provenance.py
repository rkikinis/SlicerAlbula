"""Headless smoke test for DICOMProvenance core logic.

Run with:
  Slicer --no-splash --no-main-window \
    --additional-module-paths <.../DICOMProvenance/DICOMProvenance> \
    --python-script <this file>
"""
import hashlib
import os
import sqlite3
import sys
import traceback

import numpy as np
import pydicom
import slicer

from DICOMProvenanceLib import core

FAILURES = []


def _die_on_uncaught(exc_type, exc, tb):
    # Without this, an escaping exception leaves headless Slicer sitting in its
    # event loop forever instead of exiting.
    traceback.print_exception(exc_type, exc, tb)
    print("\n  ABORTED by uncaught exception", flush=True)
    slicer.util.exit(1)


sys.excepthook = _die_on_uncaught


def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {label}" + (f" -- {detail}" if detail else ""), flush=True)
    if not condition:
        FAILURES.append(label)
    return condition


def section(name):
    print(f"\n=== {name} ===", flush=True)


section("0. Open co-located database")
core.set_author("Test Runner")
print("  author:", core.get_author(), flush=True)
opened = core.ensure_database_open()
check("database opens", opened, core.default_database_dir())
check("is co-located", core.is_using_colocated_database())
print("  provenance index:", core._provenance_db_path(), flush=True)

section("1. Pick a CT series to work with")
# Only series whose files are stored RELATIVE to the database directory are
# actually inside this folder; the rest of this database's index points at
# files elsewhere on the machine (primary-archives, Google Drive, the original
# database location), which are not readable here.
cts = []
conn = sqlite3.connect(os.path.join(slicer.dicomDatabase.databaseDirectory, "ctkDICOM.sql"))
try:
    cts = conn.execute(
        "SELECT se.SeriesInstanceUID, se.SeriesDescription, COUNT(i.SOPInstanceUID) "
        "FROM Series se JOIN Images i ON i.SeriesInstanceUID = se.SeriesInstanceUID "
        "WHERE se.Modality='CT' AND i.Filename NOT LIKE '/%' "
        "GROUP BY se.SeriesInstanceUID "
        "HAVING COUNT(i.SOPInstanceUID) BETWEEN 60 AND 100 "
        "ORDER BY COUNT(i.SOPInstanceUID) LIMIT 1"
    ).fetchall()
finally:
    conn.close()
check("found a CT series", len(cts) == 1)
if not cts:
    slicer.util.exit(1)
parentSeriesUID, parentDesc, parentCount = cts[0]
print(f"  parent series: {parentDesc} ({parentCount} images)", flush=True)
print(f"  uid: {parentSeriesUID}", flush=True)

section("2. Attach a note (SR) -- original data must be untouched")
originalFile = core.first_file_for_series(parentSeriesUID)
beforeHash = hashlib.sha256(open(originalFile, "rb").read()).hexdigest()
noteUID = core.create_note_sr(parentSeriesUID, "NEEDS_REVIEW", "Needs review")
print("  new SR series:", noteUID, flush=True)
afterHash = hashlib.sha256(open(originalFile, "rb").read()).hexdigest()
check("original DICOM file unchanged", beforeHash == afterHash)

conn = sqlite3.connect(os.path.join(slicer.dicomDatabase.databaseDirectory, "ctkDICOM.sql"))
try:
    srRow = conn.execute(
        "SELECT Modality, SeriesDescription, StudyInstanceUID FROM Series WHERE SeriesInstanceUID = ?",
        (noteUID,),
    ).fetchone()
    parentStudy = conn.execute(
        "SELECT StudyInstanceUID FROM Series WHERE SeriesInstanceUID = ?", (parentSeriesUID,)
    ).fetchone()
finally:
    conn.close()
check("SR is in the DICOM database", srRow is not None, str(srRow))
if srRow:
    check("SR modality is SR", srRow[0] == "SR", srRow[0])
    check("SR label mentions the category", "Needs review" in (srRow[1] or ""), srRow[1])
    check("SR is grouped under the parent study", srRow[2] == parentStudy[0])

section("3. Load the CT and build a throwaway segmentation")
import DICOMLib.DICOMUtils as DICOMUtils
loadedNodeIDs = DICOMUtils.loadSeriesByUID([parentSeriesUID])
volumeNodes = [slicer.mrmlScene.GetNodeByID(nid) for nid in (loadedNodeIDs or [])]
volumeNodes = [n for n in volumeNodes if n and n.IsA("vtkMRMLScalarVolumeNode")]
check("CT volume loaded", len(volumeNodes) >= 1, str(loadedNodeIDs))
if not volumeNodes:
    slicer.util.exit(1)
volumeNode = volumeNodes[0]
check("volume carries DICOM.instanceUIDs",
      bool(volumeNode.GetAttribute("DICOM.instanceUIDs")))

arr = slicer.util.arrayFromVolume(volumeNode)
labelArray = (arr > 300).astype(np.uint8)  # crude bone threshold, just needs to be non-empty
print("  labeled voxels:", int(labelArray.sum()), flush=True)
volumesLogic = slicer.modules.volumes.logic()
labelmapNode = volumesLogic.CreateAndAddLabelVolume(slicer.mrmlScene, volumeNode, "TestLabel")
slicer.util.updateVolumeFromArray(labelmapNode, labelArray)

segLogic = slicer.modules.segmentations.logic()
segNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode", "ProvenanceTestSeg")
segNode.SetReferenceImageGeometryParameterFromVolumeNode(volumeNode)
segLogic.ImportLabelmapToSegmentationNode(labelmapNode, segNode)
segNode.SetNodeReferenceID(segNode.GetReferenceImageGeometryReferenceRole(), volumeNode.GetID())
nSegments = segNode.GetSegmentation().GetNumberOfSegments()
check("segmentation has at least one segment", nSegments >= 1, f"{nSegments} segments")

section("4. Record it as an algorithm result (provenance tags must land)")
algoUID = None
try:
    algoUID = core.export_seg_with_provenance(
        segNode, parentSeriesUID, "algorithm",
        "FakeSegmenter total v9.9.9", "tool=FakeSegmenter; version=9.9.9; task=total",
        task="total", tool="FakeSegmenter", version="9.9.9",
    )
    print("  new SEG series:", algoUID, flush=True)
except Exception as e:
    check("SEG export succeeded", False, f"{type(e).__name__}: {e}")

if algoUID:
    check("SEG export succeeded", True)
    segFile = core.first_file_for_series(algoUID)
    check("SEG file is in the database", bool(segFile), str(segFile))
    if segFile:
        ds = pydicom.dcmread(segFile, stop_before_pixels=True)
        check("Manufacturer set", getattr(ds, "Manufacturer", "") == "FakeSegmenter",
              getattr(ds, "Manufacturer", "<missing>"))
        check("SoftwareVersions set", getattr(ds, "SoftwareVersions", "") == "9.9.9",
              str(getattr(ds, "SoftwareVersions", "<missing>")))
        check("DerivationDescription set", "task=total" in str(getattr(ds, "DerivationDescription", "")),
              str(getattr(ds, "DerivationDescription", "<missing>")))
        check("references the parent CT series",
              any(getattr(s, "SeriesInstanceUID", None) == parentSeriesUID
                  for ref in getattr(ds, "ReferencedSeriesSequence", []) or []
                  for s in [ref]),
              "ReferencedSeriesSequence present" if hasattr(ds, "ReferencedSeriesSequence") else "no ReferencedSeriesSequence")

section("5. Record two manual edits (chain must build on each other)")
edit1UID = edit2UID = None
if algoUID:
    n1 = core.next_edit_number(algoUID)
    check("first edit number is 1", n1 == 1, str(n1))
    edit1UID = core.export_seg_with_provenance(
        segNode, algoUID, "edit", f"edit#{n1} (Test Runner) of FakeSegmenter total",
        f"edit round {n1} of {algoUID}; reason=Refinement; by Test Runner",
        segmentAlgorithmType="MANUAL",
    )
    n2 = core.next_edit_number(algoUID)
    check("second edit number is 2", n2 == 2, str(n2))
    edit2UID = core.export_seg_with_provenance(
        segNode, edit1UID, "edit", f"edit#{n2} (Test Runner) of edit#{n1}",
        f"edit round {n2} of {edit1UID}; reason=Correction; by Test Runner",
        segmentAlgorithmType="MANUAL",
    )
    print("  edit1:", edit1UID, flush=True)
    print("  edit2:", edit2UID, flush=True)

section("6. Lineage")
if edit2UID:
    lin = core.get_lineage(edit2UID)
    chain = [a["label"] for a in lin["ancestors"]]
    print("  ancestors (oldest first):", flush=True)
    for a in lin["ancestors"]:
        print(f"    - [{a['kind']}] {a['label']}  (author={a['author']})", flush=True)
    check("chain has 3 entries (algorithm, edit1, edit2)", len(chain) == 3, str(len(chain)))
    check("chain root's parent is the original CT",
          lin["ancestors"][0]["parent_series_uid"] == parentSeriesUID)
    check("last chain entry is the focus (edit2)",
          lin["ancestors"][-1]["series_uid"] == edit2UID)

    linParent = core.get_lineage(parentSeriesUID)
    kinds = sorted(d["kind"] for d in linParent["descendants"])
    print("  direct descendants of the CT:", kinds, flush=True)
    check("CT has note + algorithm as direct descendants",
          kinds == ["algorithm", "note"], str(kinds))
    algoChildren = [d for d in linParent["descendants"] if d["kind"] == "algorithm"]
    check("algorithm has edit1 nested under it",
          algoChildren and len(algoChildren[0]["children"]) == 1,
          str(algoChildren[0]["children"] if algoChildren else None))

section("Summary")
print(f"  created SR:   {noteUID}", flush=True)
print(f"  created SEGs: {algoUID}, {edit1UID}, {edit2UID}", flush=True)
if FAILURES:
    print(f"\n  {len(FAILURES)} FAILURE(S): {FAILURES}", flush=True)
else:
    print("\n  ALL CHECKS PASSED", flush=True)

slicer.util.exit(0)
