#!/bin/bash
# Rebuilds slicer-app.js from the TypeScript source into the gallery, after editing
# anything under Contents/src/SlicerLive. Paths are relative to THIS script.
# THE REPO ROOT, which is now our PARENT: these three moved into Contents/tools/ so the folder Ron opens
# holds only the launcher he uses. Everything below is still relative to the root.
SCRIPT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"   # the workspace root: Contents/tools/ lives under Contents/
SRC="$SCRIPT_DIR/Contents/src/SlicerLive"
GALLERY="$SCRIPT_DIR/Contents/src/live"
DENO="$(command -v deno || echo /opt/homebrew/bin/deno)"

if [ ! -x "$DENO" ]; then
  echo "deno not found. Install with:  brew install deno"
  exit 1
fi

cd "$SRC" || exit 1

# THE TESTS RUN FIRST. Ron, 2026-09-17: "please add tests when you are compiling." 131 test
# files, about 45 s; a failure stops the build here with the failing tests named, so a broken
# bundle is never what the app serves. --no-check is the known state of this tree (type-checking
# fails on hundreds of Uint8Array<ArrayBufferLike> errors and runs nothing); "ALL PASS" in the
# records has always meant this run. Skip with:  ALBULA_SKIP_TESTS=1 "<this script>"
# when iterating on one thing with the tests known green -- and say so in the record.
# THE DUCKN COPY'S CODE, from the converter's sources, before the tests (one of which checks it) and
# before the server is compiled with it. A copy made by other code is not used (desktop/make-copy-code.ts).
"$DENO" run -A desktop/make-copy-code.ts | sed 's/^/      /' || exit 1

if [ "${ALBULA_SKIP_TESTS:-0}" != "1" ]; then
  echo "Tests first (deno test -A --no-check --unstable-ffi in $SRC)…"
  T0=$(date +%s)
  TEST_OUT="$(mktemp -t albula-tests)"
  if "$DENO" test -A --no-check --unstable-ffi > "$TEST_OUT" 2>&1; then
    echo "      tests: $(sed 's/\x1b\[[0-9;]*m//g' "$TEST_OUT" | grep -aE '^ok \| [0-9]+ passed' | tail -1 | sed 's/^ok | //')  ($(( $(date +%s) - T0 )) s)"
  else
    echo
    echo "TESTS FAILED — nothing was built. The failures:"
    sed 's/\x1b\[[0-9;]*m//g' "$TEST_OUT" | grep -aE "\.\.\. FAILED|^FAILED \|" | head -30
    echo "  full output: $TEST_OUT"
    exit 1
  fi
  rm -f "$TEST_OUT"
else
  echo "      tests: SKIPPED (ALBULA_SKIP_TESTS=1)"
fi

# THE BUILD STAMP, compiled into EVERY bundle so each one can say which build it IS.
# The app serves files from disk, so a window can sit for hours on JS that predates the last
# rebuild, with nothing on screen to say so -- which sent two rounds of debugging after a bug that
# had already been fixed. Baked in with --define, NOT read from the server at runtime: read at
# runtime it would describe the disk, which is the misleading thing we are trying to fix.
#
# THE WORKERS GET IT TOO, and that is not decoration. The page was cache-busted here and the workers
# were not, so a stale worker ran under a fresh page -- and since the on-screen stamp comes from the
# page, it reported the new build while old code did the work. Ron, after a rebuild that doubled the
# smoothing: "19:23 version. Nothing changes in a noticable way, once the algorithm runs." Each
# bundle now carries its own stamp and the surface worker reports its stamp with its result, so the
# two can be compared instead of assumed.
# The stamp names the VERSION as well as the moment and the commit, so a screenshot from someone
# else's machine says which release they are on without them having to look it up.
ALBULA_VERSION="$(tr -d '[:space:]' < "$SCRIPT_DIR/VERSION" 2>/dev/null || echo 0.0.0)"
BUILD_ID="v$ALBULA_VERSION $(date '+%b %e %H:%M')"
if command -v git >/dev/null 2>&1 && git -C "$SRC" rev-parse --git-dir >/dev/null 2>&1; then
  BUILD_SHA="$(git -C "$SRC" rev-parse --short HEAD 2>/dev/null)"
  [ -n "$(git -C "$SRC" status --porcelain 2>/dev/null)" ] && BUILD_SHA="$BUILD_SHA+"
  BUILD_ID="$BUILD_ID $BUILD_SHA"
