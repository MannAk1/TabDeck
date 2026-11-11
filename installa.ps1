# TabDeck - installazione guidata (e disinstallazione con -Uninstall).
# Ogni passo spiega cosa fa e perche', e chiede conferma [S/N]. Se rispondi N il passo viene saltato:
# alla fine trovi l'elenco di cosa e' stato fatto e cosa no.
#   installa.bat              installa (o ripara / cambia rete se TabDeck e' gia' installato)
#   installa.bat -DryRun      mostra cosa farebbe, senza fare nulla
#   disinstalla.bat           toglie regola del firewall, avvio automatico e (se vuoi) i tuoi dati
param([switch]$DryRun, [switch]$Uninstall, [int]$Port = 0)

$ErrorActionPreference = "Stop"
$Here = $PSScriptRoot
$Done = New-Object System.Collections.ArrayList
$Skipped = New-Object System.Collections.ArrayList
$Startup = [Environment]::GetFolderPath("Startup")
$Lnk = Join-Path $Startup "TabDeck.lnk"

function Line { Write-Host ("=" * 72) -ForegroundColor DarkCyan }

function Ask($titolo, $cosa, $perche) {
    Write-Host ""
    Line
    Write-Host ("  " + $titolo) -ForegroundColor Cyan
    Line
    Write-Host "  Cosa faccio:" -ForegroundColor Yellow
    foreach ($l in $cosa) { Write-Host ("    " + $l) }
    Write-Host "  Perche':" -ForegroundColor Yellow
    foreach ($l in $perche) { Write-Host ("    " + $l) }
    while ($true) {
        $r = Read-Host "  Procedo? [S/N]"
        if ($r -match '^[sSyY]') { return $true }
        if ($r -match '^[nN]') { return $false }
    }
}

function Act($desc, [scriptblock]$action) {
    if ($DryRun) { Write-Host ("  [PROVA] farei: " + $desc) -ForegroundColor Magenta; return }
    & $action
}

function Ok($msg) { if ($DryRun) { $msg = "(prova) " + $msg }; Write-Host ("  OK: " + $msg) -ForegroundColor Green; [void]$Done.Add($msg) }
function Skip($msg) { Write-Host ("  Saltato: " + $msg) -ForegroundColor DarkYellow; [void]$Skipped.Add($msg) }
function Info($msg) { Write-Host ("  " + $msg) }

function Read-Config {
    $p = Join-Path $Here "data\config.json"
    if (Test-Path $p) {
        try { return Get-Content $p -Raw | ConvertFrom-Json } catch { }
    }
    return $null
}

function Write-Config($nets, $port) {
    $old = Read-Config
    $parts = @()
    $parts += '"allowed_nets": [' + (($nets | ForEach-Object { '"' + $_ + '"' }) -join ", ") + ']'
    $parts += '"port": ' + $port
    if ($old -and $old.adb) { $parts += '"adb": ' + ($old.adb | ConvertTo-Json) }
    $json = "{`r`n  " + ($parts -join ",`r`n  ") + "`r`n}`r`n"
    $dir = Join-Path $Here "data"
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory $dir | Out-Null }
    [IO.File]::WriteAllText((Join-Path $dir "config.json"), $json, (New-Object Text.UTF8Encoding $false))
}

function Test-Python($exe, $extra) {
    # @{ver=[version]; exe="..."} oppure $null. Il "python" finto di Windows (apre lo Store) non stampa nulla.
    try {
        $out = & $exe @extra -c "import sys;print('%d.%d|%s' % (sys.version_info[0], sys.version_info[1], sys.executable))" 2>$null
    } catch { return $null }
    if ($LASTEXITCODE -ne 0 -or -not $out) { return $null }
    $v, $path = ("" + $out).Trim().Split("|", 2)
    try { return @{ ver = [version]$v; exe = $path } } catch { return $null }
}

