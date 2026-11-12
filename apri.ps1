# TabDeck - icona "TabDeck" (Desktop e menu Start).
# Avvia TabDeck senza console: si apre la sua finestra (stato, QR per collegare il telefono, dispositivi).
# Se TabDeck e' gia' acceso, la nuova istanza chiede a quella attiva di mostrare la finestra ed esce.
$ErrorActionPreference = "SilentlyContinue"
$Here = $PSScriptRoot
Add-Type -AssemblyName System.Windows.Forms

$py = "python.exe"
$pyFile = Join-Path $Here "data\python.txt"
if (Test-Path $pyFile) { $py = (Get-Content $pyFile -Raw -Encoding UTF8).Trim() }
$pyw = $py
if (Split-Path $py) {
    $w = Join-Path (Split-Path $py) "pythonw.exe"
    if (Test-Path $w) { $pyw = $w }
} else {
    $c = Get-Command pythonw.exe -ErrorAction SilentlyContinue
    if ($c) { $pyw = $c.Source }
}
$td = Join-Path $Here "tabdeck.py"
try {
    Start-Process $pyw -ArgumentList "`"$td`" --open" -WorkingDirectory $Here
} catch {
    [System.Windows.Forms.MessageBox]::Show("Non trovo Python per avviare TabDeck.`n`nRilancia la configurazione dal menu Start (TabDeck - Configura).", "TabDeck") | Out-Null
}
