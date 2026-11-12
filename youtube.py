"""TabDeck - YouTube: ricerca senza chiave, coda del player e server locale per la pagina del player.

La pagina del player (web/player.html) gira nel browser predefinito del PC su http://localhost:<porta> e usa il
player incorporato "nocookie" di YouTube: con l'host normale i video musicali ufficiali danno errore 150.
Il tablet non parla mai con questo server: comanda il player tramite il server principale di TabDeck.
"""
import hmac
import json
import os
import re
import secrets
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}\Z")
_DATA_RE = re.compile(r"var ytInitialData = (\{.*?\});</script>", re.S)
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:140.0) Gecko/20100101 Firefox/140.0",
    "Accept-Language": "it-IT,it;q=0.9",
    "Cookie": "SOCS=CAI",   # salta la pagina del consenso ai cookie (UE)
}
MAX_TEXT = 200


def valid_id(s):
    return isinstance(s, str) and bool(ID_RE.match(s))


class SearchError(Exception):
    pass


def _runs(o):
    return "".join(r.get("text", "") for r in (o or {}).get("runs", []))[:MAX_TEXT]


def parse_results(html, limit=20):
    """Video dalla pagina dei risultati di YouTube: [{id, title, channel, dur}] nell'ordine della pagina."""
    m = _DATA_RE.search(html)
    if not m:
        raise SearchError("dati dei risultati non trovati nella pagina")
    try:
        data = json.loads(m.group(1))
    except ValueError as e:
        raise SearchError("dati dei risultati non leggibili: %s" % e)
    out, stack = [], [data]
    while stack and len(out) < limit:
        o = stack.pop()
        if isinstance(o, dict):
            v = o.get("videoRenderer")
            if isinstance(v, dict):
                vid = v.get("videoId") or ""
                if valid_id(vid):
                    out.append({"id": vid, "title": _runs(v.get("title")), "channel": _runs(v.get("ownerText")),
                                "dur": (v.get("lengthText") or {}).get("simpleText", "")[:16]})
                continue
            stack.extend(reversed(list(o.values())))
        elif isinstance(o, list):
            stack.extend(reversed(o))
    return out


def search(q, timeout=8.0):
    url = "https://www.youtube.com/results?" + urllib.parse.urlencode({"search_query": q, "hl": "it"})
    try:
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            html = r.read().decode("utf-8", "replace")
    except (OSError, ValueError) as e:
        raise SearchError("YouTube non raggiungibile: %s" % e)
    return parse_results(html)


def parse_suggest(text, limit=8):
    """Suggerimenti dalla risposta JSONP di YouTube: window.google.ac.h(["q", [["testo", ...], ...], {...}])."""
    a, b = text.find("("), text.rfind(")")
    if a < 0 or b <= a:
        return []
    try:
        data = json.loads(text[a + 1:b])
        items = data[1]
        out = [it[0] for it in items if isinstance(it, list) and it and isinstance(it[0], str)]
    except (ValueError, IndexError, TypeError):
        return []
    return [s[:MAX_TEXT] for s in out[:limit]]


def suggest(q, timeout=4.0):
    """Fino a 8 suggerimenti per la ricerca; [] se il servizio non risponde (la ricerca normale funziona lo stesso)."""
    url = "https://suggestqueries-clients6.youtube.com/complete/search?" + urllib.parse.urlencode(
        {"client": "youtube", "ds": "yt", "hl": "it", "q": q})
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _HEADERS["User-Agent"]})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return parse_suggest(r.read().decode("utf-8", "replace"))
    except (OSError, ValueError):
        return []


# ---------------------------------------------------------------- player: coda e stato
# -1 (non avviato) arriva a ogni caricamento: non cambia lo stato, altrimenti un "+" in quel momento sostituirebbe
# il video che sta partendo. 5 = video pronto ma fermo (ripresa di un video in pausa).
_YT_STATES = {1: "playing", 2: "paused", 3: "buffering", 5: "paused"}
_SKIP_CODES = (100, 101, 150)   # video rimosso / non incorporabile: si passa al prossimo
OPEN_S = 5.0                    # senza richieste della pagina per piu' di cosi' = player chiuso
NOTICE_S = 8.0
HISTORY_MAX = 20
OPENING_S = 15.0                # il browser ci mette qualche secondo ad aprire la pagina: intanto conta come aperta
_NO_PAGE = object()


