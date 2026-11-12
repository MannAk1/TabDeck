"""TabDeck - YouTube: ricerca senza chiave, coda del player e server locale per la pagina del player.

La pagina del player (web/player.html) gira nel browser predefinito del PC su http://localhost:<porta> e usa il
player incorporato "nocookie" di YouTube: con l'host normale i video musicali ufficiali danno errore 150.
Il tablet non parla mai con questo server: comanda il player tramite il server principale di TabDeck.
"""
import json
import re
import threading
import time
import urllib.parse
import urllib.request

ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_DATA_RE = re.compile(r"var ytInitialData = (\{.*?\});</script>", re.S)
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:140.0) Gecko/20100101 Firefox/140.0",
    "Accept-Language": "it-IT,it;q=0.9",
    "Cookie": "SOCS=CAI",   # salta la pagina del consenso ai cookie (UE)
}
MAX_TEXT = 200


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
                if ID_RE.match(vid):
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


# ---------------------------------------------------------------- player: coda e stato
_YT_STATES = {1: "playing", 2: "paused", 3: "buffering", -1: "idle", 5: "idle", 0: "idle"}
_SKIP_CODES = (100, 101, 150)   # video rimosso / non incorporabile: si passa al prossimo
OPEN_S = 5.0                    # senza richieste della pagina per piu' di cosi' = player chiuso
NOTICE_S = 8.0
HISTORY_MAX = 20


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

    # --- interni (lock gia' preso)
    def _open(self):
        return self.last_seen is not None and self.clock() - self.last_seen < OPEN_S

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
            if self.notice and self.clock() - self.notice["t"] > NOTICE_S:
                self.notice = None
            op = self._open()
            st = "closed" if not op else ("ad" if self.ad and self.state == "playing" else self.state)
            return {"cur": self.cur, "queue": list(self.queue), "state": st, "pos": self.pos, "dur": self.dur,
                    "vol": self.vol, "open": op, "notice": dict(self.notice) if self.notice else None}

    def is_open(self):
        with self.lock:
            return self._open()

    # --- dalla pagina del player
    def poll(self):
        with self.lock:
            if not self._open():   # pagina (ri)aperta: riprende il video di prima da dove era
                self.out = [c for c in self.out if c["a"] not in ("load", "seek", "vol")]
                pre = [{"a": "vol", "v": self.vol}] if self.vol != 100 else []
                if self.cur is not None and self.state != "idle":
                    pre.append({"a": "load", "id": self.cur["id"], "pos": float(self.pos)})
                self.out = pre + self.out
            self.last_seen = self.clock()
            out, self.out = self.out, []
            return out

    def report(self, ev):
        with self.lock:
            t = ev.get("t")
            if t == "state":
                self.state = _YT_STATES.get(ev.get("s"), self.state)
                self.ad = bool(ev.get("ad"))
                for k in ("pos", "dur"):
                    v = ev.get(k)
                    if isinstance(v, (int, float)) and v >= 0:
                        setattr(self, k, float(v))
            elif t == "ended":
                self._next()
            elif t == "error":
                code = ev.get("code")
                if code in _SKIP_CODES and self.cur is not None:
                    self.notice = {"msg": "non riproducibile qui", "id": self.cur["id"],
                                   "title": self.cur.get("title", ""), "t": self.clock()}
                    self._next()
