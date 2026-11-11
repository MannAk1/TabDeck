"""Aggiornamento di TabDeck (processo separato, solo libreria standard).

TabDeck scarica lo zip del rilascio da GitHub, lo controlla, copia questo file in cache\\update\\updater_run.py
e lo avvia, poi si chiude. Qui:
  1. si aspetta che il vecchio TabDeck sia chiuso;
  2. si copia il codice attuale in backup\\v<vecchia>\\ (si tengono le ultime 3 copie);
  3. si estrae lo zip sopra la cartella (MAI data\\, cache\\, backup\\; nessun file viene cancellato);
  4. si avvia il nuovo TabDeck e si aspetta che scriva data\\update_ok.json con la nuova versione;
  5. se non parte entro 45 s: lo si chiude, si rimette la copia di sicurezza e si riavvia la versione vecchia.
Il risultato va in data\\update_result.json (mostrato nelle impostazioni) e il dettaglio in cache\\update.log.

Uso:  python updater.py apply ZIP --root DIR --pid PID --old 1.0.0 --new 1.0.1
      python updater.py rollback --root DIR --pid PID --old 1.0.1
"""
import ctypes
import json
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile

MAX_ZIP = 20 * 1024 * 1024
KEEP = ("data", "cache", "backup", "__pycache__", ".git", ".superpowers")   # mai toccate da un aggiornamento
BACKUPS = 3
OK_TIMEOUT = 45


class UpdateError(Exception):
    pass


_DEVICES = re.compile(r"^(con|prn|aux|nul|com\d|lpt\d)(\..*)?$")


def _norm(part):
    """Come Windows vede un nome: senza maiuscole e senza punti/spazi finali ("Data." == "data")."""
    return part.lower().rstrip(". ")


def _bad_name(name):
    n = name.replace("\\", "/")
    parts = n.split("/")
    return (n.startswith("/") or ":" in n
            or any(_norm(p) == ".." or p == ".." or _DEVICES.match(_norm(p)) for p in parts if p))


def check_zip(zip_path):
    """Controlla lo zip del rilascio prima di toccare qualsiasi file; restituisce la cartella principale ("X/")."""
    if os.path.getsize(zip_path) > MAX_ZIP:
        raise UpdateError("zip troppo grande")
    try:
        with zipfile.ZipFile(zip_path) as z:
            names = [i.filename for i in z.infolist()]
            if z.testzip() is not None:
                raise UpdateError("zip danneggiato")
    except zipfile.BadZipFile:
        raise UpdateError("il file scaricato non e' uno zip")
    if not names:
        raise UpdateError("zip vuoto")
    for n in names:
        if _bad_name(n):
            raise UpdateError("percorso non valido nello zip: %s" % n)
    prefix = names[0].split("/")[0] + "/"
    for n in names:
        if not n.startswith(prefix):
            raise UpdateError("lo zip deve contenere una sola cartella")
        rest = n[len(prefix):]
        if _norm(rest.split("/")[0]) in KEEP:
            raise UpdateError("lo zip contiene una cartella riservata: %s" % n)
    if prefix + "tabdeck.py" not in names:
        raise UpdateError("lo zip non contiene tabdeck.py")
    return prefix


def code_files(root):
    """Percorsi relativi (con "/") di tutto il codice: tutto tranne le cartelle in KEEP."""
    out = []
    for dirpath, dirs, files in os.walk(root):
        rel = os.path.relpath(dirpath, root).replace("\\", "/")
        if rel == ".":
            dirs[:] = [d for d in dirs if d not in KEEP]
        else:
            dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in files:
            out.append(f if rel == "." else rel + "/" + f)
    return out


def _copy(src_root, dst_root, rels):
    for rel in rels:
        dst = os.path.join(dst_root, *rel.split("/"))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(os.path.join(src_root, *rel.split("/")), dst)


def make_backup(root, version):
    base = os.path.join(root, "backup")
    dst = os.path.join(base, "v" + version)
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    _copy(root, dst, code_files(root))
    olds = sorted((d for d in os.listdir(base) if d.startswith("v") and os.path.isdir(os.path.join(base, d))),
                  key=lambda d: os.path.getmtime(os.path.join(base, d)))
    for d in olds[:-BACKUPS]:
        shutil.rmtree(os.path.join(base, d), ignore_errors=True)
    return dst


def latest_backup(root):
    base = os.path.join(root, "backup")
    if not os.path.isdir(base):
        return None
    dirs = [os.path.join(base, d) for d in os.listdir(base) if d.startswith("v")]
    dirs = [d for d in dirs if os.path.isfile(os.path.join(d, "tabdeck.py"))]
    return max(dirs, key=os.path.getmtime) if dirs else None


