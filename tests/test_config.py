import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tabdeck  # noqa: E402

DEF = {"allowed_nets": ("172.20.10.",), "port": 8765, "adb": None}


class ConfigTest(unittest.TestCase):
    def _cfg(self, content):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "config.json")
        with open(p, "w", encoding="utf-8") as f:
            f.write(content if isinstance(content, str) else json.dumps(content))
        return tabdeck.load_config(p)

    def test_missing_file_gives_defaults(self):
        self.assertEqual(tabdeck.load_config(os.path.join(tempfile.mkdtemp(), "nope.json")), DEF)

    def test_values_read(self):
        c = self._cfg({"allowed_nets": ["192.168.1."], "port": 8766, "adb": "C:\\x\\adb.exe"})
        self.assertEqual(c, {"allowed_nets": ("192.168.1.",), "port": 8766, "adb": "C:\\x\\adb.exe"})

    def test_bad_values_fall_back_per_key(self):
        c = self._cfg({"allowed_nets": "192.168.1.", "port": 99999})
        self.assertEqual(c, DEF)
        self.assertEqual(self._cfg({"allowed_nets": ["192.168.1"]})["allowed_nets"], DEF["allowed_nets"])
        self.assertEqual(self._cfg({"port": True})["port"], 8765)

    def test_corrupt_json_gives_defaults(self):
        self.assertEqual(self._cfg("{"), DEF)


if __name__ == "__main__":
    unittest.main()
