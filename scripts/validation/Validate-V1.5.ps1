[CmdletBinding()]
param([switch]$FullWebBuild)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $root

python .\scripts\validation\validate_v14_release.py
python .\scripts\validation\validate_v15_release.py
node .\scripts\validation\Validate-TypeScriptSyntax.js

if ($FullWebBuild) {
    Push-Location apps\web
    npm install
    npm run typecheck
    npm run build
    Pop-Location
}

Write-Host "v1.5 static validation completed. Live database, providers, Crossref, and browser preview remain owner-machine checkpoints." -ForegroundColor Green
