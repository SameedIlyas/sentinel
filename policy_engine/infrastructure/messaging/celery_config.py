"""Celery application configuration for background tasks."""

try:
    from celery import Celery
    from policy_engine.config import settings

    celery_app = Celery("sentinel", broker=settings.REDIS_URL, backend=settings.REDIS_URL)
    celery_app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
    )
except ImportError:
    # Celery is an optional dependency; define a stub so imports don't break.
    import logging
    logging.getLogger(__name__).warning(
        "celery not installed — background task processing unavailable. "
        "Install with: pip install celery"
    )

    class _CeleryStub:
        """Stub object returned when Celery is not installed."""
        def task(self, *args, **kwargs):
            def decorator(fn):
                return fn
            return decorator

    celery_app = _CeleryStub()  # type: ignore[assignment]
