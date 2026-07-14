# Stage 5 MES and RPA

## Services

- `legacy-mes`: FastAPI service on host port `8300`; provides HTML login, work order list, new work order, detail pages, and a simulated MES API.
- `rpa-worker`: FastAPI service on host port `8200`; uses Playwright Chromium to operate `legacy-mes` through the browser.
- `backend`: calls `rpa-worker` through `POST /internal/rpa/work-orders`, records RPA runs, updates internal work orders, and serves screenshots through `GET /api/rpa-runs/{id}/screenshot`.

## Legacy MES Failure Modes

Failure mode is controlled by a protected local demo endpoint:

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8300/internal/failure-mode -Headers @{ "X-Internal-Token" = "change-me-in-local-env" } -ContentType "application/json" -Body (@{ mode = "normal" } | ConvertTo-Json)
```

Allowed modes:

- `normal`: API creates a MES work order.
- `unavailable`: API returns 503.
- `timeout`: API delays beyond normal workflow timeout.
- `validation_error`: API returns 422 and must not trigger RPA.

## RPA Verification

Direct RPA call:

```powershell
$body = @{
  work_order_id = 999
  incident_no = "INC-RPA-DEMO"
  equipment_code = "CNC-01"
  title = "RPA demo work order"
  priority = "P2"
  description = "Created by Playwright RPA"
  assigned_team = "maintenance"
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri http://localhost:8200/internal/rpa/work-orders -Headers @{ "X-Internal-Token" = "change-me-in-local-env" } -ContentType "application/json" -Body $body
```

The worker returns `external_id`, `steps`, and `screenshot_path`. Screenshots are stored in the `rpa_artifacts` Docker volume and are read through backend, not by exposing arbitrary host paths.

## n8n 03 Branch Rules

- MES API `2xx`: save external id with `creation_method=API`.
- MES API `4xx`: record `MES_BUSINESS_ERROR`; do not call RPA.
- MES API `5xx`, connection error, or timeout: call RPA; on success update the work order with `creation_method=RPA`, external id, RPA run, and screenshot path.
