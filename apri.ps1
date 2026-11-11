# TabDeck - icona "TabDeck" (Desktop e menu Start).
# Avvia TabDeck se e' spento, poi apre sul PC la pagina con il QR per collegare il telefono.
$ErrorActionPreference = "SilentlyContinue"
$Here = $PSScriptRoot
Add-Type -AssemblyName System.Windows.Forms

$port = 8765
$cfgFile = Join-Path $Here "data\config.json"
if (Test-Path $cfgFile) {
    $cfg = Get-Content $cfgFile -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($cfg.port) { $port = [int]$cfg.port }
}
$c = Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq "Up" } | Select-Object -First 1
if (-not $c) {
    [System.Windows.Forms.MessageBox]::Show("Il PC non e' collegato a nessuna rete. Collegalo al Wi-Fi di casa e riprova.", "TabDeck") | Out-Null
    exit 1
}
$ip = ($c.IPv4Address | Select-Object -First 1).IPAddress
$url = "http://${ip}:$port/pair"

function Up { try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 $url | Out-Null; return $true } catch { return $false } }

if (-not (Up)) {
    Start-Process (Join-Path $Here "tabdeck.bat") -WorkingDirectory $Here -WindowStyle Minimized
    for ($i = 0; $i -lt 20 -and -not (Up); $i++) { Start-Sleep 1 }
}
if (Up) {
    Start-Process $url
} else {
    [System.Windows.Forms.MessageBox]::Show("TabDeck non risponde su $url.`n`nSe il PC e' su una rete diversa da quella di casa scelta all'installazione, rilancia la configurazione dal menu Start (TabDeck - Configura).", "TabDeck") | Out-Null
}
