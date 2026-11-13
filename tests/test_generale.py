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

    def test_page_bar_has_cog_and_no_fullscreen_button(self):
        page = self._page()
        self.assertNotIn('id="fs"', page)
        self.assertIn('<div id="gear">' + tabdeck.svg("cog"), page)


if __name__ == "__main__":
    unittest.main()
