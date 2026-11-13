# TabDeck

Trasforma il telefono (o un tablet) in un pannello di comandi per il PC Windows: app preferite,
volume per app, brano in riproduzione, Discord (canali vocali, muto, cuffie), touchpad e tastiera,
monitor di CPU/GPU, stratagemmi di Helldivers 2. Il PC fa da server; il telefono apre una pagina web
sulla stessa rete Wi-Fi. Nessun account, nessun servizio esterno: tutto resta in casa.

## Installazione

Serve: **Windows 10 o 11** e il **telefono sulla stessa rete Wi-Fi del PC** (il PC può anche essere
collegato al router via cavo).

1. Scarica **`TabDeck-Setup.exe`** dall'ultima versione: <https://github.com/MannAk1/TabDeck/releases/latest>.
2. Aprilo. Windows probabilmente dirà **"Windows ha protetto il PC"**: è normale per i programmi senza firma
   digitale a pagamento. Clicca **Ulteriori informazioni** → **Esegui comunque**.
3. Avanti → **Installa** → lascia spuntato *Configura TabDeck adesso* → **Fine**.

Il programma si installa solo per il tuo utente (non chiede l'amministratore) e crea l'icona **TabDeck** sul
Desktop e nel menu Start. Alla fine parte la **configurazione guidata**: un passo alla volta, per ognuno
spiega **cosa fa e perché** e chiede `S` (sì) o `N` (no). Se rispondi N quel passo viene saltato e alla fine
trovi il riepilogo. I passi:

- sblocca i file scaricati;
- controlla Python e, se manca, propone di installarlo (Python 3.12 ufficiale, con winget);
- chiede conferma della **rete di casa**: TabDeck ascolterà solo lì, non sui Wi-Fi di bar o alberghi;
- se Windows considera la rete di casa "pubblica", propone di renderla "privata";
- crea la regola del **firewall** (porta 8765, solo dalla rete di casa, solo su reti private): Windows
  chiede il permesso di amministratore una volta sola;
- propone l'**avvio automatico** con Windows;
- avvia TabDeck e apre sul PC la pagina con il **codice QR**.

La configurazione si può rifare quando vuoi (es. se cambi rete o router): menu Start → **TabDeck - Configura**.

In alternativa al setup: scarica **Source code (zip)**, estrailo e fai doppio clic su `installa.bat`
(stessi passi; se lo estrai in Download propone di spostarlo in `C:\Users\<tu>\TabDeck`).

## Collegare il telefono

Doppio clic sull'icona **TabDeck** (Desktop o menu Start): si apre la finestra di TabDeck con lo stato, il
**codice QR** e i dispositivi collegati. Inquadra il QR con la fotocamera: TabDeck si apre già collegato. Per
averlo sempre a portata, nel browser che si è aperto: menu ⋮ (o Condividi su iPhone) → **Aggiungi a schermata Home**.

Sul telefono: le **finestre aperte** del PC sono nella fascia a destra (tocco = la porta davanti; la freccia in alto
mostra i titoli). In basso a destra: ⚙ impostazioni e il quadrato delle sezioni. I pulsanti di Generale si
scelgono e si riordinano (trascinandoli) da ⚙ → **Pulsanti**; lo schermo intero si toglie da ⚙ → **Aspetto**.

Chiudendo la finestra TabDeck resta attivo: la sua icona è vicino all'orologio (clic = riapri, clic destro =
Riavvia / Esci). All'accensione del PC parte già nascosto, solo con l'icona.

**Approvazione dei dispositivi**: con l'opzione "Richiedi approvazione per i nuovi dispositivi" (accesa sulle
installazioni nuove) un telefono nuovo mostra un codice di 4 cifre e la finestra sul PC lo stesso codice:
premi **Approva**. Il QR contiene la chiave di accesso: tienilo per te. Se il link finisce in giro, **Nuovo link**
lo invalida (i dispositivi già approvati restano collegati).

## Aggiornare

Sul telefono: ⚙ → **TabDeck** → **Cerca aggiornamenti**. Se c'è una nuova versione vedi cosa cambia; con
**Aggiorna**:

- le tue impostazioni (cartella `data`) **non vengono toccate**;
- la versione attuale viene salvata in `backup`;
- se la nuova versione non parte, TabDeck rimette da solo quella di prima;
- **Torna alla versione precedente** riporta indietro anche a mano.

Con "Controlla aggiornamenti all'avvio" attivo, TabDeck chiede a GitHub una volta al giorno se c'è una
versione nuova e mostra un pallino sull'ingranaggio. Non installa mai nulla da solo. È l'unico
collegamento a Internet che fa TabDeck (oltre alle immagini degli avatar di Discord).

