#!/usr/bin/env python3
"""Decode every sample in codecs.tsv with an INDEPENDENT decoder and store the pixels as the truth.

    uv run --python 3.12 --with pydicom --with numpy --with pylibjpeg --with pylibjpeg-libjpeg \
        --with pylibjpeg-rle --with pylibjpeg-openjpeg Contents/data/codecs/make-truths.py

Beside each sample: <file>.truth.raw (the pixel array, little-endian, C order) and
<file>.truth.json (shape, dtype). pydicom's decoding goes through libjpeg (JPEG, JPEG-LS),
OpenJPEG (JPEG 2000) and its own RLE -- none of them our code -- so a decoder of ours that agrees
with these agrees with the world. A file the reference cannot decode is reported and skipped.
"""
import csv, json, sys, warnings
from pathlib import Path
warnings.filterwarnings("ignore")
import numpy as np, pydicom

HERE = Path(__file__).resolve().parent
base = HERE.parent / "dicom" / "codecs"
rows = [r for r in csv.reader((HERE / "codecs.tsv").open(), delimiter="\t") if r and not r[0].startswith("#")]
ok = 0
for ts, name, f, src, what, truth in rows:
    p = base / ts / f
    if not p.exists(): print("missing", p); continue
    try:
        a = pydicom.dcmread(p).pixel_array
    except Exception as e:
        print(f"  {f}: reference could not decode: {str(e)[:90]}"); continue
    a = np.ascontiguousarray(a)
    (base / ts / (f + ".truth.raw")).write_bytes(a.astype(a.dtype.newbyteorder("<")).tobytes())
    json.dump({"shape": list(a.shape), "dtype": str(a.dtype), "min": int(a.min()), "max": int(a.max())}, (base / ts / (f + ".truth.json")).open("w"))
    ok += 1
    print(f"  {ts:24} {f:36} {a.shape} {a.dtype}")
print(ok, "truths written")
