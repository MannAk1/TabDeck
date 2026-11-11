# TabDeck — come funziona

Questo documento spiega il funzionamento di ogni parte, il modello di sicurezza e le regole di
prestazioni (con le misure fatte sul tablet). I commenti nel codice rimandano qui per i dettagli.

---

## 1. Panoramica

```
 Tablet (Chrome 81)                       PC (Windows)
 ┌──────────────────┐   HTTP + token   ┌──────────────────────────────────────────┐
 │ pagina web       │ ───────────────> │ tabdeck.py (ThreadingHTTPServer, :8765)   │
 │ index.html       │ <─────────────── │  ├─ Windows: volume, finestre, tasti,     │
 │ style.css        │   JSON / HTML    │  │   mouse, OCR, monitor (ctypes)          │
 │ app.js           │                  │  ├─ Discord: RPC sulla named pipe locale   │
 └──────────────────┘                  │  └─ Helldivers 2: input + lettura schermo  │
        ▲  adb (USB): apre la pagina    └──────────────────────────────────────────┘
        └──────────────────────────────────────── main(): controlla il tablet ogni 3 s
```

- **Un solo processo Python**, solo libreria standard + `ctypes` (nessun pacchetto da installare:
  niente catena di dipendenze da fidarsi).
- **Il PC è la fonte di verità**: il tablet mostra lo stato e invia comandi; ogni comando viene
  validato sul PC.
- La pagina arriva **in una sola risposta** (stile e script in linea) e poi parla con il PC con
  piccole richieste JSON.

### Avvio (`main()`)
1. Carica il token (`data/token.txt`, creato al primo avvio).
2. Legge `data/config.json` (rete, porta, adb). Ogni 3 s: legge l'indirizzo del PC; se è sulla rete consentita (`ALLOWED_NETS`) avvia/riavvia il
   server su quell'indirizzo, altrimenti lo ferma.
