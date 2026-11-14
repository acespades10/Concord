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

| Check                          | Result                                                                                                    |
| ------------------------------ | --------------------------------------------------------------------------------------------------------- |
| Static references and evidence | PASS: local links, anchors, ARIA references, export hashes and recorded counts                            |
| Browser widths                 | PASS: 1440, 1024, 820, 768, 390 and 320 pixels                                                            |
| Overflow                       | PASS: no horizontal overflow or section content overflow at those widths                                  |
| Submissions, Review and Export | PASS: stable panel height, clicks, arrow keys, Home/End and rapid pointer changes                         |
| Mobile menu                    | PASS: focus stays in the open menu, page content becomes inert, Escape and section selection close it     |
| Copy commands                  | PASS: button and live status confirm success; denied clipboard access selects commands for manual copying |
| Images                         | PASS: original product screenshot loads and decodes                                                       |
| Browser errors                 | PASS: no JavaScript exceptions or failed local requests                                                   |
| Automated accessibility        | PASS: zero axe WCAG 2 A/AA and 2.1 AA violations on desktop and phone; 26 passing desktop rules           |
| Visual review                  | PASS: desktop, tablet and phone screenshots inspected; narrow-phone overlap corrected                     |
| Formatting                     | PASS: repository Prettier and Python formatter checks                                                     |

These are bounded checks, not a claim of complete accessibility or support for
every browser. Download and documentation targets are real files. GitHub source
links require repository access until the owner makes it public. Dataset DOI and
license links identify their original publishers.

## Design engineering polish

Applied Emil Design Engineering, Design Taste, Animate and Apple Design to the
existing site. No animation library or new artwork was added.

| Before                                     | After                                                            | Why                                                |
| ------------------------------------------ | ---------------------------------------------------------------- | -------------------------------------------------- |
| Uniform hero title and fading preview      | Two-level type hierarchy and a complete, centered record preview | Show the source and reviewed decision clearly      |
| Separate tabs with changing content height | Equal-width segmented control and stable panel height            | Keep the record in place when comparing stages     |
| 280ms tab fade on keyboard input           | Instant keyboard changes; 140ms pointer fade                     | Respond directly to keyboard navigation            |
| Narrow tablet text columns                 | Explanation above the record, aligned to the page grid           | Give the source text enough room                   |
| Copy confirmation only below the button    | In-place Copied state plus live status and failure fallback      | Confirm the action where it happened               |
| Small static workspace capture             | Responsive preview with a link to the full-size original         | Keep the page light and the screenshot inspectable |

Motion serves feedback and state indication. Pointer presses use the existing
140ms token and curve; the tab indicator travels in 240ms. All motion remains
interruptible, keyboard state changes are instant, and reduced motion disables
travel. Data, statistics and sections do not animate on scroll. Hover movement
is restricted to fine pointers. Phone checks use browser emulation; physical
device feel and Safari rendering were not tested.

## Design and performance checks

Antislop was applied during the build. The direction, typography, palette and
interaction rationale are recorded in [PLAN.md](PLAN.md). Screens use real source
records and the original application capture. No generated artwork was needed.

The design-taste performance script measured approximately 132 KiB total transfer,
12 requests, one 24 KiB image, one 30 KiB font and no WebGL contexts at device-pixel
ratio 1. It reported zero failures at 1440 and 390 pixels. Responsive images
removed the previous sizing warnings; the two remaining warnings concern high
background CPU use. Higher-density screens can select the 1280px image. Local
timing figures are not field performance or a product capacity claim.

The layout checker, including headline stress checks, reports zero findings at
1440x900, 1024x768, 820x1180, 768x1024 and 390x844. The additional 320px browser
check permits natural section height so content stays readable.

The quick consistency scan completed at 1440 and 390 pixels; it is not a clean
pass. Its findings were reviewed separately from the layout and accessibility
checks. The following dispositions explain the remaining differences:

