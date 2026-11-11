import os
import socket
import sys
import unittest
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tabdeck  # noqa: E402

TOKEN = "T" * 24


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class PairTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old_port = tabdeck.PORT
        tabdeck.PORT = _free_port()
        cls.srv, _ = tabdeck.start_server("127.0.0.1", TOKEN)

    @classmethod
    def tearDownClass(cls):
        tabdeck.stop_server(cls.srv)
        tabdeck.PORT = cls.old_port

    def test_pair_from_pc(self):
        with urllib.request.urlopen("http://127.0.0.1:%d/pair" % tabdeck.PORT, timeout=5) as r:
            body = r.read().decode("utf-8")
            self.assertEqual(r.status, 200)
            self.assertEqual(r.headers.get("Cache-Control"), "no-store")
        self.assertIn("<svg", body)
        self.assertIn("http://127.0.0.1:%d/?t=%s" % (tabdeck.PORT, TOKEN), body)
        self.assertIn(tabdeck.VERSION, body)

    def test_pair_allowed(self):
        self.assertFalse(tabdeck.pair_allowed("192.168.1.50", "192.168.1.10"))
        self.assertTrue(tabdeck.pair_allowed("192.168.1.10", "192.168.1.10"))
        self.assertTrue(tabdeck.pair_allowed("127.0.0.1", "192.168.1.10"))

    def test_other_pages_still_need_token(self):
        with self.assertRaises(urllib.error.HTTPError) as e:
            urllib.request.urlopen("http://127.0.0.1:%d/ping" % tabdeck.PORT, timeout=5)
        self.assertEqual(e.exception.code, 403)


class HostTest(unittest.TestCase):
    def test_host_ok(self):
        self.assertTrue(tabdeck.host_ok("192.168.1.10:8765", "192.168.1.10", 8765))
        self.assertFalse(tabdeck.host_ok("evil.example:8765", "192.168.1.10", 8765))
        self.assertFalse(tabdeck.host_ok(None, "192.168.1.10", 8765))
        self.assertFalse(tabdeck.host_ok("192.168.1.10", "192.168.1.10", 8765))

    def test_rebinding_refused(self):
        old = tabdeck.PORT
        tabdeck.PORT = _free_port()
        srv, _ = tabdeck.start_server("127.0.0.1", TOKEN)
        try:
            for path in ("/pair", "/?t=" + TOKEN):
                req = urllib.request.Request("http://127.0.0.1:%d%s" % (tabdeck.PORT, path), headers={"Host": "evil.example:%d" % tabdeck.PORT})
                with self.assertRaises(urllib.error.HTTPError) as e:
                    urllib.request.urlopen(req, timeout=5)
                self.assertEqual(e.exception.code, 403)
        finally:
            tabdeck.stop_server(srv)
            tabdeck.PORT = old


if __name__ == "__main__":
    unittest.main()
