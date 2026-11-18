# GeoCore API

Multi-tenant backend for geoscience data: mining organizations manage drillholes and
lithology intervals, upload CSV datasets for asynchronous ingestion, and query their data
through a versioned REST API. Every read and write is scoped to the caller's organization.

**Stack:** FastAPI · Pydantic v2 · SQLAlchemy 2 (async) · asyncpg · PostgreSQL 17 ·
PyJWT · pwdlib (Argon2) · pytest + Testcontainers · Docker Compose · GitHub Actions

## Quick start

```bash
cp .env.example .env               # then set POSTGRES_PASSWORD and JWT_SECRET
docker compose up -d --build --wait
uv run python -m scripts.seed      # demo organizations, users and drillholes
open http://localhost:8000/docs
```

### Demo accounts (from `data/seed/`, password `DemoPass123!`)

| Organization | Admin | Viewer |
|---|---|---|
| Red Ridge Mining | `admin@redridge.example` | `viewer@redridge.example` |
| Atacama Copper Co | `admin@atacama.example` | `viewer@atacama.example` |

In `/docs`: call `POST /api/v1/auth/login`, copy `access_token`, click **Authorize**, paste it.
Then upload `data/samples/intervals_red_ridge_valid.csv` (or `..._invalid.csv` to see the
validation report) to `POST /api/v1/ingestions` and poll `GET /api/v1/ingestions/{id}`.

### Local development

```bash
cp .env.example .env
uv sync
docker compose up -d --wait db     # just Postgres; --wait = until it accepts connections
uv run python -m scripts.seed      # idempotent: safe to run again
uv run fastapi dev                 # http://127.0.0.1:8000/docs, auto-reload
```

### Tests & quality

```bash
uv run pytest                      # needs Docker running (Testcontainers Postgres)
uv run ruff check . && uv run ruff format --check .
uv run ty check
```

### Database schema

Tables are created from the SQLAlchemy models when the app starts
(`create_tables()` in `app/db/init_db.py`, called from the lifespan in `app/main.py`).
It only creates *missing* tables; it never alters existing ones. After changing a model
in local dev, reset the database:

```bash
docker compose down -v && docker compose up -d --wait db
uv run python -m scripts.seed
```

## Project layout

```
app/
  main.py              create_app() factory, lifespan, router + error handler registration
  api/v1/              HTTP layer: thin routers (parse → call service → return schema)
  core/                config (pydantic-settings), dependencies, security, exceptions, logging
  db/                  engine/session, declarative Base, ORM models, create_tables()
  schemas/             Pydantic request/response models (Create / Update / Read)
  services/            business rules + transactions; raise domain errors, not HTTP errors
  repositories/        SQL queries; tenant data is always filtered by organization_id
scripts/
  seed.py              idempotent demo data loader
tests/
  unit/                no DB / no HTTP
  integration/         API + real Postgres
  security/            tenant isolation & RBAC
data/
  seed/                demo organizations, users, drillholes
  samples/             lithology CSVs for ingestion (valid and deliberately invalid)
```

## Key design decisions

- **Tenant isolation.** `organization_id` is never accepted from the client; it comes from the
  authenticated user (`CurrentUserDep`) and is passed explicitly to every repository method.
  A resource belonging to another organization returns **404**, identical to a missing one,
  so IDs can't be probed. Tested in `tests/security/`. Postgres Row-Level Security is a
  planned second layer (`organization_id` is denormalized onto child tables for that reason).
- **Layering.** Routers → services → repositories. Services own transactions and raise domain
  exceptions (`NotFoundError`, `ConflictError`, ...) mapped to HTTP in one place.
- **Constraints in the database too.** Lat/lon ranges, positive depth, `to_m > from_m`,
  RQD 0–100 and per-tenant unique `hole_id` are enforced by Postgres, not only by Pydantic.
- **Ingestion is asynchronous and all-or-nothing.** Upload returns `202 Accepted` + a job id;
  a FastAPI background task validates every row (types, ranges, `to_m > from_m`, depth within
  the hole, overlaps in the file and with stored intervals, `hole_id` owned by the caller's
  organization) and reports errors with spreadsheet line numbers. One bad row rejects the
  file, so a dataset is never half-loaded. The job opens its own DB session because the
  request's session is closed once the response is sent. For production scale this would
  move to a durable queue (e.g. Celery/Redis) so a server restart can't lose jobs.
- **Real database in tests.** Testcontainers runs Postgres and the tests create tables with the
  same `create_tables()` the app uses.

## Roadmap

- [x] Skeleton, config, async DB session, models, Docker Compose, CI
- [x] Drillhole list/get/create with tenant scoping + isolation tests
- [x] JWT login, password hashing, `get_current_user`, `/me`
- [x] Drillhole update/delete
- [x] CSV ingestion: background validation, line-level errors, status polling
- [x] Idempotent seed script
- [ ] Structured JSON logging with request IDs
- [ ] Durable job queue, Parquet export, Postgres Row-Level Security, GeoJSON output