| Finding                                        | Disposition                                                                                                                                                                                                                        |
| ---------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| No visual / text-only band                     | The hero and workflow are live HTML representations of an actual record. The evidence section is a linked test-results list. Decorative imagery would not explain these better.                                                    |
| Center axis / inset labels / split pairs       | The centered hero and date form one group. Record text uses internal padding, and the 4/8-column workflow intentionally gives more room to the data than the 5/7-column reproduction section. Outer edges pass the layout checker. |
| Multiple headings                              | The scan treats the numeric statistic `53` as a section heading. The actual section headings remain one screen apart.                                                                                                              |
| Contrast / font loading / utility button style | Strengthened explanatory text contrast, removed an unloaded font name and aligned the copy control with the secondary surface after the scan. Both accessibility scans pass.                                                       |
| Section gaps                                   | Screen-sized sections retain some extra space after the mobile workspace image. The full-size capture remains accessible by link; content is neither cropped nor stretched to fill the space.                                      |
| Small copy / status chips / selected tab       | Compact supporting metadata and source labels are distinct from primary copy and actions. The selected tab uses a light surface to maintain contrast throughout movement.                                                          |
| Navigation and footer destination              | Skip to content and Reproduce have real, checked anchors; the footer contains the reproduction commands. Section labels describe destinations without duplicating whole headings.                                                  |
| Ground colors / copy length                    | Sage variations distinguish source and reviewed decisions. Extra evidence text explicitly identifies simulation and its limits.                                                                                                    |

Quick mode omits the full motion, form and section-tile sweeps. The functional
script separately checks keyboard behavior, reduced motion, focus containment
and rapid selection. No kit asset or checker was modified to suppress findings.

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
- R-25 PASS: axe found no contrast violations on desktop and phone after the selected-tab surface was corrected.
- R-26 PASS: three tabs, menu, links and copy control have working targets or handlers.
- R-27 PASS: content is local and immediately available; clipboard failure selects commands and reports a manual-copy instruction.
- R-28 PASS: no FAQ.
- R-32 PASS: native controls, visible instant keyboard focus, arrow-key/Home/End tabs and contained menu focus with Escape dismissal.
- R-33 PASS: behavior is implemented in checked-in HTML, CSS and JavaScript.
- R-34 PASS: no theme toggle; one intentional theme with an inverse evidence section.
- R-35 PASS: site served over HTTP and browser click-through recorded above.
- R-36 PASS: no compliance, adoption, human-agreement or production-performance claims.
- R-37 PASS: design direction and ENERGY 2 / RHYTHM 2 / MOTION 1 recorded in PLAN.md.
- R-38 PASS: real exported record, source labels and explicitly identified simulated submissions.
- R-39 PASS: native named controls, image alternative text, landmarks, language, title, focus states and reduced-motion support; no timed loops.
- R-40 PASS: image dimensions, reserved status space, local font, deferred scripts and measured performance scope.

### Purpose gate

- R-01 PASS: no decorative gradients or glow; the complete recorded preview remains visible on a sage ground.
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

Those runs preceded repository publication. The repository was made public on
14 November 2026 after the release-hardening checks below. The Pages workflow
deploys the static site when public; see [the Pages instructions](README.md#github-pages).

The application CI job now also runs `site/scripts/check-browser.cjs` after
installing Chromium and uploads its report and viewport captures with the browser
evidence artifact.

## Public release hardening

The [release CI run](https://github.com/acespades10/Concord/actions/runs/43589834383)
passed application, PostgreSQL, container and production-image jobs for commit
`f64224d`. Next.js was updated to 16.4.6; the production JavaScript dependency
audit reported zero advisories. The production-image smoke test verified a real
admin login, secure cookies, blank login fields, and persisted login throttling.
The repository now includes an MIT license, third-party notices, production
configuration, account provisioning and a free-hosting guide. Managed-database
TLS and provider deployment are verified separately from this historical run.
