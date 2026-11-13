import json
import os
import sys
import tempfile
import unittest
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import storico  # noqa: E402


class StoricoTest(unittest.TestCase):
    def setUp(self):
        self.d = os.path.join(tempfile.mkdtemp(), "storico")
        self.t = [1000.0]

    def save(self, label, layout=None, settings=None, keep=30):
        self.t[0] += 1
        return storico.save(self.d, label, layout, settings, keep=keep, now=lambda: self.t[0])

    def test_empty(self):
        self.assertIsNone(storico.latest(self.d))
        self.assertIsNone(storico.pop(self.d))
        self.assertEqual(storico.entries(self.d), [])

    def test_save_and_latest(self):
        self.save("a", {"fav": ["x"]}, {"theme": "hd"})
        self.save("b", {"fav": ["y"]}, None)
        e = storico.latest(self.d)
        self.assertEqual((e["label"], e["layout"], e["settings"], e["t"]), ("b", {"fav": ["y"]}, None, 1002.0))

    def test_keeps_newest(self):
        for i in range(35):
            self.save("n%d" % i, keep=30)
        es = storico.entries(self.d)
        self.assertEqual(len(es), 30)
        self.assertEqual(es[0]["label"], "n34")
        self.assertEqual(es[-1]["label"], "n5")
        self.assertEqual(len(os.listdir(self.d)), 30)

    def test_pop_walks_back(self):
        self.save("a")
        self.save("b")
        self.assertEqual(storico.pop(self.d)["label"], "b")
        self.assertEqual(storico.pop(self.d)["label"], "a")
        self.assertIsNone(storico.pop(self.d))

    def test_damaged_file_is_skipped(self):
        self.save("good")
        with open(os.path.join(self.d, "9999999999999.json"), "w") as fh:
            fh.write("{not json")
        self.assertEqual(storico.latest(self.d)["label"], "good")
        self.assertEqual(len(os.listdir(self.d)), 1)


import socket  # noqa: E402
import tabdeck  # noqa: E402

TOKEN = "S" * 24


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class UndoServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old = (tabdeck.PORT, tabdeck.LAYOUT_FILE, tabdeck.SETTINGS_FILE, tabdeck.HISTORY_DIR)
        d = tempfile.mkdtemp()
        tabdeck.LAYOUT_FILE = os.path.join(d, "layout.json")
        tabdeck.SETTINGS_FILE = os.path.join(d, "settings.json")
        tabdeck.HISTORY_DIR = os.path.join(d, "storico")
        tabdeck.PORT = _free_port()
        cls.srv, _ = tabdeck.start_server("127.0.0.1", TOKEN)
        cls.base = "http://127.0.0.1:%d" % tabdeck.PORT

    @classmethod
    def tearDownClass(cls):
        tabdeck.stop_server(cls.srv)
        tabdeck.PORT, tabdeck.LAYOUT_FILE, tabdeck.SETTINGS_FILE, tabdeck.HISTORY_DIR = cls.old

    def setUp(self):
        self.rows = {sid: list(tabdeck.ROWS[sid]) for sid in tabdeck.ROW_SIDS}
        tabdeck.save_layout(self.rows)
        tabdeck.save_settings(tabdeck.load_settings())
        while storico.pop(tabdeck.HISTORY_DIR):
            pass

    def tearDown(self):
        tabdeck.save_layout(self.rows)

    def _req(self, path, data=None):
        req = urllib.request.Request(self.base + path, data=urllib.parse.urlencode(data).encode() if data else None,
                                     headers={"X-Token": TOKEN})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, None

    def _rows_post(self, strumenti):
        return self._req("/layout", {"fav": ",".join(tabdeck.ROWS["avvio"]), "sistema": ",".join(tabdeck.ROWS["sistema"]),
                                     "strumenti": ",".join(strumenti)})[0]

    def test_rows_save_makes_snapshot_with_old_content(self):
        before = list(tabdeck.ROWS["strumenti"])
        self.assertEqual(self._rows_post(before[:-1]), 200)
        e = storico.latest(tabdeck.HISTORY_DIR)
        self.assertEqual(e["label"], "Pulsanti salvati")
        self.assertEqual(e["layout"]["rows"]["strumenti"], before)

    def test_unchanged_save_makes_no_snapshot(self):
        self.assertEqual(self._rows_post(list(tabdeck.ROWS["strumenti"])), 200)
        self.assertIsNone(storico.latest(tabdeck.HISTORY_DIR))

    def test_setting_label(self):
        cur = tabdeck.load_settings()["theme"]
        new = "notte" if cur != "notte" else "oled"
        st, j = self._req("/settings", {"theme": new})
        self.assertEqual(st, 200)
        self.assertIn("rev", j)
        e = storico.latest(tabdeck.HISTORY_DIR)
        self.assertEqual(e["label"], "Tema → " + tabdeck.SETTING_VALUES["theme"][new])
        self.assertEqual(e["settings"]["theme"], cur)

    def test_shortcut_labels(self):
        st, j = self._req("/layout", {"a": "key", "label": "Prova", "keys": "CTRL+K"})
        self.assertEqual(st, 200)
        self.assertEqual(storico.latest(tabdeck.HISTORY_DIR)["label"], "Scorciatoia «Prova» salvata")
        self.assertEqual(self._req("/layout", {"a": "delkey", "id": j["new"]})[0], 200)
        self.assertEqual(storico.latest(tabdeck.HISTORY_DIR)["label"], "Scorciatoia eliminata")

    def test_undo_restores_rows_and_settings_and_walks_back(self):
        before = list(tabdeck.ROWS["strumenti"])
        theme = tabdeck.load_settings()["theme"]
        rev0 = self._req("/state")[1]["rev"]
        self._rows_post(before[:-1])
        self._req("/settings", {"theme": "rosso" if theme != "rosso" else "oled"})
        self.assertNotEqual(self._req("/state")[1]["rev"], rev0)
        self.assertEqual(tabdeck.undo_info()["label"].split(" ")[0], "Tema")
        self.assertTrue(tabdeck.undo_last().startswith("Tema"))
        self.assertEqual(tabdeck.load_settings()["theme"], theme)
        self.assertEqual(tabdeck.ROWS["strumenti"], before[:-1])
        self.assertEqual(tabdeck.undo_last(), "Pulsanti salvati")
        self.assertEqual(tabdeck.ROWS["strumenti"], before)
        self.assertIsNone(tabdeck.undo_last())
        self.assertIsNone(tabdeck.undo_info())

    def test_undo_restores_deleted_shortcut(self):
        st, j = self._req("/layout", {"a": "key", "label": "Tmp", "keys": "CTRL+J"})
        kid = j["new"]
        self._req("/layout", {"a": "delkey", "id": kid})
        self.assertNotIn(kid, tabdeck.BY_ID)
        tabdeck.undo_last()
        self.assertIn(kid, tabdeck.BY_ID)
        tabdeck.undo_last()
        self.assertNotIn(kid, tabdeck.BY_ID)

    def test_general_has_settings_and_rev(self):
        st, j = self._req("/general")
        self.assertEqual(j["settings"], tabdeck.load_settings())
        self.assertEqual(j["rev"], tabdeck.CFG_REV)


if __name__ == "__main__":
    unittest.main()
