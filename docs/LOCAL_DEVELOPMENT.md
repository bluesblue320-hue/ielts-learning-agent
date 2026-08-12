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
