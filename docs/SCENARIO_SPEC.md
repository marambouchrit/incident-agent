# Scenario Specification

> Read by Claude Code before generating or reviewing any scenario (`/new-scenario`, `/review-scenario`).
> Goal: realistic, solvable incidents where **the symptom and the cause live in different places**, with noise and red herrings, and **no giveaways**.

---

## 1. How a scenario is produced

```
target_app (healthy)  →  inject fault  →  traffic generator runs  →  capture  →  reset
                                                                        │
                                       scenarios/<id>/  +  ground_truth/<id>.json
```

- **Target app:** a small FastAPI service set (`api`, `worker`) + PostgreSQL in Docker Compose. Endpoints like `/checkout`, `/orders`, `/products`, `/users`. Structured JSON logs to stdout. A traffic generator produces steady, realistic load (mixed endpoints, some 4xx from bad client input).
- **Target app git history:** the app lives in its own git repo, *separate from this project repo*, seeded with ~10 realistic commits (features, refactors, dependency bumps, docs) by `target_app/seed_history.sh`. Each scenario adds its own commits on top: 1 culprit + 1–4 unrelated ones.
- **Fault scripts:** `faults/<fault>/inject.sh` and `faults/<fault>/reset.sh`. Reset must bring the app back to the healthy baseline. Fault script names may be descriptive. They never ship into `scenarios/`.
- **Capture:** `capture/capture.sh <id> <fault>` freezes the state ~N minutes after injection into `scenarios/<id>/` and writes `ground_truth/<id>.json`.

## 2. Scenario folder format (what the agent can see)

```
scenarios/s07/
├── incident.txt            # the symptom, as a user/on-call would report it
├── logs/
│   ├── api.jsonl           # one JSON object per line
│   ├── worker.jsonl
│   └── db.log              # postgres log (plain text is fine)
├── git/
│   ├── commits.jsonl       # {hash, author, date, message, files[]}, newest first, ≥ 8 commits
│   └── diffs/<hash>.patch  # unified diff per commit
├── config/                 # .env-style and/or YAML files as deployed (secrets replaced by "***")
├── db/schema.sql           # pg_dump --schema-only at capture time (tables, columns, indexes)
└── containers.json         # [{service, state, restarts, exit_code, oom_killed, mem_limit_mb, started_at}]
```

Rules:
- **Folder IDs are neutral:** `s01`, `s02`, … Never the fault name.
- **Log line schema:** `{"ts": ISO-8601 UTC, "level": "INFO|WARNING|ERROR|CRITICAL", "service", "logger", "msg", "request_id"?, "path"?, "status"?, "latency_ms"?, "exc"?}`.
- **Time window:** ~30–60 min of logs; the fault starts somewhere in the middle (healthy period before it, so "when did it start?" is answerable).
- **Volume:** 1,500–10,000 log lines per service, so the agent must filter rather than read everything.
- **Timestamps must line up:** culprit commit / deploy / config change happens shortly *before* the first error. Unrelated commits are spread across the window too.

### `incident.txt` style
1–4 sentences, as written by an on-call engineer or a customer-facing team. It gives the **symptom, approximate time and impact only**.
> "Since around 09:14 UTC customers report checkout failures (HTTP 500). Orders page still works. Started without any announced maintenance."

