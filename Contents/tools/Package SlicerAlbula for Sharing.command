#!/bin/bash
# Build the version of SlicerAlbula you can HAND TO SOMEONE.
#
# Rule 2: "Your tool does not exist, until it works on my laptop with my data." The app in
# /Applications is a THIN app -- it serves Contents/src/live from this folder, so a rebuild is instantly
# live, which is right for working. It is also why the app cannot leave this machine: the folder it
# points at does not exist anywhere else.
#
# This makes the other kind: a self-contained app with the web application copied inside, and a DMG
# with the drag-to-Applications layout people expect. It builds into Contents/src/SlicerLive/desktop/build/
# and DOES NOT touch /Applications, so the app you work with is left exactly as it is.
#
# Three things have to be true before a stranger can double-click it. This script does the first
# always, and the other two when the credentials exist:
#
#   1. SELF-CONTAINED   -- no path into this folder.               (free, always done here)
#   2. SIGNED           -- with a Developer ID, not ad-hoc.        (needs an Apple developer account)
#   3. NOTARIZED        -- checked by Apple, ticket stapled in.    (same account)
#
# Without 2 and 3 the DMG still works, but the recipient meets a macOS refusal first. See
# Contents/docs/RULES-FOR-TOOLS.md, and the notes at the bottom of this file for how to set the account up.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"   # the workspace root: tools/ lives under Contents/
SRC="$ROOT/Contents/src/SlicerLive"
BUILD="$SRC/desktop/build"
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

# WHAT THIS BUILD IS, in the filename. Ron: "The dmg should have date and version and platform in
# the name in addition to SlicerAlbula." A file called SlicerAlbula.dmg on someone's Downloads
# folder in three months answers none of those questions, and the answer matters most exactly then
# -- when they report something and nobody can tell which build they have.
#
# VERSION is Albula's own, in the repository root, and is NOT SlicerLive's version: make-app.ts
# names its DMG after Steve's 0.1.0, which says nothing about this project.
VERSION="$(tr -d '[:space:]' < "$ROOT/VERSION" 2>/dev/null || echo 0.0.0)"
DATE="$(date '+%Y-%m-%d')"
PLATFORM="macos-$(uname -m)"
COMMIT="$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)"
# DATE FIRST. Ron: "put the date at the beginning, so it sorts nicely in finder if I have more than
# one version." Finder sorts by name, so a leading ISO date puts releases in chronological order
# without anyone setting a sort column, and it stays correct when the version numbering changes.
DMG_NAME="$DATE-SlicerAlbula-$VERSION-$PLATFORM"
# WHERE IT LANDS. make-app.ts builds into Steve's desktop/build/, three levels down and next to
# his own DMG -- Ron: "where is the dmg?" Releases go to Contents/run/releases/ instead: the one gitignored
# place output goes, and Finder is opened on it so the question never needs asking.
RELEASES="$ROOT/Contents/run/releases"

# Set these to sign and notarize. SIGN_ID is the full certificate name as `security find-identity`
# prints it. The notary profile is a keychain entry made once with:
#   xcrun notarytool store-credentials albula --apple-id <you> --team-id <TEAM> --password <app-specific>
SIGN_ID="${ALBULA_SIGN_ID:-}"
# The keychain item was created as "gotthard" on 2026-09-12 (the application's name then); the
# rename did not touch the keychain, so the default stays what the keychain has.
NOTARY_PROFILE="${ALBULA_NOTARY_PROFILE:-gotthard}"

