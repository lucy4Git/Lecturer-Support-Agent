[CmdletBinding()]
param(
    [ValidateSet('static','runtime','full')][string]$Mode = 'full',
    [string]$ProfilePath = 'config/validation/owner-machine-profile.example.json',
    [switch]$InstallDependencies,
    [switch]$StartInfrastructure,
    [switch]$RunLivePreview,
    [switch]$IncludeCloudProviderProbes,
    [switch]$KeepServicesRunning,
    [switch]$OpenReport
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Set-Location $Root
. "$PSScriptRoot\Validation.Common.ps1"
if (-not (Test-Path $ProfilePath)) { throw "Validation profile not found: $ProfilePath" }
$profile = Get-Content $ProfilePath -Raw | ConvertFrom-Json
$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$evidenceRoot = Join-Path $Root ([string]$profile.evidence_root)
$evidence = Join-Path $evidenceRoot $stamp
New-Item -ItemType Directory -Path $evidence -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $evidence 'screenshots') -Force | Out-Null
$env:VALIDATION_EVIDENCE_DIR = $evidence
$results = [System.Collections.Generic.List[object]]::new()
$apiProcess = $null
$webProcess = $null

function Add-Stage([string]$Name, [scriptblock]$Action) {
    $record = Invoke-ValidationStage -Name $Name -Action $Action -EvidenceDirectory $evidence
    $results.Add($record)
    if ($record.status -eq 'failed' -and $profile.stop_on_failure) { throw "Validation stopped after failed stage: $Name" }
}

