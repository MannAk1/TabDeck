"""TabDeck - dispositivi collegati e approvazione dei nuovi.

Ogni browser riceve un ID casuale (128 bit). Con l'approvazione attiva, un ID sconosciuto con il token giusto resta
"in attesa" con un codice di 4 cifre finche' non lo si approva dalla finestra sul PC. Limiti contro chi avesse il
link: una richiesta per IP, codici validi 2 minuti, Rifiuta blocca IP e ID per 10 minuti, 3 rifiuti in 10 minuti
sospendono le richieste per 30 minuti. Sul disco (data/devices.json) solo l'interruttore e i dispositivi approvati;
attese e blocchi vivono in memoria.
"""
import collections
import json
import os
import re
import secrets
import threading
import time

PENDING_TTL = 120          # un codice non approvato scade dopo 2 minuti
REFUSE_BLOCK = 600         # Rifiuta: IP e ID bloccati 10 minuti
LOCK_WINDOW, LOCK_COUNT, LOCK_TIME = 600, 3, 1800   # 3 rifiuti in 10 minuti -> richieste sospese 30 minuti
LAST_FLUSH = 60            # "visto alle" si salva al massimo ogni 60 s

_ID_RE = re.compile(r"^[0-9a-f]{32}$")


def new_id():
    return secrets.token_hex(16)


def valid_id(s):
    return isinstance(s, str) and bool(_ID_RE.match(s))


def ua_name(ua):
    ua = ua or ""
    if "iPhone" in ua:
        return "iPhone"
    if "iPad" in ua:
        return "iPad"
    m = re.search(r"Android [\d.]+; ([^;)]+?)(?: Build/|\))", ua)
    if m and m.group(1).strip() not in ("K", "wv"):
        return m.group(1).strip()
    if "Android" in ua:
        return "Android"
    if "Windows" in ua:
        return "PC Windows"
    if "Macintosh" in ua:
        return "Mac"
    return "Dispositivo"


class DeviceStore:
    def __init__(self, path, fresh_install, now=time.time):
        self.path, self.now = path, now
        self.on_change = None
        self._lock = threading.RLock()
        self.require, self._dev = bool(fresh_install), {}
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            self.require = bool(data.get("require", fresh_install))
            for i, d in (data.get("devices") or {}).items():
                if valid_id(i) and isinstance(d, dict):
                    self._dev[i] = {k: d.get(k) for k in ("name", "ua", "ip", "added", "last")}
        except (OSError, ValueError, AttributeError):
            self.require = bool(fresh_install)
        self._pend = {}            # ip -> {id, code, t, name, ua}
        self._block_ip, self._block_id = {}, {}
        self._refusals = collections.deque()
        self.locked_until = 0.0
        self._last_dirty, self._wrote = False, self.now()

    # --- salvataggio ---
    def _save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"require": self.require, "devices": self._dev}, f, indent=1)
        os.replace(tmp, self.path)
        self._last_dirty, self._wrote = False, self.now()

    def _changed(self):
        self._save()
        cb = self.on_change
        if cb:
            try:
                cb()
            except Exception:
                pass

    def flush(self, force=False):
        with self._lock:
            if self._last_dirty and (force or self.now() - self._wrote >= LAST_FLUSH):
                self._save()

    # --- decisione ---
    def _purge(self, t):
        for ip in [ip for ip, p in self._pend.items() if t - p["t"] > PENDING_TTL]:
            del self._pend[ip]
        for blk in (self._block_ip, self._block_id):
            for k in [k for k, u in blk.items() if u <= t]:
                del blk[k]
        while self._refusals and t - self._refusals[0] > LOCK_WINDOW:
            self._refusals.popleft()

    def access(self, dev_id, ip, ua):
        """-> (decisione, id). decisione: ok | pending | refused | locked."""
        with self._lock:
            if not valid_id(dev_id):
                dev_id = new_id()
            t = self.now()
            d = self._dev.get(dev_id)
            if d is not None:
                d["last"], d["ip"] = t, ip
                self._last_dirty = True
                return "ok", dev_id
            if not self.require:
                self._dev[dev_id] = {"name": ua_name(ua), "ua": (ua or "")[:200], "ip": ip, "added": t, "last": t}
                self._changed()
                return "ok", dev_id
            self._purge(t)
            if dev_id in self._block_id or ip in self._block_ip:
                return "refused", dev_id
            if self.locked_until > t:
                return "locked", dev_id
            p = self._pend.get(ip)
            if p is None:
                self._pend[ip] = {"id": dev_id, "code": "%04d" % secrets.randbelow(10000), "t": t,
                                  "name": ua_name(ua), "ua": (ua or "")[:200]}
                self._changed()
            elif p["id"] != dev_id:
                p["id"] = dev_id          # stessa richiesta (stesso IP): stesso codice, nessun nuovo avviso
            return "pending", dev_id

    # --- azioni dalla finestra sul PC ---
    def _pending_of(self, dev_id):
        for ip, p in self._pend.items():
            if p["id"] == dev_id:
                return ip, p
        return None, None

    def approve(self, dev_id):
        with self._lock:
            ip, p = self._pending_of(dev_id)
            if p is None:
                return False
            del self._pend[ip]
            t = self.now()
            self._dev[dev_id] = {"name": p["name"], "ua": p["ua"], "ip": ip, "added": t, "last": t}
            self._changed()
            return True

    def refuse(self, dev_id):
        with self._lock:
            ip, p = self._pending_of(dev_id)
            if p is None:
                return False
            del self._pend[ip]
            t = self.now()
            self._block_ip[ip] = self._block_id[dev_id] = t + REFUSE_BLOCK
            self._refusals.append(t)
            self._purge(t)
            if len(self._refusals) >= LOCK_COUNT:
                self.locked_until = t + LOCK_TIME
            self._changed()
            return True

    def resume(self):
        with self._lock:
            self.locked_until = 0.0
            self._refusals.clear()
            self._changed()

    def remove(self, dev_id):
        with self._lock:
            if self._dev.pop(dev_id, None) is not None:
                self._changed()

    def rename(self, dev_id, name):
        with self._lock:
            d = self._dev.get(dev_id)
            name = (name or "").strip()[:40]
            if d is not None and name:
                d["name"] = name
                self._changed()

    def set_require(self, on):
        with self._lock:
            self.require = bool(on)
            self._changed()

    # --- letture ---
    def is_approved(self, dev_id):
        with self._lock:
            return valid_id(dev_id) and dev_id in self._dev

    def code_of(self, dev_id):
        with self._lock:
            self._purge(self.now())
            _, p = self._pending_of(dev_id)
            return p["code"] if p else None

    def pending(self):
        with self._lock:
            self._purge(self.now())
            return [{"id": p["id"], "name": p["name"], "ip": ip, "code": p["code"], "t": p["t"]}
                    for ip, p in sorted(self._pend.items(), key=lambda kv: kv[1]["t"])]

    def approved(self):
        with self._lock:
            return [{"id": i, "name": d["name"], "ip": d["ip"], "last": d["last"] or 0}
                    for i, d in self._dev.items()]
