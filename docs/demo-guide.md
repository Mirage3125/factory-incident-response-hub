# Demo Guide

This guide assumes the stack is running locally and workflows are imported and active.

## Start

```powershell
Copy-Item .env.example .env
docker compose up -d --build
docker compose exec -T backend alembic upgrade head
docker compose exec -T backend python -m factory_hub.seed
.\scripts\import-n8n-workflows.ps1
docker compose exec -T n8n n8n update:workflow --id=wf-01-incident-intake-analysis --active=true
docker compose exec -T n8n n8n update:workflow --id=wf-02-critical-incident-approval --active=true
docker compose exec -T n8n n8n update:workflow --id=wf-03-work-order-api-rpa-fallback --active=true
docker compose exec -T n8n n8n update:workflow --id=wf-04-sla-escalation-monitor --active=true
docker compose exec -T n8n n8n update:workflow --id=wf-05-incident-closure-knowledge --active=true
docker compose exec -T n8n n8n update:workflow --id=wf-99-global-error-handler --active=true
docker compose restart n8n
```

Open:

- Frontend: `http://localhost:3100`
- Backend docs: `http://localhost:8100/docs`
- n8n: `http://localhost:5678`
- Legacy MES: `http://localhost:8300/login`

## Recommended Interview Flow

1. Show Dashboard metrics.
2. Open Demo Scenarios.
3. Trigger Vision Defect P2.
4. Open the incident detail and show:
   - incident context
   - agent analysis
   - final rule severity P2
   - work order
   - workflow timeline
5. Trigger Duplicate Alarm.
6. Show the duplicate result increments occurrence count and does not create a second work order.
7. Trigger CNC Spindle Vibration P1.
8. Open Approval Center.
9. Approve the pending item and show n8n resume event.
10. Trigger MES API Failure and RPA Fallback.
11. Open RPA Runs and show steps, status, external MES ID, and screenshot.

## One-Command Validation

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\smoke-test.ps1
```

The smoke test validates:

- Compose config and service readiness.
- Backend `/health` and `/ready`.
- Frontend, n8n, and legacy MES access.
- P2 incident analysis and work order creation.
- Duplicate alarm idempotency.
- P1 pending approval and backend-driven n8n resume.
- MES API 503 to Playwright RPA fallback.
- External ID and screenshot persistence.
- Knowledge case generation on closure.
- SLA repeated scan idempotency.
- Global error redaction.
- Persistence across backend, n8n, and RPA Worker restarts.

## Demo URLs

| Page | URL |
|---|---|
| Dashboard | `http://localhost:3100/` |
| Incidents | `http://localhost:3100/incidents` |
| Approvals | `http://localhost:3100/approvals` |
| Work Orders | `http://localhost:3100/work-orders` |
| RPA Runs | `http://localhost:3100/rpa-runs` |
| Demo | `http://localhost:3100/demo` |

## What To Emphasize

- n8n orchestrates; backend owns business truth.
- Agent suggestions are audited, but deterministic rules decide high-risk outcomes.
- P1 requires human approval.
- RPA is a fallback for technical MES API failure only.
- Sensitive URLs and tokens are not exposed to the frontend.
- The smoke test proves the business loop instead of relying on static screenshots.

## Reset Notes

`docker compose down` stops containers but keeps data volumes. To delete all local demo data, use `docker compose down -v` only when that data loss is intentional.
