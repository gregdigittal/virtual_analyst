FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY apps ./apps
COPY shared ./shared
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir .

CMD ["uvicorn", "apps.api.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