class Player:
    """Stato del player sul PC. Il tablet lo comanda (play_now, enqueue, ...), la pagina chiede i comandi (poll)
    e riferisce cosa sta facendo (report). Tutto in memoria."""

    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.lock = threading.Lock()
        self.cur = None
        self.queue = []
        self.history = []
        self.state = "idle"
        self.ad = False
        self.pos = 0.0
        self.dur = 0.0
        self.vol = 100
        self.last_seen = None
        self.notice = None
        self.out = []
        self.page = _NO_PAGE        # id dell'ultima pagina del player che ha chiesto i comandi
        self.old_pages = set()      # pagine piu' vecchie (ricaricate o aperte due volte): devono fermarsi
        self.opening_until = 0.0

    # --- interni (lock gia' preso)
    def _open(self):
        now = self.clock()
        return (self.last_seen is not None and now - self.last_seen < OPEN_S) or now < self.opening_until

    def _send(self, cmd):
        if cmd["a"] in ("load", "seek"):   # conta solo l'ultimo: tocchi rapidi non accodano caricamenti vecchi
            drop = ("load", "seek") if cmd["a"] == "load" else ("seek",)
            self.out = [c for c in self.out if c["a"] not in drop]
        elif cmd["a"] in ("play", "pause"):
            self.out = [c for c in self.out if c["a"] not in ("play", "pause")]
        elif cmd["a"] == "vol":
            self.out = [c for c in self.out if c["a"] != "vol"]
        self.out.append(cmd)

    def _start(self, item, keep_history=True):
        if self.cur is not None and keep_history:
            self.history = (self.history + [self.cur])[-HISTORY_MAX:]
        self.cur, self.pos, self.dur, self.ad = dict(item), 0.0, 0.0, False
        self.state = "buffering"
        self._send({"a": "load", "id": item["id"], "pos": 0.0})

    def _next(self):
        if self.queue:
            self._start(self.queue.pop(0))
        else:
            self.state, self.pos = "idle", 0.0

    # --- dal tablet
    def play_now(self, item):
        with self.lock:
            self._start(item)

    def enqueue(self, item):
        with self.lock:
            if self.cur is None or (self.state == "idle" and not self.queue):
                self._start(item)
                return True
            self.queue.append(dict(item))
            return False

    def move_up(self, i):
        with self.lock:
            if 0 < i < len(self.queue):
                self.queue[i - 1], self.queue[i] = self.queue[i], self.queue[i - 1]

    def remove(self, i):
        with self.lock:
            if 0 <= i < len(self.queue):
                del self.queue[i]

    def next(self):
        with self.lock:
            self._next()

    def prev(self):
        with self.lock:
            if self.cur is None:
                return
            if self.pos > 3 or not self.history:
                self.pos = 0.0
                self._send({"a": "seek", "s": 0.0})
                return
            self.queue.insert(0, self.cur)
            self._start(self.history.pop(), keep_history=False)

    def toggle(self):
        with self.lock:
            if self.cur is None:
                return
            self._send({"a": "pause"} if self.state in ("playing", "buffering") else {"a": "play"})

    def seek(self, s):
        with self.lock:
            s = max(0.0, float(s))
            if self.dur > 0:
                s = min(s, self.dur)
            self.pos = s
            self._send({"a": "seek", "s": s})

    def volume(self, v):
        with self.lock:
            self.vol = max(0, min(100, int(v)))
            self._send({"a": "vol", "v": self.vol})

    def snapshot(self):
        with self.lock:
            if self.notice and self.notice.get("kind") != "blocked" and self.clock() - self.notice["t"] > NOTICE_S:
                self.notice = None
            op = self._open()
            st = "closed" if not op else ("ad" if self.ad and self.state == "playing" else self.state)
            return {"cur": self.cur, "queue": list(self.queue), "state": st, "pos": self.pos, "dur": self.dur,
                    "vol": self.vol, "open": op, "notice": dict(self.notice) if self.notice else None}

    def is_open(self):
        with self.lock:
            return self._open()

    def mark_opening(self, secs=OPENING_S):
        """La pagina e' appena stata aperta nel browser: per un po' non va riaperta."""
        with self.lock:
            self.opening_until = self.clock() + secs

    # --- dalla pagina del player
    def poll(self, page=None):
        """Comandi per la pagina. page = id casuale della pagina: una pagina nuova (aperta o ricaricata) riprende il
        video di prima; le pagine piu' vecchie ricevono "stop", cosi' due schede non si dividono i comandi."""
        with self.lock:
            if page != self.page:
                if page in self.old_pages:
                    return [{"a": "stop"}]
                if self.page is not _NO_PAGE:
                    self.old_pages.add(self.page)
                self.page = page
                self.out = [c for c in self.out if c["a"] not in ("load", "seek", "vol", "play", "pause")]
                pre = [{"a": "vol", "v": self.vol}] if self.vol != 100 else []
                if self.cur is not None and self.state != "idle":
                    cmd = {"a": "load", "id": self.cur["id"], "pos": float(self.pos)}
                    if self.state == "paused":
                        cmd["cue"] = True   # era in pausa: pronto ma fermo
                    pre.append(cmd)
                self.out = pre + self.out
            self.last_seen = self.clock()
            self.opening_until = 0.0
            out, self.out = self.out, []
            return out

    def report(self, ev):
        with self.lock:
            t = ev.get("t")
            if t in ("ended", "error", "blocked") and ev.get("id") and (self.cur is None or ev["id"] != self.cur["id"]):
                return   # evento in ritardo del video precedente
            if t == "state":
                self.state = _YT_STATES.get(ev.get("s"), self.state)
                if self.state == "playing" and self.notice and self.notice.get("kind") == "blocked":
                    self.notice = None
                self.ad = bool(ev.get("ad"))
                for k in ("pos", "dur"):
                    v = ev.get(k)
                    if isinstance(v, (int, float)) and v >= 0:
                        setattr(self, k, float(v))
            elif t == "blocked" and self.cur is not None:
                # il browser non lascia partire il video da solo (Firefox: "Riproduzione automatica")
                self.state = "blocked"
                self.notice = {"kind": "blocked", "msg": "il browser blocca l'avvio automatico",
                               "id": self.cur["id"], "title": self.cur.get("title", ""), "t": self.clock()}
            elif t == "ended":
                self._next()
            elif t == "error":
                code = ev.get("code")
                if code in _SKIP_CODES and self.cur is not None:
                    self.notice = {"kind": "embed", "msg": "non riproducibile qui", "id": self.cur["id"],
                                   "title": self.cur.get("title", ""), "t": self.clock()}
                    self._next()


