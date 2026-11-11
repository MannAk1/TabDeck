"""Codice QR minimo, senza dipendenze (solo libreria standard).

Usato dalla pagina di abbinamento /pair: il telefono inquadra il codice e apre TabDeck gia' con il token.
Implementa lo standard ISO/IEC 18004 quanto basta: modalita' byte, correzione errori livello M,
versioni 1-10 (fino a ~210 caratteri), scelta della maschera con le regole di penalita'.
"""

# Livello M, versioni 1-10: (codeword di correzione per blocco, [(numero blocchi, codeword dati per blocco), ...])
_EC_M = {
    1: (10, [(1, 16)]), 2: (16, [(1, 28)]), 3: (26, [(1, 44)]), 4: (18, [(2, 32)]), 5: (24, [(2, 43)]),
    6: (16, [(4, 27)]), 7: (18, [(4, 31)]), 8: (22, [(2, 38), (2, 39)]), 9: (22, [(3, 36), (2, 37)]),
    10: (26, [(4, 43), (1, 44)]),
}
_ALIGN = {1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34],
          7: [6, 22, 38], 8: [6, 24, 42], 9: [6, 26, 46], 10: [6, 28, 50]}

# Aritmetica in GF(256) con polinomio 0x11D
_EXP = [0] * 512
_LOG = [0] * 256
_x = 1
for _i in range(255):
    _EXP[_i] = _x
    _LOG[_x] = _i
    _x <<= 1
    if _x & 0x100:
        _x ^= 0x11D
for _i in range(255, 512):
    _EXP[_i] = _EXP[_i - 255]


def _gmul(a, b):
    return 0 if a == 0 or b == 0 else _EXP[_LOG[a] + _LOG[b]]


def _rs_ec(data, n):
    """Codeword di correzione Reed-Solomon (n) per i dati."""
    gen = [1]                                   # prodotto di (x - a^i), coefficienti dal grado piu' alto
    for i in range(n):
        nxt = [0] * (len(gen) + 1)
        for j, g in enumerate(gen):
            nxt[j] ^= g
            nxt[j + 1] ^= _gmul(g, _EXP[i])
        gen = nxt
    rem = [0] * n
    for d in data:
        f = d ^ rem[0]
        rem = rem[1:] + [0]
        for j in range(n):
            rem[j] ^= _gmul(gen[j + 1], f)
    return rem


def _bch(val, poly, bits):
    """Resto della divisione polinomiale binaria (per formato e versione)."""
    v = val << bits
    top = poly.bit_length() - 1
    for i in range(v.bit_length() - 1, top - 1, -1):
        if v >> i & 1:
            v ^= poly << (i - top)
    return (val << bits) | v


def _codewords(data):
    for ver in range(1, 11):
        ec, groups = _EC_M[ver]
        ndata = sum(c * k for c, k in groups)
        cc = 8 if ver < 10 else 16
        if 4 + cc + 8 * len(data) <= ndata * 8:
            break
    else:
        raise ValueError("testo troppo lungo per il QR (max versione 10)")
    bits = [0, 1, 0, 0] + [len(data) >> i & 1 for i in range(cc - 1, -1, -1)]
    for b in data:
        bits += [b >> i & 1 for i in range(7, -1, -1)]
    bits += [0] * min(4, ndata * 8 - len(bits))
    bits += [0] * (-len(bits) % 8)
    words = [int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]
    pad = 0
    while len(words) < ndata:
        words.append((0xEC, 0x11)[pad % 2])
        pad += 1
    blocks, pos = [], 0
    for count, k in groups:
        for _ in range(count):
            blocks.append(words[pos:pos + k])
            pos += k
    eccs = [_rs_ec(b, ec) for b in blocks]
    out = []
    for i in range(max(len(b) for b in blocks)):
        out += [b[i] for b in blocks if i < len(b)]
    for i in range(ec):
        out += [e[i] for e in eccs]
    return ver, out


