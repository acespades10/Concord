# Website validation

Checked locally on 14 November 2026. This report covers the static website;
[benchmark results](evidence/RESULTS.md) cover the annotation application.

## Reproduce the website checks

```sh
pnpm install --frozen-lockfile
pnpm --filter @concord/web exec playwright install chromium
node site/scripts/check-static.mjs
node site/scripts/check-browser.cjs
```

The browser script starts and closes its own loopback server and headless browser.
Set `CHROME_PATH` to use an existing Chromium executable. Results and screenshots
are written to `.local/site-qa/`. Local verification used Windows, Node 24 and
Chromium 1248. No application API or annotation account is needed by the site.

## Observed results

| Check                          | Result                                                                                 |
| ------------------------------ | -------------------------------------------------------------------------------------- |
| Static references and evidence | PASS: local links, anchors, ARIA references, export hashes and recorded counts         |
| Browser widths                 | PASS: 1440, 1024, 820, 768, 390 and 320 pixels                                         |
| Overflow                       | PASS: no horizontal overflow or section content overflow at those widths               |
| Submissions, Review and Export | PASS: clicks and arrow-key selection display the corresponding saved record panel      |
| Mobile menu                    | PASS: opens, makes page content inert, closes with Escape and section selection        |
| Copy commands                  | PASS: status confirms copying; clipboard contains the benchmark command                |
| Images                         | PASS: original product screenshot loads and decodes                                    |
| Browser errors                 | PASS: no JavaScript exceptions or failed local requests                                |
| Automated accessibility        | PASS: zero axe WCAG 2 A/AA and 2.1 AA violations on the desktop page, 26 passing rules |
| Visual review                  | PASS: desktop, tablet and phone screenshots inspected; narrow-phone overlap corrected  |
| Formatting                     | PASS: repository Prettier and Python formatter checks                                  |

These are bounded checks, not a claim of complete accessibility or support for
every browser. Download and documentation targets are real files. GitHub source
links require repository access until the owner makes it public. Dataset DOI and
license links identify their original publishers.

## Design and performance checks

Antislop was applied during the build. The direction, typography, palette and
interaction rationale are recorded in [PLAN.md](PLAN.md). Screens use real source
records and the original application capture. No generated artwork was needed.

The design-taste performance script measured approximately 181 KiB total transfer,
12 requests, one 75 KiB image, one 30 KiB font and no WebGL contexts. It reported
zero failures at 1440 and 390 pixels. Warnings covered an image larger than its
display size and high background CPU use. Its local timing figures are not field
performance or a product capacity claim. The final phone layout allows content
to grow rather than overlap adjacent sections.

The full consistency checker did not finish; it is not reported as passing.
The layout checker flags its rigid column and single-screen heuristics for the
custom evidence columns, right-aligned screenshot description and natural mobile
section heights. These are deliberate composition choices: text remains readable,
section content does not overlap, and the actual record is kept visible. Tablet
whitespace preserves the screen-based composition. No kit asset or checker was
modified to suppress findings. Functional and visual verification above are
reported separately from these design heuristics.

## Antislop delivery gate

Each line records the applicable rule and evidence. Inapplicable components are
identified explicitly rather than implying they were tested.

### Hard gate

