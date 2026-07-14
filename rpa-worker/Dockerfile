FROM mcr.microsoft.com/playwright/python:v1.49.1-noble

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY rpa-worker/requirements.txt /app/requirements.txt
RUN pip install --timeout 120 --retries 5 --no-cache-dir -r /app/requirements.txt

COPY rpa-worker /app/rpa-worker
ENV PYTHONPATH=/app/rpa-worker

EXPOSE 8200

CMD ["uvicorn", "rpa_worker.app:app", "--host", "0.0.0.0", "--port", "8200"]
