#!/bin/bash
# Rebuilds slicer-app.js from the TypeScript source into the gallery, after editing
# anything under Contents/src/SlicerLive. Paths are relative to THIS script.
# THE REPO ROOT, which is now our PARENT: these three moved into Contents/tools/ so the folder Ron opens
# holds only the launcher he uses. Everything below is still relative to the root.
SCRIPT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"   # the workspace root: Contents/tools/ lives under Contents/
SRC="$SCRIPT_DIR/Contents/src/SlicerLive"
GALLERY="$SCRIPT_DIR/Contents/src/live"
DENO="$(command -v deno || echo /opt/homebrew/bin/deno)"
# DENO'S VERSION, PINNED IN ONE PLACE (Contents/src/SlicerLive/DENO_VERSION; 2026-10-13, the cross-platform plan): the
# application IS this Deno -- its server compiled with it, its SQLite the one inside it (node:sqlite) -- so a build with
# another version is another application. Moving Deno: change that file, run the tests, rebuild.
DENO_WANTED="$(tr -d '[:space:]' < "$(cd "$(dirname "${BASH_SOURCE[0]}")/../src/SlicerLive" && pwd)/DENO_VERSION")"
if [ ! -x "$DENO" ]; then
  echo "deno not found. Install with:  brew install deno"
  exit 1
fi
DENO_HAVE="$("$DENO" --version 2>/dev/null | head -1 | awk '{print $2}')"
if [ "$DENO_HAVE" != "$DENO_WANTED" ]; then
  # Homebrew's Deno has no "deno upgrade" and keeps only its newest version (critic, 2026-10-13, finding 2).
  echo "This build needs Deno $DENO_WANTED (Contents/src/SlicerLive/DENO_VERSION); this Mac has $DENO_HAVE."
  echo "To move to $DENO_HAVE: put $DENO_HAVE in that file and run this again; every test runs before anything is built."
  echo "To keep Homebrew from moving Deno:  brew pin deno"
  exit 1
fi
# THE BUNDLER'S VERSION is in Contents/src/SlicerLive/deno.jsonc with every other JavaScript package's (Ron,
# 2026-09-25: every dependency's version in one place). Every step below runs in $SRC, so Deno finds it.
ESBUILD="npm:esbuild"

cd "$SRC" || exit 1

# THE TESTS RUN FIRST. Ron, 2026-09-17: "please add tests when you are compiling." 131 test
# files, about 45 s; a failure stops the build here with the failing tests named, so a broken
# bundle is never what the app serves. --no-check is the known state of this tree (type-checking
# fails on hundreds of Uint8Array<ArrayBufferLike> errors and runs nothing); "ALL PASS" in the
# records has always meant this run. Skip with:  ALBULA_SKIP_TESTS=1 "<this script>"
# when iterating on one thing with the tests known green -- and say so in the record.
# THE DUCKN COPY'S CODE, from the converter's sources, before the tests (one of which checks it) and
# before the server is compiled with it. A copy made by other code is not used (desktop/make-copy-code.ts).
# No pipe into sed here: a pipeline's status is the LAST command's, so `| sed ... || exit 1` could never
# stop the build when the fingerprint failed (critic, 2026-09-23, round 2, finding 6).
CC_OUT=$("$DENO" run -A desktop/make-copy-code.ts 2>&1) || { echo "$CC_OUT"; echo "The duckn copy code could not be computed -- not building."; exit 1; }
# Each extension's DICOM interpreter carries its own fingerprint, recorded in the copies it reads (Contents/tools/extensions.ts).
EXT_FP=$("$DENO" run -A "$SCRIPT_DIR/Contents/tools/extensions.ts" fingerprint 2>&1) || { echo "$EXT_FP"; echo "An extension's interpreter fingerprint could not be computed -- not building."; exit 1; }
echo "$EXT_FP"
echo "      $CC_OUT"

