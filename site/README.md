# Concord static website

Product and validation site, built with plain HTML, CSS and JavaScript. The
application source is public and MIT licensed, with separate dataset and font licenses.
No live annotation server is required by this site.

Published at [acespades10.github.io/Concord](https://acespades10.github.io/Concord/).
The separate [live annotation app](https://concord-acespades10.onrender.com/)
requires a provisioned account. Its free server sleeps when idle, so the first
request can take a minute or more. See [release verification](../docs/public-release.md).

## Preview

From the repository root:

```sh
python -m http.server 8080 --directory site
```

Open `http://localhost:8080`. The record controls replay a recorded simulation;
they do not submit or edit annotations. All assets are local, including the font.

## GitHub Pages

The `Publish Concord website` workflow validates the site while the repository is
private and skips deployment. It deploys the `site/` directory when the repository
is public. It runs on matching main-branch pushes, when the repository becomes
public, or through **Actions → Publish Concord website → Run workflow**.

After making the repository public, select **Settings → Pages → Build and
deployment → Source → GitHub Actions** if GitHub requires initial setup. Then run
the workflow. The expected address is:

`https://acespades10.github.io/Concord/`

Repository links are publicly accessible. Deployment status is available in
the repository's Actions tab; the portfolio site is separate from the live
annotation application and does not require an annotation server.

## Evidence

`evidence/results.json` is a shareable snapshot of the successful 14 November 2026
run. It omits local paths, passwords and sessions. The JSONL exports are byte-for-byte
copies of the validated files, with their hashes checked by the site validator.
The source dataset is CC BY 4.0; attribution and provenance are included.

The site explicitly identifies simulated annotations and automatic source-based
review. Its test counts are dated results, not an automatically updated CI badge.
The application screenshot shows seeded demo projects, separately from the
30-record benchmark. When replacing evidence, rerun the independent validator and
update the dated counts, report, hashes and any corresponding copy together.

```sh
node site/scripts/check-static.mjs
```

See [website validation](VALIDATION.md) for the recorded browser checks,
accessibility scan, design review and commands to reproduce them.

The layout and interaction assets come from the installed design-taste skill and
are retained unchanged. `styles.css` supplies Concord's brand tokens and record
visuals. Instrument Sans is self-hosted under the included SIL Open Font License.
The product screenshot is derived from the repository's original workspace capture.
