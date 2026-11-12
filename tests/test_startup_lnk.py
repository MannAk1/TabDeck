import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tabdeck  # noqa: E402

HERE = r"C:\Users\X\AppData\Local\TabDeck"
PYW = r"C:\Python312\pythonw.exe"
NEW_ARGS = '"%s\\tabdeck.py" --open --tray' % HERE


class StartupLnkPlanTest(unittest.TestCase):
    """Chi aggiorna dalla 1.1.0 nell'app ha ancora il collegamento in Esecuzione automatica a tabdeck.bat."""

    def test_old_bat_target_moves_to_tray(self):
        self.assertEqual(tabdeck.startup_lnk_plan(HERE + "\\tabdeck.bat", "", HERE, PYW), (PYW, NEW_ARGS))

    def test_match_ignores_case(self):
        self.assertEqual(tabdeck.startup_lnk_plan(HERE.lower() + "\\TABDECK.BAT", "", HERE, PYW), (PYW, NEW_ARGS))

    def test_already_new_untouched(self):
        self.assertIsNone(tabdeck.startup_lnk_plan(PYW, NEW_ARGS, HERE, PYW))

    def test_someone_elses_lnk_untouched(self):
        self.assertIsNone(tabdeck.startup_lnk_plan(r"C:\Other\app.exe", "", HERE, PYW))
        self.assertIsNone(tabdeck.startup_lnk_plan(r"C:\Other\TabDeck\tabdeck.bat", "", HERE, PYW))


class StartupLnkMigrateTest(unittest.TestCase):
    def test_migrates_real_shortcut(self):
        d = tempfile.mkdtemp()
        here = os.path.join(d, "Tab Deck")
        os.makedirs(here)
        lnk = os.path.join(d, "TabDeck.lnk")
        tabdeck.write_lnk(lnk, os.path.join(here, "tabdeck.bat"), "", here)
        self.assertTrue(tabdeck.migrate_startup_lnk(lnk, here, PYW))
        target, args = tabdeck.read_lnk(lnk)
        self.assertEqual(target.lower(), PYW.lower())
        self.assertEqual(args, '"%s" --open --tray' % os.path.join(here, "tabdeck.py"))
        self.assertFalse(tabdeck.migrate_startup_lnk(lnk, here, PYW))     # gia' fatto: niente

    def test_missing_lnk_does_nothing(self):
        self.assertFalse(tabdeck.migrate_startup_lnk(os.path.join(tempfile.mkdtemp(), "x.lnk"), HERE, PYW))


if __name__ == "__main__":
    unittest.main()
