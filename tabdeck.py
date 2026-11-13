"""TabDeck - pannello di comandi per Windows, usato dal browser di un tablet.

Avvio:  python tabdeck.py [--open] [--host IP]
  --open  apre la pagina sul tablet via adb quando lo trova collegato
  --host  IP su cui ascoltare (default: quello del PC sull'hotspot; scavalca ALLOWED_NETS)

Solo libreria standard di Python + ctypes: niente pacchetti esterni da installare o di cui fidarsi.
Documentazione completa (funzionamento, sicurezza, prestazioni): docs\\ARCHITETTURA.md

MAPPA DEL FILE (cerca il titolo della sezione)
  configurazione ....... PULSANTI, GROUPS, FAVORITES, HELLDIVERS 2 - stratagemmi, NAV, ICONS, VK
  righe modificabili ... "Righe di Generale modificabili" (data\\layout.json, scorciatoie personali)
  Windows .............. volume, finestre aperte, icone dei programmi, mixer, "in riproduzione",
                         monitor (PDH/NVML), OCR, input (SendInput), touchpad e tastiera
  Discord .............. client RPC sulla named pipe locale (classe Discord)
  Helldivers 2 ......... invio codici, ricariche/arrivo, lettura menu e HUD dallo schermo, Sync
  pagina ............... PAGINA WEB (web\\*.html/css/js uniti in memoria), render_page
  server ............... class Handler (ogni richiesta HTTP), main(), riavvio, adb

PRINCIPI
  Sicurezza: ogni richiesta richiede il token; si ascolta solo sull'hotspot; dalla rete si attivano
    solo pulsanti/valori previsti (mai comandi o percorsi liberi); i programmi partono senza shell;
    nessun segreto nei log. Mai leggere la memoria dei giochi: solo schermo e tastiera.
  Prestazioni: il tablet e' lento -> il PC fa il lavoro, il tablet riceve poco JSON e aggiorna solo
    cio' che cambia. Ogni sezione interroga il PC solo mentre e' aperta; i lavori pesanti (monitor,
    lettura schermo) girano solo quando servono.
"""

# ---------------------------------------------------------------------------
# PULSANTI. "keys" = combinazione di tasti (nomi in VK sotto, premuti in ordine
# e rilasciati in ordine inverso). "run" = programma da avviare (lista argv,
# niente shell). Dalla rete si può attivare SOLO un "id" presente qui.
# ---------------------------------------------------------------------------
import os

PF, PF86 = r"C:\Program Files", r"C:\Program Files (x86)"
LAD = os.path.expandvars(r"%LOCALAPPDATA%")
STEAM = PF86 + r"\Steam\steam.exe"


def appx(aumid):
    """Avvia un'app dello Store (Firefox, Xbox, ...) tramite il suo AppUserModelID."""
    return ["explorer.exe", "shell:AppsFolder\\" + aumid]


# "cat" = colore: media, edit, win, app, game.  "icon" = icona in ICONS; "mono" = sigla al posto dell'icona.
# "sec" = sezione della scheda Generale (SECTIONS) oppure "media" (pannello audio).
# "group" = dentro un gruppo che si apre (GROUPS). Le app il cui .exe non esiste vengono nascoste.
# "proc" = nomi dei processi da cercare tra le finestre aperte (se diversi dal .exe di "run");
# "tab" = sezione di TabDeck da aprire quando l'app e' gia' attiva; "iconsrc" = file da cui prendere l'icona.
SECTIONS = [("avvio", "Preferiti"), ("sistema", "Sistema"), ("strumenti", "Strumenti")]
# Riga Preferiti, da sinistra a destra (a destra = vicino alla mano). In fondo c'e' sempre "Altre app"
# con tutti i gruppi (Browser, Launcher, Giochi). Ogni id deve esistere in BUTTONS.
# "_yt" = riquadro YouTube (tocco = sezione YouTube, scorri su = player sul PC); Spotify resta in "Altre app".
DEFAULT_FAV = ["firefox", "_yt", "discord", "steam", "helldivers2"]
FAVORITES = list(DEFAULT_FAV)
GROUPS = [
    {"id": "browser",  "sec": "avvio", "cat": "app",  "icon": "globe", "label": "Browser"},
    {"id": "launcher", "sec": "avvio", "cat": "game", "icon": "pad",   "label": "Launcher"},
    {"id": "giochi",   "sec": "avvio", "cat": "game", "icon": "target", "label": "Giochi"},
]
BUTTONS = [
    {"id": "prev",       "sec": "media", "cat": "media", "icon": "prev", "label": "Precedente",   "keys": ["MEDIA_PREV"]},
    {"id": "play_pause", "sec": "media", "cat": "media", "icon": "play", "label": "Play / Pausa", "keys": ["MEDIA_PLAY_PAUSE"]},
    {"id": "next",       "sec": "media", "cat": "media", "icon": "next", "label": "Successiva",   "keys": ["MEDIA_NEXT"]},

    {"id": "helldivers2", "group": "giochi", "cat": "game", "mono": "HD", "label": "HELLDIVERS 2", "hint": "Steam",
     "run": [STEAM, "-applaunch", "553850"], "proc": ["helldivers2.exe"], "tab": "hd2",
     "iconsrc": PF86 + r"\Steam\steamapps\common\Helldivers 2\bin\helldivers2.exe"},

    {"id": "spotify", "sec": "avvio", "cat": "media", "mono": "SP", "label": "Spotify", "hint": "musica",
     "run": appx("SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify"), "proc": ["spotify.exe"]},
    {"id": "discord", "sec": "avvio", "cat": "app", "mono": "DC", "label": "Discord", "hint": "app",
     "run": [LAD + r"\Discord\Update.exe", "--processStart", "Discord.exe"], "proc": ["discord.exe"],
     "iconsrc": LAD + r"\Discord\app.ico", "tab": "dc"},

    {"id": "screenshot", "sec": "sistema", "cat": "win", "icon": "camera",   "label": "Screenshot",      "hint": "Win+Stamp",   "keys": ["WIN", "PRINTSCREEN"]},
    {"id": "snip",       "sec": "sistema", "cat": "win", "icon": "scissors", "label": "Ritaglio",        "hint": "Win+Shift+S", "keys": ["WIN", "SHIFT", "S"]},
    {"id": "desktop",    "sec": "sistema", "cat": "win", "icon": "monitor",  "label": "Desktop",         "hint": "Win+D",       "keys": ["WIN", "D"]},
    {"id": "alt_tab",    "sec": "sistema", "cat": "win", "icon": "windows",  "label": "Cambia finestra", "hint": "Alt+Tab",     "keys": ["ALT", "TAB"]},
    {"id": "task_view",  "sec": "sistema", "cat": "win", "icon": "grid",     "label": "Task View",       "hint": "Win+Tab",     "keys": ["WIN", "TAB"]},
    {"id": "taskmgr",    "sec": "sistema", "cat": "win", "icon": "chart",    "label": "Gestione attivit\u00e0", "hint": "app",  "run": ["taskmgr.exe"]},
    {"id": "lock",       "sec": "sistema", "cat": "win", "icon": "lock",     "label": "Blocca PC",       "hint": "Win+L",       "keys": ["WIN", "L"]},
    {"id": "run",        "sec": "sistema", "cat": "win", "icon": "monitor",  "label": "Esegui",          "hint": "Win+R",       "keys": ["WIN", "R"]},

    {"id": "copy",       "sec": "strumenti", "cat": "edit", "icon": "copy",   "label": "Copia",        "hint": "Ctrl+C", "keys": ["CTRL", "C"]},
    {"id": "paste",      "sec": "strumenti", "cat": "edit", "icon": "paste",  "label": "Incolla",      "hint": "Ctrl+V", "keys": ["CTRL", "V"]},
    {"id": "undo",       "sec": "strumenti", "cat": "edit", "icon": "undo",   "label": "Annulla",      "hint": "Ctrl+Z", "keys": ["CTRL", "Z"]},
    {"id": "explorer",   "sec": "avvio",     "cat": "app",  "icon": "folder", "label": "Esplora file", "hint": "app",    "run": ["explorer.exe"]},
    {"id": "notepad",    "sec": "strumenti", "cat": "app",  "icon": "note",   "label": "Blocco note",  "hint": "app",    "run": ["notepad.exe"]},
    {"id": "calc",       "sec": "strumenti", "cat": "app",  "icon": "calc",   "label": "Calcolatrice", "hint": "app",    "run": ["calc.exe"], "proc": ["calculatorapp.exe"]},

    {"id": "chrome",   "group": "browser", "cat": "app", "mono": "CH", "label": "Chrome",   "run": [PF + r"\Google\Chrome\Application\chrome.exe"]},
    {"id": "edge",     "group": "browser", "cat": "app", "mono": "ED", "label": "Edge",     "run": [PF86 + r"\Microsoft\Edge\Application\msedge.exe"]},
    {"id": "opera_gx", "group": "browser", "cat": "app", "mono": "GX", "label": "Opera GX", "run": [LAD + r"\Programs\Opera GX\opera.exe"]},
    {"id": "firefox",  "group": "browser", "cat": "app", "mono": "FF", "label": "Firefox",  "run": appx("Mozilla.Firefox_n80bbvh6b1yt2!App"), "proc": ["firefox.exe"]},

    {"id": "steam",     "group": "launcher", "cat": "game", "mono": "ST", "label": "Steam",           "run": [STEAM]},
    {"id": "epic",      "group": "launcher", "cat": "game", "mono": "EP", "label": "Epic Games",      "run": [PF86 + r"\Epic Games\Launcher\Portal\Binaries\Win64\EpicGamesLauncher.exe"]},
    {"id": "gog",       "group": "launcher", "cat": "game", "mono": "GG", "label": "GOG Galaxy",      "run": [PF86 + r"\GOG Galaxy\GalaxyClient.exe"]},
    {"id": "ea",        "group": "launcher", "cat": "game", "mono": "EA", "label": "EA app",          "run": [PF + r"\Electronic Arts\EA Desktop\EA Desktop\EADesktop.exe"]},
    {"id": "ubisoft",   "group": "launcher", "cat": "game", "mono": "UB", "label": "Ubisoft Connect", "run": [PF86 + r"\Ubisoft\Ubisoft Game Launcher\UbisoftConnect.exe"], "proc": ["upc.exe", "ubisoftconnect.exe"]},
    {"id": "riot",      "group": "launcher", "cat": "game", "mono": "RI", "label": "Riot Client",     "run": [r"C:\Riot Games\Riot Client\RiotClientServices.exe"], "proc": ["riotclientux.exe", "riotclientservices.exe"]},
    {"id": "xbox",      "group": "launcher", "cat": "game", "mono": "XB", "label": "Xbox",            "run": appx("Microsoft.GamingApp_8wekyb3d8bbwe!Microsoft.Xbox.App"), "proc": ["xboxpcapp.exe"]},
    {"id": "minecraft", "group": "launcher", "cat": "game", "mono": "MC", "label": "Minecraft",       "run": appx("Microsoft.4297127D64EC6_8wekyb3d8bbwe!Minecraft"), "proc": ["minecraft.windows.exe"]},
    {"id": "prism",     "group": "launcher", "cat": "game", "mono": "PR", "label": "Prism Launcher",  "run": [LAD + r"\Programs\PrismLauncher\prismlauncher.exe"]},
    {"id": "meta",      "group": "launcher", "cat": "game", "mono": "MH", "label": "Meta Horizon",    "run": [PF + r"\Meta Horizon\Support\oculus-client\Client.exe"]},
]


def installed(b):
    """Nasconde i pulsanti che avviano un .exe (percorso assoluto) che non esiste piu'."""
    run = b.get("run")
    return not run or not os.path.isabs(run[0]) or os.path.isfile(run[0])


# ---------------------------------------------------------------------------
# HELLDIVERS 2 - stratagemmi (scheda separata). Codici: U=su D=giu L=sinistra
# R=destra. Se Arrowhead cambia un codice con una patch, correggilo qui.
# Lo stratagemma viene digitato SOLO se la finestra in primo piano e' HD2.
# ---------------------------------------------------------------------------
HD2 = {
    "menu": "LCTRL",                                     # tasto "apri stratagemmi" (tenuto premuto)
    # direzioni: la scelta WASD/frecce si fa dal menu impostazioni sul tablet
    # (in gioco: opzione per inserire gli stratagemmi con le frecce senza fermarsi)
    "dirs": {"wasd": {"U": "W", "D": "S", "L": "A", "R": "D"},
             "arrows": {"U": "UP", "D": "DOWN", "L": "LEFT", "R": "RIGHT"}},
    "open_ms": 60,   # attesa dopo aver premuto il tasto menu
    "hold_ms": 35,   # durata di ogni direzione
    "gap_ms": 35,    # pausa tra una direzione e l'altra
    "window": "HELLDIVERS",                               # testo nel titolo della finestra del gioco
}

# Gruppi come nel gioco; il colore e' quello delle icone in gioco:
# mis = giallo (missione), off = rosso (offensivi), sup = blu (rifornimenti), def = verde (difensivi).
# Codici verificati su helldivers.wiki.gg/wiki/Stratagems il 2026-11-10.
STRATAGEMS = [
    ("Missione", "mis", [
        ("reinforce", "Reinforce", "UDRLU"),
        ("resupply", "Resupply", "DDUR"),
        ("sos", "SOS Beacon", "UDRU"),
        ("eagle_rearm", "Eagle Rearm", "UULUR"),
        ("hellbomb", "Hellbomb", "DULDURDU"),
        ("seaf", "SEAF Artillery", "RUUD"),
    ]),
    ("Orbitali", "off", [
        ("o_precision", "Orbital Precision Strike", "RRU"),
        ("o_gatling", "Orbital Gatling Barrage", "RDLUU"),
        ("o_airburst", "Orbital Airburst Strike", "RRR"),
        ("o_120", "Orbital 120mm HE Barrage", "RRDLRD"),
        ("o_380", "Orbital 380mm HE Barrage", "RDUULDD"),
        ("o_walking", "Orbital Walking Barrage", "RDRDRD"),
        ("o_laser", "Orbital Laser", "RDURD"),
        ("o_napalm", "Orbital Napalm Barrage", "RRDLRU"),
        ("o_railcannon", "Orbital Railcannon Strike", "RUDDR"),
        ("o_gas", "Orbital Gas Strike", "RRDR"),
        ("o_ems", "Orbital EMS Strike", "RRLD"),
        ("o_smoke", "Orbital Smoke Strike", "RRDU"),
    ]),
    ("Eagle", "off", [
        ("e_strafe", "Eagle Strafing Run", "URR"),
        ("e_airstrike", "Eagle Airstrike", "URDR"),
        ("e_cluster", "Eagle Cluster Bomb", "URDDR"),
        ("e_napalm", "Eagle Napalm Airstrike", "URDU"),
        ("e_smoke", "Eagle Smoke Strike", "URUD"),
        ("e_rockets", "Eagle 110mm Rocket Pods", "URUL"),
        ("e_500", "Eagle 500kg Bomb", "URDDD"),
        ("e_gas", "Eagle Gas Airstrike", "URLR"),
    ]),
    ("Armi di supporto", "sup", [
        ("w_mg", "MG-43 Machine Gun", "DLDUR"),
        ("w_hmg", "MG-206 Heavy Machine Gun", "DLUDD"),
        ("w_stalwart", "M-105 Stalwart", "DLDUUL"),
        ("w_amr", "APW-1 Anti-Materiel Rifle", "DLRUD"),
        ("w_eat", "EAT-17 Expendable Anti-Tank", "DDLUR"),
        ("w_commando", "MLS-4X Commando", "DLUDR"),
        ("w_rr", "GR-8 Recoilless Rifle", "DLRRL"),
        ("w_spear", "FAF-14 Spear", "DDUDD"),
        ("w_quasar", "LAS-99 Quasar Cannon", "DDULR"),
        ("w_autocannon", "AC-8 Autocannon", "DLDUUR"),
        ("w_railgun", "RS-422 Railgun", "DRDULR"),
        ("w_flamer", "FLAM-40 Flamethrower", "DLUDU"),
        ("w_gl", "GL-21 Grenade Launcher", "DLULD"),
        ("w_laser", "LAS-98 Laser Cannon", "DLDUL"),
        ("w_arc", "ARC-3 Arc Thrower", "DRDULL"),
        ("w_airburst", "RL-77 Airburst Rocket Launcher", "DUULR"),
        ("w_wasp", "StA-X3 W.A.S.P. Launcher", "DDUDR"),
        ("w_apex", "AMW-20 Apex", "DLLUDL"),
        ("w_hammer", "CQC-20 Breaching Hammer", "DLRLU"),
        ("w_bulletstorm", "MGX-42 Bullet Storm", "DLDRUL"),
        ("w_epoch", "PLAS-45 Epoch", "DLULR"),
        ("w_speargun", "S-11 Speargun", "DRDLUR"),
        ("w_leveller", "EAT-411 Leveller", "DDLUD"),
        ("w_eat_napalm", "EAT-700 Expendable Napalm", "DDLUL"),
        ("w_defoliation", "CQC-9 Defoliation Tool", "DLRRD"),
        ("w_deescalator", "GL-52 De-Escalator", "DRULR"),
        ("w_sterilizer", "TX-41 Sterilizer", "DLUDL"),
        ("w_c4", "B/MD C4 Pack", "DRUURU"),
        ("w_solo_silo", "MS-11 Solo Silo", "DURDD"),
        ("w_cremator", "B/FLAM-80 Cremator", "DDRDUU"),
        ("w_flag", "CQC-1 One True Flag", "DLRRU"),
        ("w_beltfed_gl", "GL-28 Belt-Fed Grenade Launcher", "DLULUU"),
        ("w_maxigun", "M-1000 Maxigun", "DLRDUU"),
        ("w_nova", "LAS-44 Nova", "DLRDD"),
        ("w_meltagun", "40-K Meltagun", "DLULLD"),
    ]),
    ("Zaini", "sup", [
        ("b_supply", "B-1 Supply Pack", "DLDUUD"),
        ("b_jump", "LIFT-850 Jump Pack", "DUUDU"),
        ("b_ballistic", "SH-20 Ballistic Shield", "DLDDUL"),
        ("b_dog", "AX/AR-23 Guard Dog", "DULURD"),
        ("b_rover", "AX/LAS-5 Rover", "DULURR"),
        ("b_shield", "SH-32 Shield Generator Pack", "DULRLR"),
        ("b_directional", "SH-51 Directional Shield", "DULRUU"),
        ("b_hotdog", "AX/FLAM-75 Hot Dog", "DULULL"),
        ("b_hellbomb", "B-100 Portable Hellbomb", "DRUUU"),
        ("b_k9", "AX/ARC-3 K-9", "DULURL"),
        ("b_hover", "LIFT-860 Hover Pack", "DUUDLR"),
        ("b_dogbreath", "AX/TX-13 Dog Breath", "DULURU"),
        ("b_warp", "LIFT-182 Warp Pack", "DLRDLR"),
    ]),
    ("Veicoli", "sup", [
        ("x_patriot", "EXO-45 Patriot Exosuit", "LDRULDD"),
        ("x_emancipator", "EXO-49 Emancipator Exosuit", "LDRULDU"),
        ("x_breakthrough", "EXO-55 Breakthrough Exosuit", "LDRLRDU"),
        ("x_lumberer", "EXO-51 Lumberer Exosuit", "LDRURLU"),
        ("v_gunner_frv", "M-102 Gunner FRV", "LDRDRDU"),
        ("v_supply_frv", "M-103 Supply FRV", "LDLLDUR"),
        ("v_incinerator_frv", "M-104 Incinerator FRV", "LDRLDUU"),
        ("v_bastion", "TD-220 Bastion MK XVI", "LDRDLDUDU"),
        ("v_maelstrom", "TD-110 Maelstrom", "LDRDLDULR"),
    ]),
    ("Sentinelle", "def", [
        ("s_mg", "A/MG-43 Machine Gun Sentry", "DURRU"),
        ("s_gatling", "A/G-16 Gatling Sentry", "DURL"),
        ("s_autocannon", "A/AC-8 Autocannon Sentry", "DURULU"),
        ("s_rocket", "A/MLS-4X Rocket Sentry", "DURRL"),
        ("s_mortar", "A/M-12 Mortar Sentry", "DURRD"),
        ("s_ems", "A/M-23 EMS Mortar Sentry", "DURDR"),
        ("s_tesla", "A/ARC-3 Tesla Tower", "DURULR"),
        ("s_laser", "A/LAS-98 Laser Sentry", "DURDUR"),
        ("s_flame", "A/FLAM-40 Flame Sentry", "DURDUU"),
        ("s_gas_mortar", "A/GM-17 Gas Mortar Sentry", "DURDL"),
    ]),
    ("Postazioni e mine", "def", [
        ("s_mines", "MD-6 Anti-Personnel Minefield", "DLUR"),
        ("s_incendiary", "MD-I4 Incendiary Mines", "DLLD"),
        ("s_at_mines", "MD-17 Anti-Tank Mines", "DLUU"),
        ("s_gas_mines", "MD-8 Gas Mines", "DLLR"),
        ("s_relay", "FX-12 Shield Generator Relay", "DDLRLR"),
        ("s_hmg", "E/MG-101 HMG Emplacement", "DULRRL"),
        ("s_grenadier", "E/GL-21 Grenadier Battlement", "DRDLR"),
        ("s_at_emplacement", "E/AT-12 Anti-Tank Emplacement", "DULRRR"),
    ]),
    ("Obiettivi", "mis", [
        ("m_flag", "Super Earth Flag", "DUDU"),
        ("m_upload", "Upload Data", "LRUUU"),
        ("m_seismic", "Seismic Probe", "UULRDD"),
        ("m_sssd", "SSSD Delivery", "DDDUU"),
        ("m_prospecting", "Prospecting Drill", "DDLRDD"),
        ("m_hive_drill", "Hive Breaker Drill", "LUDRDD"),
        ("m_tectonic", "Tectonic Drill", "UDUDUD"),
        ("m_extraction_drill", "E-711 Extraction Drill", "DDLLDD"),
        ("m_aquifer", "Aquifer Drill", "LLLUDRDD"),
        ("m_cargo", "Cargo Container", "UUDDRD"),
        ("m_comms_relay", "Portable Comms Relay", "UUDDLLD"),
        ("m_dark_fluid", "Dark Fluid Vessel", "ULRDUU"),
        ("m_camera", "Tactical Video Camera", "RDDULLU"),
        ("m_super_destroyer", "Call In Super Destroyer", "UUDDLRLR"),
    ]),
]

# Sempre disponibili in missione (non si scelgono): mostrati accanto all'equipaggiamento.
# Ricarica di base in secondi (APPROSSIMATIVA: i moduli della nave la riducono).
# Si possono correggere in hd2_cooldowns.json, es. {"o_laser": 270, "w_mg": 420}. 0 = nessun timer.
COOLDOWN_DEFAULT = {"sup": 480, "def": 150, "off": 120, "mis": 0}
COOLDOWNS = {
    "resupply": 180, "eagle_rearm": 150,
    "o_precision": 90, "o_gatling": 70, "o_airburst": 100, "o_120": 180, "o_380": 240, "o_walking": 240,
    "o_laser": 300, "o_napalm": 240, "o_railcannon": 210, "o_gas": 75, "o_ems": 75, "o_smoke": 100,
    "e_strafe": 15, "e_airstrike": 15, "e_cluster": 15, "e_napalm": 15, "e_smoke": 15, "e_rockets": 15,
    "e_500": 15, "e_gas": 15,
    "w_eat": 70, "w_leveller": 70, "w_eat_napalm": 70, "w_commando": 120,
    "x_patriot": 600, "x_emancipator": 600, "x_breakthrough": 600, "x_lumberer": 600,
    "v_bastion": 600, "v_maelstrom": 600,
    "s_mg": 90, "s_mortar": 180, "s_ems": 180, "s_gas_mortar": 180,
    "s_mines": 120, "s_incendiary": 120, "s_at_mines": 120, "s_gas_mines": 120, "s_relay": 90,
    "s_hmg": 180, "s_grenadier": 180, "s_at_emplacement": 180,
}

# "eagle_rearm" compare solo se nell'equipaggiamento c'e' almeno un Eagle.
ALWAYS = ["reinforce", "resupply", "sos", "eagle_rearm"]

# Sezioni della pagina, nell'ordine del menu (e dello scorrimento a due dita).
# (id del pannello, nome, descrizione, icona)
NAV = [
    ("grid", "Generale", "Volume, app e scorciatoie", "grid"),
    ("mix", "Audio", "Brano in riproduzione e volume per app", "music"),
    ("yt", "YouTube", "Cerca e scegli video e musica", "play"),
    ("dc", "Discord", "Server, canali vocali e chiamata", "headset"),
    ("pad", "Touchpad", "Mouse e tastiera del PC", "mouse"),
    ("mon", "Monitor", "CPU, GPU, memoria, rete e disco", "chart"),
    ("hd2", "Helldivers 2", "Stratagemmi ed equipaggiamento", "target"),
]

VERSION = "1.3.0"
# Valori predefiniti (quelli del PC originale); data\config.json, scritto dall'installer, li sostituisce.
PORT = 8765
# Reti su cui TabDeck accetta di ascoltare (prefisso dell'indirizzo del PC). 172.20.10.x = hotspot dell'iPhone.
ALLOWED_NETS = ("172.20.10.",)
ADB_PATH = None
# Tasti speciali della scheda Touchpad (griglia 4 colonne). Combinazioni con "+".
PAD_KEYS = [("ESC", "Esc"), ("TAB", "Tab"), ("WIN", "Win"), ("BACKSPACE", "&larr; Bksp"),
            ("HOME", "Inizio"), ("UP", "&#9650;"), ("END", "Fine"), ("DELETE", "Canc"),
            ("LEFT", "&#9664;"), ("DOWN", "&#9660;"), ("RIGHT", "&#9654;"), ("ENTER", "Invio"),
            ("PAGEUP", "Pag &#9650;"), ("PAGEDOWN", "Pag &#9660;"), ("CTRL+A", "Ctrl+A"), ("SPACE", "Spazio")]
HOLD_MS = 550   # tenendo premuto uno stratagemma piu' a lungo, ne mostra il nome senza attivarlo

