param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
)

$ErrorActionPreference = "Stop"

$markdownFiles = Get-ChildItem -Path $ProjectRoot -Recurse -Filter "*.md" |
    Where-Object { $_.FullName -notmatch "\\node_modules\\" -and $_.FullName -notmatch "\\.git\\" }

$errors = New-Object System.Collections.Generic.List[string]

foreach ($file in $markdownFiles) {
    $content = Get-Content -Raw -Path $file.FullName
    $fenceCount = ([regex]::Matches($content, '```')).Count
    if ($fenceCount % 2 -ne 0) {
        $errors.Add("Unclosed fenced block: $($file.FullName)")
    }

    $matches = [regex]::Matches($content, '\[[^\]]+\]\(([^)]+)\)')
    foreach ($match in $matches) {
        $target = $match.Groups[1].Value
        if ($target -match '^(https?://|mailto:|#)') {
            continue
        }
        if ($target -match '^([^#]+)#') {
            $target = $Matches[1]
        }
        if ([string]::IsNullOrWhiteSpace($target)) {
            continue
        }
        $candidate = Join-Path $file.DirectoryName $target
        if (-not (Test-Path $candidate)) {
            $errors.Add("Broken local link in $($file.FullName): $target")
        }
    }
}

if ($errors.Count -gt 0) {
    $errors | ForEach-Object { Write-Error $_ }
    exit 1
}

Write-Host "Checked $($markdownFiles.Count) Markdown files; local links and fenced blocks passed."
