FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml /app/pyproject.toml
COPY alembic.ini /app/alembic.ini

RUN python -c "import tomllib; data=tomllib.load(open('pyproject.toml','rb')); deps=data['project']['dependencies'] + data['project']['optional-dependencies']['test']; open('/tmp/requirements.txt','w').write('\n'.join(deps))" \
    && pip install --timeout 120 --retries 5 --no-cache-dir -r /tmp/requirements.txt

COPY backend /app/backend

RUN pip install --no-deps --no-build-isolation -e "."

FROM base AS test

CMD ["pytest", "-q"]

FROM base AS runtime

EXPOSE 8100

RUN chmod +x /app/backend/scripts/start.sh

HEALTHCHECK --interval=10s --timeout=3s --retries=5 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8100/health', timeout=2).read()"

CMD ["/app/backend/scripts/start.sh"]
