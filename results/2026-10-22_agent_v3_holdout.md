# Results - 2026-10-22_agent_v3_holdout

## Per scenario

| id | diff | split | runs | correct | category | judge | evidence | not_id | steps | tokens | latency s | cost $ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| s02 | easy | holdout | 3 | 3/3 | 3/3 | 0 | 8/9 | 0 | 7.3 | 38,992 | 42.9 | 0.0000 |
| s04 | medium | holdout | 3 | 3/3 | 3/3 | 2 | 9/9 | 0 | 7.0 | 36,369 | 49.9 | 0.0000 |
| s07 | medium | holdout | 3 | 3/3 | 3/3 | 0 | 7/8 | 0 | 5.3 | 29,029 | 39.4 | 0.0000 |
| s10 | hard | holdout | 3 | 3/3 | 3/3 | 0 | 9/9 | 0 | 8.7 | 59,403 | 50.0 | 0.0000 |
| s12 | hard | holdout | 3 | 3/3 | 3/3 | 0 | 9/10 | 0 | 9.0 | 47,251 | 65.0 | 0.0000 |

## Aggregate

- Runs: 15 (5 scenarios)
- Correct (cause found): 15/15 (by difficulty: easy 3/3, medium 6/6, hard 6/6)
- Category match: 15/15
- Needs judge: 2
- Evidence precision: 42/45 (0.93)
- not_identified rate: 0.00
- Stop reasons: submitted 15
- Avg steps 7.5 | avg tokens 42,209 | avg latency 49.4 s | avg cost $0.0000

## Calibration (identified runs)

| confidence | n | avg confidence | accuracy |
|---|---|---|---|
| 0.8-1.0 | 15 | 0.97 | 1.00 |

## Quotes not seen in any tool output

- s02: `-PAYMENTS_URL=http://payments:8080
+PAYMENTS_URL=http://payments:8443`
- s07: `commit 4f40f29
Author: Lina Haddad
Date:   2026-10-16T19:01:00Z

    Add bulk pricing for multi-item`
- s12: `priority integer NOT NULL (absent from table jobs)`