fi

# THE MESH CODE FINGERPRINT: a hash of the source files that turn a stored surfaces object into
# the meshes the renderer draws (the DICOM surface reader, the decimator and its worker, the
# cache format, the vendored simplifier). Every mesh cache in the database records the fingerprint
# that made it (logic/mesh-cache.ts, MESH_CODE) and the server refuses one made by other code --
# so a fix to any of these files remakes every cache on its next load, and no one has to
# remember to bump a version. It is NOT the build stamp on purpose: that changes on every rebuild
# and would throw away 300 MB caches for a change to a menu.
MESH_CODE="$(cat "$SRC/logic/readers/dicom-surface.ts" "$SRC/logic/decimate.ts" "$SRC/algorithms/decimate-worker.ts" \
  "$SRC/logic/mesh-cache.ts" "$SRC/render/vendor/meshoptimizer/meshopt_simplifier.module.js" | shasum -a 256 | cut -c1-12)"

echo "Bundling render/demos/slicer-app.ts -> $GALLERY/webgpu/slicer-app.js  (build $BUILD_ID, mesh code $MESH_CODE)"
"$DENO" run -A npm:esbuild render/demos/slicer-app.ts \
  --bundle --format=esm \
  "--define:__BUILD_ID__=\"$BUILD_ID\"" \
  "--define:__MESH_CODE__=\"$MESH_CODE\"" \
  --outfile="$GALLERY/webgpu/slicer-app.js" || exit 1

# The ingest worker is a SECOND entry point, bundled beside the page bundle. volumeToZarr looks for
# ./ingest-worker.js relative to the document, so it must land in the same directory as the page.
# The surface-extraction worker, same arrangement and for the same reason: it is looked up relative
# to the document, so it has to land beside the page bundle.
echo "Bundling algorithms/surface-nets-worker.ts -> $GALLERY/webgpu/surface-nets-worker.js"
"$DENO" run -A npm:esbuild algorithms/surface-nets-worker.ts \
  --bundle --format=esm \
  "--define:__BUILD_ID__=\"$BUILD_ID\"" \
  --outfile="$GALLERY/webgpu/surface-nets-worker.js" || exit 1

echo "Bundling algorithms/decimate-worker.ts -> $GALLERY/webgpu/decimate-worker.js"
"$DENO" run -A npm:esbuild algorithms/decimate-worker.ts \
  --bundle --format=esm \
  "--define:__BUILD_ID__=\"$BUILD_ID\"" \
  --outfile="$GALLERY/webgpu/decimate-worker.js" || exit 1

# The codec worker, and the vendored WebAssembly codecs it fetches from ./vendor/codecs/ beside it
# (render/vendor/codecs/README.md: what they are, their versions and licenses).
echo "Bundling algorithms/codec-worker.ts -> $GALLERY/webgpu/codec-worker.js"
"$DENO" run -A npm:esbuild algorithms/codec-worker.ts \
  --bundle --format=esm \
  "--define:__BUILD_ID__=\"$BUILD_ID\"" \
  --outfile="$GALLERY/webgpu/codec-worker.js" || exit 1
