FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# The gitignored market datasets travel as a small compressed seed; the
# bootstrap restores them into /app/data/historical at start time. Fail the
# build if the seed is ever missing from the context.
COPY . .
RUN test -s data/seed/historical.tar.xz

EXPOSE 16901

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=5 \
  CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:16901/api/health', timeout=3).status == 200 else 1)"

CMD ["bash", "-lc", "bash scripts/preview_bootstrap.sh && exec python -m uvicorn server.main:app --host 0.0.0.0 --port 16901"]
