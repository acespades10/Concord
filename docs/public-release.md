# Public release verification

Verified on 14 November 2026:

- [Public MIT-licensed repository](https://github.com/acespades10/Concord)
- [GitHub Pages portfolio](https://acespades10.github.io/Concord/)
- [Live annotation workspace](https://concord-acespades10.onrender.com/)

## Dependencies and CI

Next.js and eslint-config-next are 16.4.6 in the lockfile. The full pnpm audit
(including development tools) and pip-audit of the installed Python environment
both report zero advisories. GitHub scanning after publication exposed additional
tooling and dataset dependencies, which were updated to patched versions:
datasets 5.0.1, certifi 2026.10.23, filelock 4.2.10, fsspec 2026.6.0,
opentelemetry-api 1.45.2, Vitest 4.1.12, and patched transitive JavaScript packages.
Scoped pnpm overrides keep minimatch, shell-quote and Vite on fixed versions;
CI audits JavaScript and Python dependencies, including development tooling.
The refreshed environment passed 141 backend tests, 6 frontend tests, ESLint,
and formatting checks locally.

All four jobs (application, PostgreSQL, containers,
and production image) passed for release implementation `99f6265` in
[CI run 43590850118](https://github.com/acespades10/Concord/actions/runs/43590850118).
The [Pages deployment](https://github.com/acespades10/Concord/actions/runs/43591074762)
also passed and the portfolio returned HTTPS 200.

GitHub vulnerability alerts, private vulnerability reporting, secret scanning,
and secret scanning push protection are enabled. Dataset and font licenses are
preserved in [third-party notices](../THIRD_PARTY_NOTICES.md).

## Live deployment

Render Free hosts the combined Next.js/FastAPI container in Singapore. Neon Free
provides persistent PostgreSQL in the same region. Database connections verify
both the certificate authority and hostname. Migrations ran successfully and a
real owner account was provisioned. Production demo seeding and demo-account
login are disabled; the new workspace contains zero projects.

The following checks passed against the public HTTPS service:

- Health endpoint returned 200 and `status: ok`.
- Login page omitted demo credentials and its fields started empty.
- Anonymous project access returned 401.
- The provisioned owner signed in with the admin role.
- The session cookie had Secure, HttpOnly and SameSite=Lax flags.
- Session and project endpoints accepted the authenticated session.
- Logout succeeded and the revoked session subsequently returned 401.
- Ten failed logins for a disposable nonexistent account returned 401; the next
  returned 429 with a positive Retry-After value. The owner account was not used
  for the rate-limit test.
- Browser sign-in opened the empty admin workspace, including the New project
  action and zero-project statistics.

The temporary HTTP smoke-test session was logged out. No test projects or demo
accounts were created. Credentials remain in ignored private local files and
the hosting provider's secret environment settings, outside Git and Docker build
contexts. The initially shared database credential was rotated before deployment.

## Limits and operations

This is a portfolio MVP on free services. Render sleeps after 15 minutes of
inactivity; the first request may take a minute or more. Its free workspace has
a monthly compute allowance, and Neon has storage and compute quotas. No paid
resource was selected. The supplied onrender.com subdomain uses managed HTTPS.

There is no public registration. Provision an individual account for each team
member using the [production account CLI](production.md#accounts). Review
provider quotas and establish backups and a restore procedure before relying
on the service for valuable data. CI and these smoke checks do not establish an
availability guarantee or a comprehensive security assessment.
