[CmdletBinding()]
param([switch]$Force)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $root
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }

function New-RandomSecret([int]$Bytes = 48) {
    $buffer = New-Object byte[] $Bytes
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($buffer) } finally { $rng.Dispose() }
    return [Convert]::ToBase64String($buffer).TrimEnd('=').Replace('+','-').Replace('/','_')
}

$content = Get-Content ".env" -Raw
$replacements = @{
    "POSTGRES_OWNER_PASSWORD" = (New-RandomSecret)
    "POSTGRES_APP_PASSWORD" = (New-RandomSecret)
    "POSTGRES_AUTH_PASSWORD" = (New-RandomSecret)
    "REDIS_PASSWORD" = (New-RandomSecret)
    "MINIO_ROOT_PASSWORD" = (New-RandomSecret)
    "OBJECT_STORAGE_SECRET_KEY" = (New-RandomSecret)
    "JWT_SECRET_KEY" = (New-RandomSecret 64)
}
foreach ($name in $replacements.Keys) {
    $pattern = "(?m)^$([Regex]::Escape($name))=(.*)$"
    $match = [Regex]::Match($content, $pattern)
    if (-not $match.Success) { continue }
    $current = $match.Groups[2].Value
    $isTemplate = ($current -eq '') -or ($current -match '^(change-|replace-with)')
    if ($Force -or $isTemplate) {
        $content = [Regex]::Replace($content, $pattern, "$name=$($replacements[$name])")
    }
}

# Keep connection URLs aligned with generated database passwords.
function Read-Value([string]$Name) {
    $m = [Regex]::Match($content, "(?m)^$([Regex]::Escape($Name))=(.*)$")
    if ($m.Success) { return $m.Groups[1].Value }
    return ""
}
$db = Read-Value "POSTGRES_DB"
$app = Read-Value "POSTGRES_APP_PASSWORD"
$auth = Read-Value "POSTGRES_AUTH_PASSWORD"
$owner = Read-Value "POSTGRES_OWNER_PASSWORD"
$content = [Regex]::Replace($content, '(?m)^DATABASE_URL=.*$', "DATABASE_URL=postgresql+psycopg://lsa_app:$app@localhost:5432/$db")
$content = [Regex]::Replace($content, '(?m)^AUTH_DATABASE_URL=.*$', "AUTH_DATABASE_URL=postgresql+psycopg://lsa_auth:$auth@localhost:5432/$db")
$content = [Regex]::Replace($content, '(?m)^MIGRATION_DATABASE_URL=.*$', "MIGRATION_DATABASE_URL=postgresql+psycopg://lsa_owner:$owner@localhost:5432/$db")
Set-Content ".env" $content -Encoding utf8
Write-Host "Local secrets were generated in .env. Values were not printed." -ForegroundColor Green
Write-Host "Do not upload or commit .env." -ForegroundColor Yellow