# Icone dei pulsanti (SVG 24x24, tratto). Disegni originali semplici.
ICONS = {
    "vol_down": "M3 9h4l5-4v14l-5-4H3z M16 12h5",
    "mute":     "M3 9h4l5-4v14l-5-4H3z M16 9l5 6 M21 9l-5 6",
    "vol_up":   "M3 9h4l5-4v14l-5-4H3z M15.5 12h6 M18.5 9v6",
    "prev":     "M5 5v14 M19 5L8 12l11 7z",
    "play":     "M3 5l9 7-9 7z M15 5v14 M20 5v14",
    "next":     "M19 5v14 M5 5l11 7-11 7z",
    "copy":     "M9 8h11v12H9z M15 8V4H4v12h5",
    "paste":    "M8 3h8v4H8z M6 5H4v16h16V5h-2",
    "undo":     "M9 14L4 9l5-5 M4 9h10a6 6 0 0 1 0 12h-3",
    "camera":   "M3 7h4l2-3h6l2 3h4v13H3z M12 10a3.5 3.5 0 1 0 0 7a3.5 3.5 0 1 0 0-7",
    "scissors": "M6 3a3 3 0 1 0 0 6a3 3 0 1 0 0-6 M6 15a3 3 0 1 0 0 6a3 3 0 1 0 0-6 M8.5 7.5L20 19 M8.5 16.5L20 5",
    "monitor":  "M3 4h18v12H3z M8 20h8 M12 16v4",
    "windows":  "M3 8h13v11H3z M8 8V4h13v11h-5",
    "grid":     "M4 4h7v7H4z M13 4h7v7h-7z M4 13h7v7H4z M13 13h7v7h-7z",
    "lock":     "M5 11h14v10H5z M8 11V7a4 4 0 0 1 8 0v4 M12 15v2",
    "folder":   "M3 6h6l2 2h10v11H3z",
    "note":     "M6 3h12v18H6z M9 8h6 M9 12h6 M9 16h3",
    "calc":     "M5 3h14v18H5z M8 6h8v4H8z M8 14h.01 M12 14h.01 M16 14h.01 M8 18h.01 M12 18h.01 M16 18h.01",
    "chart":    "M3 20h18 M6 17v-4 M10 17V8 M14 17v-6 M18 17V5",
    "globe":    "M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18 M3 12h18 M12 3c3.5 3.5 3.5 14.5 0 18 M12 3c-3.5 3.5-3.5 14.5 0 18",
    "pad":      "M7 7h10a5 5 0 0 1 5 5v2a3 3 0 0 1-5.5 1.6L15 14H9l-1.5 1.6A3 3 0 0 1 2 14v-2a5 5 0 0 1 5-5z M7 10v4 M5 12h4 M15.5 11h.01 M18 13h.01",
    "target":   "M12 4a8 8 0 1 0 0 16a8 8 0 1 0 0-16 M12 1v6 M12 17v6 M1 12h6 M17 12h6",
    "music":    "M9 18V5l11-2v13 M9 18a3 3 0 1 1-6 0a3 3 0 1 1 6 0 M20 16a3 3 0 1 1-6 0a3 3 0 1 1 6 0",
    "mouse":    "M7 9a5 5 0 0 1 10 0v6a5 5 0 0 1-10 0z M12 4v5",
    "tri":      "M7 4l13 8-13 8z",
    "pause":    "M7 4v16 M17 4v16",
    "full":     "M3 9V3h6 M15 3h6v6 M21 15v6h-6 M9 21H3v-6",
    "mic":      "M9 3h6v11H9z M5 11a7 7 0 0 0 14 0 M12 18v3 M8 21h8",
    "mic_off":  "M9 3h6v11H9z M5 11a7 7 0 0 0 14 0 M12 18v3 M8 21h8 M3 3l18 18",
    "headset":  "M4 15v-3a8 8 0 0 1 16 0v3 M4 14h4v7H4z M16 14h4v7h-4z",
    "headset_off": "M4 15v-3a8 8 0 0 1 16 0v3 M4 14h4v7H4z M16 14h4v7h-4z M3 3l18 18",
    "leave":    "M10 4H5v16h5 M14 8l4 4-4 4 M18 12H9",
    "cog":      "M12 9a3 3 0 1 0 0 6a3 3 0 1 0 0-6 M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z",  # Feather "settings" (MIT)
    "gear":     "M12 8.5a3.5 3.5 0 1 0 0 7a3.5 3.5 0 1 0 0-7 M12 2v4 M12 18v4 M2 12h4 M18 12h4 M4.9 4.9l2.8 2.8 M16.3 16.3l2.8 2.8 M4.9 19.1l2.8-2.8 M16.3 7.7l2.8-2.8",
}

import collections
import ctypes
import devices
import youtube
import difflib
import hashlib
import hmac
import html
import json
import re
import secrets
import shutil
import socket
import struct
import subprocess
import sys
import threading
import time
import zlib
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import urllib.request
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
# data\  = stato e segreti (token, impostazioni, accesso Discord): letti solo dal server, MAI serviti al tablet
# cache\ = cose rigenerabili (icone estratte, schermate di debug); si puo' cancellare in qualsiasi momento
# assets\ = file statici forniti (icone SVG degli stratagemmi)
DATA_DIR = os.path.join(HERE, "data")
CACHE_DIR = os.path.join(HERE, "cache")
ASSETS_DIR = os.path.join(HERE, "assets")
for _d in (DATA_DIR, CACHE_DIR):
    os.makedirs(_d, exist_ok=True)
TOKEN_FILE = os.path.join(DATA_DIR, "token.txt")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
_NET_RE = re.compile(r"^\d{1,3}\.(\d{1,3}\.){0,2}$")


def load_config(path):
    """Configurazione della rete (scritta dall'installer). Ogni valore mancante o non valido -> predefinito."""
    cfg = {"allowed_nets": ("172.20.10.",), "port": 8765, "adb": None}
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError):
        return cfg
    if not isinstance(raw, dict):
        return cfg
    nets = raw.get("allowed_nets")
    if isinstance(nets, list) and nets and all(isinstance(n, str) and _NET_RE.match(n) for n in nets):
        cfg["allowed_nets"] = tuple(nets)
    port = raw.get("port")
    if type(port) is int and 1024 <= port <= 65535:
        cfg["port"] = port
    adb = raw.get("adb")
    if isinstance(adb, str) and adb:
        cfg["adb"] = adb
    return cfg
LOADOUT_FILE = os.path.join(DATA_DIR, "hd2_loadout.json")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
SETTINGS_CHOICES = {"input": ("wasd", "arrows"), "pos": ("left", "right", "top", "bottom"), "pad": ("med", "slow", "fast"), "remap": ("off", "on"),
                    "theme": ("hd", "notte", "discord", "term", "rosso", "oled"), "updchk": ("on", "off")}   # remap: beta, spento di default
ICON_DIR = os.path.join(ASSETS_DIR, "hd2_icons")
ICON_RE = re.compile(r"^[a-z0-9_]{1,40}$")
LOADOUT_MAX = 4
COOLDOWN_FILE = os.path.join(DATA_DIR, "hd2_cooldowns.json")
SYNC_DEBUG_DIR = os.path.join(CACHE_DIR, "hd2_sync_debug")

VK = {
    "CTRL": 0x11, "SHIFT": 0x10, "ALT": 0x12, "WIN": 0x5B, "TAB": 0x09,
    "ENTER": 0x0D, "ESC": 0x1B, "SPACE": 0x20, "BACKSPACE": 0x08, "DELETE": 0x2E,
    "LEFT": 0x25, "UP": 0x26, "RIGHT": 0x27, "DOWN": 0x28,
    "HOME": 0x24, "END": 0x23, "PAGEUP": 0x21, "PAGEDOWN": 0x22,
    "PRINTSCREEN": 0x2C, "INSERT": 0x2D,
    "VOLUME_MUTE": 0xAD, "VOLUME_DOWN": 0xAE, "VOLUME_UP": 0xAF,
    "MEDIA_NEXT": 0xB0, "MEDIA_PREV": 0xB1, "MEDIA_STOP": 0xB2, "MEDIA_PLAY_PAUSE": 0xB3,
}
VK.update({chr(c): c for c in range(ord("A"), ord("Z") + 1)})
VK.update({str(d): 0x30 + d for d in range(10)})
VK.update({"F%d" % n: 0x6F + n for n in range(1, 13)})
EXTENDED = {0x5B, 0x2C, 0x2D, 0x2E, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28,
            0xAD, 0xAE, 0xAF, 0xB0, 0xB1, 0xB2, 0xB3}
KEYEVENTF_EXTENDEDKEY, KEYEVENTF_KEYUP = 0x1, 0x2

BY_ID = {b["id"]: b for b in BUTTONS}
for _grp, _col, _items in STRATAGEMS:
    if _col not in ("mis", "off", "sup", "def"):
        sys.exit("Colore gruppo non valido: %r (%s)" % (_col, _grp))
    for _sid, _name, _code in _items:
        if set(_code) - set("UDLR") or not _code:
            sys.exit("Codice stratagemma non valido: %r (%s)" % (_code, _sid))
        if not ICON_RE.match(_sid):
            sys.exit("Id stratagemma non valido: %r" % _sid)
        if ("hd2_" + _sid) in BY_ID:
            sys.exit("Id stratagemma duplicato: %s" % _sid)
        BY_ID["hd2_" + _sid] = {"id": "hd2_" + _sid, "label": _name, "strat": _code, "col": _col}
for _sid in ALWAYS:
    if "hd2_" + _sid not in BY_ID:
        sys.exit("ALWAYS contiene uno stratagemma sconosciuto: %s" % _sid)
for _b in BUTTONS:  # valida la configurazione all'avvio
    for _k in _b.get("keys", []):
        if _k not in VK:
            sys.exit("Tasto sconosciuto in BUTTONS: %r (pulsante %s)" % (_k, _b["id"]))
    if _b.get("icon") and _b["icon"] not in ICONS:
        sys.exit("Icona sconosciuta: %r (pulsante %s)" % (_b["icon"], _b["id"]))
    if _b.get("sec") not in [s for s, _ in SECTIONS] + ["media", None] or \
            (_b.get("group") and _b["group"] not in [g["id"] for g in GROUPS]) or not (_b.get("sec") or _b.get("group")):
        sys.exit("Sezione/gruppo non valido nel pulsante %s" % _b["id"])
for _f in FAVORITES:
    if _f not in BY_ID and not _f.startswith("_"):
        sys.exit("FAVORITES contiene un pulsante sconosciuto: %s" % _f)

# --- Righe di Generale modificabili dal tablet: tabdeck_layout.json =
#     {"fav": [id...], "rows": {"sistema": [...], "strumenti": [...]}, "custom": [app...], "keys": [scorciatoie...]}
# "_vol", "_mic", "_yt" sono i riquadri speciali Volume, Microfono e YouTube (uno solo ciascuno).
LAYOUT_FILE = os.path.join(DATA_DIR, "layout.json")
FAV_MAX = 10
ROW_SIDS = ("avvio", "sistema", "strumenti")
SPECIALS = ("_vol", "_mic", "_yt")
# righe di un'installazione nuova (chi ha gia' salvato le sue le tiene): le altre scorciatoie restano in "Aggiungi"
DEFAULT_ROWS = {"sistema": ["desktop", "alt_tab", "task_view", "lock", "_vol", "explorer"],
                "strumenti": ["notepad", "calc", "run", "screenshot", "snip", "_mic"]}
ROWS = {"avvio": FAVORITES, "sistema": list(DEFAULT_ROWS["sistema"]), "strumenti": list(DEFAULT_ROWS["strumenti"])}
CUSTOM_KEYS = []      # scorciatoie create dal tablet: {"id", "label", "keys", "icon"}
MODS = ["CTRL", "SHIFT", "ALT", "WIN"]
KEY_CHOICES = ([chr(c) for c in range(ord("A"), ord("Z") + 1)] + [str(d) for d in range(10)] + ["F%d" % n for n in range(1, 13)] +
               ["ESC", "TAB", "ENTER", "SPACE", "BACKSPACE", "DELETE", "INSERT", "HOME", "END", "PAGEUP", "PAGEDOWN",
                "LEFT", "UP", "RIGHT", "DOWN", "PRINTSCREEN", "VOLUME_MUTE", "VOLUME_DOWN", "VOLUME_UP",
                "MEDIA_PREV", "MEDIA_PLAY_PAUSE", "MEDIA_NEXT", "MEDIA_STOP"])
KEY_PRETTY = {"CTRL": "Ctrl", "SHIFT": "Shift", "ALT": "Alt", "WIN": "Win", "ESC": "Esc", "TAB": "Tab", "ENTER": "Invio",
              "SPACE": "Spazio", "BACKSPACE": "Bksp", "DELETE": "Canc", "INSERT": "Ins", "HOME": "Inizio", "END": "Fine",
              "PAGEUP": "Pag\u25b2", "PAGEDOWN": "Pag\u25bc", "LEFT": "\u25c0", "UP": "\u25b2", "RIGHT": "\u25b6", "DOWN": "\u25bc",
              "PRINTSCREEN": "Stamp", "VOLUME_MUTE": "Muto", "VOLUME_DOWN": "Vol-", "VOLUME_UP": "Vol+", "MEDIA_PREV": "Prec",
              "MEDIA_PLAY_PAUSE": "Play", "MEDIA_NEXT": "Succ", "MEDIA_STOP": "Stop"}


def key_spec_ok(k):
    """Scorciatoia valida: nome 1-24 caratteri, modificatori (una volta ciascuno) e poi un solo tasto."""
    if not isinstance(k, dict) or not re.match(r"^k_[0-9a-f]{8}$", str(k.get("id", ""))):
        return False
    label, keys = str(k.get("label", "")).strip(), k.get("keys")
    if not 1 <= len(label) <= 24 or not isinstance(keys, list) or not 1 <= len(keys) <= 5:
        return False
    mods, last = keys[:-1], keys[-1]
    return (last in KEY_CHOICES and all(m in MODS for m in mods) and len(set(mods)) == len(mods)
            and (not k.get("icon") or k["icon"] in ICONS))


def key_button(k):
    b = {"id": k["id"], "sec": "sistema", "cat": "win", "label": k["label"].strip(), "keys": list(k["keys"]), "customkey": True,
         "hint": "+".join(KEY_PRETTY.get(x, x) for x in k["keys"])}
    if k.get("icon"):
        b["icon"] = k["icon"]
    else:
        b["mono"] = (re.sub(r"[^A-Za-z0-9]", "", b["label"])[:2] or "SC").upper()
    return b


def _put_button(b):
    old = BY_ID.get(b["id"])
    if old is not None and old in BUTTONS:
        BUTTONS[BUTTONS.index(old)] = b
    else:
        BUTTONS.append(b)
    BY_ID[b["id"]] = b


def _drop_button(bid):
    b = BY_ID.pop(bid, None)
    if b is not None and b in BUTTONS:
        BUTTONS.remove(b)
LAYOUT_LOCK = threading.Lock()


def _exe_label(path):
    n = os.path.splitext(os.path.basename(path))[0]
    return n[:1].upper() + n[1:]


AUMID_RE = re.compile(r"^[\w.\-]+![\w.\-]+$")


def _spec_ok(spec):
    """Programma aggiunto dal tablet: percorso di un .exe, oppure "appx:AUMID|processo.exe" (app dello Store)."""
    if not isinstance(spec, str):
        return False
    if spec.startswith("appx:"):
        aumid, _, proc = spec[5:].partition("|")
        return bool(AUMID_RE.match(aumid)) and proc.lower().endswith(".exe") and "\\" not in proc
    return os.path.isabs(spec) and spec.lower().endswith(".exe")


def custom_button(spec):
    """Pulsante per un programma qualsiasi aggiunto dal tablet (preso da una finestra aperta)."""
    b = {"id": "c_" + hashlib.sha1(spec.lower().encode("utf-8")).hexdigest()[:10], "sec": "avvio", "cat": "app",
         "hint": "app", "custom": spec}
    if spec.startswith("appx:"):
        aumid, _, proc = spec[5:].partition("|")
        b.update(label=_exe_label(proc), run=appx(aumid), proc=[proc.lower()])
    else:
        b.update(label=_exe_label(spec), run=[spec])
    b["mono"] = (re.sub(r"[^A-Za-z0-9]", "", b["label"])[:2] or "AP").upper()
    return b


def _add_custom(spec):
    b = custom_button(spec)
    if b["id"] not in BY_ID:
        _put_button(b)
    return b["id"]


def clean_rows(rows):
    """Righe valide: id esistenti (o speciali), ognuno in una sola riga, al massimo FAV_MAX per riga."""
    seen, out = set(), {}
    for sid in ROW_SIDS:
        lst = []
        for i in rows.get(sid) or []:
            if isinstance(i, str) and i not in seen and (i in SPECIALS or (i in BY_ID and BY_ID[i].get("sec") != "media"
                                                                            and ("run" in BY_ID[i] or "keys" in BY_ID[i]))):
                seen.add(i)
                lst.append(i)
        out[sid] = lst[:FAV_MAX]
    return out


def yt_migrate(rows, done):
    """Una volta sola: il riquadro YouTube prende il posto di Spotify nei Preferiti (o va in fondo se c'e' posto).
    done = il file salvato dice gia' "yt_added": chi poi lo toglie non se lo ritrova."""
    if done or any("_yt" in (rows.get(sid) or []) for sid in ROW_SIDS):
        return rows
    fav = list(rows.get("avvio") or [])
    if "spotify" in fav:
        fav[fav.index("spotify")] = "_yt"
    elif len(fav) < FAV_MAX:
        fav.append("_yt")
    out = dict(rows)
    out["avvio"] = fav
    return out


def apply_layout():
    try:
        with open(LAYOUT_FILE, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return
    if not isinstance(data, dict):
        return
    for p in data.get("custom") or []:
        if _spec_ok(p):
            _add_custom(p)
    for k in data.get("keys") or []:
        if key_spec_ok(k):
            CUSTOM_KEYS.append({"id": k["id"], "label": k["label"].strip(), "keys": k["keys"], "icon": k.get("icon") or ""})
            _put_button(key_button(k))
    saved = data.get("rows") if isinstance(data.get("rows"), dict) else {}
    rows = {"avvio": data.get("fav") or ROWS["avvio"], "sistema": saved.get("sistema", ROWS["sistema"]),
            "strumenti": saved.get("strumenti", ROWS["strumenti"])}
    rows = clean_rows(yt_migrate(rows, bool(data.get("yt_added"))))
    FAVORITES[:] = rows["avvio"]
    ROWS["sistema"][:] = rows["sistema"]
    ROWS["strumenti"][:] = rows["strumenti"]


def save_layout(rows=None):
    with LAYOUT_LOCK:
        if rows is not None:
            FAVORITES[:] = rows["avvio"]
            ROWS["sistema"][:] = rows["sistema"]
            ROWS["strumenti"][:] = rows["strumenti"]
        used = [i for sid in ROW_SIDS for i in ROWS[sid]]
        data = {"fav": list(FAVORITES), "rows": {"sistema": list(ROWS["sistema"]), "strumenti": list(ROWS["strumenti"])},
                "custom": [BY_ID[i]["custom"] for i in used if i in BY_ID and BY_ID[i].get("custom")],
                "keys": CUSTOM_KEYS, "yt_added": True}
        tmp = LAYOUT_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=1)
        os.replace(tmp, LAYOUT_FILE)


apply_layout()


# --- volume di Windows (Core Audio via COM, solo ctypes) ---
class _GUID(ctypes.Structure):
    _fields_ = [("d1", ctypes.c_ulong), ("d2", ctypes.c_ushort), ("d3", ctypes.c_ushort), ("d4", ctypes.c_ubyte * 8)]


def _guid(s):
    g = _GUID()
    ctypes.oledll.ole32.CLSIDFromString(ctypes.c_wchar_p(s), ctypes.byref(g))
    return g


CLSID_MMDeviceEnumerator = _guid("{BCDE0395-E52F-467C-8E3D-C4579291692E}")
IID_IMMDeviceEnumerator = _guid("{A95664D2-9614-4F35-A746-DE8DB63617E6}")
IID_IAudioEndpointVolume = _guid("{5CDF2C82-841E-4546-9722-0CF74078229A}")
AUDIO_LOCK = threading.Lock()


def _com(obj, idx, argtypes, *args, restype=ctypes.HRESULT):
    vtbl = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
    return ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)(vtbl[idx])(obj, *args)


def _with_endpoint(fn, iid=IID_IAudioEndpointVolume, flow=0, role=0):
    """Apre un'interfaccia (iid) del dispositivo predefinito (flow 0 = uscita, 1 = microfono;
    role 0 = console, 2 = comunicazioni), chiama fn(interfaccia), rilascia tutto."""
    with AUDIO_LOCK:
        hr = ctypes.windll.ole32.CoInitializeEx(None, 0)
        enum, dev, vol = ctypes.c_void_p(), ctypes.c_void_p(), ctypes.c_void_p()
        try:
            ctypes.oledll.ole32.CoCreateInstance(ctypes.byref(CLSID_MMDeviceEnumerator), None, 0x17,
                                                 ctypes.byref(IID_IMMDeviceEnumerator), ctypes.byref(enum))
            _com(enum, 4, (ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)), flow, role, ctypes.byref(dev))
            _com(dev, 3, (ctypes.POINTER(_GUID), ctypes.c_ulong, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)),
                 ctypes.byref(iid), 0x17, None, ctypes.byref(vol))
            return fn(vol)
        finally:
            for p in (vol, dev, enum):
                if p.value:
                    _com(p, 2, (), restype=ctypes.c_ulong)
            if hr in (0, 1):
                ctypes.windll.ole32.CoUninitialize()


# --- finestre aperte sul PC (scheda "Finestre") ---
_u32 = ctypes.WinDLL("user32")       # istanza separata: argtypes a 64 bit per gli HWND
_k32 = ctypes.WinDLL("kernel32")
_HWND = ctypes.c_void_p
for _fn, _args, _res in (
        ("IsWindowVisible", [_HWND], ctypes.c_bool), ("IsWindow", [_HWND], ctypes.c_bool),
        ("IsIconic", [_HWND], ctypes.c_bool), ("GetWindow", [_HWND, ctypes.c_uint], _HWND),
        ("GetWindowLongW", [_HWND, ctypes.c_int], ctypes.c_long),
        ("GetWindowTextLengthW", [_HWND], ctypes.c_int),
        ("GetWindowTextW", [_HWND, ctypes.c_wchar_p, ctypes.c_int], ctypes.c_int),
        ("GetClassNameW", [_HWND, ctypes.c_wchar_p, ctypes.c_int], ctypes.c_int),
        ("GetWindowThreadProcessId", [_HWND, ctypes.POINTER(ctypes.c_ulong)], ctypes.c_ulong),
        ("GetForegroundWindow", [], _HWND), ("SetForegroundWindow", [_HWND], ctypes.c_bool),
        ("BringWindowToTop", [_HWND], ctypes.c_bool), ("ShowWindow", [_HWND, ctypes.c_int], ctypes.c_bool),
        ("SwitchToThisWindow", [_HWND, ctypes.c_bool], None), ("IsZoomed", [_HWND], ctypes.c_bool),
        ("PostMessageW", [_HWND, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p], ctypes.c_bool),
        ("AttachThreadInput", [ctypes.c_ulong, ctypes.c_ulong, ctypes.c_bool], ctypes.c_bool)):
    getattr(_u32, _fn).argtypes, getattr(_u32, _fn).restype = _args, _res
_k32.OpenProcess.argtypes, _k32.OpenProcess.restype = [ctypes.c_ulong, ctypes.c_bool, ctypes.c_ulong], ctypes.c_void_p
_k32.QueryFullProcessImageNameW.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_ulong)]
_k32.CloseHandle.argtypes = [ctypes.c_void_p]
_EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, _HWND, ctypes.c_void_p)
_u32.EnumWindows.argtypes = [_EnumProc, ctypes.c_void_p]
_u32.EnumChildWindows.argtypes = [_HWND, _EnumProc, ctypes.c_void_p]
SKIP_CLASSES = {"Progman", "Shell_TrayWnd", "WorkerW", "Windows.UI.Core.CoreWindow"}


def _exe_of_pid(pid):
    hp = _k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not hp:
        return ""
    try:
        buf, size = ctypes.create_unicode_buffer(520), ctypes.c_ulong(520)
        return buf.value if _k32.QueryFullProcessImageNameW(hp, 0, buf, ctypes.byref(size)) else ""
    finally:
        _k32.CloseHandle(hp)


def _exe_of(h):
    """Percorso completo dell'eseguibile della finestra. Per le app dello Store (ospitate da
    ApplicationFrameHost) restituisce quello dell'app vera, cercando la finestra figlia."""
    pid = ctypes.c_ulong()
    _u32.GetWindowThreadProcessId(h, ctypes.byref(pid))
    path = _exe_of_pid(pid.value)
    if os.path.basename(path).lower() == "applicationframehost.exe":
        found = []

        def child(ch, _):
            cp = ctypes.c_ulong()
            _u32.GetWindowThreadProcessId(ch, ctypes.byref(cp))
            if cp.value != pid.value:
                found.append(cp.value)
                return False
            return True
        _u32.EnumChildWindows(h, _EnumProc(child), None)
        if found:
            path = _exe_of_pid(found[0]) or path
    return path


def list_windows():
    """Finestre come nella barra delle applicazioni, dalla piu' recente (ordine Z)."""
    out = []

    def cb(h, _):
        if not _u32.IsWindowVisible(h) or _u32.GetWindow(h, 4):           # GW_OWNER
            return True
        if _u32.GetWindowLongW(h, -20) & 0x80:                              # WS_EX_TOOLWINDOW
            return True
        n = _u32.GetWindowTextLengthW(h)
        if n <= 0:
            return True
        cloaked = ctypes.c_int(0)
        ctypes.windll.dwmapi.DwmGetWindowAttribute(_HWND(h), 14, ctypes.byref(cloaked), 4)  # DWMWA_CLOAKED
        if cloaked.value:
            return True
        cl = ctypes.create_unicode_buffer(128)
        _u32.GetClassNameW(h, cl, 128)
        if cl.value in SKIP_CLASSES:
            return True
        t = ctypes.create_unicode_buffer(n + 1)
        _u32.GetWindowTextW(h, t, n + 1)
        exe = _exe_of(h)
        out.append({"h": str(h), "t": t.value, "x": os.path.basename(exe), "i": icon_key(exe) if exe else "",
                    "min": bool(_u32.IsIconic(h))})
        return True

    _u32.EnumWindows(_EnumProc(cb), None)
    fg = _u32.GetForegroundWindow()
    for w in out:
        w["fg"] = w["h"] == str(fg)
    return out


def _procs(b):
    """Processi che identificano l'app di un pulsante tra le finestre aperte."""
    if b.get("proc"):
        return [p.lower() for p in b["proc"]]
    run = b.get("run") or []
    if run and (len(run) == 1 or run[0].lower() != "explorer.exe"):
        return [os.path.basename(run[0]).lower()]
    return []


_STICKY = {}   # pulsante o gruppo -> scelta precedente (finestra / app), finche' resta aperta
_AUTO_FG = [None]   # finestra che Windows ha messo davanti da sola dopo una nostra riduzione a icona


def minimize_window(h):
    """Riduce a icona e ricorda quale finestra Windows porta davanti al suo posto (non e' una scelta dell'utente)."""
    _u32.ShowWindow(h, 6)   # SW_MINIMIZE
    time.sleep(0.08)
    _AUTO_FG[0] = str(_u32.GetForegroundWindow())


def _sticky(key, cands, fg, newest):
    """Sceglie tra cands: quella in primo piano se c'e', altrimenti la scelta precedente se esiste
    ancora, altrimenti newest. Cosi' ridurre a icona non fa saltare il riquadro su un'altra finestra."""
    pick = fg if fg in cands else _STICKY.get(key) if _STICKY.get(key) in cands else newest
    _STICKY[key] = pick
    return pick


_k32.GetApplicationUserModelId.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32), ctypes.c_wchar_p]
_k32.GetApplicationUserModelId.restype = ctypes.c_long


def _aumid_of_window(h):
    """AppUserModelID del processo della finestra (solo app dello Store), "" se non c'e'."""
    pid = ctypes.c_ulong()
    _u32.GetWindowThreadProcessId(int(h), ctypes.byref(pid))
    hp = _k32.OpenProcess(0x1000, False, pid.value)
    if not hp:
        return ""
    try:
        n, buf = ctypes.c_uint32(256), ctypes.create_unicode_buffer(256)
        return buf.value if _k32.GetApplicationUserModelId(hp, ctypes.byref(n), buf) == 0 else ""
    finally:
        _k32.CloseHandle(hp)


def open_specs():
    """Programmi con una finestra aperta che non sono gia' pulsanti: chiave icona -> spec per custom_button."""
    known_procs = set(p for b in BUTTONS for p in _procs(b))
    skip = {"applicationframehost.exe", "explorer.exe", "python.exe", "pythonw.exe", "cmd.exe", "windowsterminal.exe"}
    out = {}
    for w in list_windows():
        path = ICON_SRC.get(w["i"], "") if w["i"] else ""
        x = w["x"].lower()
        if not path or x in known_procs or x in skip or w["i"] in out or not x.endswith(".exe"):
            continue
        if "\\windowsapps\\" in path.lower():      # app dello Store: si avvia dal suo AUMID, non dall'exe
            aumid = _aumid_of_window(w["h"])
            if not AUMID_RE.match(aumid or ""):
                continue
            spec = "appx:%s|%s" % (aumid, w["x"])
        elif os.path.isfile(path):
            spec = path
        else:
            continue
        out[w["i"]] = spec
    return out


