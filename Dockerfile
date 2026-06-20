FROM python:3.12-slim

# Keep Python lean and logs unbuffered so `docker logs` is live.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Local audit/cache data lives here (mount a volume over it).
RUN mkdir -p /data
VOLUME ["/data"]

# Run as non-root.
RUN useradd --create-home --uid 10001 trader && chown -R trader:trader /app /data
USER trader

ENTRYPOINT ["python", "-m", "app.main"]
