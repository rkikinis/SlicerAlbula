"""Core logic for the DICOMProvenance module: additive-only provenance tracking
for DICOM studies/series in a Slicer DICOM database.

Everything here resolves paths RELATIVE TO THIS FILE's location, not to any
absolute path baked in at authoring time -- the containing folder (this module
plus the co-located SlicerDICOMDatabase) is meant to be movable, renamable, or
copyable to another machine without editing anything.

Two kinds of new DICOM objects get created, both purely additive (never
touching an existing series' own files/tags):

  * A DICOM Segmentation (SEG) object, for algorithm runs and manual edits,
    built via Slicer's own DICOMSegmentationExporter (dcmqi-backed) called
    directly rather than through its UI-facing wrapper, so arbitrary
    provenance metadata (SoftwareVersions, Manufacturer, DerivationDescription)
    can be set. Those same fields are re-asserted with pydicom after dcmqi
    writes the file, since dcmqi's own JSON-schema validation may not honor
    unrecognized top-level keys.

  * A minimal hand-built DICOM Basic Text SR, for standalone notes that pick
    one category from a small fixed list plus optional short free text,
    referencing the target series by UID.

Every created object also gets one row in a small local SQLite index
(provenance.sqlite, living in this same folder, never touching
ctkDICOM.sql's own schema) recording its immediate parent -- which may be the
original acquired series or a previously-created object -- so multi-step edit
chains can be reconstructed later. This index is what "Show lineage" reads;
it is never recomputed live from DICOM tags.

Switching Slicer's *active* DICOM database is never done implicitly by this
module (that would silently disrupt whatever database a user already has
open for other work) -- call ensure_database_open() explicitly (wired to a
button in the widget) when you want to point Slicer at the co-located
SlicerDICOMDatabase folder.
"""

import datetime
import os
import sqlite3

import pydicom
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import generate_uid, ExplicitVRLittleEndian

import slicer

CODING_SCHEME_DESIGNATOR = "99RKIK"
CODING_SCHEME_NAME = "Ron Kikinis lab local provenance codes"

# CodeValue has VR SH -- max 16 characters. Keep every code at or under that;
# the human-readable text belongs in the CodeMeaning (VR LO, 64 characters).
NOTE_CATEGORIES = [
    ("NEEDS_REVIEW", "Needs review"),
    ("GOOD_QUALITY", "Good quality"),
    ("POOR_QUALITY", "Poor quality / artifact"),
    ("INTERESTING", "Interesting finding"),
    ("SEG_CANDIDATE", "Candidate for segmentation"),
    ("EXCLUDED", "Excluded from study"),
    ("OTHER", "Other"),
]

EDIT_REASONS = [
    ("CORRECTION", "Correction"),
    ("REFINEMENT", "Refinement"),
    ("VALIDATION", "Validation"),
    ("DISAGREEMENT", "Disagreement"),
]

BASIC_TEXT_SR_SOP_CLASS_UID = "1.2.840.10008.5.1.4.1.1.88.11"
IMPLEMENTATION_CLASS_UID = "1.2.826.0.1.3680043.8.498.1"  # pydicom's own root, fine for a local tool


# ---------------------------------------------------------------------------
# Folder layout -- everything is resolved relative to THIS FILE, never from an
# absolute path baked in at authoring time, so the whole tree can be moved or
# renamed (or copied to another machine) without editing anything:
#
#   <root>/
#     DICOMProvenance/DICOMProvenance/DICOMProvenanceLib/core.py   <- this file
#     SlicerDICOMDatabase/          ctkDICOM.sql, dicom/, IDCLocal/, ...
#     provenance.sqlite             <- our own index, written alongside it
#     .provenance_author            <- who is attributing notes/edits here
#
# <root> is whatever directory sits three levels above this file.
# ---------------------------------------------------------------------------

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR = os.path.abspath(os.path.join(_THIS_DIR, "..", "..", ".."))


def root_dir():
    return _ROOT_DIR


def default_database_dir():
    return os.path.join(_ROOT_DIR, "SlicerDICOMDatabase")


def _provenance_db_path():
    return os.path.join(_ROOT_DIR, "provenance.sqlite")


def is_using_colocated_database():
    target = os.path.abspath(default_database_dir())
    current = getattr(slicer.dicomDatabase, "databaseDirectory", None)
    return bool(current) and os.path.abspath(current) == target and slicer.dicomDatabase.isOpen


