# Ireland Health Evidence -- UCC School of Public Health
#
# One image serves both the dashboard and the API on port 8000.
# Build and run it with:  make up

FROM python:3.12-slim

# PYTHONDONTWRITEBYTECODE: no .pyc clutter in the image.
# PYTHONUNBUFFERED:        logs appear immediately in `docker compose logs`.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    GBD_DB_PATH=/srv/data/gbd.db

WORKDIR /srv

# Dependencies first, in their own layer: this step is only re-run when
# requirements.txt changes, so ordinary code edits rebuild in seconds.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/
COPY etl/ etl/
COPY data/ data/
COPY static/ static/
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh

# Run as a non-root user. If the container is ever exposed beyond a trusted
# network, this limits what a process escape could reach.
RUN chmod +x /usr/local/bin/entrypoint.sh \
    && useradd --system --create-home --home-dir /home/app appuser \
    && chown -R appuser:appuser /srv
USER appuser

EXPOSE 8000

# Lets `docker compose ps` and any orchestrator report real readiness rather
# than merely "the process started".
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request as u, sys; \
sys.exit(0 if u.urlopen('http://127.0.0.1:8000/api/health', timeout=2).status == 200 else 1)"

# The entrypoint seeds the database on first start, then execs this command.
ENTRYPOINT ["entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
