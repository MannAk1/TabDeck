"""Storico delle modifiche: una copia piccola di layout.json e settings.json fatta PRIMA di ogni modifica,
per poterla annullare dalla finestra sul PC. Solo libreria standard; non importa tabdeck."""
import json
import os
import time

KEEP = 30


def _files(dirpath):
    try:
        names = [n for n in os.listdir(dirpath) if n.endswith(".json") and n[:-5].replace("_", "").isdigit()]
    except OSError:
        return []
    return sorted(names, key=lambda n: [int(x) for x in n[:-5].split("_")], reverse=True)


def _read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            e = json.load(fh)
    except (OSError, ValueError):
        return None
    if isinstance(e, dict) and isinstance(e.get("label"), str) and isinstance(e.get("t"), (int, float)):
        return e
    return None


def _drop(path):
    try:
        os.remove(path)
    except OSError:
        pass


def entries(dirpath):
    """Copie valide, la piu' recente per prima (ognuna con "file"). Quelle rovinate si tolgono."""
    out = []
    for n in _files(dirpath):
        p = os.path.join(dirpath, n)
        e = _read(p)
        if e is None:
            _drop(p)
            continue
        e["file"] = p
        out.append(e)
    return out


def save(dirpath, label, layout, settings, keep=KEEP, now=time.time):
    os.makedirs(dirpath, exist_ok=True)
    t = now()
    base, n = str(int(t * 1000)), 0
    name = base + ".json"
    while os.path.exists(os.path.join(dirpath, name)):
        n += 1
        name = "%s_%d.json" % (base, n)
    path = os.path.join(dirpath, name)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"t": t, "label": label, "layout": layout, "settings": settings}, fh)
    os.replace(tmp, path)
    for old in _files(dirpath)[keep:]:
        _drop(os.path.join(dirpath, old))
    return path


def latest(dirpath):
    es = entries(dirpath)
    return es[0] if es else None


def pop(dirpath):
    e = latest(dirpath)
    if e is not None:
        _drop(e["file"])
    return e
