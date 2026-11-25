import json
import os
import socket
import sys
import tempfile
import unittest
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tabdeck  # noqa: E402

TOKEN = "N" * 24


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class NavBarTest(unittest.TestCase):
    def test_bar_has_home_audio_touchpad_squares(self):
        page = tabdeck.render_page("T" * 24)
        bar = page[page.index('<div id="bar">'):page.index('<div id="set">')]
        self.assertIn('<div id="nav" class="nsq" data-q="grid">' + tabdeck.svg("home"), bar)
        self.assertIn('<div class="nsq" data-q="mix">' + tabdeck.svg("music") + "</div>", bar)
        self.assertIn('<div class="nsq" data-q="pad">' + tabdeck.svg("mouse") + "</div>", bar)
        self.assertNotIn("&#9650;", bar)                 # niente piu' freccia del menu
        self.assertIn('id="navpop"', page)               # l'elenco resta: tenendo premuto Home

    def test_radial_fan_lists_main_sections_and_all(self):
        page = tabdeck.render_page("T" * 24)
        fan = page[page.index('<div id="fan">'):page.index('<div id="navpop"')]
        tabs = [t for t, _n, _d, _i in tabdeck.NAV if t not in ("grid", "mix", "pad")]
        self.assertEqual(tabdeck.FAN_TABS, tabs)        # Audio e Touchpad hanno gia' il loro quadrato
        pos = [fan.index('data-tab="%s"' % t) for t in tabs]
        self.assertEqual(pos, sorted(pos))
        for t in ("grid", "mix", "pad"):
            self.assertNotIn('data-tab="%s"' % t, fan)
        self.assertIn('<div class="fb" data-tab="hd2">' + tabdeck.svg("target") + "<b>HD2</b></div>", fan)
        self.assertIn('class="fb fall"', fan)           # "Tutte" apre l'elenco completo
        self.assertIn("<b>Tutte</b>", fan)

    def test_monitor_tile(self):
        self.assertIn("_mon", tabdeck.SPECIALS)
        live, copy = tabdeck.special_html("_mon"), tabdeck.special_html("_mon", False)
        self.assertIn('data-go="mon"', live)
        self.assertIn('id="moncpu"', live)
        self.assertNotIn('id="', copy)                   # le copie nell'editor non duplicano gli id

    def test_new_installs_get_monitor_in_sistema(self):
        self.assertEqual(tabdeck.DEFAULT_ROWS["sistema"][-1], "_mon")
        rows = {"avvio": list(tabdeck.DEFAULT_FAV), "sistema": list(tabdeck.DEFAULT_ROWS["sistema"]),
                "strumenti": list(tabdeck.DEFAULT_ROWS["strumenti"])}
        self.assertEqual(tabdeck.clean_rows(rows), rows)


class StateCpuTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old = tabdeck.PORT, tabdeck.LAYOUT_FILE, tabdeck.HISTORY_DIR
        tabdeck.LAYOUT_FILE = os.path.join(tempfile.mkdtemp(), "layout.json")
        tabdeck.HISTORY_DIR = os.path.join(tempfile.mkdtemp(), "storico")
        tabdeck.PORT = _free_port()
        cls.srv, _ = tabdeck.start_server("127.0.0.1", TOKEN)
        cls.rows = list(tabdeck.ROWS["sistema"])

    @classmethod
    def tearDownClass(cls):
        tabdeck.ROWS["sistema"][:] = cls.rows
        tabdeck.stop_server(cls.srv)
        tabdeck.PORT, tabdeck.LAYOUT_FILE, tabdeck.HISTORY_DIR = cls.old

    def state(self):
        req = urllib.request.Request("http://127.0.0.1:%d/state?g=1" % tabdeck.PORT, headers={"X-Token": TOKEN})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())

    def test_cpu_only_when_the_monitor_tile_is_in_generale(self):
        tabdeck.ROWS["sistema"][:] = [i for i in self.rows if i != "_mon"]
        self.assertNotIn("cpu", self.state())            # niente campionamento se il riquadro non c'e'
        tabdeck.ROWS["sistema"][:] = [i for i in self.rows if i != "_mon"] + ["_mon"]
        self.assertIn("cpu", self.state())


if __name__ == "__main__":
    unittest.main()
