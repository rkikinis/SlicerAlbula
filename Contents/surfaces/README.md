# `Contents/surfaces/` — surface nets in torch

One implementation, device chosen at runtime (CPU / MPS / CUDA), following haversack's `backends/`
architecture: a portable reference that any device can run. Ron: *"Our GPU code should also run on
other platforms. Perhaps using Mike's architecture."*

```
<python-with-torch> Contents/surfaces/run.py [labelmap.nrrd] [cpu|mps|cuda]
```

## It is CORRECT, and it is SLOWER than what ships. Both were verified.

Parity against `Contents/src/SlicerLive/algorithms/surface-nets.ts` is exact — on NEPHROGENIC `ts:total`,
**6,061,448 vertices and 12,121,372 triangles, matching digit for digit**; on a 40³ sphere, identical
vertex and triangle counts and identical radius statistics to two decimals (mean 11.94, min 11.56,
max 12.08). It is watertight (Euler characteristic 2), normals point outward, and two touching labels
share their vertices.

But end to end it is **32.4 s against the TypeScript's 25.0 s**, and the phase split says exactly why:

| phase | TypeScript | torch (CPU) | |
|---|---|---|---|
| 1-2 mask, compaction, vertices, quads | 13.9 s | **1.71 s** | **8x faster** |
| 3 Taubin smoothing (48 passes) | ~4.7 s | **20.2 s** | 4x slower |
| 4 per-label meshes | ~1.1 s | 2.7 s | slower |
| 4b normals | ~4.6 s | 5.9 s | slower |
| **total** | **25.0 s** | **32.4 s** | |

**Vectorised set operations win enormously; iterative neighbour gathers lose badly.** Phases 1-2 are a
boundary mask and a compaction — `torch.nonzero` over 417 M elements is one call and beats a
hand-written loop eightfold. Phase 3 is 48 passes of "average each vertex with its neighbours", and
torch materialises a 48 M x 3 gather (1.16 GB) on every pass, where the TypeScript's CSR loop
accumulates in registers. Alternatives were measured and none helps: `index_add_` 40.7 s,
`segment_reduce` 22.0 s, a padded neighbour table 16.9-20.2 s.

**The GPU is worse still**, which is the other thing this settled. Phases 1-2 on MPS take 4.3 s
against 1.3 s on CPU, because compaction is irregular rather than streaming: `torch.nonzero` over
417 M elements costs 1.81 s on MPS against 0.15 s on CPU.

## What this is for

1. **The answer to "can we use Mike's multi-platform infrastructure?"** — measured rather than
   guessed. It works, it is portable, and it does not meet the 33 s target by this route.
2. **A second independent implementation** of an algorithm whose output Ron has accepted. Exact parity
   from a completely different execution model is strong evidence the TypeScript is right.
3. **It located the win precisely**: phases 1-2 are 56% of the TypeScript's time and are the part that
   vectorises. That is where parallel workers should be aimed, and this measured the ceiling — 8x.

See `Contents/src/SlicerLive/docs/GREASED-LIGHTNING.md` for the decision this fed into.
