import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tray  # noqa: E402


class TrayTest(unittest.TestCase):
    def test_import(self):
        for m in ("start", "notify", "stop"):
            self.assertTrue(callable(getattr(tray.Tray, m)))

    def test_start_stop(self):
        ico = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tabdeck.ico")
        t = tray.Tray(ico, "TabDeck test", lambda: None, lambda: None, lambda: None)
        t.start()
        self.assertTrue(t.ready.wait(5))
        self.assertTrue(t.added)
        t.stop()
        t.thread.join(5)
        self.assertFalse(t.thread.is_alive())


if __name__ == "__main__":
    unittest.main()
