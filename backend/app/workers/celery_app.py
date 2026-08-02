from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "text_to_sql_platform",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    worker_concurrency=settings.celery_concurrency,
    broker_connection_retry_on_startup=True,
)
