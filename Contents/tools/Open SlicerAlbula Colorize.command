#!/bin/bash
# Opens the colorized CT + segmentation scene in the SlicerLive desktop app.
# Every path is resolved relative to THIS script, so the whole SlicerLive folder
# can be moved or renamed without editing anything.
# THE REPO ROOT, which is now our PARENT: these three moved into Contents/tools/ so the folder Ron opens
# holds only the launcher he uses. Everything below is still relative to the root.
SCRIPT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"   # the workspace root: Contents/tools/ lives under Contents/
GALLERY="$SCRIPT_DIR/Contents/src/SlicerLive/LiveStory/workspace"

if [ ! -d "$GALLERY" ]; then
  echo "Gallery workspace not found at: $GALLERY"
  exit 1
fi

TS=$(date +%s)
/Applications/SlicerAlbula.app/Contents/MacOS/SlicerAlbula \
  --gallery "$GALLERY" \
  --url "/webgpu/colorize.html?data=/colorize/&nocache=$TS" &
APP_PID=$!

# Wait for the window, then place it: use the remembered portrait position/size
# if it fits the current screen, otherwise scale it down proportionally and
# centre it (menu-bar and Dock aware, whichever edge the Dock is on).
RESULT=$(osascript -l JavaScript <<'EOF'
function run() {
  ObjC.import("AppKit");
  var full = $.NSScreen.mainScreen.frame;
  var vis = $.NSScreen.mainScreen.visibleFrame;
  var mainH = full.size.height;

  // Cocoa screens use a bottom-left origin with y increasing upward; System Events
  // window positions use a top-left origin (of the main screen) with y increasing
  // downward. Convert visibleFrame into that coordinate space.
  var usable = {
    x: vis.origin.x,
    y: mainH - (vis.origin.y + vis.size.height),
    w: vis.size.width,
    h: vis.size.height
  };

  var PREF = { x: 1762, y: 33, w: 1149, h: 1577 };
  var fits = PREF.x >= usable.x && PREF.y >= usable.y &&
             PREF.x + PREF.w <= usable.x + usable.w &&
             PREF.y + PREF.h <= usable.y + usable.h;

  var target;
  if (fits) {
    target = PREF;
  } else {
    var scale = Math.min(1, usable.w / PREF.w, usable.h / PREF.h);
    var w = Math.round(PREF.w * scale), h = Math.round(PREF.h * scale);
    target = {
      x: Math.round(usable.x + (usable.w - w) / 2),
      y: Math.round(usable.y + (usable.h - h) / 2),
      w: w, h: h
    };
  }

  var se = Application("System Events");
  se.includeStandardAdditions = true;
  var lastErr = "";
  for (var i = 0; i < 40; i++) {
    try {
      var win = se.processes["SlicerAlbula"].windows[0];
      win.position = [target.x, target.y];
      win.size = [target.w, target.h];
      return "ok " + target.x + "," + target.y + "," + target.w + "," + target.h;
    } catch (e) {
      lastErr = "" + e;
      delay(0.25);
    }
  }
  return "FAILED: " + lastErr;
}
EOF
)

echo "Window placement: $RESULT"
if [[ "$RESULT" == FAILED* ]]; then
  echo ""
  echo "Could not resize/reposition the SlicerLive window automatically, so it opened"
  echo "at its native default size, which may be larger than this screen."
  echo ""
  echo "This is almost always a permissions issue. Open System Settings > Privacy &"
  echo "Security > Automation, find this terminal app in the list, and make sure"
  echo "\"System Events\" is checked under it. If it's not listed at all yet, quit"
  echo "SlicerLive and run this script again -- macOS should prompt you to allow it."
  echo ""
  osascript -e 'display alert "SlicerLive window sizing failed" message "Could not resize/reposition the SlicerLive window (it opened at its native default size, which may be larger than the screen).\n\nOpen System Settings > Privacy & Security > Automation, find this terminal app, and enable \"System Events\" under it. If it is not listed yet, quit SlicerLive and run this launcher again -- macOS should prompt you to allow it." as warning' >/dev/null 2>&1
fi

wait "$APP_PID"