3. Con `--open` controlla i dispositivi adb: a un tablet nuovo (o se cambia l'indirizzo) apre la pagina
   con il token nell'URL; la pagina lo toglie subito dalla barra (`history.replaceState`) e da lì in poi
   usa il cookie.
4. Thread in background: icone dei programmi, `_ctrl_watch` (chiamate manuali HD2), `_remap_thread`
   (beta), `DISCORD`.

---

## 2. Le parti di `tabdeck.py`

| Sezione (cerca il titolo nel file) | Cosa fa |
|---|---|
| `PULSANTI`, `GROUPS`, `FAVORITES` | configurazione dei riquadri: tasti (`keys`) o programmi (`run`, lista argv). |
| `HELLDIVERS 2 - stratagemmi` | tabella dei codici; `HD2` = tasti e tempi di inserimento. |
| `Righe di Generale modificabili` | righe Preferiti/Sistema/Strumenti, scorciatoie personali, `data/layout.json`. |
| `volume di Windows` | Core Audio via COM in ctypes (`_com` chiama i metodi per indice della vtable). |
| `finestre aperte sul PC` | `list_windows` (come la barra delle applicazioni), app attive, focus/minimizza. |
| `icone vere dei programmi` | icone estratte dalla shell di Windows, salvate in `cache/icons`. |
| `Discord` | client RPC sulla named pipe di Discord (vedi §4). |
| `mixer` | volume per singola app (sessioni audio). |
| `"in riproduzione"` | brano corrente via WinRT (GlobalSystemMediaTransportControls) in ctypes. |
| `monitor del PC` | contatori PDH + GPU NVIDIA (NVML); campiona **solo** mentre la sezione è aperta. |
| `testo sullo schermo: OCR` | OCR di Windows (WinRT) per leggere il menu/HUD di HD2. |
| `input a scancode` / `touchpad e tastiera` | SendInput: tasti per i giochi, mouse, testo. |
| `sincronizzazione equipaggiamento` | legge il menu stratagemmi dallo schermo. |
| `PAGINA WEB` | unisce `web/*` in memoria; `render_page` riempie i segnaposto `__NOME__`. |
| `class Handler` | tutte le richieste HTTP (vedi §3 per i controlli). |
| `main`, `restart_tabdeck`, adb | avvio, riavvio dal tablet, apertura pagina via USB. |

### Helldivers 2 (sintesi)
- **Mai lettura della memoria del gioco** (rischio ban anti-cheat): solo cattura dello schermo (GDI) e
  stato di tastiera/mouse.
- Uno stratagemma viene digitato **solo se HD2 è la finestra in primo piano** (`send_stratagem`,
  altrimenti `NotInGame` -> 409).
- Flusso di una chiamata: codice -> "LANCIA" -> rilascio del tasto sinistro -> "IN ARRIVO" (OCR dell'HUD)
  -> ricarica. Durate imparate dal gioco (`data/hd2_cooldowns.json`), poi previste senza più leggere lo
  schermo (`all_known()`).
- Remap Ctrl+WASD -> frecce: **beta, spento di default**.

---

## 3. Sicurezza

### Modello
Il server può **comandare il PC** (tasti, testo, programmi): chi ha il token ha di fatto il controllo
della tastiera. Tutta la difesa serve a che **solo il tablet** abbia il token e possa raggiungere la porta.

### Controlli in atto
| Livello | Controllo | Dove |
|---|---|---|
| Rete | Firewall di Windows: porta 8765 aperta **solo** per l'indirizzo del tablet (172.20.10.3). | regola "TabDeck (TCP 8765, solo tablet)" |
| Rete | Il server ascolta **solo sulla rete dell'hotspot** (`ALLOWED_NETS`); su altri Wi-Fi resta chiuso. | `main()` |
| Accesso | Token casuale (`secrets.token_urlsafe(18)`, 24 caratteri) richiesto su **ogni** richiesta; confronto a tempo costante (`hmac.compare_digest`). | `Handler._token_ok` |
| Accesso | Cookie `HttpOnly` + `SameSite=Strict`: altri siti aperti sul tablet non possono usarlo. | `do_GET "/"` |
| Comandi | Dalla rete si può attivare **solo** un id di pulsante esistente; i programmi partono come lista argv **senza shell**. | `/press`, `trigger` |
| Comandi | App aggiunte dal tablet: solo programmi con una finestra **aperta ora** (percorso .exe esistente o AUMID dello Store validato con regex). | `open_specs`, `_spec_ok` |
| Comandi | Scorciatoie personali: solo tasti della lista `KEY_CHOICES` + modificatori. | `key_spec_ok` |
| Input | Corpo delle richieste limitato (1 KB, 8 KB per il testo); valori controllati (regex, liste ammesse, intervalli). | `do_POST` |
| Pagina | Testo che viene da fuori (titoli finestre, nomi Discord, brani) inserito **sempre** con `esc()` o `textContent`; mai codice dinamico (`eval`). | `web/app.js` |
| Pagina | Intestazioni: `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`; SVG serviti con CSP che blocca script. | `Handler._send`, `/icon/` |
| File | Percorsi serviti solo da nomi validati (regex): niente `../`. | `/icon/`, `/appicon/`, `/cover/` |
| Log | Il token viene sostituito con `***`; il testo digitato non viene mai scritto. | `log_message`, `/type` |
| Segreti | `data/` esclusa da git; i segreti Discord restano nel profilo utente. | `.gitignore` |
| Discord | Scambio del token OAuth solo con `https://discord.com`; accesso revocabile (⚙ -> Discord -> Scollega). | `Discord._token_req` |

### Rischi accettati (e perché)
- **HTTP senza cifratura sull'hotspot**: chi fosse collegato allo stesso hotspot potrebbe leggere il token.
  L'hotspot è il telefono dell'utente; HTTPS con certificato autofirmato su Chrome 81 / Android 4.4 sarebbe
  scomodo (avvisi) e fragile. Se in futuro altri dispositivi usassero l'hotspot: rigenerare il token
  (cancellare `data/token.txt`) e valutare HTTPS.
- **Chi ha il token controlla la tastiera** (`/type`, scorciatoie): è lo scopo dell'app.
- Le immagini degli avatar Discord le scarica il tablet da `cdn.discordapp.com` (senza referrer).

---

## 3b. Installazione, configurazione, aggiornamenti

### `data/config.json`
Scritto dall'installer: `{"allowed_nets": ["192.168.1."], "port": 8765, "adb": "..."}`. Ogni chiave
mancante o non valida torna al valore predefinito (`load_config`), quindi senza file TabDeck si comporta
come sul PC originale (hotspot `172.20.10.`, porta 8765, adb cercato nei posti soliti).

### Installer (`installa.ps1`, lanciato da `installa.bat` / `disinstalla.bat`)
Passi, ognuno con "cosa / perche'" e conferma `[S/N]`: copia in una cartella stabile + `Unblock-File`
(Mark-of-the-Web) -> Python >= 3.10 (lo stub dello Store conta come assente; winget, poi PATH riletto dal
registro) -> rete di casa (`Get-NetIPConfiguration` con gateway; prefisso per ottetti interi) -> se la rete
e' Pubblica, proposta di renderla Privata -> regola firewall `TabDeck (TCP <porta>, rete locale)`
(RemoteAddress = la sottorete, profili Private+Domain, Program = python.exe) -> collegamento in
Esecuzione automatica -> avvio + pagina `/pair`. I comandi da amministratore passano da UNA sola
elevazione (`-EncodedCommand`). `-DryRun` stampa le azioni senza farle. In disinstallazione `data/` si
cancella solo scrivendo `CANCELLA`. Il file e' solo ASCII (PowerShell 5.1 legge i file senza BOM come ANSI)
e, come i `.bat`, resta CRLF anche nello zip (`.gitattributes`: `-text`).

### Abbinamento (`/pair`, `tdqr.py`)
Pagina con il QR di `http://<IP>:<porta>/?t=<token>`. Non chiede il token, quindi risponde SOLO a richieste
che arrivano dal PC stesso (`pair_allowed`: indirizzo del client = indirizzo su cui ascolta il server, o
127.0.0.1); dagli altri dispositivi 403. `tdqr.py` e' un codificatore QR minimo (byte, livello M,
versioni 1-10) senza dipendenze.

### Aggiornamenti (`/update` + `updater.py`)
- `UPDATE_REPO` = repository GitHub. `a=check` legge `releases/latest` (tag `vX.Y.Z`, note, `zipball_url`).
- Sicurezza: solo HTTPS verso `api.github.com`, `codeload.github.com`, `github.com`, controllato anche a ogni
  reindirizzamento (`_SafeRedirect`); zip <= 20 MB; `check_zip` rifiuta percorsi con `..`, assoluti o con
  lettera di unita', piu' cartelle principali, file in `data/ cache/ backup/`, zip senza `tabdeck.py`.
- `a=apply`: scarica in `cache/update/`, controlla, copia `updater.py` in `cache/update/updater_run.py`
  (cosi' puo' sostituire se stesso), lo avvia staccato e TabDeck si chiude. `updater.py`: aspetta la
  chiusura, copia il codice in `backup/v<vecchia>/` (ultime 3), estrae lo zip (mai `data/`, nessun file
  cancellato), avvia `tabdeck.bat` e aspetta `data/update_ok.json` con la nuova versione (scritto da
  `main()` appena partito, indipendente dalla rete). Entro 45 s niente segnale -> chiude la nuova, rimette
  la copia, riavvia la vecchia. Esito in `data/update_result.json` (mostrato una volta), dettagli in
  `cache/update.log`.
- `a=rollback`: rimette l'ultima copia in `backup/`.
- Controllo automatico: 60 s dopo l'avvio, al massimo una volta al giorno, se `updchk` e' acceso; mostra solo
  un pallino sull'ingranaggio.

### Pubblicare una versione
`pubblica.bat -Note "..."`: albero pulito, `VERSION` maggiore dell'ultimo tag, controllo che nei file
pubblicati non ci siano token, segreti Discord o percorsi personali, poi tag + push + release con `gh`.

---

### Telefoni (layout e app a tutto schermo)
- Tutte le regole per i telefoni sono in fondo a `web/style.css`, in due media query: verticale
  `(max-width:600px)`; orizzontale `(max-height:500px)` E densita' >= 2 (o schermo >= 2,1:1). Il tablet
  (962x481 a densita' 1,33 con la barra di Chrome) non corrisponde a nessuna: resta identico.
- Audio in verticale sta in una schermata sola (i cursori del volume sono verticali: niente pagina da scorrere).
- Tocchi: `lastScroll` (evento scroll in cattura su tutto il documento) annulla il tocco se qualcosa scorre o
  stava scorrendo da < 150 ms; il menu finestra si apre tenendo premuto (HOLD_MS) col dito ancora giu' e
  ignora i tocchi finche' il dito non si alza (+450 ms), perche' Safari manda un "tap" al rilascio.
- App per la schermata Home: `/manifest.json?t=<token>` (display fullscreen, start_url con il token: le app
  aggiunte alla Home possono avere cookie separati) e icone pubbliche `/apple-touch-icon.png`, `/icon-512.png`.
  Su iPhone il token resta nella barra indirizzi (Safari salva quell'indirizzo per l'icona); zoom con due dita
  bloccato (`gesturestart`, `touch-action: pan-x pan-y`, body fisso).
- Link diretti per le prove: `/#mix`, `/#set-td`, ... (sezione o scheda delle impostazioni aperta all'avvio).

---

## 4. Discord (RPC locale)

- Discord espone una **named pipe** (`\\.\pipe\discord-ipc-N`). Messaggi: intestazione 8 byte
  (opcode, lunghezza) + JSON.
- **Un solo thread** possiede la pipe: su Windows lettura e scrittura sincrone sullo stesso handle si
  bloccano a vicenda. Gli eventi si leggono con `PeekNamedPipe` (non bloccante) tra un lavoro e l'altro;
  le richieste HTTP passano da `Discord.run()/call()` (coda + attesa del risultato).
- Primo accesso: `AUTHORIZE` (popup in Discord) -> codice -> token OAuth con l'app dell'utente
  (`data/discord.json`) -> salvato in `data/discord_token.json` e rinnovato da solo.
- Canale vocale: `GET_SELECTED_VOICE_CHANNEL` + iscrizione agli eventi (chi entra/esce, chi parla) solo
  per il canale attuale; si spostano quando cambi canale.
- Limite di Discord: l'RPC **non** permette di leggere o scrivere la chat.

---

## 5. Prestazioni (tablet lento: GPU debole, Chrome 81)

Regole imparate misurando sul tablet (vedi §6 per come si misura).

### Scorrimento
1. **Nessun `clip-path` su un antenato di una lista che scorre.** Crea un livello "maschera" e Chrome 81
   torna allo scorrimento lento sul processore. Misurato: impostazioni da ~12 a ~47 fotogrammi/s
   togliendolo. Gli angoli tagliati si fanno con triangoli (`:before`/`:after` con bordi).
2. **Nessun listener `touchmove` non-passivo sul documento.** Costringe ogni scorrimento ad aspettare il
   JavaScript. Il gesto a due dita aggiunge il suo listener solo durante il gesto (`gMove`).
3. Le liste che scorrono hanno `will-change: transform` e **sfondo pieno** (scorrimento fatto dalla GPU).
4. Con le impostazioni aperte la pagina sotto è nascosta (`setOpen`): niente strati trasparenti sovrapposti.

### A riposo
5. **Non riscrivere testo uguale** (`setText`): riscriverlo costringe a ridisegnare il riquadro.
   Generale a riposo: dal 9% al 2% di lavoro.
6. `contain: strict` sulle sezioni e `contain: layout paint` sui riquadri: un cambiamento resta locale.
7. Aggiornamenti: 1,5 s in Generale, 0,5 s in HD2, 0,6 s in Discord; nelle altre sezioni il "ping"
   generale scende a 4,5 s. Ogni sezione interroga il PC **solo mentre è aperta**.
8. Liste e riquadri si **ricostruiscono solo se cambia il contenuto** (chiave confrontata); se cambia solo
   lo stato (attiva, ridotta, chi parla) si aggiornano le classi. Mai ricostruire sotto il dito.
9. HD2: la parte "statica" (in arrivo, non disponibili, usi) si ridisegna solo se cambia la sua firma;
   ogni secondo si aggiornano solo i conti alla rovescia.
10. Niente animazioni CSS, transizioni, ombre sfocate o `backdrop-filter`.

### Lato PC
- Il monitor (PDH/NVML) campiona solo mentre la sezione è aperta.
- La lettura dello schermo di HD2 smette del tutto quando tutte le durate sono note.
- La pagina è unita una volta e riletta solo se un file di `web/` cambia.

---

## 6. Come lavorarci

- **Modifiche**: `web/app.js` e `web/style.css` si modificano come file normali (il server li rilegge da
  solo: basta ricaricare la pagina). `tabdeck.py` richiede il riavvio.
- **Controlli prima di riavviare**: `python -m py_compile tabdeck.py` e `node --check web\app.js`.
- **Riavvio**: dal tablet (⚙ -> TabDeck -> Riavvia) oppure chiudere la finestra "TabDeck" e rilanciare
  `TabDeck.lnk`.
- **git**: un commit per ogni passo verificato (`git log` per la storia, `git diff` per le modifiche).
- **Misurare sul tablet** (USB): `adb forward tcp:9222 localabstract:chrome_devtools_remote`, poi Chrome
  DevTools Protocol (Performance.getMetrics, Tracing con eventi `DrawFrame`, `Input.synthesizeScrollGesture`,
  LayerTree). Non usare un contatore `requestAnimationFrame` per misurare il lavoro a riposo: lo gonfia.
- **Screenshot del tablet**: `adb shell screencap -p /sdcard/td.png` + `adb pull`. L'immagine è ruotata
  (asse x dell'immagine = asse y dello schermo orizzontale).
