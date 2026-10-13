# Target App Brief

> Input for generating `target_app/`, `capture/` and `faults/`. Follows `docs/SCENARIO_SPEC.md`; where the two disagree, the spec wins.
> Status: **approved 2026-10-13.** §8 filled and §9 decided.

## 1. Purpose
A small online-shop backend ("shopline") that is boring when healthy and has enough moving parts (services, config knobs, tables, deploy steps) to host 15–20 different faults whose cause and symptom sit in different places.

## 2. Services (Docker Compose)

| Service | What it does | Memory limit |
|---|---|---|
| `api` | FastAPI + SQLAlchemy 2 (sync, psycopg 3), served by uvicorn | 512 MB |
| `worker` | Polls the `jobs` table: order confirmation, stock reconciliation, daily sales export | 256 MB |
| `db` | PostgreSQL 16 | 1 GB |
| `payments` | Tiny stub of an external payment provider, called by `/checkout` over HTTP | 64 MB |
| `loadgen` | Traffic generator. Not captured into scenarios | none |

## 3. API endpoints
`GET /products` (paged, by category) · `GET /products/{id}` · `GET /products/search?q=` · `POST /users` · `GET /users/{id}` · `GET /orders?user_id=` · `GET /orders/{id}` · `POST /checkout` · `GET /healthz`

`/checkout` is the multi-step one: validate cart → reserve inventory → call `payments` → insert order + items → enqueue a job for the worker.

## 4. Database
- **Tables:** `users`, `products`, `inventory`, `orders`, `order_items`, `payments`, `jobs`, `alembic_version`.
- **Indexes (beyond PKs):** `users(email)` unique, `products(category)`, `orders(user_id)`, `orders(created_at)`, `order_items(order_id)`, `jobs(status, run_at)`.
- **Seed data:** ~2,000 users, ~500 products, and enough orders (start at ~1.5M, tune) that `GET /orders?user_id=` goes from a few ms to several hundred ms without its index.
- **Migrations:** Alembic, applied by an explicit `alembic upgrade head` step in `deploy.sh`. The app does **not** migrate on startup, so code and schema can drift apart.

## 5. Configuration (captured into `config/`)

| File | Knobs |
|---|---|
| `api.env` | `DATABASE_URL`, `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT_S`, `SLOW_REQUEST_MS`, `PAYMENTS_URL`, `PAYMENTS_TIMEOUT_S`, `PAYMENTS_RETRIES`, `FEATURE_DISCOUNTS`, `CATALOG_CACHE_TTL_S`, `LOG_LEVEL` |
| `worker.env` | `DATABASE_URL`, `DB_POOL_SIZE`, `WORKER_CONCURRENCY`, `WORKER_POLL_INTERVAL_S`, `WORKER_BATCH_SIZE`, `EXPORT_CHUNK_ROWS`, `EXPORT_INTERVAL_S`, `RECONCILE_INTERVAL_S`, `LOG_LEVEL` |
| `postgres.conf` | `max_connections`, `statement_timeout`, `shared_buffers`, `log_min_duration_statement` |
| `docker-compose.yml` | images, memory limits, restart policy, healthchecks |

Config files are tracked in the target app's git repo, so a config change is also a commit with a diff. Secrets are written as `***`.

## 6. Logs and deploys
- Line schema as in the spec §2. Loggers: `app.access` (one line per request), `app.checkout`, `app.orders`, `app.payments_client`, `sqlalchemy.pool`, `worker.jobs`, `worker.export`.
- Errors carry the real library exception text in `exc` (psycopg, SQLAlchemy, httpx, uvicorn). No invented explanations.
- Every service logs one startup line with its version: `"msg": "service started", "version": "<short hash>"`. `deploy.sh <service>` rebuilds, optionally migrates, restarts. This makes "what was deployed when" answerable from logs + commits.
- **Healthy-period noise:** health check every 30 s; ~5% of requests are 4xx from bad client input; a deprecation WARNING at worker startup; a slow-request WARNING on `/checkout` a few times per hour (the payment stub is occasionally slow); a payment retry that succeeds on ~1% of checkouts.

## 7. Traffic and git history
- **Traffic:** ~2–3 requests/s with a fixed random seed. Mix: 45% products, 20% orders, 15% checkout, 10% users, 5% search, 5% malformed. A 40-minute window gives roughly 5,000–7,000 `api` lines, inside the spec's 1,500–10,000.
- **Seed history** (`seed_history.sh`, 3 fictional authors, dates spread over the previous 3 weeks):
  1. Initial project skeleton and Compose setup
  2. Add products and users endpoints
  3. Add orders and checkout flow with payments client
  4. Add request logging middleware and request ids
  5. Add worker and jobs queue
  6. Add payment provider stub for local runs
  7. Bump SQLAlchemy and psycopg versions
  8. Add product search endpoint
  9. Add sales export job
  10. Add load test script, update README and deploy notes

  Each scenario then adds 1 culprit + 1–4 unrelated commits on top, with intent-describing messages.

## 8. Fault map for Day 1

Worked out with Maram on 2026-10-13.

| Scenario | Fault | Difficulty | Cause lives in | Symptom first shows in |
|---|---|---|---|---|
| s01 | Missing migration | easy | Commit diff adds `orders.discount_code` to the model; `db/schema.sql` does not have the column | `logs/api.jsonl`: `/checkout` returns 500 with `UndefinedColumn` |
| s02 | Wrong env var | easy | `config/api.env`: `PAYMENTS_URL` points to a port nothing listens on (and the commit that edited it) | `logs/api.jsonl`: connection errors on `/checkout` only; every other endpoint is fine |
| s03 | OOM restart | easy | Commit diff makes the sales export load all rows at once, ignoring `EXPORT_CHUNK_ROWS` | `containers.json`: `worker` has `oom_killed: true` and several restarts. `logs/worker.jsonl`: jobs stop mid-task, repeated startup lines, backlog grows |
| s04 | Connection pool exhaustion | medium | `config/api.env`: `DB_POOL_SIZE` reduced, in a commit with an innocent message | `logs/api.jsonl`: `QueuePool limit … reached` timeouts, starting only once traffic is busy, not at deploy time |
| s05 | Dropped index | medium | Migration diff drops the `orders(user_id)` index; `db/schema.sql` no longer lists it | `logs/api.jsonl`: `GET /orders?user_id=` still returns 200 but `latency_ms` is very high; no errors |

Notes:
- s04: the log names the mechanism (pool exhausted) but not the root cause (who shrank the pool, and when). Red herring: an unrelated logging-refactor commit deployed close to the same time.
- s05: nothing to find by searching for errors; the evidence is a number. Red herring to be chosen in the `/new-scenario` design step.

## 9. Decisions (agreed 2026-10-13)
1. **`payments` stub:** built now, so the capture layout does not change later.
2. **Capture time:** 35-minute windows, fault at about minute 18, run sequentially in the background (about 3 hours for five).
3. **Difficulty assignment:** as in §8 (three easy, two medium).

## 10. Out of scope
Auth, a frontend, real payment logic, metrics/tracing, Kubernetes, more than one database.