def ensure_database_open():
    """Explicitly point Slicer's DICOM database at the co-located
    SlicerDICOMDatabase folder. Never called automatically -- only in
    response to a user action (a button), since it changes which database
    the whole Slicer session is currently pointed at."""
    target = default_database_dir()
    if not os.path.isdir(target):
        raise FileNotFoundError(f"No SlicerDICOMDatabase folder found at {target}")
    if is_using_colocated_database():
        return True
    slicer.dicomDatabase.openDatabase(os.path.join(target, "ctkDICOM.sql"))
    return slicer.dicomDatabase.isOpen


def _ctk_sql_path():
    dbDir = getattr(slicer.dicomDatabase, "databaseDirectory", None)
    if not dbDir:
        raise RuntimeError("No DICOM database is open in Slicer.")
    return os.path.join(dbDir, "ctkDICOM.sql")


def database_status():
    """(ok, message) describing whether this module can query the active DICOM
    database -- used to give an actionable hint instead of a raw exception."""
    dbDir = getattr(slicer.dicomDatabase, "databaseDirectory", None)
    if not dbDir:
        return False, "No DICOM database is open. Click \"Use this folder's SlicerDICOMDatabase\" above."
    sqlPath = os.path.join(dbDir, "ctkDICOM.sql")
    if not os.path.exists(sqlPath):
        return False, f"No ctkDICOM.sql in the active database folder ({dbDir})."
    if not os.access(sqlPath, os.R_OK):
        return False, (f"The active database ({dbDir}) is not readable by Slicer -- this is usually "
                        "macOS privacy protection on iCloud/Documents folders. Click "
                        "\"Use this folder's SlicerDICOMDatabase\" above to switch to the local copy.")
    if not is_using_colocated_database():
        return True, f"Active database is {dbDir} (not this folder's copy)."
    return True, "Using this folder's database."


# ---------------------------------------------------------------------------
# Author identity -- stored inside this same folder too (per-checkout,
# not per-machine), so it travels with the folder rather than needing to be
# re-entered after a move; a different machine sharing this same folder still
# sees the same author unless explicitly changed.
# ---------------------------------------------------------------------------

def _author_file():
    return os.path.join(_ROOT_DIR, ".provenance_author")


def get_author():
    path = _author_file()
    if os.path.exists(path):
        with open(path) as f:
            name = f.read().strip()
        if name:
            return name
    return None


def set_author(name):
    name = name.strip()
    with open(_author_file(), "w") as f:
        f.write(name)
    return name


def ensure_author(promptIfMissing=True):
    author = get_author()
    if author or not promptIfMissing:
        return author
    import qt
    # Slicer's PythonQt returns the entered string directly, while PyQt returns
    # a (text, accepted) tuple -- accept either shape.
    result = qt.QInputDialog.getText(
        None, "Your name", "This is used to attribute notes and edits you make. Enter your name:"
    )
    if isinstance(result, (tuple, list)):
        name = result[0] if result else ""
        accepted = bool(result[1]) if len(result) > 1 else bool(name)
    else:
        name = result or ""
        accepted = bool(name)
    if accepted and name.strip():
        return set_author(name)
    return None


# ---------------------------------------------------------------------------
# Provenance index (provenance.sqlite, alongside SlicerDICOMDatabase)
# ---------------------------------------------------------------------------

