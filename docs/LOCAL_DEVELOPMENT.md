# Local development

## PostgreSQL

Copy `.env.example` to `.env`, replace every placeholder password with a
local-only value, and keep `.env` uncommitted. Start and verify PostgreSQL:

```bash
docker compose up -d --wait db
docker compose exec db sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

Stop PostgreSQL while preserving its named development volume:

```bash
docker compose down
```

Run `docker compose down --volumes` only when the local development data is no
longer needed.

The development `db` uses the named `postgres_data` volume. The test profile
uses a separate `test-db` service on `TEST_POSTGRES_PORT` (5433 by default),
with no persistent volume. Its credentials and database name come from the
`TEST_POSTGRES_*` values in `.env`.

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

Compose passes `IELTS_DOCKER_TEST_DATABASE_URL` to pytest as
`IELTS_TEST_DATABASE_URL`, so database and Alembic integration tests operate
only on `test-db`. The `api` and `migrate` services continue to use the
development `db` through `IELTS_DOCKER_DATABASE_URL`.

Stop the stack with `docker compose down`. Add `--volumes` only when its local
PostgreSQL data is no longer needed.

## DeepSeek and Writing evaluation

The normal API composition always uses `DeepSeekProvider`; there is no provider
selector or runtime FakeProvider mode. Configure these local-only values in
`.env`:

```text
IELTS_DEEPSEEK_API_KEY=your-local-key
IELTS_DEEPSEEK_API_URL=https://api.deepseek.com/chat/completions
IELTS_DEEPSEEK_MODEL=deepseek-v4-pro
IELTS_DEEPSEEK_TIMEOUT_SECONDS=30
IELTS_DEEPSEEK_THINKING_MODE=disabled
```

`IELTS_DEEPSEEK_THINKING_MODE` is a strict `enabled`/`disabled` enum. The
application default is explicitly `disabled`, and every DeepSeek request sends
that mode using the provider `thinking.type` field. Invalid values fail
configuration before a provider call.

The key is required only when calling `POST /writing/evaluate`. Without it, the
application and health endpoints still start, while the writing endpoint returns
the safe `provider_configuration` response. No live DeepSeek request was
required for Phase 2 automated or Docker validation.

See the [Writing API reference](API.md) for request/response examples,
deterministic word count and product-band behavior, bounded retries, failure
codes, trust-boundary limits, and the score-equivalence disclaimer.

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

Start the isolated test database with
`docker compose --profile test up -d --wait test-db`, then set
`IELTS_TEST_DATABASE_URL` to its host URL before running all tests:

```bash
python -m pytest -q --strict-markers
```

The database name must contain a separate `test` token and its URL must differ
from `IELTS_DATABASE_URL`. Integration tests skip explicitly only when
`IELTS_TEST_DATABASE_URL` is absent. Run the deterministic non-integration
suite without PostgreSQL with:

```bash
python -m pytest -m "not integration" -q --strict-markers
```

Both commands remove any inherited DeepSeek key and block provider HTTP unless a
test supplies an explicit mocked client.

Apply or inspect development migrations with `alembic upgrade head`,
`alembic current`, and `alembic downgrade base`; `IELTS_DATABASE_URL` controls
that target. The current head is `0004_writing_practice`. Pytest migration checks instead
use `IELTS_TEST_DATABASE_URL` and must point to the isolated test database.

## Phase 3 learner-state commands

Phase 3 adds deterministic learner state and planning on top of the Writing
pipeline. The isolated test database must be migrated to `head`
(`0004_writing_practice`) before the learner and practice integration suites run; the test fixtures
handle this automatically via `IELTS_TEST_DATABASE_URL`.

Focused Phase 3 suites (all require the isolated test database):

```bash
python -m pytest tests/test_learning_application.py -q --strict-markers
python -m pytest tests/test_learning_concurrency.py -q --strict-markers
python -m pytest tests/test_learning_api.py -q --strict-markers
python -m pytest tests/test_phase3_consolidated.py -q --strict-markers
```

The learner APIs are:

```text
POST /learners
GET  /learners/{learner_id}/state
POST /learners/{learner_id}/writing/evaluations/{evaluation_id}/apply
```

No DeepSeek key is required: learner-state updates and planning are fully
deterministic and never call a provider.

## Phase 4 adaptive Writing practice commands

Phase 4 uses the same isolated PostgreSQL test database and deterministic
fakes. The complete Docker command above is the reproducibility check. Focused
practice coverage is available with:

```bash
python -m pytest tests/test_practice_generation.py -q --strict-markers
python -m pytest tests/test_practice_submission.py -q --strict-markers
python -m pytest tests/test_practice_concurrency.py -q --strict-markers
python -m pytest tests/test_phase4_consolidated.py -q --strict-markers
```

No DeepSeek key is required for these tests. Production generation uses the
configured DeepSeek key, while submission reuses the existing Writing evaluator.

## Windows Docker Desktop note

On the validated Docker Desktop 29.6.1 / Compose 5.3.0 environment, Compose/Bake
failed before Dockerfile execution when the checkout path contained non-ASCII
characters. If Docker reports a non-printable `x-docker-expose-session-sharedkey`
header, use an ASCII-only checkout path. The clean Compose workflow was verified
from an ASCII-only temporary checkout.
