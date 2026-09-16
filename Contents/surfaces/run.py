"""Extract surfaces from a labelmap on disk and report per-phase timing.

    <python> Contents/surfaces/run.py [labelmap.nrrd] [cpu|mps|cuda]

Defaults to the NEPHROGENIC ts:total checkpoint, whose correct triangle count is 12,121,372 --
the parity contract against Contents/src/SlicerLive/algorithms/surface-nets.ts.
"""
from __future__ import annotations

import sys, time
from pathlib import Path

import numpy as np
import SimpleITK as sitk

sys.path.insert(0, str(Path(__file__).resolve().parent))
from surface_nets import extract          # noqa: E402

HERE = Path(__file__).resolve().parent
DEFAULT = HERE.parent / "Contents/Slicer/SlicerDICOMDatabase/SlicerAlbula-Checkpoints/2026-09-08T21-46-02-107Z-ts_total.seg.nrrd"

path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
device = sys.argv[2] if len(sys.argv) > 2 else "cpu"
if not path.exists():
    sys.exit(f"no labelmap at {path}")

t_load = time.perf_counter()
img = sitk.ReadImage(str(path))
lab = sitk.GetArrayFromImage(img).astype(np.uint8)     # (Z, Y, X)
t_load = time.perf_counter() - t_load

# SimpleITK reports direction/spacing/origin in x,y,z world order; build the 4x4 IJK->RAS.
sp = np.array(img.GetSpacing(), dtype=np.float64)
D = np.array(img.GetDirection(), dtype=np.float64).reshape(3, 3)
org = np.array(img.GetOrigin(), dtype=np.float64)
m = np.eye(4, dtype=np.float32)
m[:3, :3] = (D * sp).astype(np.float32)
m[:3, 3] = org.astype(np.float32)

print(f"{path.name}")
print(f"  {lab.shape[2]} x {lab.shape[1]} x {lab.shape[0]} = {lab.size/1e6:.0f}M voxels, "
      f"{' x '.join(f'{v:.2f}' for v in sp)} mm, read in {t_load:.1f}s\n")

t0 = time.perf_counter()
meshes, tm = extract(lab, m, device=device)
total = time.perf_counter() - t0

tris = sum(len(x["indices"]) // 3 for x in meshes)
verts = sum(len(x["positions"]) for x in meshes)
print(tm.report())
print(f"\n  device {device}: {len(meshes)} labels, {verts:,} vertices, {tris:,} triangles in {total:.1f}s")
print(f"  parity target (TypeScript, same data): 12,121,372 triangles"
      f"  -> {'MATCH' if tris == 12_121_372 else 'DIFFERS by ' + format(tris - 12_121_372, ',')}")
print(f"  TypeScript on this data: 25.0s extraction. Budget: <=33s target, <=66s ceiling.")
