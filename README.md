# TabDeck

Trasforma il telefono (o un tablet) in un pannello di comandi per il PC Windows: app preferite,
volume per app, brano in riproduzione, Discord (canali vocali, muto, cuffie), touchpad e tastiera,
monitor di CPU/GPU, stratagemmi di Helldivers 2. Il PC fa da server; il telefono apre una pagina web
sulla stessa rete Wi-Fi. Nessun account, nessun servizio esterno: tutto resta in casa.

## Installazione

Serve: **Windows 10 o 11** e il **telefono sulla stessa rete Wi-Fi del PC** (il PC può anche essere
collegato al router via cavo).

1. Scarica l'ultima versione: pagina **Releases** del progetto su GitHub, file **Source code (zip)**.
2. Clic destro sullo zip, **Estrai tutto**.
3. Nella cartella estratta, doppio clic su **`installa.bat`**.

L'installer fa un passo alla volta: per ognuno spiega **cosa fa e perché** e chiede `S` (sì) o `N` (no).
Se rispondi N quel passo viene saltato e alla fine trovi il riepilogo. I passi:

- sposta TabDeck in `C:\Users\<tu>\TabDeck` (se l'hai estratto in Download) e sblocca i file scaricati;
- controlla Python e, se manca, propone di installarlo (Python 3.12 ufficiale, con winget);
- chiede conferma della **rete di casa**: TabDeck ascolterà solo lì, non sui Wi-Fi di bar o alberghi;
- se Windows considera la rete di casa "pubblica", propone di renderla "privata";
- crea la regola del **firewall** (porta 8765, solo dalla rete di casa, solo su reti private): Windows
  chiede il permesso di amministratore una volta sola;
- propone l'**avvio automatico** con Windows;
- avvia TabDeck e apre sul PC la pagina con il **codice QR**.

Vuoi vedere cosa farebbe senza cambiare nulla? `installa.bat -DryRun`.

## Collegare il telefono

Inquadra il QR con la fotocamera: TabDeck si apre già collegato. Per averlo sempre a portata, nel
browser che si è aperto: menu ⋮ → **Aggiungi a schermata Home**.

La pagina del QR si riapre in ogni momento **dal PC** all'indirizzo che l'installer mostra alla fine
(`http://<indirizzo-del-PC>:8765/pair`). Dagli altri dispositivi quella pagina non si apre: il QR contiene
la chiave di accesso, tienilo per te.

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

Doppio clic su **`disinstalla.bat`**: toglie la regola del firewall e l'avvio automatico. I tuoi dati
restano, a meno che tu non scriva `CANCELLA` quando lo chiede. Poi puoi cancellare la cartella.

## Limiti da sapere

- **Schermo del telefono**: per ora l'aspetto è quello del tablet, rimpicciolito. Usalo in orizzontale.
  Una versione pensata per il telefono arriverà con un aggiornamento.
- **Helldivers 2**: la lettura dello schermo (Sync dell'equipaggiamento, ricariche) è tarata sul gioco
  **in italiano a 1920×1080**. Con altre lingue o risoluzioni i pulsanti degli stratagemmi funzionano,
  la lettura automatica probabilmente no.
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
| `installa.ps1` + `.bat` | installazione e disinstallazione guidate |
| `data/` | **tue impostazioni e chiavi** (token, rete, Discord): mai condividerla, mai toccata dagli aggiornamenti |
| `cache/`, `backup/` | file rigenerabili e copie delle versioni precedenti |
| `docs/ARCHITETTURA.md` | come funziona, sicurezza, prestazioni |

## Per chi lo sviluppa

- Avvio a mano: `tabdeck.bat` (oppure `python tabdeck.py --open`; con adb apre la pagina sul tablet
  collegato via USB). Opzione `--host IP` per forzare l'indirizzo.
- Test: `python -m unittest discover -s tests`.
- Nuova versione: aumenta `VERSION` in `tabdeck.py`, fai il commit, poi `pubblica.bat -Note "cosa cambia"`.
- Dettagli: `docs/ARCHITETTURA.md`.
