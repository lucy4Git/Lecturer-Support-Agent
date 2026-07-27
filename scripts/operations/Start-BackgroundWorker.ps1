[CmdletBinding()]
param(
    [string]$Queue = 'default',
    [double]$PollSeconds = 2,
    [switch]$Once
)
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Set-Location $Root
if (Test-Path '.env') {
    . "$Root\scripts\validation\Validation.Common.ps1"
    Import-ProjectEnvironment -Path '.env' -Override
}
$args = @('-m','services.worker.main','--queue',$Queue,'--poll-seconds',[string]$PollSeconds)
if ($Once) { $args += '--once' }
& python @args
if ($LASTEXITCODE -ne 0) { throw "Background worker exited with code $LASTEXITCODE" }
