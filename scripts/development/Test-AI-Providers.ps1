[CmdletBinding()]
param(
    [switch]$IncludeCloud
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$checks = @()

try {
    $tags = Invoke-RestMethod -Uri 'http://localhost:11434/api/tags' -Method Get -TimeoutSec 10
    $checks += [pscustomobject]@{ provider = 'ollama'; configured = $true; reachable = $true; detail = "$($tags.models.Count) model(s) installed" }
} catch {
    $checks += [pscustomobject]@{ provider = 'ollama'; configured = $true; reachable = $false; detail = $_.Exception.Message }
}

$cloud = @(
    @{ provider = 'openai'; key = 'OPENAI_API_KEY'; model = 'OPENAI_DEFAULT_MODEL' },
    @{ provider = 'anthropic'; key = 'ANTHROPIC_API_KEY'; model = 'ANTHROPIC_DEFAULT_MODEL' },
    @{ provider = 'google_gemini'; key = 'GOOGLE_GEMINI_API_KEY'; model = 'GOOGLE_GEMINI_DEFAULT_MODEL' },
    @{ provider = 'deepseek'; key = 'DEEPSEEK_API_KEY'; model = 'DEEPSEEK_DEFAULT_MODEL' }
)

foreach ($item in $cloud) {
    $keyValue = [Environment]::GetEnvironmentVariable($item.key)
    $modelValue = [Environment]::GetEnvironmentVariable($item.model)
    $configured = -not [string]::IsNullOrWhiteSpace($keyValue) -and -not [string]::IsNullOrWhiteSpace($modelValue)
    $detail = if ($configured) { 'API key and default model are configured' } else { "Set $($item.key) and $($item.model)" }
    $checks += [pscustomobject]@{ provider = $item.provider; configured = $configured; reachable = $null; detail = $detail }
}

if ($IncludeCloud) {
    Write-Warning 'This script deliberately does not send academic content to cloud providers. Connectivity probes should be implemented through the application gateway with redacted test prompts and audit logging.'
}

$checks | Format-Table -AutoSize
if ($checks | Where-Object { $_.provider -eq 'ollama' -and -not $_.reachable }) { exit 2 }
