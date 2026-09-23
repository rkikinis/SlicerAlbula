# Ron's Rules for Tools

The specification this project is built against. Kept here because it is cited throughout — the
response-time budget in `CONSTRAINTS.md` derives from rule 5 — and because its home is a wiki that
was returning 502 on 2026-09-10 when this copy was made.

**Source:** `https://www.slicer.org/wiki/Documentation-Rons-Rules-For-Tools`, transcribed from the
Internet Archive. A presentation on the topic was given at the IMIC workshop at MICCAI 2014; **this
page is the source, not the slides.** **Citable, archived version (2026-09-21):** Kikinis R.
"Ron's Rules for Tools", Zenodo, https://doi.org/10.5281/zenodo.22707222 (CC BY 4.0, dated
2014-09-14) — the same text as below, reformatted; cite the DOI.

---

> "Rules for tools" is an informal set of rules that developers should keep in mind when working on
> interactive tools for translational clinical research. If you follow them, you will create tools
> that many people will use.

**1. You make it, I break it.**
> Tools need to be robust and function with a variety of workflows, not only the one envisioned by
> the developer.

**2. Your tool does not exist, until it works on my laptop with my data.**
> Until then, it's an unconfirmed rumor.

**3. I am lazy. I do not like to move the mouse or to type.**
> User friendliness:
> - Minimize the number of clicks
> - Minimize the distance my pointer has to travel
> - Have good default values for the parameter and I/O, and allow me to override.

**4. No more than one simple parameter.**
> If I need more than 20 seconds to figure out how to set the parameter, I won't! See also here about
> the dangers of too many parameters.

**5. I have ADD. Make your algorithm fast.**
> Performance Requirements
> - ADD = attention deficit disorder
> - instantaneous is what I really want (this is where the slider comes in)
> - under a minute is good
> - 5 minutes are acceptable
> - 10 minutes or more are not

## How To Make Algorithms Robust

> - Build a case library with 10 or more cases
> - Use half for development, cycle through the cases daily
> - Use the other half for testing

---

## Two notes on applying these here

**The performance bar in this project is stricter than the one above, deliberately.** The wiki calls
under a minute good and five minutes acceptable. Asked directly on 2026-09-08, Ron gave a tighter
answer: *"30 sec is ok, 1m is acceptable, everything else is problematic. Each of these with a plus
minus 10%."* `CONSTRAINTS.md` uses that — 33 s target, 66 s limit — because it is the recent and
direct statement, and because twelve years of faster hardware have moved what counts as fast. The
2014 wording is the floor, not the target. Ron's own reasoning for the tightening, 2026-09-10:
*"The rules are old. People's attention span has decreased, the computers have become faster. If it
is slower, we need a batch job paradigm and software that can handle asynchronous parallel
activities. The user will move on and we will need to be able to bring in the slow [result later]."*
So the rule has two halves now: be fast, and where you cannot be, **be a job rather than a wait**.
See `CONSTRAINTS.md`.

**The case library exists; the public corpus is a different thing.** Ron, 2026-09-10: *"My dicom db
in Albula has all the test cases. I have not exercised all of them because the current topics at
hand do not require robustness testing."* The development database holds 29 patients, which meets the
"ten or more" bar comfortably. `Contents/data/README.md` describes six series across four cases, and that is
not the case library — it is the **reproducibility** corpus, the subset a stranger can fetch so the
numbers quoted in this project can be checked. Do not read one as a shortfall against the other.

**Rules 3 and 4 are deferred on purpose, not neglected.** Ron: *"My approach was to first get a
package together with basic functionality and then improve the usability (points 3 and 4)."* So a
count of clicks or parameters today measures a stage that has not been reached yet. What that does
NOT excuse is failing to count: footnote 3 asks for clicks and pointer distance, footnote 4 gives a
20-second test, and neither number exists for this application.
