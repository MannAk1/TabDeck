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
        sent = []
        orig = tabdeck._send_inputs
        tabdeck._send_inputs = lambda items: sent.append([(i.u.mi.dwFlags, i.u.mi.dx, i.u.mi.dy) for i in items])
        try:
            tabdeck.SMOOTH.flush()
            tabdeck.SMOOTH.move(80, 0)          # mossa ancora in viaggio verso il cursore
            tabdeck.mouse_input(5, 0, buttons=["lc"])
        finally:
            tabdeck._send_inputs = orig
        flags = sent[-1]
        self.assertEqual(flags[0], (0x1, 85, 0))  # prima tutto il movimento rimasto...
        self.assertTrue(all(f != 0x1 for f, _, _ in flags[1:]))   # ...poi il clic
        self.assertEqual(tabdeck.SMOOTH.take(), (0, 0))


if __name__ == "__main__":
    unittest.main()