# TWO TIERS (Ron, 2026-09-29: "yes ... the fast/full test split"). A test file whose header says `// @full-tier` reads a
# large data collection (the DICOM corpus, the 27 diffusion scanner sets) and runs only in the FULL tier; every other
# test runs every build (the FAST tier). The full tier runs when: ALBULA_FULL_TESTS=1; no full pass is recorded; the
# last full pass is more than 7 days old; or anything changed since it in the code those tests guard -- the DICOM and
# NIfTI/NRRD readers, the codecs, the DICOM library, the vendored packages, diffusion, or a dependency's version.
# A passing full run touches Contents/run/last-full-tests; a failing one does not.
FULL_STAMP="$SCRIPT_DIR/Contents/run/last-full-tests"
FULL_WHY=""
if [ "${ALBULA_FULL_TESTS:-0}" = "1" ]; then FULL_WHY="asked for (ALBULA_FULL_TESTS=1)"
elif [ ! -f "$FULL_STAMP" ]; then FULL_WHY="no full run recorded"
elif [ -n "$(find "$FULL_STAMP" -mtime +7)" ]; then FULL_WHY="the last full run is more than 7 days old"
else
  CHANGED=$(find logic/readers logic/codecs logic/dicom-io.ts logic/dcmjs.ts render/vendor render/nrrd.ts sdk "$SCRIPT_DIR/Contents/extensions" deno.jsonc deno.lock -type f -newer "$FULL_STAMP" -not -path '*/.git/*' 2>/dev/null | head -1)
  [ -n "$CHANGED" ] && FULL_WHY="changed since the last full run: ${CHANGED#./}"
fi
if [ -n "$FULL_WHY" ]; then TIER="full"; IGNORE_ARG=""
else TIER="fast"; IGNORE_ARG="--ignore=$(grep -l '@full-tier' $(git ls-files '*.test.ts') 2>/dev/null | paste -sd, -)"; fi

# THE EXTENSIONS ARE AT THEIR PINNED COMMITS (or ALBULA_UNPINNED=1), tests or not.
echo "Extensions:"
"$DENO" run -A "$SCRIPT_DIR/Contents/tools/extensions.ts" check || exit 1

if [ "${ALBULA_SKIP_TESTS:-0}" != "1" ]; then
  echo "Tests first, $TIER tier${FULL_WHY:+ ($FULL_WHY)} (deno test -A --no-check --unstable-ffi in $SRC)…"
  T0=$(date +%s)
  TEST_OUT="$(mktemp -t albula-tests)"
  if "$DENO" test -A --no-check --unstable-ffi $IGNORE_ARG > "$TEST_OUT" 2>&1; then
    echo "      tests ($TIER): $(sed 's/\x1b\[[0-9;]*m//g' "$TEST_OUT" | grep -aE '^ok \| [0-9]+ passed' | tail -1 | sed 's/^ok | //')  ($(( $(date +%s) - T0 )) s)"
  else
    echo
    echo "TESTS FAILED — nothing was built. The failures:"
    sed 's/\x1b\[[0-9;]*m//g' "$TEST_OUT" | grep -aE "\.\.\. FAILED|^FAILED \|" | head -30
    echo "  full output: $TEST_OUT"
    exit 1
  fi
  rm -f "$TEST_OUT"
  # THE EXTENSIONS' TESTS (Contents/extensions/extensions.json; each extension's own, with its manifest's flags and
  # core's config for the SDK names; the same tier as core's). A full pass is recorded only when they pass too.
  echo "Extensions' tests…"
  if ! ALBULA_TIER="$TIER" "$DENO" run -A "$SCRIPT_DIR/Contents/tools/extensions.ts" test; then
    echo "EXTENSION TESTS FAILED — nothing was built."
    exit 1
  fi
  [ "$TIER" = "full" ] && mkdir -p "$(dirname "$FULL_STAMP")" && touch "$FULL_STAMP"
  # THE ENGINE CHECK (algorithms/surface-nets.engine-bench.ts): the same surface extraction in JavaScriptCore, the
  # engine the app's window runs, and in V8, which the tests run. The Greased Lightning fix (118 s -> 15 s) is
  # invisible in V8, so no ordinary test can catch a change that quietly costs the shipping engine a factor of seven
  # (it was 6.9x). Fails the build when phases 1-2 are more than 3x slower in JavaScriptCore, or the engines disagree
  # on the triangles. Critic, qa/2026-09-28-dependencies.md, finding 11: the rebuild never ran it.
  JSC=/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc
  if [ -x "$JSC" ]; then
    EB="$(mktemp -d -t albula-engine)"
    "$DENO" run -A "$ESBUILD" algorithms/surface-nets.engine-bench.ts --bundle --format=iife --target=es2020 --outfile="$EB/eb.js" --log-level=warning || exit 1
    printf 'globalThis.print=console.log;\n' | cat - "$EB/eb.js" > "$EB/eb-v8.js"
    J_OUT=$("$JSC" "$EB/eb.js" 2>&1); V_OUT=$("$DENO" run -A "$EB/eb-v8.js" 2>&1)
    rm -rf "$EB"
    if ! ENGINE=$(python3 "$SCRIPT_DIR/Contents/tools/engine-check.py" "$J_OUT" "$V_OUT"); then
      echo; echo "ENGINE CHECK FAILED — nothing was built. $ENGINE"; echo "  JavaScriptCore: $J_OUT"; echo "  V8: $V_OUT"; exit 1
    fi
    echo "      engine: $ENGINE"
  else
    echo "      engine: SKIPPED (no JavaScriptCore at $JSC)"
  fi
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

