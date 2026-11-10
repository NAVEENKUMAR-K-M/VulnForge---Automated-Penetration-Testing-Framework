"""
Celery application for VulnForge.

The worker runs scans (and, in later phases, writeup ingestion) outside the
request/response cycle.  The broker and result backend both point at the
existing Redis instance via the computed properties already defined on
``Settings`` (``celery_broker_url`` / ``celery_result_backend``).

The worker is a separate process from the FastAPI app, so it does NOT share
the request-scoped async engine.  Tasks create their own short-lived async
engine inside their event loop (see ``scan_tasks._execute_scan``) — this keeps
asyncpg connections bound to the loop that uses them.
"""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "vulnforge",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.scan_tasks", "app.tasks.ingestion_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_soft_time_limit=settings.celery_task_soft_time_limit,
    task_time_limit=settings.celery_task_time_limit,
    worker_concurrency=settings.celery_worker_concurrency,
    worker_max_tasks_per_child=50,
    result_expires=86400,
)

# Beat schedule. The ingestion task self-gates on ``rag_ingest_enabled`` so this
# entry is inert until an operator turns ingestion on.
celery_app.conf.beat_schedule = {
    "ingest-writeups-daily": {
        "task": "vulnforge.ingest_writeups",
        "schedule": crontab(hour=3, minute=0),  # 03:00 UTC daily
    },
}
