[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [switch]$ForceReinstall,
    [switch]$SkipServiceCheck
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Test-IsWindows {
    return [System.Environment]::OSVersion.Platform -eq [System.PlatformID]::Win32NT
}

if (-not (Test-IsWindows)) {
    throw 'This installer is intended for Windows. Use the official Ollama installer for your operating system.'
}

$existing = Get-Command ollama -ErrorAction SilentlyContinue
if ($existing -and -not $ForceReinstall) {
    Write-Host "Ollama is already installed: $($existing.Source)"
} else {
    if ($PSCmdlet.ShouldProcess('This Windows computer', 'Install Ollama using the official HTTPS PowerShell installer')) {
        Write-Host 'Downloading and running the official Ollama Windows installer...'
        $installScript = Invoke-RestMethod -Uri 'https://ollama.com/install.ps1'
        Invoke-Expression $installScript
    }
}

$ollama = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollama) {
    $candidate = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'
    if (Test-Path $candidate) {
        $env:Path = "$(Split-Path $candidate);$env:Path"
        $ollama = Get-Command ollama -ErrorAction SilentlyContinue
    }
}

if (-not $ollama) {
    throw 'Ollama installation could not be verified. Restart PowerShell and run ollama --version.'
}

& ollama --version

if (-not $SkipServiceCheck) {
    try {
        Invoke-RestMethod -Uri 'http://localhost:11434/api/tags' -Method Get -TimeoutSec 5 | Out-Null
        Write-Host 'Ollama API is available at http://localhost:11434.'
    } catch {
        Write-Warning 'The Ollama API is not responding yet. Start the Ollama desktop application, or run: ollama serve'
    }
}

Write-Host 'Ollama installation check completed.'
