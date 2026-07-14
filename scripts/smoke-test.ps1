param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [int]$TimeoutSeconds = 180,
    [string]$InternalToken = $env:INTERNAL_SERVICE_TOKEN
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($InternalToken)) {
    $InternalToken = "change-me-in-local-env"
}

$BackendUrl = "http://localhost:8100"
$FrontendUrl = "http://localhost:3100"
$N8nUrl = "http://localhost:5678"
$LegacyMesUrl = "http://localhost:8300"
$RpaWorkerUrl = "http://localhost:8200"

$Workflow01 = "$N8nUrl/webhook/wf-01-incident-intake-analysis/webhook%2520-%2520incident%2520intake/incident-intake-analysis"
$Workflow02 = "$N8nUrl/webhook/wf-02-critical-incident-approval/webhook%2520-%2520start%2520p1%2520approval/critical-incident-approval"
$Workflow03 = "$N8nUrl/webhook/wf-03-work-order-api-rpa-fallback/webhook%2520-%2520create%2520external%2520work%2520order/work-order-api-rpa-fallback"
$Workflow05 = "$N8nUrl/webhook/wf-05-incident-closure-knowledge/webhook%2520-%2520close%2520incident/incident-closure-knowledge"
$Workflow99 = "$N8nUrl/webhook/wf-99-global-error-handler/webhook%2520-%2520test%2520error%2520ingest/global-error-handler-test"

function Write-Step([string]$Message) {
    Write-Host "[SMOKE] $Message"
}

function ConvertTo-JsonBody($Value) {
    return $Value | ConvertTo-Json -Depth 30
}

function Assert-True([bool]$Condition, [string]$Message) {
    if (-not $Condition) {
        throw $Message
    }
}

function Invoke-Json([string]$Method, [string]$Uri, $Body = $null, [hashtable]$Headers = @{}, [int]$TimeoutSec = 30) {
    $params = @{
        Method      = $Method
        Uri         = $Uri
        TimeoutSec  = $TimeoutSec
        Headers     = $Headers
        ErrorAction = "Stop"
    }
    if ($null -ne $Body) {
        $params.ContentType = "application/json"
        $params.Body = ConvertTo-JsonBody $Body
    }
    return Invoke-RestMethod @params
}

function Wait-Until([string]$Name, [scriptblock]$Check, [int]$TimeoutSec = $TimeoutSeconds) {
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    $lastError = $null
    while ((Get-Date) -lt $deadline) {
        try {
            $result = & $Check
            if ($result) {
                Write-Step "$Name ready"
                return
            }
        }
        catch {
            $lastError = $_.Exception.Message
        }
        Start-Sleep -Seconds 2
    }
    throw "$Name did not become ready within $TimeoutSec seconds. Last error: $lastError"
}

function Invoke-Compose([string[]]$ComposeArgs) {
    Push-Location $ProjectRoot
    try {
        & docker compose @ComposeArgs
        if ($LASTEXITCODE -ne 0) {
            throw "docker compose $($ComposeArgs -join ' ') failed with exit code $LASTEXITCODE"
        }
    }
    finally {
        Pop-Location
    }
}

function Invoke-PostgresScalar([string]$Sql) {
    Push-Location $ProjectRoot
    try {
        $output = & docker compose exec -T postgres psql -U factory -d factory_incidents -t -A -c $Sql
        if ($LASTEXITCODE -ne 0) {
            throw "PostgreSQL query failed: $Sql"
        }
        return ($output | Select-Object -Last 1).Trim()
    }
    finally {
        Pop-Location
    }
}

function Invoke-N8nPostgresScalar([string]$Sql) {
    Push-Location $ProjectRoot
    try {
        $output = & docker compose exec -T postgres psql -U factory -d n8n -t -A -c $Sql
        if ($LASTEXITCODE -ne 0) {
            throw "n8n PostgreSQL query failed: $Sql"
        }
        return ($output | Select-Object -Last 1).Trim()
    }
    finally {
        Pop-Location
    }
}

function Activate-Workflows {
    $ids = @(
        "wf-01-incident-intake-analysis",
        "wf-02-critical-incident-approval",
        "wf-03-work-order-api-rpa-fallback",
        "wf-04-sla-escalation-monitor",
        "wf-05-incident-closure-knowledge",
        "wf-99-global-error-handler"
    )
    foreach ($id in $ids) {
        Invoke-Compose @("exec", "-T", "n8n", "n8n", "update:workflow", "--id=$id", "--active=true")
    }
}

function Import-Workflows {
    $script = Join-Path $ProjectRoot "scripts\import-n8n-workflows.ps1"
    & powershell -ExecutionPolicy Bypass -File $script -ProjectRoot $ProjectRoot
    if ($LASTEXITCODE -ne 0) {
        throw "n8n workflow import failed with exit code $LASTEXITCODE"
    }
}

