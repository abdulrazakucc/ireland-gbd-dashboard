FROM python:3.12-slim

WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/
COPY etl/ etl/
COPY data/ data/
COPY static/ static/

# Seed the database at build time so the container is ready to serve
# immediately. Re-run etl/load_seed.py (or mount a fresh gbd.db) to refresh.
RUN python etl/load_seed.py

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
