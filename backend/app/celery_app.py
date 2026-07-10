"""Celery app for async tasks — crawling, batch vectorization, cleanup.

Only used when CELERY_BROKER_URL is configured (production / staging).
In dev mode (SQLite + no broker), tasks run synchronously via always_eager.
"""
from celery import Celery

from app.config import settings

_broker = getattr(settings, "celery_broker_url", "") or "redis://localhost:6379/1"

app = Celery(
    "guessr",
    broker=_broker,
    backend=_broker,
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_always_eager=settings.database_url.startswith("sqlite"),
    broker_connection_retry_on_startup=True,
)

# Auto-discover tasks in app/tasks/
app.autodiscover_tasks(["app.tasks"], force=True)