def install_zip(root, zip_path):
    prefix = check_zip(zip_path)
    root_abs = os.path.abspath(root)
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            rel = info.filename[len(prefix):]
            if not rel or rel.endswith("/"):
                continue
            dst = os.path.abspath(os.path.join(root_abs, *rel.split("/")))
            if not dst.startswith(root_abs + os.sep):
                raise UpdateError("percorso fuori dalla cartella: %s" % rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with z.open(info) as src, open(dst, "wb") as out:
                shutil.copyfileobj(src, out)


def restore(root, backup_dir):
    _copy(backup_dir, root, code_files(backup_dir))


def wait_ok(root, version, since, timeout=OK_TIMEOUT):
    """True quando il nuovo TabDeck ha scritto data\\update_ok.json con questa versione (dopo `since`)."""
    path = os.path.join(root, "data", "update_ok.json")
    end = time.time() + timeout
    while time.time() < end:
        try:
            with open(path, encoding="utf-8") as f:
                ok = json.load(f)
            if ok.get("version") == version and ok.get("t", 0) >= since:
                return True
        except (OSError, ValueError):
            pass
        time.sleep(0.25)
    return False


# --- parte che gira davvero (non usata dai test) -------------------------------------------------------

def _log(root, msg):
    os.makedirs(os.path.join(root, "cache"), exist_ok=True)
    with open(os.path.join(root, "cache", "update.log"), "a", encoding="utf-8") as f:
        f.write("[%s] %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))


def _result(root, ok, old, new, error=""):
    with open(os.path.join(root, "data", "update_result.json"), "w", encoding="utf-8") as f:
        json.dump({"ok": ok, "from": old, "to": new, "error": error, "t": time.time()}, f)


def _wait_pid(pid, timeout=15):
    k = ctypes.windll.kernel32
    h = k.OpenProcess(0x00100000, False, int(pid))   # SYNCHRONIZE
    if not h:
        return                                        # gia' chiuso
    try:
        if k.WaitForSingleObject(h, int(timeout * 1000)) != 0:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
            time.sleep(1)
    finally:
        k.CloseHandle(h)


def _start(root):
    """Avvia tabdeck.bat in una finestra ridotta a icona; restituisce il processo (cmd)."""
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 7   # SW_SHOWMINNOACTIVE
    return subprocess.Popen(["cmd", "/c", os.path.join(root, "tabdeck.bat")], cwd=root,
                            creationflags=subprocess.CREATE_NEW_CONSOLE, startupinfo=si)


def _kill(proc):
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
    time.sleep(1)


def _apply(root, zip_path, pid, old, new):
    _log(root, "aggiornamento %s -> %s" % (old, new))
    _wait_pid(pid)
    backup = None
    try:
        check_zip(zip_path)
        backup = make_backup(root, old)
        install_zip(root, zip_path)
    except Exception as e:  # noqa: BLE001
        _log(root, "errore prima dell'avvio: %r" % e)
        err = str(e)
        try:
            if backup:
                restore(root, backup)
        except Exception as e2:  # noqa: BLE001
            err += "; ripristino non riuscito (%s): copia in %s" % (e2, backup)
        finally:
            _start(root)
            _result(root, False, old, new, err)
        return
    since = time.time()
    proc = _start(root)
    if wait_ok(root, new, since):
        _log(root, "nuova versione %s avviata" % new)
        _result(root, True, old, new)
        return
    _log(root, "la %s non si e' avviata: ripristino la %s" % (new, old))
    _kill(proc)
    err = "la nuova versione non si e' avviata; ripristinata la %s" % old
    try:
        restore(root, backup)
    except Exception as e:  # noqa: BLE001
        _log(root, "ripristino non riuscito: %r" % e)
        err = "la nuova versione non si e' avviata e il ripristino non e' riuscito (%s): copia in %s" % (e, backup)
    finally:
        _start(root)
        _result(root, False, old, new, err)


def _rollback(root, pid, cur):
    b = latest_backup(root)
    _wait_pid(pid)
    if not b:
        _start(root)
        _result(root, False, cur, cur, "nessuna copia di sicurezza")
        return
    prev = os.path.basename(b)[1:]
    _log(root, "ritorno dalla %s alla %s" % (cur, prev))
    try:
        make_backup(root, cur)
        restore(root, b)
    except Exception as e:  # noqa: BLE001
        _log(root, "ritorno non riuscito: %r" % e)
        _start(root)
        _result(root, False, cur, prev, "ritorno alla %s non riuscito: %s" % (prev, e))
        return
    _start(root)
    _result(root, True, cur, prev)


def main(argv):
    def arg(name, default=None):
        return argv[argv.index(name) + 1] if name in argv else default
    root = os.path.abspath(arg("--root", os.path.dirname(os.path.abspath(__file__))))
    try:
        if argv[:1] == ["apply"]:
            _apply(root, argv[1], arg("--pid", 0), arg("--old"), arg("--new"))
        elif argv[:1] == ["rollback"]:
            _rollback(root, arg("--pid", 0), arg("--old"))
        else:
            print(__doc__)
            return 2
    except Exception as e:  # noqa: BLE001
        _log(root, "errore: %r" % e)
        raise
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
