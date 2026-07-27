[CmdletBinding()]
param(
    [string]$ApiBaseUrl = "http://localhost:8000/api/v1",
    [string]$InstitutionSlug = "demo-north",
    [string]$Email = "admin@demo-north.example.invalid",
    [string]$RoleCode = "institution_administrator"
)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$securePassword = Read-Host "Synthetic demonstration password" -AsSecureString
$password = [System.Net.NetworkCredential]::new('', $securePassword).Password
$loginBody = @{
    institution_slug = $InstitutionSlug
    email = $Email
    password = $password
    role_code = $RoleCode
    device_label = "Owner-machine validation"
} | ConvertTo-Json
$login = Invoke-RestMethod -Method Post -Uri "$ApiBaseUrl/auth/login" -ContentType "application/json" -Body $loginBody
if (-not $login.access_token -or -not $login.refresh_token) { throw "Login did not return a token pair." }
$refreshBody = @{ refresh_token = $login.refresh_token } | ConvertTo-Json
$rotated = Invoke-RestMethod -Method Post -Uri "$ApiBaseUrl/auth/refresh" -ContentType "application/json" -Body $refreshBody
if ($rotated.refresh_token -eq $login.refresh_token) { throw "Refresh token did not rotate." }
$headers = @{ Authorization = "Bearer $($rotated.access_token)" }
Invoke-RestMethod -Method Post -Uri "$ApiBaseUrl/auth/logout" -Headers $headers -ContentType "application/json" -Body (@{ refresh_token = $rotated.refresh_token; all_sessions = $false } | ConvertTo-Json) | Out-Null
Write-Host "Login, refresh rotation, and logout completed. Save sanitised terminal evidence." -ForegroundColor Green
