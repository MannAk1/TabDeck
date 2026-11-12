import json
import os
import socket
import sys
import unittest
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tabdeck  # noqa: E402
import youtube  # noqa: E402

TOKEN = "Y" * 24
VID = "5NV6Rdv1a3I"


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class YoutubeApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old = tabdeck.PORT
        tabdeck.PORT = _free_port()
        cls.srv, _ = tabdeck.start_server("127.0.0.1", TOKEN)
        cls.base = "http://127.0.0.1:%d" % tabdeck.PORT

    @classmethod
    def tearDownClass(cls):
        tabdeck.stop_server(cls.srv)
        tabdeck.PORT = cls.old

    def setUp(self):
        self.old_search, self.old_open, self.old_yt = tabdeck.youtube.search, tabdeck.yt_open, tabdeck.YT
        self.opened = []
        tabdeck.yt_open = lambda front: self.opened.append(front) or "opened"
        tabdeck.YT = youtube.Player()

    def tearDown(self):
        tabdeck.youtube.search, tabdeck.yt_open, tabdeck.YT = self.old_search, self.old_open, self.old_yt

    def _get(self, path, token=True):
        req = urllib.request.Request(self.base + path, headers={"X-Token": TOKEN} if token else {})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, json.loads(r.read() or b"null")
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def _post(self, path, form, token=True):
        req = urllib.request.Request(self.base + path, data=urllib.parse.urlencode(form).encode(),
                                     headers={"X-Token": TOKEN} if token else {})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def test_yts_rejects_empty_and_long(self):
        called = []
        tabdeck.youtube.search = lambda q: called.append(q) or []
        self.assertEqual(self._get("/yts?q=%20%20")[0], 400)
        self.assertEqual(self._get("/yts?q=" + "a" * 201)[0], 400)
        self.assertEqual(called, [])

    def test_yts_returns_results(self):
        tabdeck.youtube.search = lambda q: [{"id": VID, "title": q, "channel": "c", "dur": "1:00"}]
        st, j = self._get("/yts?q=" + urllib.parse.quote("get lucky"))
        self.assertEqual(st, 200)
        self.assertEqual(j["r"][0]["title"], "get lucky")

    def test_yts_search_error_502(self):
        def boom(q):
            raise youtube.SearchError("offline")
        tabdeck.youtube.search = boom
        st, body = self._get("/yts?q=x")
        self.assertEqual(st, 502)
        self.assertEqual(json.loads(body)["err"], "Ricerca non riuscita")

    def test_yt_play_opens_player_when_closed(self):
        st, j = self._post("/yt", {"a": "play", "id": VID, "title": "T", "channel": "C", "dur": "4:09"})
        self.assertEqual(st, 200)
        self.assertEqual(j["cur"]["id"], VID)
        self.assertEqual(self.opened, [False])

    def test_yt_play_does_not_reopen_when_open(self):
        tabdeck.YT.poll()
        self._post("/yt", {"a": "play", "id": VID, "title": "T"})
        self.assertEqual(self.opened, [])

    def test_yt_add_and_queue_ops(self):
        tabdeck.YT.poll()
        self._post("/yt", {"a": "play", "id": VID, "title": "A"})
        tabdeck.YT.report({"t": "state", "s": 1, "pos": 1, "dur": 100})
        self._post("/yt", {"a": "add", "id": "CCHdMIEGaaM", "title": "B"})
        st, j = self._post("/yt", {"a": "add", "id": "4NRXx6U8ABQ", "title": "C"})
        self.assertEqual([x["title"] for x in j["queue"]], ["B", "C"])
        st, j = self._post("/yt", {"a": "up", "i": "1"})
        self.assertEqual([x["title"] for x in j["queue"]], ["C", "B"])
        st, j = self._post("/yt", {"a": "rm", "i": "0"})
        self.assertEqual([x["title"] for x in j["queue"]], ["B"])
        st, j = self._post("/yt", {"a": "vol", "v": "40"})
        self.assertEqual(j["vol"], 40)

    def test_yt_title_trimmed(self):
        st, j = self._post("/yt", {"a": "play", "id": VID, "title": "x" * 300})
        self.assertEqual(st, 200)
        self.assertEqual(len(j["cur"]["title"]), 200)

    def test_yt_bad_id_400(self):
        self.assertEqual(self._post("/yt", {"a": "play", "id": "abc"})[0], 400)
        self.assertEqual(self._post("/yt", {"a": "web", "id": "../x"})[0], 400)

    def test_yt_id_with_newline_400(self):
        self.assertEqual(self._post("/yt", {"a": "play", "id": "AAAAAAAAAAA" + chr(10)})[0], 400)

    def test_yt_quick_plays_open_player_once(self):
        for v in (VID, "CCHdMIEGaaM", "4NRXx6U8ABQ"):
            self._post("/yt", {"a": "add", "id": v, "title": "T"})
        self.assertEqual(self.opened, [False])

    def test_yt_bad_numbers_400(self):
        self.assertEqual(self._post("/yt", {"a": "vol", "v": "loud"})[0], 400)
        self.assertEqual(self._post("/yt", {"a": "up", "i": "-x"})[0], 400)
        self.assertEqual(self._post("/yt", {"a": "seek", "s": "nan"})[0], 400)

    def test_yt_bad_action_400(self):
        self.assertEqual(self._post("/yt", {"a": "rm -rf"})[0], 400)

    def test_yt_open(self):
        st, j = self._post("/yt", {"a": "open"})
        self.assertEqual(st, 200)
        self.assertEqual(j["open_r"], "opened")
        self.assertEqual(self.opened, [True])

    def test_yt_state(self):
        st, j = self._get("/yt")
        self.assertEqual(st, 200)
        self.assertEqual(j["state"], "closed")
        self.assertFalse(j["open"])

    def test_yt_requires_token(self):
        self.assertEqual(self._get("/yt", token=False)[0], 403)
        self.assertEqual(self._get("/yts?q=x", token=False)[0], 403)
        self.assertEqual(self._post("/yt", {"a": "next"}, token=False)[0], 403)


