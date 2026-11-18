# GeoCore API

Multi-tenant backend for geoscience data: mining organizations manage drillholes and
lithology intervals, upload CSV datasets for asynchronous ingestion, and query their data
through a versioned REST API. Every read and write is scoped to the caller's organization.

**Stack:** FastAPI · Pydantic v2 · SQLAlchemy 2 (async) · asyncpg · PostgreSQL 17 ·
PyJWT · pwdlib (Argon2) · pytest + Testcontainers · Docker Compose · GitHub Actions

## Quick start

```bash
docker compose up --build          # Postgres + API (creates tables on start)
open http://localhost:8000/docs
```

### Local development

```bash
cp .env.example .env
uv sync
docker compose up -d db            # just Postgres
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
docker compose down -v && docker compose up -d db
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
  repositories/        SQL queries; every method takes organization_id
  workers/             background ingestion (Celery, Day 3)
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
- **Ingestion is asynchronous.** Upload returns `202 Accepted` + a job id; a worker validates
  and loads rows, so large files never block the request cycle.
- **Real database in tests.** Testcontainers runs Postgres and the tests create tables with the
  same `create_tables()` the app uses.

## Roadmap

- [x] Skeleton, config, async DB session, models, Docker Compose, CI
- [x] Drillhole list/get/create with tenant scoping + isolation tests
- [x] JWT login, password hashing, `get_current_user`, `/me`
- [ ] Seed script
- [ ] Drillhole update/delete
- [ ] CSV ingestion → MinIO → Celery worker → Parquet; ingestion status & errors
- [ ] Structured JSON logging with request IDs
- [ ] Postgres Row-Level Security, GeoJSON output, Redis caching
