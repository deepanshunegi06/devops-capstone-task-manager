# syntax=docker/dockerfile:1.7
# ---------- Stage 1: build wheels (has compilers, never shipped) ----------
FROM python:3.12-slim AS builder
WORKDIR /build
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
COPY requirements.txt .
RUN pip wheel --wheel-dir /wheels -r requirements.txt

# ---------- Stage 2: minimal runtime ----------
FROM python:3.12-slim AS runtime
ARG APP_VERSION=2.0.0
ARG GIT_COMMIT=unknown
LABEL org.opencontainers.image.title="taskmanager" \
      org.opencontainers.image.description="Orbit Task Manager - DevOps capstone (ENSP461)" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.revision="${GIT_COMMIT}" \
      org.opencontainers.image.source="https://github.com/deepanshunegi06/devops-capstone-task-manager"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_VERSION=${APP_VERSION} \
    PORT=5000

# Security: patch OS packages, run as an unprivileged user with a fixed UID.
RUN apt-get update && apt-get upgrade -y && apt-get clean && rm -rf /var/lib/apt/lists/* \
 && groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --home-dir /app --shell /usr/sbin/nologin app

WORKDIR /app
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels /wheels/*.whl && rm -rf /wheels

COPY --chown=app:app taskmanager ./taskmanager
COPY --chown=app:app wsgi.py gunicorn.conf.py ./

USER 10001
EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import os,sys,urllib.request; u='http://127.0.0.1:%s/health/live' % os.environ.get('PORT','5000'); sys.exit(0 if urllib.request.urlopen(u, timeout=2).status == 200 else 1)"

CMD ["gunicorn", "--config", "gunicorn.conf.py", "wsgi:app"]
