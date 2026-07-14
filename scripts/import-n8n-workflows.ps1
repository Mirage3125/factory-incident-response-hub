param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
)

$ErrorActionPreference = "Stop"

$workflowDir = Join-Path $ProjectRoot "n8n\workflows"
if (-not (Test-Path $workflowDir)) {
    throw "Workflow directory not found: $workflowDir"
}

$files = Get-ChildItem -Path $workflowDir -Filter "*.json" | Sort-Object Name
if ($files.Count -ne 6) {
    throw "Expected 6 workflow JSON files, found $($files.Count)"
}

Push-Location $ProjectRoot
try {
    docker compose exec -T n8n n8n --version
    foreach ($file in $files) {
        $containerPath = "/workflows/$($file.Name)"
        Write-Host "Importing $($file.Name)"
        docker compose exec -T n8n n8n import:workflow --input $containerPath
    }

    Write-Host "Imported workflow files. Activate them in the n8n UI if your n8n version does not preserve active=false imports as editable inactive workflows."
}
finally {
    Pop-Location
}
