import json
import os
import socket
import sys
import tempfile
import unittest
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tabdeck  # noqa: E402

TOKEN = "G" * 24


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class GeneraleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old = tabdeck.PORT
        cls.old_file = tabdeck.LAYOUT_FILE
        tabdeck.LAYOUT_FILE = os.path.join(tempfile.mkdtemp(), "layout.json")
        tabdeck.PORT = _free_port()
        cls.srv, _ = tabdeck.start_server("127.0.0.1", TOKEN)
        cls.base = "http://127.0.0.1:%d" % tabdeck.PORT

    @classmethod
    def tearDownClass(cls):
        tabdeck.stop_server(cls.srv)
        tabdeck.PORT = cls.old
        tabdeck.LAYOUT_FILE = cls.old_file

    def setUp(self):
        self.saved = {sid: list(tabdeck.ROWS[sid]) for sid in tabdeck.ROW_SIDS}

    def tearDown(self):
        tabdeck.save_layout(self.saved)

    def _post(self, data):
        req = urllib.request.Request(self.base + "/layout", data=urllib.parse.urlencode(data).encode(),
                                     headers={"X-Token": TOKEN})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code

    def _page(self):
        with urllib.request.urlopen(self.base + "/?t=" + TOKEN, timeout=10) as r:
            return r.read().decode("utf-8")

    def test_move_between_sections(self):
        sis = [i for i in tabdeck.ROWS["sistema"] if i != "_vol"]
        stru = [i for i in tabdeck.ROWS["strumenti"] if i != "_vol"] + ["_vol"]
        self.assertEqual(self._post({"fav": ",".join(tabdeck.ROWS["avvio"]), "sistema": ",".join(sis),
                                     "strumenti": ",".join(stru)}), 200)
        self.assertNotIn("_vol", tabdeck.ROWS["sistema"])
        self.assertEqual(tabdeck.ROWS["strumenti"][-1], "_vol")

    def test_general_has_no_window_strip(self):
        secs, _ = tabdeck.render_general()
        self.assertNotIn("sec-wins", secs)
        self.assertNotIn('id="tbar"', secs)

    def test_new_install_defaults_follow_the_curated_layout(self):
        self.assertEqual(tabdeck.DEFAULT_FAV, ["firefox", "_yt", "discord", "steam", "helldivers2"])
        self.assertEqual(tabdeck.DEFAULT_ROWS["sistema"], ["desktop", "alt_tab", "task_view", "lock", "_vol", "explorer"])
        self.assertEqual(tabdeck.DEFAULT_ROWS["strumenti"], ["notepad", "calc", "run", "screenshot", "snip", "_mic"])
        rows = {"avvio": list(tabdeck.DEFAULT_FAV), "sistema": list(tabdeck.DEFAULT_ROWS["sistema"]),
                "strumenti": list(tabdeck.DEFAULT_ROWS["strumenti"])}
        self.assertEqual(tabdeck.clean_rows(rows), rows)   # tutti validi, nessuno in due righe

    def test_run_dialog_is_a_builtin_button(self):
        b = tabdeck.BY_ID["run"]
        self.assertEqual((b["label"], b["keys"], b["icon"]), ("Esegui", ["WIN", "R"], "monitor"))

    def _get(self, path, token=True):
        req = urllib.request.Request(self.base + path, headers={"X-Token": TOKEN} if token else {})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, None

    def test_general_endpoint_returns_fresh_markup(self):
        # dopo "Salva" la pagina rifa' Generale da qui, senza ricaricarsi
        st, j = self._get("/general")
        self.assertEqual(st, 200)
        secs, pops = tabdeck.render_general()
        self.assertEqual(j, {"secs": secs, "pops": pops})
        tabdeck.ROWS["strumenti"][:] = ["_mic"]
        self.assertEqual(self._get("/general")[1]["secs"], tabdeck.render_general()[0])

    def test_general_endpoint_needs_token(self):
        self.assertEqual(self._get("/general", token=False)[0], 403)

    def test_page_bar_has_cog_and_no_fullscreen_button(self):
        page = self._page()
        self.assertNotIn('id="fs"', page)
        self.assertIn('<div id="gear">' + tabdeck.svg("cog"), page)


if __name__ == "__main__":
    unittest.main()
