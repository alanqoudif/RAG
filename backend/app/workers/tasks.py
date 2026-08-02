from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.tasks.ping")
def ping() -> str:
    """Smoke-test task used by health checks and Phase 1 validation."""
    return "pong"
