import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import devices  # noqa: E402
import gui  # noqa: E402

UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"


class GuiLogicTest(unittest.TestCase):
    def test_device_rows_order_and_active(self):
        t = [1000.0]
        s = devices.DeviceStore(os.path.join(tempfile.mkdtemp(), "d.json"), fresh_install=False, now=lambda: t[0])
        _, old = s.access(None, "10.0.0.1", "SM-T230")
        t[0] = 1100
        _, new = s.access(None, "10.0.0.2", UA)
        s.set_require(True)
        s.access(None, "10.0.0.3", UA)
        t[0] = 1105
        rows = gui.device_rows(s, t[0])
        self.assertEqual([r["kind"] for r in rows], ["pending", "approved", "approved"])
        self.assertEqual(rows[1]["id"], new)            # visto piu' di recente prima
        self.assertTrue(rows[1]["active"])               # 5 s fa
        self.assertFalse(rows[2]["active"])              # 105 s fa
        self.assertRegex(rows[0]["code"], r"^\d{4}$")

    def test_should_autoshow_once_per_minute(self):
        self.assertTrue(gui.should_autoshow(0, 1000))
        self.assertFalse(gui.should_autoshow(1000, 1059))
        self.assertTrue(gui.should_autoshow(1000, 1060))


if __name__ == "__main__":
    unittest.main()