def layout_info():
    """Per l'editor delle righe: le tre righe e tutto cio' che si puo' aggiungere."""
    def h(i):
        return special_html(i, False) if i in SPECIALS else button_html(BY_ID[i])
    rows = {sid: [{"id": i, "h": h(i)} for i in ROWS[sid] if i in SPECIALS or i in BY_ID] for sid in ROW_SIDS}
    apps = [b for b in BUTTONS if b.get("run") and installed(b) and b.get("sec") != "media" and not b.get("custom")]
    keys = [b for b in BUTTONS if b.get("keys") and b.get("sec") != "media"]
    mine = {k["id"]: k for k in CUSTOM_KEYS}
    return {"rows": rows, "max": FAV_MAX,
            "apps": [{"id": b["id"], "h": button_html(b)} for b in apps],
            "keys": [dict({"id": b["id"], "h": button_html(b)}, **({"edit": 1, "label": mine[b["id"]]["label"], "keys": mine[b["id"]]["keys"],
                                                                    "icon": mine[b["id"]]["icon"]} if b["id"] in mine else {})) for b in keys],
            "open": [{"k": k, "h": button_html(custom_button(spec))} for k, spec in open_specs().items()],
            "spec": [{"id": i, "h": special_html(i, False)} for i in SPECIALS]}


def running_apps(wins=None):
    """Per la scheda Generale: quali pulsanti hanno una finestra aperta e, per ogni gruppo, quale app
    mostrare. Scelte "appiccicose": cambiano solo quando un'altra finestra/app viene in primo piano."""
    wins = list_windows() if wins is None else wins
    apps, members = {}, {}
    fg_h = next((w["h"] for w in wins if w["fg"]), None)
    if fg_h == _AUTO_FG[0]:
        fg_h = None
    for b in BUTTONS:
        procs = _procs(b) if b.get("sec") != "media" and installed(b) else []
        mine = [w for w in wins if w["x"].lower() in procs]
        if not mine:
            continue
        h = _sticky(b["id"], [w["h"] for w in mine], fg_h, mine[0]["h"])
        w = next(w for w in mine if w["h"] == h)
        apps[b["id"]] = {"h": h, "i": w["i"], "n": b["label"]}
        if b.get("tab"):
            apps[b["id"]]["tab"] = b["tab"]
        if b.get("group"):
            members.setdefault(b["group"], []).append((wins.index(w), b["id"], any(x["fg"] for x in mine)))
    grp = {}
    for g, lst in members.items():
        lst.sort()
        fg_id = next((bid for _, bid, isfg in lst if isfg), None)
        grp[g] = _sticky("grp:" + g, [bid for _, bid, _ in lst], fg_id, lst[0][1])
    return {"apps": apps, "grp": grp}


# --- icone vere dei programmi (browser, launcher, finestre), estratte dalla shell di Windows ---
class _SIZE(ctypes.Structure):
    _fields_ = [("cx", ctypes.c_long), ("cy", ctypes.c_long)]


class _BITMAP(ctypes.Structure):
    _fields_ = [("bmType", ctypes.c_long), ("bmWidth", ctypes.c_long), ("bmHeight", ctypes.c_long),
                ("bmWidthBytes", ctypes.c_long), ("bmPlanes", ctypes.c_ushort), ("bmBitsPixel", ctypes.c_ushort),
                ("bmBits", ctypes.c_void_p)]


class _BIH(ctypes.Structure):
    _fields_ = [("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_long), ("biHeight", ctypes.c_long),
                ("biPlanes", ctypes.c_ushort), ("biBitCount", ctypes.c_ushort), ("biCompression", ctypes.c_uint32),
                ("biSizeImage", ctypes.c_uint32), ("biXPelsPerMeter", ctypes.c_long), ("biYPelsPerMeter", ctypes.c_long),
                ("biClrUsed", ctypes.c_uint32), ("biClrImportant", ctypes.c_uint32)]


IID_IShellItemImageFactory = _guid("{bcc18b79-ba16-442f-80c4-8a59c30c463b}")
_sh32, _gdi = ctypes.WinDLL("shell32"), ctypes.WinDLL("gdi32")
_sh32.SHCreateItemFromParsingName.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p, ctypes.POINTER(_GUID), ctypes.POINTER(ctypes.c_void_p)]
_sh32.SHCreateItemFromParsingName.restype = ctypes.HRESULT
_gdi.GetObjectW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
_gdi.GetDIBits.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint]
_gdi.DeleteObject.argtypes = [ctypes.c_void_p]
_u32.GetDC.argtypes, _u32.GetDC.restype = [_HWND], ctypes.c_void_p
_u32.ReleaseDC.argtypes = [_HWND, ctypes.c_void_p]
ICON_CACHE = os.path.join(CACHE_DIR, "icons")
ICON_SRC = {}            # chiave -> percorso/nome shell: si servono SOLO icone di questa lista
ICON_LOCK = threading.Lock()


def icon_key(src):
    k = hashlib.sha1(src.lower().encode("utf-8")).hexdigest()[:16]
    ICON_SRC[k] = src
    return k


