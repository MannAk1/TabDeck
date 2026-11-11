import json
import os
import sys
import tempfile
import threading
import time
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import updater  # noqa: E402


def _write(root, rel, text):
    p = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)


def _read(root, rel):
    with open(os.path.join(root, *rel.split("/")), encoding="utf-8") as f:
        return f.read()


def _zip(entries):
    fd, p = tempfile.mkstemp(suffix=".zip")
    os.close(fd)
    with zipfile.ZipFile(p, "w") as z:
        for name, text in entries.items():
            z.writestr(name, text)
    return p


class CheckZipTest(unittest.TestCase):
    def test_check_zip_ok(self):
        p = _zip({"TabDeck-1.0.1/tabdeck.py": "x", "TabDeck-1.0.1/web/app.js": "y"})
        self.assertEqual(updater.check_zip(p), "TabDeck-1.0.1/")

    def test_check_zip_rejects(self):
        bad = [
            {"TabDeck-1.0.1/tabdeck.py": "x", "TabDeck-1.0.1/../evil.py": "x"},
            {"TabDeck-1.0.1/tabdeck.py": "x", "C:/x.py": "x"},
            {"TabDeck-1.0.1/tabdeck.py": "x", "/abs.py": "x"},
            {"TabDeck-1.0.1/app.js": "x"},
            {"TabDeck-1.0.1/tabdeck.py": "x", "TabDeck-1.0.1/data/token.txt": "x"},
            {"TabDeck-1.0.1/tabdeck.py": "x", "Altro/file.py": "x"},
        ]
        for entries in bad:
            with self.assertRaises(updater.UpdateError, msg=str(entries)):
                updater.check_zip(_zip(entries))
        fd, p = tempfile.mkstemp()
        os.write(fd, b"not a zip")
        os.close(fd)
        with self.assertRaises(updater.UpdateError):
            updater.check_zip(p)

    def test_check_zip_too_big(self):
        old = updater.MAX_ZIP
        updater.MAX_ZIP = 10
        try:
            with self.assertRaises(updater.UpdateError):
                updater.check_zip(_zip({"T/tabdeck.py": "x" * 100}))
        finally:
            updater.MAX_ZIP = old


class FilesTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        _write(self.root, "tabdeck.py", "old")
        _write(self.root, "web/app.js", "js")
        _write(self.root, "data/token.txt", "A")
        _write(self.root, "cache/x.png", "c")
        _write(self.root, "__pycache__/t.pyc", "p")

    def test_code_files(self):
        self.assertEqual(sorted(updater.code_files(self.root)), ["tabdeck.py", "web/app.js"])

    def test_install_keeps_data(self):
        z = _zip({"TabDeck-1.0.1/tabdeck.py": "new", "TabDeck-1.0.1/web/new.css": "css"})
        updater.install_zip(self.root, z)
        self.assertEqual(_read(self.root, "tabdeck.py"), "new")
        self.assertEqual(_read(self.root, "web/new.css"), "css")
        self.assertEqual(_read(self.root, "web/app.js"), "js")      # mai cancellato
        self.assertEqual(_read(self.root, "data/token.txt"), "A")

    def test_backup_restore_roundtrip(self):
        b = updater.make_backup(self.root, "1.0.0")
        self.assertTrue(os.path.isdir(b))
        self.assertFalse(os.path.exists(os.path.join(b, "data")))
        _write(self.root, "tabdeck.py", "broken")
        updater.restore(self.root, b)
        self.assertEqual(_read(self.root, "tabdeck.py"), "old")
        self.assertEqual(_read(self.root, "data/token.txt"), "A")

    def test_backup_keeps_three(self):
        for i in range(5):
            updater.make_backup(self.root, "1.0.%d" % i)
            time.sleep(0.02)
        left = sorted(os.listdir(os.path.join(self.root, "backup")))
        self.assertEqual(left, ["v1.0.2", "v1.0.3", "v1.0.4"])

    def test_latest_backup(self):
        self.assertIsNone(updater.latest_backup(self.root))
        updater.make_backup(self.root, "1.0.0")
        self.assertTrue(updater.latest_backup(self.root).endswith("v1.0.0"))


class WaitOkTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, "data"))

    def _ok(self, version, t, delay=0):
        def w():
            time.sleep(delay)
            with open(os.path.join(self.root, "data", "update_ok.json"), "w") as f:
                json.dump({"version": version, "pid": 1, "t": t}, f)
        threading.Thread(target=w).start()

    def test_wait_ok_true(self):
        since = time.time()
        self._ok("1.0.1", since + 0.1, delay=0.3)
        self.assertTrue(updater.wait_ok(self.root, "1.0.1", since, timeout=3))

    def test_wait_ok_wrong_version(self):
        since = time.time()
        self._ok("1.0.0", since + 0.1)
        self.assertFalse(updater.wait_ok(self.root, "1.0.1", since, timeout=1))

    def test_wait_ok_stale(self):
        since = time.time()
        self._ok("1.0.1", since - 100)
        self.assertFalse(updater.wait_ok(self.root, "1.0.1", since, timeout=1))


class WindowsNamesTest(unittest.TestCase):
    def test_rejects_windows_tricks(self):
        for bad in ("T/Data/token.txt", "T/data./x", "T/data /x", "T/foo:bar", "T/CON", "T/web/com1.txt",
                    "T/sub/D:x", r"T/a\..\b", "T/../x"):
            with self.assertRaises(updater.UpdateError, msg=bad):
                updater.check_zip(_zip({"T/tabdeck.py": "x", bad: "y"}))


class StartAlwaysTest(unittest.TestCase):
    def test_start_and_result_even_if_restore_fails(self):
        from unittest import mock
        root = tempfile.mkdtemp()
        _write(root, "tabdeck.py", "old")
        _write(root, "data/x", "")
        z = _zip({"T/tabdeck.py": "new"})
        with mock.patch.object(updater, "_wait_pid"), mock.patch.object(updater, "_start") as st,                 mock.patch.object(updater, "wait_ok", return_value=False), mock.patch.object(updater, "_kill"),                 mock.patch.object(updater, "restore", side_effect=OSError("locked")):
            updater._apply(root, z, 0, "1.0.0", "1.0.1")
        self.assertEqual(st.call_count, 2)
        with open(os.path.join(root, "data", "update_result.json")) as f:
            r = json.load(f)
        self.assertFalse(r["ok"])
        self.assertIn("locked", r["error"])


if __name__ == "__main__":
    unittest.main()