## Disinstallare

Impostazioni di Windows → **App installate** → TabDeck → **Disinstalla** (oppure menu Start →
**Disinstalla TabDeck**). Si apre la finestra che toglie la regola del firewall e l'avvio automatico: alla
fine premi un tasto per chiuderla e Windows rimuove il resto. I tuoi dati (impostazioni, chiave del
telefono, Discord) restano, a meno che tu non scriva `CANCELLA` quando lo chiede.

Se avevi installato dallo zip: doppio clic su `disinstalla.bat`, poi cancella la cartella.

## Limiti da sapere

- **Telefono**: funziona sia in verticale che in orizzontale. Per averlo **a tutto schermo** aggiungilo alla
  schermata Home (Android: menu ⋮ → *Aggiungi a schermata Home*; iPhone: Safari → Condividi → *Aggiungi alla
  schermata Home*) e aprilo dall'icona. Su iPhone tenere premuto un riquadro può a volte richiedere un secondo tentativo.
- **Helldivers 2**: la lettura dello schermo (Sync dell'equipaggiamento, ricariche) è tarata sul gioco
  **in italiano a 1920×1080**. Con altre lingue o risoluzioni i pulsanti degli stratagemmi funzionano,
  la lettura automatica probabilmente no.
- **YouTube**: cerca e scegli video e musica dal telefono; suonano in una finestra "TabDeck YouTube" del browser
  del PC, che si apre da sola la prima volta e poi resta dietro (anche mentre giochi). La prima volta il browser
  può bloccare l'avvio automatico: in Firefox vai in *Impostazioni → Privacy e sicurezza → Permessi →
  Riproduzione automatica → Impostazioni…* e consenti audio e video per `http://localhost:8865`.
  Alcuni video non si possono incorporare: per quelli TabDeck propone "Apri su YouTube".
- **Discord**: serve una tua "app" Discord (gratis, 2 minuti):
  1. vai su <https://discord.com/developers/applications> → **New Application** (nome a piacere);
  2. **OAuth2** → **Redirects** → aggiungi `http://localhost` → salva;
  3. copia **Client ID** e **Client Secret** (Reset Secret se non lo vedi);
  4. crea il file `data\discord.json` nella cartella di TabDeck con il Blocco note:
     `{"client_id": "IL_TUO_CLIENT_ID", "client_secret": "IL_TUO_CLIENT_SECRET"}`
  5. apri la sezione Discord sul telefono e conferma il popup "Autorizza" che compare in Discord sul PC.

## Problemi comuni

- **Il telefono non si collega (pagina che carica all'infinito)**: telefono e PC sono sulla stessa rete?
  Alcuni telefoni passano da soli ai dati mobili: controlla l'icona del Wi-Fi. Se hai cambiato rete o
  router, rilancia `installa.bat`.
- **"403 Forbidden"**: questo browser non è collegato. Riapri la pagina del QR sul PC e inquadralo di nuovo.
- **La finestra di TabDeck dice "rete non consentita"**: il PC è su una rete diversa da quella scelta
  durante l'installazione. Rilancia `installa.bat` dalla rete di casa.

## Cartelle

| Percorso | Contenuto |
|---|---|
| `tabdeck.py`, `tdqr.py`, `updater.py` | il programma (solo libreria standard di Python) |
| `web/` | la pagina mostrata sul telefono |
| `installa.ps1` + `.bat`, `apri.ps1` | configurazione e disinstallazione guidate, icona "TabDeck" |
| `data/` | **tue impostazioni e chiavi** (token, rete, Discord): mai condividerla, mai toccata dagli aggiornamenti |
| `cache/`, `backup/` | file rigenerabili e copie delle versioni precedenti |
| `docs/ARCHITETTURA.md` | come funziona, sicurezza, prestazioni |

## Per chi lo sviluppa

- Avvio a mano: `tabdeck.bat` (oppure `python tabdeck.py --open`; con adb apre la pagina sul tablet
  collegato via USB). Opzione `--host IP` per forzare l'indirizzo.
- Test: `python -m unittest discover -s tests`.
- Nuova versione: aumenta `VERSION` in `tabdeck.py`, fai il commit, poi `pubblica.bat -Note "cosa cambia"` (crea anche `TabDeck-Setup.exe` con Inno Setup 6 da `installer/TabDeck.iss` e lo allega al rilascio).
- Dettagli: `docs/ARCHITETTURA.md`.