mkdir -p "$GALLERY/webgpu/vendor/codecs"
cp "$SRC"/render/vendor/codecs/*.js "$SRC"/render/vendor/codecs/*.wasm "$GALLERY/webgpu/vendor/codecs/"

# The segmentation decoder: the largest single-threaded phase of a load until 2026-09-22.
echo "Bundling algorithms/seg-decode-worker.ts -> $GALLERY/webgpu/seg-decode-worker.js"
"$DENO" run -A npm:esbuild algorithms/seg-decode-worker.ts \
  --bundle --format=esm \
  "--define:__BUILD_ID__=\"$BUILD_ID\"" \
  --outfile="$GALLERY/webgpu/seg-decode-worker.js" || exit 1

# Unpacking a compressed labelmap off the page's thread (render/zarr.ts, assembleInWorker). Without
# this file the page falls back to unpacking on its own thread and says so in the console.
echo "Bundling render/zarr-assemble-worker.ts -> $GALLERY/webgpu/zarr-assemble-worker.js"
"$DENO" run -A npm:esbuild render/zarr-assemble-worker.ts \
  --bundle --format=esm \
  "--define:__BUILD_ID__=\"$BUILD_ID\"" \
  --outfile="$GALLERY/webgpu/zarr-assemble-worker.js" || exit 1

# Fetching and unpacking the pieces of a series' duckn working copy (render/zarr-copy.ts). Without
# this file a load from a copy fails and falls back to the DICOM files, and the status line says so.
echo "Bundling render/zarr-copy-worker.ts -> $GALLERY/webgpu/zarr-copy-worker.js"
"$DENO" run -A npm:esbuild render/zarr-copy-worker.ts \
  --bundle --format=esm \
  "--define:__BUILD_ID__=\"$BUILD_ID\"" \
  --outfile="$GALLERY/webgpu/zarr-copy-worker.js" || exit 1

echo "Bundling logic/ingest-worker.ts -> $GALLERY/webgpu/ingest-worker.js"
"$DENO" run -A npm:esbuild logic/ingest-worker.ts \
  --bundle --format=esm \
  "--define:__BUILD_ID__=\"$BUILD_ID\"" \
  --outfile="$GALLERY/webgpu/ingest-worker.js" || exit 1

# The page and its stylesheet live in the source tree; keep the served copies fresh.
cp "$SRC/render/demos/slicer-app.html" "$SRC/render/demos/theme.css" \
   "$SRC/render/demos/manifest.webmanifest" "$SRC/render/demos/albula-app-icon.png" \
   "$GALLERY/webgpu/"

# VERSION THE ASSET URLS the page imports.
#
# The launchers already append ?nocache=<epoch> to the PAGE url, which was assumed to be enough and
# is not: a freshly fetched page still asks for "slicer-app.js" and "theme.css" by their plain
# names, and the browser happily serves those from cache. So a relaunch could load new HTML around
# an old bundle -- the exact way a fix that was verified as landed kept not being there. It bit this
# session too: a reload came up on the previous build and only the on-screen stamp caught it.
#
# Stamping the URLs makes each build a different resource, so the cache cannot answer for it.
BUILD_TAG="$(printf '%s' "$BUILD_ID" | tr -c 'A-Za-z0-9' '-')"
sed -i '' \
  -e "s|src=\"slicer-app.js\"|src=\"slicer-app.js?v=$BUILD_TAG\"|" \
  -e "s|href=\"theme.css\"|href=\"theme.css?v=$BUILD_TAG\"|" \
  "$GALLERY/webgpu/slicer-app.html"
echo "Done. Reload the app (or run 'Contents/tools/Open SlicerAlbula App.command')."
echo
# Staleness has cost three debugging rounds in this project, so the script REPORTS what the app
# will actually serve rather than asserting it. A "thin" app carries a gallery-path.txt pointing
# back here and therefore always serves what was just built; an older "fat" app carries its own
# embedded copy, which this script does not touch and which then goes stale invisibly.
APP="/Applications/SlicerAlbula.app"
EMBEDDED="$APP/Contents/Resources/gallery/webgpu/slicer-app.js"
POINTER="$APP/Contents/Resources/gallery-path.txt"
echo -n "      just built:    "; stat -f "%Sm" -t "%b %e %H:%M" "$GALLERY/webgpu/slicer-app.js"
if [ -f "$EMBEDDED" ]; then
  echo "      SlicerAlbula.app carries its OWN embedded gallery, which this did NOT rebuild:"
  echo -n "      embedded copy: "; stat -f "%Sm" -t "%b %e %H:%M" "$EMBEDDED"
  echo "      Launching the app from the Dock or Spotlight serves THAT, with no sign it is stale."
  echo "      Either use 'StartSlicerAlbula.command', or rebuild the app itself:"
  echo "        cd Contents/src/SlicerLive && deno run -A desktop/make-app.ts --thin"
elif [ -f "$POINTER" ]; then
  echo "      SlicerAlbula.app is a THIN app: it serves $(cat "$POINTER")"
  if [ "$(cat "$POINTER")" = "$GALLERY" ]; then
    echo "      which is what was just built, so launching it any way you like gives current code."
  else
    echo "      which is NOT the directory just built ($GALLERY). Rebuild the app to repoint it:"
    echo "        cd Contents/src/SlicerLive && deno run -A desktop/make-app.ts --thin"
  fi
else
  echo "      No SlicerAlbula.app found in /Applications; use 'StartSlicerAlbula.command'."
fi

# THE SERVER CODE IS COMPILED IN, SO THIS SCRIPT REBUILDS IT TOO.
#
# The check above catches a stale GALLERY (the JavaScript). desktop/*.ts -- the DICOM index writer,
# the provenance writer, the _db routes -- is `deno compile`d into the binary instead, and for four
# rounds this script only WARNED that it was stale. Warnings do not get read while a test is
# running: on 2026-09-05 provenance edges and the autosave routes had never run because the binary
# was eight hours old, and on 2026-09-07 "Put it in the DICOM database" wrote 258 instances into a
# database whose server did not have the route that indexes them. Ron: "so save to dicom failed
# silently! That is bad. Do I understand correctly that from now on the server side will get updated
# on every compile?" It does now.
#
# Recompiling takes about a minute, so it happens only when a source file is actually newer than the
# binary. Installing it means REPLACING a bundle in /Applications, which cannot be done under a
# running app -- so that step waits for the app to be closed, and says so plainly when it is not.
BIN="$APP/Contents/MacOS/SlicerAlbula"
BUILT="$SRC/desktop/build/SlicerAlbula.app"
NEWEST_SERVER=""
[ -f "$BIN" ] && NEWEST_SERVER=$(find "$SRC/desktop" -name '*.ts' -not -name '*.test.ts' -newer "$BIN" 2>/dev/null | head -1)
if [ ! -f "$BIN" ]; then
  echo "      (no installed binary to compare the server code against)"
elif [ -n "$NEWEST_SERVER" ]; then
  echo
  echo "      THE APP'S SERVER CODE IS STALE — recompiling it:"
  echo -n "         installed binary:  "; stat -f "%Sm" -t "%b %e %H:%M" "$BIN"
  echo "         newer source:      ${NEWEST_SERVER#"$SRC"/}"
  if "$DENO" run -A "$SRC/desktop/make-app.ts" --thin >/tmp/albula-makeapp.log 2>&1; then
    # An ad-hoc signature that did not take is how the app once shipped as "a.out" (make-app.ts has
    # the story). Checked here rather than trusted, because it failed silently for days.
    IDENT=$(codesign -dv "$BUILT" 2>&1 | sed -n 's/^Identifier=//p')
    if [ "$IDENT" != "org.slicer.SlicerAlbula" ]; then
      echo "      ✘ the rebuilt app is signed as \"$IDENT\", not org.slicer.SlicerAlbula — NOT installing it."
      echo "        see /tmp/albula-makeapp.log"
    elif pgrep -qx SlicerAlbula 2>/dev/null || pgrep -f "/Applications/SlicerAlbula.app" >/dev/null 2>&1; then
      echo "      ⚠  SlicerAlbula IS RUNNING, so the new server code was compiled but NOT installed."
      echo "         Quit it and run this script again; until then the app's server side is the old one."
    else
      rm -rf "$APP" && cp -R "$BUILT" "$APP" && \
        echo "      ✓ recompiled and installed: $APP  (server side now matches the source)"
    fi
  else
    echo "      ✘ recompiling the app failed; see /tmp/albula-makeapp.log"
  fi
else
  echo "      Server code is current with the installed binary."
fi
echo

# ---- colorize ---------------------------------------------------------------
# The colorize page used to be a hand-patched copy of this bundle: the background gradient, the
# pin indicator and the session persistence existed only in the built .js and would have been
# lost by any rebuild. They now live in source (render/background.ts, render/demos/sl-chrome.ts,
# examples/colorize/colorize-browser.ts), so colorize is rebuilt here too and stays reproducible.
WORKSPACE="$SRC/LiveStory/workspace/webgpu"
if [ -d "$WORKSPACE" ]; then
  echo "Bundling examples/colorize/colorize-browser.ts -> $WORKSPACE/colorize.js"
  "$DENO" run -A npm:esbuild examples/colorize/colorize-browser.ts \
    --bundle --format=esm \
    --outfile="$WORKSPACE/colorize.js" || exit 1
  echo "Done. Reload colorize (or run 'Contents/tools/Open SlicerAlbula Colorize.command')."
fi
