"""TabDeck - YouTube: ricerca senza chiave, coda del player e server locale per la pagina del player.

La pagina del player (web/player.html) gira nel browser predefinito del PC su http://localhost:<porta> e usa il
player incorporato "nocookie" di YouTube: con l'host normale i video musicali ufficiali danno errore 150.
Il tablet non parla mai con questo server: comanda il player tramite il server principale di TabDeck.
"""
import json
import re
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
