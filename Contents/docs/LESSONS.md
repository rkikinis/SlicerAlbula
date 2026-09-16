# Lessons

Working with an LLM on this project. Three general principles, then the things specific to
SlicerAlbula.

## General

**1. Get the facts. Do not guess from stale or nonexistent information.** This is the most
important one, and the root cause of most of the wasted rounds. I had to remind the LLM several
times; within a day it slid back into guessing, often wrong. Two examples from this project's own
documentation: a test corpus described as "a few hundred megabytes" that measures 932 MB, and
eight historical dates published with no source. Both were one command away from being facts.
Before writing a number, a path, a size, a version, or a claim about what code does: read it, and
say where it came from.

**2. Do not flatter.**

**3. When a prompt is ambiguous, ask and confirm.** Again: do not guess.

## Project-specific

- **Read a tool's documented limits before reporting its behavior as a bug.** FastSurfer
  supports 0.7 mm to 1 mm voxels; the studyforrest T1 is 0.67 mm. A session measured the Metal
  tensor ceiling (2³² elements, ~379³ at 79 classes), wrote it up as a haversack limit and told
  Mike Halle — who pointed at the paper. The number was right and the framing was wrong: the input
  was outside what the model is built for. Mike has since made haversack accept 0.5 mm input and
  run it at the supported resolution; Albula does nothing about voxel size (Ron, 2026-09-12:
  "we should hold off").
- **A write that succeeds is not a write that lands.** dcmjs copies a fixed list of attributes
  per SEG segment; a laterality modifier placed beside them was silently dropped, and only reading
  the file back with a second library (pydicom) showed it. Verify the effect, not the path.
- **Read the build stamp before reporting a bug.** Bottom right of the window. A running
  application keeps the bundle it loaded, and three debugging rounds went to a window that had
  not been restarted.
- **Thirty seconds is fine, a minute is acceptable, past that people leave.** Anything slower is
  run as a job: started, left running, delivered when ready, with a notification that offers to go
  and look or to carry on.
- **One session drives.** Two sessions on the same tree, both clean, is how work gets lost. Say
  which one holds the edits.
- **If it is not in writing, it does not exist.** The next session starts from the files, not from
  what was said to the last one.
- **"The image disappeared" is a killed page process until proven otherwise.** The session log
  shows it: a "native shell" line with no "session start" before it is the page reloading on its
  own. Five volumes in time, each kept twice on the CPU and twice on the GPU, was 11 GB; the
  webview drew the line long before the machine did. Count the copies before adding a frame.
- **A shared GPU texture is keyed by its content, never by the thing it belongs to.** A label
  texture keyed by segmentation id was replaced under a field that still read it, and the renderer
  died on a destroyed texture. Key by content signature; free after the last holder, a beat later.
- **A model that runs in the library may still not run in the server.** haversack refused a
  transposed nnU-Net through `serve` while the Python API took a flag for it. The answer was the
  API, a NRRD on disk, and the result placed where the application already restores from.