function Get-Python {
    # Il piu' recente tra: "python" nel PATH, il launcher "py -3", le cartelle d'installazione solite.
    $found = @()
    $found += Test-Python "python" @()
    if (Get-Command py -ErrorAction SilentlyContinue) { $found += Test-Python "py" @("-3") }
    $dirs = @("$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe", "$env:ProgramFiles\Python3*\python.exe")
    foreach ($d in $dirs) { foreach ($f in (Get-ChildItem $d -ErrorAction SilentlyContinue)) { $found += Test-Python $f.FullName @() } }
    return $found | Where-Object { $_ } | Sort-Object { $_.ver } | Select-Object -Last 1
}

function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
}

function Get-Net {
    $c = Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq "Up" } | Select-Object -First 1
    if (-not $c) { return $null }
    $a = $c.IPv4Address | Select-Object -First 1
    $ip = $a.IPAddress
    $len = [int]$a.PrefixLength
    $b = ([Net.IPAddress]$ip).GetAddressBytes()
    for ($i = 0; $i -lt 4; $i++) {
        $bits = [Math]::Max(0, [Math]::Min(8, $len - 8 * $i))
        $mask = (0xFF -shl (8 - $bits)) -band 0xFF
        $b[$i] = $b[$i] -band $mask
    }
    $octets = if ($len -ge 24) { 3 } elseif ($len -ge 16) { 2 } else { 3 }
    $o = $ip.Split(".")
    return @{
        alias = $c.InterfaceAlias; index = $c.InterfaceIndex; ip = $ip; len = $len
        net = ((($b | ForEach-Object { [string]$_ }) -join ".") + "/" + $len)
        prefix = (($o[0..($octets - 1)] -join ".") + ".")
        name = $c.NetProfile.Name; category = [string]$c.NetProfile.NetworkCategory
    }
}

function Run-Admin([string[]]$cmds) {
    # Esegue i comandi in una finestra PowerShell con permessi di amministratore (Windows chiede conferma).
    $script = '$ErrorActionPreference = "Stop"; ' + ($cmds -join "; ")
    $enc = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($script))
    try {
        $p = Start-Process powershell -Verb RunAs -Wait -PassThru -WindowStyle Hidden -ArgumentList "-NoProfile -ExecutionPolicy Bypass -EncodedCommand $enc"
        return ($p.ExitCode -eq 0)
    } catch {
        Info "Permesso di amministratore non concesso."
        return $false
    }
}

function Stop-TabDeck {
    $me = (Join-Path $Here "tabdeck.py").ToLower()
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -and $_.CommandLine.ToLower().Contains($me) } | ForEach-Object {
        $parent = Get-CimInstance Win32_Process -Filter ("ProcessId=" + $_.ParentProcessId) -ErrorAction SilentlyContinue
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        if ($parent -and $parent.Name -eq "cmd.exe") { Stop-Process -Id $parent.ProcessId -Force -ErrorAction SilentlyContinue }
    }
}

function Lnk-Target {
    if (-not (Test-Path $Lnk)) { return $null }
    return (New-Object -ComObject WScript.Shell).CreateShortcut($Lnk).TargetPath
}

function Summary {
    Write-Host ""
    Line
    Write-Host "  Riepilogo" -ForegroundColor Cyan
    Line
    foreach ($d in $Done) { Write-Host ("  [fatto]   " + $d) -ForegroundColor Green }
    foreach ($s in $Skipped) { Write-Host ("  [saltato] " + $s) -ForegroundColor DarkYellow }
    if ($DryRun) { Write-Host "  Era una prova (-DryRun): non e' stato cambiato nulla." -ForegroundColor Magenta }
}

# ------------------------------------------------------------------------------------------------
$cfg = Read-Config
if ($Port -eq 0) { $Port = if ($cfg -and $cfg.port) { [int]$cfg.port } else { 8765 } }
$RuleName = "TabDeck (TCP $Port, rete locale)"

Write-Host ""
Write-Host "  TabDeck - $(if ($Uninstall) { 'disinstallazione' } else { 'installazione' }) guidata" -ForegroundColor Cyan
Write-Host "  Cartella: $Here"
if ($DryRun) { Write-Host "  MODALITA' PROVA: mostro cosa farei, senza cambiare nulla." -ForegroundColor Magenta }

