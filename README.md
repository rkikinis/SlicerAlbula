# SlicerAlbula

⚠️ **EXPERIMENTAL & AI-ASSISTED** — This is an early-stage research project deliberately written with AI-assisted coding. Expect rapid change, incomplete features, and rough edges. Use at your own risk in production.

> ## This software is not intended for clinical use.
> ## Slicer is NOT an FDA approved medical device.

## What this is

SlicerAlbula is my sandbox. I want to experiment on how to improve the user experience. I am
leveraging my decades of experience, which I put into writing in 2014 in
[Ron's Rules for Tools](Contents/docs/RULES-FOR-TOOLS.md).

SlicerAlbula is work in progress, living out the "publish early, publish often" concept. It
leverages the efforts of other people, including [3D Slicer](https://github.com/Slicer/Slicer#readme),
[SlicerLive](https://github.com/pieper/SlicerLive#readme) by Steve Pieper and
[haversack](https://github.com/mhalle/haversack#readme) by Michael Halle.

## What it does today

- A 3D Slicer-style DICOM database browser, with changes to the defaults: derived series are
  nested under the series they came from, the text shown is the text you need, and there is a
  reader and writer for a DICOM-compliant round trip of surfaces.
- GPU-accelerated versions of more than 70 trained AI segmentation networks, through the
  haversack platform.
- 2D viewers of grayscale images with overlays of the segmentations. A 3D viewer with GPU
  accelerated volume and surface rendering.
- Custom hierarchical organization of anatomical structures, compliant with
  [TA2](https://ta2viewer.openanatomy.org/).
- A crop box with handles in all viewers, aligned to the volume's own axes. The cropped
  volume goes back into the DICOM database as a derived series, with its provenance recorded.

## Installation

The application will be distributed as a signed, notarized DMG under Releases: drag it to
Applications and open it. It needs a Mac with plenty of memory — a whole-body case has peaked
at 11.7 GB.

As an alternative, SlicerAlbula can be built from GitHub. You need
[3D Slicer](https://download.slicer.org), [deno](https://deno.land) and
[uv](https://docs.astral.sh/uv/).

```
git clone --recurse-submodules https://github.com/rkikinis/SlicerAlbula
cd SlicerAlbula
"Contents/tools/Rebuild SlicerAlbula App.command"
./StartSlicerAlbula.command
```

**Where the source stands (September 2026):** the application is a branch of SlicerLive with
about 300 commits of my own on it. That branch is not published yet — I have written to its
author first, and it goes up under `Contents/src/SlicerLive` when we have talked. Until then the
build step above will not find it; the data model it rests on is already public as
[SlicerAlbula-core](https://github.com/rkikinis/SlicerAlbula-core), and `Contents/src/live`
(Steve Pieper's gallery, unchanged) is a submodule.

AI segmentation needs haversack running:

```
uvx --python 3.12 --from "haversack[serve,remote] @ git+https://github.com/mhalle/haversack@v0.12.0" haversack serve --port 8790 --allow-transpose
```

There is no data in this repository. The test cases are public and come from the
[Imaging Data Commons](https://portal.imaging.datacommons.cancer.gov). [`Contents/data/README.md`](Contents/data/README.md)
lists them, and `Contents/data/fetch-idc.py` downloads them.

## What it is built on

- **[haversack](https://github.com/mhalle/haversack)**, Michael Halle. One command in front
  of every segmentation network. Nothing here wraps a network itself.
- **[SlicerLive](https://github.com/pieper/SlicerLive)** and **[live](https://github.com/pieper/live)**,
  Steve Pieper. The renderer and the application shell. Albula is a branch of his work.
- **[3D Slicer](https://slicer.org)**. The DICOM database, dcmqi, and the toolchain this
  interoperates with.
- **[duckn](https://github.com/mhalle/duckn)**, Michael Halle, for the lossless DICOM–zarr
  round trip. The structure tree follows his [Open Anatomy Browser](https://www.openanatomy.org/).
- TotalSegmentator and the other networks, each cited with its paper inside the AI module.
  [dcmjs](https://github.com/dcmjs-org/dcmjs) for DICOM in the browser. Terminologia
  Anatomica and SNOMED CT for the names.

## Funding

Most 3D Slicer funding has come from government sources and many of those programs have
ended, so Slicer's funder list is not reproduced here. Current work, including
SlicerAlbula, is supported by NIH grant
[R01 CA310962](https://reporter.nih.gov/search/NqGZkegLQkaxQEbLxCXMdw/project-details/11343589#description).

## The name

The Albula Pass joins the Rhine valley to the Engadin, in Graubünden. It was a mule track in
Roman times — grain and wine going up, cheese, honey and hides coming back — and the bishops
of Chur took a toll on it through the Middle Ages. What prevented the building of a road was never the
summit: it was the gorge below Bergün, first blasted open with gunpowder in 1695; the post road came
in 1866 and the railway in 1903, which goes through the mountain instead and is a World
Heritage Site. That is the pattern I keep meeting: the hard part is rarely where you expect
it. Surface extraction took 118 seconds; the algorithm was fine and one loop in the webview's
JavaScript engine was not. Dates from Wikipedia's article on the
[Albula Pass](https://en.wikipedia.org/wiki/Albula_Pass). The road in the logo leads to
that pass.

## Contributing, license

Open an issue rather than a pull request — [CONTRIBUTING.md](CONTRIBUTING.md) says why.
Apache-2.0, see [LICENSE](LICENSE). Ron Kikinis, 2026.
