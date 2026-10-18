#!/usr/bin/env bash
# A short busy period on top of the steady load: the normal traffic mix plus shoppers
# opening their order history, both for the same number of seconds.
set -euo pipefail
export MSYS_NO_PATHCONV=1
BURST_S="${RUSH_SECONDS:-25}"

read -r -d '' BROWSE <<'PY' || true
import os, random, threading, time

import httpx

rps = float(os.environ["BROWSE_RPS"])
threads = int(os.environ["BROWSE_THREADS"])
stop = time.time() + float(os.environ["BROWSE_SECONDS"])
seed = int(os.environ["BROWSE_SEED"])
counts, lock = {}, threading.Lock()


def shopper(index):
    rng = random.Random(seed * 1000 + index)
    with httpx.Client(base_url=os.environ["API_URL"], timeout=15) as client:
        while True:
            time.sleep(rng.expovariate(rps / threads))
            if time.time() >= stop:
                return
            try:
                if rng.random() < 0.85:
                    response = client.get("/orders", params={"user_id": rng.randint(1, 2000)})
                else:
                    response = client.get(f"/orders/{rng.randint(1, 1_000_000)}")
                key = str(response.status_code)
            except httpx.HTTPError as exc:
                key = type(exc).__name__
            with lock:
                counts[key] = counts.get(key, 0) + 1


workers = [threading.Thread(target=shopper, args=(i,)) for i in range(threads)]
for worker in workers:
    worker.start()
for worker in workers:
    worker.join()
print(f"browse finished: {dict(sorted(counts.items()))}", flush=True)
PY

docker compose run --rm --no-deps \
    -e LOADGEN_MIX=all -e LOADGEN_THREADS="${RUSH_THREADS:-30}" -e LOADGEN_RPS="${RUSH_RPS:-12}" \
    -e LOADGEN_DURATION_S="$BURST_S" -e LOADGEN_SEED="$RANDOM" \
    loadgen python -m loadgen.run &
mixed=$!
docker compose run --rm --no-deps \
    -e BROWSE_THREADS="${BROWSE_THREADS:-40}" -e BROWSE_RPS="${BROWSE_RPS:-12}" \
    -e BROWSE_SECONDS="$BURST_S" -e BROWSE_SEED="$RANDOM" \
    loadgen python -c "$BROWSE" &
browse=$!
wait "$mixed"
wait "$browse"
