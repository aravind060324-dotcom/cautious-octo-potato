# FastAPI API image. Bake a pre-built Parquet catalog into the image.
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CATALOG_PATH=data/processed/restaurants.parquet

COPY requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt

COPY app/ app/
COPY scripts/ scripts/
COPY data/processed/restaurants.parquet data/processed/restaurants.parquet

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
