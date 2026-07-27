[CmdletBinding()]
param(
    [string]$ProjectRoot = (Get-Location).Path,
    [string]$OutputPath = ""
)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$ProjectRoot = (Resolve-Path $ProjectRoot).Path
if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $OutputPath = Join-Path (Split-Path $ProjectRoot -Parent) "Lecturer-Support-Agent-SAFE.zip"
}
$staging = Join-Path $env:TEMP ("lsa-safe-" + [Guid]::NewGuid())
New-Item -ItemType Directory -Path $staging | Out-Null
$excludedDirectories = @(".git","node_modules",".venv","venv","__pycache__",".pytest_cache",".next","dist","build","coverage","runtime\secrets")
$excludedFiles = @(".env",".env.local",".env.development",".env.production",".env.test","*.pem","*.key","*.p12","*.pfx","credentials.json","service-account*.json")
$args = @($ProjectRoot,$staging,"/E","/R:1","/W:1","/NFL","/NDL","/NJH","/NJS","/NC","/NS","/NP","/XD") + $excludedDirectories + @("/XF") + $excludedFiles
& robocopy @args | Out-Null
Get-ChildItem $staging -Recurse -Force -File | Where-Object { $_.Name -like ".env*" -and $_.Name -ne ".env.example" } | Remove-Item -Force
$textExtensions = @(".md",".txt",".json",".yaml",".yml",".toml",".ini",".ps1",".py",".js",".jsx",".ts",".tsx")
$patterns = @("sk-ant-[A-Za-z0-9_-]{20,}","sk-[A-Za-z0-9_-]{20,}","AIza[0-9A-Za-z_-]{25,}","(?i)(api[_-]?key|secret|token)[ \t]*[:=][ \t]*['`"]?(?=[A-Za-z0-9_-]{24,})(?=[A-Za-z0-9_-]*[0-9])(?=[A-Za-z0-9_-]*[A-Z])[A-Za-z0-9_-]{24,}")
$files = Get-ChildItem $staging -Recurse -File | Where-Object { $textExtensions -contains $_.Extension.ToLower() }
$findings = foreach ($pattern in $patterns) { $files | Select-String -Pattern $pattern -AllMatches -ErrorAction SilentlyContinue }
if ($findings) {
    $findings | Select-Object Path,LineNumber,Line | Format-Table -AutoSize
    Remove-Item $staging -Recurse -Force
    throw "Potential secrets detected. Safe ZIP creation stopped."
}
if (Test-Path $OutputPath) { Remove-Item $OutputPath -Force }
Compress-Archive -Path (Join-Path $staging "*") -DestinationPath $OutputPath -CompressionLevel Optimal
Remove-Item $staging -Recurse -Force
$hash = (Get-FileHash $OutputPath -Algorithm SHA256).Hash.ToLower()
Write-Host "Safe archive: $OutputPath" -ForegroundColor Green
Write-Host "SHA-256: $hash"
