"""Gunicorn settings (overridable via env vars)."""
import os

bind = f"0.0.0.0:{os.environ.get('PORT', '5000')}"
workers = int(os.environ.get("GUNICORN_WORKERS", "2"))
threads = int(os.environ.get("GUNICORN_THREADS", "4"))
timeout = 30
graceful_timeout = 20
accesslog = None          # the app emits structured JSON request logs itself
errorlog = "-"
# RAM-backed heartbeat dir avoids stalls on slow disks (Linux containers); skipped where absent.
if os.path.isdir("/dev/shm"):
    worker_tmp_dir = "/dev/shm"
