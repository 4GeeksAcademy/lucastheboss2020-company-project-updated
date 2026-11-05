"""Standalone Celery application for TrackFlow background workers."""

import os
from urllib.parse import urlparse

from celery import Celery

redis_url = os.environ.get("REDIS_URL", "").strip()
parsed_url = urlparse(redis_url)
if parsed_url.scheme not in {"redis", "rediss"} or not parsed_url.hostname:
    raise RuntimeError("REDIS_URL must be configured with a valid Redis connection URL.")

soft_time_limit = int(os.environ.get("CELERY_TASK_SOFT_TIME_LIMIT", "540"))
time_limit = int(os.environ.get("CELERY_TASK_TIME_LIMIT", "600"))
visibility_timeout = int(os.environ.get("CELERY_VISIBILITY_TIMEOUT", "3600"))
if not 0 < soft_time_limit < time_limit < visibility_timeout:
    raise RuntimeError(
        "Celery limits must satisfy 0 < soft time limit < time limit < visibility timeout."
    )

app = Celery(
    "trackflow",
    broker=redis_url,
    backend=redis_url,
    include=["services.tasks"],
)
app.conf.update(
    accept_content=["json"],
    task_serializer="json",
    result_serializer="json",
    task_default_queue="reporting",
    task_track_started=True,
    task_acks_late=True,
    task_soft_time_limit=soft_time_limit,
    task_time_limit=time_limit,
    worker_concurrency=1,
    worker_prefetch_multiplier=1,
    worker_send_task_events=True,
    task_send_sent_event=True,
    broker_connection_timeout=5,
    broker_connection_retry_on_startup=True,
    broker_transport_options={
        "visibility_timeout": visibility_timeout,
        "socket_connect_timeout": 5,
        "socket_timeout": 5,
    },
    result_backend_transport_options={
        "visibility_timeout": visibility_timeout,
    },
    redis_socket_connect_timeout=5,
    redis_socket_timeout=5,
    visibility_timeout=visibility_timeout,
    result_expires=86400,
    enable_utc=True,
    timezone="UTC",
    worker_log_format="%(asctime)s [%(levelname)s] %(processName)s: %(message)s",
    worker_task_log_format=(
        "%(asctime)s [%(levelname)s] %(task_name)s[%(task_id)s]: %(message)s"
    ),
)