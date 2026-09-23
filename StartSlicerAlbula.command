#!/bin/bash
# Opens slicer-app -- the full SlicerLive application (Data panel with DICOM loading, Volume
# Rendering, Segment Editor, Volumes, Markups, Transforms, Save) -- in the NATIVE SlicerLive app.
#
# No browser involved. SlicerAlbula.app is itself a local HTTP server plus a webview, so pointing
# --gallery at Contents/src/live makes it serve and display slicer-app directly. (The older
# "Contents/tools/Open SlicerAlbula App.command" used Microsoft Edge only because the DICOM database browser needs
# the File System Access API, which the webview lacks; serving the database over HTTP replaces it.)
#
# WINDOW GEOMETRY. Unlike the colorize launcher, which restores a frame hard-coded into the script,
# this remembers the ACTUAL window: the geometry is read back when the app quits and saved to
# .slicer-app-window, then restored on the next launch. If the saved frame does not fit the current
# screen (laptop display instead of the XDR), it is scaled down proportionally and centred, using
# visibleFrame so the menu bar and Dock are respected.
#
# Every path is relative to THIS script, so the SlicerLive folder can be moved.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
GALLERY="$SCRIPT_DIR/Contents/src/live"
STATE="$SCRIPT_DIR/.slicer-app-window"
DB="$SCRIPT_DIR/Contents/Slicer/SlicerDICOMDatabase"
PORT=4180

if [ ! -f "$GALLERY/webgpu/slicer-app.html" ]; then
  echo "slicer-app.html not found in $GALLERY/webgpu/"
  echo "Rebuild it with:  \"$SCRIPT_DIR/Contents/tools/Rebuild SlicerAlbula App.command\""
  exit 1
fi
if [ ! -x "/Applications/SlicerAlbula.app/Contents/MacOS/SlicerAlbula" ]; then
  echo "SlicerAlbula.app not found in /Applications."
  exit 1
fi

# The DICOM database is reached over HTTP from inside the gallery, so expose it there as a symlink.
# Relative, so it keeps working wherever this folder moves.
if [ -d "$DB" ] && [ ! -e "$GALLERY/dicomdb" ]; then
  ln -sfn "../../Slicer/SlicerDICOMDatabase" "$GALLERY/dicomdb"
fi

/Applications/SlicerAlbula.app/Contents/MacOS/SlicerAlbula \
  --gallery "$GALLERY" \
  --port "$PORT" \
  --url "/webgpu/slicer-app.html?nocache=$(date +%s)" &
APP_PID=$!

# ---- restore the saved geometry (or fit it to this screen) -------------------
SAVED=""
[ -f "$STATE" ] && SAVED="$(cat "$STATE")"