try {
    Add-Stage 'Preflight metadata' {
        [pscustomobject]@{
            validation_id=$stamp; mode=$Mode; project_root=$Root;
            powershell=$PSVersionTable.PSVersion.ToString(); os=[System.Environment]::OSVersion.VersionString;
            started_at=(Get-Date).ToUniversalTime().ToString('o')
        } | ConvertTo-Json | Set-Content (Join-Path $evidence 'machine.json') -Encoding utf8
        python --version
        node --version
        npm --version
        $insideGit = git rev-parse --is-inside-work-tree 2>$null
        if ($LASTEXITCODE -eq 0 -and $insideGit -eq 'true') { git status --short } else { Write-Host 'Git repository not initialised; validation will continue using .gitignore safety rules.' }
    }

    Add-Stage 'Environment safety' {
        & "$PSScriptRoot\Test-EnvironmentSafety.ps1" -RequireRuntimeEnvironment:($Mode -ne 'static')
    }

    if (Test-Path '.env') { Import-ProjectEnvironment -Path '.env' -Override }

    if ($InstallDependencies) {
        Add-Stage 'Install dependencies' {
            Invoke-CheckedCommand -FilePath 'python' -ArgumentList @('-m','pip','install','-e','.[dev]')
            Push-Location 'apps/web'
            try {
                Invoke-CheckedCommand -FilePath 'npm' -ArgumentList @('install')
                if ($RunLivePreview) { Invoke-CheckedCommand -FilePath 'npx' -ArgumentList @('playwright','install','chromium') }
            } finally { Pop-Location }
        }
    }

    Add-Stage 'Cumulative static validation' {
        Invoke-CheckedCommand -FilePath 'python' -ArgumentList @('scripts/validation/validate_data_foundation.py')
        Invoke-CheckedCommand -FilePath 'python' -ArgumentList @('scripts/validation/validate_multi_provider_pack.py')
        Invoke-CheckedCommand -FilePath 'python' -ArgumentList @('scripts/validation/validate_v13_foundation.py')
        Invoke-CheckedCommand -FilePath 'python' -ArgumentList @('scripts/validation/validate_v14_release.py')
        Invoke-CheckedCommand -FilePath 'python' -ArgumentList @('scripts/validation/validate_v15_release.py')
        Invoke-CheckedCommand -FilePath 'python' -ArgumentList @('scripts/validation/validate_v16_release.py')
        Invoke-CheckedCommand -FilePath 'python' -ArgumentList @('scripts/validation/validate_v17_release.py')
        Invoke-CheckedCommand -FilePath 'python' -ArgumentList @('scripts/validation/validate_v18_release.py')
        Invoke-CheckedCommand -FilePath 'python' -ArgumentList @('scripts/validation/validate_v19_release.py')
        Invoke-CheckedCommand -FilePath 'python' -ArgumentList @('scripts/validation/validate_v20_release.py')
        Invoke-CheckedCommand -FilePath 'python' -ArgumentList @('scripts/validation/validate_v21_release.py')
        Invoke-CheckedCommand -FilePath 'python' -ArgumentList @('scripts/validation/validate_v22_release.py')
        Invoke-CheckedCommand -FilePath 'python' -ArgumentList @('scripts/validation/validate_v23_release.py')
        Invoke-CheckedCommand -FilePath 'python' -ArgumentList @('scripts/validation/validate_v24_release.py')
        Invoke-CheckedCommand -FilePath 'python' -ArgumentList @('scripts/validation/validate_v25_completion.py')
        Invoke-CheckedCommand -FilePath 'python' -ArgumentList @('scripts/data/validate_institution_onboarding.py','data/manifests/example_institution_onboarding_package.json')
        Invoke-CheckedCommand -FilePath 'python' -ArgumentList @('-m','pytest','tests/unit','-q')
        Invoke-CheckedCommand -FilePath 'node' -ArgumentList @('scripts/validation/Validate-TypeScriptSyntax.js')
    }

    if ($Mode -ne 'static') {
        Add-Stage 'Owner-machine prerequisites' {
            & "$PSScriptRoot\Test-OwnerMachinePrerequisites.ps1" -ProfilePath $ProfilePath -RequireBrowserTooling:$RunLivePreview
        }
        if ($StartInfrastructure) {
            Add-Stage 'Start local infrastructure' {
                & "$Root\scripts\database\Start-DatabaseStack.ps1"
            }
        }
        Add-Stage 'Database migrations and seed' {
            & "$Root\scripts\database\Run-Migrations.ps1"
            & "$Root\scripts\database\Initialize-Qdrant.ps1"
            & "$Root\scripts\database\Seed-DemonstrationData.ps1"
            Invoke-CheckedCommand -FilePath 'python' -ArgumentList @('-m','pytest','tests/integration','-q')
            & "$Root\scripts\database\Test-TenantIsolation.ps1"
        }
        Add-Stage 'Web typecheck and production build' {
            Push-Location 'apps/web'
            try {
                Invoke-CheckedCommand -FilePath 'npm' -ArgumentList @('run','typecheck')
                Invoke-CheckedCommand -FilePath 'npm' -ArgumentList @('run','build')
            } finally { Pop-Location }
        }

        if ($RunLivePreview) {
            Add-Stage 'Launch API and web preview' {
                $pythonCommand = (Get-Command python).Source
                $npmCmd = Get-Command npm.cmd -ErrorAction SilentlyContinue
                $npmCommand = if ($npmCmd) { $npmCmd.Source } else { (Get-Command npm).Source }
                $apiOut = Join-Path $evidence 'api.stdout.log'
                $apiErr = Join-Path $evidence 'api.stderr.log'
                $webOut = Join-Path $evidence 'web.stdout.log'
                $webErr = Join-Path $evidence 'web.stderr.log'
                $script:apiProcess = Start-Process -FilePath $pythonCommand -ArgumentList @('-m','uvicorn','services.api.app.main:app','--host','127.0.0.1','--port','8000') -WorkingDirectory $Root -PassThru -RedirectStandardOutput $apiOut -RedirectStandardError $apiErr
                $script:webProcess = Start-Process -FilePath $npmCommand -ArgumentList @('run','start','--','--hostname','127.0.0.1','--port','3000') -WorkingDirectory (Join-Path $Root 'apps/web') -PassThru -RedirectStandardOutput $webOut -RedirectStandardError $webErr
                Wait-HttpEndpoint -Url 'http://localhost:8000/health' -TimeoutSeconds 120
                Wait-HttpEndpoint -Url 'http://localhost:3000/sign-in' -TimeoutSeconds 120
            }
        }

        Add-Stage 'Runtime service probes' {
            $arguments = @(
                'scripts/validation/runtime_probe.py', '--output', (Join-Path $evidence 'runtime-probes.json'),
                '--api-health-url', 'http://localhost:8000/health',
                '--api-ready-url', 'http://localhost:8000/ready',
                '--web-url', 'http://localhost:3000/sign-in', '--ollama-generation', '--crossref'
            )
            foreach ($model in $profile.required_ollama_models) { $arguments += @('--required-ollama-model', [string]$model) }
            if ($IncludeCloudProviderProbes) { $arguments += '--cloud-providers' }
            if (-not $RunLivePreview) { $arguments += '--skip-application-probes' }
            Invoke-CheckedCommand -FilePath 'python' -ArgumentList $arguments
        }

        if ($RunLivePreview) {
            Add-Stage 'v2.3 operational runtime controls' {
                & "$PSScriptRoot\Test-V2.3OperationalRuntime.ps1"
            }
            Add-Stage 'v2.4 domain automation runtime controls' {
                & "$PSScriptRoot\Test-V2.4DomainAutomationRuntime.ps1"
            }
            Add-Stage 'v2.5 completion runtime controls' {
                & "$PSScriptRoot\Test-V2.5CompletionRuntime.ps1"
            }
            Add-Stage 'Role-aware live preview' {
                Push-Location 'apps/web'
                try { Invoke-CheckedCommand -FilePath 'npx' -ArgumentList @('playwright','test') } finally { Pop-Location }
            }
        }
    }
} finally {
    if (-not $KeepServicesRunning) {
        foreach ($process in @($apiProcess, $webProcess)) {
            if ($process -and -not $process.HasExited) { Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue }
        }
    }
}

