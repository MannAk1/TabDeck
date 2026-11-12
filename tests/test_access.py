import http.client
import json
import os
import re
import socket
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import devices  # noqa: E402
import tabdeck  # noqa: E402

TOKEN = "A" * 24
UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Mobile/15E148 Safari/604.1"


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class AccessTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old_port, cls.old_dev, cls.old_tok = tabdeck.PORT, tabdeck.DEVICES, tabdeck.TOKEN_FILE
        tabdeck.PORT = _free_port()
        d = tempfile.mkdtemp()
        tabdeck.TOKEN_FILE = os.path.join(d, "token.txt")
        cls.srv, _ = tabdeck.start_server("127.0.0.1", TOKEN)

    @classmethod
    def tearDownClass(cls):
        tabdeck.stop_server(cls.srv)
        tabdeck.PORT, tabdeck.DEVICES, tabdeck.TOKEN_FILE = cls.old_port, cls.old_dev, cls.old_tok

    def setUp(self):
        self.srv.token = TOKEN
        p = os.path.join(tempfile.mkdtemp(), "devices.json")
        tabdeck.DEVICES = self.store = devices.DeviceStore(p, fresh_install=False)

    def req(self, path, token=TOKEN, dev=None, cookie_dev=None, method="GET", body=None):
        c = http.client.HTTPConnection("127.0.0.1", tabdeck.PORT, timeout=10)
        h = {"Host": "127.0.0.1:%d" % tabdeck.PORT, "User-Agent": UA}
        if token:
            h["X-Token"] = token
        if dev:
            h["X-Device"] = dev
        if cookie_dev:
            h["Cookie"] = "tdd=" + cookie_dev
        if body is not None:
            h["Content-Type"] = "application/x-www-form-urlencoded"
        c.request(method, path, body=body, headers=h)
        r = c.getresponse()
        data = r.read().decode("utf-8", "replace")
        cookies = r.msg.get_all("Set-Cookie") or []
        c.close()
        return r.status, data, cookies

    def dev_from(self, cookies):
        for c in cookies:
            m = re.match(r"tdd=([0-9a-f]{32})", c)
            if m:
                return m.group(1)
        return None

    def test_require_off_page_sets_cookie(self):
        st, body, cookies = self.req("/")
        self.assertEqual(st, 200)
        dev = self.dev_from(cookies)
        self.assertTrue(dev)
        self.assertTrue(self.store.is_approved(dev))
        self.assertIn(dev, body)       # la pagina riceve l'ID per localStorage

    def test_require_on_unknown_gets_wait_page(self):
        self.store.set_require(True)
        st, body, cookies = self.req("/")
        self.assertEqual(st, 200)
        dev = self.dev_from(cookies)
        self.assertIn(self.store.code_of(dev), body)
        st, body, _ = self.req("/state", dev=dev)
        self.assertEqual(st, 403)
        self.assertTrue(json.loads(body).get("pending"))

    def test_approved_device_ok_after_approve(self):
        self.store.set_require(True)
        dev = self.dev_from(self.req("/")[2])
        self.store.approve(dev)
        self.assertEqual(self.req("/ping", dev=dev)[0], 200)

    def test_device_id_from_header_wins(self):
        self.store.set_require(True)
        dev = self.dev_from(self.req("/")[2])
        self.store.approve(dev)
        other = devices.new_id()
        self.assertEqual(self.req("/ping", dev=dev, cookie_dev=other)[0], 200)

    def test_request_without_id_does_not_create(self):
        self.req("/ping")
        self.assertEqual(self.store.approved(), [])

    def test_known_format_id_reappears_when_require_off(self):
        dev = devices.new_id()
        self.assertEqual(self.req("/press", dev=dev, method="POST", body="id=x")[0] in (200, 400, 404), True)
        self.assertTrue(self.store.is_approved(dev))     # niente accessi invisibili: torna nell'elenco

    def test_removed_device_blocked_when_require_on(self):
        dev = self.dev_from(self.req("/")[2])
        self.store.set_require(True)
        self.assertEqual(self.req("/ping", dev=dev)[0], 200)
        self.store.remove(dev)
        st, body, _ = self.req("/ping", dev=dev)
        self.assertEqual(st, 403)
        self.assertTrue(json.loads(body).get("pending"))

    def test_log_message_without_path(self):
        h = object.__new__(tabdeck.Handler)
        h.client_address, h.server = ("1.2.3.4", 1), self.srv
        h.log_message("Request timed out: %r", TimeoutError("x"))   # non deve sollevare eccezioni

    def test_rotated_token_keeps_approved(self):
        self.store.set_require(True)
        dev = self.dev_from(self.req("/")[2])
        self.store.approve(dev)
        new = tabdeck.rotate_token()
        self.assertNotEqual(new, TOKEN)
        self.assertEqual(self.req("/ping", token=TOKEN, dev=dev)[0], 200)
        self.assertEqual(self.req("/ping", token=TOKEN, dev=devices.new_id())[0], 403)
        self.assertEqual(self.req("/ping", token=new)[0], 403)        # require on: nuovo ID sconosciuto
        with open(tabdeck.TOKEN_FILE, encoding="utf-8") as f:
            self.assertEqual(f.read().strip(), new)

    def test_no_token_no_device_is_403(self):
        self.assertEqual(self.req("/ping", token=None)[0], 403)

    def test_no_route_changes_require(self):
        self.store.set_require(True)
        dev = self.dev_from(self.req("/")[2])
        self.store.approve(dev)
        for body in ("require=0", "appr=0", "k=require&v=0"):
            self.req("/settings", dev=dev, method="POST", body=body)
        self.assertTrue(self.store.require)

    def test_devstate_reports_pending_then_ok(self):
        self.store.set_require(True)
        dev = self.dev_from(self.req("/")[2])
        st, body, _ = self.req("/devstate", dev=dev)
        self.assertEqual(st, 200)
        self.assertEqual(json.loads(body)["state"], "pending")
        self.store.approve(dev)
        self.assertEqual(json.loads(self.req("/devstate", dev=dev)[1])["state"], "ok")

    def test_refused_page(self):
        self.store.set_require(True)
        dev = self.dev_from(self.req("/")[2])
        self.store.refuse(dev)
        st, body, _ = self.req("/", dev=dev)
        self.assertEqual(st, 403)


if __name__ == "__main__":
    unittest.main()