Never mention the cause, a guess at the cause, or the component that broke (unless it's the symptom itself).

## 3. Ground truth format (what the agent can NEVER see)

`ground_truth/s07.json`:
```json
{
  "id": "s07",
  "fault": "missing_migration",
  "category": "missing_migration",
  "key_detail": "column orders.discount_code referenced by commit a1b2c3d but never added to the DB",
  "key_detail_aliases": ["discount_code", "orders.discount_code"],
  "culprit_commit": "a1b2c3d",
  "culprit_file": "app/models/order.py",
  "first_error_ts": "2026-10-10T09:14:03Z",
  "symptom_location": "logs/api.jsonl",
  "cause_location": ["git/diffs/a1b2c3d.patch", "db/schema.sql"],
  "difficulty": "medium",
  "red_herrings": ["worker WARNING about slow S3 retry since 08:50", "dependency bump commit at 09:05"],
  "split": "dev",
  "expected_fix": "add and run the migration adding orders.discount_code (nullable)",
  "notes": "free text for humans"
}
```
- `category` ∈ `missing_migration, bad_config, resource_exhaustion, performance_regression, code_bug, dependency_failure, infra_crash, unknown` (same list as the agent's report).
- `split` ∈ `dev | holdout`, assigned when the scenario is created (~60/40 overall). Don't change it later.

## 4. Difficulty levels

| Level | Definition | Red herrings |
|---|---|---|
| **easy** | One hop: the error message points at the right *area*, and one tool call to the right place confirms the cause. | 0–1 |
| **medium** | Two hops: the symptom is in one source (e.g. API logs) and the cause in another (diff, config, schema). There are some plausible distractions. | ≥ 1 |
| **hard** | Needs combining ≥ 2 sources plus timing reasoning. The cause may be inside an innocent-sounding commit, or the loudest error is a consequence, not the cause. | ≥ 2, including one *plausible* error-level one |

## 5. Noise and red herrings

**Always present (all scenarios):**
- Normal INFO traffic, periodic health checks, some 4xx from bad client input.
- Harmless WARNINGs that exist in the healthy period too (deprecation notice, slow-ish request, retry that succeeds).

**Red herring ideas (medium/hard):**
- An unrelated commit deployed just before the incident (dependency bump, logging refactor, docs).
- A WARNING/ERROR that started at a different time than the incident, or that also appears in the healthy period.
- A container restart that happened *before* the incident window and is unrelated.
- A config change to a different service.
- Downstream errors (worker can't read orders) that are a *consequence* of the real cause.

## 6. Giveaway checklist (must all pass)

- [ ] No commit message reveals the fault ("remove index", "oops", "break", "bug", "temporarily", "hack", "TODO fix pool").
  Realistic messages describe the *intent*: "Add discount codes to checkout", "Tune DB settings for staging parity", "Clean up order queries".
- [ ] No code comments in diffs that hint at the problem.
- [ ] No file, folder, branch, container or log-logger names that mention the fault.
- [ ] `incident.txt` describes only symptoms, time and impact.
- [ ] Nothing in `scenarios/<id>/` mentions `ground_truth`, `fault`, `inject`, `scenario`, or the fault name.
- [ ] The cause is **not** in the same file as the first visible symptom.
- [ ] Log messages are what the real library would print (real psycopg/SQLAlchemy/uvicorn error formats), not invented explanations like "ERROR: pool too small".
- [ ] Solvable: a human can find the cause in < 10 minutes using only the folder, and the evidence exists verbatim in it.

## 7. Fault catalogue (starting set)

| Fault | Category | Typical symptom | Where the cause is |
|---|---|---|---|
| Missing migration | missing_migration | 500s with `UndefinedColumn` on one endpoint | diff adds a model field; `schema.sql` lacks it |
| Wrong env var | bad_config | connection refused / auth errors / feature misbehaving | config file value vs. previous commit of config |
| Connection pool exhaustion | resource_exhaustion | timeouts, `QueuePool limit … reached` under load | config pool size reduced, or a leak in a diff |
| Dropped index | performance_regression | latency spike, timeouts, no errors at first | `schema.sql` missing index; migration diff dropping it |
| OOM restart | infra_crash | intermittent 502/connection reset, gaps in logs | `containers.json` OOMKilled + restarts; mem limit / diff loading data in memory |
| *(later)* Upstream dependency down | dependency_failure | timeouts to external service | logs of the client + config of the URL |
| *(later)* Code bug in edge case | code_bug | 500s only for some inputs | diff with logic change |
| *(later)* Two co-occurring issues (hard) | — | one real cause + one loud harmless one | timing tells them apart |

Aim over the project: 15–20 scenarios, roughly 5 easy / 7 medium / 6 hard, red herrings in every medium/hard.