def _png(w, h, rgba):
    raw = b"".join(b"\x00" + rgba[y * w * 4:(y + 1) * w * 4] for y in range(h))

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def _shell_icon_png(src, size=96):
    hr = ctypes.windll.ole32.CoInitializeEx(None, 2)  # la shell vuole un apartment STA
    fac, hbm = ctypes.c_void_p(), ctypes.c_void_p()
    try:
        _sh32.SHCreateItemFromParsingName(src, None, ctypes.byref(IID_IShellItemImageFactory), ctypes.byref(fac))
        _com(fac, 3, (_SIZE, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)), _SIZE(size, size), 0x4, ctypes.byref(hbm))
        bm = _BITMAP()
        _gdi.GetObjectW(hbm, ctypes.sizeof(bm), ctypes.byref(bm))
        w, h = bm.bmWidth, abs(bm.bmHeight)
        bih = _BIH(biSize=40, biWidth=w, biHeight=-h, biPlanes=1, biBitCount=32)
        buf = (ctypes.c_ubyte * (w * h * 4))()
        dc = _u32.GetDC(None)
        try:
            _gdi.GetDIBits(dc, hbm, 0, h, buf, ctypes.byref(bih), 0)
        finally:
            _u32.ReleaseDC(None, dc)
        px = bytearray(buf)
        if not any(px[3::4]):            # icona senza canale alfa: opaca
            px[3::4] = b"\xff" * (w * h)
        for i in range(0, len(px), 4):   # BGRA premoltiplicato -> RGBA
            b, g, r, a = px[i], px[i + 1], px[i + 2], px[i + 3]
            if 0 < a < 255:
                r, g, b = min(255, r * 255 // a), min(255, g * 255 // a), min(255, b * 255 // a)
            px[i], px[i + 1], px[i + 2] = r, g, b
        return _png(w, h, bytes(px))
    finally:
        if hbm.value:
            _gdi.DeleteObject(hbm)
        if fac.value:
            _com(fac, 2, (), restype=ctypes.c_ulong)
        if hr in (0, 1):
            ctypes.windll.ole32.CoUninitialize()


def app_icon(key):
    """PNG dell'icona (dalla cache su disco, o estratta ora). None se sconosciuta o non estraibile."""
    src = ICON_SRC.get(key)
    if not src:
        return None
    path = os.path.join(ICON_CACHE, key + ".png")
    with ICON_LOCK:
        if os.path.isfile(path):
            with open(path, "rb") as f:
                return f.read()
        try:
            data = _shell_icon_png(src)
        except OSError:
            return None
        os.makedirs(ICON_CACHE, exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        return data


def button_icon_src(b):
    if b.get("iconsrc"):
        return b["iconsrc"]
    run = b.get("run") or []
    if len(run) > 1 and run[0] == "explorer.exe" and run[1].startswith("shell:AppsFolder\\"):
        return run[1]
    return run[0] if run and os.path.isabs(run[0]) else None


def focus_window(h):
    """Porta in primo piano una finestra (ripristinandola se ridotta a icona)."""
    if _u32.IsIconic(h):
        _u32.ShowWindow(h, 9)  # SW_RESTORE
    fg = _u32.GetForegroundWindow()
    me = _k32.GetCurrentThreadId()
    other = _u32.GetWindowThreadProcessId(fg, None) if fg else 0
    attached = bool(other and other != me and _u32.AttachThreadInput(me, other, True))
    try:
        _u32.SetForegroundWindow(h)
        _u32.BringWindowToTop(h)
    finally:
        if attached:
            _u32.AttachThreadInput(me, other, False)
    if _u32.GetForegroundWindow() != h:
        _u32.SwitchToThisWindow(h, True)
    return _u32.GetForegroundWindow() == h


def audio_state(level=None, mute=None):
    """Imposta (se dati) volume 0-100 e/o muto, poi restituisce lo stato attuale."""
    def op(v):
        if level is not None:
            _com(v, 7, (ctypes.c_float, ctypes.c_void_p), ctypes.c_float(level / 100.0), None)
        if mute is not None:
            _com(v, 14, (ctypes.c_int, ctypes.c_void_p), 1 if mute else 0, None)
        f, m = ctypes.c_float(), ctypes.c_int()
        _com(v, 9, (ctypes.POINTER(ctypes.c_float),), ctypes.byref(f))
        _com(v, 15, (ctypes.POINTER(ctypes.c_int),), ctypes.byref(m))
        return {"vol": int(round(f.value * 100)), "mute": bool(m.value)}
    return _with_endpoint(op)


def mic_state(mute=None):
    """Muto del microfono di Windows. Imposta sia il microfono predefinito sia quello "per le
    comunicazioni" (Discord di solito usa uno dei due), poi legge quello predefinito.
    Discord non vede questo muto: riceve solo silenzio."""
    def op(v):
        if mute is not None:
            _com(v, 14, (ctypes.c_int, ctypes.c_void_p), 1 if mute else 0, None)
        m = ctypes.c_int()
        _com(v, 15, (ctypes.POINTER(ctypes.c_int),), ctypes.byref(m))
        return bool(m.value)
    if mute is not None:
        try:
            _with_endpoint(op, flow=1, role=2)
        except OSError:
            pass
    return {"mute": _with_endpoint(op, flow=1, role=0)}


# --- Discord: muto / silenzia via RPC locale (named pipe di Discord) ---
# Serve un'applicazione dell'utente sul Developer Portal: tabdeck_discord.json = {client_id, client_secret}.
# La prima volta Discord chiede "Autorizza"; il token viene salvato e rinnovato da solo.
DISCORD_CFG = os.path.join(DATA_DIR, "discord.json")             # client_id + client_secret dell'app dell'utente
DISCORD_TOKEN = os.path.join(DATA_DIR, "discord_token.json")      # accesso OAuth salvato (rinnovato da solo)
DISCORD_SCOPES = ["rpc", "rpc.voice.read", "rpc.voice.write"]
DISCORD_REDIRECT = "http://localhost"
_k32.PeekNamedPipe.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p,
                               ctypes.POINTER(ctypes.c_ulong), ctypes.c_void_p]


class DiscordError(Exception):
    pass


class Discord:
    """Un solo thread possiede la pipe (lettura e scrittura sincrone sullo stesso handle si bloccano
    a vicenda su Windows): esegue i lavori in coda e, tra un lavoro e l'altro, legge gli eventi.
    Gli endpoint HTTP passano da call()/run(), che aspettano il risultato."""

    VC_EVENTS = ("VOICE_STATE_CREATE", "VOICE_STATE_UPDATE", "VOICE_STATE_DELETE", "SPEAKING_START", "SPEAKING_STOP")

    def __init__(self):
        self.lock = threading.Lock()
        self.wake = threading.Event()
        self.queue = []
        self.st = {"s": "off", "msg": "avvio"}
        self.want_auth = False
        self.started = False
        self.f = self.h = None
        self.me = None            # id dell'utente collegato
        self.vc = None            # canale vocale attuale: {id, n, g, m: {user_id: membro}, sp: set()}
        self.vc_dirty = False
        self.drop = False         # chiesto "scollega": chiude la sessione
        self.cache = {}           # chiave -> (istante, valore)

    @staticmethod
    def _log(msg):
        print("[%s] discord: %s" % (time.strftime("%H:%M:%S"), msg))

    def start(self):
        with self.lock:
            if self.started:
                return
            self.started = True
        threading.Thread(target=self._run, daemon=True).start()

    def state(self):
        self.start()
        with self.lock:
            return dict(self.st)

    def vc_state(self):
        """Chiamata attuale per il tablet (None se non sei in un canale vocale)."""
        with self.lock:
            if not self.vc:
                return None
            mem = sorted(self.vc["m"].values(), key=lambda m: m["n"].lower())
            return {"id": self.vc["id"], "n": self.vc["n"], "g": self.vc["g"], "me": self.me,
                    "m": [dict(m, sp=m["id"] in self.vc["sp"]) for m in mem]}

    def logout(self, reauth=False):
        """Dimentica il token e chiude la sessione; con reauth chiede subito una nuova autorizzazione."""
        try:
            os.remove(DISCORD_TOKEN)
        except OSError:
            pass
        with self.lock:
            self.drop = True
            self.want_auth = reauth
        self.wake.set()

    def patch_member(self, uid, **kw):
        with self.lock:
            if self.vc and uid in self.vc["m"]:
                self.vc["m"][uid].update(kw)

    def request(self, auth=False, **vals):
        """auth: avvia l'autorizzazione; vals: mute/deaf -> bool (aggiornamento ottimistico, senza attesa)."""
        self.start()
        with self.lock:
            if auth:
                self.want_auth = True
            if vals and self.st.get("s") == "ok":
                args = {k: vals[k] for k in ("mute", "deaf") if k in vals}
                if "inv" in vals:
                    args["input"] = {"volume": vals["inv"]}
                self.queue.append({"cmd": "SET_VOICE_SETTINGS", "args": args})
                self.st.update(vals)
            out = dict(self.st)
        self.wake.set()
        return out

    def run(self, fn, timeout=8.0):
        """Esegue fn() nel thread della pipe (puo' usare self._cmd) e ne restituisce il risultato."""
        self.start()
        job = {"fn": fn, "done": threading.Event(), "res": None, "err": None}
        with self.lock:
            if self.st.get("s") != "ok":
                raise DiscordError("Discord non collegato")
            self.queue.append(job)
        self.wake.set()
        if not job["done"].wait(timeout):
            raise DiscordError("Discord non risponde")
        if job["err"]:
            raise DiscordError(job["err"])
        return job["res"]

    def call(self, cmd, args, timeout=8.0):
        return self.run(lambda: self._cmd(cmd, args), timeout)

    def cached(self, key, ttl, fn):
        hit = self.cache.get(key)
        if hit and time.time() - hit[0] < ttl:
            return hit[1]
        val = fn()
        self.cache[key] = (time.time(), val)
        return val

    # --- dati per la sezione Discord ---
    def guilds(self):
        def get():
            gs = self.call("GET_GUILDS", {}).get("guilds") or []
            return [{"id": g.get("id"), "n": g.get("name") or "?", "i": g.get("icon_url") or ""} for g in gs]
        return self.cached("guilds", 60, get)

    def channels(self, gid):
        """Canali vocali del server, con chi c'e' dentro (un solo lavoro nel thread della pipe)."""
        def work():
            chs = self._cmd("GET_CHANNELS", {"guild_id": gid}).get("channels") or []
            out = []
            for c in chs:
                if c.get("type") not in (2, 13):     # vocale, stage
                    continue
                d = self._cmd("GET_CHANNEL", {"channel_id": c["id"]})
                out.append({"id": c["id"], "n": d.get("name") or c.get("name") or "?", "p": d.get("position", 0),
                            "m": [self._member(v) for v in d.get("voice_states") or []]})
            out.sort(key=lambda c: c["p"])
            return out
        return self.cached("ch:" + gid, 3, lambda: self.run(work, 12.0))

    @staticmethod
    def _member(v):
        u = v.get("user") or {}
        vs = v.get("voice_state") or {}
        return {"id": u.get("id") or "", "n": v.get("nick") or u.get("global_name") or u.get("username") or "?",
                "av": u.get("avatar") or "", "vol": int(round(v.get("volume", 100) or 0)), "lm": bool(v.get("mute")),
                "sm": bool(vs.get("self_mute") or vs.get("mute")), "sd": bool(vs.get("self_deaf") or vs.get("deaf"))}

    # --- pipe ---
    def _read(self, n):
        buf = b""
        while len(buf) < n:
            part = self.f.read(n - len(buf))
            if not part:
                raise OSError("pipe chiusa")
            buf += part
        return buf

    def _send(self, op, obj):
        data = json.dumps(obj).encode("utf-8")
        self.f.write(struct.pack("<II", op, len(data)) + data)

    def _recv(self):
        op, n = struct.unpack("<II", self._read(8))
        d = json.loads(self._read(n).decode("utf-8")) if n else {}
        if op == 2:
            raise OSError("Discord ha chiuso la connessione: %s" % d.get("message", d))
        if op == 3:
            self._send(4, d)
        return op, d

    def _avail(self):
        n = ctypes.c_ulong()
        if not _k32.PeekNamedPipe(self.h, None, 0, None, ctypes.byref(n), None):
            raise OSError("pipe chiusa")
        return n.value

    def _cmd(self, cmd, args, evt=None):
        nonce = secrets.token_hex(8)
        msg = {"cmd": cmd, "args": args, "nonce": nonce}
        if evt:
            msg["evt"] = evt
        self._send(1, msg)
        while True:
            op, d = self._recv()
            if op != 1:
                continue
            if d.get("nonce") == nonce:
                if d.get("evt") == "ERROR":
                    raise DiscordError("%s: %s" % ((d.get("data") or {}).get("code"), (d.get("data") or {}).get("message")))
                return d.get("data") or {}
            self._event(d)

    def _event(self, d):
        evt, v = d.get("evt"), d.get("data") or {}
        if evt == "VOICE_SETTINGS_UPDATE":
            self._set(**self._vs(v))
        elif evt == "VOICE_CHANNEL_SELECT":
            self.vc_dirty = True
        elif evt in self.VC_EVENTS:
            with self.lock:
                if not self.vc:
                    return
                if evt == "SPEAKING_START":
                    self.vc["sp"].add(v.get("user_id"))
                elif evt == "SPEAKING_STOP":
                    self.vc["sp"].discard(v.get("user_id"))
                elif evt == "VOICE_STATE_DELETE":
                    uid = (v.get("user") or {}).get("id")
                    self.vc["m"].pop(uid, None)
                    self.vc["sp"].discard(uid)
                else:
                    m = self._member(v)
                    if m["id"]:
                        self.vc["m"][m["id"]] = m

    def _load_vc(self):
        """Rilegge il canale vocale attuale e sposta le iscrizioni agli eventi (chi parla, chi entra/esce)."""
        old = self.vc["id"] if self.vc else None
        ch = self._cmd("GET_SELECTED_VOICE_CHANNEL", {}) or {}
        new = ch.get("id")
        if old and old != new:
            for e in self.VC_EVENTS:
                try:
                    self._cmd("UNSUBSCRIBE", {"channel_id": old}, evt=e)
                except DiscordError:
                    pass
        vc = None
        if new:
            vc = {"id": new, "n": ch.get("name") or "?", "g": ch.get("guild_id") or "", "sp": set(),
                  "m": {m["id"]: m for m in (self._member(v) for v in ch.get("voice_states") or []) if m["id"]}}
        with self.lock:
            self.vc = vc
        if new and new != old:
            for e in self.VC_EVENTS:
                try:
                    self._cmd("SUBSCRIBE", {"channel_id": new}, evt=e)
                except DiscordError as ex:
                    self._log("iscrizione %s rifiutata (%s)" % (e, ex))
        self.cache = {k: c for k, c in self.cache.items() if not k.startswith("ch:")}
        if (old or None) != (new or None):
            self._log("canale vocale: %s" % (vc["n"] if vc else "nessuno"))

    def _set(self, **kw):
        with self.lock:
            self.st.update(kw)

    @staticmethod
    def _vs(v):
        """Impostazioni voce che interessano il tablet: muto, cuffie, volume del microfono."""
        out = {"mute": bool(v.get("mute")), "deaf": bool(v.get("deaf"))}
        inv = (v.get("input") or {}).get("volume")
        if isinstance(inv, (int, float)):
            out["inv"] = int(round(inv))
        return out

    # --- OAuth ---
    @staticmethod
    def _cfg():
        try:
            with open(DISCORD_CFG, encoding="utf-8-sig") as fh:
                c = json.load(fh)
        except (OSError, ValueError):
            return None
        cid, sec = str(c.get("client_id", "")), str(c.get("client_secret", ""))
        return (cid, sec) if cid.isdigit() and sec and "PASTE" not in sec else None

    @staticmethod
    def _token_req(cfg, **form):
        import urllib.error
        import urllib.parse
        import urllib.request
        form.update(client_id=cfg[0], client_secret=cfg[1])
        req = urllib.request.Request("https://discord.com/api/oauth2/token",
                                     urllib.parse.urlencode(form).encode(),
                                     {"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "TabDeck/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                t = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise DiscordError("token HTTP %d" % e.code)
        except (OSError, ValueError) as e:
            raise DiscordError("token: %s" % e)
        if "access_token" not in t:
            raise DiscordError("token: risposta senza access_token")
        t["expires_at"] = time.time() + int(t.get("expires_in", 0))
        with open(DISCORD_TOKEN, "w", encoding="utf-8") as fh:
            json.dump({k: t.get(k) for k in ("access_token", "refresh_token", "expires_at", "scope")}, fh)
        return t

    def _authenticate(self, cfg):
        """True se autenticato con il token salvato (rinnovandolo se serve)."""
        try:
            with open(DISCORD_TOKEN, encoding="utf-8") as fh:
                tok = json.load(fh)
        except (OSError, ValueError):
            return False
        for attempt in (0, 1):
            if attempt or time.time() > tok.get("expires_at", 0) - 3600:
                if not tok.get("refresh_token"):
                    return False
                try:
                    tok = self._token_req(cfg, grant_type="refresh_token", refresh_token=tok["refresh_token"])
                except DiscordError as e:
                    self._log("rinnovo token fallito (%s)" % e)
                    return False
            try:
                a = self._cmd("AUTHENTICATE", {"access_token": tok["access_token"]})
                if set(DISCORD_SCOPES) - set(a.get("scopes") or DISCORD_SCOPES):
                    self._log("servono nuovi permessi: chiedo di nuovo l'autorizzazione")
                    return False
                return True
            except DiscordError as e:
                self._log("autenticazione rifiutata (%s)" % e)
        return False

    # --- ciclo ---
    def _session(self, cfg):
        self._send(0, {"v": 1, "client_id": cfg[0]})
        _, ready = self._recv()   # READY
        self.me = ((ready.get("data") or {}).get("user") or {}).get("id")
        while not self._authenticate(cfg):
            self._set(s="auth", msg="")
            self.drop = False
            while True:
                with self.lock:
                    go, self.want_auth = self.want_auth, False
                if go:
                    break
                self._avail()          # se Discord si chiude, esce con OSError
                time.sleep(0.3)
            self._set(s="wait", msg="")
            self._log("chiedo l'autorizzazione (popup in Discord)")
            try:
                code = self._cmd("AUTHORIZE", {"client_id": cfg[0], "scopes": DISCORD_SCOPES}).get("code")
                self._token_req(cfg, grant_type="authorization_code", code=code, redirect_uri=DISCORD_REDIRECT)
            except DiscordError as e:
                self._log("autorizzazione non riuscita (%s)" % e)
                self._set(s="auth", msg="non autorizzato")
        with self.lock:
            self.want_auth = False
            self.drop = False
            self.queue = []
        v = self._cmd("GET_VOICE_SETTINGS", {})
        self._cmd("SUBSCRIBE", {}, evt="VOICE_SETTINGS_UPDATE")
        self._cmd("SUBSCRIBE", {}, evt="VOICE_CHANNEL_SELECT")
        self._load_vc()
        self._set(s="ok", msg="", **self._vs(v))
        self._log("collegato (muto=%s, silenziato=%s)" % (bool(v.get("mute")), bool(v.get("deaf"))))
        while True:
            with self.lock:
                todo, self.queue = self.queue, []
            for job in todo:
                try:
                    if "fn" in job:
                        job["res"] = job["fn"]()
                    else:
                        v = self._cmd(job["cmd"], job["args"])
                        if job["cmd"] == "SET_VOICE_SETTINGS":
                            self._set(**self._vs(v))
                            self._log("impostato %s" % job["args"])
                except DiscordError as e:
                    job["err"] = str(e)
                    self._log("comando rifiutato (%s)" % e)
                except Exception:
                    job["err"] = "Discord disconnesso"
                    if job.get("done"):
                        job["done"].set()
                    raise
                if job.get("done"):
                    job["done"].set()
            while self._avail():
                op, d = self._recv()
                if op == 1:
                    self._event(d)
            if self.vc_dirty:
                self.vc_dirty = False
                self._load_vc()
            if self.drop:
                self.drop = False
                raise DiscordError("scollegato dal tablet")
            self.wake.wait(0.1)
            self.wake.clear()

    def _run(self):
        import msvcrt
        last = None
        while True:
            cfg = self._cfg()
            if not cfg:
                self._set(s="off", msg="da configurare")
                time.sleep(10)
                continue
            for i in range(10):
                try:
                    self.f = open(r"\\.\pipe\discord-ipc-%d" % i, "r+b", buffering=0)
                    break
                except OSError:
                    self.f = None
            if not self.f:
                self._set(s="off", msg="Discord chiuso")
                time.sleep(5)
                continue
            self.h = msvcrt.get_osfhandle(self.f.fileno())
            try:
                self._session(cfg)
            except (OSError, ValueError, KeyError, DiscordError, struct.error) as e:
                if str(e) != last:
                    self._log("disconnesso (%s)" % e)
                last = str(e)
            finally:
                try:
                    self.f.close()
                except OSError:
                    pass
                self.f = None
                with self.lock:
                    pending, self.queue, self.vc = self.queue, [], None
                    self.st.update(s="off", msg="Discord chiuso")
                for job in pending:
                    if job.get("done"):
                        job["err"] = "Discord disconnesso"
                        job["done"].set()
                self.cache = {}
            time.sleep(3)


DISCORD = Discord()


# --- mixer: volume per singola app (sessioni audio di Core Audio) ---
_P, _VP = ctypes.POINTER, ctypes.c_void_p
IID_IAudioSessionManager2 = _guid("{77AA99A0-1BD6-484F-8BC7-2C654C9A9B6F}")
IID_IAudioSessionControl2 = _guid("{BFB7FF88-7239-4FC9-8FA2-07C950BE9C6D}")
IID_ISimpleAudioVolume = _guid("{87CE5498-68D6-44E5-9215-6DA47EF883D8}")
_ver = ctypes.WinDLL("version")
_ver.GetFileVersionInfoSizeW.argtypes = [ctypes.c_wchar_p, _VP]
_ver.GetFileVersionInfoW.argtypes = [ctypes.c_wchar_p, ctypes.c_ulong, ctypes.c_ulong, _VP]
_ver.VerQueryValueW.argtypes = [_VP, ctypes.c_wchar_p, _P(_VP), _P(ctypes.c_uint)]
NAME_CACHE = {}


def _release(p):
    if p.value:
        _com(p, 2, (), restype=ctypes.c_ulong)


def _qi(p, iid):
    out = _VP()
    _com(p, 0, (_P(_GUID), _P(_VP)), ctypes.byref(iid), ctypes.byref(out))
    return out


def app_name(exe):
    """Nome leggibile del programma (descrizione del file .exe), altrimenti il nome del file."""
    if exe in NAME_CACHE:
        return NAME_CACHE[exe]
    name = os.path.splitext(os.path.basename(exe))[0]
    try:
        n = _ver.GetFileVersionInfoSizeW(exe, None)
        buf = ctypes.create_string_buffer(n) if n else None
        if buf and _ver.GetFileVersionInfoW(exe, 0, n, buf):
            tr, ln = _VP(), ctypes.c_uint()
            if _ver.VerQueryValueW(buf, r"\VarFileInfo\Translation", ctypes.byref(tr), ctypes.byref(ln)) and ln.value >= 4:
                lang, cp = ctypes.cast(tr, _P(ctypes.c_ushort))[0], ctypes.cast(tr, _P(ctypes.c_ushort))[1]
                p = _VP()
                if _ver.VerQueryValueW(buf, r"\StringFileInfo\%04x%04x\FileDescription" % (lang, cp),
                                       ctypes.byref(p), ctypes.byref(ln)) and ln.value > 1:
                    desc = ctypes.wstring_at(p).strip()
                    if desc and len(desc) <= 40:
                        name = desc
    except OSError:
        pass
    NAME_CACHE[exe] = name
    return name


def _each_session(fn):
    """Chiama fn(pid, ISimpleAudioVolume, e' attiva) per ogni sessione audio non scaduta."""
    def op(mgr):
        se, n = _VP(), ctypes.c_int()
        _com(mgr, 5, (_P(_VP),), ctypes.byref(se))
        try:
            _com(se, 3, (_P(ctypes.c_int),), ctypes.byref(n))
            for i in range(n.value):
                c, c2, sv = _VP(), _VP(), _VP()
                try:
                    _com(se, 4, (ctypes.c_int, _P(_VP)), i, ctypes.byref(c))
                    state, pid = ctypes.c_int(), ctypes.c_ulong()
                    _com(c, 3, (_P(ctypes.c_int),), ctypes.byref(state))
                    if state.value == 2:      # AudioSessionStateExpired
                        continue
                    c2, sv = _qi(c, IID_IAudioSessionControl2), _qi(c, IID_ISimpleAudioVolume)
                    _com(c2, 14, (_P(ctypes.c_ulong),), ctypes.byref(pid))
                    fn(pid.value, sv, state.value == 1)
                except OSError:
                    continue
                finally:
                    for p in (sv, c2, c):
                        _release(p)
        finally:
            _release(se)
    _with_endpoint(op, IID_IAudioSessionManager2)


def _sess_read(sv):
    f, m = ctypes.c_float(), ctypes.c_int()
    _com(sv, 4, (_P(ctypes.c_float),), ctypes.byref(f))
    _com(sv, 6, (_P(ctypes.c_int),), ctypes.byref(m))
    return int(round(f.value * 100)), bool(m.value)


def mixer_list():
    """Programmi che hanno una sessione audio, raggruppati per eseguibile (Chrome/Discord ne aprono piu' d'una)."""
    apps = {}

    def cb(pid, sv, active):
        exe = _exe_of_pid(pid) if pid else ""
        key = icon_key(exe) if exe else "system"
        vol, mute = _sess_read(sv)
        a = apps.get(key)
        if a is None:
            apps[key] = {"k": key, "n": app_name(exe) if exe else "Suoni di sistema", "i": key if exe else "",
                         "vol": vol, "mute": mute, "on": active}
        else:
            a["on"] = a["on"] or active
    _each_session(cb)
    return sorted(apps.values(), key=lambda a: (a["k"] == "system", not a["on"], a["n"].lower()))


def mixer_set(key, level=None, mute=None):
    """Applica volume/muto a tutte le sessioni del programma `key`. Restituisce False se non c'e' piu'."""
    hit = []

    def cb(pid, sv, _active):
        exe = _exe_of_pid(pid) if pid else ""
        if (icon_key(exe) if exe else "system") != key:
            return
        if level is not None:
            _com(sv, 3, (ctypes.c_float, _VP), ctypes.c_float(level / 100.0), None)
        if mute is not None:
            _com(sv, 5, (ctypes.c_int, _VP), 1 if mute else 0, None)
        hit.append(True)
    _each_session(cb)
    return bool(hit)


# --- "in riproduzione": sessione multimediale di Windows (WinRT, solo ctypes) ---
_cbase = ctypes.WinDLL("combase")
_cbase.WindowsCreateString.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, _P(_VP)]
_cbase.WindowsCreateString.restype = ctypes.HRESULT
_cbase.WindowsGetStringRawBuffer.argtypes = [_VP, _P(ctypes.c_uint32)]
_cbase.WindowsGetStringRawBuffer.restype = _VP
_cbase.WindowsDeleteString.argtypes = [_VP]
_cbase.RoGetActivationFactory.argtypes = [_VP, _P(_GUID), _P(_VP)]
_cbase.RoGetActivationFactory.restype = ctypes.HRESULT
_shc = ctypes.WinDLL("shcore")
_shc.CreateStreamOverRandomAccessStream.argtypes = [_VP, _P(_GUID), _P(_VP)]
_shc.CreateStreamOverRandomAccessStream.restype = ctypes.HRESULT
IID_GSMTCManagerStatics = _guid("{2050C4EE-11A0-57DE-AED7-C97C70338245}")
IID_IAsyncInfo = _guid("{00000036-0000-0000-C000-000000000046}")
IID_IStream = _guid("{0000000C-0000-0000-C000-000000000046}")
IID_IShellItem = _guid("{43826D1E-E718-42EE-BC55-A1E261C37BFE}")
MEDIA_STATUS = {4: "play", 5: "pause"}       # altri: chiuso/aperto/cambio/fermo
MEDIA_CMDS = {"toggle": 20, "next": 16, "prev": 17}
COVER_MAX = 4 * 1024 * 1024


def _hstring_take(h):
    if not h.value:
        return ""
    n = ctypes.c_uint32()
    s = ctypes.wstring_at(_cbase.WindowsGetStringRawBuffer(h, ctypes.byref(n)), n.value)
    _cbase.WindowsDeleteString(h)
    return s


def _hget(obj, idx):
    h = _VP()
    _com(obj, idx, (_P(_VP),), ctypes.byref(h))
    return _hstring_take(h)


def _await(op, want_obj=True, timeout=3.0):
    """Attende un'operazione asincrona WinRT (IAsyncOperation) e ne restituisce il risultato."""
    info = _VP()
    try:
        info = _qi(op, IID_IAsyncInfo)
        t0 = time.time()
        while True:
            s = ctypes.c_int()
            _com(info, 7, (_P(ctypes.c_int),), ctypes.byref(s))
            if s.value == 1:
                break
            if s.value > 1 or time.time() - t0 > timeout:
                raise OSError("operazione WinRT non riuscita (%d)" % s.value)
            time.sleep(0.005)
        out = _VP() if want_obj else ctypes.c_int64()
        _com(op, 8, (_P(type(out)),), ctypes.byref(out))
        return out
    finally:
        _release(info)
        _release(op)


def shell_display_name(parsing):
    """Nome mostrato da Esplora risorse (es. per shell:AppsFolder\\<AUMID>); None se non risolvibile."""
    hr = ctypes.windll.ole32.CoInitializeEx(None, 2)
    item, s = _VP(), ctypes.c_wchar_p()
    try:
        _sh32.SHCreateItemFromParsingName(parsing, None, ctypes.byref(IID_IShellItem), ctypes.byref(item))
        _com(item, 5, (ctypes.c_int, _P(ctypes.c_wchar_p)), 0, ctypes.byref(s))
        name = s.value
        ctypes.windll.ole32.CoTaskMemFree(s)
        return name
    except OSError:
        return None
    finally:
        _release(item)
        if hr in (0, 1):
            ctypes.windll.ole32.CoUninitialize()


class Media:
    """Un thread dedicato (apartment MTA) tiene il gestore delle sessioni multimediali e fa tutte le chiamate."""
    def __init__(self):
        self.q = []
        self.cv = threading.Condition()
        self.mgr = _VP()
        self.track = None            # (app, titolo, artista) dell'ultima copertina letta
        self.cover = (None, None)    # (chiave, (tipo, dati))
        threading.Thread(target=self._loop, daemon=True).start()

    def call(self, fn, timeout=5.0):
        box, done = {}, threading.Event()
        with self.cv:
            self.q.append((fn, box, done))
            self.cv.notify()
        if not done.wait(timeout):
            raise OSError("media: nessuna risposta")
        if "e" in box:
            raise box["e"]
        return box["r"]

    def _loop(self):
        ctypes.windll.ole32.CoInitializeEx(None, 0)
        while True:
            with self.cv:
                while not self.q:
                    self.cv.wait()
                fn, box, done = self.q.pop(0)
            try:
                box["r"] = fn()
            except Exception as e:  # noqa: BLE001
                box["e"] = e if isinstance(e, OSError) else OSError(str(e))
                _release(self.mgr)       # al prossimo giro si riparte da zero
                self.mgr = _VP()
            done.set()

    def _session(self):
        if not self.mgr.value:
            cls = "Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager"
            hs, fac = _VP(), _VP()
            _cbase.WindowsCreateString(cls, len(cls), ctypes.byref(hs))
            try:
                _cbase.RoGetActivationFactory(hs, ctypes.byref(IID_GSMTCManagerStatics), ctypes.byref(fac))
            finally:
                _cbase.WindowsDeleteString(hs)
            try:
                op = _VP()
                _com(fac, 6, (_P(_VP),), ctypes.byref(op))
                self.mgr = _await(op)
            finally:
                _release(fac)
        ses = _VP()
        _com(self.mgr, 6, (_P(_VP),), ctypes.byref(ses))
        return ses

    def _read_cover(self, props):
        ref, stream, ist = _VP(), _VP(), _VP()
        try:
            _com(props, 15, (_P(_VP),), ctypes.byref(ref))
            if not ref.value:
                return None
            op = _VP()
            _com(ref, 6, (_P(_VP),), ctypes.byref(op))
            stream = _await(op)
            _shc.CreateStreamOverRandomAccessStream(stream, ctypes.byref(IID_IStream), ctypes.byref(ist))
            chunks, total, buf = [], 0, (ctypes.c_ubyte * 65536)()
            while total < COVER_MAX:
                got = ctypes.c_ulong()
                _com(ist, 3, (_VP, ctypes.c_ulong, _P(ctypes.c_ulong)), buf, 65536, ctypes.byref(got), restype=ctypes.c_long)
                if not got.value:
                    break
                chunks.append(bytes(buf[:got.value]))
                total += got.value
            data = b"".join(chunks)
        finally:
            for p in (ist, stream, ref):
                _release(p)
        for magic, ctype in ((b"\x89PNG", "image/png"), (b"\xff\xd8", "image/jpeg"), (b"GIF8", "image/gif"), (b"BM", "image/bmp")):
            if data.startswith(magic):
                return ctype, data
        return None

    def state(self):
        def fn():
            ses = self._session()
            if not ses.value:
                return {"on": False}
            props, pi, tl = _VP(), _VP(), _VP()
            try:
                app = _hget(ses, 6)
                op = _VP()
                _com(ses, 7, (_P(_VP),), ctypes.byref(op))
                props = _await(op)
                title, artist, album = _hget(props, 6), _hget(props, 9), _hget(props, 10)
                _com(ses, 9, (_P(_VP),), ctypes.byref(pi))
                st = ctypes.c_int()
                _com(pi, 7, (_P(ctypes.c_int),), ctypes.byref(st))
                _com(ses, 8, (_P(_VP),), ctypes.byref(tl))
                t = []
                for idx in (6, 7, 10, 11):   # inizio, fine, posizione, ultimo aggiornamento (100 ns)
                    v = ctypes.c_int64()
                    _com(tl, idx, (_P(ctypes.c_int64),), ctypes.byref(v))
                    t.append(v.value)
                track = (app, title, artist)
                if track != self.track:
                    self.track = track
                    c = self._read_cover(props)
                    self.cover = (hashlib.sha1(c[1]).hexdigest()[:16] if c else None, c)
            finally:
                for p in (tl, pi, props, ses):
                    _release(p)
            status = MEDIA_STATUS.get(st.value, "stop")
            dur, pos = (t[1] - t[0]) / 1e7, (t[2] - t[0]) / 1e7
            if status == "play" and t[3] > 0:   # la posizione e' riferita all'ultimo aggiornamento dell'app
                pos += max(0.0, (time.time() + 11644473600) - t[3] / 1e7)
            return {"on": True, "app": app, "t": title, "a": artist, "al": album, "st": status,
                    "dur": round(dur, 1) if dur > 0 else 0, "pos": round(min(max(pos, 0.0), dur), 1) if dur > 0 else 0,
                    "c": self.cover[0]}
        s = self.call(fn)
        if s.get("on"):
            s["an"], s["i"] = media_app(s["app"])
        return s

    def command(self, name):
        def fn():
            ses = self._session()
            if not ses.value:
                return False
            try:
                op = _VP()
                _com(ses, MEDIA_CMDS[name], (_P(_VP),), ctypes.byref(op))
                return bool(_await(op, want_obj=False).value & 0xff)
            finally:
                _release(ses)
        return self.call(fn)

    def seek(self, seconds):
        def fn():
            ses, tl = self._session(), _VP()
            if not ses.value:
                return False
            try:
                _com(ses, 8, (_P(_VP),), ctypes.byref(tl))
                start = ctypes.c_int64()
                _com(tl, 6, (_P(ctypes.c_int64),), ctypes.byref(start))
                op = _VP()
                _com(ses, 24, (ctypes.c_int64, _P(_VP)), start.value + int(seconds * 1e7), ctypes.byref(op))
                return bool(_await(op, want_obj=False).value & 0xff)
            finally:
                _release(tl)
                _release(ses)
        return self.call(fn)


MEDIA_APPS = {}


def media_app(aumid):
    """(nome, chiave icona) dell'app che sta riproducendo, dal suo AppUserModelID o nome .exe."""
    if aumid not in MEDIA_APPS:
        shell = "shell:AppsFolder\\" + aumid
        name = shell_display_name(shell)
        if name:
            MEDIA_APPS[aumid] = (name, icon_key(shell))
        else:
            base = aumid.rsplit("!", 1)[-1]
            MEDIA_APPS[aumid] = (base[:-4] if base.lower().endswith(".exe") else base, "")
    return MEDIA_APPS[aumid]


MEDIA = Media()


# --- monitor del PC: contatori di Windows (PDH, come Gestione attivita') + GPU NVIDIA (NVML) ---
_pdh = ctypes.WinDLL("pdh")
for _fn, _args in (("PdhOpenQueryW", [_VP, ctypes.c_size_t, _P(_VP)]),
                   ("PdhAddEnglishCounterW", [_VP, ctypes.c_wchar_p, ctypes.c_size_t, _P(_VP)]),
                   ("PdhCollectQueryData", [_VP]), ("PdhCloseQuery", [_VP]),
                   ("PdhGetFormattedCounterValue", [_VP, ctypes.c_ulong, _VP, _VP]),
                   ("PdhGetFormattedCounterArrayW", [_VP, ctypes.c_ulong, _P(ctypes.c_ulong), _P(ctypes.c_ulong), _VP])):
    getattr(_pdh, _fn).argtypes, getattr(_pdh, _fn).restype = _args, ctypes.c_long
PDH_FMT = 0x200 | 0x8000   # double, senza tetto a 100 (il turbo supera il 100%)


class _PdhValue(ctypes.Structure):
    _fields_ = [("status", ctypes.c_ulong), ("value", ctypes.c_double)]


class _PdhItem(ctypes.Structure):
    _fields_ = [("name", ctypes.c_wchar_p), ("v", _PdhValue)]


class _MemStatus(ctypes.Structure):
    _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("total", ctypes.c_ulonglong),
                ("avail", ctypes.c_ulonglong), ("pf_total", ctypes.c_ulonglong), ("pf_avail", ctypes.c_ulonglong),
                ("v_total", ctypes.c_ulonglong), ("v_avail", ctypes.c_ulonglong), ("v_ext", ctypes.c_ulonglong)]


class _NvUtil(ctypes.Structure):
    _fields_ = [("gpu", ctypes.c_uint), ("mem", ctypes.c_uint)]


class _NvMem(ctypes.Structure):
    _fields_ = [("total", ctypes.c_ulonglong), ("free", ctypes.c_ulonglong), ("used", ctypes.c_ulonglong)]


PDH_COUNTERS = {
    "cpu": r"\Processor Information(_Total)\% Processor Utility",
    "perf": r"\Processor Information(_Total)\% Processor Performance",
    "freq": r"\Processor Information(_Total)\Processor Frequency",
    "cores": r"\Processor Information(*)\% Processor Utility",
    "rx": r"\Network Interface(*)\Bytes Received/sec",
    "tx": r"\Network Interface(*)\Bytes Sent/sec",
    "dr": r"\PhysicalDisk(_Total)\Disk Read Bytes/sec",
    "dw": r"\PhysicalDisk(_Total)\Disk Write Bytes/sec",
    "didle": r"\PhysicalDisk(_Total)\% Idle Time",
}
STATS_HIST = 60          # secondi di storico per i grafici
STATS_IDLE = 20          # senza richieste per 20 s il campionamento si ferma
NET_SKIP = ("isatap", "teredo", "loopback", "pseudo")


class Stats:
    def __init__(self):
        self.lock = threading.Lock()
        self.last_req = 0.0
        self.cur, self.hist = {}, {k: [] for k in ("cpu", "gpu", "ram", "vram")}
        self.thread = None

    def get(self, with_hist):
        with self.lock:
            self.last_req = time.time()
            if self.thread is None or not self.thread.is_alive():
                self.thread = threading.Thread(target=self._loop, daemon=True)
                self.thread.start()
            out = dict(self.cur)
            if with_hist:
                out["hist"] = {k: list(v) for k, v in self.hist.items()}
            return out

    @staticmethod
    def _pdh_open():
        q, cs = _VP(), {}
        if _pdh.PdhOpenQueryW(None, 0, ctypes.byref(q)) != 0:
            raise OSError("PDH non disponibile")
        for k, path in PDH_COUNTERS.items():
            c = _VP()
            if _pdh.PdhAddEnglishCounterW(q, path, 0, ctypes.byref(c)) == 0:
                cs[k] = c
        _pdh.PdhCollectQueryData(q)
        return q, cs

    @staticmethod
    def _one(c):
        v = _PdhValue()
        if c is None or _pdh.PdhGetFormattedCounterValue(c, PDH_FMT, None, ctypes.byref(v)) != 0 or v.status > 1:
            return None
        return v.value

    @staticmethod
    def _many(c):
        if c is None:
            return {}
        size, n = ctypes.c_ulong(0), ctypes.c_ulong(0)
        _pdh.PdhGetFormattedCounterArrayW(c, PDH_FMT, ctypes.byref(size), ctypes.byref(n), None)
        if not size.value:
            return {}
        buf = ctypes.create_string_buffer(size.value)
        if _pdh.PdhGetFormattedCounterArrayW(c, PDH_FMT, ctypes.byref(size), ctypes.byref(n), buf) != 0:
            return {}
        items = ctypes.cast(buf, _P(_PdhItem))
        return {items[i].name: items[i].v.value for i in range(n.value) if items[i].v.status <= 1}

    @staticmethod
    def _nvml():
        try:
            nv = ctypes.CDLL("nvml.dll")
            h = _VP()
            if nv.nvmlInit_v2() != 0:
                return None, None, ""
            if nv.nvmlDeviceGetHandleByIndex_v2(0, ctypes.byref(h)) != 0:
                nv.nvmlShutdown()
                return None, None, ""
            name = ctypes.create_string_buffer(96)
            nv.nvmlDeviceGetName(h, name, 96)
            return nv, h, name.value.decode("utf-8", "replace").replace("NVIDIA GeForce ", "")
        except OSError:
            return None, None, ""

    @staticmethod
    def _gpu(nv, h):
        u, t, m, pw, fan, clk = _NvUtil(), ctypes.c_uint(), _NvMem(), ctypes.c_uint(), ctypes.c_uint(), ctypes.c_uint()
        g = {}
        if nv.nvmlDeviceGetUtilizationRates(h, ctypes.byref(u)) == 0:
            g["gpu"] = u.gpu
        if nv.nvmlDeviceGetTemperature(h, 0, ctypes.byref(t)) == 0:
            g["gt"] = t.value
        if nv.nvmlDeviceGetMemoryInfo(h, ctypes.byref(m)) == 0 and m.total:
            g["vu"], g["vt"] = round(m.used / 2 ** 30, 1), round(m.total / 2 ** 30, 1)
            g["vram"] = round(m.used * 100 / m.total)
        if nv.nvmlDeviceGetPowerUsage(h, ctypes.byref(pw)) == 0:
            g["gw"] = round(pw.value / 1000)
        if nv.nvmlDeviceGetFanSpeed(h, ctypes.byref(fan)) == 0:
            g["gf"] = fan.value
        if nv.nvmlDeviceGetClockInfo(h, 0, ctypes.byref(clk)) == 0:
            g["gc"] = clk.value
        return g

    def _sample(self, cs, nv, h, gname, ms):
        cur = {"gn": gname}
        cpu, perf, freq = self._one(cs.get("cpu")), self._one(cs.get("perf")), self._one(cs.get("freq"))
        if cpu is not None:
            cur["cpu"] = round(min(100.0, cpu))
        if perf is not None and freq:
            cur["mhz"] = round(freq * perf / 100)
        cores = sorted(((k, v) for k, v in self._many(cs.get("cores")).items() if "_Total" not in k),
                       key=lambda kv: [int(x) for x in kv[0].split(",") if x.isdigit()])
        cur["cores"] = [round(min(100.0, v)) for _k, v in cores]
        for k in ("rx", "tx"):
            cur[k] = round(sum(v for n, v in self._many(cs.get(k)).items() if not any(x in n.lower() for x in NET_SKIP)))
        for k in ("dr", "dw"):
            cur[k] = round(self._one(cs.get(k)) or 0)
        idle = self._one(cs.get("didle"))
        if idle is not None:
            cur["disk"] = round(max(0.0, min(100.0, 100 - idle)))
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms)):
            used = ms.total - ms.avail
            cur["ram"], cur["ru"], cur["rt"] = round(used * 100 / ms.total), round(used / 2 ** 30, 1), round(ms.total / 2 ** 30, 1)
        if nv is not None:
            cur.update(self._gpu(nv, h))
        return cur

    def _loop(self):
        q, cs = self._pdh_open()
        nv, h, gname = self._nvml()
        ms = _MemStatus(dwLength=ctypes.sizeof(_MemStatus))
        try:
            while time.time() - self.last_req < STATS_IDLE:
                time.sleep(1.0)
                _pdh.PdhCollectQueryData(q)
                cur = self._sample(cs, nv, h, gname, ms)
                with self.lock:
                    self.cur = cur
                    for k, hist in self.hist.items():
                        hist.append(cur.get(k, 0))
                        del hist[:-STATS_HIST]
        finally:
            _pdh.PdhCloseQuery(q)
            if nv is not None:
                nv.nvmlShutdown()


STATS = Stats()


def cpu_name():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as k:
            n = winreg.QueryValueEx(k, "ProcessorNameString")[0]
        return re.sub(r"\s+", " ", re.sub(r"\b(AMD|Intel\(R\)|Core\(TM\)|CPU|Processor|\d+-Core)\b", "", n)).strip()
    except OSError:
        return ""


CPU_NAME = cpu_name()


# --- testo sullo schermo: OCR integrato di Windows (Windows.Media.Ocr, WinRT, solo ctypes) ---
IID_OcrEngineStatics = _guid("{5BFFA85A-3384-3540-9940-699120D428A8}")
IID_SoftwareBitmapStatics = _guid("{DF0385DB-672F-4A9D-806E-C2442F343E86}")
IID_CryptographicBufferStatics = _guid("{320B7E22-3CB0-4CDF-8663-1D28910065EB}")


class _Rect(ctypes.Structure):
    _fields_ = [("x", ctypes.c_float), ("y", ctypes.c_float), ("w", ctypes.c_float), ("h", ctypes.c_float)]


def _factory(cls, iid):
    hs, fac = _VP(), _VP()
    _cbase.WindowsCreateString(cls, len(cls), ctypes.byref(hs))
    try:
        _cbase.RoGetActivationFactory(hs, ctypes.byref(iid), ctypes.byref(fac))
    finally:
        _cbase.WindowsDeleteString(hs)
    return fac


def _vec(view):
    """Elementi di una IVectorView WinRT (vanno rilasciati dal chiamante)."""
    n = ctypes.c_uint()
    _com(view, 7, (_P(ctypes.c_uint),), ctypes.byref(n))
    out = []
    for i in range(n.value):
        it = _VP()
        _com(view, 6, (ctypes.c_uint, _P(_VP)), i, ctypes.byref(it))
        out.append(it)
    return out


def ocr_lines(w, h, bgra):
    """Righe di testo riconosciute: [(testo, x, y, larghezza, altezza)], dall'alto in basso."""
    def fn():
        objs = []
        try:
            cb = _factory("Windows.Security.Cryptography.CryptographicBuffer", IID_CryptographicBufferStatics)
            objs.append(cb)
            buf = _VP()
            data = (ctypes.c_ubyte * len(bgra)).from_buffer_copy(bgra)
            _com(cb, 9, (ctypes.c_uint32, _VP, _P(_VP)), len(bgra), data, ctypes.byref(buf))
            objs.append(buf)
            sbs = _factory("Windows.Graphics.Imaging.SoftwareBitmap", IID_SoftwareBitmapStatics)
            objs.append(sbs)
            bmp = _VP()   # Bgra8 (87), alfa ignorato (2)
            _com(sbs, 10, (_VP, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, _P(_VP)), buf, 87, w, h, 2, ctypes.byref(bmp))
            objs.append(bmp)
            es = _factory("Windows.Media.Ocr.OcrEngine", IID_OcrEngineStatics)
            objs.append(es)
            eng = _VP()
            _com(es, 10, (_P(_VP),), ctypes.byref(eng))
            if not eng.value:
                raise OSError("nessuna lingua OCR installata")
            objs.append(eng)
            op = _VP()
            _com(eng, 6, (_VP, _P(_VP)), bmp, ctypes.byref(op))
            res = _await(op)
            objs.append(res)
            lines = _VP()
            _com(res, 6, (_P(_VP),), ctypes.byref(lines))
            objs.append(lines)
            out = []
            for ln in _vec(lines):
                objs.append(ln)
                text = _hget(ln, 7)
                words = _VP()
                _com(ln, 6, (_P(_VP),), ctypes.byref(words))
                objs.append(words)
                x0 = y0 = 1e9
                x1 = y1 = -1e9
                for wd in _vec(words):
                    objs.append(wd)
                    r = _Rect()
                    _com(wd, 6, (_P(_Rect),), ctypes.byref(r))
                    x0, y0, x1, y1 = min(x0, r.x), min(y0, r.y), max(x1, r.x + r.w), max(y1, r.y + r.h)
                out.append((text, x0, y0, x1 - x0, y1 - y0))
            return sorted(out, key=lambda t: t[2])
        finally:
            for o in reversed(objs):
                _release(o)
    return MEDIA.call(fn, timeout=8.0)


def audio_overview():
    """Tutto cio' che serve alla scheda Audio in una sola risposta (letta ogni 1,5 s mentre e' aperta)."""
    out = {}
    for k, fn in (("m", MEDIA.state), ("apps", mixer_list), ("master", audio_state), ("mic", mic_state), ("dc", DISCORD.state)):
        try:
            out[k] = fn()
        except OSError as e:
            sys.stderr.write("[%s] audio %s: %s\n" % (time.strftime("%H:%M:%S"), k, e))
    return out


