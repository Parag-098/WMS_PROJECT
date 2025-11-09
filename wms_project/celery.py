"""
Celery configuration for wms_project.

Optional: Use this when scaling beyond Django-Q.
Requires: celery, redis

To use Celery instead of Django-Q:
1. Install: pip install celery redis
2. Set CELERY_BROKER_URL in settings or environment
3. Run worker: celery -A wms_project worker -l info
4. Run beat (for scheduled tasks): celery -A wms_project beat -l info

For development, Django-Q is simpler and sufficient.
"""
from __future__ import absolute_import, unicode_literals
import os
from celery import Celery

# Set default Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "wms_project.settings")

app = Celery("wms_project")

# Load config from Django settings with CELERY_ prefix
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    """Debug task to test Celery configuration."""
    print(f'Request: {self.request!r}')
