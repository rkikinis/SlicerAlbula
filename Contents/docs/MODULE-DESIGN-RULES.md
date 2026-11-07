# Albula Module Design Rules

The rules every module in Albula is built and reviewed against: what goes where on the screen, how controls behave, how
things are worded, and the principles behind them. Each rule says why it exists. A checklist for reviews is at the end.

**What Albula is.** Albula is Ron Kikinis's sandbox for improving the user experience of medical image software: a
desktop application, one double-clickable program like 3D Slicer, built on Steve Pieper's SlicerLive. A **module** is
one panel in the left column (Segmentations, Scenes, Diffusion, …), chosen from the module menu.

**Who it is for.** A clinician who needs an answer and knows neither the jargon nor the concepts (our test case: a
neurosurgery resident preparing a case), and a researcher who wants numbers they can trust. Both use the same module.
Neither reads instructions.

**How the rules are used.** Every mockup is checked against this page before it is shown, and says which rules it does
not meet and why. The adversarial reviewer checks every module against it, item by item.

## The foundation: Ron's Rules for Tools

Written for interactive tools in translational clinical research ([RULES-FOR-TOOLS.md](RULES-FOR-TOOLS.md); Kikinis R.,
"Ron's Rules for Tools", 2014, [doi:10.5281/zenodo.22707222](https://doi.org/10.5281/zenodo.22707222)). Every other
rule on this page serves one of these five.

1. **You make it, I break it.** A tool works with workflows its builder never imagined: a case without a tumor, two
   patients loaded at once, a missing scan, a button pressed twice, a window reloaded halfway through.
2. **Your tool does not exist until it works on my laptop with my data.** Until then it is a rumor. Every change is
   tried in the user's own window, on their build.
3. **I am lazy: I do not like to move the mouse or to type.** Few clicks, short pointer travel, good defaults that can
   be overridden. Nothing to press where nothing has to be computed.
4. **No more than one simple parameter.** If setting it takes more than 20 seconds of thought, it will not be set.
   Everything else goes under Advanced.
5. **Make it fast.** Our budget: 30 seconds is fine, a minute is acceptable, past 66 seconds a feature does not ship.
   Past the budget, the work runs in the background (for example when a scan is imported), never slower in the
   foreground. Times are measured on real data and stated.

## Layout of a module

- **Sections with colored bands.** Each section has a colored band at the left of its header, and the color says what
  kind of section it is: **yellow** makes something new (segment, crop, save, merge); **green** is a list of what
  exists; **blue** is the views (a display); **gray** is secondary and starts folded; **orange** shows only while
  something runs. *Why: Ron found the first modules "engineering level interfaces: everything is there, but the
  presentation and organization is inconsistent".*
- **One yellow action per section, in the same place.** The main action is the one yellow button, in the section's last
  row, at the right. Everything else is plain. A display-only module has no yellow at all. *Why: someone moving between
  modules knows where to look.*
- **Advanced is collapsed.** The face of a module holds a few controls with good starting values. Everything else is
  under a collapsed Advanced. *Why: rule 4.*
- **No fine print on the face.** An explanation is a tooltip. A state (saved, failed, running) is the status line or the
  button's own label. Advanced holds controls, not prose. *Why: the face has to work for someone who never hovers.*
- **A list fits its space, and the person can resize it.** A list in a module is as tall as its rows, until the module
  column would have to scroll. A grip under it drags it taller or shorter, and the height is remembered; a double-click
  on the grip goes back to automatic. Never a fixed height with a scroll bar above empty space. *Ron: "Scrolling is
  mouse work."*
- **Nothing important under a list.** Anything below a list is effectively hidden (Ron, 2026-10-15: "anything under the
  list is effectively hidden"). A list's actions (Export, Show in Finder) and its notes sit above it; actions on one row
  go in that row's ⋯. In a section whose body is a list, this overrides "the yellow in the last row".

## Controls

- **Every button answers the click.** A pressed button flashes at once. Work that takes more than a moment changes the
  button's own label ("Saving…"), then says the result in the same place ("Saved ✓" or "Not saved"). The status line is
  a second place to say it, never the only one.
- **Work past a few seconds says so, on the 3D view.** Anything that may take more than about two seconds puts one
  banner across the top of the 3D view within a third of a second (`render/working.ts`, `startWork`): what is being
  done, how far (a count, or a moving bar), Stop where the work can be stopped, and its usual time only when that work
  has been measured on this Mac. Facts only. It goes by itself when the work is done; the result is said by the button
  that started it. *Ron, 2026-10-17: "If you need time, you need time. But tell the user that you are working. If you
  don't then the user is left guessing what is going on."*
- **"…" means more is needed.** A button ends in "…" only when its click needs more from the person before anything
  happens: a window, a choice, a question.
- **Visible at arm's length.** A small control (a triangle, ⋯, a pencil, an eye) is never smaller than the text beside
  it, about 12 px; a lone icon is about 16 px. *Ron's test: easily recognizable with your eyes at arm's length from the
  monitor.*
- **(The Databases list in Load / Save has a Details button in place of the ⋯, on Ron's word, 2026-11-01: "Just a details button".)**
- **Names: one click to rename, ⋯ for the rest.** Wherever a module shows a name, the name is its own edit field: a
  pencil on hover, one click gives a text box with the name selected, Enter keeps, Esc cancels. A ⋯ button at the end of
  the row holds every other action, Remove first. A right-click opens the same menu. *Why: no directions to read, the
  fewest clicks.*
- **A final delete asks first.** Anything that cannot be undone asks before it happens and names what goes and from
  where; "Keep" is the way back. Taking a saved thing out of the view does not ask: it can be loaded again.
- **No orange for "not saved".** Unsaved, edited or "placing" is shown by turning the button that resolves it yellow.
  Orange is kept for something running. *Why: orange is foreign to the palette; the yellow button already means "the
  thing to do here".*
- **Shown and hidden are an open and a closed eye.** One drawing for every list (`render/demos/eye-icon.ts`; the SDK's
  `eyeSvg` for extensions); a hidden row is said by the closed eye, never by fading the row or the eye. *Ron, 2026-10-31:
  "In our domain the consensus is open eye and closed eye. dimming is not used normally."*
- **Every tool shows its mouse and keys.** A tool that answers the mouse or keys in the views (the Segment Editor's tools,
  and any like them) lists each action under its controls: the action on the left (Drag, Shift-click, Option-drag, Esc),
  what it does in a few words on the right, a tooltip on each line saying it in plain words. One shared part draws it
  the same way in every tool (`render/demos/seg-tools/registry.ts`, `cheats`). *Ron, 2026-10-31: "we should have
  cheatsheets in every effect to remind the user of modifiers, with tool tips explaining in layperson's terms."*
- **What is not needed now stays out of sight, and can be brought back.** A control that serves only some cases (the
  player that steps through a series' frames, for a diffusion scan) is hidden by default and offered under Advanced.

## Words

- **Plain language.** Words a doctor understands, on the screen and in tooltips: *Illustration* and *Realistic*, not
  *Drawing* and *Lit*. No project jargon, no file paths, no commands. *Ron: "The messages are cryptic and not
  understandable by a new user."*
- **Tooltips say what, not how.** The first sentence says what the person sees or gets. How it is computed belongs in
  the code's comments. *Ron: "for the tooltips the what is important not the how."*
- **Say what was done, not when.** A result says what it is and which method made it ("Aligned to the T1: rigid,
  normalized gradient fields (Haber and Modersitzki 2006)"), with the details and references in the module's Help.
  Dates, rule numbers and program versions belong to the record and the tooltip.
- **The first-time user does not read.** Put things where people look (the top of Downloads, not a subfolder), name
  files by what they are, and give a button rather than a sentence ("Show in Finder"). A message is the fallback, not
  the design.
- **American spelling; anatomy by TA2.** Color, gray, center, labeled. Anatomical terms follow Terminologia Anatomica 2
  in its US English form ("gray matter", "esophagus").

## Principles

- **Controls live in the module you are in.** Count the places one task makes someone visit. A control that lives
  elsewhere (a view's gear, Settings) is also offered in the module where the work happens.
- **Never design for "single" anything.** Two volumes, two patients, two segmentations, two boxes, two versions of a
  result. Any "the volume" in a design is rework waiting.
- **Leave the data, change the appearance.** Display changes are free. Anything that touches voxels is explicit and
  lossless, and the original acquisition is never changed.
- **Any scale: sizes in voxels, never a fixed length.** Albula is used from electron microscopy to astrophysics. A
  default size, a smallest or largest size, a step, a brush, a margin, a handle is stated in voxels of the data shown,
  and turned into the data's units only for display, with the grid named ("14 voxels ≈ 13.6 mm on this 0.97 mm grid").
  A fixed number of millimeters in an interaction is a bug. Clinical measurements (a distance to a tumor) stay in the
  data's units. *Ron, 2026-09-03: "dimensions are extremely important. People use slicer from microscopy to
  astrophysics"; 2026-09-24: "work in voxels, not mm"; 2026-10-20, on a 2 mm smallest box: "did you forget about scales?
  from astrophysics to electron microscope."* (`data-model-design-2026-09-03.md`, Addendum 5.) **The exception:
  image-guided therapy.** A tracked tool (a needle, a pointer, a phone standing in for one) moves in real millimeters,
  and its lengths, distances and errors are stated in mm. *Ron, 2026-11-02: "For IGT mm is the correct measure."*
- **Self-contained.** Every step a user needs (make a database, add scans from a folder, outline a tumor) is a button
  in the application, never a script someone runs for them. *Ron: most users have no assistant at hand; the application
  has to stand on its own.*
- **Modular and versioned.** A look, a color table, a processing rule is a numbered version in one place of its own.
  Old versions stay, and every result records the version that made it, so a scientist can rerun a specific version on
  their data.
- **One writer for each piece of state.** Each setting, list or mapping has one place in the code that changes it;
  everything else goes through it. A copy of data is held only while something reads it.
- **Nothing leaves the computer** unless the person asks. "Everything stays on this computer" must be true wherever the
  screen says it.
- **No changing resolution while someone looks.** One picture quality, chosen by the person. Save work by not redrawing
  an unchanged view, never by switching resolution while the view moves: the jumps read as flicker.
- **Built for hundreds.** Lists and drawing stay usable and fast with hundreds of items: morphometric studies place
  hundreds of landmarks.

## Process

- **A mockup first.** Before a menu or panel is rearranged, a mockup is checked against this page and shown to Ron. It
  says which rules it does not meet and why. Code follows his word.
- **Tests for what can be tested.** The rules a module applies (which tracts count as "near", how a number is computed)
  live in plain functions outside the panel, with tests.
- **An adversarial review.** A separate reviewer who did not build it tries to break the module, checks it item by item
  against this page, and writes down what it finds. The builder answers each finding: fixed, disagreed, or deferred.
- **Then the user's own window.** Rule 2: on their laptop, with their data, on a build whose stamp is checked first.

## The checklist

For reviewing a mockup or a module. A "no" is fine when the mockup says why.

- [ ] Works with no lesion, two patients, a missing scan, a second press
- [ ] Tried on the user's machine and data
- [ ] Clicks and places for the main task counted
- [ ] At most one parameter on the face
- [ ] Times measured on real data; past a minute, in the background
- [ ] Sections banded by kind
- [ ] One yellow action per section, last row, right
- [ ] Advanced collapsed
- [ ] No fine print on the face
- [ ] Lists fit their space and can be resized
- [ ] Nothing important under a list: its actions and notes above it, row actions in the row's ⋯
- [ ] Every button answers the click
- [ ] Work past a few seconds shows the working banner on the 3D view: facts only
- [ ] "…" only where more is needed
- [ ] Small controls visible at arm's length
- [ ] Names: one click to rename; ⋯ and right-click menu
- [ ] Final deletes ask first
- [ ] Yellow button, not orange, for unsaved
- [ ] What only some cases need is hidden, and can be brought back under Advanced
- [ ] A tool's mouse and keys listed under it, with plain tooltips
- [ ] Shown / hidden: the open and closed eye, nothing faded
- [ ] Plain words; tooltips say what
- [ ] Results say what was done and by which method
- [ ] Buttons, not sentences, for the first-time user
- [ ] American spelling; TA2 terms
- [ ] Controls in the module where the work is
- [ ] Nothing designed for one of anything
- [ ] Data left alone; appearance changed
- [ ] Every step a button in the app
- [ ] Rules versioned; results record the version
- [ ] One writer per piece of state
- [ ] Nothing leaves the computer unasked
- [ ] No resolution changes while looking
- [ ] Usable with hundreds of items
- [ ] Mockup first; tests; adversarial review

---

*Compiled 2026-10-15 from the project's working documents for Ron Kikinis; drafted with Claude (Anthropic). The decisions behind
each rule, with Ron's words, are kept in the project's working notes.*
