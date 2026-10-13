"""Steady synthetic traffic for load testing: python -m loadgen.run"""

import os
import random
import threading
import time

import httpx

API_URL = os.environ.get("API_URL", "http://api:8000")
RPS = float(os.environ.get("LOADGEN_RPS", "2.5"))
SEED = int(os.environ.get("LOADGEN_SEED", "7"))
THREADS = int(os.environ.get("LOADGEN_THREADS", "8"))
USERS = int(os.environ.get("LOADGEN_USERS", "2000"))
PRODUCTS = int(os.environ.get("LOADGEN_PRODUCTS", "500"))
MIX = os.environ.get("LOADGEN_MIX", "all")  # "all" or "checkout"
DURATION_S = float(os.environ.get("LOADGEN_DURATION_S", "0"))  # 0 = run until stopped
RUN_TAG = os.environ.get("LOADGEN_RUN_TAG", format(int(time.time()) % 0xFFFFFF, "x"))

CATEGORIES = ["books", "electronics", "home", "toys", "garden", "sports", "beauty", "grocery"]
TERMS = ["classic", "mini", "pro", "eco", "smart", "deluxe", "travel", "kit", "set", "light"]

counts: dict[str, int] = {}
lock = threading.Lock()


def one_request(client: httpx.Client, rng: random.Random) -> httpx.Response:
    roll = 0.70 if MIX == "checkout" else rng.random()
    if roll < 0.30:
        return client.get("/products", params={"category": rng.choice(CATEGORIES), "page": rng.randint(1, 3)})
    if roll < 0.45:
        return client.get(f"/products/{rng.randint(1, PRODUCTS)}")
    if roll < 0.60:
        return client.get("/orders", params={"user_id": rng.randint(1, USERS)})
    if roll < 0.65:
        return client.get(f"/orders/{rng.randint(1, 1_000_000)}")
    if roll < 0.80:
        items = [
            {"product_id": rng.randint(1, PRODUCTS), "quantity": rng.randint(1, 3)}
            for _ in range(rng.randint(1, 4))
        ]
        return client.post("/checkout", json={"user_id": rng.randint(1, USERS), "items": items})
    if roll < 0.88:
        return client.get(f"/users/{rng.randint(1, USERS)}")
    if roll < 0.90:
        n = rng.randint(1, 3000)
        return client.post("/users", json={"email": f"shopper{n}.{RUN_TAG}@example.com", "name": f"Shopper {n}"})
    if roll < 0.95:
        return client.get("/products/search", params={"q": rng.choice(TERMS)})
    # malformed client input
    bad = rng.choice(["missing_product", "missing_user", "empty_cart", "bad_quantity", "bad_email"])
    if bad == "missing_product":
        return client.get(f"/products/{PRODUCTS + rng.randint(1, 9000)}")
    if bad == "missing_user":
        return client.get(f"/users/{10_000_000 + rng.randint(1, 9000)}")
    if bad == "empty_cart":
        return client.post("/checkout", json={"user_id": rng.randint(1, USERS), "items": []})
    if bad == "bad_quantity":
        return client.post(
            "/checkout", json={"user_id": rng.randint(1, USERS), "items": [{"product_id": 1, "quantity": 0}]}
        )
    return client.post("/users", json={"email": "not-an-email", "name": "x"})


def worker(index: int) -> None:
    rng = random.Random(SEED * 1000 + index)
    with httpx.Client(base_url=API_URL, timeout=15) as client:
        while True:
            time.sleep(rng.expovariate(RPS / THREADS))
            try:
                key = str(one_request(client, rng).status_code)
            except httpx.HTTPError as exc:
                key = type(exc).__name__
            with lock:
                counts[key] = counts.get(key, 0) + 1


def main() -> None:
    for index in range(THREADS):
        threading.Thread(target=worker, args=(index,), daemon=True).start()
    if DURATION_S:
        time.sleep(DURATION_S)
        print(f"loadgen finished after {DURATION_S:g}s: {dict(sorted(counts.items()))}", flush=True)
        return
    while True:
        time.sleep(60)
        with lock:
            snapshot = dict(sorted(counts.items()))
            counts.clear()
        print(f"loadgen last 60s: {snapshot}", flush=True)


if __name__ == "__main__":
    main()
