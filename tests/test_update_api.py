import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tabdeck  # noqa: E402


class UpdateApiTest(unittest.TestCase):
    def test_parse_version(self):
        self.assertEqual(tabdeck.parse_version("v1.2.3"), (1, 2, 3))
        self.assertEqual(tabdeck.parse_version("1.2.3"), (1, 2, 3))
        self.assertGreater(tabdeck.parse_version("1.10.0"), tabdeck.parse_version("1.9.9"))
        self.assertEqual(tabdeck.parse_version("garbage"), (0, 0, 0))
        self.assertEqual(tabdeck.parse_version(None), (0, 0, 0))

    def test_latest_release_parses(self):
        body = json.dumps({"tag_name": "v1.0.1", "body": "note",
                           "zipball_url": "https://api.github.com/repos/o/TabDeck/zipball/v1.0.1"}).encode()
        with mock.patch.object(tabdeck, "_http_get", return_value=body) as g:
            r = tabdeck.latest_release("o/TabDeck")
        g.assert_called_once_with("https://api.github.com/repos/o/TabDeck/releases/latest")
        self.assertEqual(r, {"version": "1.0.1", "notes": "note",
                             "zip": "https://api.github.com/repos/o/TabDeck/zipball/v1.0.1"})

    def test_host_allowed(self):
        self.assertTrue(tabdeck.update_host_ok("https://codeload.github.com/x"))
        self.assertTrue(tabdeck.update_host_ok("https://api.github.com/repos/o/r/zipball/v1"))
        self.assertFalse(tabdeck.update_host_ok("http://codeload.github.com/x"))
        self.assertFalse(tabdeck.update_host_ok("https://evil.com/x"))
        self.assertFalse(tabdeck.update_host_ok("https://github.com.evil.com/x"))
        self.assertFalse(tabdeck.update_host_ok("https://user@evil.com/x"))

    def test_apply_refuses_older(self):
        with mock.patch.dict(tabdeck.UPD, {"latest": tabdeck.VERSION, "zip": "https://api.github.com/z"}), \
                mock.patch.object(tabdeck, "_download") as dl:
            self.assertEqual(tabdeck.update_apply(), "Hai gia' l'ultima versione")
            dl.assert_not_called()

    def test_apply_without_check(self):
        with mock.patch.dict(tabdeck.UPD, {"latest": None, "zip": None}):
            self.assertEqual(tabdeck.update_apply(), "Prima cerca gli aggiornamenti")

    def test_status_without_repo(self):
        with mock.patch.object(tabdeck, "UPDATE_REPO", ""):
            st = tabdeck.update_status()
        self.assertEqual(st["cur"], tabdeck.VERSION)
        self.assertFalse(st["repo"])
        self.assertIn("backup", st)


    def test_result_shown_once(self):
        import tempfile
        f = os.path.join(tempfile.mkdtemp(), "update_result.json")
        with open(f, "w") as fh:
            json.dump({"ok": True, "from": "1.0.0", "to": "1.0.1", "error": "", "t": 1}, fh)
        with mock.patch.object(tabdeck, "UPDATE_RESULT_FILE", f):
            self.assertEqual(tabdeck.update_status()["result"]["to"], "1.0.1")
            self.assertIsNone(tabdeck.update_status()["result"])


    def test_auto_check_does_not_consume_result(self):
        import tempfile
        d = tempfile.mkdtemp()
        res = os.path.join(d, "update_result.json")
        with open(res, "w") as fh:
            json.dump({"ok": False, "from": "1.0.0", "to": "1.0.1", "error": "x", "t": 1}, fh)
        with mock.patch.object(tabdeck, "UPDATE_RESULT_FILE", res),                 mock.patch.object(tabdeck, "UPDATE_CHECK_FILE", os.path.join(d, "c.json")):
            tabdeck._load_saved_check()
            self.assertEqual(tabdeck.update_status()["result"]["error"], "x")


if __name__ == "__main__":
    unittest.main()
