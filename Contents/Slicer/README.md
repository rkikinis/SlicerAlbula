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
| `relativize-internal-paths.py` | absolute → database-relative for files that live inside |

## `export/` — creating derived DICOM

| | |
|---|---|
| `export-cropped-volume.py` | writes a cropped grayscale as a new series. Takes patient/study attributes from the parent series **actual tags**, not the ctk index (see the trap note below). |
| `check-vr.py` | VR conformance check. **Note it assumes explicit VR** and will report a false clean bill of health on an implicit-VR file. |
| `check-seg-meta.py` | validates the `seg_meta.json` handed to dcmqi |

## `zarr/` — the working copy

| | |
|---|---|
| `roundtrip-duckn.py` | proves the round trip: pixels compared frame-by-frame against the originals, identity diffed |

Both need the duckn venv: `.venv-duckn/bin/python zarr/<script>.py`.

## Also here

- `SlicerDICOMDatabase/` — the archive itself. Patient data; never in git.
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

## Retired 2026-09-25

Ron, asked which one-off scripts he still runs: "none, as far as I know." Moved to the macOS Trash (Put Back works) and
kept in git history: `database/` copy-archives-into-database, import-archives-into-database, rewrite-archive-paths,
copy-gdrive-into-database, verify-relocation, rewrite-old-db-paths; `export/` export-nninteractive-seg, fix-provenance,
fix-series-301-vr; `zarr/convert-series-to-zarr.py` and the derived `zarr-cache/` (165 MB; the duckn copies replaced
it); `Contents/tools/` repair_index.py, surfaces-to-patient-space.py, cardiac-phases/, decimation-study/, npr-mockup/.
Kept: export-cropped-volume.py (CONSTRAINTS.md cites it) and relativize-internal-paths.py, which it tells you to run
afterwards.
