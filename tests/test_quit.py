import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tabdeck  # noqa: E402


class QuitTest(unittest.TestCase):
    def _quit(self, parent_exe):
        with mock.patch.object(tabdeck, "_exe_of_pid", return_value=parent_exe),                 mock.patch.object(tabdeck.subprocess, "run") as run,                 mock.patch.object(tabdeck.os, "_exit"), mock.patch.object(tabdeck.threading, "Timer"),                 mock.patch.object(tabdeck, "SERVER", None), mock.patch.object(tabdeck, "_TRAY", None),                 mock.patch.object(tabdeck, "DEVICES", None):
            tabdeck.quit_tabdeck()
        return [c[0][0] for c in run.call_args_list]

    def test_quit_closes_console_parent(self):
        calls = self._quit(r"C:\Windows\System32\cmd.exe")
        self.assertTrue(any(c[0] == "taskkill" and str(os.getppid()) in c for c in calls))

    def test_quit_leaves_other_parents(self):
        self.assertEqual(self._quit(r"C:\Windows\explorer.exe"), [])


if __name__ == "__main__":
    unittest.main()
