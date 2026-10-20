from celery import Celery
from celery.signals import worker_process_init

from app.core.config import settings


@worker_process_init.connect
def _setup_worker_logging(**kwargs):
    from app.core.log_handler import setup_log_handler
    setup_log_handler(settings.redis_url, source="worker")

celery_app = Celery(
    "openavisio",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.pipeline", "app.workers.scheduler", "app.workers.task_tracking", "app.workers.watchdog"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_hijack_root_logger=False,
)

# GPU stages share ONE model on ONE card. Four of them in parallel produced five
# ReadTimeouts out of nine documents (#152) — they go on their own queue, drained
# by a dedicated worker with --concurrency=1 (deploy/docker-compose.prod.yml).
# Cross-instance serialisation is Ollama's job (OLLAMA_NUM_PARALLEL=1), not ours.
celery_app.conf.task_routes = {
    "app.workers.pipeline.ocr_stage": {"queue": "gpu"},
    "app.workers.pipeline.extraction_stage": {"queue": "gpu"},
    "app.workers.pipeline.embedding_stage": {"queue": "gpu"},
    "app.workers.pipeline.intake_form_stage": {"queue": "gpu"},
}

# Celery Beat schedule
celery_app.conf.beat_schedule = {
    "embedding-scheduler": {
        "task": "app.workers.scheduler.embedding_scheduler",
        "schedule": 900,  # 15 minutes
    },
    "event-reminder-scheduler": {
        "task": "app.workers.scheduler.event_reminder_scheduler",
        "schedule": 3600,  # hourly
    },
    "retention-purge-scheduler": {
        "task": "app.workers.scheduler.retention_purge_scheduler",
        "schedule": 86400,  # daily
    },
    # A broken pipeline used to be invisible until a user complained (#115)
    "failed-document-watchdog": {
        "task": "app.workers.watchdog.failed_document_watchdog",
        "schedule": 3600,  # hourly
    },
}
