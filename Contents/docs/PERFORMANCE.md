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

**Ask why the work is where it is.** Making a slow step faster can make its place look right. The
surface step above, once 7.9x faster on the processor, stayed there for two weeks — until the user
asked whether the whole load could run on the graphics card, where the segmentation already was.
Rewritten for the card, reading the data in place, it went from 20.9 to 2.2 seconds with the same
triangles. The earlier check that said "the GPU is slower" was right about the port it measured; it
was not the last word on the step.

**Time the whole thing, as the user sees it, and count every step.** "Loading" means from the click
until the display is stable, not the part that is easy to time. A profile that times and counts
each step found, on its first run, every segmentation of a scene being built twice. Counting found
what timing alone would not have.

**A busy page looks like slow input.** Stored surfaces took seconds to "read" from a server that
answered in milliseconds: the page's one thread was busy decoding, and everything else waited
behind it. Measure how long the page is blocked, not only how long each step takes. With the
double builds gone and that work moved off the page, a scene with a CT and four whole-body
segmentations went from 18.7 to 4.9 seconds; a compressed working copy of the CT beside its DICOM
files took it to 4.4.

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
  compaction and iterative neighbor gathers — unless the work is restructured for it (one bit per
  cell, prefix sums instead of lookup tables). Measure before porting, and measure the port.
- **WebGPU implementations disagree.** Deno's accepted a buffer bound twice and 31 storage buffers
  per shader; Chrome refused both (its limit is 10; the standard promises 8). Develop against the
  standard's limits and test in the browser that ships. The surfaces-on-the-card numbers above are
  Chrome's; the application's own WebKit window has not been measured yet, so the switch is off by
  default.
- **A hidden browser tab is not a measurement.** Its timers are throttled to about once a second,
  which reads as the page stalling.
- **Memory peaks at 11.7 GB** on a whole-body CT with a 111-structure segmentation. It comes back
  down — it is not a leak — but a 16 GB Mac cannot run that case, and the DMG says so.
- **FastSurfer on Apple Silicon has a size ceiling** at about 379³ voxels. Crop to 360³ or below.

## Reproducing the numbers

Everything above is measured on `C3N-01524`, a public CPTAC case; see [`Contents/data/README.md`](../data/README.md).
Segmented with `ts:total`, a correct surface extraction produces exactly 12,121,372 triangles;
with `ts.v2:total` (111 structures), 12,137,916 — on the processor and on the graphics card alike.
