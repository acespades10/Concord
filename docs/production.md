# Production deployment

Concord's code is MIT licensed. Dataset and font licenses are listed in
[third-party notices](../THIRD_PARTY_NOTICES.md). The public portfolio website is
independent of the annotation service and never receives account credentials.

## Free hosting

[Render Free](https://render.com/docs/free) can run the combined web/API image in
`deploy/Dockerfile.hosted`, with an HTTPS `onrender.com` subdomain. The
[Neon Free plan](https://neon.com/pricing) supplies persistent PostgreSQL storage.
Use a Neon region near the Render service. Stay on the free plans; no paid
resource is required for a small portfolio demo.

Render Free services sleep after 15 minutes without traffic and share a monthly
750-hour workspace allowance. The first request after sleep can take a minute
or more. The container filesystem is ephemeral: store application data in Neon,
never SQLite or a file inside the container. Render's own free PostgreSQL
expires after 30 days, so it is not the database recommended here. Neon has
storage and compute quotas; review the current provider limits before importing
large datasets. Free hosting does not provide an availability guarantee.

Create a Render web service from this repository using `render.yaml`, or choose
Docker, the hosted Dockerfile, and the **Free** plan in its dashboard. Configure:

| Variable        | Value                                                                |
| --------------- | -------------------------------------------------------------------- |
| `APP_ENV`       | `production`                                                         |
| `DATABASE_SSL`  | `verify-full` (also the hosted image default)                        |
| `COOKIE_SECURE` | `true`                                                               |
| `APP_ORIGIN`    | The exact `https://...onrender.com` origin, without a trailing slash |
| `DATABASE_URL`  | Neon PostgreSQL URL, with `postgresql+asyncpg://` and `ssl=require`  |

Use the direct Neon connection rather than its transaction pooler. Replace
`sslmode=require` with `ssl=require` and remove `channel_binding=require` for
SQLAlchemy's asyncpg driver. Keep the generated database password; do not use
the local-demo password. Production rejects PostgreSQL passwords shorter than
20 characters. Database URLs are secrets and belong only in the provider's
secret environment settings or an ignored local file.

`DATABASE_SSL=verify-full` uses the operating system's trusted certificate
authorities and verifies the database hostname for both migrations and runtime
connections. Self-hosted Compose uses a private internal database network and
does not enable database TLS; do not expose that database port to the internet.

Startup applies migrations, starts one loopback API process and the public web
proxy, and stops both if either exits. It never seeds demo data. The provider
terminates HTTPS. The application still requires the configured browser Origin,
CSRF protection, secure cookies, and authenticated roles.

## Accounts

There is no public registration. Run account provisioning against the production
database from a trusted workstation or a provider shell. Set `DATABASE_URL` in
the process environment without displaying it. Then run:

```sh
uv run --directory apps/api python -m app.accounts create --email owner@example.com --name "Workspace owner" --role admin
```

The command prompts twice for a unique password of at least 16 characters. It
does not accept a password argument or overwrite an existing account. Provision
reviewers and annotators with the corresponding `--role`. To rotate a password:

```sh
uv run --directory apps/api python -m app.accounts reset-password --email owner@example.com
```

Rotation revokes that account's existing sessions. Use a password manager to
share individual accounts securely. Production refuses all `@concord.demo`
logins and refuses `python -m app.seed`, including against a previously seeded
database. Login fields start empty and do not advertise demo credentials.

For the first deployment on a host without a shell, the combined image also
accepts `INITIAL_ADMIN_EMAIL` and `INITIAL_ADMIN_PASSWORD_HASH` as secret
environment variables. Generate a unique password locally and hash it with
Concord's Argon2id password hasher. Only the hash is uploaded. Bootstrap requires
an empty workspace, never promotes an existing non-admin, and never changes an
existing admin's password. Remove these two environment variables after the
first successful sign-in. They are not needed for subsequent deployments.

## Login rate limiting

Every login consumes an atomic database budget before password verification:
10 attempts per normalized account per 10 minutes, plus 30 total attempts per
workspace per minute. All attempts count, including successful and rejected
ones. Exhausted budgets return HTTP 429 with `Retry-After`; expired windows
recover automatically. Budgets survive worker restarts and are shared by
multiple workers. Account keys are SHA-256 digests, and forwarded IP headers
cannot bypass these limits.

These conservative limits suit a small workspace. Shared budgets can also deny
legitimate sign-ins during abuse. Larger deployments should add provider/WAF
controls and tune limits after measuring traffic. There is no claim of DDoS
protection.

## Self-hosting with automatic HTTPS

On a Docker-enabled server with DNS pointing to it and ports 80/443 available:

```sh
cp deploy/production.env.example .env.production
# Set DOMAIN and a generated POSTGRES_PASSWORD in this ignored file.
docker compose --env-file .env.production -f compose.production.yaml up --build -d
```

Use a URL-safe random database password of at least 32 characters. Caddy obtains
and renews certificates, redirects HTTP to HTTPS, and sets HSTS. Only Caddy
publishes host ports; web, API and PostgreSQL use a private internal network.
Certificate and database files persist in named volumes. Provision accounts:

```sh
docker compose --env-file .env.production -f compose.production.yaml exec api python -m app.accounts create --email owner@example.com --name "Workspace owner" --role admin
```

Back up PostgreSQL before upgrades and keep backups outside the server. Applying
migrations does not replace a restore procedure. Before accepting real data,
verify account sign-in, secure cookie flags, unauthorized-role rejection, the
429 response and recovery, export round trips, and persistence after restart.

## Verification

CI audits production JavaScript dependencies and checks formatting, lint, types,
API contracts, tests, migrations, browser workflows, accessibility and Docker
startup. Dedicated security regressions cover production settings, demo-account
rejection, secure cookies, account provisioning and password rotation, persisted
login failures, concurrent rate budgets, and window recovery. Provider setup
and a successful hosted smoke test must be recorded separately from CI.