# THE ENTRY IS GENERATED from Contents/extensions/extensions.json (Contents/tools/extensions.ts): each extension's hooks
# and module, then core's app (render/demos/slicer-app.ts). Core never imports an extension; the list is where one is
# added or removed. "albula" -- the SDK, the one name an extension imports from core -- is mapped here as in deno.jsonc.
EXT_STAMP="$("$DENO" run -A "$SCRIPT_DIR/Contents/tools/extensions.ts" stamp)"
[ -n "$EXT_STAMP" ] && BUILD_ID="$BUILD_ID · $EXT_STAMP"
ENTRY="$SCRIPT_DIR/Contents/run/build/albula-app.generated.ts"
"$DENO" run -A "$SCRIPT_DIR/Contents/tools/extensions.ts" entry "$ENTRY" || exit 1
echo "Bundling the app (core + extensions) -> $GALLERY/webgpu/slicer-app.js  (build $BUILD_ID)"
"$DENO" run -A "$ESBUILD" "$ENTRY" \
  --bundle --format=esm --alias:albula=./sdk/albula.ts \
  "--define:__BUILD_ID__=\"$BUILD_ID\"" \
  --outfile="$GALLERY/webgpu/slicer-app.js" || exit 1

# The ingest worker is a SECOND entry point, bundled beside the page bundle. volumeToZarr looks for
# ./ingest-worker.js relative to the document, so it must land in the same directory as the page.
# The surface-extraction worker, same arrangement and for the same reason: it is looked up relative
# to the document, so it has to land beside the page bundle.
echo "Bundling algorithms/surface-nets-worker.ts -> $GALLERY/webgpu/surface-nets-worker.js"
"$DENO" run -A "$ESBUILD" algorithms/surface-nets-worker.ts \
  --bundle --format=esm \
  "--define:__BUILD_ID__=\"$BUILD_ID\"" \
  --outfile="$GALLERY/webgpu/surface-nets-worker.js" || exit 1

echo "Bundling algorithms/decimate-worker.ts -> $GALLERY/webgpu/decimate-worker.js"
"$DENO" run -A "$ESBUILD" algorithms/decimate-worker.ts \
  --bundle --format=esm \
  "--define:__BUILD_ID__=\"$BUILD_ID\"" \
  --outfile="$GALLERY/webgpu/decimate-worker.js" || exit 1

# The codec worker, and the vendored WebAssembly codecs it fetches from ./vendor/codecs/ beside it
# (render/vendor/codecs/README.md: what they are, their versions and licenses).
echo "Bundling algorithms/codec-worker.ts -> $GALLERY/webgpu/codec-worker.js"
"$DENO" run -A "$ESBUILD" algorithms/codec-worker.ts \
  --bundle --format=esm \
  "--define:__BUILD_ID__=\"$BUILD_ID\"" \
  --outfile="$GALLERY/webgpu/codec-worker.js" || exit 1
