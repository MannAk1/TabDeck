import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import youtube  # noqa: E402

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "yt_results.html")


def _html():
    with open(FIX, encoding="utf-8") as f:
        return f.read()


class ParseTest(unittest.TestCase):
    def test_parses_videos_in_order(self):
        r = youtube.parse_results(_html())
        self.assertEqual(len(r), 3)
        self.assertEqual(r[0], {"id": "5NV6Rdv1a3I", "title": "Daft Punk - Get Lucky (Official Audio)",
                                "channel": "Daft Punk", "dur": "4:09"})
        self.assertEqual([x["id"] for x in r], ["5NV6Rdv1a3I", "jfKfPfyJRdk", "CCHdMIEGaaM"])

    def test_live_has_empty_dur(self):
        r = youtube.parse_results(_html())
        self.assertEqual(r[1]["dur"], "")

    def test_limit(self):
        self.assertEqual(len(youtube.parse_results(_html(), limit=2)), 2)

    def test_bad_id_skipped(self):
        self.assertNotIn("bad id", [x["id"] for x in youtube.parse_results(_html())])

    def test_no_data_raises(self):
        with self.assertRaises(youtube.SearchError):
            youtube.parse_results("<html></html>")


if __name__ == "__main__":
    unittest.main()
