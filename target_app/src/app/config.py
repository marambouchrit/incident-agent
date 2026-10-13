import os


def _int(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


def _float(name: str, default: float) -> float:
    return float(os.environ.get(name, default))


def _bool(name: str, default: bool) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


APP_VERSION = os.environ.get("APP_VERSION", "dev")
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql+psycopg://shopline:shopline@db:5432/shopline")
DB_POOL_SIZE = _int("DB_POOL_SIZE", 10)
DB_MAX_OVERFLOW = _int("DB_MAX_OVERFLOW", 5)
DB_POOL_TIMEOUT_S = _float("DB_POOL_TIMEOUT_S", 10)

SLOW_REQUEST_MS = _int("SLOW_REQUEST_MS", 400)
CATALOG_CACHE_TTL_S = _int("CATALOG_CACHE_TTL_S", 30)
FEATURE_DISCOUNTS = _bool("FEATURE_DISCOUNTS", False)

PAYMENTS_URL = os.environ.get("PAYMENTS_URL", "http://payments:8080")
PAYMENTS_TIMEOUT_S = _float("PAYMENTS_TIMEOUT_S", 3)
PAYMENTS_RETRIES = _int("PAYMENTS_RETRIES", 2)

WORKER_CONCURRENCY = _int("WORKER_CONCURRENCY", 2)
WORKER_POLL_INTERVAL_S = _float("WORKER_POLL_INTERVAL_S", 1)
WORKER_BATCH_SIZE = _int("WORKER_BATCH_SIZE", 10)
EXPORT_CHUNK_ROWS = _int("EXPORT_CHUNK_ROWS", 2000)
EXPORT_INTERVAL_S = _int("EXPORT_INTERVAL_S", 600)
RECONCILE_INTERVAL_S = _int("RECONCILE_INTERVAL_S", 300)
