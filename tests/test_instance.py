import os
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import tabdeck  # noqa: E402

PORT = 8798
CHILD = r"""
import sys, time
sys.path.insert(0, %r)
import tabdeck
role, hold = sys.argv[1], float(sys.argv[2])
t0 = time.time()
r = tabdeck.single_instance(%d, restart=(role == "R"))
print("got", r, round(time.time() - t0, 2), flush=True)
if role == "A":
    time.sleep(hold / 2)
    print("show", tabdeck.show_requested(), flush=True)
    time.sleep(hold / 2)
""" % (ROOT, PORT)


def child(role, hold=0.0):
    return subprocess.Popen([sys.executable, "-c", CHILD, role, str(hold)], stdout=subprocess.PIPE, text=True)


class InstanceTest(unittest.TestCase):
    def test_parse_flags(self):
        f = tabdeck.parse_flags(["--open", "--tray"])
        self.assertEqual(f, {"open": True, "tray": True, "restart": False, "host": None})
        self.assertEqual(tabdeck.parse_flags(["--host", "1.2.3.4"])["host"], "1.2.3.4")
        with self.assertRaises(SystemExit):
            tabdeck.parse_flags(["--host"])

    def test_second_launch_signals_and_exits(self):
        a = child("A", 3)
        time.sleep(0.8)
        b = child("B")
        out_b = b.communicate(timeout=10)[0].split()
        self.assertEqual(out_b[1], "False")
        self.assertLess(float(out_b[2]), 1.0)
        out_a = a.communicate(timeout=10)[0]
        self.assertIn("show True", out_a)

    def test_restart_waits_for_old(self):
        a = child("A", 2)
        time.sleep(0.8)
        r = child("R")
        out = r.communicate(timeout=20)[0].split()
        self.assertEqual(out[1], "True")
        self.assertGreater(float(out[2]), 0.5)
        a.wait(timeout=10)

    def test_log_cap(self):
        p = os.path.join(tempfile.mkdtemp(), "tabdeck.log")
        with open(p, "w", encoding="utf-8") as f:
            for n in range(6000):
                f.write("riga %05d %s\n" % (n, "x" * 40))
        self.assertGreater(os.path.getsize(p), 300 * 1024)
        tabdeck.cap_log(p)
        self.assertLessEqual(os.path.getsize(p), 160 * 1024)
        with open(p, encoding="utf-8") as f:
            self.assertTrue(f.readline().startswith("riga "))

    def test_log_tail(self):
        p = os.path.join(tempfile.mkdtemp(), "tabdeck.log")
        with open(p, "w", encoding="utf-8") as f:
            f.write("".join("l%d\n" % n for n in range(500)))
        self.assertEqual(tabdeck.log_tail(3, p), ["l497", "l498", "l499"])


if __name__ == "__main__":
    unittest.main()
