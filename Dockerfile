# Python base image
FROM python:3.12-slim

# System deps for psycopg2 and building wheels
RUN apt-get update \
     && apt-get install -y --no-install-recommends \
         build-essential \
         libpq-dev \
         curl \
     && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Improve Python behavior in containers
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Install Python dependencies first (leverages Docker layer caching)
COPY requirements.txt ./
# Optional Neo4j requirements (if present)
COPY requirements-neo4j.txt ./
RUN python -m pip install --upgrade pip \
    && pip install -r requirements.txt \
    && if [ -f requirements-neo4j.txt ]; then pip install -r requirements-neo4j.txt; fi

# Copy the rest of the project
COPY . .

# Environment defaults (override in compose or env)
ENV DJANGO_DEBUG=1 \
    DJANGO_SECRET_KEY=dev-insecure-secret-key \
    DJANGO_ALLOWED_HOSTS=*

# Expose Django dev server port
EXPOSE 8000

# Default command runs Django dev server (SQLite by default)
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
