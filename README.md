# Incident Investigation Agent

An autonomous, read-only LLM agent that does **root cause analysis** on a production incident.
It gets an incident report, forms hypotheses, chooses its own tools (logs, commits and diffs,
config, DB schema, container status), and ends with a structured report: cause, verbatim
evidence, confidence and a suggested fix. It **proposes** fixes and never applies them.

**Result (v1.0, 11 recorded incidents × 3 runs):** right cause in **29/33** runs, right
category in **28/33**, 90 % of evidence quotes found verbatim in what the agent actually read.
Free model (`gemini-3.5-flash-lite`), $0. Details: [results/2026-10-22_v1.0.md](results/2026-10-22_v1.0.md).

> Learning project (final-year AI/LLM engineering), built in ~2 weeks. Raw tool-calling loop,
> no LangChain/LangGraph, on purpose: every limit, retry and stop condition is visible code.

---

## The problem

When a service breaks, an on-call engineer reads logs, looks at what was deployed, checks the
config and the database, and connects the dots. Most of that time goes into *looking*, not
*fixing*. This agent does the looking: it must find the change that started the incident,
quote the lines that prove it, and say how sure it is. It must also avoid the easy wrong
answer, such as the last commit before the errors, or a loud error that is only a symptom.

## Why this is an agent, not a workflow

A workflow runs the same steps every time ("read logs → read last commit → answer"). Here the
code only gives the model 7 tools and a 15-step budget. **The model picks the next tool from
what the last result showed**, so each incident gets a different investigation. Real v1.0
trajectories:

```
s01  log_stats → list_commits → show_commit → get_db_schema(orders)               → missing_migration
s04  log_stats → list_commits → show_commit → get_container_status → read_config(api.env) → resource_exhaustion
s03  log_stats ×2 → get_container_status → list_commits → show_commit → read_config(docker-compose.yml) → search_logs ×2 → infra_crash
s08  log_stats ×2, search_logs ×5, show_commit ×2, get_db_schema ×3… (15 steps)    → performance_regression
```

All four start the same way (*when* did errors start?), then split. In s01 the diff adds a
column, so the agent checks the schema. In s04 the errors are pool timeouts, so it reads the
pool config. In s03 the worker restarts, so it reads the container state. Nobody wrote "if pool
timeout then read config". The proof is in the trajectories: the order and the choice of tools
change with the evidence, and the agent stops when it has enough (6 steps in s01; in s08 one run
hit the 15-step limit and got a forced report).

## Architecture

```
 scenarios/<id>/  (frozen snapshot of one incident)
   incident.txt  logs/  git/  config/  db/  containers.json
        │
        ▼
 ┌─────────────────────── agent/loop.py ─────────────────────────┐
 │  system prompt + incident                                       │
 │      │                                                          │
 │      ▼                                                          │
 │   LLM ──► tool call ──► tools/ (read-only, confined, capped) ──┐│
 │    ▲                                                           ││
 │    └──────────────── result (data, not instructions) ◄─────────┘│
 │                                                                 │
 │  stops on: submit_report · 15 steps (forced report) · LLM error │
 └──────────────────────────────┬──────────────────────────────────┘
                                ▼
                 trajectory JSON (every thought, call, result, report)
                     │                                   │
                     ▼                                   ▼
        eval/  vs. ground_truth/<id>.json         ui/  trajectory viewer
        (agent never sees ground_truth/)          (static, no backend)
```

## Tools

| Tool | What it returns | Use it when… |
|---|---|---|
| `log_stats` | counts per level, p95 latency and top errors per time bucket | you need **when** errors started, before reading raw lines |
| `search_logs` | exact log lines, filtered by service, level, keyword, time | you need evidence lines |
| `list_commits` | hash, time, author, message, files changed | you want to know what changed around the incident |
| `show_commit` | the diff of one commit | you suspect a specific change |
| `read_config` | one config file (or the list of files) | env vars, pool sizes, timeouts |
| `get_db_schema` | tables, columns, indexes | you suspect a migration, index or schema mismatch |
| `get_container_status` | state, restarts, exit code, OOM-killed, memory limit | crashes, restart loops, resource issues |
| `submit_report` | *(terminal)* category, summary, evidence quotes, confidence, fix | ends the investigation |

`submit_report` is a tool, not free text: the report shape is enforced by a schema, and calling
it is the clean stop condition. An invalid report gets one retry with the validation error.

## Safety design

