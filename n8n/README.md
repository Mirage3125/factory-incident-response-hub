# n8n Workflows

## Configuration

Copy `.env.example` to `.env` and change the example values before a real demo:

- `N8N_ENCRYPTION_KEY`: local demo encryption key, 32+ characters.
- `N8N_BASIC_AUTH_USER` / `N8N_BASIC_AUTH_PASSWORD`: local n8n UI protection.
- `INTERNAL_SERVICE_TOKEN`: shared token used by n8n when calling backend internal APIs.
- `N8N_WEBHOOK_URL`: default local value is `http://localhost:5678/`.

The Compose setup uses the existing PostgreSQL container with a separate `n8n` database created by `postgres-init`. Business tables stay in `factory_incidents`.

## Start n8n

```powershell
docker compose up -d postgres backend n8n
docker compose ps
docker compose exec -T n8n n8n --version
```

Open `http://localhost:5678` and sign in with the local Basic Auth values from `.env`.

## Import and activate

```powershell
.\scripts\import-n8n-workflows.ps1
```

The script imports all files in `n8n/workflows`:

- `01-incident-intake-analysis.json`
- `02-critical-incident-approval.json`
- `03-work-order-api-rpa-fallback.json`
- `04-sla-escalation-monitor.json`
- `05-incident-closure-knowledge.json`
- `99-global-error-handler.json`

The validated local n8n version is `2.29.10`. Imported workflows are not active by default. Activate each imported workflow by ID, then restart n8n so webhook registrations are refreshed:

```powershell
docker compose exec -T n8n n8n list:workflow
docker compose exec -T n8n n8n update:workflow --id=wf-01-incident-intake-analysis --active=true
docker compose exec -T n8n n8n update:workflow --id=wf-02-critical-incident-approval --active=true
docker compose exec -T n8n n8n update:workflow --id=wf-03-work-order-api-rpa-fallback --active=true
docker compose exec -T n8n n8n update:workflow --id=wf-04-sla-escalation-monitor --active=true
docker compose exec -T n8n n8n update:workflow --id=wf-05-incident-closure-knowledge --active=true
docker compose exec -T n8n n8n update:workflow --id=wf-99-global-error-handler --active=true
docker compose restart n8n
```

`update:workflow` is deprecated in n8n 2.29.10 but was the command verified in this project. If a future n8n version removes it, open each workflow in the UI, review the HTTP nodes, and toggle Active. Set `99 - Global Error Handler` as the error workflow in n8n workflow settings for the other workflows.

## Webhook URLs

Default local webhook URLs after activation on n8n 2.29.10:

```text
POST http://localhost:5678/webhook/wf-01-incident-intake-analysis/webhook%2520-%2520incident%2520intake/incident-intake-analysis
POST http://localhost:5678/webhook/wf-02-critical-incident-approval/webhook%2520-%2520start%2520p1%2520approval/critical-incident-approval
POST http://localhost:5678/webhook/wf-03-work-order-api-rpa-fallback/webhook%2520-%2520create%2520external%2520work%2520order/work-order-api-rpa-fallback
POST http://localhost:5678/webhook/wf-05-incident-closure-knowledge/webhook%2520-%2520close%2520incident/incident-closure-knowledge
POST http://localhost:5678/webhook/wf-99-global-error-handler/webhook%2520-%2520test%2520error%2520ingest/global-error-handler-test
```

The `%2520` segments are intentional for PowerShell/browser calls. n8n stores the webhook node names with encoded spaces, and HTTP clients must send the `%` characters encoded.

## Verification

Validation commands:

```powershell
docker compose config
docker compose up -d --build postgres backend legacy-mes rpa-worker n8n
docker compose ps
docker compose exec -T backend python -m pytest -q
docker compose exec -T n8n n8n --version
.\scripts\import-n8n-workflows.ps1
```

Demo incident through workflow 01:

```powershell
$body = @{
  equipment_code = "CNC-01"
  incident_type = "stage4-n8n-vibration"
  title = "n8n demo spindle vibration"
  description = "vibration=9.8 mm/s"
  severity = "P3"
  production_batch_no = "BATCH-20260714-001"
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri "http://localhost:5678/webhook/wf-01-incident-intake-analysis/webhook%2520-%2520incident%2520intake/incident-intake-analysis" -ContentType "application/json" -Body $body
```

Approval verification without frontend:

```powershell
Invoke-RestMethod http://localhost:8100/api/approvals/pending
Invoke-RestMethod -Method Post -Uri http://localhost:8100/api/approvals/1/approve -ContentType "application/json" -Body (@{ approver = "ops-manager"; comment = "approved from PowerShell" } | ConvertTo-Json)
```

Global error handler test webhook:

```powershell
$errorBody = @{
  workflow_name = "manual-stage4-test"
  error_message = "token=super-secret resume_url=http://n8n/webhook-waiting/private"
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri "http://localhost:5678/webhook/wf-99-global-error-handler/webhook%2520-%2520test%2520error%2520ingest/global-error-handler-test" -ContentType "application/json" -Body $errorBody
```

Stage 5 RPA fallback uses the real `legacy-mes` and `rpa-worker` services:

- MES API `2xx`: workflow 03 saves the MES external work order id through backend.
- MES API `4xx`: workflow 03 records a business error and does not call RPA.
- MES API `5xx`, connection error, or timeout: workflow 03 calls backend, which calls `rpa-worker`; the worker uses Playwright to operate the MES web pages and returns the external id and screenshot path.

Control the local MES failure mode with the protected demo endpoint:

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8300/internal/failure-mode -Headers @{ "X-Internal-Token" = "change-me-in-local-env" } -ContentType "application/json" -Body (@{ mode = "unavailable" } | ConvertTo-Json)
```
