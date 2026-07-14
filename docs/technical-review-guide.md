# Technical Review Guide

Use this guide when walking through the project in an interview or code review.

## Review Path

1. Start with `README.md` and the architecture diagram.
2. Open `docker-compose.yml` to show the six services and health checks.
3. Open `backend/src/factory_hub/services/core.py` for dedupe, state, SLA, and seed behavior.
4. Open `backend/src/factory_hub/agent/` for schemas, adapter, demo analyzer, safety filtering, and rule engine.
5. Open `n8n/workflows/` and `docs/workflow-design.md` for orchestration boundaries.
6. Open `rpa-worker/rpa_worker/runner.py` for Playwright browser automation.
7. Open `frontend/src/lib/api.ts` and pages to show public API usage.
8. Run `scripts/smoke-test.ps1` for full closure evidence.

## Design Questions And Answers

Why not let the LLM decide final severity?

- The analyzer can suggest risk, but P1/P2 decisions and approval requirements are deterministic because they affect operations and escalation.

Why n8n?

- n8n is used for long-running orchestration, Wait-based approval, workflow retries, and cross-service glue. It does not own domain invariants.

Why RPA?

- Many legacy MES systems have partial or unreliable APIs. The demo uses RPA only when the API has a technical failure and keeps screenshots and logs for audit.

Why not Redis, Kafka, Kubernetes, or Celery?

- The local demo requirements are satisfied with FastAPI, PostgreSQL, n8n, and Compose. Adding more infrastructure would increase operational risk without improving the interview objective.

How is idempotency handled?

- Incident dedupe uses stable keys and time windows.
- Approval decisions are single-use.
- SLA escalation is once per level.
- Smoke test can be rerun and creates unique incident types per run.

How are secrets protected?

- `.env` is ignored.
- Internal APIs require `X-Internal-Token`.
- Public responses do not include n8n `resume_url`.
- Logging and workflow error storage redact sensitive patterns.

## Useful Commands

```powershell
docker compose config
docker compose up -d --build
docker compose ps
docker compose exec -T backend alembic current
docker compose exec -T backend python -m pytest -q
docker compose exec -T legacy-mes python -m pytest -q /app/legacy-mes/tests
docker compose exec -T rpa-worker python -m pytest -q /app/rpa-worker/tests
cd frontend
npm.cmd run lint
npm.cmd test -- --run
npm.cmd run build
cd ..
powershell -ExecutionPolicy Bypass -File .\scripts\smoke-test.ps1
```

## Known Tradeoffs

- n8n activation command is version-sensitive.
- CI intentionally avoids full Docker+n8n E2E because it is heavier and more environment-sensitive.
- Local demo auth is not enterprise-grade.
- The simulated MES exists for controlled RPA proof, not as a production MES replacement.
