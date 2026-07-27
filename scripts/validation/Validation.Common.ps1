Set-StrictMode -Version Latest

function Import-ProjectEnvironment {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)][string]$Path,
        [switch]$Override
    )
    if (-not (Test-Path $Path)) { throw "Local environment file was not found: $Path" }
    foreach ($line in Get-Content $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith('#') -or -not $trimmed.Contains('=')) { continue }
        $parts = $trimmed.Split('=', 2)
        $name = $parts[0].Trim()
        $value = $parts[1]
        if ($name -notmatch '^[A-Za-z_][A-Za-z0-9_]*$') { continue }
        if ($Override -or [string]::IsNullOrEmpty([Environment]::GetEnvironmentVariable($name, 'Process'))) {
            [Environment]::SetEnvironmentVariable($name, $value, 'Process')
        }
    }
}


function Invoke-CheckedCommand {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)][string]$FilePath,
        [object[]]$ArgumentList = @()
    )
    $global:LASTEXITCODE = 0
    & $FilePath @ArgumentList
    if ($LASTEXITCODE -ne 0) {
        throw "$FilePath exited with code $LASTEXITCODE."
    }
}

function Protect-ValidationLog {
    [CmdletBinding()]
    param([Parameter(Mandatory=$true)][string]$Path)
    if (-not (Test-Path $Path)) { return }
    $content = Get-Content $Path -Raw
    $sensitiveNames = Get-ChildItem Env: | Where-Object {
        $_.Name -match '(?i)(PASSWORD|SECRET|TOKEN|API_KEY|DATABASE_URL|PRIVATE_KEY|ACCESS_KEY)'
    }
    foreach ($item in $sensitiveNames) {
        $value = [string]$item.Value
        if ($value.Length -ge 8) { $content = $content.Replace($value, '[REDACTED]') }
    }
    Set-Content -Path $Path -Value $content -Encoding utf8
}

function Invoke-ValidationStage {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)][string]$Name,
        [Parameter(Mandatory=$true)][scriptblock]$Action,
        [Parameter(Mandatory=$true)][string]$EvidenceDirectory
    )
    $safeName = ($Name -replace '[^A-Za-z0-9_-]', '_').ToLowerInvariant()
    $logPath = Join-Path $EvidenceDirectory "$safeName.log"
    $started = Get-Date
    $status = 'passed'
    $exitCode = 0
    $message = 'Completed successfully.'
    Write-Host "`n=== $Name ===" -ForegroundColor Cyan
    try {
        $global:LASTEXITCODE = 0
        & $Action *>&1 | Tee-Object -FilePath $logPath
        if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) { throw "Stage command exited with code $LASTEXITCODE." }
    } catch {
        $status = 'failed'
        $exitCode = if ($LASTEXITCODE) { [int]$LASTEXITCODE } else { 1 }
        $message = $_.Exception.Message
        $_ | Out-String | Add-Content -Path $logPath
        Write-Host "$Name failed: $message" -ForegroundColor Red
    } finally {
        Protect-ValidationLog -Path $logPath
    }
    $ended = Get-Date
    return [pscustomobject]@{
        name = $Name
        status = $status
        exit_code = $exitCode
        started_at = $started.ToUniversalTime().ToString('o')
        ended_at = $ended.ToUniversalTime().ToString('o')
        duration_seconds = [Math]::Round(($ended - $started).TotalSeconds, 2)
        message = $message
        log = (Split-Path $logPath -Leaf)
    }
}

function Wait-HttpEndpoint {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)][string]$Url,
        [int]$TimeoutSeconds = 90
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) { return }
        } catch { Start-Sleep -Seconds 2 }
    } while ((Get-Date) -lt $deadline)
    throw "Endpoint did not become reachable within $TimeoutSeconds seconds: $Url"
}
