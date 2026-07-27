[CmdletBinding()]
param([switch]$InstallDependencies)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location (Join-Path $root "apps\web")
if ($InstallDependencies) { npm install }
npm run dev
