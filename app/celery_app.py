from celery import Celery
from celery.schedules import crontab
import os

# Create Celery app
celery = Celery(
    'easm',
    broker=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    include=[
        'app.tasks.discovery',
        'app.tasks.enrichment',
        'app.tasks.scanning',
        'app.tasks.alerting'
    ]
)

# Celery configuration
celery.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max per task
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,
    result_expires=3600,  # Results expire after 1 hour
)

# Celery Beat Schedule (for Sprint 1 - basic discovery)
celery.conf.beat_schedule = {
    'daily-full-discovery': {
        'task': 'app.tasks.discovery.run_full_discovery',
        'schedule': crontab(hour=2, minute=0),  # 2 AM daily
        'options': {'expires': 7200}  # Task expires after 2 hours
    },
    'critical-asset-watch': {
        'task': 'app.tasks.discovery.watch_critical_assets',
        'schedule': crontab(minute='*/30'),  # Every 30 minutes
        'options': {'expires': 1800}  # Task expires after 30 minutes
    },
}

if __name__ == '__main__':
    celery.start()
