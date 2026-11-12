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

# risposta reale (accorciata) di suggestqueries-clients6.youtube.com, client=youtube
SAMPLE = ('window.google.ac.h(["daft pu",[["daft punk",0,[512,47],{"zae":"/m/016j7m","zao":"Daft Punk"}],'
          '["daft punk around the world",0,[512]],["daft punk veridis quo",0,[512]],["daft punk get lucky",0,[512]],'
          '["daft punk one more time",0,[512]],["daft punk harder better faster stronger",0,[512]],'
          '["daft punk instant crush",0,[512]],["daft punk lose yourself to dance",0,[512]],'
          '["daft punk something about us",0,[512]],["daft punk digital love",0,[512]]],{"k":1,"q":"x"}])')
TOKEN = "S" * 24


class ParseSuggestTest(unittest.TestCase):
    def test_parses_in_order_with_limit(self):
        s = youtube.parse_suggest(SAMPLE)
        self.assertEqual(len(s), 8)
        self.assertEqual(s[:3], ["daft punk", "daft punk around the world", "daft punk veridis quo"])

    def test_custom_limit(self):
        self.assertEqual(len(youtube.parse_suggest(SAMPLE, limit=3)), 3)

    def test_garbage_gives_empty(self):
        for bad in ("", "<html>400</html>", "window.google.ac.h(nope)", 'window.google.ac.h(["q", 5])'):
            self.assertEqual(youtube.parse_suggest(bad), [], bad)

    def test_suggest_network_error_gives_empty(self):
        old = youtube.urllib.request.urlopen

        def boom(*a, **k):
            raise OSError("offline")
        youtube.urllib.request.urlopen = boom
        try:
            self.assertEqual(youtube.suggest("daft"), [])
        finally:
            youtube.urllib.request.urlopen = old


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class SuggestApiTest(unittest.TestCase):
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
        self.old_suggest = tabdeck.youtube.suggest
        self.calls = []
        tabdeck.youtube.suggest = lambda q: self.calls.append(q) or [q + " uno", q + " due"]

    def tearDown(self):
        tabdeck.youtube.suggest = self.old_suggest

    def _get(self, path, token=True):
        req = urllib.request.Request(self.base + path, headers={"X-Token": TOKEN} if token else {})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, None

    def test_returns_suggestions(self):
        st, j = self._get("/ytsug?q=" + urllib.parse.quote("daft"))
        self.assertEqual(st, 200)
        self.assertEqual(j, {"s": ["daft uno", "daft due"]})

    def test_rejects_empty_and_long(self):
        self.assertEqual(self._get("/ytsug?q=%20")[0], 400)
        self.assertEqual(self._get("/ytsug?q=" + "a" * 201)[0], 400)
        self.assertEqual(self.calls, [])

    def test_requires_token(self):
        self.assertEqual(self._get("/ytsug?q=x", token=False)[0], 403)
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
