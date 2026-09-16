#!/usr/bin/env python3
"""Derive every cut of the Albula logo from Contents/brand/albula-logo.svg.

    python3 Contents/brand/regenerate.py

Run this after replacing the master. It rewrites the three SVG cuts, the two PNG rasters and the two
base64 data URIs in theme.css, and then `render/demos/brand-assets.test.ts` will pass again -- that
test exists precisely to catch a master that was replaced without this being run.

Nothing here is hand-maintained artwork: the master is the only file a designer touches. What the
script does that a crop could not is the SMALL-SIZE CUT. At 18px the wordmark is a grey smear, the
hairpin dividers (3px strokes) erase the road they divide, and the delivered browns are darker than
the toolbar they sit on (#151922). So the emblem is not the master shrunk -- it is the master with
the text dropped, the dividers dropped and the rock lightened one step. Same geometry, so it still
reads as the same mark.

Rasterising needs macOS: qlmanage renders the SVG, sips resizes. There is no SVG rasteriser in the
Deno toolchain and adding one for two PNGs that change once a year is not worth it.
"""
import base64
import pathlib
import re
import subprocess
import sys
import tempfile

BRAND = pathlib.Path(__file__).resolve().parent
DEMOS = BRAND.parent / "src" / "SlicerLive" / "render" / "demos"
DOCS = BRAND.parent / "src" / "SlicerLive" / "docs"
MASTER = BRAND / "albula-logo.svg"


def cuts(src: str) -> tuple[str, str]:
    """(square app-icon svg, small-size emblem svg) from the master."""
    defs = src[src.index("<defs>"):src.index("</defs>") + 7]
    body = src[src.index("<!-- Main Logo Group -->"):src.rindex("</svg>")]
    mtn = src[src.index('<g id="mountain-group">'):src.index("</g>", src.index("<!-- Hairpin"))]
    mtn_full = mtn   # with the hairpin dividers: what the icon keeps, since it is large enough for them

    # THE ROCK, LIGHTENED. The master's browns are the panel browns, and on the plate that makes the
    # mountains vanish into it. Ron, of the Dock: "The icon looks like a darkish square with a
    # bright wriggle ... Can you make the mountains a little brighter?" The same step the emblem
    # takes for the title bar, applied to the icon's mountain group; the master is untouched.
    # Two steps: the emblem's one, tuned for 18 px against the toolbar, and a second for the icon --
    # Ron, shown the first on the Dock: "The mountains in the small one are still too dark."
    STEPS = {
        1: ([("#3A3128", "#5A4C3C"), ("#29221C", "#40352A"), ("#2E261E", "#463A2E"), ("#2A2724", "#332E28")],
            [("darkBrown", "gDark"), ("medBrown", "gMed"), ("goldAccent", "gGold"), ("snowGrad", "gSnow")]),
        2: ([("#3A3128", "#7C6952"), ("#29221C", "#5C4D3D"), ("#2E261E", "#665544"), ("#2A2724", "#3D3630")],
            [("darkBrown", "iDark"), ("medBrown", "iMed"), ("goldAccent", "gGold"), ("snowGrad", "gSnow")]),
    }

    def lighten(g: str, step: int = 1) -> str:
        flats, gradients = STEPS[step]
        for dark, light in flats:
            g = g.replace(dark, light)
        for old, new in gradients:
            g = g.replace(f"url(#{old})", f"url(#{new})")
        return g

    grads = """  <linearGradient id="gDark" x1="0%" y1="0%" x2="100%" y2="100%">
    <stop offset="0%" stop-color="#6B5B49"/><stop offset="100%" stop-color="#463A2E"/>
  </linearGradient>
  <linearGradient id="gMed" x1="0%" y1="0%" x2="0%" y2="100%">
    <stop offset="0%" stop-color="#9A8670"/><stop offset="100%" stop-color="#6B5B49"/>
  </linearGradient>
  <linearGradient id="gGold" x1="0%" y1="0%" x2="100%" y2="100%">
    <stop offset="0%" stop-color="#FFE896"/><stop offset="60%" stop-color="#FBDD70"/>
    <stop offset="100%" stop-color="#E8BE45"/>
  </linearGradient>
  <linearGradient id="gSnow" x1="0%" y1="0%" x2="0%" y2="100%">
    <stop offset="0%" stop-color="#FFFDF9"/><stop offset="100%" stop-color="#EDE7D9"/>
  </linearGradient>
  <linearGradient id="iDark" x1="0%" y1="0%" x2="100%" y2="100%">
    <stop offset="0%" stop-color="#8E7A62"/><stop offset="100%" stop-color="#665544"/>
  </linearGradient>
  <linearGradient id="iMed" x1="0%" y1="0%" x2="0%" y2="100%">
    <stop offset="0%" stop-color="#BFA98C"/><stop offset="100%" stop-color="#8E7A62"/>
  </linearGradient>"""
    # Square plate for the favicon and the .icns. rx is 22% of the side, which is the macOS
    # squircle; iconutil applies no mask of its own, so the artwork has to bring its own corners.
    #
    # THE EMBLEM ALONE, LARGE. Ron, 2026-09-12, having had the rock lightened twice: "Remove the disc
    # rim and the writing." A Dock icon is read at 64 px, where the wordmark is a smear and the rim a
    # hairline; what survives is the disc with the massif and the road. So the icon is the disc and
    # the mountains, no rim, no text, no divider, scaled to fill the plate (disc radius 175 -> 280,
    # 70% of the side) and centred. Ron keeps the shadowless flat disc: the drop shadow is dropped
    # with the rim.
    icon_mtn = lighten(mtn_full + "</g>", 2)   # the slice stops short of the group's own closing tag
    icon = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 800" width="800" height="800">\n'
        f"{defs[:-7]}\n{grads}\n</defs>\n"
        '  <rect width="800" height="800" rx="176" fill="url(#bgGrad)"/>\n'
        '  <g transform="translate(400,400) scale(1.6) translate(-400,-240)">\n'
        '    <circle cx="400" cy="240" r="175" fill="#3D3630"/>\n'
        f"{icon_mtn}\n  </g>\n</svg>\n"
    )

    mtn = lighten(mtn[:mtn.index("<!-- Hairpin Pass Dash Dividers -->")] + "</g>")
    emblem = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="215 55 370 370" width="370" height="370">\n'
        f"<defs>\n{grads}\n"
        '  <clipPath id="disc"><circle cx="400" cy="240" r="171"/></clipPath>\n'
        "</defs>\n"
        '  <circle cx="400" cy="240" r="171" fill="#332E28" stroke="#8A765C" stroke-width="10"/>\n'
        f'  <g clip-path="url(#disc)">\n{mtn}\n  </g>\n</svg>\n'
    )
    return icon, emblem


