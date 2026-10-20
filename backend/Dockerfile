FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/backend/requirements.txt
COPY ml /app/ml

# --default-timeout/--retries: large wheels (xgboost, pandas, shap, ...) can
# exceed pip's default per-read timeout on a slow or flaky connection,
# failing the whole build with a ReadTimeoutError. This matters here more
# than most Dockerfiles since this image is meant to be built on a client's
# home/office network, not just CI.
RUN pip install --no-cache-dir --default-timeout=180 --retries 10 -r /app/backend/requirements.txt \
    && pip install --no-cache-dir --default-timeout=180 --retries 10 -e /app/ml

COPY backend /app/backend
WORKDIR /app/backend

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD alembic upgrade head && python -m app.seed && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS:-10}