- **Read-only.** No tool writes, executes or calls the network. Fixes are text in the report.
- **Confined.** Every path is resolved inside the current `scenarios/<id>/` folder. Absolute
  paths, `..` and symlinks pointing outside are rejected ([agent/tools/guards.py](agent/tools/guards.py)).
- **Bounded.** Max 15 steps (then a forced final report), 10 s timeout per tool, output capped
  at 100 lines with a "narrow your query" footer. A repeated identical call is not run again: the agent gets a
  short reminder of the earlier result and a nudge to try another angle.
- **Tool outputs are data.** Logs can contain text that looks like instructions; the system
  prompt says to treat it as evidence only.
- **No answer leaks.** The agent can only read the scenario folder. Scenario IDs are neutral
  (`s01`…), and a test fails if the system prompt contains giveaway words.

## Evaluation

- **Scenarios.** 11 incidents recorded from a real FastAPI + PostgreSQL app in Docker Compose,
  each with an injected fault and decoys (an innocent commit just before the errors, a loud
  symptom, a look-alike of an earlier scenario). Split: 6 dev / 5 holdout.
- **Ground truth** per scenario: guilty commit, key detail, category, accepted fixes, decoys.
- **Metrics** ([eval/metrics.py](eval/metrics.py)): cause found (guilty commit + key detail
  named), category match, evidence precision (each quote must appear verbatim in a tool result
  the agent received in that run), confidence vs. accuracy.
- **3 runs per scenario**, because the model's output varies between runs.

| Split | Runs | Cause found | Category | Evidence |
|---|---|---|---|---|
| dev (tuned on) | 18 | 14/18 | 13/18 | 51/58 |
| holdout | 15 | 15/15 | 15/15 | 42/45 |
| **total** | **33** | **29/33** | **28/33** | **93/103 (0.90)** |

The holdout was read before the last tuning round, so it is no longer blind. The last blind
holdout measure (prompt v2) is **cause 15/15, category 11/15**.

## Where it fails

- **Anchoring (s08).** The agent finds and quotes the commit that lowered the DB
  `statement_timeout` (30 s → 250 ms), and still names the older slow-query commit as the
  main cause. It sees the evidence but doesn't weigh the timing.
- **Overconfidence.** Average confidence 0.96 for 78 % accuracy on dev; all wrong runs are at
  0.9–1.0. A written confidence scale in the prompt barely moved it.
- **Ambiguous scenario (s06).** An external payment provider runs as a container in the same
  compose file, so the agent labels it `infra_crash` instead of `dependency_failure`.

All limits with numbers: [results/2026-10-22_v1.0.md#known-limits](results/2026-10-22_v1.0.md#known-limits).

## What I'd do next

- **Compute confidence in code**, from the checks the agent actually did (compared timing,
  read the state, ruled out an alternative with a quote), instead of asking the model.
- **Run on a public benchmark** (e.g. RCAEval) and a fresh, never-read holdout, to measure
  generalisation beyond 11 incidents I designed myself.
- **Add a one-shot baseline** (all snapshot data in one prompt) to measure what the loop adds
  per token spent.

## Run it

Requires Python 3.11+, Node 18+ and a free Gemini API key ([Google AI Studio](https://aistudio.google.com/)).
Docker is **not** needed: the agent reads the recorded snapshots in `scenarios/`.

```bash
git clone https://github.com/marambouchrit/incident-agent.git
cd incident-agent
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt     # macOS/Linux: .venv/bin/python
cp .env.example .env                                         # then set LLM_API_KEY
.venv/Scripts/python -m pytest -q                            # no API key needed
```

**Run the agent on one incident** (about 1–4 min on the free tier):

```bash
.venv/Scripts/python -m agent.run s01
```

It prints each step and the report, and saves the full trajectory as JSON in `runs/`.

**Open the trajectory viewer** (the 33 v1.0 runs are shipped in `ui/public/data/`):

```bash
cd ui
npm install
npm run dev          # open the printed http://localhost:5173
```

**Full evaluation** (11 × 3 runs, ~2 h, fits one day of free quota):

```bash
.venv/Scripts/python -m eval.run_all --runs 3
```

## Repository layout

```
agent/         loop, LLM wrapper, prompts, tools (+ guards)
eval/          metrics, report tables, N × K runner
scenarios/     what the agent can see (one folder per incident)
ground_truth/  what the agent can never see
results/       eval tables, v1.0 results and limits
ui/            trajectory viewer (Vite + React + TypeScript + Tailwind)
target_app/  faults/  capture/   the app, fault kits and scripts used to record scenarios
tests/         pytest (a few tests skip in a fresh clone: they read the git-ignored runs/)
```
