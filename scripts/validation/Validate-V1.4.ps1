[CmdletBinding()]
param([switch]$FullWebBuild)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $root
python -m compileall -q services tests
python -m pytest tests/unit -v
python -c "from services.database.models import Base; assert len(Base.metadata.tables) == 59; print('SQLAlchemy metadata: 59 tables')"
node .\scripts\validation\Validate-TypeScriptSyntax.js
if ($FullWebBuild) {
    Push-Location apps\web
    npm install
    npm run typecheck
    npm run build
    Pop-Location
}
Write-Host "v1.4 static validation completed. Runtime infrastructure remains a separate checkpoint." -ForegroundColor Green
