# Contributing to SlicerAlbula

Please open an issue rather than a pull request.

SlicerAlbula is written with AI assistance and changes fast. Whole parts get replaced rather
than patched, so a pull request against today's code is often against code that no longer
exists, and I cannot review it fairly.

Most of what you see here belongs to someone else. The renderer and the application shell are
Steve Pieper's SlicerLive; the segmentation server is Michael Halle's haversack; the DICOM
database and toolchain are 3D Slicer's. A fix to any of those belongs in its own repository.

## What helps

**A wrong number.** This is medical research software written with AI assistance. Coordinate
systems, units, voxel ordering, and DICOM round trips are exactly where it will be wrong in
ways that look right. If you can show a wrong number, please do. Those get fixed first.

**A bug report.** If I cannot reproduce it, I cannot analyze it. So: what you did, what you
expected, and what happened. Include the build stamp from the corner of the module column — it
tells me which version you have, and I have lost days to that question. Include the data if it
is public, for instance as a series UID from the
[IDC](https://portal.imaging.datacommons.cancer.gov). **Do not attach patient data.**

**A measurement.** If something is slow, tell me how slow and on what. See
[Ron's Rules for Tools](Contents/docs/RULES-FOR-TOOLS.md), rule 5.

**An anatomical correction.** Structure names follow TA2. If a structure is in the wrong
place in the tree, that is a bug.

**A feature request** that describes what you are trying to do and why the current behavior
is in the way. How 3D Slicer does it is usually the answer.

## License

Apache-2.0. Anything you post in an issue is offered under the same terms.
