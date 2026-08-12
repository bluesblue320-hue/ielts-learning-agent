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

## Local Python environment

Python 3.12 or newer is required. Create an ignored virtual environment and
install the project with test dependencies:

```bash
python -m venv .venv
```

Activate it with `. .venv/bin/activate` on POSIX or
`.venv\Scripts\Activate.ps1` in PowerShell, then install dependencies:

```bash
python -m pip install -e ".[test]"
```

Set `IELTS_TEST_DATABASE_URL` to the isolated PostgreSQL test database before
running all tests. Tests marked `integration` skip explicitly when it is absent.
Run unit/API tests without PostgreSQL with:

```bash
python -m pytest -m "not integration" -q
```

Apply or inspect migrations with `alembic upgrade head`, `alembic current`, and
`alembic downgrade base`. `IELTS_DATABASE_URL` must point to PostgreSQL.

## Windows Docker Desktop note

On the validated Docker Desktop 29.6.1 / Compose 5.3.0 environment, Compose/Bake
failed before Dockerfile execution when the checkout path contained non-ASCII
characters. If Docker reports a non-printable `x-docker-expose-session-sharedkey`
header, use an ASCII-only checkout path. The clean Compose workflow was verified
from an ASCII-only temporary checkout.