# ---------------------------------------------------------------- disinstallazione
if ($Uninstall) {
    if (Ask "Fermare TabDeck" @("Chiudo TabDeck se e' in esecuzione da questa cartella.") @("Serve per poter togliere i suoi file e impostazioni.")) {
        Act "fermare TabDeck" { Stop-TabDeck }; Ok "TabDeck fermato"
    } else { Skip "TabDeck non fermato" }
    if (Get-NetFirewallRule -DisplayName $RuleName -ErrorAction SilentlyContinue) {
        if (Ask "Togliere la regola del firewall" @("Tolgo la regola '$RuleName'.", "Windows chiedera' il permesso di amministratore.", "Le altre regole del firewall non vengono toccate.") @("Senza TabDeck non serve piu' tenere aperta la porta $Port.")) {
            $ok = $true
            Act "Remove-NetFirewallRule -DisplayName '$RuleName'" { $script:ok = Run-Admin @("Remove-NetFirewallRule -DisplayName '$RuleName'") }
            if ($ok) { Ok "regola del firewall tolta" } else { Skip "regola del firewall (toglila da 'Windows Defender Firewall')" }
        } else { Skip "regola del firewall" }
    }
    $t = Lnk-Target
    if ($t -and $t.ToLower() -eq (Join-Path $Here "tabdeck.bat").ToLower()) {
        if (Ask "Togliere l'avvio automatico" @("Cancello il collegamento TabDeck dalla cartella Esecuzione automatica.") @("Cosi' TabDeck non parte piu' all'accensione del PC.")) {
            Act "cancellare $Lnk" { Remove-Item $Lnk -Force }; Ok "avvio automatico tolto"
        } else { Skip "avvio automatico" }
    }
    $data = Join-Path $Here "data"
    if (Test-Path $data) {
        Write-Host ""
        Write-Host "  ATTENZIONE: la cartella data contiene le tue impostazioni, la chiave del telefono e l'accesso a Discord." -ForegroundColor Yellow
        Write-Host "  Di solito NON serve: se li tieni, reinstallando TabDeck ritrovi tutto." -ForegroundColor Yellow
        $r = Read-Host "  Per cancellarli scrivi CANCELLA (in maiuscolo); per tenerli premi solo Invio"
        if ($r -ceq "CANCELLA") {
            Act "cancellare $data" { Remove-Item $data -Recurse -Force }; Ok "dati cancellati"
        } else { Skip "dati tenuti in $data" }
    }
    Info ""
    Info "Per togliere del tutto TabDeck, alla fine cancella la cartella $Here"
    Summary
    exit 0
}

# ---------------------------------------------------------------- 0. cartella
if ($Here -match '\\Downloads\\|\\Download\\|\\AppData\\Local\\Temp\\|\\Temp\\') {
    $dest = Join-Path $env:USERPROFILE "TabDeck"
    if (Ask "Spostare TabDeck in una cartella stabile" @("Copio TabDeck da: $Here", "a: $dest", "(se c'e' gia' TabDeck li', i tuoi dati in data restano) e continuo da li'.") @("Download e cartelle temporanee vengono svuotate: TabDeck deve restare in un posto fisso.")) {
        Act "copiare i file in $dest" {
            New-Item -ItemType Directory -Force $dest | Out-Null
            Get-ChildItem $Here -Force | Where-Object { $_.Name -notin @("data", "cache", "backup") } | Copy-Item -Destination $dest -Recurse -Force
        }
        if (-not $DryRun) {
            Ok "TabDeck copiato in $dest"
            $a = @(); if ($Port -ne 8765) { $a += @("-Port", $Port) }
            & (Join-Path $dest "installa.ps1") @a
            exit $LASTEXITCODE
        }
    } else { Skip "TabDeck resta in $Here" }
}
if (Ask "Sbloccare i file scaricati" @("Tolgo il segno 'scaricato da Internet' dai file di questa cartella (Unblock-File).") @("Windows lo mette sui file presi da Internet e poi blocca o avvisa a ogni avvio di TabDeck.")) {
    Act "Unblock-File su $Here" { Get-ChildItem $Here -Recurse -File | Unblock-File }; Ok "file sbloccati"
} else { Skip "sblocco dei file" }

