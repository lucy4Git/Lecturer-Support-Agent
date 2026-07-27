[CmdletBinding()]
param([switch]$RequireRuntimeEnvironment)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Set-Location $Root
if ($RequireRuntimeEnvironment -and -not (Test-Path '.env')) { throw 'Create the local ignored .env file before runtime validation.' }
$gitRepository = $false
try {
    $inside = git rev-parse --is-inside-work-tree 2>$null
    $gitRepository = ($LASTEXITCODE -eq 0 -and $inside -eq 'true')
} catch { $gitRepository = $false }
if (Test-Path '.env') {
    if ($gitRepository) {
        $tracked = git ls-files --error-unmatch .env 2>$null
        if ($LASTEXITCODE -eq 0 -or $tracked) { throw '.env is tracked by Git. Remove it from tracking and rotate any exposed credentials.' }
        git check-ignore -q .env
        if ($LASTEXITCODE -ne 0) { throw '.env is not ignored by Git.' }
    } elseif (-not (Select-String -Path '.gitignore' -Pattern '^\.env$' -Quiet)) {
        throw 'This extracted folder is not yet a Git repository and .gitignore does not explicitly protect .env.'
    }
    $unsafe = Select-String -Path '.env' -Pattern '=(change-|replace-with|your-real-key)' -CaseSensitive:$false
    if ($unsafe) { throw 'The local .env still contains template values. Run Initialize-LocalSecrets.ps1 and configure providers locally.' }
}
$forbidden = @('.env.local','.env.production','credentials.json') | Where-Object { Test-Path $_ }
if ($gitRepository) {
    foreach ($file in $forbidden) {
        $tracked = git ls-files --error-unmatch $file 2>$null
        if ($LASTEXITCODE -eq 0 -or $tracked) { throw "$file is tracked by Git." }
    }
}
python scripts/validation/scan_repository_secrets.py
if ($LASTEXITCODE -ne 0) { throw 'Repository secret scan failed.' }
Write-Host 'Environment and repository secret-safety checks passed.' -ForegroundColor Green