class YtStartTest(unittest.TestCase):
    def test_busy_port_leaves_player_unavailable(self):
        busy = socket.socket()
        busy.bind(("127.0.0.1", 0))
        busy.listen(1)
        old_port, old_url = tabdeck.PORT, tabdeck.YT_URL
        try:
            tabdeck.PORT = busy.getsockname()[1] - 100
            tabdeck.YT_URL = None
            tabdeck.yt_start()
            self.assertIsNone(tabdeck.YT_URL)
            self.assertEqual(tabdeck.yt_open(front=True), "unavailable")
        finally:
            busy.close()
            tabdeck.PORT, tabdeck.YT_URL = old_port, old_url


class RowsTest(unittest.TestCase):
    def test_default_favorites_have_yt_not_spotify(self):
        self.assertIn("_yt", tabdeck.DEFAULT_FAV)
        self.assertNotIn("spotify", tabdeck.DEFAULT_FAV)
        self.assertIn("_yt", tabdeck.SPECIALS)

    def test_clean_rows_keeps_yt(self):
        r = tabdeck.clean_rows({"avvio": ["_yt", "discord"], "sistema": [], "strumenti": []})
        self.assertEqual(r["avvio"], ["_yt", "discord"])

    def test_migration_replaces_spotify_once(self):
        rows = {"avvio": ["opera_gx", "spotify", "steam"], "sistema": ["_vol"], "strumenti": []}
        out = tabdeck.yt_migrate(rows, done=False)
        self.assertEqual(out["avvio"], ["opera_gx", "_yt", "steam"])
        self.assertEqual(tabdeck.yt_migrate(out, done=False)["avvio"], ["opera_gx", "_yt", "steam"])

    def test_migration_appends_when_no_spotify(self):
        out = tabdeck.yt_migrate({"avvio": ["discord"], "sistema": [], "strumenti": []}, done=False)
        self.assertEqual(out["avvio"], ["discord", "_yt"])
        full = ["k%d" % i for i in range(tabdeck.FAV_MAX)]
        self.assertEqual(tabdeck.yt_migrate({"avvio": list(full), "sistema": [], "strumenti": []}, done=False)["avvio"], full)

    def test_migration_respects_removed_tile(self):
        rows = {"avvio": ["opera_gx", "spotify"], "sistema": [], "strumenti": []}
        self.assertEqual(tabdeck.yt_migrate(rows, done=True)["avvio"], ["opera_gx", "spotify"])

    def test_migration_skips_when_yt_elsewhere(self):
        rows = {"avvio": ["spotify"], "sistema": ["_yt"], "strumenti": []}
        self.assertEqual(tabdeck.yt_migrate(rows, done=False), rows)

    def test_save_layout_writes_flag(self):
        import tempfile
        old = tabdeck.LAYOUT_FILE
        d = tempfile.mkdtemp()
        try:
            tabdeck.LAYOUT_FILE = os.path.join(d, "layout.json")
            tabdeck.save_layout()
            with open(tabdeck.LAYOUT_FILE, encoding="utf-8") as fh:
                self.assertTrue(json.load(fh)["yt_added"])
        finally:
            tabdeck.LAYOUT_FILE = old

    def test_yt_special_html_has_data_go(self):
        h = tabdeck.special_html("_yt")
        self.assertIn('data-go="yt"', h)
        self.assertIn('data-yt="1"', h)
        self.assertIn('id="syt"', h)
        self.assertNotIn('id="syt"', tabdeck.special_html("_yt", False))


if __name__ == "__main__":
    unittest.main()
