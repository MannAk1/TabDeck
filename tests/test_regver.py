import os
import sys
import unittest
import uuid
import winreg

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tabdeck  # noqa: E402


class UninstallVersionTest(unittest.TestCase):
    def setUp(self):
        self.key = r"Software\TabDeckTest_" + uuid.uuid4().hex

    def tearDown(self):
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, self.key)
        except OSError:
            pass

    def test_missing_key_does_nothing(self):
        self.assertFalse(tabdeck.sync_uninstall_version("1.2.3", self.key))
        with self.assertRaises(OSError):
            winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.key)

    def test_updates_version(self):
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, self.key) as k:
            winreg.SetValueEx(k, "DisplayVersion", 0, winreg.REG_SZ, "1.0.0")
        self.assertTrue(tabdeck.sync_uninstall_version("1.2.3", self.key))
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.key) as k:
            self.assertEqual(winreg.QueryValueEx(k, "DisplayVersion")[0], "1.2.3")
        self.assertFalse(tabdeck.sync_uninstall_version("1.2.3", self.key))   # gia' giusta


if __name__ == "__main__":
    unittest.main()
