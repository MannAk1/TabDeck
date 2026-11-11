# TabDeck - pubblica una nuova versione su GitHub (solo per chi sviluppa TabDeck).
#   pubblica.bat -Note "cosa cambia"
# Controlla: albero pulito su main, VERSION maggiore dell'ultimo tag, nessun segreto o dato personale
# nei file pubblicati e nei commit da inviare. Poi: tag vX.Y.Z, push, release su GitHub.
param([Parameter(Mandatory = $true)][string]$Note)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Fail($msg) { Write-Host ("  ERRORE: " + $msg) -ForegroundColor Red; exit 1 }

$gh = (Get-Command gh -ErrorAction SilentlyContinue).Source
if (-not $gh) { $gh = "C:\Program Files\GitHub CLI\gh.exe" }
if (-not (Test-Path $gh)) { Fail "GitHub CLI (gh) non trovato" }
& $gh auth status *> $null
if ($LASTEXITCODE -ne 0) { Fail "gh non e' collegato: esegui 'gh auth login'" }

if ((git rev-parse --abbrev-ref HEAD) -ne "main") { Fail "devi essere sul ramo main" }
if (git status --porcelain) { Fail "ci sono modifiche non salvate (fai il commit prima)" }

$m = Select-String -Path tabdeck.py -Pattern '^VERSION = "(\d+\.\d+\.\d+)"' | Select-Object -First 1
if (-not $m) { Fail "VERSION non trovata in tabdeck.py" }
$ver = $m.Matches[0].Groups[1].Value
$tags = @(git tag --list "v*" | ForEach-Object { try { [version]$_.Substring(1) } catch { } })
$last = $tags | Sort-Object | Select-Object -Last 1
if ($last -and [version]$ver -le $last) { Fail "VERSION $ver non e' maggiore dell'ultima pubblicata ($last): aumentala in tabdeck.py" }

# --- controllo segreti e dati personali -------------------------------------------------------
$pats = @()
if (Test-Path data\token.txt) { $pats += (Get-Content data\token.txt -Raw).Trim() }
if (Test-Path data\discord.json) {
    $dc = Get-Content data\discord.json -Raw | ConvertFrom-Json
    if ($dc.client_secret) { $pats += [string]$dc.client_secret }
    if ($dc.client_id) { $pats += [string]$dc.client_id }
}
$mail = git config --global user.email
if ($mail) { $pats += $mail }
$pats += ("C:\Users\" + $env:USERNAME)
$pats += ("C:/Users/" + $env:USERNAME)
$pats = $pats | Where-Object { $_ -and $_.Length -ge 4 }
$bad = @()
foreach ($f in (git ls-files)) {
    if (-not (Test-Path -LiteralPath $f -PathType Leaf)) { continue }
    $hit = Select-String -LiteralPath $f -SimpleMatch -Pattern $pats -ErrorAction SilentlyContinue
    foreach ($h in $hit) { $bad += ("{0}:{1}" -f $f, $h.LineNumber) }
    if ((Get-Content -LiteralPath $f -Raw -ErrorAction SilentlyContinue) -match 'access_token"?\s*[:=]\s*"[A-Za-z0-9]{10,}') { $bad += "$f (access_token)" }
}
$mailRe = '[A-Za-z0-9._%+-]+@(gmail|googlemail|outlook|hotmail|live|yahoo|icloud|me|libero|virgilio|tiscali|alice|proton|protonmail)\.[a-z.]+'
foreach ($f in (git ls-files)) {
    if (-not (Test-Path -LiteralPath $f -PathType Leaf)) { continue }
    foreach ($h in (Select-String -LiteralPath $f -Pattern $mailRe -ErrorAction SilentlyContinue)) { $bad += ("{0}:{1} (email)" -f $f, $h.LineNumber) }
}
$remote = git ls-remote --heads origin main
$range = if ($remote) { "origin/main..HEAD" } else { "HEAD" }
# anche il contenuto dei commit da inviare (un segreto aggiunto e poi tolto resta nella storia)
$hist = git log -p $range
foreach ($p in $pats) { if ($hist | Select-String -SimpleMatch -Pattern $p -Quiet) { $bad += "storia dei commit ($range): contiene un dato riservato" } }
if ($hist | Select-String -Pattern $mailRe -Quiet) { $bad += "storia dei commit ($range): contiene un indirizzo email personale" }
foreach ($e in (git log $range --format="%ae %ce")) {
    foreach ($a in $e.Split(" ")) { if ($a -notlike "*@users.noreply.github.com") { $bad += "commit con email non privata: $a" } }
}
if ($bad.Count) {
    Write-Host "  Trovati dati da non pubblicare:" -ForegroundColor Red
    $bad | Select-Object -Unique | ForEach-Object { Write-Host ("    " + $_) }
    Fail "pubblicazione annullata"
}
Write-Host "  Controllo segreti: ok" -ForegroundColor Green

# --- pubblicazione ------------------------------------------------------------------------------
$tag = "v$ver"
git tag -a $tag -m "TabDeck $ver"
if ($LASTEXITCODE -ne 0) { Fail "tag non creato" }
git push origin main --follow-tags
if ($LASTEXITCODE -ne 0) { Fail "push non riuscito (il tag $tag resta solo in locale: 'git tag -d $tag' per toglierlo)" }
& $gh release create $tag --title "TabDeck $ver" --notes $Note --verify-tag
if ($LASTEXITCODE -ne 0) { Fail "release non creata (tag gia' inviato: riprova con 'gh release create $tag')" }
Write-Host "  Pubblicata TabDeck $ver" -ForegroundColor Green