# ---------------------------------------------------------------- server locale per la pagina del player
MAX_EV = 4096


def player_url(port, secret):
    return "http://localhost:%d/player?k=%s" % (port, secret)


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body=b"", ctype="text/plain; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _route(self):
        """Percorso se Host e segreto sono giusti, altrimenti None (risposta 403 gia' inviata)."""
        srv = self.server
        # SICUREZZA: solo "localhost:<porta>" (niente DNS rebinding) e solo con il segreto della pagina:
        # un altro sito aperto nel browser non puo' comandare il player.
        u = urllib.parse.urlparse(self.path)
        k = (urllib.parse.parse_qs(u.query).get("k") or [""])[0]
        if self.headers.get("Host") != "localhost:%d" % srv.server_address[1] or \
                not hmac.compare_digest(k.encode(), srv.secret.encode()):
            self._send(403, b"403 Forbidden")
            return None
        return u.path

    def do_GET(self):
        path = self._route()
        if path is None:
            return
        if path == "/player":
            with open(os.path.join(self.server.web_dir, "player.html"), "rb") as f:
                return self._send(200, f.read(), "text/html; charset=utf-8")
        if path == "/pcmd":
            page = (urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("n") or [""])[0][:40]
            return self._send(200, json.dumps(self.server.player.poll(page)).encode(), "application/json")
        self._send(404, b"404")

    def do_POST(self):
        path = self._route()
        if path is None:
            return
        if path != "/pev":
            return self._send(404, b"404")
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = -1
        if n < 0 or n > MAX_EV:
            return self._send(400, b"troppo grande")
        try:
            ev = json.loads(self.rfile.read(n).decode("utf-8"))
        except ValueError:
            return self._send(400, b"json non valido")
        if not isinstance(ev, dict):
            return self._send(400, b"json non valido")
        self.server.player.report(ev)
        self._send(204)


def start_player_server(port, player, web_dir):
    """Avvia il server della pagina del player su 127.0.0.1:<port>. Restituisce (server, segreto)."""
    srv = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    srv.daemon_threads = True
    srv.player, srv.web_dir, srv.secret = player, web_dir, secrets.token_urlsafe(18)
    threading.Thread(target=srv.serve_forever, name="yt-player", daemon=True).start()
    return srv, srv.secret
