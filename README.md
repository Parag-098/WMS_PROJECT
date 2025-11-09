# WMS Project (wms_project)

Warehouse Management System scaffold built with Django. This repository includes an initial Django project (`wms_project`) and an app (`inventory`) with optional integrations for Postgres, Redis, Celery (worker & beat), and Neo4j via Docker Compose. The default local setup uses SQLite so you can get started quickly.

## Quick start (local, SQLite)

Prerequisites: Python 3.11+ recommended.

```powershell
# Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Initialize the Django project
python manage.py migrate
python manage.py createsuperuser  # optional
python manage.py runserver 0.0.0.0:8000
```

Then open http://127.0.0.1:8000/ in your browser.

## Project layout

- `wms_project/` – Django project (settings, URLs, WSGI/ASGI, Celery config)
- `inventory/` – App skeleton (models, views, admin, urls, templates, static)
- `requirements.txt` – Python dependencies
- `Dockerfile`, `docker-compose.yml` – Containerized dev stack (optional services)
- `.gitignore` – Standard Python/Django ignores

## Optional: Run with Docker Compose

This repo includes definitions for Postgres, Redis, Celery (worker & beat), and Neo4j. The web service defaults to SQLite for simplicity. To use Postgres, set the env vars below; otherwise, the Django app will continue using SQLite.

```powershell
# Build images (first time)
docker compose build

# Start only web using SQLite (no external DB required)
docker compose up web

# Start full stack (Postgres, Redis, Celery worker & beat, Neo4j)
docker compose up -d
```

### Environment variables (web)

- `DJANGO_DEBUG` (default: `1`)
- `DJANGO_SECRET_KEY` (default: a dev key)
- `DJANGO_ALLOWED_HOSTS` (e.g., `127.0.0.1,localhost`)
- For Postgres (switches DB from SQLite to Postgres if `POSTGRES_DB` is set):
  - `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`
- Celery
  - `CELERY_BROKER_URL` (default: `redis://redis:6379/0`)
  - `CELERY_RESULT_BACKEND` (default: `redis://redis:6379/1`)

### Common Docker commands

```powershell
# Create DB tables
docker compose exec web python manage.py migrate

# Create admin
docker compose exec web python manage.py createsuperuser

# Collect static (if/when configured)
docker compose exec web python manage.py collectstatic --noinput
```

## Docker vs local SQLite (when and why)

Use Docker (Postgres + Redis + Celery + Neo4j) when you need:

- Full-stack parity with CI/production (transactions, locks, background workers)
- Stable, reproducible dev environments across the team (no local deps install)
- Running background tasks (Celery) or graph features (Neo4j)
- Testing concurrency-sensitive paths that behave differently on SQLite

Use local SQLite when you want:

- Fast onboarding and quick prototyping without external services
- Running unit tests and iterating on Django views/serializers/templates
- Minimal resource usage on your laptop

How to switch:

- Local SQLite: set `DEBUG=1` and do not define `DATABASE_URL`/Postgres vars
- Docker Postgres: set `DATABASE_URL=postgresql://wms_user:wms_password@db:5432/wms_db` (already provided in compose) and run with `docker compose up -d`

## Notes

- SQLite by default: Lightweight for local dev; no extra services required.
- Postgres/Redis/Celery/Neo4j are optional and can be brought up when needed.
- `django-q` is included for teams that prefer Django Q; Celery is also wired.
- Adjust settings in `wms_project/settings.py` as needed for your environment.
