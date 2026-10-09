# API reference and implementation notes

The interactive reference is served at `/api/v1/docs`, with a checked-in schema in `apps/api/openapi.json`. Regenerate with `pnpm api:types`. CI fails if the generated schema/types differ from the committed contract.

## Authentication

`POST /auth/login` accepts `{email,password}` and sets `concord_session`. The cookie is HTTP-only, SameSite=Lax, scoped to `/`, and Secure when configured. Tokens have 256 bits of randomness; only SHA-256 token digests are stored. Passwords use Argon2id. Login replaces an existing session in the same browser.

All mutations require `Origin` equal to `APP_ORIGIN`. Authenticated mutations additionally require the `X-CSRF-Token` returned by login or `GET /auth/session`. The CSRF value remains in client memory. Unauthenticated login still requires a trusted origin.

| Method     | Path                                       | Role / behavior                                                                 |
| ---------- | ------------------------------------------ | ------------------------------------------------------------------------------- |
| POST       | `/auth/login`                              | Public, trusted origin required                                                 |
| GET        | `/auth/session`                            | Authenticated user and CSRF token                                               |
| POST       | `/auth/logout`                             | Revoke session, remove cookie                                                   |
| GET        | `/users`                                   | Admin; no password/session fields                                               |
| GET / POST | `/projects`                                | List accessible projects / admin create                                         |
| GET / PUT  | `/projects/{id}`                           | Read / admin configure draft                                                    |
| GET / PUT  | `/projects/{id}/members`                   | Admin list / replace membership                                                 |
| POST       | `/projects/{id}/state`                     | Admin activate, complete, archive                                               |
| POST       | `/projects/{id}/imports`                   | Admin, multipart `file`, draft only                                             |
| GET        | `/projects/{id}/assignments/current`       | Annotator, active claim or null                                                 |
| POST       | `/projects/{id}/assignments/next`          | Annotator, resume/allocate or null                                              |
| PUT        | `/assignments/{id}/draft`                  | Owner, versioned autosave and renewal                                           |
| POST       | `/assignments/{id}/submit`                 | Owner, immutable submission                                                     |
| POST       | `/assignments/{id}/skip`                   | Owner, release and remember skip                                                |
| POST       | `/projects/{id}/assignments/reset-skipped` | Annotator, make own skipped items eligible                                      |
| GET        | `/projects/{id}/metrics`                   | Reviewer/admin, combined quality report                                         |
| GET        | `/projects/{id}/review`                    | Reviewer/admin, unresolved complete items; `all_items=true` includes every item |
| PUT        | `/projects/{id}/items/{item}/adjudication` | Reviewer/admin, fully rated active/completed item                               |
| GET        | `/projects/{id}/events`                    | Reviewer/admin, authenticated SSE                                               |
| GET        | `/projects/{id}/exports`                   | Reviewer/admin; format, selection, include_unresolved                           |
| GET        | `/health`                                  | Public liveness check                                                           |

All paths in the table are relative to `/api/v1`.

Database dependencies use FastAPI's function scope: commits and rollbacks complete before response headers are sent. This prevents a fast follow-up request from observing an uncommitted login, newly created project, or saved annotation.

## Errors

Typical statuses are 401 for missing/expired sessions, 403 for role/membership/CSRF violations, 404 for missing resources, 409 for stale versions or lifecycle conflicts, 413 for an oversized import, and 422 for invalid input. Error responses use FastAPI’s `detail`. Import errors contain `{message, errors: [{row, message}]}` and roll back the entire import.

## SSE and revisions

Submissions and adjudications increment `metric_revision` in the same transaction. State transitions also increment it. The SSE generator opens a fresh database session every second, emits `event: revision` on changes, and emits comment keepalives every ten unchanged polling intervals. It validates the session and current user role on every poll, emitting `event: expired` before closing when authorization expires. The initial event always sends the current revision, allowing reconnects to catch up without an event log.

The browser invalidates TanStack Query metrics/review/project keys after revision events. If streaming is unavailable, metrics fall back to ten-second polling. Review lists also poll every ten seconds. No broker or per-process memory state is required. Proxy buffering is disabled through `X-Accel-Buffering: no`, and stream responses use `Cache-Control: no-cache, no-transform`.

## Export schema 1.0.0

Common fields: `schema_version`, `project_id`, `item_id`, `external_id`, `mode`, `content`, `metadata_json`, `tokens`.

Raw rows add `annotator_id` (pseudonymous UUID), normalized `payload`, and `submitted_at` (Unix seconds). Consensus adds `payload`, `resolved`, `vote_share`, `resolution`, `reviewer_id` (pseudonymous UUID or null), and `rationale`.

JSONL preserves mode-specific payloads. Arrow-based formats use a stable payload struct with nullable `label`, `choice`, `note`, and `spans`. Content similarly has nullable mode-specific fields. This supports empty datasets and deterministic cross-format typing. Arbitrary metadata is serialized to lossless, sorted JSON in `metadata_json`.

Exports take a consistent materialized snapshot while holding the project mutation lock, release it, then encode off the async event loop. Hugging Face archives contain a `DatasetDict.save_to_disk` directory at `dataset/`. Empty splits explicitly receive one Arrow shard so they can be reopened with `load_from_disk`.