def _connect():
    conn = sqlite3.connect(_provenance_db_path())
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ProvenanceEdges (
          id INTEGER PRIMARY KEY,
          child_series_uid  TEXT NOT NULL,
          parent_series_uid TEXT,
          kind   TEXT NOT NULL,
          label  TEXT NOT NULL,
          detail TEXT,
          author TEXT,
          created_at TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_prov_parent ON ProvenanceEdges(parent_series_uid)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_prov_child ON ProvenanceEdges(child_series_uid)")
    conn.commit()
    return conn


def _record_edge(childSeriesUID, parentSeriesUID, kind, label, detail, author):
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO ProvenanceEdges (child_series_uid, parent_series_uid, kind, label, detail, author, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (childSeriesUID, parentSeriesUID, kind, label, detail, author,
             datetime.datetime.now().isoformat(timespec="seconds")),
        )
        conn.commit()
    finally:
        conn.close()


def next_edit_number(parentSeriesUID):
    """1-based count of existing 'edit' children of this parent, plus one."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM ProvenanceEdges WHERE parent_series_uid = ? AND kind = 'edit'",
            (parentSeriesUID,),
        ).fetchone()
        return (row[0] if row else 0) + 1
    finally:
        conn.close()


def get_lineage(seriesUID):
    """Return {'ancestors': [...], 'node': seriesUID, 'descendants': [nested dict tree]}."""
    conn = _connect()
    try:
        ancestors = []
        cur = seriesUID
        seen = set()
        while cur and cur not in seen:
            seen.add(cur)
            row = conn.execute(
                "SELECT parent_series_uid, kind, label, detail, author, created_at "
                "FROM ProvenanceEdges WHERE child_series_uid = ? ORDER BY id DESC LIMIT 1",
                (cur,),
            ).fetchone()
            if not row:
                break
            parent, kind, label, detail, author, created_at = row
            ancestors.insert(0, {
                "series_uid": cur, "parent_series_uid": parent, "kind": kind,
                "label": label, "detail": detail, "author": author, "created_at": created_at,
            })
            cur = parent

        def _descendants(uid):
            rows = conn.execute(
                "SELECT child_series_uid, kind, label, detail, author, created_at "
                "FROM ProvenanceEdges WHERE parent_series_uid = ? ORDER BY created_at",
                (uid,),
            ).fetchall()
            out = []
            for child, kind, label, detail, author, created_at in rows:
                out.append({
                    "series_uid": child, "kind": kind, "label": label, "detail": detail,
                    "author": author, "created_at": created_at,
                    "children": _descendants(child),
                })
            return out

        return {"ancestors": ancestors, "node": seriesUID, "descendants": _descendants(seriesUID)}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Series/study lookup against the live ctkDICOM.sql (read-only queries only)
# ---------------------------------------------------------------------------

def search_series(searchText, limit=200):
    """Return rows of (PatientName, PatientID, StudyDescription, StudyDate,
    SeriesDescription, Modality, SeriesInstanceUID, StudyInstanceUID) matching
    searchText against patient/study/series description fields."""
    like = f"%{searchText}%" if searchText else "%"
    query = """
        SELECT p.DisplayedPatientsName, p.PatientID, st.StudyDescription, st.StudyDate,
               se.SeriesDescription, se.Modality, se.SeriesInstanceUID, st.StudyInstanceUID
        FROM Series se
        JOIN Studies st ON se.StudyInstanceUID = st.StudyInstanceUID
        JOIN Patients p ON st.PatientsUID = p.UID
        WHERE p.DisplayedPatientsName LIKE ? OR st.StudyDescription LIKE ? OR se.SeriesDescription LIKE ?
        ORDER BY p.DisplayedPatientsName, st.StudyDate, se.SeriesNumber
        LIMIT ?
    """
    conn = sqlite3.connect(_ctk_sql_path())
    try:
        return conn.execute(query, (like, like, like, limit)).fetchall()
    finally:
        conn.close()


def study_uid_for_series(seriesUID):
    conn = sqlite3.connect(_ctk_sql_path())
    try:
        row = conn.execute(
            "SELECT StudyInstanceUID FROM Series WHERE SeriesInstanceUID = ?", (seriesUID,)
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def series_label(seriesUID):
    """Short human-readable label for a series straight from the DICOM database
    -- used to name nodes (e.g. the original acquisition) that have no row of
    their own in the provenance index."""
    conn = sqlite3.connect(_ctk_sql_path())
    try:
        row = conn.execute(
            "SELECT Modality, SeriesDescription FROM Series WHERE SeriesInstanceUID = ?", (seriesUID,)
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return seriesUID[:24] + "..."
    modality, desc = row
    return f"[{modality}] {desc or '(no description)'}"


def resolve_db_path(filename):
    """ctkDICOMDatabase stores an image's path either as an absolute path (files
    indexed in place, wherever they live on this machine) or relative to the
    database directory (files copied into the database). Resolve both forms."""
    if not filename:
        return None
    if os.path.isabs(filename):
        return filename
    return os.path.join(slicer.dicomDatabase.databaseDirectory, filename)


def first_file_for_series(seriesUID):
    conn = sqlite3.connect(_ctk_sql_path())
    try:
        row = conn.execute(
            "SELECT Filename FROM Images WHERE SeriesInstanceUID = ? LIMIT 1", (seriesUID,)
        ).fetchone()
    finally:
        conn.close()
    return resolve_db_path(row[0]) if row else None


# ---------------------------------------------------------------------------
# SEG export with provenance
# ---------------------------------------------------------------------------

def export_seg_with_provenance(segmentationNode, parentSeriesUID, kind, label, detail,
                                task=None, tool=None, version=None,
                                segmentAlgorithmType="AUTOMATIC", author=None):
    """Export segmentationNode as a DICOM SEG with provenance tags set, import
    it into the current DICOM database, and record one provenance edge.

    kind: 'algorithm' | 'edit' | 'validation'
    Returns the new SEG's SeriesInstanceUID.
    """
    import DICOMSegmentationPlugin

    author = author or ensure_author()

    segmentation = segmentationNode.GetSegmentation()
    segmentIDs = []
    segmentation.GetSegmentIDs(segmentIDs)
    for segmentID in segmentIDs:
        segment = segmentation.GetSegment(segmentID)
        segment.SetTag("DICOM.SegmentAlgorithmType", segmentAlgorithmType)
        if tool:
            segment.SetTag("DICOM.SegmentAlgorithmName", tool)

    metadata = {"SeriesDescription": label}
    if tool:
        metadata["ManufacturerModelName"] = tool
        metadata["Manufacturer"] = tool
    if version:
        metadata["SoftwareVersions"] = version
    if detail:
        metadata["DerivationDescription"] = detail

    exporter = DICOMSegmentationPlugin.DICOMSegmentationExporter(
        segmentationNode, contentCreatorName=author or "Unknown"
    )
    outDir = slicer.util.tempDirectory()
    segFileName = "provenance_seg.dcm"
    try:
        exporter.export(outDir, segFileName, metadata)
        segFilePath = os.path.join(outDir, segFileName)

        # Safety net: force-set provenance tags directly, in case dcmqi's own
        # JSON-schema validation dropped any unrecognized top-level keys.
        ds = pydicom.dcmread(segFilePath)
        if tool:
            ds.Manufacturer = tool
            ds.ManufacturerModelName = tool
        if version:
            ds.SoftwareVersions = version
        if detail:
            ds.DerivationDescription = detail
        ds.save_as(segFilePath)

        childSeriesUID = str(ds.SeriesInstanceUID)
        slicer.dicomDatabase.insert(segFilePath)
    finally:
        exporter.cleanup()

    _record_edge(childSeriesUID, parentSeriesUID, kind, label, detail, author)
    return childSeriesUID


# ---------------------------------------------------------------------------
# Note SR (hand-built minimal Basic Text SR)
# ---------------------------------------------------------------------------

def _coded_concept(code, meaning, schemeDesignator=CODING_SCHEME_DESIGNATOR):
    # Fail loudly rather than writing a non-conformant object that strict
    # parsers may reject: CodeValue is VR SH (16 chars), designator likewise.
    if len(code) > 16:
        raise ValueError(f"CodeValue {code!r} is {len(code)} chars; VR SH allows at most 16")
    if len(schemeDesignator) > 16:
        raise ValueError(f"CodingSchemeDesignator {schemeDesignator!r} exceeds 16 chars")
    seq_item = Dataset()
    seq_item.CodeValue = code
    seq_item.CodingSchemeDesignator = schemeDesignator
    seq_item.CodeMeaning = meaning
    return seq_item


def _code_item(conceptCode, conceptMeaning, valueCode, valueMeaning):
    item = Dataset()
    item.RelationshipType = "CONTAINS"
    item.ValueType = "CODE"
    item.ConceptNameCodeSequence = [_coded_concept(conceptCode, conceptMeaning)]
    item.ConceptCodeSequence = [_coded_concept(valueCode, valueMeaning)]
    return item


def _text_item(conceptCode, conceptMeaning, text):
    item = Dataset()
    item.RelationshipType = "CONTAINS"
    item.ValueType = "TEXT"
    item.ConceptNameCodeSequence = [_coded_concept(conceptCode, conceptMeaning)]
    item.TextValue = text
    return item


def _uidref_item(conceptCode, conceptMeaning, uid):
    item = Dataset()
    item.RelationshipType = "HAS_PROPERTIES"
    item.ValueType = "UIDREF"
    item.ConceptNameCodeSequence = [_coded_concept(conceptCode, conceptMeaning)]
    item.UID = uid
    return item


def create_note_sr(targetSeriesUID, categoryCode, categoryMeaning, freeText=None, author=None):
    """Build a minimal Basic Text SR referencing targetSeriesUID, carrying a
    coded category (and optional free text), import it, and record one
    provenance edge. Returns the new SR's SeriesInstanceUID."""
    author = author or ensure_author()

    targetStudyUID = study_uid_for_series(targetSeriesUID)
    referenceFile = first_file_for_series(targetSeriesUID)
    if not referenceFile:
        raise ValueError(f"No files found for series {targetSeriesUID}")
    ref = pydicom.dcmread(referenceFile, stop_before_pixels=True)

    now = datetime.datetime.now()
    contentDate = now.strftime("%Y%m%d")
    contentTime = now.strftime("%H%M%S")

    ds = Dataset()
    ds.PatientName = getattr(ref, "PatientName", "")
    ds.PatientID = getattr(ref, "PatientID", "")
    ds.PatientBirthDate = getattr(ref, "PatientBirthDate", "")
    ds.PatientSex = getattr(ref, "PatientSex", "")

    ds.StudyInstanceUID = targetStudyUID or ref.StudyInstanceUID
    ds.StudyDate = getattr(ref, "StudyDate", contentDate)
    ds.StudyTime = getattr(ref, "StudyTime", contentTime)
    ds.StudyID = getattr(ref, "StudyID", "")
    ds.AccessionNumber = getattr(ref, "AccessionNumber", "")
    ds.ReferringPhysicianName = getattr(ref, "ReferringPhysicianName", "")

    seriesUID = generate_uid()
    ds.Modality = "SR"
    ds.SeriesInstanceUID = seriesUID
    ds.SeriesNumber = 900
    label = f"NOTE ({author}): {categoryMeaning}" if author else f"NOTE: {categoryMeaning}"
    ds.SeriesDescription = label

    ds.Manufacturer = "SlicerDICOMProvenance"

    sopInstanceUID = generate_uid()
    ds.SOPClassUID = BASIC_TEXT_SR_SOP_CLASS_UID
    ds.SOPInstanceUID = sopInstanceUID
    ds.InstanceNumber = 1
    ds.CompletionFlag = "COMPLETE"
    ds.VerificationFlag = "UNVERIFIED"
    ds.ContentDate = contentDate
    ds.ContentTime = contentTime
    if author:
        ds.OperatorsName = author

    ds.CodingSchemeIdentificationSequence = [Dataset()]
    ds.CodingSchemeIdentificationSequence[0].CodingSchemeDesignator = CODING_SCHEME_DESIGNATOR
    ds.CodingSchemeIdentificationSequence[0].CodingSchemeName = CODING_SCHEME_NAME

    content = [
        _code_item("CATEGORY", "Category", categoryCode, categoryMeaning),
        _uidref_item("REF_SERIES", "Referenced series", targetSeriesUID),
    ]
    if freeText:
        content.append(_text_item("NOTE_TEXT", "Note text", freeText))

    ds.ValueType = "CONTAINER"
    ds.ContinuityOfContent = "SEPARATE"
    ds.ConceptNameCodeSequence = [_coded_concept("NOTE_DOCUMENT", "Provenance annotation note")]
    ds.ContentSequence = content

    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = ds.SOPClassUID
    file_meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    file_meta.ImplementationClassUID = IMPLEMENTATION_CLASS_UID

    fileDs = pydicom.dataset.FileDataset(None, ds, file_meta=file_meta, preamble=b"\x00" * 128)
    for elem in ds:
        fileDs.add(elem)
    fileDs.is_little_endian = True
    fileDs.is_implicit_VR = False

    outDir = slicer.util.tempDirectory()
    outPath = os.path.join(outDir, "note_sr.dcm")
    fileDs.save_as(outPath, enforce_file_format=True)

    slicer.dicomDatabase.insert(outPath)

    detail = freeText if freeText else categoryMeaning
    _record_edge(seriesUID, targetSeriesUID, "note", label, detail, author)
    return seriesUID