# make-app.ts names the DMG after SlicerLive's version and the bare architecture. Rename rather than
# patch Steve's script: the naming is Albula's business, and his tree stays his.
rename_dmg() {
  # Defensive on purpose: under `set -euo pipefail` a glob that matches nothing makes ls fail and
  # takes the whole script with it, which is how the first version of this silently did nothing.
  local made=""
  for f in "$BUILD"/*.dmg; do
    [ -e "$f" ] || continue
    case "$(basename "$f")" in
      SlicerLive-*) continue ;;                       # Steve's, not ours
      "$DMG_NAME.dmg") return 0 ;;                    # already named correctly
    esac
    if [ -z "$made" ] || [ "$f" -nt "$made" ]; then made="$f"; fi
  done
  [ -n "$made" ] || { echo "    (no DMG found to rename)"; return 0; }
  mkdir -p "$RELEASES"
  mv "$made" "$RELEASES/$DMG_NAME.dmg"
  echo "    release: Contents/run/releases/$DMG_NAME.dmg"
  open -R "$RELEASES/$DMG_NAME.dmg" 2>/dev/null || true
  return 0
}

echo "=== 1. Building the self-contained app (this copies ~400 MB and takes a few minutes)"
cd "$SRC"
"$DENO" run -A desktop/make-app.ts            # no --thin: the gallery goes INSIDE the bundle
APP="$BUILD/SlicerAlbula.app"
[ -d "$APP" ] || { echo "make-app.ts did not produce $APP"; exit 1; }

# The thin app's give-away is this file. A self-contained one must not have it.
if [ -f "$APP/Contents/Resources/gallery-path.txt" ]; then
  echo "STOP: the build still carries gallery-path.txt, so it points at this machine."
  exit 1
fi
[ -d "$APP/Contents/Resources/gallery" ] || { echo "STOP: no gallery inside the bundle."; exit 1; }
echo "    self-contained: gallery is inside the bundle, no path out of it"

# If no certificate is configured, stop here and say exactly what is missing rather than shipping
# something that looks finished. make-app.ts has already ad-hoc signed and built a DMG.
if [ -z "$SIGN_ID" ]; then
  cat <<'MSG'

=== 2 and 3 SKIPPED: no Developer ID configured

    The DMG in Contents/src/SlicerLive/desktop/build/ is complete and self-contained, and it will run on
    another Mac -- but macOS will refuse it on first open, and the recipient has to go to
    System Settings > Privacy & Security and click "Open Anyway".

    To remove that step you need an Apple Developer Program membership ($99/year), then:
      1. In Xcode or on developer.apple.com, create a "Developer ID Application" certificate
         and let it install into your login keychain.
      2. Run: security find-identity -v -p codesigning
         Copy the full name in quotes, e.g. Developer ID Application: Ron Kikinis (AB12CD34EF)
      3. Run: xcrun notarytool store-credentials albula \
                 --apple-id <your apple id> --team-id <TEAM> --password <app-specific password>
         An app-specific password is made at appleid.apple.com, not your normal password.
      4. Re-run this script with:
         ALBULA_SIGN_ID="Developer ID Application: ... (TEAM)" "Contents/tools/Package SlicerAlbula for Sharing.command"
MSG
  rename_dmg
  ls -lh "$RELEASES/$DMG_NAME.dmg" 2>/dev/null | sed 's/^/    /'
  exit 0
fi

echo "=== 2. Signing with $SIGN_ID"
# SIGN A COPY IN /tmp. When this workspace lived on the Desktop (until 2026-09-16), iCloud's File
# Provider tagged every file (com.apple.fileprovider.fpfs#P, com.apple.provenance, com.apple.macl)
# faster than xattr could clear them -- codesign then refused the bundle: "resource fork, Finder
# information, or similar detritus not allowed". The first signed build failed exactly there.
# The workspace is out of iCloud's reach now; the copy is kept because it costs nothing and
# a clone on someone else's synced Desktop would hit the same wall.
STAGE="$(mktemp -d /tmp/albula-sign.XXXXXX)"
ditto "$APP" "$STAGE/SlicerAlbula.app"
APP="$STAGE/SlicerAlbula.app"
# The launcher links Contents/src/live/dicomdb to THIS MACHINE'S DICOM database so the app can reach it over
# HTTP, and rsync copies that link into the bundle, where it dangles. It is a path into Ron's Mac
# and must not ship; it also makes xattr fail on the broken link and stop the script under set -e.
find "$APP/Contents/Resources/gallery" -type l -name dicomdb -delete
# xattr first: codesign refuses a bundle carrying extended attributes, and macOS adds
# com.apple.provenance on copy. This is what once let the app ship signed only as "a.out".
xattr -cr "$APP"
# com.apple.provenance is SIP-protected -- xattr cannot remove it -- and codesign tolerates it. What
# codesign refuses is Finder info, resource forks and the File Provider tags, so check for those.
LEFT="$(xattr -lr "$APP" 2>/dev/null | grep -v "com.apple.provenance" || true)"
[ -z "$LEFT" ] || { echo "STOP: attributes codesign will refuse survive even in $STAGE:"; echo "$LEFT" | head -5; exit 1; }
# --options runtime is the hardened runtime, and notarization REFUSES a bundle without it.
# --timestamp is likewise required. Inner binaries first, then the bundle.
find "$APP/Contents/Resources/lib" -name '*.dylib' -print0 2>/dev/null \
  | xargs -0 -r codesign --force --timestamp --options runtime -s "$SIGN_ID"
codesign --force --deep --timestamp --options runtime -s "$SIGN_ID" "$APP"
codesign --verify --strict --verbose=2 "$APP"
echo "    signed"

echo "=== 3. Rebuilding the DMG around the signed app, then notarizing"
mkdir -p "$RELEASES"; DMG="$RELEASES/$DMG_NAME.dmg"
STAGE="$BUILD/dmg-staging-signed"
rm -rf "$STAGE" "$DMG"; mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
cat > "$STAGE/README.txt" <<TXT
SlicerAlbula $VERSION — built $DATE — $PLATFORM
commit $COMMIT

Drag SlicerAlbula to Applications, then open it. That is all.

This software is not intended for clinical use.
Slicer is NOT an FDA approved medical device.

Needs macOS 26 or newer, and a Mac with plenty of memory: a whole-body CT with a
111-structure segmentation has peaked at 11.7 GB. 16 GB is not enough for that case.

For AI segmentation you also need haversack running; see the project README.
TXT
hdiutil create -volname SlicerAlbula -srcfolder "$STAGE" -ov -format UDZO "$DMG" >/dev/null
rm -rf "$STAGE"

# Notarize the DMG rather than the app: it is what the recipient downloads, and stapling the ticket
# into the DMG means the check passes with no network on their side.
#
# SUBMIT, THEN WAIT SEPARATELY, AND SURVIVE A NETWORK DROP. `submit --wait` died two hours into
# the first submission when the connection blinked -- "The Internet connection appears to be
# offline" -- and took the stapling step with it, while Apple still had the file. The submission id
# is what matters; polling it can fail and retry as often as it likes.
SUBMIT="$(xcrun notarytool submit "$DMG" --keychain-profile "$NOTARY_PROFILE" 2>&1 | tee /dev/stderr)"
ID="$(printf '%s' "$SUBMIT" | sed -n 's/^ *id: //p' | head -1)"
[ -n "$ID" ] || { echo "STOP: no submission id from notarytool"; exit 1; }
echo "    submission $ID -- waiting for Apple (minutes usually; hours on a first submission)"
STATUS=""
for i in $(seq 1 480); do                                   # up to 8 hours, one look a minute
  STATUS="$(xcrun notarytool info "$ID" --keychain-profile "$NOTARY_PROFILE" 2>/dev/null | sed -n 's/.*status: //p' | head -1)"
  case "$STATUS" in
    "In Progress"|"") sleep 60 ;;                            # empty = a network blink; ask again
    *) break ;;
  esac
done
if [ "$STATUS" != "Accepted" ]; then
  echo "STOP: Apple answered '$STATUS'. Its log:"
  xcrun notarytool log "$ID" --keychain-profile "$NOTARY_PROFILE" 2>&1 | head -40
  exit 1
fi
xcrun stapler staple "$DMG"
rm -rf "$STAGE"

echo
echo "=== Done. Verifying the way macOS will:"
spctl -a -vv -t install "$DMG" || true
ls -lh "$DMG"; open -R "$DMG" 2>/dev/null || true
echo
echo "    This DMG can be sent to anyone. It opens by double-clicking, with no warning."
echo "    $DMG_NAME.dmg — version, date and platform are in the name on purpose."