def send_keys(names):
    user32 = ctypes.windll.user32
    codes = [VK[n] for n in names]
    for c in codes:
        user32.keybd_event(c, 0, KEYEVENTF_EXTENDEDKEY if c in EXTENDED else 0, 0)
        time.sleep(0.02)
    for c in reversed(codes):
        flags = KEYEVENTF_KEYUP | (KEYEVENTF_EXTENDEDKEY if c in EXTENDED else 0)
        user32.keybd_event(c, 0, flags, 0)
        time.sleep(0.02)


# --- input a scancode (per i giochi), via SendInput ---
SCAN = {"LCTRL": (0x1D, False), "LSHIFT": (0x2A, False), "LALT": (0x38, False),
        "W": (0x11, False), "A": (0x1E, False), "S": (0x1F, False), "D": (0x20, False),
        "UP": (0x48, True), "LEFT": (0x4B, True), "DOWN": (0x50, True), "RIGHT": (0x4D, True)}
for _k in [HD2["menu"]] + [k for _m in HD2["dirs"].values() for k in _m.values()]:
    if _k not in SCAN:
        sys.exit("Tasto HD2 non supportato: %r (usa uno di %s)" % (_k, ", ".join(sorted(SCAN))))

ULONG_PTR = ctypes.c_size_t


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_ushort), ("wScan", ctypes.c_ushort), ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong), ("dwExtraInfo", ULONG_PTR)]


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long), ("mouseData", ctypes.c_ulong),
                ("dwFlags", ctypes.c_ulong), ("time", ctypes.c_ulong), ("dwExtraInfo", ULONG_PTR)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", _KEYBDINPUT), ("mi", _MOUSEINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("u", _INPUTUNION)]


KEYEVENTF_SCANCODE = 0x8
INPUT_LOCK = threading.Lock()  # due tocchi ravvicinati non si mescolano


# --- Ctrl + WASD -> frecce (solo in Helldivers 2): per chiamare a mano gli stratagemmi con WASD
#     quando in gioco l'inserimento e' impostato sulle frecce (come serve al tablet) ---
_LLPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, ctypes.c_size_t, ctypes.c_void_p)


class _KBDLL(ctypes.Structure):
    _fields_ = [("vkCode", ctypes.c_ulong), ("scanCode", ctypes.c_ulong), ("flags", ctypes.c_ulong),
                ("time", ctypes.c_ulong), ("dwExtraInfo", ULONG_PTR)]


REMAP = {0x57: 0x48, 0x41: 0x4B, 0x53: 0x50, 0x44: 0x4D}   # W A S D -> scancode di su sinistra giu' destra
_u32.SetWindowsHookExW.argtypes = [ctypes.c_int, _LLPROC, ctypes.c_void_p, ctypes.c_ulong]
_u32.SetWindowsHookExW.restype = ctypes.c_void_p
_u32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_size_t, ctypes.c_void_p]
_u32.CallNextHookEx.restype = ctypes.c_ssize_t
_u32.GetAsyncKeyState.argtypes = [ctypes.c_int]
_u32.GetAsyncKeyState.restype = ctypes.c_short
_k32.GetModuleHandleW.restype = ctypes.c_void_p


def _remap_thread():
    """Hook di tastiera a basso livello: con Ctrl sinistro premuto e HD2 in primo piano, W/A/S/D premuti a mano
    diventano le frecce (il tasto originale non arriva al gioco). Tutto il resto passa invariato.
    Niente lock qui dentro: il callback deve essere velocissimo, o Windows rallenta la tastiera."""
    state = {"fg_t": 0.0, "fg": False, "on": set()}      # "on": tasti WASD trasformati e ancora giu'
    hook = {}

    def in_game():
        now = time.time()
        if now - state["fg_t"] > 0.5:
            st = load_settings()
            REMAP_ON["on"] = st.get("remap") == "on" and st.get("input") == "arrows"
            state["fg_t"], state["fg"] = now, HD2["window"].upper() in foreground_title().upper()
        return state["fg"]

    def send(scan, up):
        inp = _INPUT(type=1, u=_INPUTUNION(ki=_KEYBDINPUT(0, scan, KEYEVENTF_SCANCODE | KEYEVENTF_EXTENDEDKEY
                                                          | (KEYEVENTF_KEYUP if up else 0), 0, 0)))
        ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))

    def proc(code, wparam, lparam):
        if code == 0:
            k = ctypes.cast(lparam, ctypes.POINTER(_KBDLL)).contents
            if k.vkCode in REMAP and not k.flags & 0x10:          # 0x10 = iniettato (anche dal tablet): si lascia
                up = wparam in (0x101, 0x105)                     # WM_KEYUP / WM_SYSKEYUP
                if up and k.vkCode in state["on"]:
                    state["on"].discard(k.vkCode)
                    send(REMAP[k.vkCode], True)
                    return 1
                if not up and (k.vkCode in state["on"] or (not REMAP_ON["done"] and not INJECTING["on"] and
                        _u32.GetAsyncKeyState(0xA2) & 0x8000 and in_game() and REMAP_ON["on"])):
                    state["on"].add(k.vkCode)
                    send(REMAP[k.vkCode], False)                  # anche le ripetizioni del tasto tenuto
                    return 1
        return _u32.CallNextHookEx(None, code, wparam, lparam)

    cb = _LLPROC(proc)
    hook["h"] = _u32.SetWindowsHookExW(13, cb, _k32.GetModuleHandleW(None), 0)   # WH_KEYBOARD_LL
    if not hook["h"]:
        print("Ctrl+WASD -> frecce non disponibile (hook rifiutato)")
        return
    msg = ctypes.create_string_buffer(64)
    while ctypes.windll.user32.GetMessageW(msg, None, 0, 0) > 0:   # il hook vive con la coda messaggi del thread
        pass


REMAP_ON = {"on": True, "done": False}   # done: codice completato in questa pressione di Ctrl -> WASD normali


def scan_key(name, up):
    code, ext = SCAN[name]
    flags = KEYEVENTF_SCANCODE | (KEYEVENTF_KEYUP if up else 0) | (KEYEVENTF_EXTENDEDKEY if ext else 0)
    inp = _INPUT(type=1, u=_INPUTUNION(ki=_KEYBDINPUT(0, code, flags, 0, 0)))
    if ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT)) != 1:
        raise OSError("SendInput rifiutato (gioco avviato come amministratore?)")


# --- touchpad e tastiera (scheda "Touchpad") ---
MOUSE_BTN = {"ld": [0x2], "lu": [0x4], "rd": [0x8], "ru": [0x10], "md": [0x20], "mu": [0x40],
             "lc": [0x2, 0x4], "rc": [0x8, 0x10], "mc": [0x20, 0x40]}
KEYEVENTF_UNICODE = 0x4


def _send_inputs(items):
    if not items:
        return
    arr = (_INPUT * len(items))(*items)
    with INPUT_LOCK:
        if ctypes.windll.user32.SendInput(len(items), arr, ctypes.sizeof(_INPUT)) != len(items):
            raise OSError("SendInput rifiutato (finestra in primo piano avviata come amministratore?)")


def _mouse(flags, dx=0, dy=0, data=0):
    return _INPUT(type=0, u=_INPUTUNION(mi=_MOUSEINPUT(dx, dy, data & 0xffffffff, flags, 0, 0)))


def mouse_input(dx=0, dy=0, wheel=0, hwheel=0, buttons=()):
    """Movimento relativo (con l'accelerazione di Windows), rotella verticale/orizzontale, poi i pulsanti."""
    items = []
    if dx or dy:
        items.append(_mouse(0x1, dx, dy))                 # MOUSEEVENTF_MOVE
    if wheel:
        items.append(_mouse(0x800, data=wheel))           # MOUSEEVENTF_WHEEL (120 = uno scatto)
    if hwheel:
        items.append(_mouse(0x1000, data=hwheel))         # MOUSEEVENTF_HWHEEL
    for b in buttons:
        items += [_mouse(f) for f in MOUSE_BTN[b]]
    _send_inputs(items)


def _vk_input(vk, up):
    flags = (KEYEVENTF_KEYUP if up else 0) | (KEYEVENTF_EXTENDEDKEY if vk in EXTENDED else 0)
    return _INPUT(type=1, u=_INPUTUNION(ki=_KEYBDINPUT(vk, 0, flags, 0, 0)))


def type_text(text, backspaces=0):
    """Cancella `backspaces` caratteri e scrive `text` come caratteri Unicode (qualsiasi layout di tastiera)."""
    items = []
    for _ in range(backspaces):
        items += [_vk_input(0x08, False), _vk_input(0x08, True)]
    data = text.encode("utf-16-le")
    for i in range(0, len(data), 2):
        unit = int.from_bytes(data[i:i + 2], "little")
        for up in (False, True):
            items.append(_INPUT(type=1, u=_INPUTUNION(ki=_KEYBDINPUT(
                0, unit, KEYEVENTF_UNICODE | (KEYEVENTF_KEYUP if up else 0), 0, 0))))
    _send_inputs(items)


def press_combo(names):
    """Combinazione di tasti VK (es. ["CTRL", "A"]): giu' in ordine, su al contrario."""
    vks = [VK[n] for n in names]
    _send_inputs([_vk_input(v, False) for v in vks] + [_vk_input(v, True) for v in reversed(vks)])


def foreground_title():
    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    buf = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(hwnd, buf, 256)
    return buf.value


class NotInGame(Exception):
    pass


# SICUREZZA/GIOCO: gli stratagemmi si digitano SOLO se Helldivers 2 e' la finestra in primo piano
# (altrimenti NotInGame -> 409): un tocco per sbaglio non scrive frecce in un'altra app.
def send_stratagem(code):
    title = foreground_title()
    if HD2["window"].upper() not in title.upper():
        raise NotInGame(title)
    menu = HD2["menu"]
    dirs = HD2["dirs"][load_settings()["input"]]
    INJECTING["on"] = True
    scan_key(menu, False)
    if len(code) >= 3:     # il menu resta aperto abbastanza a lungo
        threading.Thread(target=_peek_menu, args=(0.18,), daemon=True).start()
    try:
        time.sleep(HD2["open_ms"] / 1000.0)
        for c in code:
            k = dirs[c]
            scan_key(k, False)
            time.sleep(HD2["hold_ms"] / 1000.0)
            scan_key(k, True)
            time.sleep(HD2["gap_ms"] / 1000.0)
    finally:
        scan_key(menu, True)
        INJECTING["on"] = False


CD_READY = {}     # id -> (istante in cui torna disponibile, durata totale)
PENDING = {"id": None, "until": 0.0}   # stratagemma inserito ma non ancora lanciato
THROW_WAIT = 30   # secondi entro cui va lanciato; poi si lascia perdere
CD_LOCK = threading.Lock()


EAGLE_DEFAULT = {"eagle_short": 6, "eagle_rearm": 120}


def learned():
    return _json_load(COOLDOWN_FILE)


def known_cd(bid, L=None):
    """La durata e' stata misurata nel gioco (non solo la tabella)? Per gli Eagle servono breve e riarmo."""
    L = learned() if L is None else L
    if bid.startswith("hd2_e_"):
        return "eagle_short" in L and "eagle_rearm" in L
    return bid[4:] in L


def known_arrival(bid, L=None):
    L = learned() if L is None else L
    return isinstance(L.get("arr_" + bid[4:]), (int, float))


def all_known():
    """Tutte le fasi degli stratagemmi in uso sono note: non serve piu' leggere lo schermo."""
    L = learned()
    ids = [i for i in load_loadout() + ["hd2_resupply"] if i in BY_ID]
    return all(known_cd(i, L) and known_arrival(i, L) and (not i.startswith("hd2_e_") or i in USES) for i in ids)


def cooldown_of(bid):
    """Secondi di ricarica di uno stratagemma (file di correzioni > tabella > default del gruppo)."""
    sid = bid[4:]
    if bid.startswith("hd2_e_"):
        L = learned()
        eagles = [e for e in USES if e.startswith("hd2_e_")]
        kind = "eagle_rearm" if eagles and all(USES[e] == 0 for e in eagles) else "eagle_short"
        return int(L.get(kind, EAGLE_DEFAULT[kind]))
    try:
        with open(COOLDOWN_FILE, encoding="utf-8") as f:
            over = json.load(f)
        if isinstance(over, dict) and isinstance(over.get(sid), (int, float)):
            return max(0, int(over[sid]))
    except (OSError, ValueError):
        pass
    return COOLDOWNS.get(sid, COOLDOWN_DEFAULT.get(BY_ID[bid].get("col"), 0))


def cd_state():
    """Per il tablet: {"cd": {id: [secondi rimasti, durata]}, "p": id in attesa di lancio o null}."""
    now = time.time()
    with CD_LOCK:
        cd = {k: [round(end - now), tot] for k, (end, tot) in CD_READY.items() if end - now > 0.5}
        p = PENDING["id"] if PENDING["until"] > now else None
        a = ARRIVING["id"]
        if REARM["end"] and now > REARM["end"]:
            REARM["end"] = 0.0
            tot = _json_load(USES_FILE)
            for e in list(USES):
                if e.startswith("hd2_e_") and tot.get(e[4:]):
                    USES[e] = tot[e[4:]]
            EMPTY.difference_update([e for e in EMPTY if e.startswith("hd2_e_")])
        na = sorted(EMPTY)
        tot = _json_load(USES_FILE)
        u = {k: [v, max(v, tot.get(k[4:], v))] for k, v in USES.items()}
    return {"cd": cd, "p": p, "a": a, "na": na, "u": u}


def _throw_watch():
    """In gioco la ricarica parte quando si LANCIA la sfera (rilascio del tasto sinistro), non quando si
    inserisce il codice. Si osserva solo lo stato del pulsante (GetAsyncKeyState), senza toccare il gioco."""
    get = ctypes.windll.user32.GetAsyncKeyState
    down = bool(get(0x01) & 0x8000)
    while True:
        time.sleep(0.02)
        with CD_LOCK:
            bid, until = PENDING["id"], PENDING["until"]
            if bid is None or time.time() > until:
                PENDING["id"] = None
                return
        now_down = bool(get(0x01) & 0x8000)
        if down and not now_down and HD2["window"].upper() in foreground_title().upper():
            with CD_LOCK:
                if PENDING["id"] == bid:
                    PENDING["id"] = None
                    ARRIVING["id"] = bid
            threading.Thread(target=_arrival_watch, args=(bid, time.time()), daemon=True).start()
            return
        down = now_down


ARRIVING = {"id": None}
ARRIVAL_RE = re.compile(r"ATTIV|ARRIV")


def _start_cooldown(bid, start):
    cd = cooldown_of(bid)
    with CD_LOCK:
        if USES.get(bid):
            USES[bid] -= 1
            if USES[bid] == 0 and bid.startswith("hd2_e_"):
                EMPTY.add(bid)
        if ARRIVING["id"] == bid:
            ARRIVING["id"] = None
        THROWN[bid] = start                     # da qui si misura la durata vera (impara hd2_cooldowns.json)
        if bid in CD_READY and CD_READY[bid][0] > time.time() + 1:   # gia' letto dal menu del gioco: vale quello
            return
        if bid.startswith("hd2_e_"):
            cd = cooldown_of(bid)                  # dopo aver tolto l'uso: breve o riarmo
            for e in set(load_loadout()) | {bid}:
                if e.startswith("hd2_e_"):
                    CD_READY[e] = (start + cd, cd)
            if cd > 30:
                REARM["end"] = start + cd
            return
        if cd:
            CD_READY[bid] = (start + cd, cd)


def _arrival_watch(bid, thrown):
    """Dopo il lancio il gioco mostra lo stratagemma in alto a sinistra con "Attivazione" finche' non arriva;
    la ricarica vera parte solo dopo. Si guarda lo schermo (nessun input) qualche volta al secondo."""
    L = learned()
    if known_arrival(bid, L) and known_cd(bid, L):      # tutto gia' misurato: si prevede, senza leggere
        end = thrown + L["arr_" + bid[4:]]
        while time.time() < end:
            with CD_LOCK:
                if ARRIVING["id"] != bid:
                    return
            time.sleep(0.2)
        _start_cooldown(bid, end)
        return
    seen, last_seen, arrivo = False, thrown, False
    while time.time() - thrown < 40:
        with CD_LOCK:
            if ARRIVING["id"] != bid:             # un altro lancio l'ha sostituito
                return
        t = time.time()
        try:
            img = grab_screen(0, 0, *menu_area())
            lines = [l[0].upper() for l in ocr_lines(*_ocr_prep(*img))]
        except OSError:
            lines = []
        if any(ARRIVAL_RE.search(l) for l in lines):
            seen, last_seen = True, t
            arrivo = arrivo or any("ARR" in l or "RIVO" in l for l in lines)
        elif seen and t - last_seen > (1.5 if arrivo else 6.0):   # sparito: e' arrivato, parte la ricarica
            # (tra "Attivazione" e "T. arrivo" il testo puo' sparire per qualche secondo: si aspetta di piu')
            start = last_seen + 0.3
            arr = round(start - thrown, 1)
            if 0.5 < arr < 30:                    # durata dell'arrivo: la prossima volta non serve leggere
                L = learned()
                L["arr_" + bid[4:]] = arr
                _json_save(COOLDOWN_FILE, L)
            _start_cooldown(bid, start)
            if not known_cd(bid):
                _read_hud_cooldown(bid)
            return
        elif not seen and t - thrown > 6:       # non letto (es. nebbia): come prima, dal lancio
            _start_cooldown(bid, thrown)
            return
        time.sleep(max(0.0, 0.35 - (time.time() - t)))
    _start_cooldown(bid, time.time())


def _read_hud_cooldown(bid, secs=12.0):
    """Dopo l'arrivo il gioco mostra in alto a sinistra "T. ricarica -MM:SS" (breve tra un uso e l'altro
    degli Eagle, lunga - il riarmo - dopo l'ultimo uso; a volte compare qualche secondo dopo).
    Si legge finche' non si trova il tempo di questo stratagemma (piu' una lettura di conferma)."""
    start, found = time.time(), None
    while time.time() - start < secs:
        t = time.time()
        try:
            apply_menu(grab_screen(0, 0, *menu_area()), t, wait=True)
        except OSError:
            pass
        if LAST_READ.get(bid, 0) >= start:
            if found is not None and t - found > 1.0:
                return
            found = found or t
        time.sleep(max(0.0, 0.5 - (time.time() - t)))


def arm_throw(bid):
    """Uno stratagemma appena inserito: se ne aspetta il lancio (un nuovo codice sostituisce il precedente)."""
    with CD_LOCK:
        start = PENDING["id"] is None
        PENDING["id"], PENDING["until"] = bid, time.time() + THROW_WAIT
    if start:
        threading.Thread(target=_throw_watch, daemon=True).start()


# --- sincronizzazione equipaggiamento: si legge il menu stratagemmi dallo schermo (mai la memoria del gioco) ---
# LETTURA DELLO SCHERMO (HD2): solo cattura GDI di una zona dello schermo + OCR di Windows.
# Mai lettura della memoria del gioco (l'anti-cheat la considererebbe un trucco).
# Prestazioni: si cattura solo la zona del menu; quando tutte le durate sono note (all_known) non si
# legge piu' lo schermo e i tempi vengono previsti.
def grab_screen(x, y, w, h):
    """Cattura un'area dello schermo: (w, h, byte BGRA dall'alto in basso)."""
    gdi, u32 = ctypes.windll.gdi32, ctypes.windll.user32
    for fn, res in (("GetDC", _VP), ("CreateCompatibleDC", _VP), ("CreateCompatibleBitmap", _VP), ("SelectObject", _VP)):
        getattr(gdi if fn != "GetDC" else u32, fn).restype = res
    gdi.CreateCompatibleDC.argtypes = [_VP]
    gdi.CreateCompatibleBitmap.argtypes = [_VP, ctypes.c_int, ctypes.c_int]
    gdi.SelectObject.argtypes = [_VP, _VP]
    gdi.BitBlt.argtypes = [_VP, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, _VP, ctypes.c_int, ctypes.c_int, ctypes.c_ulong]
    gdi.DeleteDC.argtypes = [_VP]
    u32.ReleaseDC.argtypes = [_VP, _VP]
    sdc = u32.GetDC(None)
    mdc = gdi.CreateCompatibleDC(sdc)
    bmp = gdi.CreateCompatibleBitmap(sdc, w, h)
    try:
        old = gdi.SelectObject(mdc, bmp)
        gdi.BitBlt(mdc, 0, 0, w, h, sdc, x, y, 0x00CC0020 | 0x40000000)   # SRCCOPY | CAPTUREBLT
        gdi.SelectObject(mdc, old)
        bih = _BIH(biSize=40, biWidth=w, biHeight=-h, biPlanes=1, biBitCount=32)
        buf = (ctypes.c_ubyte * (w * h * 4))()
        _gdi.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bih), 0)
        return w, h, bytes(buf)
    finally:
        _gdi.DeleteObject(bmp)
        gdi.DeleteDC(mdc)
        u32.ReleaseDC(None, sdc)


