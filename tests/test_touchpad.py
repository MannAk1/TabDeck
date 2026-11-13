import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tabdeck  # noqa: E402


class TouchpadLayoutTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = tabdeck.render_page("T" * 24)
        cls.pad = cls.page[cls.page.index('<div id="pad"'):cls.page.index('<div id="mon"')]

    def test_buttons_column_beside_the_touchpad(self):
        # tasti in colonna accanto al touchpad: Sinistro sopra, Rotellina in mezzo, Destro sotto
        self.assertRegex(self.pad, re.compile(r'id="tpwrap"><div id="tp">.*?</div>\s*<div id="tpb">', re.S))
        self.assertEqual(re.findall(r'class="tb[^"]*" data-b="(\w)"', self.pad), ["l", "m", "r"])
        self.assertIn('class="tb tw" data-b="m">Rotellina', self.pad)

    def test_keys_panel_can_be_hidden(self):
        self.assertIn('id="kbx"', self.pad)       # "Nascondi" nel pannello
        self.assertIn('id="kbshow"', self.pad)    # linguetta per riaprirlo
        self.assertLess(self.pad.index('id="kb"'), self.pad.index('id="tpwrap"'))   # tastiera a sinistra del touchpad

    def test_per_device_touchpad_options(self):
        self.assertIn('class="lseg" data-l="tpside"><div data-v="right">A destra</div><div data-v="left">A sinistra</div>',
                      self.page)
        self.assertIn('class="lseg" data-l="mb"><div data-v="right">A destra</div><div data-v="left">A sinistra</div>'
                      '<div data-v="top">Sopra</div><div data-v="bottom">Sotto</div></div>', self.page)
        self.assertIn('class="lseg" data-l="kb"><div data-v="on">Visibile</div><div data-v="off">Nascosta</div>', self.page)


if __name__ == "__main__":
    unittest.main()
