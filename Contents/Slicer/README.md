# Slicer-side tooling

Scripts that act on the DICOM database and its derived data. Each one is a single standalone file
with its rationale in a header comment and its usage in the first few lines — none of them import
each other, so any one can be run, read or pasted on its own.

Every script derives its paths from its own location (`SLICER_DIR`), so this whole folder can move to
another directory or another machine without edits.

## `database/` — the archive and its index

| | |
|---|---|
| `audit-database.py` | the health check: zombies, orphan files, empty dirs, stale provenance, zarr copies. `--clean` acts, no flag reports. Run this after anything that writes. |
| `db-summary.py` | patients / studies / series counts, quickly |
| `clean-database.py` | targeted removal of a patient or study |
| `copy-gdrive-into-database.py` | copies a Google Drive study in, skipping non-DICOM (checks the DICM magic, not the extension) |
| `copy-archives-into-database.py` | the same for the local archive folders |
| `import-archives-into-database.py` | indexes without copying |
| `rewrite-archive-paths.py` | repoints index rows after files move; falls back to basename matching with a uniqueness check |
| `rewrite-old-db-paths.py` | one-off: rows still pointing at `~/Documents/SlicerDICOMDatabase` |
| `relativize-internal-paths.py` | absolute → database-relative for files that live inside |
| `verify-relocation.py` | reads `MediaStorageSOPInstanceUID` from the file meta group to prove a relocation matched the right files. No pydicom needed — the meta group is always explicit VR LE. |

## `export/` — creating derived DICOM

| | |
|---|---|
| `export-cropped-volume.py` | writes a cropped grayscale as a new series. Takes patient/study attributes from the parent series **actual tags**, not the ctk index (see the trap note below). |
| `export-nninteractive-seg.py` | writes a segmentation as DICOM SEG via dcmqi, with a geometry-equality guard that aborts rather than producing a misaligned SEG |
| `check-vr.py` | VR conformance check. **Note it assumes explicit VR** and will report a false clean bill of health on an implicit-VR file. |
| `check-seg-meta.py` | validates the `seg_meta.json` handed to dcmqi |
| `fix-series-301-vr.py` | one-off repair of the VR violations described below |
| `fix-provenance.py` | one-off repair of the provenance chain |

## `zarr/` — the working copy

| | |
|---|---|
| `convert-series-to-zarr.py` | DICOM series → zarr working copy, with the source fingerprint stored *inside* the zarr attributes so it cannot drift from what it describes |
| `roundtrip-duckn.py` | proves the round trip: pixels compared frame-by-frame against the originals, identity diffed |

Both need the duckn venv: `.venv-duckn/bin/python zarr/<script>.py`.

## Also here

- `SlicerDICOMDatabase/` — the archive itself. Patient data; never in git.
- `zarr-cache/` — derived working copies, one directory per `SeriesInstanceUID`. Regenerable.
- `provenance.sqlite` — the lineage index. Small, but its rows are real `SeriesInstanceUID`s, so it
  is not in git either.
- `DICOMProvenance/` — the scripted Slicer module.

## Two traps worth knowing before you edit anything here

**Never feed ctkDICOM *index* values into DICOM tags.** The index stores display concatenations and
reformatted values that violate VR limits — a 68-character `StudyDescription` against LO's 64, an
ISO-format birth date against DA's 8 digits. Read the parent series' real tags instead;
`export-cropped-volume.py` does this in `authoritative_from_parent()`. This cost several rounds of
opaque dcmqi "Value Representation violated" errors.

**Series 301 is implicit VR LE.** A checker that assumes explicit VR silently passes it. `check-vr.py`
did exactly that once, which is why the false-negative warning is in the table above rather than
buried in the source.