def _components(mask, w, h):
    """Zone di pixel accesi collegate (4-vicini): lista di (x0, y0, x1, y1, n_pixel, pixel)."""
    seen = bytearray(w * h)
    out = []
    start = -1
    while True:
        start = mask.find(1, start + 1)           # salta direttamente al prossimo pixel acceso
        if start < 0:
            break
        if seen[start]:
            continue
        stack, pix = [start], []
        seen[start] = 1
        while stack:
            i = stack.pop()
            pix.append(i)
            x, y = i % w, i // w
            for j in ((i - 1) if x else -1, (i + 1) if x < w - 1 else -1, i - w, i + w):
                if 0 <= j < w * h and mask[j] and not seen[j]:
                    seen[j] = 1
                    stack.append(j)
            if len(pix) > 4000:      # troppo grande: non e' una freccia
                break
        xs, ys = [i % w for i in pix], [i // w for i in pix]
        out.append((min(xs), min(ys), max(xs), max(ys), len(pix), pix))
    return out


def _arrow_dir(c, w):
    """Direzione di una freccia: la punta e' l'estremita' piu' stretta, sull'asse piu' asimmetrico.
    None se non ha una punta (es. i riquadri bianchi con il numero di usi accanto alle icone)."""
    x0, y0, x1, y1, _n, pix = c
    bw, bh = x1 - x0 + 1, y1 - y0 + 1
    rows, cols = [0] * bh, [0] * bw
    for i in pix:
        rows[i // w - y0] += 1
        cols[i % w - x0] += 1
    k = max(1, bh // 5)
    top, bot = sum(rows[:k]) / (k * bw), sum(rows[-k:]) / (k * bw)
    k = max(1, bw // 5)
    lef, rig = sum(cols[:k]) / (k * bh), sum(cols[-k:]) / (k * bh)
    if min(top, bot, lef, rig) > 0.45:
        return None
    if abs(top - bot) >= abs(lef - rig):
        return "U" if top < bot else "D"
    return "L" if lef < rig else "R"


def parse_stratagem_menu(w, h, bgra):
    """Righe di frecce del menu stratagemmi (dall'alto in basso) come codici 'UDLR'."""
    return [c for _y, c in parse_arrow_rows(w, h, bgra)]


def parse_arrow_rows(w, h, bgra):
    """[(y del centro in pixel, codice 'UDLR')] per ogni riga di frecce, dall'alto in basso."""
    step = 1 if w * h <= 1400 * 1100 else 2     # a 1080p le frecce sono di ~12 px: serve la risoluzione piena
    if step == 2:
        bgra = b"".join(bgra[y * w * 4:(y + 1) * w * 4] for y in range(0, h - h % 2, 2))
        bgra = b"".join(bgra[i:i + 4] for i in range(0, len(bgra), 8))
    sw, sh = w // step, h // step
    n = sw * sh

    def over(ch, t):                             # 1 dove il canale supera la soglia (blocchi di byte, veloce)
        tab = bytes(1 if v > t else 0 for v in range(256))
        return int.from_bytes(bgra[ch:n * 4:4].translate(tab), "big")
    mask = bytearray((over(0, 105) & over(1, 125) & over(2, 125)).to_bytes(n, "big"))   # chiaro (bianco/grigio)
    scr = h / 0.75                          # altezza dello schermo (la cattura ne prende il 75%)
    lo, hi = scr * 0.0095 / step, scr * 0.022 / step   # frecce ~13 px a 1080p; le lettere sono piu' strette
    arrows = []
    for c in _components(mask, sw, sh):
        x0, y0, x1, y1, n, _p = c
        bw, bh = x1 - x0 + 1, y1 - y0 + 1
        if lo <= bw <= hi and lo <= bh <= hi and 0.75 <= bw / bh <= 1.33 and 0.35 <= n / (bw * bh) <= 0.75:
            d = _arrow_dir(c, sw)
            if d:
                arrows.append(((y0 + y1) / 2, (x0 + x1) / 2, bw, d))
    arrows.sort()
    rows, cur = [], []
    for a in arrows:                       # stessa riga = centro verticale entro 6 px
        if cur and abs(a[0] - cur[-1][0]) > 6 / step:
            rows.append(cur)
            cur = []
        cur.append(a)
    if cur:
        rows.append(cur)
    codes = []
    for r in rows:
        r.sort(key=lambda a: a[1])
        size = sorted(a[2] for a in r)[len(r) // 2]
        seq = [r[0]]
        for a in r[1:]:                   # frecce consecutive: distanza regolare (non testo sparso)
            if a[1] - seq[-1][1] <= size * 2.6:
                seq.append(a)
            elif len(seq) < 3:
                seq = [a]
        if len(seq) >= 3:
            codes.append((seq[0][0] * step, "".join(a[3] for a in seq)))
    return codes


NAMES_FILE = os.path.join(DATA_DIR, "hd2_names.json")    # nome letto in gioco -> id (imparato dalle frecce)
TIME_RE = re.compile(r"(\d{1,2})\s*[:.]\s*(\d{2})")
EMPTY = set()      # stratagemmi "Non disponibile" (Eagle con gli usi finiti, fino al riarmo)
LAST_READ = {}     # id -> istante dell'ultima ricarica letta dallo schermo
THROWN = {}        # id -> istante del lancio rilevato (per imparare la durata vera della ricarica)
MENU_LOCK = threading.Lock()


def _norm(t):
    return re.sub(r"[^A-Z0-9]", "", t.upper())


def _json_load(path):
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _json_save(path, d):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1, sort_keys=True)
    os.replace(tmp, path)


_THR_TABS = {}


def _ocr_prep(w, h, bgra, scale=2, thr=85, margin=30):
    """Per l'OCR: testo chiaro (anche i nomi grigi in ricarica) -> nero su bianco, ingrandito 2x.
    La soglia si adatta riga per riga: il testo deve essere piu' chiaro dello sfondo della sua riga
    (con nebbia o neve dietro il menu una soglia fissa annerisce tutto). Solo operazioni su blocchi di byte."""
    w2 = int(w * 0.6)                                  # il pannello sta a sinistra
    x0 = int(w2 * 0.2)                                 # lo sfondo si misura a destra delle icone
    out_rows = []
    for y in range(h):
        g = bgra[y * w * 4 + 1:(y * w + w2) * 4:4]     # canale verde (luminosita')
        bg = sorted(g[x0:])[(w2 - x0) // 2]            # mediana = sfondo della riga
        t = max(thr, min(230, bg + margin))
        tab = _THR_TABS.get(t)
        if tab is None:
            tab = _THR_TABS[t] = bytes(0 if v > t else 255 for v in range(256))   # testo nero, resto bianco
        m = g.translate(tab)
        if scale == 2:
            wide = bytearray(2 * w2)
            wide[0::2], wide[1::2] = m, m
            m = bytes(wide)
            out_rows.append(m)
        out_rows.append(m)
    m = b"".join(out_rows)
    out = bytearray(len(m) * 4)
    out[0::4], out[1::4], out[2::4] = m, m, m
    out[3::4] = b"\xff" * len(m)
    return w2 * scale, h * (2 if scale == 2 else 1), bytes(out)


def menu_rows(img):
    """Righe del menu stratagemmi: [{"name", "y", "code" (se disponibile), "left" (secondi di ricarica)}]."""
    lines = [(t, x / 2, y / 2, lw / 2, lh / 2) for t, x, y, lw, lh in ocr_lines(*_ocr_prep(*img))]
    arrows = parse_arrow_rows(*img)
    caps = [l for l in lines if sum(ch.isupper() for ch in l[0]) >= max(3, 0.6 * sum(ch.isalpha() for ch in l[0]))]
    if not caps:
        return []
    xs = sorted(round(l[1]) for l in caps)
    col = xs[len(xs) // 2]                       # colonna dei nomi
    names = [l for l in caps if abs(l[1] - col) <= 12 and not TIME_RE.search(l[0])]
    rows = []
    for i, (text, _x, y, _w, lh) in enumerate(names):
        nxt = names[i + 1][2] if i + 1 < len(names) else y + 3 * max(lh, 10)
        row = {"name": text, "y": y}
        mine = [t for t in lines if y < t[2] < min(nxt, y + 2.4 * max(lh, 8))]   # subito sotto il proprio nome
        up = " ".join(t[0].upper() for t in mine)
        if "DISPON" in up:                 # "Non disponibile": Eagle senza piu' usi fino al riarmo
            row["na"] = True
        if "ARR" in up or "RIVO" in up or "ATTIV" in up or "ICA" not in up:
            row["arr"] = "ARR" in up or "RIVO" in up or "ATTIV" in up   # "T. arrivo" non e' una ricarica
        else:
            for t in mine:
                m = TIME_RE.search(t[0])
                if m:
                    row["left"] = int(m.group(1)) * 60 + int(m.group(2))
        for ay, code in arrows:
            if y < ay < min(nxt, y + 3.4 * max(lh, 8)):
                row["code"] = code
        if "code" in row:                 # frecce visibili = pronto: un tempo li' sarebbe di un'altra riga
            row.pop("left", None)
        rows.append(row)
    return rows


def apply_menu(img, when, wait=False):
    """Legge il menu catturato all'istante `when`: impara i nomi, corregge le ricariche, impara le durate.
    Restituisce gli id riconosciuti, riga per riga (None = riga non riconosciuta)."""
    found = []
    if not MENU_LOCK.acquire(blocking=wait):
        return found
    try:
        rows = menu_rows(img)
        names, learned, totals = _json_load(NAMES_FILE), _json_load(COOLDOWN_FILE), _json_load(USES_FILE)
        changed_names = changed_cd = changed_tot = False
        for r in rows:
            key = _norm(r["name"])
            if len(key) < 3:
                continue
            bid = CODE_TO_ID.get(r.get("code", ""))
            if bid and len(key) >= 5 and names.get(key) != bid:
                names[key], changed_names = bid, True
            if not bid:
                bid = names.get(key)
            if not bid and names:                       # l'OCR sbaglia qualche lettera: il nome piu' simile
                near = [n for n in names if abs(len(n) - len(key)) <= max(2, len(key) // 7)]   # niente parole in meno
                best = max(near, key=lambda n: difflib.SequenceMatcher(None, n, key).ratio()) if near else ""
                if best and difflib.SequenceMatcher(None, best, key).ratio() >= 0.75:
                    bid = names[best]
            if bid in BY_ID:
                MENU_IDS.add(bid)
            if "code" in r or "left" in r:          # (Rinforzo "Pronti..." non conta)
                found.append(bid if bid in BY_ID else None)
            if not bid or bid not in BY_ID:
                continue
            u = 0 if r.get("na") else read_uses(img, r["y"])
            with CD_LOCK:
                if u is not None:
                    USES[bid] = u
                    if u > totals.get(bid[4:], 0):
                        totals[bid[4:]], changed_tot = u, True
                if r.get("na"):
                    EMPTY.add(bid)
                elif "code" in r:
                    EMPTY.discard(bid)
                if "left" in r and bid.startswith("hd2_e_") and r["left"] > 30:
                    EMPTY.difference_update([e for e in EMPTY if e.startswith("hd2_e_")])   # riarmo: tornano tutti
                    REARM["end"] = when + r["left"]
                if "left" in r:
                    left = r["left"]
                    t0 = THROWN.pop(bid, None)
                    total = cooldown_of(bid)
                    if t0 and 0 < when - t0 < 1200 and bid.startswith("hd2_e_"):   # Eagle: breve o riarmo
                        real = round(left + (when - t0))
                        kind = "eagle_short" if real <= 30 else "eagle_rearm"
                        if 2 <= real <= 600 and abs(real - learned.get(kind, -99)) >= 2:
                            learned[kind], changed_cd = real, True
                    if t0 and 0 < when - t0 < 1200 and not bid.startswith("hd2_e_"):
                        real = round(left + (when - t0))
                        if 5 <= real <= 1200 and abs(real - total) >= 2:
                            learned[bid[4:]], changed_cd, total = real, True, real
                    CD_READY[bid] = (when + left, left if bid.startswith("hd2_e_") else max(total, left))
                    LAST_READ[bid] = when
                    if bid.startswith("hd2_e_"):       # gli Eagle condividono la ricarica (breve e riarmo)
                        for e in set(load_loadout()) | {k for k in CD_READY if k.startswith("hd2_e_")} | {ARRIVING["id"] or ""}:
                            if e.startswith("hd2_e_"):
                                CD_READY[e], LAST_READ[e] = (when + left, left), when
                    if PENDING["id"] == bid:
                        PENDING["id"] = None
                    if ARRIVING["id"] == bid and not r.get("arr"):
                        ARRIVING["id"] = None
                elif "code" in r and bid in CD_READY and CD_READY[bid][0] - when < 15:
                    del CD_READY[bid]                  # in gioco e' gia' pronto
        if changed_names:
            _json_save(NAMES_FILE, names)
        if changed_cd:
            _json_save(COOLDOWN_FILE, learned)
        if changed_tot:
            _json_save(USES_FILE, totals)
    except OSError as e:
        sys.stderr.write("[%s] lettura menu: %s\n" % (time.strftime("%H:%M:%S"), e))
    finally:
        MENU_LOCK.release()
    return found


def menu_area():
    sw, sh = ctypes.windll.user32.GetSystemMetrics(0), ctypes.windll.user32.GetSystemMetrics(1)
    return int(sw * 0.42), int(sh * 0.75)


def _peek_menu(delay):
    """Durante l'inserimento di un codice il menu e' aperto: lo si fotografa una volta, senza rallentare i tasti."""
    if all_known():
        return
    time.sleep(delay)
    when = time.time()
    try:
        img = grab_screen(0, 0, *menu_area())
    except OSError:
        return
    apply_menu(img, when)


# --- usi rimasti: il numero nel riquadro chiaro sull'icona (es. Eagle 500 kg "2") ---
# Cifre prese dagli screenshot del gioco (1080p, 1-5: gli Eagle potenziati arrivano a 5).
DIGIT_TEMPLATES = {      # piu' forme per cifra (il gioco le disegna con piccole differenze)
    "1": [["####..", "..##..", "..##..", "..##..", "..##..", "..##..", "..##..", "..##..", "..##..", "######", "######"]],
    "2": [[".####..", "######.", ".....##", ".....##", ".....##", "...###.", ".####..", "###....", "#......", "#......", "#######"]],
    "3": [[".####..", "######.", ".....##", ".....##", ".....##", "...###.", "...####", ".....##", ".....##", "#....##", "######."],
          ["..###..", "######.", "#....##", ".....##", ".....##", "...###.", "...####", ".....##", ".....##", "#....##", "#######", ".####.."]],
    "4": [["...#.....", "..##.....", "..##.....", ".##......", ".##...#..", ".#....#..", "##....#..", "#########", "......#..", "......#.."]],
    "5": [["######", "######", "##....", "##....", "##....", "######", ".....##", ".....##", ".....##", "#....##", "######"]],
}


def _digit_feat(grid):
    ys = [y for y, r in enumerate(grid) if any(r)]
    xs = [x for x in range(len(grid[0])) if any(r[x] for r in grid)] if grid else []
    if not ys or not xs:
        return None
    y0, y1, x0, x1 = ys[0], ys[-1] + 1, xs[0], xs[-1] + 1
    out = []
    for j in range(6):
        for i in range(4):
            ya, yb = y0 + (y1 - y0) * j // 6, y0 + (y1 - y0) * (j + 1) // 6
            xa, xb = x0 + (x1 - x0) * i // 4, x0 + (x1 - x0) * (i + 1) // 4
            yb, xb = max(yb, ya + 1), max(xb, xa + 1)
            cells = [grid[y][x] for y in range(ya, yb) for x in range(xa, xb)]
            out.append(sum(cells) / len(cells))
    out.append(2 * min(1.5, (x1 - x0) / (y1 - y0)))     # proporzioni
    return out


DIGIT_FEATS = [(d, _digit_feat([[1 if c == "#" else 0 for c in row] for row in t])) for d, ts in DIGIT_TEMPLATES.items() for t in ts]


def read_uses(img, row_y):
    """Numero di usi nel riquadro dell'icona della riga (nome a quota row_y); None se non c'e' o incerto."""
    w, h, b = img
    k = (h / 0.75) / 1080.0
    lit = lambda x, y: min(b[(y * w + x) * 4], b[(y * w + x) * 4 + 1], b[(y * w + x) * 4 + 2]) > 170
    box = None
    for y in range(int(row_y + 12 * k), min(h - 1, int(row_y + 36 * k))):
        run = 0
        for x in range(int(82 * k), int(110 * k)):
            run = run + 1 if lit(x, y) else 0
            if run >= int(15 * k):
                box = (x - run + 1, y)
                break
        if box:
            break
    if not box or not (int(84 * k) <= box[0] <= int(90 * k)):
        return None
    bx, by = box
    side = int(18 * k)
    if by + side >= h or bx + side >= w:
        return None
    grid = [[1 if max(b[(yy * w + xx) * 4:(yy * w + xx) * 4 + 3]) < 120 else 0 for xx in range(bx + 2, bx + side - 2)]
            for yy in range(by + 2, by + side - 2)]
    f = _digit_feat(grid)
    if f is None:
        return None
    dist, d = min((sum(abs(a - c) for a, c in zip(f, t)), d) for d, t in DIGIT_FEATS)
    return int(d) if dist < 4.5 else None


USES_FILE = os.path.join(DATA_DIR, "hd2_uses.json")   # usi totali (il massimo visto) per stratagemma
USES = {}           # id -> usi rimasti (letti dal menu, poi scalati a ogni lancio dal tablet)
REARM = {"end": 0.0}   # fine del riarmo Eagle: dopo, tutti gli Eagle tornano pieni


MENU_IDS = set()   # stratagemmi visti nel menu del gioco all'ultima lettura (anche gli obiettivi di missione)


def manual_match(seq):
    """Quale stratagemma ha completato la sequenza premuta a mano? Come il gioco: solo tra quelli disponibili
    (equipaggiamento, sempre disponibili, visti nel menu), esclusi quelli in ricarica o esauriti."""
    now = time.time()
    pool = [i for i in load_loadout() + ["hd2_" + a for a in ALWAYS] + sorted(MENU_IDS) if i in BY_ID]
    with CD_LOCK:
        avail = [i for i in pool if i not in EMPTY and not (i in CD_READY and CD_READY[i][0] > now + 1)]
    hit = [i for i in avail if BY_ID[i]["strat"] == seq]
    if hit:
        return hit
    if any(BY_ID[i]["strat"].startswith(seq) for i in avail):
        return []                            # puo' ancora diventare uno di quelli disponibili
    bid = CODE_TO_ID.get(seq)                # ultima risorsa: elenco completo, se nessun codice piu' lungo inizia cosi'
    if bid and not any(c != seq and c.startswith(seq) for c in CODE_TO_ID):
        return [bid]
    return []


INJECTING = {"on": False}   # TabDeck sta inserendo un codice (non e' una chiamata a mano)
MANUAL_KEYS = {"arrows": {0x26: "U", 0x28: "D", 0x25: "L", 0x27: "R"},
               "wasd": {0x57: "U", 0x53: "D", 0x41: "L", 0x44: "R"}}


def _ctrl_watch():
    """Quando in gioco si tiene premuto Ctrl (anche dalla tastiera) il menu stratagemmi e' aperto.
    1) Si riconoscono gli stratagemmi chiamati A MANO (tasti direzione premuti con Ctrl tenuto) -> stesso
       LANCIA / IN ARRIVO / ricarica delle chiamate dal tablet.
    2) Si legge il menu per correggere le ricariche, ma solo finche' qualcosa non e' ancora noto.
    Si osserva solo lo stato dei tasti (GetAsyncKeyState), senza inviare nulla al gioco."""
    get = ctypes.windll.user32.GetAsyncKeyState
    since, last = 0.0, 0.0
    seq, held, done, read, keys = "", set(), False, False, {}
    while True:
        ctrl = get(0xA2) & 0x8000                 # VK_LCONTROL
        time.sleep(0.01 if ctrl else 0.05)
        if not ctrl:
            since, seq, held, done, read = 0.0, "", set(), False, False
            REMAP_ON["done"] = False
            continue
        now = time.time()
        if not since:
            since = now
            keys = MANUAL_KEYS[load_settings()["input"]]
            if HD2["window"].upper() not in foreground_title().upper():
                since = now + 3600                # non in gioco: questa pressione si ignora
            continue
        if since > now:
            continue
        if not INJECTING["on"] and not done:      # tasti direzione premuti a mano
            for vk, d in keys.items():
                down = get(vk) & 0x8000
                if down and vk not in held:
                    held.add(vk)
                    seq += d
                    cands = manual_match(seq)
                    if cands:
                        done = True
                        REMAP_ON["done"] = True       # stratagemma attivato: WASD tornano a muovere
                        if cooldown_of(cands[0]):
                            arm_throw(cands[0])
                elif not down:
                    held.discard(vk)
        if now - since >= 0.2 and now - last >= 2 and not read and not all_known():
            last = now
            try:
                img = grab_screen(0, 0, *menu_area())
            except OSError:
                continue
            threading.Thread(target=apply_menu, args=(img, now), daemon=True).start()
            read = True                           # una lettura per pressione


CODE_TO_ID = {}
for _grp, _col, _items in STRATAGEMS:
    for _sid, _name, _code in _items:
        CODE_TO_ID.setdefault(_code, "hd2_" + _sid)


def sync_loadout():
    """Apre il menu stratagemmi in gioco per un attimo, lo fotografa e ne ricava l'equipaggiamento."""
    title = foreground_title()
    if HD2["window"].upper() not in title.upper():
        raise NotInGame(title)
    w, h = menu_area()
    with INPUT_LOCK:
        scan_key(HD2["menu"], False)
        try:
            time.sleep(0.6)                   # il menu si apre con una dissolvenza
            img = grab_screen(0, 0, w, h)
        finally:
            scan_key(HD2["menu"], True)
    when = time.time()
    codes = parse_stratagem_menu(*img)
    rows = apply_menu(img, when, wait=True)       # anche le righe in ricarica (riconosciute dal nome)
    ids = [i for i in rows if i] or [CODE_TO_ID[c] for c in codes if c in CODE_TO_ID]
    picked = []
    for i in ids:
        if pinnable(i) and i not in picked:
            picked.append(i)
    unknown = sum(1 for i in rows if i is None)
    if picked and unknown and len(picked) < LOADOUT_MAX:   # righe non riconosciute: si tengono i precedenti
        for i in load_loadout():
            if i not in picked and len(picked) < LOADOUT_MAX:
                picked.append(i)
    picked = picked[:LOADOUT_MAX]
    if True:           # l'ultima lettura resta su disco (last_menu.png) per migliorare il riconoscimento
        os.makedirs(SYNC_DEBUG_DIR, exist_ok=True)
        w, h, bgra = img
        px = bytearray(bgra)
        px[0::4], px[2::4] = bgra[2::4], bgra[0::4]
        px[3::4] = b"\xff" * (w * h)
        name = os.path.join(SYNC_DEBUG_DIR, "last_menu.png" if picked else time.strftime("menu_%Y%m%d_%H%M%S.png"))
        with open(name, "wb") as f:
            f.write(_png(w, h, bytes(px)))
        with open(name[:-4] + ".txt", "w", encoding="utf-8") as f:
            f.write("codici letti: %r\nrighe: %r\nequipaggiamento: %r\n" % (codes, rows, picked))
    return picked, codes


def trigger(button):
    if "strat" in button:
        with INPUT_LOCK:
            send_stratagem(button["strat"])
        if cooldown_of(button["id"]):
            arm_throw(button["id"])
    elif "keys" in button:
        with INPUT_LOCK:
            send_keys(button["keys"])
    elif "run" in button:
        subprocess.Popen(button["run"], close_fds=True)


def load_loadout():
    try:
        with open(LOADOUT_FILE, encoding="utf-8") as f:
            ids = json.load(f)
    except (OSError, ValueError):
        return []
    if not isinstance(ids, list):
        return []
    out = []
    for i in ids:
        if isinstance(i, str) and pinnable(i) and i not in out:
            out.append(i)
    return out[:LOADOUT_MAX]


def pinnable(i):
    """Si puo' mettere nell'equipaggiamento: stratagemma esistente e non di missione."""
    return i.startswith("hd2_") and i in BY_ID and BY_ID[i].get("col") != "mis"


SETTINGS_LOCK = threading.Lock()


def load_settings():
    s = {k: v[0] for k, v in SETTINGS_CHOICES.items()}
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            saved = json.load(f)
    except (OSError, ValueError):
        return s
    if isinstance(saved, dict):
        for k, choices in SETTINGS_CHOICES.items():
            if saved.get(k) in choices:
                s[k] = saved[k]
    return s


def save_settings(s):
    with SETTINGS_LOCK:
        tmp = SETTINGS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(s, f)
        os.replace(tmp, SETTINGS_FILE)


def save_loadout(ids):
    tmp = LOADOUT_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(ids, f)
    os.replace(tmp, LOADOUT_FILE)


def load_token():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, encoding="utf-8") as f:
            tok = f.read().strip()
        if len(tok) >= 16:
            return tok
    tok = secrets.token_urlsafe(18)
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        f.write(tok + "\n")
    return tok


DEVICES = None   # devices.DeviceStore, creato in main() (None = nessun controllo dei dispositivi, es. nei test vecchi)
SERVER = None    # server HTTP in ascolto (per cambiare il token al volo)


def rotate_token():
    """"Nuovo link" dalla finestra sul PC: nuovo token, il vecchio link smette di funzionare per i nuovi
    dispositivi. Quelli approvati restano dentro grazie al loro ID."""
    tok = secrets.token_urlsafe(18)
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        f.write(tok + "\n")
    if SERVER is not None:
        SERVER.token = tok
    return tok


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))  # nessun pacchetto inviato (UDP)
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


# ---------------------------------------------------------------------------
# PAGINA WEB. Sta in web\ divisa in tre file (index.html, style.css, app.js) per poterla leggere e
# modificare comodamente. Qui vengono uniti in memoria (stile e script restano "in linea": il tablet
# scarica UNA sola risposta, niente richieste in piu') e riletti solo se un file cambia (mtime).
# I segnaposto __NOME__ vengono riempiti da render_page().
# ---------------------------------------------------------------------------
WEB_DIR = os.path.join(HERE, "web")
_PAGE_CACHE = {"key": None, "page": ""}
_PAGE_LOCK = threading.Lock()


def page_template():
    files = [os.path.join(WEB_DIR, n) for n in ("index.html", "style.css", "app.js")]
    key = tuple(os.path.getmtime(f) for f in files)
    with _PAGE_LOCK:
        if key != _PAGE_CACHE["key"]:
            parts = []
            for f in files:
                with open(f, encoding="utf-8") as fh:
                    parts.append(fh.read())
            _PAGE_CACHE["page"] = parts[0].replace("__CSS__", parts[1], 1).replace("__JS__", parts[2], 1)
            _PAGE_CACHE["key"] = key
        return _PAGE_CACHE["page"]


def svg(name):
    return '<svg viewBox="0 0 24 24"><path d="%s"/></svg>' % ICONS[name]


def arrows_html(code):
    return "".join('<i class="t t%s"></i>' % c.lower() for c in code)


def available_icons():
    try:
        return {f[:-4] for f in os.listdir(ICON_DIR) if f.endswith(".svg")}
    except OSError:
        return set()


ICON_IMG = ('<img src="/appicon/%s.png" alt="" onload="this.previousSibling.style.visibility=\'hidden\'" '
            'onerror="this.parentNode.removeChild(this)">')


def button_html(b, extra_cls="", attrs=""):
    src = button_icon_src(b) if b.get("mono") else None
    if b.get("mono") and src:   # icona vera dell'app; la sigla resta sotto finche' l'icona non e' caricata
        inner = '<span class="ic"><span class="mo">%s</span>%s</span>' % (html.escape(b["mono"]), ICON_IMG % icon_key(src))
    elif b.get("mono"):
        inner = '<span class="mo">%s</span>' % html.escape(b["mono"])
    else:
        inner = svg(b["icon"]) if b.get("icon") else ""
    inner += '<span class="l">%s</span>' % html.escape(b["label"])
    if b.get("hint"):
        inner += '<span class="h mono">%s</span>' % html.escape(b["hint"])
    return ('<button class="b %s%s" data-n="%s"%s>%s</button>'
            % (b.get("cat", "app"), extra_cls, html.escape(b["label"], True), attrs, inner))


def special_html(i, live=True):
    """Riquadri Volume e Microfono; live=False per le copie nell'editor (senza id duplicati)."""
    if i == "_vol":
        return ('<button class="b win"%s data-go="mix" data-n="Volume">%s<span class="l">Volume</span>'
                '<span class="h mono"><span%s>--</span>%% &rsaquo;</span></button>'
                % (' id="svol"' if live else "", svg("vol_up"), ' id="volval"' if live else ""))
    if i == "_yt":
        return ('<button class="b media"%s data-go="yt" data-yt="1" data-n="YouTube"><span class="mo">YT</span>'
                '<span class="l">YouTube</span><span class="h mono">musica e video</span></button>' % (' id="syt"' if live else ""))
    return ('<button class="b app"%s data-mic="1" data-n="Microfono"><span class="v1">%s</span><span class="v2">%s</span>'
            '<span class="l">Mic</span><span class="h mono">Windows</span></button>' % (' id="smic"' if live else "", svg("mic"), svg("mic_off")))


def row_tile(i):
    if i in SPECIALS:
        return special_html(i)
    b = BY_ID.get(i)
    return button_html(b, "", ' data-id="%s"' % i) if b and installed(b) else ""


def render_general():
    """Scheda Generale: pannello audio a sinistra, sezioni a destra; gruppi come riquadri che si aprono."""
    shown = [b for b in BUTTONS if installed(b)]
    secs, pops = [], []
    for sid, title in SECTIONS:
        tiles = []
        if sid == "avvio":
            tiles = [row_tile(f) for f in ROWS["avvio"]]
            parts, total = [], 0
            for g in GROUPS:
                items = [b for b in shown if b.get("group") == g["id"]]
                total += len(items)
                parts += [button_html(dict(b, hint=g["label"]), "", ' data-id="%s"' % b["id"]) for b in items]
            tiles.append(button_html({"label": "Altre app", "icon": "grid", "cat": "app", "hint": "%d app &rsaquo;" % total},
                                     " grpt", ' data-grp="altre"').replace("&amp;rsaquo;", "&rsaquo;"))
            pops.append('<div class="gpop" id="pop_altre"><div class="gbox"><div class="ghd"><b>Altre app</b><span class="gx">Chiudi</span></div>'
                        '<div class="ggrid">%s</div></div></div>' % "".join(parts))
        else:
            tiles = [row_tile(i) for i in ROWS[sid]]
        # le finestre aperte non stanno piu' qui: sono nella fascia a destra, visibile in ogni sezione
        secs.append('<div class="sec sec-%s"><div class="sh">%s</div><div class="row">%s</div></div>'
                    % (sid, html.escape(title), "".join(tiles)))
    return '<div id="secs">%s</div>' % "".join(secs), "".join(pops)


# ---------------------------------------------------------------------------
# AGGIORNAMENTI da GitHub. Si contatta solo GitHub (HTTPS); nulla viene installato senza conferma.
# Il lavoro vero (copia di sicurezza, sostituzione, ripristino se la nuova versione non parte) lo fa updater.py.
# ---------------------------------------------------------------------------
UPDATE_REPO = "MannAk1/TabDeck"   # repository GitHub dei rilasci; vuoto = aggiornamenti non configurati
UPDATE_HOSTS = ("api.github.com", "codeload.github.com", "github.com")
UPDATE_DIR = os.path.join(CACHE_DIR, "update")
UPDATE_CHECK_FILE = os.path.join(DATA_DIR, "update_check.json")
UPDATE_RESULT_FILE = os.path.join(DATA_DIR, "update_result.json")
UPD = {"latest": None, "notes": "", "zip": None, "t": 0}
UPD_LOCK = threading.Lock()


def parse_version(s):
    m = re.match(r"^v?(\d{1,4})\.(\d{1,4})\.(\d{1,4})$", s or "")
    return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)


def update_host_ok(url):
    p = urlparse(url)
    try:
        port = p.port
    except ValueError:
        return False
    return p.scheme == "https" and p.hostname in UPDATE_HOSTS and not p.username and port in (None, 443)


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not update_host_ok(newurl):
            raise OSError("reindirizzamento non consentito: %s" % urlparse(newurl).hostname)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _open(url, timeout):
    if not update_host_ok(url):
        raise OSError("indirizzo non consentito")
    req = urllib.request.Request(url, headers={"User-Agent": "TabDeck-updater", "Accept": "application/vnd.github+json"})
    return urllib.request.build_opener(_SafeRedirect).open(req, timeout=timeout)


def _http_get(url):
    with _open(url, 10) as r:
        return r.read(1024 * 1024)


def _download(url, dst):
    import updater
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    n = 0
    with _open(url, 30) as r, open(dst, "wb") as f:
        while True:
            chunk = r.read(65536)
            if not chunk:
                break
            n += len(chunk)
            if n > updater.MAX_ZIP:
                raise OSError("file troppo grande")
            f.write(chunk)


def latest_release(repo):
    j = json.loads(_http_get("https://api.github.com/repos/%s/releases/latest" % repo).decode("utf-8"))
    return {"version": str(j.get("tag_name") or "").lstrip("v"), "notes": str(j.get("body") or "")[:4000],
            "zip": str(j.get("zipball_url") or "")}


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _load_saved_check():
    """Ultimo controllo salvato (es. dopo un riavvio). Non tocca l'esito dell'ultimo aggiornamento."""
    if UPD["latest"] is None:
        saved = _read_json(UPDATE_CHECK_FILE)
        if isinstance(saved, dict) and saved.get("latest"):
            UPD.update({k: saved.get(k) for k in ("latest", "notes", "zip", "t")})


def update_status():
    import updater
    _load_saved_check()
    res = _read_json(UPDATE_RESULT_FILE)          # esito dell'ultimo aggiornamento: mostrato una volta sola
    if isinstance(res, dict) and not res.get("seen"):
        try:
            with open(UPDATE_RESULT_FILE, "w", encoding="utf-8") as f:
                json.dump(dict(res, seen=True), f)
        except OSError:
            pass
    else:
        res = None
    return {"cur": VERSION, "repo": bool(UPDATE_REPO), "latest": UPD["latest"], "notes": UPD["notes"] or "",
            "newer": parse_version(UPD["latest"]) > parse_version(VERSION),
            "result": res, "backup": updater.previous_backup(HERE, VERSION) is not None}


def update_check():
    if not UPDATE_REPO:
        raise OSError("aggiornamenti non configurati")
    r = latest_release(UPDATE_REPO)
    with UPD_LOCK:
        UPD.update({"latest": r["version"], "notes": r["notes"], "zip": r["zip"], "t": time.time()})
        try:
            with open(UPDATE_CHECK_FILE, "w", encoding="utf-8") as f:
                json.dump(UPD, f)
        except OSError:
            pass
    return update_status()


def _spawn_updater(args):
    os.makedirs(UPDATE_DIR, exist_ok=True)
    run = os.path.join(UPDATE_DIR, "updater_run.py")   # copia: updater.py stesso puo' essere sostituito
    shutil.copy2(os.path.join(HERE, "updater.py"), run)
    subprocess.Popen([sys.executable, run] + args + ["--root", HERE, "--pid", str(os.getpid())], cwd=HERE,
                     creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP, close_fds=True)
    threading.Thread(target=_exit_for_update, daemon=True).start()


def _exit_for_update():
    time.sleep(0.6)            # lascia partire la risposta al telefono
    ppid = os.getppid()
    if os.path.basename(_exe_of_pid(ppid)).lower() == "cmd.exe":
        subprocess.run(["taskkill", "/F", "/PID", str(ppid)], capture_output=True)
    os._exit(0)


def update_apply():
    """Scarica e controlla lo zip, poi passa la mano a updater.py e chiude TabDeck. Restituisce un errore o ""."""
    import updater
    latest, url = UPD["latest"], UPD["zip"]
    if not latest or not url:
        return "Prima cerca gli aggiornamenti"
    if parse_version(latest) <= parse_version(VERSION):
        return "Hai gia' l'ultima versione"
    dst = os.path.join(UPDATE_DIR, "v%s.zip" % ".".join(map(str, parse_version(latest))))
    try:
        _download(url, dst)
        updater.check_zip(dst)
    except (OSError, updater.UpdateError) as e:
        return "Download non riuscito: %s" % e
    _spawn_updater(["apply", dst, "--old", VERSION, "--new", latest])
    return ""


def update_rollback():
    import updater
    if updater.previous_backup(HERE, VERSION) is None:
        return "Nessuna versione precedente salvata"
    _spawn_updater(["rollback", "--old", VERSION])
    return ""


def _update_auto_check():
    """Controllo silenzioso all'avvio (al massimo una volta al giorno): solo un pallino sull'ingranaggio."""
    time.sleep(60)
    if not UPDATE_REPO or load_settings().get("updchk") == "off":
        return
    _load_saved_check()
    if time.time() - (UPD.get("t") or 0) < 86400:
        return
    try:
        update_check()
    except (OSError, ValueError) as e:
        print("[%s] controllo aggiornamenti non riuscito: %s" % (time.strftime("%H:%M:%S"), e))


def host_ok(host, bound_ip, port):
    """Contro il DNS rebinding: una pagina web maligna aperta sul PC potrebbe far puntare un suo nome
    all'indirizzo di TabDeck; il browser manderebbe pero' Host: <quel nome>. Si accetta solo IP:porta."""
    return host == "%s:%d" % (bound_ip, port)


# Chiave che TabDeck-Setup.exe (Inno Setup, AppId fisso) crea in "App installate": dopo un aggiornamento
# dal telefono la versione mostrata da Windows va riallineata a quella vera.
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\{7AEEA677-21CD-402C-AC74-6CC3D2F40359}_is1"


def sync_uninstall_version(version, key_path=UNINSTALL_KEY):
    """Aggiorna DisplayVersion se TabDeck e' stato installato con il setup; True se l'ha cambiata."""
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE) as k:
            try:
                if winreg.QueryValueEx(k, "DisplayVersion")[0] == version:
                    return False
            except OSError:
                pass
            winreg.SetValueEx(k, "DisplayVersion", 0, winreg.REG_SZ, version)
            return True
    except OSError:
        return False


def web_manifest(token):
    """Descrizione dell'app per la schermata Home (Android/iPhone): tutto schermo, icona, avvio con il token
    (le app aggiunte alla Home possono avere cookie separati dal browser)."""
    return {"name": "TabDeck", "short_name": "TabDeck", "start_url": "/?t=" + token, "scope": "/",
            "display": "fullscreen", "orientation": "any", "background_color": "#0a0b08", "theme_color": "#0a0b08",
            "icons": [{"src": "/apple-touch-icon.png", "sizes": "180x180", "type": "image/png"},
                      {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png"}]}


def pair_allowed(client_ip, bound_ip):
    """La pagina /pair mostra il token: la si apre solo dal PC stesso (stesso indirizzo o localhost)."""
    return client_ip in (bound_ip, "127.0.0.1")


def render_pair(host, token):
    import tdqr
    url = "http://%s:%d/?t=%s" % (host, PORT, token)
    with open(os.path.join(WEB_DIR, "pair.html"), encoding="utf-8") as f:
        page = f.read()
    return (page.replace("__QR__", tdqr.qr_svg(url)).replace("__URL__", html.escape(url))
            .replace("__VERSION__", html.escape(VERSION)))


def render_wait(token, state, code):
    """Pagina per un dispositivo non ancora approvato (o rifiutato / richieste sospese)."""
    with open(os.path.join(WEB_DIR, "wait.html"), encoding="utf-8") as f:
        page = f.read()
    msg = {"pending": "Approva questo dispositivo dalla finestra di TabDeck sul PC.<br>Controlla che il codice sia lo stesso.",
           "refused": "Richiesta rifiutata dal PC. Riprova tra qualche minuto.",
           "locked": "Troppe richieste rifiutate: nuove richieste sospese per un po'."}.get(state, "")
    return (page.replace("__CODE__", html.escape(code or "----")).replace("__MSG__", msg)
            .replace("__STATE__", state).replace("__TOKEN__", token))


def render_page(token, device=""):
    general, pops = render_general()
    icons = available_icons()
    strats, jump = [], []
    for gi, (grp, col, items) in enumerate(STRATAGEMS):
        jump.append('<div class="jc %s" data-g="g%d">%s</div>' % (col, gi, html.escape(grp)))
        strats.append('<div class="grp %s" id="g%d"><i></i><b>%s</b><span></span><em>%d</em></div><div class="gl">'
                      % (col, gi, html.escape(grp), len(items)))
        for sid, name, code in items:
            if sid in icons:
                inner = '<img src="/icon/%s.svg" alt="">' % sid
            else:
                inner = '<span class="n">%s</span><span class="c%s">%s</span>' % (
                    html.escape(name), " lg" if len(code) >= 7 else "", arrows_html(code))
            strats.append('<button class="s %s" data-id="hd2_%s" data-n="%s" data-c="%s">%s</button>'
                          % (col, sid, html.escape(name, True), code, inner))
        strats.append("</div>")
    page = re.sub(r"__SVG_([a-z_]+)__", lambda m: svg(m.group(1)), page_template())
    page = page.replace("__PADKEYS__", "".join('<div class="kk%s" data-k="%s">%s</div>' % (" ar" if k in ("UP", "DOWN", "LEFT", "RIGHT") else "", k, lab)
                                                for k, lab in PAD_KEYS))
    return (page.replace("__BUTTONS__", general).replace("__POPS__", pops).replace("__STRATS__", "".join(strats))
            .replace("__JUMP__", "".join(jump))
            .replace("__FULLICON__", svg("full")).replace("__GEARICON__", svg("cog")).replace("__NAVICON__", svg("grid"))
            .replace("__KEYGRID__", "".join('<div data-k="%s">%s</div>' % (k, html.escape(KEY_PRETTY.get(k, k))) for k in KEY_CHOICES))
            .replace("__MODGRID__", "".join('<div data-m="%s">%s</div>' % (m, KEY_PRETTY[m]) for m in MODS))
            .replace("__ICONGRID__", '<div data-i="">Aa</div>' + "".join('<div data-i="%s">%s</div>' % (n, svg(n)) for n in ICONS))
            .replace("__NAVTILES__", "".join('<div class="tab nt%s" data-tab="%s">%s<div><b>%s</b><span>%s</span></div></div>'
                                             % (" sel" if i == 0 else "", t, svg(ic), html.escape(n), html.escape(d))
                                             for i, (t, n, d, ic) in enumerate(NAV)))
            .replace("__TABS__", json.dumps([t for t, _n, _d, _i in NAV]))
            .replace("__TABNAMES__", json.dumps({t: n for t, n, _d, _i in NAV}))
            .replace("__HOLD__", str(HOLD_MS))
            .replace("__SETTINGS__", json.dumps(load_settings()))
            .replace("__ALWAYS__", json.dumps(["hd2_" + s for s in ALWAYS]))
            .replace("__CD__", json.dumps(cd_state()))
            .replace("__LOADOUT__", json.dumps(load_loadout())).replace("__DEVICE__", device)
            .replace("__APPR__", "true" if DEVICES is not None and DEVICES.require else "false")
            .replace("__TOKEN__", token))


# ---------------------------------------------------------------------------
# SERVER HTTP. Ogni richiesta passa di qui (un thread per connessione: ThreadingHTTPServer).
# Sicurezza, in ordine:
#   1. _token_ok: token in X-Token (richieste della pagina), ?t= (solo il primo caricamento da adb)
#      o cookie "td" (ricaricamenti); confronto a tempo costante. Senza token: 403 e basta.
#   2. do_POST: solo percorsi in lista, corpo limitato (1 KB / 8 KB per il testo), poi ogni endpoint
#      valida i suoi valori (liste ammesse, regex sugli id, intervalli numerici).
#   3. _send: intestazioni anti-cache/sniffing/iframe/referrer su tutte le risposte.
#   4. log_message: niente token e niente testo digitato nei log.
# Prestazioni: keep-alive (HTTP/1.1) per non aprire una connessione TCP a ogni tocco; risposte JSON
# piccole; le richieste frequenti riuscite non vengono scritte nel log.
# ---------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    server_version = "TabDeck"
    sys_version = ""
    protocol_version = "HTTP/1.1"  # keep-alive: niente nuova connessione TCP a ogni tocco
    timeout = 30                   # chiude le connessioni inattive

    def _send(self, code, body, ctype="text/plain; charset=utf-8", headers=None):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        hdrs = {"Cache-Control": "no-store"}
        if code >= 400:  # il corpo della richiesta potrebbe non essere stato letto: chiudi
            hdrs["Connection"] = "close"
            self.close_connection = True
        hdrs.update(headers or {})
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")   # l'indirizzo della pagina non va mai ad altri siti (es. CDN di Discord)
        for k, v in hdrs.items():
            for one in (v if isinstance(v, list) else [v]):   # lista = piu' intestazioni uguali (Set-Cookie)
                self.send_header(k, one)
        self.end_headers()
        self.wfile.write(data)

    def _token_ok(self, query):
        given = self.headers.get("X-Token") or (query.get("t") or [""])[0]
        if not given:
            try:
                morsel = SimpleCookie(self.headers.get("Cookie") or "").get("td")
            except CookieError:
                morsel = None
            given = morsel.value if morsel else ""
        return hmac.compare_digest(given.encode(), self.server.token.encode())

    def _dev_id(self):
        dev = self.headers.get("X-Device")     # dalla pagina (localStorage): conta anche senza cookie (app iOS)
        if not devices.valid_id(dev):
            try:
                morsel = SimpleCookie(self.headers.get("Cookie") or "").get("tdd")
            except CookieError:
                morsel = None
            dev = morsel.value if morsel else None
        return dev if devices.valid_id(dev) else None

    def _auth(self, query, create=False):
        """-> (stato, id dispositivo). stato: ok | pending | refused | locked | bad (= 403 senza dettagli).
        Entra chi ha il token giusto (e, con l'approvazione attiva, un dispositivo approvato) oppure un dispositivo
        approvato anche con un token vecchio ("Nuovo link"). Solo la pagina e /devstate (create=True) registrano
        un dispositivo nuovo: icone e richieste sparse non riempiono l'elenco."""
        tok = self._token_ok(query)
        store = DEVICES
        if store is None:
            return ("ok" if tok else "bad"), None
        dev = self._dev_id()
        ip, ua = self.client_address[0], self.headers.get("User-Agent") or ""
        if store.is_approved(dev):
            return store.access(dev, ip, ua)
        if not tok:
            return "bad", None
        if create or dev:
            # chi manda gia' un ID (la pagina lo fa sempre) viene registrato: niente accessi che non compaiono
            # nell'elenco, e un dispositivo tolto torna "in attesa" alla sua prossima azione
            return store.access(dev, ip, ua)
        return ("ok" if not store.require else "pending"), dev

    def _dev_cookie(self, dev):
        return "tdd=%s; Path=/; Max-Age=31536000; HttpOnly; SameSite=Strict" % dev

    def _host_ok(self):
        return host_ok(self.headers.get("Host"), *self.server.server_address[:2])

    def do_GET(self):
        if not self._host_ok():
            return self._send(403, "403 Forbidden")
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path in ("/apple-touch-icon.png", "/icon-512.png"):   # icona per la schermata Home: pubblica, niente segreti
            try:
                with open(os.path.join(ASSETS_DIR, u.path[1:]), "rb") as f:
                    return self._send(200, f.read(), "image/png", {"Cache-Control": "public, max-age=86400"})
            except OSError:
                return self._send(404, "404")
        if u.path == "/pair":   # abbinamento del telefono: niente token, ma SOLO da questo PC
            bound = self.server.server_address[0]
            if not pair_allowed(self.client_address[0], bound):
                return self._send(403, "403 Forbidden")
            return self._send(200, render_pair(bound, self.server.token), "text/html; charset=utf-8")
        st, dev = self._auth(q, create=u.path in ("/", "/devstate"))
        if st == "bad":
            if u.path == "/":   # link vecchio o senza cookie: la pagina prova l'ID salvato nel browser (app iOS)
                with open(os.path.join(WEB_DIR, "recover.html"), "rb") as f:
                    return self._send(403, f.read(), "text/html; charset=utf-8")
            return self._send(403, "403 Forbidden")
        if u.path == "/devstate":   # la pagina d'attesa chiede ogni 2 s se e' stata approvata
            code = DEVICES.code_of(dev) if DEVICES is not None and dev else None
            return self._send(200, json.dumps({"state": st, "code": code}), "application/json",
                              {"Set-Cookie": self._dev_cookie(dev)} if dev else None)
        if st != "ok":
            if u.path == "/":
                code = DEVICES.code_of(dev) if st == "pending" else None
                return self._send(200 if st == "pending" else 403, render_wait(self.server.token, st, code),
                                  "text/html; charset=utf-8", {"Set-Cookie": self._dev_cookie(dev)})
            return self._send(403, json.dumps({st: True}), "application/json")
        if u.path == "/":
            # cookie: dopo aver tolto il token dall'URL, un ricaricamento della pagina funziona ancora
            cookies = ["td=%s; Path=/; Max-Age=31536000; HttpOnly; SameSite=Strict" % self.server.token]
            if dev:
                cookies.append(self._dev_cookie(dev))
            return self._send(200, render_page(self.server.token, dev or ""), "text/html; charset=utf-8",
                              {"Set-Cookie": cookies})
        if u.path == "/ping":
            return self._send(200, "ok")
        if u.path == "/manifest.json":   # "Aggiungi a schermata Home": app a tutto schermo che riparte gia' collegata
            return self._send(200, json.dumps(web_manifest(self.server.token)), "application/manifest+json")
        if u.path.startswith("/appicon/") and u.path.endswith(".png"):
            key = u.path[len("/appicon/"):-len(".png")]
            data = app_icon(key) if re.match(r"^[0-9a-f]{16}$", key) else None
            if data is None:
                return self._send(404, "404")
            return self._send(200, data, "image/png", {"Cache-Control": "private, max-age=86400"})
        if u.path == "/windows":
            return self._send(200, json.dumps(list_windows()), "application/json")
        if u.path == "/stats":
            st = STATS.get("h" in q)
            st["cn"] = CPU_NAME
            return self._send(200, json.dumps(st), "application/json")
        if u.path == "/audio":
            return self._send(200, json.dumps(audio_overview()), "application/json")
        if u.path.startswith("/cover/"):
            key, cover = MEDIA.cover
            if key and cover and u.path == "/cover/" + key:
                return self._send(200, cover[1], cover[0], {"Cache-Control": "private, max-age=86400"})
            return self._send(404, "404")
        if u.path == "/layout":
            return self._send(200, json.dumps(layout_info()), "application/json")
        if u.path == "/general":   # Generale rifatto dopo "Salva": la pagina lo sostituisce senza ricaricarsi
            secs, pops = render_general()
            return self._send(200, json.dumps({"secs": secs, "pops": pops}), "application/json")
        if u.path == "/yts":    # ricerca YouTube dal tablet
            yq = (q.get("q") or [""])[0].strip()
            if not yq or len(yq) > 200:
                return self._send(400, "ricerca non valida")
            try:
                res = youtube.search(yq)
            except youtube.SearchError as e:
                self.log_message("ERRORE ricerca YouTube: %s", e)
                return self._send(502, json.dumps({"err": "Ricerca non riuscita"}), "application/json")
            return self._send(200, json.dumps({"r": res}), "application/json")
        if u.path == "/ytsug":  # suggerimenti mentre si scrive nella ricerca YouTube
            yq = (q.get("q") or [""])[0].strip()
            if not yq or len(yq) > 200:
                return self._send(400, "ricerca non valida")
            return self._send(200, json.dumps({"s": youtube.suggest(yq)}), "application/json")
        if u.path == "/yt":     # stato del player YouTube (ogni secondo mentre la sezione e' aperta)
            return self._send(200, json.dumps(YT.snapshot()), "application/json")
        if u.path == "/dc":     # sezione Discord: stato + chiamata attuale (ogni 0,6 s mentre e' aperta)
            return self._send(200, json.dumps({"st": DISCORD.state(), "vc": DISCORD.vc_state()}), "application/json")
        if u.path in ("/dcguilds", "/dcch"):
            gid = (q.get("g") or [""])[0]
            if u.path == "/dcch" and not re.match(r"^\d{5,25}$", gid):
                return self._send(400, "server non valido")
            try:
                data = DISCORD.guilds() if u.path == "/dcguilds" else DISCORD.channels(gid)
            except DiscordError as e:
                self.log_message("discord %s: %s", u.path, e)
                return self._send(409, json.dumps({"err": str(e)}), "application/json")
            return self._send(200, json.dumps(data), "application/json")
        if u.path == "/state":  # stato letto dal tablet ogni 1,5 s
            try:
                st = audio_state()
            except OSError:
                st = {}
            st["hd"] = cd_state()
            if "g" in q:
                st["dc"] = DISCORD.state()
                try:
                    st["mic"] = mic_state()
                except OSError:
                    pass
                try:
                    st["wins"] = list_windows()
                    st["run"] = running_apps(st["wins"])
                except OSError as e:
                    self.log_message("ERRORE app attive: %s", e)
            return self._send(200, json.dumps(st), "application/json")
        if u.path == "/volume":
            try:
                return self._send(200, json.dumps(audio_state()), "application/json")
            except OSError as e:
                self.log_message("ERRORE volume: %s", e)
                return self._send(500, "errore audio")
        if u.path.startswith("/icon/") and u.path.endswith(".svg"):
            name = u.path[len("/icon/"):-len(".svg")]
            path = os.path.join(ICON_DIR, name + ".svg")
            if ICON_RE.match(name) and os.path.isfile(path):
                with open(path, "rb") as f:
                    return self._send(200, f.read(), "image/svg+xml", {
                        "Cache-Control": "private, max-age=86400",
                        "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'"})
        self._send(404, "404")

    def _yt(self, form):
        """Comandi del player YouTube dal tablet."""
        f = lambda k: (form.get(k) or [""])[0]
        a, vid = f("a"), f("id")
        if a in ("play", "add", "web") and not youtube.ID_RE.match(vid):
            return self._send(400, "video non valido")
        try:
            if a in ("play", "add"):
                item = {"id": vid, "title": f("title")[:200], "channel": f("channel")[:200], "dur": f("dur")[:16]}
                was_open = YT.is_open()
                YT.play_now(item) if a == "play" else YT.enqueue(item)
                if not was_open and yt_open(front=False) == "opened":
                    YT.mark_opening()   # niente seconda scheda mentre il browser la sta aprendo
            elif a in ("up", "rm"):
                if not f("i").isdigit():
                    return self._send(400, "posizione non valida")
                (YT.move_up if a == "up" else YT.remove)(int(f("i")))
            elif a == "seek":
                sv = float(f("s"))
                if sv != sv or sv in (float("inf"), float("-inf")):
                    raise ValueError
                YT.seek(sv)
            elif a == "vol":
                if not f("v").isdigit():
                    return self._send(400, "volume non valido")
                YT.volume(int(f("v")))
            elif a in ("next", "prev", "toggle"):
                getattr(YT, a)()
            elif a == "web":
                os.startfile("https://www.youtube.com/watch?v=" + vid)
            elif a != "open":
                return self._send(400, "azione non valida")
        except ValueError:
            return self._send(400, "valore non valido")
        st = YT.snapshot()
        if a == "open":
            st["open_r"] = yt_open(front=True)
            if st["open_r"] == "opened":
                YT.mark_opening()
        return self._send(200, json.dumps(st), "application/json")

    def do_POST(self):
        if not self._host_ok():
            return self._send(403, "403 Forbidden")
        u = urlparse(self.path)
        st, _dev = self._auth(parse_qs(u.query))
        if st == "bad":
            return self._send(403, "403 Forbidden")
        if st != "ok":
            return self._send(403, json.dumps({st: True}), "application/json")
        if u.path not in ("/press", "/hd2sync", "/loadout", "/settings", "/volume", "/focus", "/appvol", "/media",
                          "/mouse", "/type", "/key", "/mic", "/discord", "/winact", "/layout", "/restart", "/update", "/yt"):
            return self._send(404, "404")
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return self._send(400, "400")
        if n < 0:
            return self._send(400, "400")
        if n > (8192 if u.path == "/type" else 4096 if u.path == "/yt" else 1024):
            return self._send(413, "413")
        form = parse_qs(self.rfile.read(n).decode("utf-8", "replace"), keep_blank_values=True)
        if u.path in ("/mouse", "/type", "/key"):
            return self._input(u.path, form)
        if u.path == "/yt":
            return self._yt(form)
        if u.path == "/hd2sync":
            try:
                ids, codes = sync_loadout()
            except NotInGame as e:
                self.log_message("sincronizzazione ignorata: in primo piano c'e' %r", str(e))
                return self._send(409, "HD2 non in primo piano")
            except OSError as e:
                self.log_message("ERRORE sincronizzazione: %s", e)
                return self._send(500, "errore")
            self.log_message("sincronizzazione: codici %s -> %s", codes, ids)
            if not ids:
                return self._send(422, json.dumps({"codes": codes}), "application/json")
            save_loadout(ids)
            return self._send(200, json.dumps({"ids": ids}), "application/json")
        if u.path == "/loadout":
            raw = (form.get("ids") or [""])[0]
            ids = [i for i in raw.split(",") if i]
            if len(ids) > LOADOUT_MAX or len(set(ids)) != len(ids) or not all(pinnable(i) for i in ids):
                return self._send(400, "equipaggiamento non valido")
            save_loadout(ids)
            self.log_message("equipaggiamento: %s", ", ".join(BY_ID[i]["label"] for i in ids) or "(vuoto)")
            return self._send(200, json.dumps({"ok": True, "ids": ids}), "application/json")
        if u.path == "/focus":
            h = (form.get("h") or [""])[0]
            wins = list_windows()
            target = next((w for w in wins if w["h"] == h), None)  # solo finestre elencate in questo momento
            if target is None:
                return self._send(404, "finestra non trovata")
            keep = (form.get("keep") or [""])[0] == "1"     # dai riquadri della scheda Generale: solo in primo piano
            if target["fg"] and not target["min"] and not keep:   # e' gia' davanti: ripremerla la riduce a icona
                minimize_window(int(h))
                action, ok = "min", True
            else:
                action, ok = "focus", focus_window(int(h))
            self.log_message("finestra %s: %s", {"min": "ridotta a icona", "focus": "in primo piano"}[action]
                             if ok else "NON portata avanti", target["x"])
            return self._send(200 if ok else 409, json.dumps({"a": action, "w": list_windows()}), "application/json")
        if u.path == "/volume":
            level, mute =(form.get("vol") or [None])[0], (form.get("mute") or [None])[0]
            try:
                level = None if level is None else max(0, min(100, int(level)))
            except ValueError:
                return self._send(400, "volume non valido")
            if mute not in (None, "0", "1"):
                return self._send(400, "muto non valido")
            try:
                st = audio_state(level, None if mute is None else mute == "1")
            except OSError as e:
                self.log_message("ERRORE volume: %s", e)
                return self._send(500, "errore audio")
            return self._send(200, json.dumps(st), "application/json")
        if u.path == "/update":
            a = (form.get("a") or [""])[0]
            try:
                if a == "status":
                    return self._send(200, json.dumps(update_status()), "application/json")
                if a == "check":
                    return self._send(200, json.dumps(update_check()), "application/json")
            except (OSError, ValueError) as e:
                return self._send(200, json.dumps({"error": "Controllo non riuscito: %s" % e}), "application/json")
            if a in ("apply", "rollback"):
                self.log_message("aggiornamento chiesto dal tablet: %s", a)
                err = update_apply() if a == "apply" else update_rollback()
                return self._send(200, json.dumps({"error": err}), "application/json")
            return self._send(400, "400")
        if u.path == "/restart":
            self.log_message("riavvio chiesto dal tablet")
            threading.Thread(target=restart_tabdeck, daemon=True).start()
            return self._send(200, "ok")
        if u.path == "/layout" and (form.get("a") or [""])[0] in ("key", "delkey"):
            kid = (form.get("id") or [""])[0] or "k_" + secrets.token_hex(4)
            if form["a"][0] == "delkey":
                with LAYOUT_LOCK:
                    CUSTOM_KEYS[:] = [k for k in CUSTOM_KEYS if k["id"] != kid]
                    for sid in ROW_SIDS:
                        ROWS[sid][:] = [i for i in ROWS[sid] if i != kid]
                _drop_button(kid)
                save_layout()
                self.log_message("scorciatoia eliminata: %s", kid)
                return self._send(200, json.dumps(layout_info()), "application/json")
            spec = {"id": kid, "label": (form.get("label") or [""])[0].strip(),
                    "keys": [x for x in (form.get("keys") or [""])[0].split("+") if x], "icon": (form.get("icon") or [""])[0]}
            if not key_spec_ok(spec) or (kid in BY_ID and not BY_ID[kid].get("customkey")):
                return self._send(400, "scorciatoia non valida")
            with LAYOUT_LOCK:
                CUSTOM_KEYS[:] = [k for k in CUSTOM_KEYS if k["id"] != kid] + [spec]
            _put_button(key_button(spec))
            save_layout()
            self.log_message("scorciatoia %s: %s = %s", kid, spec["label"], "+".join(spec["keys"]))
            out = layout_info()
            out["new"] = kid
            return self._send(200, json.dumps(out), "application/json")
        if u.path == "/layout":
            want = {}
            for sid in ROW_SIDS:
                field = (form.get(sid) or form.get("fav" if sid == "avvio" else sid) or [None])[0]
                want[sid] = ROWS[sid] if field is None else [x for x in field.split(",") if x]
                if len(want[sid]) > FAV_MAX:
                    return self._send(400, "troppi riquadri")
            opened = open_specs() if any(x.startswith("x:") for sid in ROW_SIDS for x in want[sid]) else {}   # solo finestre aperte ora
            for sid in ROW_SIDS:
                lst = []
                for it in want[sid]:
                    if it.startswith("x:"):
                        spec = opened.get(it[2:], "")
                        if not _spec_ok(spec):
                            return self._send(409, "app non piu' aperta")
                        it = _add_custom(spec)
                    if it not in SPECIALS and it not in BY_ID:
                        return self._send(400, "riquadro sconosciuto")
                    lst.append(it)
                want[sid] = lst
            rows = clean_rows(want)
            save_layout(rows)
            self.log_message("righe: %s", " | ".join(",".join(rows[sid]) for sid in ROW_SIDS))
            return self._send(200, json.dumps(rows), "application/json")
        if u.path == "/winact":
            h, a = (form.get("h") or [""])[0], (form.get("a") or [""])[0]
            if a not in ("min", "max", "close"):
                return self._send(400, "azione non valida")
            target = next((w for w in list_windows() if w["h"] == h), None)  # solo finestre elencate ora
            if target is None:
                return self._send(404, "finestra non trovata")
            hw = int(h)
            if a == "min":
                minimize_window(hw)
                ok, what = True, "ridotta a icona"
            elif a == "max":
                if _u32.IsZoomed(hw) and not target["min"]:  # gia' ingrandita: torna normale
                    _u32.ShowWindow(hw, 9)                   # SW_RESTORE
                    what = "ripristinata"
                else:
                    _u32.ShowWindow(hw, 3)                   # SW_MAXIMIZE
                    what = "ingrandita"
                ok = focus_window(hw)
            else:
                ok, what = _u32.PostMessageW(hw, 0x0010, None, None), "chiusura chiesta"   # WM_CLOSE: l'app puo' chiedere di salvare
            self.log_message("finestra %s: %s", what if ok else "NON " + what, target["x"])
            return self._send(200 if ok else 409, json.dumps({"r": what, "w": list_windows()}), "application/json")
        if u.path == "/discord" and (form.get("a") or [""])[0] in ("logout", "reauth"):
            DISCORD.logout(reauth=form["a"][0] == "reauth")
            self.log_message("discord: %s", form["a"][0])
            return self._send(200, json.dumps(DISCORD.state()), "application/json")
        if u.path == "/discord" and (form.get("a") or [""])[0] in ("join", "leave", "uvol", "umute"):
            act = form["a"][0]
            c, uid, v = (form.get("c") or [""])[0], (form.get("u") or [""])[0], (form.get("v") or [""])[0]
            idre = re.compile(r"^\d{5,25}$")
            try:
                if act == "join":
                    if not idre.match(c):
                        return self._send(400, "canale non valido")
                    DISCORD.call("SELECT_VOICE_CHANNEL", {"channel_id": c, "force": True}, 15.0)
                elif act == "leave":
                    DISCORD.call("SELECT_VOICE_CHANNEL", {"channel_id": None, "force": True})
                else:
                    if not idre.match(uid):
                        return self._send(400, "utente non valido")
                    if act == "uvol":
                        if not v.isdigit() or int(v) > 200:
                            return self._send(400, "volume non valido")
                        DISCORD.call("SET_USER_VOICE_SETTINGS", {"user_id": uid, "volume": int(v)})
                        DISCORD.patch_member(uid, vol=int(v))
                    else:
                        DISCORD.call("SET_USER_VOICE_SETTINGS", {"user_id": uid, "mute": v == "1"})
                        DISCORD.patch_member(uid, lm=v == "1")
            except DiscordError as e:
                self.log_message("discord %s: %s", act, e)
                return self._send(409, json.dumps({"err": str(e)}), "application/json")
            DISCORD.cache = {}
            return self._send(200, json.dumps({"st": DISCORD.state(), "vc": DISCORD.vc_state()}), "application/json")
        if u.path == "/discord":
            vals = {}
            for k in ("mute", "deaf"):
                v = (form.get(k) or [None])[0]
                if v not in (None, "0", "1"):
                    return self._send(400, "valore non valido")
                if v is not None:
                    vals[k] = v == "1"
            inv = (form.get("inv") or [None])[0]
            if inv is not None:
                if not inv.isdigit() or int(inv) > 100:
                    return self._send(400, "volume non valido")
                vals["inv"] = int(inv)
            st = DISCORD.request(auth=(form.get("a") or [""])[0] == "auth", **vals)
            return self._send(200, json.dumps(st), "application/json")
        if u.path == "/mic":
            mute = (form.get("mute") or [None])[0]
            if mute not in ("0", "1"):
                return self._send(400, "muto non valido")
            try:
                st = mic_state(mute == "1")
            except OSError as e:
                self.log_message("ERRORE microfono: %s", e)
                return self._send(500, "nessun microfono")
            self.log_message("microfono %s", "MUTO" if st["mute"] else "attivo")
            return self._send(200, json.dumps(st), "application/json")
        if u.path == "/appvol":
            key = (form.get("k") or [""])[0]
            level, mute = (form.get("vol") or [None])[0], (form.get("mute") or [None])[0]
            if not (key == "system" or re.match(r"^[0-9a-f]{16}$", key)) or mute not in (None, "0", "1"):
                return self._send(400, "richiesta non valida")
            try:
                level = None if level is None else max(0, min(100, int(level)))
            except ValueError:
                return self._send(400, "volume non valido")
            try:
                found = mixer_set(key, level, None if mute is None else mute == "1")
            except OSError as e:
                self.log_message("ERRORE mixer: %s", e)
                return self._send(500, "errore audio")
            return self._send(200 if found else 404, "ok" if found else "app non trovata")
        if u.path == "/media":
            cmd, pos = (form.get("cmd") or [""])[0], (form.get("pos") or [None])[0]
            try:
                if pos is not None:
                    pos = float(pos)
                    if not 0 <= pos < 86400:
                        raise ValueError
                    ok = MEDIA.seek(pos)
                elif cmd in MEDIA_CMDS:
                    ok = MEDIA.command(cmd)
                else:
                    return self._send(400, "comando non valido")
            except ValueError:
                return self._send(400, "posizione non valida")
            except OSError as e:
                self.log_message("ERRORE media: %s", e)
                return self._send(500, "errore media")
            self.log_message("media %s: %s", cmd or "posizione %s" % pos, "ok" if ok else "rifiutato dall'app")
            return self._send(200 if ok else 409, "ok" if ok else "rifiutato")
        if u.path == "/settings":
            s = load_settings()
            for k, choices in SETTINGS_CHOICES.items():
                v = (form.get(k) or [None])[0]
                if v is None:
                    continue
                if v not in choices:
                    return self._send(400, "impostazione non valida")
                s[k] = v
            save_settings(s)
            self.log_message("impostazioni: %s", s)
            return self._send(200, json.dumps(s), "application/json")
        button = BY_ID.get((form.get("id") or [""])[0])
        if button is None:
            return self._send(400, "pulsante sconosciuto")
        try:
            trigger(button)
        except NotInGame as e:
            self.log_message("ignorato %s: in primo piano c'e' %r", button["id"], str(e))
            return self._send(409, "HD2 non in primo piano")
        except Exception as e:  # noqa: BLE001
            self.log_message("ERRORE %s: %s", button["id"], e)
            return self._send(500, "errore")
        self.log_message("premuto %s", button["id"])
        self._send(200, json.dumps({"ok": True, "id": button["id"], "hd": cd_state()}),
                   "application/json")

    def _input(self, path, form):
        """Touchpad e tastiera. Il testo scritto non finisce MAI nel log (potrebbe essere una password)."""
        def num(k, lim):
            v = int((form.get(k) or ["0"])[0] or 0)
            return max(-lim, min(lim, v))
        try:
            if path == "/mouse":
                btns = [b for b in (form.get("b") or [""])[0].split(",") if b]
                if any(b not in MOUSE_BTN for b in btns) or len(btns) > 8:
                    return self._send(400, "pulsante non valido")
                mouse_input(num("dx", 3000), num("dy", 3000), num("w", 2400), num("hw", 2400), btns)
            elif path == "/type":
                text = (form.get("t") or [""])[0]
                bs = num("bs", 500)
                if len(text) > 1000 or bs < 0:
                    return self._send(400, "testo non valido")
                type_text(text, bs)
            else:
                names = (form.get("k") or [""])[0].split("+")
                if not names or len(names) > 4 or any(k not in VK for k in names):
                    return self._send(400, "tasto non valido")
                press_combo(names)
                self.log_message("tasto %s", "+".join(names))
        except ValueError:
            return self._send(400, "valore non valido")
        except OSError as e:
            self.log_message("ERRORE input: %s", e)
            return self._send(500, "errore input")
        return self._send(200, "ok")

    def do_PUT(self):
        self._send(405, "405")
    do_DELETE = do_PATCH = do_PUT

    def log_message(self, fmt, *args):
        if getattr(self, "path", "").startswith(("/ping", "/icon/", "/appicon/", "/volume", "/windows", "/state", "/audio", "/cover/", "/appvol", "/mouse", "/type", "/stats", "/dc", "/discord", "/yt")) and len(args) > 1 and str(args[1]) == "200":
            return  # ping e icone riusciti non intasano il log
        msg = (fmt % args).replace(self.server.token, "***")  # mai il token nei log
        msg = _LOG_TOKEN_RE.sub(r"\1***", msg)               # nemmeno quelli vecchi o sbagliati
        sys.stderr.write("[%s] %s %s\n" % (time.strftime("%H:%M:%S"),
                                            self.client_address[0], msg))


_LOG_TOKEN_RE = re.compile(r"([?&]t=)[^&\s]+")


def find_adb():
    if ADB_PATH and os.path.isfile(ADB_PATH):
        return ADB_PATH
    a = shutil.which("adb")
    if a:
        return a
    for p in (os.path.join(HERE, "platform-tools", "adb.exe"), os.path.expanduser(r"~\Desktop\platform-tools\adb.exe"),
              os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"),
              r"C:\platform-tools\adb.exe"):
        if os.path.exists(p):
            return p
    return None


def _adb(adb, *cmd):
    """Esegue adb senza aprire finestre; None se fallisce o non risponde."""
    try:
        r = subprocess.run([adb] + list(cmd), capture_output=True, text=True, timeout=10,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return r.stdout if r.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def adb_devices(adb):
    out = _adb(adb, "devices") or ""
    rows = [ln.split() for ln in out.splitlines()[1:]]
    return {r[0] for r in rows if len(r) == 2 and r[1] == "device"}


def open_on_tablet(adb, url, serial):
    """Apre (o ricarica) la pagina in Chrome sul tablet, sempre nella stessa scheda."""
    ok = _adb(adb, "-s", serial, "shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", url,
              "-e", "com.android.browser.application_id", "tabdeck") is not None
    print("[%s] %s" % (time.strftime("%H:%M:%S"), "pagina aperta sul tablet" if ok else "apertura sul tablet NON riuscita"))


# Il server ascolta su UN indirizzo (quello del PC sull'hotspot), non su 0.0.0.0: le altre schede di rete
# (Ethernet, VPN, altri Wi-Fi) non lo vedono. main() lo ferma se il PC esce dalla rete consentita.
def start_server(host, token):
    global SERVER
    srv = ThreadingHTTPServer((host, PORT), Handler)
    srv.token = token
    SERVER = srv
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    return srv, th


YT = youtube.Player()   # player YouTube: la pagina gira nel browser del PC, il tablet la comanda
YT_URL = None


def _ylog(msg):
    print("[%s] YouTube: %s" % (time.strftime("%H:%M:%S"), msg))


def yt_start():
    """Server locale della pagina del player (solo 127.0.0.1, porta = PORT + 100)."""
    global YT_URL
    port = PORT + 100
    try:
        _srv, secret = youtube.start_player_server(port, YT, WEB_DIR)
    except OSError as e:
        _ylog("porta %d occupata, player non disponibile (%s)" % (port, e))
        return
    YT_URL = youtube.player_url(port, secret)


def yt_open(front):
    """Apre la pagina del player nel browser predefinito, o (front) porta davanti quella gia' aperta."""
    if YT_URL is None:
        return "unavailable"
    if YT.is_open():
        if not front:
            return "open"
        try:
            for w in list_windows():
                if w.get("t", "").startswith("TabDeck YouTube"):
                    focus_window(int(w["h"]))
                    return "front"
        except (OSError, ValueError) as e:
            _ylog("finestra del player non trovata: %s" % e)
        return "open"
    os.startfile(YT_URL)
    return "opened"


STATUS = {"state": None, "ip": None, "port": None, "adb": []}   # letto dalla finestra sul PC
_STOP = threading.Event()
_TRAY = None
_WINDOW_HIDDEN = lambda: True   # sostituita dalla finestra: serve al riavvio per ripartire uguale


def pythonw_exe():
    """pythonw.exe accanto al Python in uso (niente console); se manca, lo stesso Python."""
    w = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    return w if os.path.isfile(w) else sys.executable


STARTUP_LNK = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs",
                           "Startup", "TabDeck.lnk")


def _ps_lnk(script, **env):
    """PowerShell (WScript.Shell) per leggere/scrivere un .lnk; i percorsi passano come variabili d'ambiente."""
    e = dict(os.environ, **{"TD_" + k.upper(): v for k, v in env.items()})
    pre = "[Console]::OutputEncoding=[Text.Encoding]::UTF8; $s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:TD_LNK); "
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", pre + script], env=e,
                       capture_output=True, timeout=20, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode != 0:
        raise OSError(r.stderr.decode("utf-8", "replace").strip()[:200])
    return r.stdout.decode("utf-8", "replace")


def read_lnk(path):
    """-> (destinazione, argomenti) del collegamento."""
    out = _ps_lnk("[Console]::Out.Write($s.TargetPath + [char]10 + $s.Arguments)", lnk=path)
    target, _, args = out.partition("\n")
    return target.strip(), args.strip()


def write_lnk(path, target, args, workdir):
    """Crea o aggiorna il collegamento (un'icona gia' impostata resta)."""
    _ps_lnk("$s.TargetPath=$env:TD_T; $s.Arguments=$env:TD_A; $s.WorkingDirectory=$env:TD_W; $s.WindowStyle=1; "
            "$i=Join-Path $env:TD_W 'tabdeck.ico'; if (-not $s.IconLocation.Trim(',0') -and (Test-Path $i)) "
            "{ $s.IconLocation=$i }; $s.Save()", lnk=path, t=target, a=args, w=workdir)


def startup_lnk_plan(target, args, here, pyw):
    """Collegamento della 1.1.0 (tabdeck.bat di QUESTA cartella) -> (nuova destinazione, argomenti); altrimenti None.
    Chi aggiorna dall'app non riesegue l'installazione: senza questo all'avvio di Windows avrebbe console e finestra."""
    if os.path.normcase(target or "") != os.path.normcase(os.path.join(here, "tabdeck.bat")):
        return None
    return pyw, '"%s" --open --tray' % os.path.join(here, "tabdeck.py")


def migrate_startup_lnk(lnk=STARTUP_LNK, here=HERE, pyw=None):
    """True se ha aggiornato il collegamento in Esecuzione automatica."""
    if not os.path.isfile(lnk):
        return False
    plan = startup_lnk_plan(*read_lnk(lnk), here, pyw or pythonw_exe())
    if plan is None:
        return False
    write_lnk(lnk, plan[0], plan[1], here)
    print("collegamento in Esecuzione automatica aggiornato: ora TabDeck parte nell'area di notifica")
    return True


def _migrate_startup_bg():
    try:
        migrate_startup_lnk()
    except (OSError, subprocess.SubprocessError) as e:
        print("collegamento in Esecuzione automatica non aggiornato: %s" % e)


def quit_tabdeck():
    """Esci: ferma server e icona, salva i dispositivi, termina. Dopo 3 s si esce comunque."""
    t = threading.Timer(3, os._exit, (0,))
    t.daemon = True
    t.start()
    _STOP.set()
    try:   # avviato con la console (tabdeck.bat): chiude anche quella finestra, invece di lasciarla su "pause"
        ppid = os.getppid()
        if os.path.basename(_exe_of_pid(ppid)).lower() == "cmd.exe":
            subprocess.run(["taskkill", "/F", "/PID", str(ppid)], capture_output=True)
    except OSError:
        pass
    try:
        if DEVICES is not None:
            DEVICES.flush(force=True)
    except OSError:
        pass
    if _TRAY is not None:
        _TRAY.stop()
    if SERVER is not None:
        stop_server(SERVER)
    os._exit(0)


def restart_tabdeck(hidden=None):
    """Riavvia TabDeck: lancia una nuova istanza senza console (--restart: aspetta che questa esca) e termina.
    La nuova istanza riapre la pagina sul tablet; resta nell'area di notifica se la finestra era nascosta."""
    if hidden is None:
        hidden = _WINDOW_HIDDEN()
    time.sleep(0.6)
    cmd = [pythonw_exe(), os.path.join(HERE, "tabdeck.py"), "--open", "--restart"] + (["--tray"] if hidden else [])
    try:
        subprocess.Popen(cmd, cwd=HERE, close_fds=True,
                         creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
    except OSError as e:
        print("[%s] riavvio non riuscito: %s" % (time.strftime("%H:%M:%S"), e))
        return
    quit_tabdeck()


def stop_server(srv):
    try:
        srv.shutdown()
        srv.server_close()
    except Exception:  # noqa: BLE001
        pass


_INSTANCE = _SHOW_EVENT = None   # mutex "una sola istanza" + evento "mostra la finestra" (aperti finche' il processo vive)
_ik = ctypes.WinDLL("kernel32", use_last_error=True)
_ik.CreateMutexW.restype = _ik.CreateEventW.restype = ctypes.c_void_p
_ik.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
_ik.CreateEventW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_wchar_p]
_ik.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
_ik.SetEvent.argtypes = _ik.CloseHandle.argtypes = [ctypes.c_void_p]


def single_instance(port, restart=False, wait=15.0):
    """True se questa e' l'unica istanza di TabDeck su questa porta. Mutex con nome per porta, cosi'
    una copia di prova su un'altra porta puo' girare insieme. Se e' gia' preso:
    - avvio normale (icona cliccata di nuovo): chiede alla prima istanza di mostrare la finestra ed esce subito;
    - restart (/restart, aggiornamento): la vecchia istanza sta uscendo, la si aspetta fino a `wait` secondi."""
    global _INSTANCE, _SHOW_EVENT
    ev = _ik.CreateEventW(None, False, False, "Local\\TabDeck-%d-show" % port)   # auto-reset
    h = _ik.CreateMutexW(None, True, "Local\\TabDeck-%d" % port)
    if not h:
        _SHOW_EVENT = ev
        return True                        # mutex non disponibile: meglio partire che bloccarsi
    if ctypes.get_last_error() != 183:     # ERROR_ALREADY_EXISTS: altrimenti il mutex e' nostro
        _INSTANCE, _SHOW_EVENT = h, ev
        return True
    if not restart:
        if ev:
            _ik.SetEvent(ev)
            _ik.CloseHandle(ev)
        _ik.CloseHandle(h)
        return False
    # 0 = WAIT_OBJECT_0, 0x80 = WAIT_ABANDONED (la vecchia istanza e' terminata senza rilasciarlo)
    if _ik.WaitForSingleObject(h, int(wait * 1000)) in (0, 0x80):
        _INSTANCE, _SHOW_EVENT = h, ev
        return True
    return False


def show_requested():
    """True (una volta) se un secondo avvio ha chiesto di mostrare la finestra."""
    return bool(_SHOW_EVENT) and _ik.WaitForSingleObject(_SHOW_EVENT, 0) == 0


def parse_flags(argv):
    f = {"open": "--open" in argv, "tray": "--tray" in argv, "restart": "--restart" in argv, "host": None}
    if "--host" in argv:
        i = argv.index("--host") + 1
        if i >= len(argv) or argv[i].startswith("--"):
            sys.exit("Uso: python tabdeck.py [--open] [--tray] [--restart] [--host IP]")
        f["host"] = argv[i]
    return f


LOG_FILE = os.path.join(DATA_DIR, "tabdeck.log")
LOG_MAX = 256 * 1024


def cap_log(path=LOG_FILE, limit=LOG_MAX):
    """Registro oltre `limit`: tiene l'ultima meta' (tagliata a inizio riga)."""
    try:
        if os.path.getsize(path) <= limit:
            return
        with open(path, "rb") as f:
            f.seek(-(limit // 2), os.SEEK_END)
            tail = f.read()
        nl = tail.find(b"\n")
        with open(path, "wb") as f:
            f.write(tail[nl + 1:] if nl >= 0 else tail)
    except OSError:
        pass


def setup_log(path=LOG_FILE):
    """Senza console (pythonw) print va nel file data/tabdeck.log. Con la console (tabdeck.bat) non cambia nulla."""
    if sys.stdout is not None and os.path.basename(sys.executable).lower() != "pythonw.exe":
        return
    cap_log(path)
    try:
        f = open(path, "a", encoding="utf-8", errors="replace", buffering=1)
    except OSError:
        return
    sys.stdout = sys.stderr = f


def log_tail(n=200, path=LOG_FILE):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return [l.rstrip("\n") for l in collections.deque(f, n)]
    except OSError:
        return []


def main():
    flags = parse_flags(sys.argv[1:])
    global PORT, ALLOWED_NETS, ADB_PATH
    cfg = load_config(CONFIG_FILE)
    PORT, ALLOWED_NETS, ADB_PATH = cfg["port"], cfg["allowed_nets"], cfg["adb"]
    if not single_instance(PORT, flags["restart"]):
        print("TabDeck e' gia' in esecuzione (porta %d): mostro la sua finestra." % PORT)
        sys.exit(3)
    setup_log()
    global DEVICES
    DEVICES = devices.DeviceStore(os.path.join(DATA_DIR, "devices.json"),
                                  fresh_install=not os.path.exists(TOKEN_FILE))   # prima installazione: approvazione attiva
    token = load_token()

    def warm_icons():  # prepara in cache le icone di browser e launcher
        for b in BUTTONS:
            src = button_icon_src(b) if b.get("group") and installed(b) else None
            if src:
                app_icon(icon_key(src))
    threading.Thread(target=warm_icons, daemon=True).start()
    yt_start()
    threading.Thread(target=_ctrl_watch, daemon=True).start()
    threading.Thread(target=_remap_thread, daemon=True).start()
    DISCORD.start()
    threading.Thread(target=_update_auto_check, daemon=True).start()
    sync_uninstall_version(VERSION)
    threading.Thread(target=_migrate_startup_bg, daemon=True).start()
    # Segnale per updater.py: questa versione si e' avviata (non dipende dalla rete)
    try:
        with open(os.path.join(DATA_DIR, "update_ok.json"), "w", encoding="utf-8") as f:
            json.dump({"version": VERSION, "pid": os.getpid(), "t": time.time()}, f)
    except OSError:
        pass
    print("[%s] TabDeck %s avviato. Se la rete cade, il server si ricollega da solo." % (time.strftime("%H:%M:%S"), VERSION))
    try:
        import gui
        import tray
    except ImportError as e:     # Python senza tkinter: si resta col server e basta (come prima)
        print("finestra non disponibile (%s): solo server" % e)
        return serve_loop(flags)
    threading.Thread(target=serve_loop, args=(flags,), name="server", daemon=True).start()
    gui.run(_App(flags, tray))


class _App:
    """Quello che serve alla finestra (gui.py), senza che gui.py importi tabdeck."""
    def __init__(self, flags, tray_mod):
        self.version, self.start_hidden = VERSION, flags["tray"]
        self.icon_path = os.path.join(HERE, "tabdeck.ico")
        self.devices, self._tray = DEVICES, tray_mod
        self.qr_matrix = __import__("tdqr").qr_matrix
        self.log_tail, self.show_requested, self.rotate_token = log_tail, show_requested, rotate_token
        self.hidden = flags["tray"]       # aggiornato dalla finestra (letto dal riavvio, anche da altri thread)
        global _WINDOW_HIDDEN
        _WINDOW_HIDDEN = lambda: self.hidden

    def status(self):
        st = dict(STATUS)
        st["update"] = UPD["latest"] if UPD["latest"] and parse_version(UPD["latest"]) > parse_version(VERSION) else None
        return st

    def pair_url(self):
        ip = STATUS.get("ip") if STATUS.get("state") == "listening" else None
        return "http://%s:%d/?t=%s" % (ip, PORT, SERVER.token) if ip and SERVER is not None else None

    def make_tray(self, on_open, on_restart, on_quit):
        global _TRAY
        try:
            _TRAY = self._tray.Tray(self.icon_path, "TabDeck %s" % VERSION, on_open, on_restart, on_quit)
            _TRAY.start()
        except Exception as e:
            print("icona di notifica non disponibile: %s" % e)
            _TRAY = None
        return _TRAY

    def restart(self, hidden):
        threading.Thread(target=restart_tabdeck, args=(hidden,), daemon=True).start()

    def quit(self):
        quit_tabdeck()


def serve_loop(flags):
    """Il ciclo di sempre (thread "server"): ascolta solo sulla rete consentita, apre la pagina sul tablet via adb."""
    fixed = flags["host"]
    srv = th = None
    host = url = None
    adb = find_adb() if flags["open"] else None
    if flags["open"] and not adb:
        print("adb non trovato: la pagina andra' aperta a mano sul tablet")
    seen, opened, warned = set(), {}, None     # tablet collegati via adb; seriale -> ultimo indirizzo aperto
    try:
        while not _STOP.is_set():
            ip = fixed or lan_ip()
            alive = th is not None and th.is_alive()
            # SICUREZZA: si ascolta solo sulla rete dell'hotspot (ALLOWED_NETS). Su un altro Wi-Fi (bar, albergo)
            # la porta resta chiusa anche se il firewall venisse cambiato. --host IP scavalca il controllo.
            if (ip == "127.0.0.1" or not ip.startswith(ALLOWED_NETS)) and not fixed:
                if host is not None or ip != warned:
                    print("[%s] %s, attendo l'hotspot..." % (time.strftime("%H:%M:%S"),
                                                              "rete assente" if ip == "127.0.0.1" else "rete non consentita (%s)" % ip))
                    warned = ip
                if host is not None:
                    stop_server(srv)
                    srv = th = host = None
                STATUS.update(state="blocked" if ip != "127.0.0.1" else "waiting", ip=None if ip == "127.0.0.1" else ip,
                              port=PORT)
            elif ip != host or not alive:
                if srv is not None:
                    stop_server(srv)
                token = load_token()     # "Nuovo link" puo' averlo cambiato
                try:
                    srv, th = start_server(ip, token)
                except OSError as e:
                    print("[%s] impossibile ascoltare su %s: %s (riprovo)" % (time.strftime("%H:%M:%S"), ip, e))
                    srv = th = host = None
                else:
                    host = ip
                    url = "http://%s:%d/?t=%s" % (host, PORT, token)
                    print("[%s] TabDeck in ascolto su %s:%d" % (time.strftime("%H:%M:%S"), host, PORT))   # niente token nel registro
            if host is not None:
                STATUS.update(state="listening", ip=host, port=PORT)
            # apertura automatica: quando il tablet si collega (cavo USB) o quando cambia l'indirizzo del PC
            if adb and host is not None:
                devs = adb_devices(adb)
                for d in devs - seen:
                    print("[%s] tablet collegato: %s" % (time.strftime("%H:%M:%S"), d))
                if SERVER is not None:
                    url = "http://%s:%d/?t=%s" % (host, PORT, SERVER.token)   # "Nuovo link": riapre il tablet col token nuovo
                for d in devs:
                    if opened.get(d) != url:
                        opened[d] = url
                        open_on_tablet(adb, url, d)
                for d in seen - devs:
                    opened.pop(d, None)   # ricollegandolo, la pagina si riapre
                seen = devs
                STATUS["adb"] = sorted(devs)
            if DEVICES is not None:
                DEVICES.flush()          # "visto alle" sul disco al massimo ogni 60 s
            _STOP.wait(3)
    except KeyboardInterrupt:
        pass
    finally:
        if srv is not None:
            stop_server(srv)


if __name__ == "__main__":
    main()
