import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tabdeck  # noqa: E402


class OpenTabletTest(unittest.TestCase):
    def run_it(self, status, adb="adb.exe", opened=True):
        app = tabdeck._App.__new__(tabdeck._App)
        srv = mock.Mock(token="tok")
        with mock.patch.object(tabdeck, "STATUS", status), mock.patch.object(tabdeck, "SERVER", srv), \
                mock.patch.object(tabdeck, "_ADB", adb), \
                mock.patch.object(tabdeck, "open_on_tablet", return_value=opened) as op:
            return app.open_tablet(), op.call_args_list

    def test_opens_each_usb_tablet_with_token_url(self):
        r, calls = self.run_it({"state": "listening", "ip": "172.20.10.2", "adb": ["S1"]})
        self.assertEqual(r, "ok")
        self.assertEqual(calls[0][0], ("adb.exe", "http://172.20.10.2:%d/?t=tok" % tabdeck.PORT, "S1"))

    def test_not_listening(self):
        self.assertEqual(self.run_it({"state": "waiting", "adb": ["S1"]})[0], "off")

    def test_no_tablet_or_no_adb(self):
        self.assertEqual(self.run_it({"state": "listening", "ip": "1.2.3.4", "adb": []})[0], "nousb")
        self.assertEqual(self.run_it({"state": "listening", "ip": "1.2.3.4", "adb": ["S1"]}, adb=None)[0], "nousb")

    def test_adb_failure(self):
        self.assertEqual(self.run_it({"state": "listening", "ip": "1.2.3.4", "adb": ["S1"]}, opened=False)[0], "fail")


if __name__ == "__main__":
    unittest.main()
