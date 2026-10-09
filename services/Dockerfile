FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY services/requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir uv==0.12.17 \
    && uv pip install --system --no-cache -r /tmp/requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "services.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "/app/backend", "--reload-dir", "/app/services", "--reload-dir", "/app/packages"]