RESULT=$(osascript -l JavaScript - "$SAVED" <<'EOF'
function run(argv) {
  ObjC.import("AppKit");
  var full = $.NSScreen.mainScreen.frame;
  var vis  = $.NSScreen.mainScreen.visibleFrame;
  var mainH = full.size.height;

  // Cocoa screen rects use a bottom-left origin with y up; System Events window positions use a
  // top-left origin with y down. Convert visibleFrame into that space before comparing.
  var usable = {
    x: vis.origin.x,
    y: mainH - (vis.origin.y + vis.size.height),
    w: vis.size.width,
    h: vis.size.height
  };

  var saved = null;
  var parts = (argv[0] || "").split(/\s+/).map(Number);
  if (parts.length === 4 && parts.every(function (n) { return !isNaN(n); })) {
    saved = { x: parts[0], y: parts[1], w: parts[2], h: parts[3] };
  }

  var se = Application("System Events");
  se.includeStandardAdditions = true;

  // Wait for the window to exist, then read its own frame as the fallback target.
  var win = null, lastErr = "";
  for (var i = 0; i < 40 && !win; i++) {
    try { win = se.processes["SlicerAlbula"].windows[0]; win.position(); }
    catch (e) { lastErr = "" + e; win = null; delay(0.25); }
  }
  if (!win) return "FAILED: " + lastErr;

  // Bring it to the front. The app is launched as a CHILD of this shell, so Terminal keeps the
  // activation and the window opens behind it -- Ron: "the terminal window is always on top of
  // Albula". Nothing in the bundle causes that (no LSUIElement, a normal Mach-O), it is simply
  // who launched whom. We are already talking to the process here, so this is the place to fix it.
  try { se.processes["SlicerAlbula"].frontmost = true; } catch (e) { /* positioning still matters */ }

  var target = saved;
  if (!target) return "no-saved-geometry";
  // A FRAME TOO SMALL TO BE THE WINDOW IS NOT RESTORED. On 2026-09-23 the saved frame was 53 x 48
  // pixels -- the last sample had caught something other than the main window -- and it was put
  // back exactly, because it fitted on the screen: Ron's window opened tiny. The app itself already
  // refuses anything under 640 x 480 when it reads this file (desktop/main.ts); this is the same
  // rule on the launcher's side, so the window keeps the size the app gave it.
  if (target.w < 640 || target.h < 480) return "ignored a saved frame of " + target.w + "x" + target.h + " (too small to be the window)";

  var fits = target.x >= usable.x && target.y >= usable.y &&
             target.x + target.w <= usable.x + usable.w &&
             target.y + target.h <= usable.y + usable.h;
  if (!fits) {
    var scale = Math.min(1, usable.w / target.w, usable.h / target.h);
    var w = Math.round(target.w * scale), h = Math.round(target.h * scale);
    target = {
      x: Math.round(usable.x + (usable.w - w) / 2),
      y: Math.round(usable.y + (usable.h - h) / 2),
      w: w, h: h
    };
  }
  // Apply, then KEEP applying until it sticks. The webview sets its own default size shortly after
  // the window appears, so a single set is silently undone a moment later -- the geometry was
  // restored and then replaced by 1440x900 before anyone could see it.
  var applied = "";
  for (var k = 0; k < 10; k++) {
    try {
      win.position = [target.x, target.y];
      win.size = [target.w, target.h];
      applied = "restored " + target.x + "," + target.y + "," + target.w + "," + target.h;
    } catch (e) { return "FAILED: " + e; }
    delay(0.4);
    try {
      var p = win.position(), sz = win.size();
      if (p[0] === target.x && p[1] === target.y && sz[0] === target.w && sz[1] === target.h) {
        return applied + (fits ? "" : " (scaled to fit)") + " after " + (k + 1) + " tries";
      }
    } catch (e) { /* window not ready yet; try again */ }
  }
  return applied + " (did not stick)";
}
EOF
)
echo "Window: $RESULT"
if [[ "$RESULT" == FAILED* ]]; then
  echo ""
  echo "Could not position the window. This is normally an Automation permission:"
  echo "System Settings > Privacy & Security > Automation, find this terminal app, and enable"
  echo "\"System Events\" under it. If it is not listed, quit SlicerLive and run this again."
fi

# ---- remember the geometry, sampled while the app is alive ------------------
# Reading on quit is unreliable: by the time wait returns, the window is already gone. So poll and
# keep the last frame seen; whatever was on screen last is what gets saved.
# Settle before sampling: the webview overrides the size just after launch, and sampling during that
# window recorded the app default and saved it over the user geometry on quit.
sleep 3
LAST=""
while kill -0 "$APP_PID" 2>/dev/null; do
  # THE APPLICATION'S WINDOW, NOT WHATEVER IS FIRST. `windows[0]` is only the frontmost window of
  # the process, and when a panel, a sheet or a minimized window is in that place the sample is that
  # one's frame. That is how 53 x 48 got saved on 2026-09-23 and the next launch opened a window the
  # size of an icon. So: the largest window the process has, and nothing smaller than the app will
  # accept -- a sample that fails either test keeps the last good frame instead of replacing it.
  GEO=$(osascript -l JavaScript <<'EOF' 2>/dev/null
function run() {
  var se = Application("System Events");
  try {
    var ws = se.processes["SlicerAlbula"].windows(), best = null, area = 0;
    for (var i = 0; i < ws.length; i++) {
      try {
        var mini = false;
        try { mini = ws[i].attributes["AXMinimized"].value(); } catch (e) { /* not reported */ }
        if (mini) continue;
        var p = ws[i].position(), s = ws[i].size();
        if (s[0] < 640 || s[1] < 480) continue;
        if (s[0] * s[1] > area) { area = s[0] * s[1]; best = [p[0], p[1], s[0], s[1]]; }
      } catch (e) { /* a window closing under us */ }
    }
    return best ? best.join(" ") : "";
  } catch (e) { return ""; }
}
EOF
)
  [ -n "$GEO" ] && LAST="$GEO"
  sleep 2
done

if [ -n "$LAST" ]; then
  echo "$LAST" > "$STATE"
  echo "Saved window geometry: $LAST"
fi
