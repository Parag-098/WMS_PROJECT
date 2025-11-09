# Task Scheduling Guide

This document covers background task processing using **Django-Q** (default) and optional **Celery** (for advanced scaling).

---

## Django-Q Setup (Default)

Django-Q is a lightweight task queue for Django that uses your existing database or Redis.

### Installation

```bash
pip install django-q
```

### Configuration

Add to `INSTALLED_APPS` in `settings.py`:

```python
INSTALLED_APPS = [
    # ...
    'django_q',
]
```

Add Django-Q configuration:

```python
Q_CLUSTER = {
    'name': 'wms',
    'workers': 4,
    'recycle': 500,
    'timeout': 90,
    'compress': True,
    'save_limit': 250,
    'queue_limit': 500,
    'cpu_affinity': 1,
    'label': 'Django Q',
    'redis': {
        'host': '127.0.0.1',
        'port': 6379,
        'db': 0,
    }
}
```

### Running Django-Q Cluster

**Development (single command):**

```bash
python manage.py qcluster
```

**Production (supervisor):**

Create `/etc/supervisor/conf.d/wms_qcluster.conf`:

```ini
[program:wms_qcluster]
command=/path/to/venv/bin/python /path/to/wms_project/manage.py qcluster
directory=/path/to/wms_project
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/wms/qcluster.log
stderr_logfile=/var/log/wms/qcluster_error.log
environment=DJANGO_SETTINGS_MODULE="wms_project.settings"
```

Reload supervisor:

```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start wms_qcluster
```

---

## Scheduled Tasks

### Daily Expiry Scan

Automatically run daily to scan for expired/near-expiry batches:

**Django Shell:**

```python
from django_q.models import Schedule

Schedule.objects.create(
    func='inventory.tasks.scheduled_expiry_scan',
    schedule_type='D',  # Daily
    name='Daily Expiry Scan',
)
```

**Admin Interface:**

1. Go to Django Admin → Django-Q → Scheduled tasks
2. Add new schedule:
   - Func: `inventory.tasks.scheduled_expiry_scan`
   - Schedule Type: Daily
   - Name: Daily Expiry Scan

### Scheduled Reports

Generate daily inventory reports:

```python
Schedule.objects.create(
    func='inventory.tasks.generate_scheduled_report',
    schedule_type='D',
    name='Daily Inventory Report',
    kwargs='{"report_type": "inventory_snapshot"}'
)
```

### Bulk Import (Large Files)

Large file imports are automatically queued via Django-Q in the bulk import view when file size > 1MB.

Manual trigger:

```python
from django_q.tasks import async_task

async_task(
    'inventory.tasks.process_bulk_import',
    '/path/to/file.csv',
    'item',
    user_id=1
)
```

---

## Celery Setup (Optional - Advanced)

Use Celery for more complex workflows, task routing, and horizontal scaling.

### Installation

```bash
pip install celery redis
```

### Configuration

Add to `wms_project/__init__.py`:

```python
from __future__ import absolute_import, unicode_literals
from .celery import app as celery_app

__all__ = ('celery_app',)
```

Add to `settings.py`:

```python
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/1'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
```

### Running Celery

**Worker:**

```bash
celery -A wms_project worker -l info
```

**Beat (scheduled tasks):**

```bash
celery -A wms_project beat -l info
```

**Combined (development):**

```bash
celery -A wms_project worker -B -l info
```

**Supervisor config for Celery:**

`/etc/supervisor/conf.d/wms_celery_worker.conf`:

```ini
[program:wms_celery_worker]
command=/path/to/venv/bin/celery -A wms_project worker -l info
directory=/path/to/wms_project
user=www-data
numprocs=1
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/wms/celery_worker.log
```

`/etc/supervisor/conf.d/wms_celery_beat.conf`:

```ini
[program:wms_celery_beat]
command=/path/to/venv/bin/celery -A wms_project beat -l info
directory=/path/to/wms_project
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/wms/celery_beat.log
```

---

## Docker Compose

The provided `docker-compose.yml` includes services for:

- **Redis**: Task broker
- **celery_worker**: Celery worker (optional)
- **celery_beat**: Celery beat scheduler (optional)

To use Django-Q instead, disable Celery containers and run:

```bash
docker-compose up web redis
docker-compose exec web python manage.py qcluster
```

---

## Task Definitions

All background tasks are defined in `inventory/tasks.py`:

- `process_bulk_import(file_path, model_type, user_id)` - Process large file imports
- `scheduled_expiry_scan()` - Daily expiry check and notification
- `generate_scheduled_report(report_type)` - Generate scheduled reports

---

## Monitoring

### Django-Q Admin

View task history and failures in Django Admin → Django-Q → Completed tasks / Failed tasks

### Celery Flower (optional monitoring UI)

```bash
pip install flower
celery -A wms_project flower
```

Access at: http://localhost:5555

---

## Comparison: Django-Q vs Celery

| Feature | Django-Q | Celery |
|---------|----------|--------|
| Setup Complexity | Simple | Moderate |
| Dependencies | Django ORM or Redis | Redis/RabbitMQ |
| Admin Interface | Built-in | Requires Flower |
| Horizontal Scaling | Limited | Excellent |
| Task Routing | Basic | Advanced |
| Best For | Small-medium apps | Large-scale systems |

**Recommendation:** Start with Django-Q for simplicity. Migrate to Celery when you need advanced features or horizontal scaling.

---

## Troubleshooting

**Django-Q not processing tasks:**

1. Ensure qcluster is running: `python manage.py qcluster`
2. Check Redis connection in Q_CLUSTER config
3. Verify tasks are queued: Django Admin → Django-Q → Queued tasks

**Celery worker not starting:**

1. Check Redis connection: `redis-cli ping`
2. Verify CELERY_BROKER_URL in settings
3. Check worker logs for errors

**Tasks failing silently:**

1. Check Django-Q Failed tasks in admin
2. Enable debug logging in Q_CLUSTER config: `'catch_up': False`
3. Test task manually in Django shell
