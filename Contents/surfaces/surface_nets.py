"""Surface nets over a labelmap, in torch: one implementation, MPS / CUDA / CPU.

WHY THIS EXISTS. The TypeScript implementation in `Contents/src/SlicerLive/algorithms/surface-nets.ts` is
correct and its appearance is accepted, but it is single-threaded and takes 118 s inside the
application against Ron's 66 s ceiling ("30 sec is ok, 1m is acceptable, everything else is
problematic"). See `Contents/src/SlicerLive/docs/GREASED-LIGHTNING.md`.

WHY TORCH AND NOT WGSL. Ron: "Our GPU code should also run on other platforms. Perhaps using Mike's
architecture." haversack's `backends/` is a registry where each backend exposes `available()` and an
identical `run()`, and `torch_gather`'s docstring carries the load-bearing idea: "Runs on any device;
this is the reference the fused kernels are checked against." Torch gives that portability from one
implementation, with no per-vendor kernels and no WebGPU device-limit tiling.

AND THE MEASUREMENT THAT DECIDED IT, which this package now carries in full (see run.py and the
phase table in README.md; the earlier phases-1-2-only probe it grew out of was deleted 2026-09-10).
On NEPHROGENIC, phases 1-2:
TypeScript 13.9 s, torch on MPS 4.3 s, torch on CPU 1.3 s. **The GPU is the slowest of the real
options** because this work is dominated by irregular compaction rather than streaming -- compacting
417 M elements costs 1.81 s via `torch.nonzero` on MPS against 0.15 s on CPU. So the default device
here is CPU, and that is a measured choice rather than a fallback.

NOT IN haversack ITSELF. Its engine registry says of itself: "Deliberately a static registry, not a
plugin framework", and it is a segmentation-model runner -- a mesh extractor is outside that. This
follows its architecture and stays in Albula, which Ron calls "a sandbox... complementary to what
steve and mike are doing". It is written so it could be offered upstream as an engine later.

PARITY IS THE CONTRACT. This must agree with the TypeScript reference, which has seven behavioural
tests and shipped output Ron has accepted. The check is the triangle count on NEPHROGENIC ts:total:
**12,121,372**.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np
import torch

# Corner c of a cell as (dx, dy, dz), bit 0 = x, bit 1 = y, bit 2 = z -- the SAME numbering as the
# TypeScript CORNER table. The edge table indexes into it, so the two must not drift apart.
CORNER = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0),
          (0, 0, 1), (1, 0, 1), (0, 1, 1), (1, 1, 1)]
CELL_EDGES = [(0, 1), (2, 3), (4, 5), (6, 7),      # along x
              (0, 2), (1, 3), (4, 6), (5, 7),      # along y
              (0, 4), (1, 5), (2, 6), (3, 7)]      # along z

# For a face between a voxel and its +axis neighbour, the four CELLS around that face, as
# (di, dj, dk) offsets from the voxel, in the winding the TypeScript emits (a -> b).
FACE_CELLS = {
    0: [(0, -1, -1), (0, 0, -1), (0, 0, 0), (0, -1, 0)],      # +x
    1: [(-1, 0, -1), (-1, 0, 0), (0, 0, 0), (0, 0, -1)],      # +y
    2: [(-1, -1, 0), (0, -1, 0), (0, 0, 0), (-1, 0, 0)],      # +z
}

DEFAULT_SMOOTH_ITERS = 24        # matches the TypeScript defaults, which are measured, not chosen
DEFAULT_NORMAL_SMOOTH = 16
LAMBDA, MU = 0.6, -0.62          # Taubin: mu slightly under -lambda is the pass-band


@dataclass
class Timing:
    """Per-phase wall clock, because the phase split is the whole diagnostic."""
    stages: dict

    def report(self) -> str:
        w = max(len(k) for k in self.stages)
        return "\n".join(f"  {k.ljust(w)}  {v:6.2f}s" for k, v in self.stages.items())


def _sync(dev: torch.device) -> None:
    if dev.type == "mps":
        torch.mps.synchronize()
    elif dev.type == "cuda":
        torch.cuda.synchronize()


def extract(
    lab: np.ndarray,
    ijk_to_ras: np.ndarray,
    *,
    device: str = "cpu",
    smooth_iters: int = DEFAULT_SMOOTH_ITERS,
    normal_smooth: int = DEFAULT_NORMAL_SMOOTH,
    only: set[int] | None = None,
) -> tuple[list[dict], Timing]:
    """One closed surface per label.

    `lab` is (Z, Y, X) -- the array order SimpleITK and numpy use. The TypeScript indexes
    (k * ny + j) * nx + i, which is the same layout.

    Returns a list of {"label", "positions", "normals", "indices"} with positions in RAS.
    """
    dev = torch.device(device)
    t = {}
    t0 = time.perf_counter()

    def mark(name: str) -> None:
        _sync(dev)
        t[name] = time.perf_counter() - t0 - sum(t.values())

    lab_t = torch.from_numpy(np.ascontiguousarray(lab)).to(dev)
    Z, Y, X = lab_t.shape
    cz, cy, cx = Z - 1, Y - 1, X - 1
    if min(cx, cy, cz) < 1:
        return [], Timing(t)
    mark("upload")

    # ── PHASE 1a: which cells straddle a label boundary ──
    # Corners as strided views, so no copy. (dx, dy, dz) has to be applied as (dz, dy, dx) here.
    corners = [lab_t[dz:dz + cz, dy:dy + cy, dx:dx + cx] for (dx, dy, dz) in CORNER]
    has_vert = torch.zeros((cz, cy, cx), dtype=torch.bool, device=dev)
    for k in range(1, 8):
        has_vert |= corners[k] != corners[0]
    mark("1a boundary mask")

    # ── PHASE 1b: compaction. torch.nonzero IS the multi-level prefix sum, in one call. ──
    cell_lin = torch.nonzero(has_vert.reshape(-1), as_tuple=False).squeeze(1)
    n_v = int(cell_lin.numel())
    if n_v == 0:
        return [], Timing(t)
    mark("1b compaction")

    # A DENSE cell -> vertex index map. This is the 1.67 GB array that killed the first TypeScript
    # version, and it is affordable here only because torch keeps it off the JS heap and this runs on
    # a machine with room. It is the one place a port to constrained hardware must tile by z-slab.
    cell_to_v = torch.full((cz * cy * cx,), -1, dtype=torch.int32, device=dev)
    cell_to_v[cell_lin] = torch.arange(n_v, dtype=torch.int32, device=dev)

    kz = (cell_lin // (cy * cx)).to(torch.int64)
    rem = cell_lin % (cy * cx)
    ky = (rem // cx).to(torch.int64)
    kx = (rem % cx).to(torch.int64)
    mark("1b index map")

    # ── PHASE 1c: vertex positions, for the compacted cells only ──
    # A label boundary is categorical, so each crossing contributes its edge MIDPOINT; averaging them
    # still pulls the vertex toward the true surface rather than the cell centre.
    cvals = torch.stack([lab_t[kz + dz, ky + dy, kx + dx] for (dx, dy, dz) in CORNER])
    acc = torch.zeros((3, n_v), dtype=torch.float32, device=dev)
    cnt = torch.zeros(n_v, dtype=torch.float32, device=dev)
    for (a, b) in CELL_EDGES:
        cross = (cvals[a] != cvals[b]).to(torch.float32)
        ca, cb = CORNER[a], CORNER[b]
        for d in range(3):                                   # d: 0=x, 1=y, 2=z
            acc[d] += cross * ((ca[d] + cb[d]) / 2.0)
        cnt += cross
    verts_ijk = torch.stack([kx.to(torch.float32) + acc[0] / cnt,
                             ky.to(torch.float32) + acc[1] / cnt,
                             kz.to(torch.float32) + acc[2] / cnt], dim=1)
    mark("1c vertex positions")

    # ── PHASE 2: quads ──
    # A face between voxel A and voxel B belongs to BOTH: it is the outside of A and the outside of B,
    # so it is emitted into each one's mesh with opposite winding. Background (0) gets no mesh.
    quad_a, quad_b, quad_v = [], [], []
    for axis in range(3):                                    # 0=x, 1=y, 2=z, in voxel space
        tor_ax = 2 - axis                                    # torch dim: x is last
        lo = lab_t.narrow(tor_ax, 0, lab_t.shape[tor_ax] - 1)
        hi = lab_t.narrow(tor_ax, 1, lab_t.shape[tor_ax] - 1)
        diff = lo != hi
        f_lin = torch.nonzero(diff.reshape(-1), as_tuple=False).squeeze(1)
        if f_lin.numel() == 0:
            continue
        sz, sy_, sx_ = diff.shape
        fk = (f_lin // (sy_ * sx_)).to(torch.int64)
        fr = f_lin % (sy_ * sx_)
        fj = (fr // sx_).to(torch.int64)
        fi = (fr % sx_).to(torch.int64)

        a_lab = lab_t[fk, fj, fi]
        b_lab = hi.reshape(-1)[f_lin]

        # The four cells around this face; every one must exist, or the TypeScript skips the quad.
        keep = torch.ones_like(fi, dtype=torch.bool)
        vids = []
        for (di, dj, dk) in FACE_CELLS[axis]:
            ci, cj, ck = fi + di, fj + dj, fk + dk
            ok = (ci >= 0) & (cj >= 0) & (ck >= 0) & (ci < cx) & (cj < cy) & (ck < cz)
            lin = (ck.clamp(0, cz - 1) * cy + cj.clamp(0, cy - 1)) * cx + ci.clamp(0, cx - 1)
            v = cell_to_v[lin]
            keep &= ok & (v >= 0)
            vids.append(v)
        if not bool(keep.any()):
            continue
        quad_a.append(a_lab[keep].to(torch.int32))
        quad_b.append(b_lab[keep].to(torch.int32))
        quad_v.append(torch.stack([v[keep] for v in vids], dim=1))

    if not quad_v:
        return [], Timing(t)
    qa = torch.cat(quad_a)
    qb = torch.cat(quad_b)
    qv = torch.cat(quad_v).to(torch.int64)
    mark("2  quads")

    return _finish(lab_t, verts_ijk, qa, qb, qv, ijk_to_ras, dev, smooth_iters, normal_smooth, only, t, t0, mark)


def _finish(lab_t, verts_ijk, qa, qb, qv, ijk_to_ras, dev, smooth_iters, normal_smooth, only, t, t0, mark):
    """Phases 3-4: Taubin smoothing on the shared vertices, then one mesh per label.

    MEASURED AND DISAPPOINTING. These phases do NOT benefit from torch, and the numbers are here so
    nobody re-derives them: 48 Taubin passes over 5.7 M vertices and 48 M directed edges cost 40.7 s
    via `index_add_` on CPU (22.4 s on MPS) and 10.0 s via the padded gather table used below -- while
    the TypeScript does the WHOLE of phases 3-4 in 11.2 s with a CSR adjacency. A contiguous
    per-vertex neighbour list in a tight loop beats materialising a (n_v, K, 3) tensor every pass.

    So the torch win is confined to phases 1-2 (13.9 s -> 1.3 s). See GREASED-LIGHTNING.md.
    """
    n_v = verts_ijk.shape[0]

    # ── PHASE 3: Taubin smoothing on the SHARED vertices ──
    # Shared is the point: every label meeting in a cell uses that cell's one vertex, so smoothing
    # moves them together and no seam can open. That is what Slicer's separate "joint smoothing"
    # option exists to prevent, obtained here from the representation instead.
    if smooth_iters > 0:
        # Edges from quad sides, both directions.
        e_src = torch.cat([qv[:, 0], qv[:, 1], qv[:, 2], qv[:, 3],
                           qv[:, 1], qv[:, 2], qv[:, 3], qv[:, 0]])
        e_dst = torch.cat([qv[:, 1], qv[:, 2], qv[:, 3], qv[:, 0],
                           qv[:, 0], qv[:, 1], qv[:, 2], qv[:, 3]])
        # A PADDED NEIGHBOUR TABLE, not a CSR: sort by source, then place each vertex's neighbours in
        # a fixed-width row. Duplicates are kept -- a Laplacian weights by how many times a neighbour
        # is seen, and the TypeScript CSR keeps them too, so dropping them here would change the
        # result and break parity.
        order = torch.argsort(e_src)
        s_src, s_dst = e_src[order], e_dst[order]
        deg = torch.bincount(s_src, minlength=n_v)
        K = int(deg.max().item())
        start = torch.cumsum(deg, 0) - deg
        # Column index of each edge within its vertex's row.
        col = torch.arange(s_src.numel(), device=dev, dtype=torch.int64) - start[s_src]
        nbr = torch.zeros((n_v, K), dtype=torch.int64, device=dev)
        msk = torch.zeros((n_v, K), dtype=torch.bool, device=dev)
        nbr[s_src, col] = s_dst
        msk[s_src, col] = True
        mark("3a neighbour table")

        p = verts_ijk.to(torch.float64)
        degf = deg.clamp(min=1).to(torch.float64).unsqueeze(1)
        mskf = msk.unsqueeze(2)

        def step(f: float) -> None:
            nonlocal p
            s = (p[nbr] * mskf).sum(1)                 # (n_v, 3)
            p = p + f * (s / degf - p)

        # TWO PASSES PER ITERATION, the second negative. A Laplacian pass alone shrinks the surface
        # every time; Taubin's second pass pushes back slightly harder, cancelling the shrinkage.
        for _ in range(smooth_iters):
            step(LAMBDA)
            step(MU)
        verts_ijk = p.to(torch.float32)
        mark("3b taubin")

    # ── into RAS. Affine, so it commutes with the smoothing above and may be applied either side. ──
    m = torch.tensor(np.asarray(ijk_to_ras, dtype=np.float32).reshape(4, 4), device=dev)
    ones = torch.ones((n_v, 1), dtype=torch.float32, device=dev)
    verts_ras = (torch.cat([verts_ijk, ones], dim=1) @ m[:3, :].T)
    mark("3c to RAS")

    # ── PHASE 4: one mesh per label ──
    # Each face is emitted into BOTH neighbouring labels, reversed for the b side, so a parcel is
    # never rendered inside-out.
    labels = torch.cat([qa, qb]).unique()
    labels = labels[labels != 0]
    out = []
    v_np = verts_ras.cpu().numpy()
    qa_c, qb_c, qv_c = qa.cpu(), qb.cpu(), qv.cpu()
    for lv in labels.cpu().tolist():
        if only is not None and lv not in only:
            continue
        fwd = qa_c == lv
        rev = qb_c == lv
        parts = []
        if bool(fwd.any()):
            parts.append(qv_c[fwd])
        if bool(rev.any()):
            parts.append(qv_c[rev].flip(1))            # reversed winding for the b side
        if not parts:
            continue
        quads = torch.cat(parts)
        # Global -> local vertex indices for this label.
        used, inv = torch.unique(quads.reshape(-1), return_inverse=True)
        local = inv.reshape(quads.shape)
        tris = torch.stack([local[:, 0], local[:, 1], local[:, 2],
                            local[:, 0], local[:, 2], local[:, 3]], dim=1).reshape(-1)
        pos = v_np[used.numpy()]
        out.append({"label": int(lv), "positions": pos,
                    "indices": tris.numpy().astype(np.uint32), "normals": None})
    mark("4  per-label meshes")

    # ── normals: area-weighted, then smoothed. Geometry is untouched. ──
    for mesh in out:
        mesh["normals"] = _normals(mesh["positions"], mesh["indices"], normal_smooth)
    mark("4b normals")
    return out, Timing(t)


def _normals(pos: np.ndarray, idx: np.ndarray, passes: int) -> np.ndarray:
    """Area-weighted vertex normals, then `passes` of averaging with neighbours.

    The unnormalised cross product is already proportional to triangle area, so summing it weights
    big triangles more -- which is what you want. Angle weighting was measured against this on
    anisotropic voxels and made no difference: 16.1 vs 16.1 degrees.
    """
    p = torch.from_numpy(pos)
    i = torch.from_numpy(idx.astype(np.int64)).reshape(-1, 3)
    a, b, c = p[i[:, 0]], p[i[:, 1]], p[i[:, 2]]
    fn = torch.cross(b - a, c - a, dim=1)
    n = torch.zeros_like(p)
    for k in range(3):
        n.index_add_(0, i[:, k], fn)
    n = torch.nn.functional.normalize(n, dim=1, eps=1e-12)
    if passes > 0:
        e_src = torch.cat([i[:, 0], i[:, 1], i[:, 2], i[:, 1], i[:, 2], i[:, 0]])
        e_dst = torch.cat([i[:, 1], i[:, 2], i[:, 0], i[:, 0], i[:, 1], i[:, 2]])
        for _ in range(passes):
            acc = n.clone()
            acc.index_add_(0, e_src, n[e_dst])
            n = torch.nn.functional.normalize(acc, dim=1, eps=1e-12)
    return n.numpy().astype(np.float32)
