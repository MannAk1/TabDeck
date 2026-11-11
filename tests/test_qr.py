import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tdqr  # noqa: E402

URL55 = "http://192.168.100.200:8765/?t=" + "x" * 24


def _finder_ok(m, r0, c0):
    for r in range(7):
        for c in range(7):
            ring = max(abs(r - 3), abs(c - 3))
            want = ring != 2   # 3 = bordo scuro, 2 = anello chiaro, 0-1 = centro scuro
            if m[r0 + r][c0 + c] != want:
                return False
    return True


def _format_bits(m):
    """I 15 bit di formato (copia vicino al finder in alto a sinistra), dal piu' significativo."""
    pos = [(8, c) for c in (0, 1, 2, 3, 4, 5, 7, 8)] + [(r, 8) for r in (7, 5, 4, 3, 2, 1, 0)]
    return [m[r][c] for r, c in pos]


def _format_bits2(m):
    n = len(m)
    pos = [(n - 1 - i, 8) for i in range(7)] + [(8, n - 8 + i) for i in range(8)]
    return [m[r][c] for r, c in pos]


class QrTest(unittest.TestCase):
    def test_size(self):
        self.assertEqual(len(tdqr.qr_matrix("A")), 21)
        m = tdqr.qr_matrix(URL55)
        self.assertEqual(len(m), 33)          # versione 4
        self.assertTrue(all(len(row) == 33 for row in m))

    def test_finder_patterns(self):
        m = tdqr.qr_matrix(URL55)
        n = len(m)
        self.assertTrue(_finder_ok(m, 0, 0))
        self.assertTrue(_finder_ok(m, 0, n - 7))
        self.assertTrue(_finder_ok(m, n - 7, 0))

    def test_timing_pattern(self):
        m = tdqr.qr_matrix(URL55)
        n = len(m)
        self.assertEqual([m[6][c] for c in range(8, n - 8)], [c % 2 == 0 for c in range(8, n - 8)])
        self.assertEqual([m[r][6] for r in range(8, n - 8)], [r % 2 == 0 for r in range(8, n - 8)])

    def test_format_info_is_level_m_and_consistent(self):
        m = tdqr.qr_matrix(URL55)
        a, b = _format_bits(m), _format_bits2(m)
        self.assertEqual(a, b)
        val = int("".join("1" if x else "0" for x in a), 2) ^ 0x5412
        self.assertEqual(val >> 13, 0b00)                  # livello M
        # resto BCH(15,5) nullo
        rem = val
        for i in range(14, 9, -1):
            if rem >> i & 1:
                rem ^= 0x537 << (i - 10)
        self.assertEqual(rem, 0)
        self.assertTrue(m[len(m) - 8][8])                  # modulo sempre scuro

    @unittest.skip("nessun codificatore di riferimento fidato disponibile: verifica con la fotocamera del telefono")
    def test_known_vector(self):
        pass

    def test_too_long(self):
        with self.assertRaises(ValueError):
            tdqr.qr_matrix("x" * 300)

    def test_svg(self):
        s = tdqr.qr_svg("A")
        self.assertTrue(s.startswith("<svg"))
        self.assertIn('viewBox="0 0 29 29"', s)   # 21 + 2*4 di margine
        self.assertIn("crispEdges", s)


if __name__ == "__main__":
    unittest.main()
