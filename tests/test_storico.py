import json
import os
import sys
import tempfile
import unittest
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import storico  # noqa: E402


class StoricoTest(unittest.TestCase):
    def setUp(self):
        self.d = os.path.join(tempfile.mkdtemp(), "storico")
        self.t = [1000.0]

    def save(self, label, layout=None, settings=None, keep=30):
        self.t[0] += 1
        return storico.save(self.d, label, layout, settings, keep=keep, now=lambda: self.t[0])

    def test_empty(self):
        self.assertIsNone(storico.latest(self.d))
        self.assertIsNone(storico.pop(self.d))
        self.assertEqual(storico.entries(self.d), [])

    def test_save_and_latest(self):
        self.save("a", {"fav": ["x"]}, {"theme": "hd"})
        self.save("b", {"fav": ["y"]}, None)
        e = storico.latest(self.d)
        self.assertEqual((e["label"], e["layout"], e["settings"], e["t"]), ("b", {"fav": ["y"]}, None, 1002.0))

    def test_keeps_newest(self):
        for i in range(35):
            self.save("n%d" % i, keep=30)
        es = storico.entries(self.d)
        self.assertEqual(len(es), 30)
        self.assertEqual(es[0]["label"], "n34")
        self.assertEqual(es[-1]["label"], "n5")
        self.assertEqual(len(os.listdir(self.d)), 30)

    def test_pop_walks_back(self):
        self.save("a")
        self.save("b")
        self.assertEqual(storico.pop(self.d)["label"], "b")
        self.assertEqual(storico.pop(self.d)["label"], "a")
        self.assertIsNone(storico.pop(self.d))

    def test_damaged_file_is_skipped(self):
        self.save("good")
        with open(os.path.join(self.d, "9999999999999.json"), "w") as fh:
            fh.write("{not json")
        self.assertEqual(storico.latest(self.d)["label"], "good")
        self.assertEqual(len(os.listdir(self.d)), 1)


if __name__ == "__main__":
    unittest.main()
