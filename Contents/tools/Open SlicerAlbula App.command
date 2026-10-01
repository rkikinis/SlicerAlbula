#!/bin/bash
# Serves the gallery and opens slicer-app -- the standalone SlicerLive application
# (Data panel with DICOM loading incl. the DICOM database browser, Segment Editor,
# Volumes, Markups, Transforms, Save). No 3D Slicer involved.
#
# Opened in Microsoft Edge rather than Chrome: Edge is Chromium (so it has the
# File System Access APIs that WKWebView/Safari lacks, which the DICOM folder and
# database browsing need), and it avoids landing the window on whichever Space
# Chrome is assigned to.
#
# All paths are relative to THIS script, so the SlicerLive folder can be moved.
# THE REPO ROOT, which is now our PARENT: these three moved into Contents/tools/ so the folder Ron opens
# holds only the launcher he uses. Everything below is still relative to the root.
SCRIPT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"   # the workspace root: Contents/tools/ lives under Contents/
GALLERY="$SCRIPT_DIR/Contents/src/live"
PORT=4200
DENO="$(command -v deno || echo /opt/homebrew/bin/deno)"

if [ ! -f "$GALLERY/webgpu/slicer-app.html" ]; then
  echo "slicer-app.html not found in $GALLERY/webgpu/"
  echo "Rebuild it with:  $SCRIPT_DIR/Contents/tools/Rebuild SlicerAlbula App.command"
  exit 1
fi
if [ ! -x "$DENO" ]; then
  echo "deno not found (brew install deno) -- needed to serve the gallery."
  exit 1
fi

# Reuse a server if one is already listening on this port.
if curl -s -m 2 -o /dev/null "http://127.0.0.1:$PORT/webgpu/slicer-app.html"; then
  echo "Server already running on $PORT."
else
  echo "Serving $GALLERY on http://127.0.0.1:$PORT"
  # The file server's version comes from SlicerLive's deno.jsonc, where every JavaScript package's is (critic,
  # qa/2026-09-28-dependencies.md, finding 12: this asked for jsr:@std/http with no version at all).
  "$DENO" run -A --quiet --config "$SCRIPT_DIR/Contents/src/SlicerLive/deno.jsonc" jsr:@std/http@1/file-server --port "$PORT" --host 127.0.0.1 "$GALLERY" &
  SERVER_PID=$!
  for i in $(seq 1 40); do
    curl -s -m 2 -o /dev/null "http://127.0.0.1:$PORT/webgpu/slicer-app.html" && break
    sleep 0.25
  done
fi

open -na "Microsoft Edge" --args --app="http://127.0.0.1:$PORT/webgpu/slicer-app.html?nocache=$(date +%s)"
echo "Opened slicer-app. Close this window to stop the server."

if [ -n "$SERVER_PID" ]; then wait "$SERVER_PID"; fi