# ---------------------------------------------------------------- 1. Python
$py = Get-Python
if ($py -and $py.ver -ge [version]"3.10") {
    Info ""
    Info ("Python " + $py.ver + " trovato: " + $py.exe)
} else {
    $why = if ($py) { "Hai Python $($py.ver): TabDeck richiede 3.10 o piu' recente." } else { "Python non e' installato (o c'e' solo il collegamento che apre il Microsoft Store)." }
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        if (Ask "Installare Python 3.12" @("Installo Python 3.12 (sito ufficiale python.org) con winget, solo per il tuo utente.", "Ci vuole circa un minuto; potrebbe comparire una richiesta di conferma.") @($why, "TabDeck e' scritto in Python e non funziona senza.")) {
            Act "winget install -e --id Python.Python.3.12 --scope user" {
                winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
                Refresh-Path
            }
            $py = Get-Python
            if ($py -and $py.ver -ge [version]"3.10") { Ok "Python $($py.ver) installato" } elseif (-not $DryRun) { Skip "Python: installazione non riuscita" }
        } else { Skip "Python" }
    } else {
        Info $why
        Info "Scaricalo da https://www.python.org/downloads/ (spunta 'Add python.exe to PATH') e rilancia installa.bat."
        Skip "Python (da installare a mano)"
    }
}
if (-not $DryRun -and -not ($py -and $py.ver -ge [version]"3.10")) {
    Write-Host "  Senza Python non posso continuare. Installalo e rilancia installa.bat." -ForegroundColor Red
    Summary
    exit 1
}
if ($py) {
    # tabdeck.bat usa questo Python (serve se "python" non e' nel PATH, es. dopo winget)
    Act "scrivere data\python.txt = $($py.exe)" {
        $dir = Join-Path $Here "data"
        if (-not (Test-Path $dir)) { New-Item -ItemType Directory $dir | Out-Null }
        [IO.File]::WriteAllText((Join-Path $dir "python.txt"), $py.exe, (New-Object Text.UTF8Encoding $false))
    }
}

# ---------------------------------------------------------------- 2. rete
$admin = @()
$net = Get-Net
if (-not $net) {
    Write-Host "  Non trovo nessuna rete collegata. Collega il PC al Wi-Fi di casa e rilancia installa.bat." -ForegroundColor Red
    Summary
    exit 1
}
if (Ask "Scegliere la rete di casa" @("Rete trovata: '$($net.name)' (scheda: $($net.alias))", "Indirizzo del PC: $($net.ip)   rete: $($net.net)", "Salvo in data\config.json: TabDeck ascolta solo su reti $($net.prefix)x, porta $Port.") @("Il telefono deve essere sulla STESSA rete del PC.", "Su altre reti (bar, albergo, ...) TabDeck resta chiuso, per sicurezza.", "Rispondi N se ora il PC NON e' sulla rete dove userai il telefono.")) {
    Act "scrivere data\config.json (allowed_nets $($net.prefix), port $Port)" { Write-Config @($net.prefix) $Port }
    Ok "rete di casa: $($net.prefix)x (porta $Port)"
    if ($net.category -eq "Public") {
        if (Ask "Rendere privata la rete di casa" @("Windows considera '$($net.name)' una rete PUBBLICA. La imposto come PRIVATA.", "Servira' il permesso di amministratore (lo chiedo una volta sola, al passo del firewall).") @("Sulle reti pubbliche Windows blocca le connessioni in arrivo: il telefono non riuscirebbe a collegarsi.", "'Privata' e' l'impostazione giusta per il Wi-Fi di casa.")) {
            $admin += "Set-NetConnectionProfile -InterfaceIndex $($net.index) -NetworkCategory Private"
        } else { Skip "rete lasciata pubblica (il telefono potrebbe non collegarsi)" }
    }
} else { Skip "rete di casa (rilancia installa.bat quando sei sulla rete giusta)" }

