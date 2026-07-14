FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY legacy-mes/requirements.txt /app/requirements.txt
RUN pip install --timeout 120 --retries 5 --no-cache-dir -r /app/requirements.txt

COPY legacy-mes /app/legacy-mes
ENV PYTHONPATH=/app/legacy-mes

EXPOSE 8300

CMD ["uvicorn", "legacy_mes.app:app", "--host", "0.0.0.0", "--port", "8300"]
