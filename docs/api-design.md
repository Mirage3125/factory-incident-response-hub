# API Design

Base URL: `http://localhost:8100`

OpenAPI: `http://localhost:8100/docs`

## Health

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Process liveness |
| GET | `/ready` | Database readiness |

## Public Business APIs

Equipment:

- `GET /api/equipment`
- `GET /api/equipment/{id}`
- `GET /api/equipment/{id}/maintenance-records`

Incidents:

- `POST /api/incidents`
- `GET /api/incidents`
- `GET /api/incidents/{id}`
- `GET /api/incidents/{id}/timeline`
- `GET /api/incidents/{id}/analysis-runs`
- `POST /api/incidents/{id}/analyze`
- `PATCH /api/incidents/{id}/status`

Work orders:

- `POST /api/work-orders`
- `GET /api/work-orders`
- `GET /api/work-orders/{id}`
- `PATCH /api/work-orders/{id}/status`
- `POST /api/work-orders/{id}/assign`
- `POST /api/work-orders/{id}/resolve`

Approvals:

- `GET /api/approvals/pending`
- `POST /api/approvals/{id}/approve`
- `POST /api/approvals/{id}/reject`

Dashboard:

- `GET /api/dashboard/summary`
- `GET /api/dashboard/severity-distribution`
- `GET /api/dashboard/recent-incidents`
- `GET /api/dashboard/sla-metrics`

Demo and RPA views:

- `GET /api/demo/scenarios`
- `POST /api/demo/scenarios/{scenario_code}/trigger`
- `POST /api/demo/rpa-fallback`
- `GET /api/rpa-runs`
- `GET /api/rpa-runs/{id}`
- `GET /api/rpa-runs/{id}/screenshot`

## Internal APIs

Internal APIs require:

```text
X-Internal-Token: <INTERNAL_SERVICE_TOKEN>
```

Paths:

- `POST /api/internal/agent/analyze`
- `POST /api/internal/agent/close-case`
- `POST /api/internal/workflow-events`
- `POST /api/internal/notifications`
- `POST /api/internal/work-orders/create`
- `POST /api/internal/approvals/register`
- `POST /api/internal/rpa-runs`
- `POST /api/internal/errors`
- `POST /api/internal/sla/escalations/scan`

## Important Contracts

Incident creation:

- Returns `duplicate=false` for a new incident.
- Returns `duplicate=true` and the original incident for a deduped incident.
- Deduped incidents do not create a second work order.

Analysis:

- Agent output is stored as structured JSON.
- Final severity and `requires_human_approval` come from deterministic rules.
- P1 rule hits cannot be downgraded by the agent.

Approvals:

- Public approval responses do not expose `resume_url`.
- A pending approval can be decided once.
- Duplicate approval attempts return conflict.
- Backend proxies n8n resume.

RPA:

- Backend calls RPA Worker with internal token.
- Successful RPA stores `creation_method=RPA`, external ID, run log, and screenshot path.
- Failed RPA stores failure details and no fake external ID.

## Example PowerShell

Create an incident:

```powershell
$body = @{
  equipment_code = "VISION-01"
  incident_type = "manual-vision-demo"
  title = "Manual vision defect demo"
  description = "defect_rate=7.5 percent"
  severity = "P3"
  production_batch_no = "BATCH-20260714-001"
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri http://localhost:8100/api/incidents -ContentType "application/json" -Body $body
```

Analyze it:

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8100/api/incidents/1/analyze
```

Approve a pending P1:

```powershell
Invoke-RestMethod http://localhost:8100/api/approvals/pending
Invoke-RestMethod -Method Post -Uri http://localhost:8100/api/approvals/1/approve -ContentType "application/json" -Body (@{ approver = "demo-manager"; comment = "approved" } | ConvertTo-Json)
```