# ---------------------------------------------------------------- 3. firewall
$fwAsked = Ask "Aprire TabDeck al telefono (firewall)" @("Creo la regola del firewall '$RuleName':", "connessioni in arrivo sulla porta TCP $Port, SOLO dalla rete $($net.net), SOLO su reti private.", "Se esiste gia' una regola con questo nome la sostituisco; le altre non le tocco.", "Windows chiedera' il permesso di amministratore.") @("Senza questa regola Windows blocca il telefono.", "Anche con la porta aperta, ogni richiesta deve avere la chiave segreta di TabDeck.")
if ($fwAsked) {
    $admin += "Remove-NetFirewallRule -DisplayName '$RuleName' -ErrorAction SilentlyContinue"
    $admin += "New-NetFirewallRule -DisplayName '$RuleName' -Direction Inbound -Action Allow -Protocol TCP -LocalPort $Port -RemoteAddress '$($net.net)' -Profile Private,Domain | Out-Null"
}
if ($admin.Count -gt 0) {
    $ok = $true
    Act ("come amministratore: " + ($admin -join " ; ")) { $script:ok = Run-Admin $admin }
    if (-not $DryRun) {
        if ($ok -and $fwAsked -and (Get-NetFirewallRule -DisplayName $RuleName -ErrorAction SilentlyContinue)) { Ok "regola del firewall creata" }
        elseif ($fwAsked) { Skip "regola del firewall (non creata)" }
        if ($admin[0] -like "Set-NetConnectionProfile*") { if ($ok) { Ok "rete impostata come privata" } else { Skip "rete privata (non impostata)" } }
    }
} elseif (-not $fwAsked) { Skip "regola del firewall (il telefono sara' bloccato)" }

# ---------------------------------------------------------------- 4. avvio automatico
$bat = Join-Path $Here "tabdeck.bat"
$t = Lnk-Target
$extra = if ($t -and $t.ToLower() -ne $bat.ToLower()) { @("ATTENZIONE: sostituisce il collegamento esistente, che avvia: $t") } else { @() }
if (Ask "Avviare TabDeck con Windows" (@("Metto un collegamento a TabDeck nella cartella Esecuzione automatica (finestra ridotta a icona).") + $extra) @("Cosi' TabDeck e' gia' pronto quando accendi il PC. Puoi toglierlo con disinstalla.bat.")) {
    Act "creare $Lnk" {
        $s = (New-Object -ComObject WScript.Shell).CreateShortcut($Lnk)
        $s.TargetPath = $bat; $s.WorkingDirectory = $Here; $s.WindowStyle = 7
        $ico = Join-Path $Here "tabdeck.ico"; if (Test-Path $ico) { $s.IconLocation = $ico }
        $s.Save()
    }
    Ok "avvio automatico con Windows"
} else { Skip "avvio automatico (avvia TabDeck con tabdeck.bat)" }

# ---------------------------------------------------------------- 5. avvio + abbinamento
$pair = "http://$($net.ip):$Port/pair"
if (Ask "Avviare TabDeck e collegare il telefono" @("Avvio TabDeck (se e' gia' acceso lo riavvio) e apro su questo PC la pagina con il codice QR:", $pair) @("Inquadri il QR con il telefono e TabDeck si apre gia' collegato, senza scrivere nulla.")) {
    Act "avviare $bat e aprire $pair" {
        Stop-TabDeck
        Start-Process $bat -WorkingDirectory $Here -WindowStyle Minimized
        $up = $false
        for ($i = 0; $i -lt 20 -and -not $up; $i++) {
            Start-Sleep 1
            try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 $pair | Out-Null; $up = $true } catch { }
        }
        if ($up) { Start-Process $pair; Ok "TabDeck avviato, pagina di abbinamento aperta" }
        else {
            Skip "TabDeck non risponde su $pair"
            Info "Controlla la finestra di TabDeck: se dice 'rete non consentita', rilancia installa.bat sulla rete di casa."
        }
    }
} else { Skip "avvio (apri tabdeck.bat, poi $pair sul PC)" }

Summary
Info ""
Info "Per disinstallare: disinstalla.bat. Per riaprire il QR: $pair (solo da questo PC)."