_MASKS = [
    lambda r, c: (r + c) % 2 == 0, lambda r, c: r % 2 == 0, lambda r, c: c % 3 == 0,
    lambda r, c: (r + c) % 3 == 0, lambda r, c: (r // 2 + c // 3) % 2 == 0,
    lambda r, c: (r * c) % 2 + (r * c) % 3 == 0, lambda r, c: ((r * c) % 2 + (r * c) % 3) % 2 == 0,
    lambda r, c: ((r + c) % 2 + (r * c) % 3) % 2 == 0,
]


def _base(ver):
    """Matrice con i soli motivi fissi + mappa delle celle riservate."""
    n = 17 + 4 * ver
    m = [[False] * n for _ in range(n)]
    fn = [[False] * n for _ in range(n)]

    def put(r, c, v):
        m[r][c] = v
        fn[r][c] = True

    for r0, c0 in ((0, 0), (0, n - 7), (n - 7, 0)):           # finder + separatori
        for dr in range(-1, 8):
            for dc in range(-1, 8):
                r, c = r0 + dr, c0 + dc
                if 0 <= r < n and 0 <= c < n:
                    ring = max(abs(dr - 3), abs(dc - 3))
                    put(r, c, ring != 2 and ring != 4)
    for i in range(8, n - 8):                                   # timing
        put(6, i, i % 2 == 0)
        put(i, 6, i % 2 == 0)
    al = _ALIGN[ver]
    for a in al:                                                # allineamento
        for b in al:
            if (a, b) in ((6, 6), (6, al[-1]), (al[-1], 6)):
                continue
            for dr in range(-2, 3):
                for dc in range(-2, 3):
                    put(a + dr, b + dc, max(abs(dr), abs(dc)) != 1)
    for i in range(9):                                          # spazio del formato
        fn[8][i] = fn[i][8] = True
    for i in range(8):
        fn[8][n - 1 - i] = fn[n - 1 - i][8] = True
    put(n - 8, 8, True)                                         # modulo sempre scuro
    if ver >= 7:                                                # informazioni di versione
        v = _bch(ver, 0x1F25, 12)
        for i in range(18):
            bit = bool(v >> i & 1)
            put(i // 3, n - 11 + i % 3, bit)
            put(n - 11 + i % 3, i // 3, bit)
    return m, fn


def _place(m, fn, words):
    n = len(m)
    bits = [w >> i & 1 for w in words for i in range(7, -1, -1)]
    k = 0
    right = n - 1
    while right >= 1:
        if right == 6:
            right = 5
        up = ((right + 1) & 2) == 0
        for vert in range(n):
            r = n - 1 - vert if up else vert
            for j in range(2):
                c = right - j
                if not fn[r][c]:
                    m[r][c] = bool(bits[k]) if k < len(bits) else False
                    k += 1
        right -= 2


def _format(m, mask):
    n = len(m)
    v = _bch((0b00 << 3) | mask, 0x537, 10) ^ 0x5412          # livello M = 00
    b = [bool(v >> i & 1) for i in range(15)]
    for i in range(6):
        m[i][8] = b[i]
    m[7][8], m[8][8], m[8][7] = b[6], b[7], b[8]
    for i in range(9, 15):
        m[8][14 - i] = b[i]
    for i in range(8):
        m[8][n - 1 - i] = b[i]
    for i in range(8, 15):
        m[n - 15 + i][8] = b[i]
    m[n - 8][8] = True


def _penalty(m):
    n = len(m)
    p = 0
    lines = m + [[m[r][c] for r in range(n)] for c in range(n)]
    pat = [True, False, True, True, True, False, True]
    for line in lines:
        run, prev = 0, None
        for v in line:
            if v == prev:
                run += 1
            else:
                if run >= 5:
                    p += run - 2
                run, prev = 1, v
        if run >= 5:
            p += run - 2
        ext = [False] * 4 + line + [False] * 4
        for i in range(len(ext) - 10):
            if ext[i:i + 7] == pat and not any(ext[i + 7:i + 11]):
                p += 40
            if ext[i + 4:i + 11] == pat and not any(ext[i:i + 4]):
                p += 40
    for r in range(n - 1):
        for c in range(n - 1):
            if m[r][c] == m[r][c + 1] == m[r + 1][c] == m[r + 1][c + 1]:
                p += 3
    dark = sum(map(sum, m))
    p += abs(dark * 20 - n * n * 10) // (n * n) * 10
    return p


def qr_matrix(text):
    """Matrice del QR (lista di righe, True = modulo scuro) per il testo dato (UTF-8)."""
    ver, words = _codewords(text.encode("utf-8"))
    best = None
    for mask in range(8):
        m, fn = _base(ver)
        _place(m, fn, words)
        f = _MASKS[mask]
        for r in range(len(m)):
            for c in range(len(m)):
                if not fn[r][c] and f(r, c):
                    m[r][c] = not m[r][c]
        _format(m, mask)
        score = _penalty(m)
        if best is None or score < best[0]:
            best = (score, m)
    return best[1]


def qr_svg(text, scale=8, border=4):
    """QR come immagine SVG (nero su bianco, un solo <path>)."""
    m = qr_matrix(text)
    size = len(m) + 2 * border
    d = "".join("M%d,%dh1v1h-1z" % (c + border, r + border)
                for r, row in enumerate(m) for c, v in enumerate(row) if v)
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" '
            'shape-rendering="crispEdges"><rect width="100%%" height="100%%" fill="#fff"/>'
            '<path d="%s" fill="#000"/></svg>' % (size, size, size * scale, size * scale, d))
