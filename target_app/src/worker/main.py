import importlib
import logging
import pkgutil
import time
import warnings
from concurrent.futures import ThreadPoolExecutor
from types import ModuleType
from typing import Any

from sqlalchemy import text

from app import config
from app.db import SessionLocal
from app.logging_setup import configure
from worker import handlers

log = logging.getLogger("worker.jobs")
MAX_ATTEMPTS = 3

CLAIM_SQL = text(
    """
    UPDATE jobs SET status = 'running', attempts = attempts + 1
    WHERE id IN (
        SELECT id FROM jobs
        WHERE status = 'pending' AND run_at <= now()
        ORDER BY id LIMIT :batch
        FOR UPDATE SKIP LOCKED
    )
    RETURNING id, kind, payload, attempts
    """
)


def discover() -> dict[str, ModuleType]:
    found = {}
    for module in pkgutil.iter_modules(handlers.__path__):
        loaded = importlib.import_module(f"worker.handlers.{module.name}")
        found[loaded.KIND] = loaded
    return found


def requeue_interrupted() -> None:
    with SessionLocal() as session:
        result = session.execute(text("UPDATE jobs SET status = 'pending' WHERE status = 'running'"))
        session.commit()
    if result.rowcount:
        log.warning("requeued interrupted jobs", extra={"count": result.rowcount})


def schedule_periodic(registry: dict[str, ModuleType], last_run: dict[str, float]) -> None:
    now = time.monotonic()
    for kind, module in registry.items():
        interval = getattr(module, "INTERVAL_S", None)
        if interval is None or now - last_run.setdefault(kind, now) < interval:
            continue
        last_run[kind] = now
        with SessionLocal() as session:
            session.execute(
                text(
                    "INSERT INTO jobs (kind, payload, status, attempts) "
                    "SELECT CAST(:kind AS varchar), '{}'::jsonb, 'pending', 0 WHERE NOT EXISTS "
                    "(SELECT 1 FROM jobs WHERE kind = CAST(:kind AS varchar) AND status IN ('pending', 'running'))"
                ),
                {"kind": kind},
            )
            session.commit()


def claim() -> list[tuple[int, str, dict[str, Any], int]]:
    with SessionLocal() as session:
        rows = session.execute(CLAIM_SQL, {"batch": config.WORKER_BATCH_SIZE}).all()
        session.commit()
    return [tuple(row) for row in rows]


def run_job(registry: dict[str, ModuleType], job: tuple[int, str, dict[str, Any], int]) -> None:
    job_id, kind, payload, attempts = job
    fields = {"job_id": job_id, "kind": kind}
    started = time.perf_counter()
    log.info("job started", extra=fields)
    try:
        with SessionLocal() as session:
            registry[kind].handle(session, payload)
            session.execute(
                text("UPDATE jobs SET status = 'done', finished_at = now() WHERE id = :id"), {"id": job_id}
            )
            session.commit()
        log.info("job finished", extra=fields | {"duration_ms": round((time.perf_counter() - started) * 1000)})
    except Exception:
        log.exception("job failed", extra=fields | {"attempt": attempts})
        status = "failed" if attempts >= MAX_ATTEMPTS else "pending"
        with SessionLocal() as session:
            session.execute(
                text("UPDATE jobs SET status = :status, run_at = now() + interval '30 seconds' WHERE id = :id"),
                {"status": status, "id": job_id},
            )
            session.commit()


def main() -> None:
    configure("worker")
    log.info("service started", extra={"version": config.APP_VERSION})
    warnings.warn(
        "jobs payload format v1 is deprecated and will be removed in shopline 2.0", DeprecationWarning, stacklevel=1
    )
    registry = discover()
    requeue_interrupted()
    last_run: dict[str, float] = {}
    with ThreadPoolExecutor(max_workers=config.WORKER_CONCURRENCY) as pool:
        while True:
            schedule_periodic(registry, last_run)
            jobs = claim()
            if not jobs:
                time.sleep(config.WORKER_POLL_INTERVAL_S)
                continue
            list(pool.map(lambda job: run_job(registry, job), jobs))


if __name__ == "__main__":
    main()