function Get-WorkOrderCountForIncident([int]$IncidentId) {
    return [int](Invoke-PostgresScalar "select count(*) from work_orders where incident_id = $IncidentId;")
}

Push-Location $ProjectRoot
try {
    $RunId = "stage7-" + (Get-Date -Format "yyyyMMddHHmmss")
    Write-Step "Run id: $RunId"

    Write-Step "Validating Compose config"
    Invoke-Compose @("config")

    Write-Step "Starting all services"
    Invoke-Compose @("up", "-d", "postgres", "backend", "n8n", "legacy-mes", "rpa-worker", "frontend")

    Wait-Until "Backend" { (Invoke-Json "GET" "$BackendUrl/ready").status -eq "ready" }
    Wait-Until "Legacy MES" { (Invoke-Json "GET" "$LegacyMesUrl/ready").status -eq "ready" }
    Wait-Until "RPA Worker" { (Invoke-Json "GET" "$RpaWorkerUrl/ready").status -eq "ready" }
    Wait-Until "Frontend" { (Invoke-WebRequest "$FrontendUrl" -UseBasicParsing -TimeoutSec 10).StatusCode -eq 200 }
    Wait-Until "n8n" { (Invoke-WebRequest "$N8nUrl" -UseBasicParsing -TimeoutSec 10).StatusCode -eq 200 }
    Wait-Until "Legacy MES login" { (Invoke-WebRequest "$LegacyMesUrl/login" -UseBasicParsing -TimeoutSec 10).StatusCode -eq 200 }

    Write-Step "Importing n8n workflows"
    Import-Workflows

    Write-Step "Activating n8n workflows"
    Activate-Workflows
    Invoke-Compose @("restart", "n8n")
    Wait-Until "n8n after workflow activation" { (Invoke-WebRequest "$N8nUrl" -UseBasicParsing -TimeoutSec 10).StatusCode -eq 200 } 90

    Write-Step "Checking seed data"
    Assert-True ([int](Invoke-PostgresScalar "select count(*) from equipment;") -ge 5) "Expected at least 5 equipment rows"
    Assert-True ([int](Invoke-PostgresScalar "select count(*) from production_batches;") -ge 5) "Expected at least 5 production batches"

    Write-Step "Running P2 workflow through n8n 01"
    $p2Payload = @{
        equipment_code       = "VISION-01"
        incident_type        = "stage7_p2_$RunId"
        title                = "Stage 7 P2 vision defect"
        description          = "defect_rate=7.5 percent; smoke test $RunId"
        severity             = "P3"
        production_batch_no  = "BATCH-20260714-001"
    }
    $p2Response = Invoke-Json "POST" $Workflow01 $p2Payload @{} 45
    Assert-True ($p2Response.work_order_no -like "WO-*") "P2 workflow did not create a work order"
    Assert-True ($p2Response.priority -eq "P2") "P2 workflow did not produce P2 priority"
    $p2WorkOrderId = [int]$p2Response.id
    $p2IncidentId = [int]$p2Response.incident_id

    Write-Step "Verifying duplicate alert idempotency"
    $dupPayload = @{
        equipment_code       = "VISION-01"
        incident_type        = "stage7_duplicate_$RunId"
        title                = "Stage 7 duplicate alert"
        description          = "same alarm submitted twice"
        severity             = "P2"
        production_batch_no  = "BATCH-20260714-001"
    }
    $dup1 = Invoke-Json "POST" "$BackendUrl/api/incidents" $dupPayload
    $dup2 = Invoke-Json "POST" "$BackendUrl/api/incidents" $dupPayload
    Assert-True ($dup1.duplicate -eq $false) "First duplicate scenario call unexpectedly deduped"
    Assert-True ($dup2.duplicate -eq $true) "Second duplicate scenario call did not dedupe"
    Assert-True ($dup2.incident.occurrence_count -ge 2) "Duplicate occurrence count was not incremented"
    Assert-True ((Get-WorkOrderCountForIncident ([int]$dup2.incident.id)) -eq 0) "Duplicate scenario created an unexpected work order"

    Write-Step "Running P1 workflow and n8n approval resume"
    $p1Payload = @{
        equipment_code       = "CNC-01"
        incident_type        = "stage7_p1_$RunId"
        title                = "Stage 7 P1 spindle vibration"
        description          = "vibration=9.6 mm/s; smoke test $RunId"
        severity             = "P3"
        production_batch_no  = "BATCH-20260714-001"
    }
    $p1Response = Invoke-Json "POST" $Workflow01 $p1Payload @{} 45
    $p1IncidentId = [int](Invoke-PostgresScalar "select id from incidents where incident_type = 'stage7_p1_$RunId' order by id desc limit 1;")
    Assert-True ($p1IncidentId -gt 0) "P1 workflow did not return an incident id"
    $approvalStart = Invoke-Json "POST" $Workflow02 @{ incident_id = $p1IncidentId } @{} 45
    Assert-True ($null -ne $approvalStart) "P1 approval workflow did not start"
    Wait-Until "P1 pending approval" {
        $pending = Invoke-Json "GET" "$BackendUrl/api/approvals/pending"
        return @($pending | Where-Object { $_.incident_id -eq $p1IncidentId }).Count -gt 0
    } 60
    $approval = @(Invoke-Json "GET" "$BackendUrl/api/approvals/pending" | Where-Object { $_.incident_id -eq $p1IncidentId } | Select-Object -First 1)[0]
    $approved = Invoke-Json "POST" "$BackendUrl/api/approvals/$($approval.id)/approve" @{ approver = "stage7-smoke"; comment = "approved by smoke test" } @{} 45
    Assert-True ($approved.status -eq "APPROVED") "Approval did not return APPROVED"
    try {
        Invoke-Json "POST" "$BackendUrl/api/approvals/$($approval.id)/approve" @{ approver = "stage7-smoke"; comment = "duplicate approval" } @{} 10 | Out-Null
        throw "Duplicate approval unexpectedly succeeded"
    }
    catch {
        Assert-True ($_.Exception.Message -match "409|approval_already_decided") "Duplicate approval did not fail with an expected conflict"
    }
    Wait-Until "n8n approval resume event" {
        [int](Invoke-PostgresScalar "select count(*) from workflow_events where incident_id = $p1IncidentId and event_type = 'N8N_RESUMED';") -ge 1
    } 60

    Write-Step "Running MES API 503 to RPA through n8n 03"
    Invoke-Json "POST" "$LegacyMesUrl/internal/failure-mode" @{ mode = "unavailable" } @{ "X-Internal-Token" = $InternalToken } | Out-Null
    $rpaWorkOrder = Invoke-Json "POST" "$BackendUrl/api/work-orders" @{
        incident_id      = $p2IncidentId
        title            = "Stage 7 RPA fallback $RunId"
        description      = "MES API unavailable smoke test"
        priority         = "P2"
        assigned_team    = "maintenance"
        creation_method  = "API"
    }
    $rpaPayload = @{
        work_order_id   = $rpaWorkOrder.id
        incident_no     = "STAGE7-RPA-$RunId"
        equipment_code  = "CNC-01"
        title           = "Stage 7 RPA fallback $RunId"
        priority        = "P2"
        description     = "MES 503 should trigger Playwright RPA"
        assigned_team   = "maintenance"
    }
    $rpaResponse = Invoke-Json "POST" $Workflow03 $rpaPayload @{} 90
    Invoke-Json "POST" "$LegacyMesUrl/internal/failure-mode" @{ mode = "normal" } @{ "X-Internal-Token" = $InternalToken } | Out-Null
    Wait-Until "RPA result persisted" {
        $current = Invoke-Json "GET" "$BackendUrl/api/work-orders/$($rpaWorkOrder.id)"
        return ($current.creation_method -eq "RPA" -and -not [string]::IsNullOrWhiteSpace($current.external_id))
    } 60
    $rpaRuns = @(Invoke-Json "GET" "$BackendUrl/api/rpa-runs?work_order_id=$($rpaWorkOrder.id)")
    Assert-True ($rpaRuns.Count -ge 1) "No RPA run was recorded"
    Assert-True ($rpaRuns[0].status -eq "SUCCEEDED") "RPA run did not succeed"
    Assert-True ((Invoke-WebRequest "$BackendUrl/api/rpa-runs/$($rpaRuns[0].id)/screenshot" -UseBasicParsing -TimeoutSec 20).StatusCode -eq 200) "RPA screenshot was not accessible"

    Write-Step "Closing work order and generating knowledge case through n8n 05"
    Invoke-Json "POST" "$BackendUrl/api/work-orders/$p2WorkOrderId/assign" @{ assigned_team = "quality"; assignee = "stage7-smoke" } | Out-Null
    Invoke-Json "POST" "$BackendUrl/api/work-orders/$p2WorkOrderId/resolve" @{ resolution = "Smoke test resolution for $RunId" } | Out-Null
    $knowledgeBefore = [int](Invoke-PostgresScalar "select count(*) from knowledge_cases where incident_id = $p2IncidentId;")
    $knowledge = Invoke-Json "POST" $Workflow05 @{ incident_id = $p2IncidentId; resolution = "Smoke test closure knowledge for $RunId" } @{} 45
    Assert-True ($knowledge.id -gt 0) "Knowledge workflow did not return a knowledge case"
    $knowledgeAfter = [int](Invoke-PostgresScalar "select count(*) from knowledge_cases where incident_id = $p2IncidentId;")
    Assert-True ($knowledgeAfter -ge [Math]::Max(1, $knowledgeBefore)) "Knowledge case was not persisted"

    Write-Step "Checking SLA scan idempotency"
    $overdueWorkOrder = Invoke-Json "POST" "$BackendUrl/api/work-orders" @{
        title           = "Stage 7 overdue SLA $RunId"
        description     = "SLA idempotency smoke test"
        priority        = "P1"
        assigned_team   = "maintenance"
        creation_method = "API"
    }
    Invoke-PostgresScalar "update work_orders set sla_due_at = now() - interval '30 minutes' where id = $($overdueWorkOrder.id); select 1;" | Out-Null
    $slaFirst = Invoke-Json "POST" "$BackendUrl/api/internal/sla/escalations/scan" @{ level = 1 } @{ "X-Internal-Token" = $InternalToken }
    $slaSecond = Invoke-Json "POST" "$BackendUrl/api/internal/sla/escalations/scan" @{ level = 1 } @{ "X-Internal-Token" = $InternalToken }
    Assert-True ($slaFirst.created_notifications -ge 1) "First SLA scan did not create a notification"
    Assert-True ($slaSecond.created_notifications -eq 0) "Second SLA scan created a duplicate same-level notification"

    Write-Step "Checking global error workflow and sanitization"
    $errorBefore = [int](Invoke-PostgresScalar "select count(*) from workflow_events where event_type = 'WORKFLOW_ERROR';")
    Invoke-Json "POST" $Workflow99 @{ workflow_name = "stage7-smoke"; error_message = "token=super-secret resume_url=http://n8n/private/$RunId" } @{} 45 | Out-Null
    Wait-Until "Global error record" {
        [int](Invoke-PostgresScalar "select count(*) from workflow_events where event_type = 'WORKFLOW_ERROR';") -gt $errorBefore
    } 30
    $leaked = [int](Invoke-PostgresScalar "select count(*) from workflow_events where event_type = 'WORKFLOW_ERROR' and payload::text like '%super-secret%';")
    Assert-True ($leaked -eq 0) "Sensitive token leaked into workflow error payload"

    Write-Step "Checking persistence across restarts"
    $externalIdBefore = (Invoke-Json "GET" "$BackendUrl/api/work-orders/$($rpaWorkOrder.id)").external_id
    $runIdBefore = [int]$rpaRuns[0].id
    Invoke-Compose @("restart", "backend", "n8n", "rpa-worker")
    Wait-Until "Backend after restart" { (Invoke-Json "GET" "$BackendUrl/ready").status -eq "ready" } 90
    Wait-Until "RPA Worker after restart" { (Invoke-Json "GET" "$RpaWorkerUrl/ready").status -eq "ready" } 90
    Wait-Until "n8n after restart" { (Invoke-WebRequest "$N8nUrl" -UseBasicParsing -TimeoutSec 10).StatusCode -eq 200 } 90
    $externalIdAfter = (Invoke-Json "GET" "$BackendUrl/api/work-orders/$($rpaWorkOrder.id)").external_id
    Assert-True ($externalIdAfter -eq $externalIdBefore) "PostgreSQL did not retain external work order id across restart"
    Assert-True ((Invoke-WebRequest "$BackendUrl/api/rpa-runs/$runIdBefore/screenshot" -UseBasicParsing -TimeoutSec 20).StatusCode -eq 200) "RPA screenshot was not retained across restart"
    $workflowCount = [int](Invoke-N8nPostgresScalar "select count(*) from workflow_entity;")
    Assert-True ($workflowCount -ge 6) "n8n workflow persistence check failed"

    [pscustomobject]@{
        run_id = $RunId
        p2_incident_id = $p2IncidentId
        p2_work_order_id = $p2WorkOrderId
        p1_incident_id = $p1IncidentId
        rpa_work_order_id = $rpaWorkOrder.id
        rpa_external_id = $externalIdAfter
        rpa_run_id = $runIdBefore
        sla_first_created = $slaFirst.created_notifications
        sla_second_created = $slaSecond.created_notifications
        result = "PASS"
    } | ConvertTo-Json -Depth 6

    Write-Step "Smoke test completed"
}
finally {
    try {
        Invoke-Json "POST" "$LegacyMesUrl/internal/failure-mode" @{ mode = "normal" } @{ "X-Internal-Token" = $InternalToken } | Out-Null
    }
    catch {
        Write-Warning "Could not reset legacy MES failure mode: $($_.Exception.Message)"
    }
    Pop-Location
}
