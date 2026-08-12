# Local development

## PostgreSQL

Copy `.env.example` to `.env`, replace every placeholder password with a
local-only value, and keep `.env` uncommitted. Start and verify PostgreSQL:

```bash
docker compose up -d --wait db
docker compose exec db pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"
```

Stop PostgreSQL while preserving its named development volume:

```bash
docker compose down
```

Run `docker compose down --volumes` only when the local development data is no
longer needed.

## Integrated application stack

From a clean checkout, create `.env` as described above, then build and start the
API, migration job, and PostgreSQL service:

```bash
docker compose up -d --build --wait
```

The API is available on `http://localhost:8000` by default. Verify liveness and
readiness at `/health/live` and `/health/ready`. Run the complete test suite in
the test image:

```bash
docker compose --profile test run --rm --build test
```

Stop the stack with `docker compose down`. Add `--volumes` only when its local
PostgreSQL data is no longer needed.
