import json
import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import devices  # noqa: E402

UA_IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1"
UA_TAB = "Mozilla/5.0 (Linux; Android 4.4.2; SM-T230 Build/KOT49H) AppleWebKit/537.36 Chrome/81.0 Safari/537.36"
UA_WIN = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36"


class DeviceStoreTest(unittest.TestCase):
    def setUp(self):
        self.t = [1000.0]
        self.path = os.path.join(tempfile.mkdtemp(), "devices.json")

    def store(self, fresh=True):
        return devices.DeviceStore(self.path, fresh_install=fresh, now=lambda: self.t[0])

    def on(self):
        s = self.store()
        s.set_require(True)
        return s

    def test_defaults_existing_install(self):
        self.assertFalse(self.store(fresh=False).require)
        os.remove(self.path) if os.path.exists(self.path) else None
        self.assertTrue(self.store(fresh=True).require)

    def test_require_off_auto_approves(self):
        s = self.store(fresh=False)
        d, i = s.access(None, "1.2.3.4", UA_TAB)
        self.assertEqual(d, "ok")
        self.assertTrue(devices.valid_id(i))
        self.assertTrue(s.is_approved(i))

    def test_require_on_unknown_is_pending_with_code(self):
        s = self.on()
        d, i = s.access(None, "1.2.3.4", UA_IPHONE)
        self.assertEqual(d, "pending")
        self.assertRegex(s.code_of(i), r"^\d{4}$")

    def test_one_pending_per_ip(self):
        s = self.on()
        _, a = s.access(None, "1.2.3.4", UA_IPHONE)
        code = s.code_of(a)
        d, b = s.access(None, "1.2.3.4", UA_IPHONE)
        self.assertEqual(d, "pending")
        self.assertEqual(len(s.pending()), 1)
        self.assertEqual(s.code_of(b), code)

    def test_pending_expires_after_2_min(self):
        s = self.on()
        s.access(None, "1.2.3.4", UA_IPHONE)
        self.t[0] += 121
        self.assertEqual(s.pending(), [])
        d, _ = s.access(None, "1.2.3.4", UA_IPHONE)
        self.assertEqual(d, "pending")
        self.assertEqual(len(s.pending()), 1)

    def test_refuse_blocks_ip_and_id_10_min(self):
        s = self.on()
        _, i = s.access(None, "1.2.3.4", UA_IPHONE)
        s.refuse(i)
        self.assertEqual(s.access(i, "1.2.3.4", UA_IPHONE)[0], "refused")
        self.assertEqual(s.access(None, "1.2.3.4", UA_IPHONE)[0], "refused")
        self.assertEqual(s.access(i, "1.2.3.9", UA_IPHONE)[0], "refused")
        self.t[0] += 601
        self.assertEqual(s.access(None, "1.2.3.4", UA_IPHONE)[0], "pending")

    def test_lockdown_after_3_refusals(self):
        s = self.on()
        for n in range(3):
            _, i = s.access(None, "1.2.3.%d" % n, UA_IPHONE)
            s.refuse(i)
            self.t[0] += 60
        self.assertEqual(s.access(None, "1.2.3.50", UA_IPHONE)[0], "locked")
        self.assertGreater(s.locked_until, self.t[0])
        s.resume()
        self.assertEqual(s.access(None, "1.2.3.50", UA_IPHONE)[0], "pending")

    def test_lockdown_ends_after_30_min(self):
        s = self.on()
        for n in range(3):
            _, i = s.access(None, "1.2.3.%d" % n, UA_IPHONE)
            s.refuse(i)
        self.t[0] += 30 * 60 + 1
        self.assertEqual(s.access(None, "1.2.3.50", UA_IPHONE)[0], "pending")

    def test_approved_still_ok_during_lockdown(self):
        s = self.on()
        _, ok = s.access(None, "1.2.3.200", UA_TAB)
        s.approve(ok)
        for n in range(3):
            _, i = s.access(None, "1.2.3.%d" % n, UA_IPHONE)
            s.refuse(i)
        self.assertEqual(s.access(ok, "1.2.3.200", UA_TAB)[0], "ok")

    def test_approve_remove_rename_persist(self):
        s = self.on()
        _, i = s.access(None, "1.2.3.4", UA_TAB)
        s.approve(i)
        s.rename(i, "Tablet")
        s2 = self.store()
        self.assertTrue(s2.is_approved(i))
        self.assertEqual([d["name"] for d in s2.approved()], ["Tablet"])
        s2.remove(i)
        self.assertFalse(self.store().is_approved(i))

    def test_last_flush_throttled(self):
        s = self.store(fresh=False)
        _, i = s.access(None, "1.2.3.4", UA_TAB)
        with open(self.path, encoding="utf-8") as f:
            before = f.read()
        self.t[0] += 10
        s.access(i, "1.2.3.4", UA_TAB)
        s.flush()
        with open(self.path, encoding="utf-8") as f:
            self.assertEqual(f.read(), before)
        self.t[0] += 61
        s.access(i, "1.2.3.4", UA_TAB)
        s.flush()
        with open(self.path, encoding="utf-8") as f:
            self.assertNotEqual(f.read(), before)

    def test_fresh_default_survives_restart(self):
        self.assertTrue(self.store(fresh=True).require)
        self.assertTrue(self.store(fresh=False).require)     # dopo il riavvio token.txt esiste gia'

    def test_revoke_all(self):
        s = self.store(fresh=False)
        _, i = s.access(None, "1.2.3.4", UA_TAB)
        s.revoke_all()
        self.assertFalse(s.is_approved(i))
        self.assertEqual(self.store(fresh=False).approved(), [])

    def test_ua_name(self):
        self.assertEqual(devices.ua_name(UA_IPHONE), "iPhone")
        self.assertEqual(devices.ua_name(UA_TAB), "SM-T230")
        self.assertEqual(devices.ua_name(UA_WIN), "PC Windows")
        self.assertEqual(devices.ua_name(""), "Dispositivo")

    def test_corrupt_file_starts_empty(self):
        with open(self.path, "w") as f:
            f.write("{not json")
        s = self.store(fresh=False)
        self.assertEqual(s.approved(), [])
        self.assertFalse(s.require)

    def test_invalid_id_gets_new_one(self):
        s = self.store(fresh=False)
        d, i = s.access("../evil", "1.2.3.4", UA_TAB)
        self.assertEqual(d, "ok")
        self.assertTrue(re.match(r"^[0-9a-f]{32}$", i))

    def test_on_change_called(self):
        s = self.on()
        hits = []
        s.on_change = lambda: hits.append(1)
        s.access(None, "1.2.3.4", UA_IPHONE)
        self.assertTrue(hits)


if __name__ == "__main__":
    unittest.main()