mkdir -p "$GALLERY/webgpu/vendor/codecs"
cp "$SRC"/render/vendor/codecs/*.js "$SRC"/render/vendor/codecs/*.wasm "$SRC"/render/vendor/codecs/LICENSE-* "$GALLERY/webgpu/vendor/codecs/"
# dcmjs, vendored since 2026-09-28 (it came from jsdelivr/unpkg at run time: no network, no DICOM; critic,
# qa/2026-09-28-dependencies.md, finding 1). The page and the workers load it from ./vendor/ beside the bundle.
# EACH EXTENSION'S FILES (its manifest's "assets": dcm2niix's WebAssembly, TractCloud's network, ...) to vendor/<group>/.
"$DENO" run -A "$SCRIPT_DIR/Contents/tools/extensions.ts" assets "$GALLERY/webgpu" || exit 1
# (sql.js went on 2026-10-14: the server reads the index and the page asks it, desktop/db-listing.ts.)
mkdir -p "$GALLERY/webgpu/vendor/dcmjs"
cp "$SRC"/render/vendor/dcmjs/dcmjs.js "$SRC"/render/vendor/dcmjs/License.txt "$GALLERY/webgpu/vendor/dcmjs/"
rm -rf "$GALLERY/webgpu/vendor/sqljs"   # an older build's copy, so the app ships none

# The segmentation decoder: the largest single-threaded phase of a load until 2026-09-22.
echo "Bundling algorithms/seg-decode-worker.ts -> $GALLERY/webgpu/seg-decode-worker.js"
"$DENO" run -A "$ESBUILD" algorithms/seg-decode-worker.ts \
  --bundle --format=esm \
  "--define:__BUILD_ID__=\"$BUILD_ID\"" \
  --outfile="$GALLERY/webgpu/seg-decode-worker.js" || exit 1

# Unpacking a compressed labelmap off the page's thread (render/zarr.ts, assembleInWorker). Without
# this file the page falls back to unpacking on its own thread and says so in the console.
echo "Bundling render/zarr-assemble-worker.ts -> $GALLERY/webgpu/zarr-assemble-worker.js"
"$DENO" run -A "$ESBUILD" render/zarr-assemble-worker.ts \
  --bundle --format=esm \
  "--define:__BUILD_ID__=\"$BUILD_ID\"" \
  --outfile="$GALLERY/webgpu/zarr-assemble-worker.js" || exit 1

# Fetching and unpacking the pieces of a series' duckn working copy (render/zarr-copy.ts). Without
# this file a load from a copy fails and falls back to the DICOM files, and the status line says so.
echo "Bundling render/zarr-copy-worker.ts -> $GALLERY/webgpu/zarr-copy-worker.js"
"$DENO" run -A "$ESBUILD" render/zarr-copy-worker.ts \
  --bundle --format=esm \
  "--define:__BUILD_ID__=\"$BUILD_ID\"" \
  --outfile="$GALLERY/webgpu/zarr-copy-worker.js" || exit 1

echo "Bundling logic/ingest-worker.ts -> $GALLERY/webgpu/ingest-worker.js"
"$DENO" run -A "$ESBUILD" logic/ingest-worker.ts \
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
# EVERY FILE THE SERVER IS COMPILED FROM, not only desktop/: it also uses logic/mesh-cache.ts,
# logic/scene/*.ts, logic/settings.ts, algorithms/surface-nets.ts and render/mat4.ts, and a change to any of
# them never reached the installed app (code review 2026-09-24, A2). Deno lists the graph from the two entry
# points make-app.ts compiles; desktop/ is still searched in case that listing fails.
SERVER_FILES=$( { "$DENO" info --json "$SRC/desktop/main.ts" 2>/dev/null; echo; "$DENO" info --json "$SRC/desktop/server-worker.ts" 2>/dev/null; } \
  | python3 -c 'import json,sys
for chunk in sys.stdin.read().split("\n{"):
    chunk = chunk.strip()
    if not chunk: continue
    if not chunk.startswith("{"): chunk = "{" + chunk
    try: d = json.loads(chunk)
    except Exception: continue
    for m in d.get("modules", []):
        # "local" is the plain path; the specifier is a URL ("a b" is "a%20b" there) (critic, finding 11).
        if m.get("specifier", "").startswith("file://") and m.get("local"): print(m["local"])' 2>/dev/null | sort -u)
[ -f "$BIN" ] && NEWEST_SERVER=$( { echo "$SERVER_FILES"; find "$SRC/desktop" -name '*.ts' -not -name '*.test.ts'; } | while read -r f; do [ -n "$f" ] && [ "$f" -nt "$BIN" ] && { echo "$f"; break; }; done)
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
  "$DENO" run -A "$ESBUILD" examples/colorize/colorize-browser.ts \
    --bundle --format=esm \
    --outfile="$WORKSPACE/colorize.js" || exit 1
  echo "Done. Reload colorize (or run 'Contents/tools/Open SlicerAlbula Colorize.command')."
fi
