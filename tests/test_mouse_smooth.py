import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tabdeck  # noqa: E402


class MouseSmootherTest(unittest.TestCase):
    def drain(self, s, limit=50):
        out = []
        for _ in range(limit):
            c = s.take()
            if c == (0, 0):
                break
            out.append(c)
        return out

    def test_move_is_spread_and_total_is_exact(self):
        s = tabdeck.MouseSmoother(send=None)
        s.move(100, -37)
        steps = self.drain(s)
        self.assertEqual((sum(x for x, _ in steps), sum(y for _, y in steps)), (100, -37))
        self.assertGreater(len(steps), 3)              # niente salto unico
        self.assertLessEqual(len(steps), 12)           # ma finisce in fretta (~50 ms)
        self.assertLess(abs(steps[0][0]), 100)

    def test_small_moves_go_at_once(self):
        s = tabdeck.MouseSmoother(send=None)
        s.move(1, 0)
        self.assertEqual(self.drain(s), [(1, 0)])

    def test_flush_returns_what_is_left(self):
        s = tabdeck.MouseSmoother(send=None)
        s.move(50, 20)
        first = s.take()
        self.assertEqual(s.flush(), (50 - first[0], 20 - first[1]))
        self.assertEqual(s.take(), (0, 0))

    def test_clicks_land_after_pending_moves(self):
        log = []
        orig = tabdeck._send_inputs, tabdeck.move_cursor
        tabdeck._send_inputs = lambda items: log.append(("in", [i.u.mi.dwFlags for i in items]))
        tabdeck.move_cursor = lambda dx, dy: log.append(("move", dx, dy))
        try:
            tabdeck.SMOOTH.flush()
            tabdeck.SMOOTH.move(80, 0)          # mossa ancora in viaggio verso il cursore
            tabdeck.mouse_input(5, 0, buttons=["lc"])
        finally:
            tabdeck._send_inputs, tabdeck.move_cursor = orig
        self.assertEqual(log, [("move", 85, 0), ("in", [0x2, 0x4])])   # prima tutto il movimento, poi il clic
        self.assertEqual(tabdeck.SMOOTH.take(), (0, 0))

    def test_moves_bypass_windows_acceleration(self):
        # il cursore si sposta di esattamente dx, dy (niente "precisione puntatore avanzata" di Windows)
        log = []
        orig = tabdeck._send_inputs, tabdeck.move_cursor
        tabdeck._send_inputs = lambda items: log.append(("in", [i.u.mi.dwFlags for i in items]))
        tabdeck.move_cursor = lambda dx, dy: log.append(("move", dx, dy))
        try:
            tabdeck._mouse_now(7, -3, 0, 0, ["rc"])
            tabdeck._smooth_send(2, 1)
        finally:
            tabdeck._send_inputs, tabdeck.move_cursor = orig
        self.assertEqual(log, [("move", 7, -3), ("in", [0x8, 0x10]), ("move", 2, 1)])   # mai MOUSEEVENTF_MOVE (0x1)


if __name__ == "__main__":
    unittest.main()
