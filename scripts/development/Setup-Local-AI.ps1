[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [ValidateSet('minimal', 'standard', 'advanced')]
    [string]$Profile = 'standard',
    [switch]$SkipExisting,
    [switch]$SmokeTest
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$installer = Join-Path $PSScriptRoot 'Install-Ollama-Windows.ps1'
$puller = Join-Path $PSScriptRoot 'Pull-Ollama-Models.ps1'

& $installer
& $puller -Profile $Profile -SkipExisting:$SkipExisting -SmokeTest:$SmokeTest

Write-Host 'Local AI setup completed. Configure OLLAMA_BASE_URL=http://localhost:11434 in your local .env file.'
