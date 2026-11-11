import json
import os
import socket
import sys
import unittest
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tabdeck  # noqa: E402

TOKEN = "W" * 24


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class WebAppTest(unittest.TestCase):
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

    def test_manifest_needs_token(self):
        with self.assertRaises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(self.base + "/manifest.json", timeout=5)
        self.assertEqual(e.exception.code, 403)

    def test_manifest_with_token(self):
        with urllib.request.urlopen(self.base + "/manifest.json?t=" + TOKEN, timeout=5) as r:
            self.assertIn("manifest+json", r.headers.get("Content-Type"))
            m = json.loads(r.read())
        self.assertEqual(m["display"], "fullscreen")
        self.assertEqual(m["start_url"], "/?t=" + TOKEN)
        self.assertTrue(any(i["sizes"] == "512x512" for i in m["icons"]))

    def test_icons_are_public_png(self):
        for path in ("/apple-touch-icon.png", "/icon-512.png"):
            with urllib.request.urlopen(self.base + path, timeout=5) as r:
                self.assertEqual(r.headers.get("Content-Type"), "image/png")
                self.assertEqual(r.read(8), b"\x89PNG\r\n\x1a\n")

    def test_page_links_manifest(self):
        with urllib.request.urlopen(self.base + "/?t=" + TOKEN, timeout=10) as r:
            body = r.read().decode("utf-8")
        self.assertIn('rel="manifest" href="/manifest.json?t=%s"' % TOKEN, body)
        self.assertIn('name="apple-mobile-web-app-capable" content="yes"', body)


if __name__ == "__main__":
    unittest.main()
