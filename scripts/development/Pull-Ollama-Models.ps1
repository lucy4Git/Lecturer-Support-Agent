[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [ValidateSet('minimal', 'standard', 'advanced', 'custom')]
    [string]$Profile = 'standard',
    [string[]]$Models,
    [switch]$SkipExisting,
    [switch]$SmokeTest,
    [switch]$ContinueOnError
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$profilePath = Join-Path $projectRoot 'config\ai\ollama-model-profiles.json'
$inventoryDir = Join-Path $projectRoot 'runtime\model-inventory'
$inventoryPath = Join-Path $inventoryDir 'ollama-models.local.json'

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    throw 'Ollama is not installed or not on PATH. Run Install-Ollama-Windows.ps1 first.'
}

try {
    Invoke-RestMethod -Uri 'http://localhost:11434/api/tags' -Method Get -TimeoutSec 5 | Out-Null
} catch {
    throw 'Ollama is installed but its API is not responding. Start the Ollama application or run ollama serve.'
}

if ($Profile -eq 'custom') {
    if (-not $Models -or $Models.Count -eq 0) {
        throw 'For the custom profile, provide -Models model1,model2.'
    }
    $selectedModels = @($Models)
    $recommendedDisk = $null
} else {
    if (-not (Test-Path $profilePath)) { throw "Profile file not found: $profilePath" }
    $profiles = Get-Content $profilePath -Raw | ConvertFrom-Json
    $profileConfig = $profiles.profiles.$Profile
    if (-not $profileConfig) { throw "Unknown profile: $Profile" }
    $selectedModels = @($profileConfig.models | ForEach-Object { $_.name })
    $recommendedDisk = [double]$profileConfig.recommended_free_disk_gb
}

$driveName = (Split-Path $env:USERPROFILE -Qualifier).TrimEnd(':')
$drive = Get-PSDrive -Name $driveName -ErrorAction SilentlyContinue
if ($drive -and $recommendedDisk) {
    $freeGb = [math]::Round($drive.Free / 1GB, 1)
    Write-Host "Free disk on $($drive.Name): $freeGb GB; profile planning recommendation: $recommendedDisk GB."
    if ($freeGb -lt $recommendedDisk) {
        Write-Warning 'Free disk is below the profile planning recommendation. Pulls may fail or leave insufficient working space.'
    }
}

$current = @()
try {
    $current = @((Invoke-RestMethod -Uri 'http://localhost:11434/api/tags' -Method Get).models | ForEach-Object { $_.name })
} catch { }

$results = @()
foreach ($model in $selectedModels) {
    if ($SkipExisting -and ($current -contains $model -or $current -contains "$model`:latest")) {
        Write-Host "Skipping existing model: $model"
        $results += [pscustomobject]@{ model = $model; status = 'already_present'; timestamp = (Get-Date).ToString('o') }
        continue
    }

    try {
        if ($PSCmdlet.ShouldProcess($model, 'Pull Ollama model')) {
            Write-Host "Pulling $model ..."
            & ollama pull $model
            if ($LASTEXITCODE -ne 0) { throw "ollama pull returned exit code $LASTEXITCODE" }
            $results += [pscustomobject]@{ model = $model; status = 'pulled'; timestamp = (Get-Date).ToString('o') }
        }
    } catch {
        $results += [pscustomobject]@{ model = $model; status = 'failed'; error = $_.Exception.Message; timestamp = (Get-Date).ToString('o') }
        if (-not $ContinueOnError) { throw }
        Write-Warning "Failed to pull $model: $($_.Exception.Message)"
    }
}

if ($SmokeTest) {
    $chatModel = $selectedModels | Where-Object { $_ -notmatch 'embed' } | Select-Object -First 1
    if ($chatModel) {
        Write-Host "Running a small smoke test with $chatModel ..."
        $body = @{ model = $chatModel; messages = @(@{ role = 'user'; content = 'Reply with exactly READY.' }); stream = $false } | ConvertTo-Json -Depth 6
        $response = Invoke-RestMethod -Uri 'http://localhost:11434/api/chat' -Method Post -ContentType 'application/json' -Body $body -TimeoutSec 300
        Write-Host "Smoke-test response: $($response.message.content)"
    }
}

New-Item -ItemType Directory -Path $inventoryDir -Force | Out-Null
$tags = Invoke-RestMethod -Uri 'http://localhost:11434/api/tags' -Method Get
$inventory = [ordered]@{
    generated_at = (Get-Date).ToUniversalTime().ToString('o')
    host = $env:COMPUTERNAME
    profile = $Profile
    requested_models = $selectedModels
    pull_results = $results
    installed_models = $tags.models
}
$inventory | ConvertTo-Json -Depth 10 | Set-Content -Path $inventoryPath -Encoding UTF8

Write-Host "Model inventory written to: $inventoryPath"
Write-Host 'Installed Ollama models:'
& ollama list
