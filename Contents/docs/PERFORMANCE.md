# Performance

The goal is software that feels immediate — the response arrives before the question is
forgotten. Thirty seconds is fine, a minute is acceptable, past that people leave. A correct
feature that takes two minutes is not shipped. This document is what that rule has taught, in
general terms.

## The problem

The application runs in a WebKit webview. Every benchmark, test and profiler runs somewhere else.
Numbers measured in the wrong place are not estimates; they are wrong, and they look exactly like
right ones.

## Principles

**Measure where it ships.** The webview runs JavaScriptCore; `deno` and `node` run V8. On one
tight loop the two engines differed by 6.9x. That single ratio was a 118-second wait, and it
survived three expensive plans because every measurement had been taken in V8. The fix was 30
lines; the application went from 118 seconds to 15. A test now runs the same code in both engines
and fails if they drift apart.

**Measure the real data.** A synthetic case said a change was worth 2.4x; the real data said 16%.
The real data is one file away.

**Before planning a big change, check that the assumption behind it is true.** A GPU port was
planned at two to three weeks on the assumption it would be 20–30x faster. One hour of measurement
showed 3.2x, with the GPU slower than the CPU. The check had been on the plan's to-do list from
the first draft and was done last. Do it first; it is the cheapest step and the only one that can
cancel the rest.

**Past the budget, run it as a job.** Faster is the first answer. When it is not available, the
work is started, left running while the user does something else, and delivered when ready — with
a notification that offers to go and look or to carry on. A tool that blocks is a tool nobody uses.

**Put the number on the screen.** Every load, every extraction, every job reports how long it took,
where the user can read it. A number nobody can see is a number nobody can hold you to.

## Known issues

- **JavaScriptCore punishes what V8 forgives:** closures called per element, arrays of arrays,
  `for (const [a, b] of pairs)` in an inner loop, per-iteration array literals. Flat typed arrays and
  precomputed offsets are the remedy. The fix is invisible in V8, so only the two-engine test can
  catch a regression.
- **The GPU is not automatically faster.** It wins on streaming work and loses on irregular
  compaction and iterative neighbor gathers. Measure before porting.
- **Memory peaks at 11.7 GB** on a whole-body CT with a 111-structure segmentation. It comes back
  down — it is not a leak — but a 16 GB Mac cannot run that case, and the DMG says so.
- **FastSurfer on Apple Silicon has a size ceiling** at about 379³ voxels. Crop to 360³ or below.

## Reproducing the numbers

Everything above is measured on `C3N-01524`, a public CPTAC case; see [`Contents/data/README.md`](../data/README.md).
Segmented with `ts:total`, a correct surface extraction produces exactly 12,121,372 triangles.
