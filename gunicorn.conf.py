"""Gunicorn settings (overridable via env vars)."""
import os
import sys

bind = f"0.0.0.0:{os.environ.get('PORT', '5000')}"
workers = int(os.environ.get("GUNICORN_WORKERS", "2"))
threads = int(os.environ.get("GUNICORN_THREADS", "4"))
timeout = 30
# Build the app (and run create_all / demo seeding) once in the master, not in every worker,
# so several workers never race to create the schema on first start. Linux only: on macOS,
# forking after OpenSSL is initialised crashes workers (Objective-C fork-safety).
preload_app = os.environ.get("GUNICORN_PRELOAD", "1" if sys.platform.startswith("linux") else "0") == "1"
graceful_timeout = 20
accesslog = None          # the app emits structured JSON request logs itself
errorlog = "-"
# RAM-backed heartbeat dir avoids stalls on slow disks (Linux containers); skipped where absent.
if os.path.isdir("/dev/shm"):
    worker_tmp_dir = "/dev/shm"