- R-02 PASS: authored page text contains no em dash.
- R-03 PASS: six-width checks and screenshots confirm contained, readable content.
- R-17 PASS: displayed counts link to dated benchmark results and exported evidence.
- R-18 PASS: no testimonials or fictional customers.
- R-23 PASS: existing product identity and screenshot; navigation implements the requested project and validation site.
- R-24 PASS: every navigation anchor resolves in the static check.
- R-25 PASS: axe found no contrast violations on the desktop page; phone uses the same colors.
- R-26 PASS: three tabs, menu, links and copy control have working targets or handlers.
- R-27 PASS: content is local and immediately available; clipboard failure selects commands and reports a manual-copy instruction.
- R-28 PASS: no FAQ.
- R-32 PASS: native links and buttons, visible focus, arrow-key tabs and Escape menu dismissal.
- R-33 PASS: behavior is implemented in checked-in HTML, CSS and JavaScript.
- R-34 PASS: no theme toggle; one intentional theme with an inverse evidence section.
- R-35 PASS: site served over HTTP and browser click-through recorded above.
- R-36 PASS: no compliance, adoption, human-agreement or production-performance claims.
- R-37 PASS: design direction and ENERGY 2 / RHYTHM 2 / MOTION 1 recorded in PLAN.md.
- R-38 PASS: real exported record, source labels and explicitly identified simulated submissions.
- R-39 PASS: native named controls, image alternative text, landmarks, language, title, focus states and reduced-motion support; no timed loops.
- R-40 PASS: image dimensions, reserved status space, local font, deferred scripts and measured performance scope.

### Purpose gate

- R-01 PASS: desktop preview fade signals a product window; no decorative glow.
- R-04 PASS: no generic decorative icon set.
- R-06 PASS: Instrument Sans serves readable labels; monospace is limited to IDs and commands.
- R-07 PASS: no background grid or pattern.
- R-08 PASS: link arrows come from the existing interaction system; buttons use descriptive text.
- R-09 PASS: the adjudicated state identifies a real recorded decision.
- R-10 PASS: no glass panels.
- R-12 PASS: limited preview shadow separates the product window from its ground.
- R-13 PASS: no glow.
- R-14 PASS: evidence rows support comparison; workflow and screenshot use different compositions.
- R-19 PASS: user-triggered hover and tab feedback; no scroll animation or timed carousel.
- R-22 PASS: no generic illustration.

### Liveliness

- Dials PASS: ENERGY 2 / RHYTHM 2 / MOTION 1 are explicit in PLAN.md.
- Consistency PASS: calm color, varied evidence and record sections, restrained interaction.
- Focal points PASS: source record, interactive review, test counts, product screen and reproduction command.
- Whitespace PASS: section boundaries separate different kinds of evidence.
- Accent PASS: sage identifies decisions and primary actions.
- Identity PASS: record IDs, label rows and reviewed states repeat across the page.
- Design read PASS: existing Concord cream/sage identity and original screenshot informed the plan.

### Craftsmanship and quality locks

- C-1 PASS: palette, type, record motif and inverse evidence area have written purposes.
- C-2 PASS: interactive controls passed the browser checks.
- C-3 PASS: each section supports workflow inspection, evidence or reproduction.
- C-4 PASS: six viewport sizes, keyboard controls and reduced-motion checks; broader browser coverage remains untested.
- C-5 PASS: figures and records match checked-in evidence.
- R-05 PASS: record inspection, evidence list, original screenshot and commands supply distinct sections.
- R-11 PASS: controls and record surfaces use a restrained radius scale, without capsule styling everywhere.
- R-15 PASS: actions name their objects, such as View repository and Copy commands.
- R-16 PASS: copy describes annotation and validation behavior without marketing superlatives.
- R-20 PASS: the unanimous-wrong SMS case makes the page specific to this benchmark.
- R-21 PASS: light product page; inverse section separates validation evidence.
- R-29 PASS: cream, dark ink and sage form the page palette.
- R-30 PASS: original Concord content and product capture, no copied competitor identity.
- R-31 PASS: major visual choices are documented in PLAN.md.

## Publication

GitHub Actions verified implementation commit `23f91bc` on 14 November 2026:

- [Verify Concord](https://github.com/acespades10/Concord/actions/runs/43512334863): application, PostgreSQL and container jobs all passed.
- [Publish Concord website](https://github.com/acespades10/Concord/actions/runs/43512334790): static validation passed; deployment skipped because the repository was private.

The repository remains private. The Pages workflow validates the static files and
skips deployment while private. The owner controls visibility and can follow
[the Pages instructions](README.md#github-pages) when ready. No live public site
is claimed by this report.