$summary = [ordered]@{
    validation_id = $stamp
    generated_at = (Get-Date).ToUniversalTime().ToString('o')
    mode = $Mode
    overall_status = if (@($results | Where-Object status -eq 'failed').Count) { 'failed' } else { 'passed' }
    counts = [ordered]@{
        passed = @($results | Where-Object status -eq 'passed').Count
        failed = @($results | Where-Object status -eq 'failed').Count
        total = $results.Count
    }
    stages = $results
    runtime_claim = if ($Mode -eq 'full' -and $RunLivePreview -and -not @($results | Where-Object status -eq 'failed').Count) { 'validated_on_owner_machine' } else { 'validation_incomplete_or_failed' }
}
$summary | ConvertTo-Json -Depth 8 | Set-Content (Join-Path $evidence 'validation-summary.json') -Encoding utf8
$lines = @(
    '# Lecturer Support Agent owner-machine validation report', '',
    "- Validation ID: $stamp", "- Mode: $Mode", "- Overall status: **$($summary.overall_status)**",
    "- Passed stages: $($summary.counts.passed)", "- Failed stages: $($summary.counts.failed)", '',
    '| Stage | Status | Duration (s) | Evidence |', '|---|---:|---:|---|'
)
foreach ($stage in $results) { $lines += "| $($stage.name) | $($stage.status) | $($stage.duration_seconds) | $($stage.log) |" }
$lines += @('', '## Release gate', '', "Runtime claim: **$($summary.runtime_claim)**", '', 'Claude must not report a runtime checkpoint complete unless this report passes in full mode with live preview evidence and all corrective actions are closed.')
$reportPath = Join-Path $evidence 'VALIDATION_REPORT.md'
Set-Content -Path $reportPath -Value $lines -Encoding utf8
Write-Host "`nValidation evidence: $evidence" -ForegroundColor Yellow
Write-Host "Overall status: $($summary.overall_status)" -ForegroundColor $(if($summary.overall_status -eq 'passed'){'Green'}else{'Red'})
if ($OpenReport) { Start-Process $reportPath }
if ($summary.overall_status -ne 'passed') { exit 1 }
