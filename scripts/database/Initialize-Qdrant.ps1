[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $root

Get-Content .env | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
        [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
    }
}
$url = if ($env:QDRANT_URL) { $env:QDRANT_URL } else { "http://localhost:6333" }
$collection = if ($env:QDRANT_COLLECTION) { $env:QDRANT_COLLECTION } else { "lecturer_support_documents" }
$body = Get-Content "infrastructure\database\qdrant\collection.json" -Raw
try {
    Invoke-RestMethod -Method Put -Uri "$url/collections/$collection" -ContentType "application/json" -Body $body | Out-Null
} catch {
    if ($_.Exception.Response.StatusCode.value__ -ne 409) { throw }
}
Write-Host "Qdrant collection '$collection' is available." -ForegroundColor Green
