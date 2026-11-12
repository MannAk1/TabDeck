import http.client
import json
import os
import socket
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


def _it(i):
    return {"id": (i * 11)[:11], "title": "T" + i, "channel": "C", "dur": "3:00"}


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class PlayerTest(unittest.TestCase):
    def setUp(self):
        self.c = Clock()
        self.p = youtube.Player(clock=self.c)
        self.p.poll()   # pagina aperta

    def _playing(self, item, pos=0.0, dur=200.0):
        self.p.play_now(item)
        self.p.poll()
        self.p.report({"t": "state", "s": 1, "pos": pos, "dur": dur})

    def test_play_now_sets_current_and_queues_load(self):
        self.p.play_now(_it("a"))
        self.assertEqual(self.p.snapshot()["cur"]["id"], _it("a")["id"])
        self.assertEqual(self.p.poll(), [{"a": "load", "id": _it("a")["id"], "pos": 0.0}])

    def test_enqueue_starts_when_idle(self):
        self.assertTrue(self.p.enqueue(_it("a")))
        self.assertEqual(self.p.snapshot()["cur"]["id"], _it("a")["id"])
        self.assertEqual(self.p.snapshot()["queue"], [])

    def test_enqueue_appends_when_playing(self):
        self._playing(_it("a"))
        self.assertFalse(self.p.enqueue(_it("b")))
        s = self.p.snapshot()
        self.assertEqual(s["cur"]["id"], _it("a")["id"])
        self.assertEqual([x["id"] for x in s["queue"]], [_it("b")["id"]])

    def test_move_up_and_remove(self):
        self._playing(_it("a"))
        for k in "bcd":
            self.p.enqueue(_it(k))
        self.p.move_up(2)
        self.assertEqual([x["title"] for x in self.p.snapshot()["queue"]], ["Tb", "Td", "Tc"])
        self.p.remove(0)
        self.assertEqual([x["title"] for x in self.p.snapshot()["queue"]], ["Td", "Tc"])
        self.p.move_up(0)
        self.p.move_up(9)
        self.p.remove(9)
        self.p.remove(-1)
        self.assertEqual([x["title"] for x in self.p.snapshot()["queue"]], ["Td", "Tc"])

    def test_ended_plays_next(self):
        self._playing(_it("a"))
        self.p.enqueue(_it("b"))
        self.p.report({"t": "ended"})
        s = self.p.snapshot()
        self.assertEqual(s["cur"]["id"], _it("b")["id"])
        self.assertEqual(s["queue"], [])
        self.assertEqual(self.p.poll()[0]["id"], _it("b")["id"])

    def test_ended_on_empty_queue_goes_idle(self):
        self._playing(_it("a"))
        self.p.report({"t": "ended"})
        s = self.p.snapshot()
        self.assertEqual(s["state"], "idle")
        self.assertEqual(s["cur"]["id"], _it("a")["id"])
        self.assertEqual(self.p.poll(), [])

    def test_embed_error_skips_and_sets_notice(self):
        self._playing(_it("a"))
        self.p.enqueue(_it("b"))
        self.p.report({"t": "error", "code": 150})
        s = self.p.snapshot()
        self.assertEqual(s["cur"]["id"], _it("b")["id"])
        self.assertEqual(s["notice"]["id"], _it("a")["id"])
        self.assertEqual(s["notice"]["msg"], "non riproducibile qui")
        self.c.t += 9
        self.p.poll()
        self.assertIsNone(self.p.snapshot()["notice"])
        self.p.enqueue(_it("c"))
        self.p.report({"t": "error", "code": 2})
        self.assertEqual(self.p.snapshot()["cur"]["id"], _it("b")["id"])

    def test_prev_restarts_after_3s(self):
        self._playing(_it("a"))
        self._playing(_it("b"), pos=10)
        self.p.prev()
        self.assertEqual(self.p.snapshot()["cur"]["id"], _it("b")["id"])
        self.assertEqual(self.p.poll(), [{"a": "seek", "s": 0.0}])

    def test_prev_goes_back_in_history(self):
        self._playing(_it("a"))
        self._playing(_it("b"), pos=1)
        self.p.prev()
        s = self.p.snapshot()
        self.assertEqual(s["cur"]["id"], _it("a")["id"])
        self.assertEqual([x["id"] for x in s["queue"]], [_it("b")["id"]])

    def test_outbox_keeps_last_load_only(self):
        for k in "abc":
            self.p.play_now(_it(k))
        cmds = [c for c in self.p.poll() if c["a"] == "load"]
        self.assertEqual(cmds, [{"a": "load", "id": _it("c")["id"], "pos": 0.0}])

    def test_poll_after_reopen_reloads_current(self):
        self._playing(_it("a"), pos=42)
        self.c.t += 6
        self.assertFalse(self.p.is_open())
        self.assertEqual(self.p.snapshot()["state"], "closed")
        cmds = self.p.poll()
        self.assertIn({"a": "load", "id": _it("a")["id"], "pos": 42.0}, cmds)
        self.assertTrue(self.p.is_open())

    def test_volume_and_seek_clamped(self):
        self._playing(_it("a"), dur=200)
        self.p.volume(150)
        self.assertEqual(self.p.snapshot()["vol"], 100)
        self.p.seek(-5)
        self.assertEqual(self.p.poll()[-1], {"a": "seek", "s": 0.0})
        self.p.seek(999)
        self.assertIn({"a": "seek", "s": 200.0}, self.p.poll())

    def test_toggle(self):
        self._playing(_it("a"))
        self.p.toggle()
        self.assertEqual(self.p.poll(), [{"a": "pause"}])
        self.p.report({"t": "state", "s": 2, "pos": 5, "dur": 200})
        self.p.toggle()
        self.assertEqual(self.p.poll(), [{"a": "play"}])

    def test_closed_before_first_poll(self):
        p = youtube.Player(clock=self.c)
        self.assertFalse(p.is_open())
        self.assertEqual(p.snapshot()["state"], "closed")


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")


class LocalServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = _free_port()
        cls.player = youtube.Player()
        cls.srv, cls.k = youtube.start_player_server(cls.port, cls.player, WEB)

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def _req(self, method, path, body=None, host=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        c.putrequest(method, path, skip_host=True)
        c.putheader("Host", host or "localhost:%d" % self.port)
        data = body.encode() if isinstance(body, str) else body
        if data is not None:
            c.putheader("Content-Length", str(len(data)))
        c.endheaders(data)
        r = c.getresponse()
        out = (r.status, r.read())
        c.close()
        return out

    def test_player_url(self):
        self.assertEqual(youtube.player_url(8865, "abc"), "http://localhost:8865/player?k=abc")

    def test_page_needs_secret(self):
        self.assertEqual(self._req("GET", "/player")[0], 403)
        self.assertEqual(self._req("GET", "/player?k=wrong")[0], 403)
        st, body = self._req("GET", "/player?k=" + self.k)
        self.assertEqual(st, 200)
        self.assertIn(b"youtube-nocookie.com", body)

    def test_wrong_host_rejected(self):
        for h in ("evil.com:%d" % self.port, "127.0.0.1:%d" % self.port, "localhost"):
            self.assertEqual(self._req("GET", "/player?k=" + self.k, host=h)[0], 403, h)

    def test_pcmd_returns_commands(self):
        self.player.play_now(_it("z"))
        st, body = self._req("GET", "/pcmd?k=" + self.k)
        self.assertEqual(st, 200)
        self.assertIn({"a": "load", "id": _it("z")["id"], "pos": 0.0}, json.loads(body))
        self.assertEqual(self._req("GET", "/pcmd")[0], 403)

    def test_pev_reports_state(self):
        self.player.play_now(_it("y"))
        st, _ = self._req("POST", "/pev?k=" + self.k, json.dumps({"t": "state", "s": 1, "pos": 3, "dur": 200}))
        self.assertEqual(st, 204)
        self.assertEqual(self.player.snapshot()["state"], "playing")
        self.assertEqual(self._req("POST", "/pev", "{}")[0], 403)

    def test_pev_too_big_or_bad_json(self):
        self.assertEqual(self._req("POST", "/pev?k=" + self.k, "x" * 5000)[0], 400)
        self.assertEqual(self._req("POST", "/pev?k=" + self.k, "not json")[0], 400)
        self.assertEqual(self._req("POST", "/pev?k=" + self.k, "[1]")[0], 400)

    def test_unknown_path_404(self):
        self.assertEqual(self._req("GET", "/x?k=" + self.k)[0], 404)


if __name__ == "__main__":
    unittest.main()
