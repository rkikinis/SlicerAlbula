# The Albula logo

`albula-logo.svg` is **the master**. Everything else in the application is derived from it by
`regenerate.py`. To change the logo, replace that one file and run:

```bash
python3 Contents/brand/regenerate.py
```

then rebuild (`Contents/tools/Rebuild SlicerAlbula App.command`). Nothing else is hand-edited.

Made by Ron Kikinis, 2026-09-09, with Gemini.

The gold line switchbacking up the massif is the pass road, and it is the point of the mark rather
than decoration on it — it is also the only feature that still reads at 18px. The name's origin
story is in the main `README.md` under "The name": the summit never prevented a road, the gorge
below Bergün did, and every generation since has cut or tunneled through the hard part.

## The 3D view's background is part of this too

Ron, 2026-09-10, asked whether the 3D view should stay light or match the dark chrome: **"keep the
current light blue its part of the branding."**

So the pale blue-lavender gradient behind the surfaces — against dark panels everywhere else — is
deliberate. **Do not "fix" it to match the chrome.** The constants are `render/background.ts` and the
values are pinned by `render/test/slicer-bg.gpu.test.ts`.

It is also 3D Slicer's own gradient, read out of an installed Slicer 5.13 rather than copied from
documentation, with the stop order checked empirically and the sRGB mixing verified to within 1/255
(`e119625`). Parity and branding happen to agree here, which is why it survived long enough to
become the second.

## Where it ends up

| where you see it | size | which cut |
|---|---|---|
| application title bar, left of the name | 18px | emblem alone — mountain and pass, no wordmark |
| Welcome panel, under the disclaimer | 230px | the full lockup |
| browser tab, PWA manifest | 716px | the disc and the massif alone on a square plate, no rim, no wordmark, 1.6× |
| the macOS app icon in the Dock and Finder | up to 1024px | the same square plate, via `.icns` |

The derived files, all written by the script and none of them worth editing by hand:

```
Contents/src/SlicerLive/render/demos/albula-logo.svg        copy of the master; inlined into .sl-welcome-logo
Contents/src/SlicerLive/render/demos/albula-emblem.svg      small-size cut;     inlined into .sl-brand-mark
Contents/src/SlicerLive/render/demos/albula-app-icon.svg    square plate: disc + massif, rock two steps lighter
Contents/src/SlicerLive/render/demos/albula-app-icon.png    716px — favicon and manifest
Contents/src/SlicerLive/docs/albula-logo.png                1024px — desktop/make-app.ts builds the .icns
```

## Why the app icon is a different drawing too

Ron, 2026-09-12, looking at the Dock: *"The icon looks like a darkish square with a bright
wriggle."* Then, after two lightenings: *"Remove the disc rim and the writing."* At 64px the
wordmark is a smear and the rim a hairline; what survives is the disc with the massif and the road.
So the icon is that alone, scaled to fill the plate, with the rock two steps lighter than the
master (the emblem takes one step). Ron: *"the one on the right works."*

## Why the small one is a different drawing

It is a cut, not a crop. At 18px the master does not survive: the wordmark becomes a gray smear, the
hairpin dividers are 3px strokes across a road only a few pixels wide and erase the one feature that
carries the mark, and the delivered browns are darker than the toolbar they have to sit on
(`#151922`). So the emblem drops the text and the dividers and lightens the rock one step. The
geometry is untouched, so it still reads as the same mark.

## Two things that go stale in silence

Both are covered by `Contents/src/SlicerLive/render/demos/brand-assets.test.ts`, so neither has to be
remembered:

- The title-bar and Welcome logos are **inlined into `theme.css` as base64 data URIs**. That is
  deliberate — a data URI cannot 404 and needs no entry in the rebuild script's copy list — but edit
  an SVG without rerunning the script and the app serves the old artwork with nothing on screen to
  say so.
- `albula-app-icon.png` is fetched by name, so it has to be in the rebuild script's copy list or
  the served gallery keeps yesterday's icon.

## What this logo is

Artwork, Apache-2.0 with the rest of the project. **No trademark is claimed.** So there is no usage
policy, no "do not alter the shape or text", no permission to ask for — copy it, change it, put it
on a poster.

It replaced the official `3D-Slicer-Mark.svg`, which was in the title bar while the application had
no mark of its own. That is the last thing here that raised a trademark question, and it is gone.
The one remaining question — the application's *name* — is answered in the main `README.md`, not
repeated here or in the application, which mentions no trademarks at all. Ron: "why referring to the
trademark at all if we are not using it?"
