# Workflow Design

The workflows live in `n8n/workflows` and are imported by `scripts/import-n8n-workflows.ps1`. The smoke test imports and activates them before running E2E checks.

## Workflow Inventory

| File | ID | Purpose |
|---|---|---|
| `01-incident-intake-analysis.json` | `wf-01-incident-intake-analysis` | Create/dedupe incident, analyze, route by severity |
| `02-critical-incident-approval.json` | `wf-02-critical-incident-approval` | Register approval, Wait, resume after backend approval |
| `03-work-order-api-rpa-fallback.json` | `wf-03-work-order-api-rpa-fallback` | Try MES API, fallback to RPA on technical failure |
| `04-sla-escalation-monitor.json` | `wf-04-sla-escalation-monitor` | Scan overdue work orders and notify once per level |
| `05-incident-closure-knowledge.json` | `wf-05-incident-closure-knowledge` | Generate closure knowledge case |
| `99-global-error-handler.json` | `wf-99-global-error-handler` | Record sanitized workflow errors |

## Import And Activation

```powershell
docker compose up -d postgres backend n8n
.\scripts\import-n8n-workflows.ps1
docker compose exec -T n8n n8n update:workflow --id=wf-01-incident-intake-analysis --active=true
docker compose exec -T n8n n8n update:workflow --id=wf-02-critical-incident-approval --active=true
docker compose exec -T n8n n8n update:workflow --id=wf-03-work-order-api-rpa-fallback --active=true
docker compose exec -T n8n n8n update:workflow --id=wf-04-sla-escalation-monitor --active=true
docker compose exec -T n8n n8n update:workflow --id=wf-05-incident-closure-knowledge --active=true
docker compose exec -T n8n n8n update:workflow --id=wf-99-global-error-handler --active=true
docker compose restart n8n
```

`update:workflow` is deprecated but verified with local n8n `2.29.10`. If a future version removes it, use the n8n UI to activate each workflow and restart the container.

## Webhooks

```text
POST http://localhost:5678/webhook/wf-01-incident-intake-analysis/webhook%2520-%2520incident%2520intake/incident-intake-analysis
POST http://localhost:5678/webhook/wf-02-critical-incident-approval/webhook%2520-%2520start%2520p1%2520approval/critical-incident-approval
POST http://localhost:5678/webhook/wf-03-work-order-api-rpa-fallback/webhook%2520-%2520create%2520external%2520work%2520order/work-order-api-rpa-fallback
POST http://localhost:5678/webhook/wf-05-incident-closure-knowledge/webhook%2520-%2520close%2520incident/incident-closure-knowledge
POST http://localhost:5678/webhook/wf-99-global-error-handler/webhook%2520-%2520test%2520error%2520ingest/global-error-handler-test
```

The `%2520` encoding is intentional for these local URLs.

## 01 Incident Intake And Analysis

Inputs:

- `equipment_code`
- `incident_type`
- `title`
- `description`
- `severity`
- optional `production_batch_no`

Flow:

1. Calls backend `POST /api/incidents`.
2. Stops on duplicate and records a workflow event.
3. Calls `POST /api/incidents/{id}/analyze`.
4. Uses backend final severity, not n8n code rules.
5. Creates approval for P1 or work order for P2-P4.
6. Records notifications and workflow events.

## 02 Critical Incident Approval

Flow:

1. Registers a protected backend approval with the n8n resume URL.
2. Waits in n8n.
3. Frontend or PowerShell calls backend approve/reject endpoint.
4. Backend updates approval once and resumes n8n.
5. Duplicate approval returns conflict and does not resume twice.

Normal frontend APIs do not return `resume_url`.

## 03 Work Order API With RPA Fallback

Error classification:

- MES API 2xx: save external work order ID.
- MES API 4xx: record business error; do not call RPA.
- MES API 5xx, timeout, or connection error: call backend RPA path.
- RPA failure: persist failure status and error; do not invent an external ID.

## 04 SLA Escalation Monitor

The workflow calls backend SLA scan. Backend owns idempotency so the same escalation level produces at most one notification per work order.

## 05 Incident Closure And Knowledge

Creates a template knowledge case when no model key is configured. This keeps final closure testable offline.

## 99 Global Error Handler

Accepts workflow error details, redacts secrets, and records a `WORKFLOW_ERROR` event plus administrator notification.
