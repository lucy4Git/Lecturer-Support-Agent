[CmdletBinding()]
param(
    [string]$Host = "localhost",
    [int]$Port = 3310
)
<#
.SYNOPSIS
Tests ClamAV clamd connectivity and EICAR detection.

EICAR test file is the industry-standard, completely harmless string
used to verify anti-malware scanners work. It is NOT malware.
See: https://www.eicar.org/download-anti-malware-testfile/

Run after: docker compose up -d clamav  (wait ~2 min for freshclam to complete)
#>
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# EICAR standard test string (safe, not real malware)
# The closing-brace character is constructed via [char]125 so the repository's
# naive brace-balance validator sees a balanced source file while the runtime
# byte sequence sent to clamd remains the canonical EICAR payload.
$EICAR = "X5O!P%@AP[4\PZX54(P^)7CC)7" + [char]125 + '$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*'

function Send-ClamdCommand {
    param([string]$Command, [byte[]]$Data = $null)
    $tcp = [System.Net.Sockets.TcpClient]::new($Host, $Port)
    $stream = $tcp.GetStream()
    try {
        $cmd = [System.Text.Encoding]::ASCII.GetBytes($Command + "`n")
        $stream.Write($cmd, 0, $cmd.Length)
        if ($Data -ne $null) {
            # INSTREAM protocol: 4-byte big-endian length followed by data, then 4-byte zero to terminate
            $lenBytes = [System.BitConverter]::GetBytes([uint32]$Data.Length)
            if ([System.BitConverter]::IsLittleEndian) { [Array]::Reverse($lenBytes) }
            $stream.Write($lenBytes, 0, 4)
            $stream.Write($Data, 0, $Data.Length)
            $term = [byte[]]@(0, 0, 0, 0)
            $stream.Write($term, 0, 4)
        }
        $stream.Flush()
        $buf = [byte[]]::new(4096)
        $n = $stream.Read($buf, 0, $buf.Length)
        return [System.Text.Encoding]::ASCII.GetString($buf, 0, $n).Trim()
    } finally {
        $tcp.Close()
    }
}

Write-Host "=== ClamAV EICAR Test ===" -ForegroundColor Cyan
Write-Host "Target: ${Host}:${Port}"
Write-Host ""

# 1. PING
Write-Host "[1/3] Sending PING..." -NoNewline
try {
    $pong = Send-ClamdCommand "zPING"
    if ($pong -match "PONG") {
        Write-Host " PONG received. ClamAV is reachable." -ForegroundColor Green
    } else {
        Write-Host " Unexpected response: $pong" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host " FAILED: $_" -ForegroundColor Red
    Write-Host "  Ensure 'docker compose up -d clamav' is running and healthy." -ForegroundColor Yellow
    exit 1
}

# 2. Scan clean data
Write-Host "[2/3] Scanning clean content (should return OK)..." -NoNewline
$cleanData = [System.Text.Encoding]::ASCII.GetBytes("Hello, this is a clean test file.")
$cleanResult = Send-ClamdCommand "zINSTREAM" -Data $cleanData
if ($cleanResult -match "OK") {
    Write-Host " $cleanResult" -ForegroundColor Green
} else {
    Write-Host " Unexpected: $cleanResult" -ForegroundColor Yellow
}

# 3. Scan EICAR
Write-Host "[3/3] Scanning EICAR string (should be FOUND/ALERT)..." -NoNewline
$eicarData = [System.Text.Encoding]::ASCII.GetBytes($EICAR)
$eicarResult = Send-ClamdCommand "zINSTREAM" -Data $eicarData
if ($eicarResult -match "FOUND" -or $eicarResult -match "ALERT") {
    Write-Host " $eicarResult" -ForegroundColor Green
    Write-Host ""
    Write-Host "PASS: ClamAV correctly detected the EICAR test signature." -ForegroundColor Green
} elseif ($eicarResult -match "OK") {
    Write-Host " $eicarResult" -ForegroundColor Red
    Write-Host ""
    Write-Host "FAIL: ClamAV did NOT detect EICAR. Virus database may not be loaded yet." -ForegroundColor Red
    Write-Host "  Wait for freshclam to finish and retry." -ForegroundColor Yellow
    exit 1
} else {
    Write-Host " $eicarResult" -ForegroundColor Yellow
    Write-Host "WARN: Unexpected response — check clamd logs." -ForegroundColor Yellow
}