def rasterise(svg: pathlib.Path, size: int, out: pathlib.Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["qlmanage", "-t", "-s", "1024", "-o", tmp, str(svg)],
                       check=True, capture_output=True)
        big = pathlib.Path(tmp) / f"{svg.name}.png"
        if not big.exists():
            sys.exit(f"qlmanage produced no thumbnail for {svg} — is this macOS?")
        subprocess.run(["sips", "-z", str(size), str(size), str(big), "--out", str(out)],
                       check=True, capture_output=True)


def inline(css_path: pathlib.Path, cls: str, svg: pathlib.Path) -> None:
    """Replace the base64 data URI in one CSS rule. The URIs are inlined so they cannot 404 and
    need no entry in the rebuild script's copy list; the cost is that they go stale in silence."""
    css = css_path.read_text()
    at = css.index(f".{cls} {{")
    b64 = base64.b64encode(svg.read_bytes()).decode()
    head, tail = css[:at], css[at:]
    tail, n = re.subn(r'url\("data:image/svg\+xml;base64,[^"]+"\)',
                      f'url("data:image/svg+xml;base64,{b64}")', tail, count=1)
    if n != 1:
        sys.exit(f"no data URI found in .{cls}")
    css_path.write_text(head + tail)


# Steve's convention for generated brand assets, adopted: viewer/sllogo.js opens with
# "AUTO-GENERATED (do not hand-edit; see Contents/tools/genlogo.py)" and says so IN THE FILE, where the person
# about to edit it is looking -- not only in a README they have no reason to open.
BANNER = ("<!-- AUTO-GENERATED (do not hand-edit; see Contents/brand/regenerate.py):"
          " %s.\n     The master is Contents/brand/albula-logo.svg. -->\n")

src = MASTER.read_text()
icon_svg, emblem_svg = cuts(src)

# inlined into .sl-welcome-logo
(DEMOS / "albula-logo.svg").write_text(BANNER % "verbatim copy of the master" + src)
# source of the PNGs below
(DEMOS / "albula-app-icon.svg").write_text(BANNER % "the lockup on a square plate" + icon_svg)
# inlined into .sl-brand-mark
(DEMOS / "albula-emblem.svg").write_text(BANNER % "small-size cut: no wordmark, no hairpin dividers, rock lightened one step" + emblem_svg)

rasterise(DEMOS / "albula-app-icon.svg", 716, DEMOS / "albula-app-icon.png")  # favicon, manifest
rasterise(DEMOS / "albula-app-icon.svg", 1024, DOCS / "albula-logo.png")      # make-app.ts → .icns

inline(DEMOS / "theme.css", "sl-brand-mark", DEMOS / "albula-emblem.svg")
inline(DEMOS / "theme.css", "sl-welcome-logo", DEMOS / "albula-logo.svg")

print("regenerated. Now run:")
print("  deno test -A --no-check Contents/src/SlicerLive/render/demos/brand-assets.test.ts")
print("  'Contents/tools/Rebuild SlicerAlbula App.command'")
