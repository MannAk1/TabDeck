"""TabDeck - finestra sul PC (tkinter): stato, QR per collegare un telefono, dispositivi, approvazioni.

Non importa tabdeck.py: riceve un oggetto `app` con quello che serve (vedi run()). Gira sul thread principale;
gli altri thread (icona, server) non toccano mai Tk: mettono funzioni in una coda che la finestra svuota.
"""
import queue
import time
import tkinter as tk
from tkinter import messagebox, simpledialog

# colori del tema predefinito della pagina (web/style.css :root)
BG, PANEL, PANEL2, LINE = "#0a0b08", "#14160f", "#1b1e15", "#2c3022"
AMBER, TEXT, DIM, OK, ERR, WARN = "#f5c518", "#ebe7d6", "#8d8a72", "#5cc45a", "#e8463a", "#ffd166"
FONT, MONO = "Segoe UI", "Consolas"
ACTIVE_S = 10          # verde se visto negli ultimi 10 s
AUTOSHOW_S = 60        # la finestra si apre da sola per una richiesta al massimo una volta al minuto


def device_rows(store, now):
    """Righe dell'elenco: prima le richieste in attesa, poi gli approvati dal piu' recente."""
    rows = [dict(p, kind="pending") for p in store.pending()]
    appr = sorted(store.approved(), key=lambda d: -(d["last"] or 0))
    rows += [dict(d, kind="approved", active=now - (d["last"] or 0) < ACTIVE_S) for d in appr]
    return rows


def undo_text(info, now):
    """Riga accanto a "Annulla ultima modifica": cosa verrebbe annullato e quando era stato fatto."""
    if not info:
        return "Nessuna modifica da annullare"
    return "Ultima: %s · %s" % (info["label"], _ago(info["t"], now))


def should_autoshow(last_show, now):
    return now - last_show >= AUTOSHOW_S


def _ago(t, now):
    if not t:
        return "mai"
    s = int(now - t)
    if s < 60:
        return "adesso"
    if s < 3600:
        return "%d min fa" % (s // 60)
    return time.strftime("%d/%m %H:%M", time.localtime(t))


class Window:
    def __init__(self, app):
        self.app = app
        self.q = queue.Queue()
        self.last_show, self.seen_pending, self.sig, self.told_tray = 0.0, set(), None, False
        self.root = r = tk.Tk()
        r.title("TabDeck")
        r.configure(bg=BG)
        r.geometry("760x600")
        r.minsize(680, 540)
        try:
            r.iconbitmap(app.icon_path)
        except tk.TclError:
            pass
        r.protocol("WM_DELETE_WINDOW", self.hide)
        self._build()
        if app.start_hidden:
            r.withdraw()
        self.tray = app.make_tray(lambda: self.q.put(self.show), lambda: self.q.put(self.restart),
                                  lambda: self.q.put(self.quit))
        r.after(200, self._tick_fast)
        r.after(300, self._tick)

    # --- costruzione ---
    def _btn(self, parent, text, cmd, fg=TEXT, bg=PANEL2, big=False):
        b = tk.Label(parent, text=text, fg=fg, bg=bg, font=(FONT, 12 if big else 10, "bold"), padx=18 if big else 12,
                     pady=10 if big else 6, cursor="hand2")
        b.bind("<Button-1>", lambda e: cmd())
        b.bind("<Enter>", lambda e: b.configure(bg=LINE))
        b.bind("<Leave>", lambda e: b.configure(bg=bg))
        return b

    def _build(self):
        r = self.root
        head = tk.Frame(r, bg=BG)
        head.pack(fill="x", padx=16, pady=(14, 8))
        tk.Label(head, text="TABDECK", fg=AMBER, bg=BG, font=(MONO, 18, "bold")).pack(side="left")
        tk.Label(head, text=self.app.version, fg=DIM, bg=BG, font=(MONO, 11)).pack(side="left", padx=(8, 0), pady=(6, 0))
        self.upd = tk.Label(head, text="", fg=AMBER, bg=BG, font=(FONT, 10))
        self.upd.pack(side="right")
        self.stat = tk.Label(r, text="", fg=DIM, bg=BG, font=(FONT, 10), anchor="w")
        self.stat.pack(fill="x", padx=16)

        body = tk.Frame(r, bg=BG)
        body.pack(fill="both", expand=True, padx=16, pady=10)
        left = tk.Frame(body, bg=PANEL, padx=14, pady=12)
        left.pack(side="left", fill="y")
        tk.Label(left, text="COLLEGA UN TELEFONO", fg=AMBER, bg=PANEL, font=(MONO, 10, "bold")).pack(anchor="w")
        tk.Label(left, text="Inquadra con la fotocamera", fg=DIM, bg=PANEL, font=(FONT, 9)).pack(anchor="w", pady=(0, 8))
        self.qr = tk.Canvas(left, width=232, height=232, bg="#ffffff", highlightthickness=0)
        self.qr.pack()
        self.url = tk.Label(left, text="", fg=DIM, bg=PANEL, font=(MONO, 8), wraplength=232, justify="left")
        self.url.pack(anchor="w", pady=(8, 8))
        row = tk.Frame(left, bg=PANEL)
        row.pack(fill="x")
        self._btn(row, "Copia link", self.copy_link).pack(side="left")
        self._btn(row, "Nuovo link", self.new_link).pack(side="left", padx=(6, 0))
        self.openpc = self._btn(left, "Apri TabDeck sul PC", self.open_page, fg=AMBER, big=True)
        self.openpc.pack(fill="x", pady=(8, 0))

        right = tk.Frame(body, bg=PANEL, padx=14, pady=12)
        right.pack(side="left", fill="both", expand=True, padx=(12, 0))
        tk.Label(right, text="DISPOSITIVI", fg=AMBER, bg=PANEL, font=(MONO, 10, "bold")).pack(anchor="w")
        self.banner = tk.Frame(right, bg=PANEL)
        self.banner.pack(fill="x")
        self.adb = tk.Label(right, text="", fg=DIM, bg=PANEL, font=(FONT, 9), anchor="w")
        self.adb.pack(fill="x", pady=(2, 6))
        self.list = tk.Frame(right, bg=PANEL)
        self.list.pack(fill="both", expand=True)

        # annulla: torna alla configurazione di prima (pulsanti, scorciatoie, impostazioni), un passo per volta
        und = tk.Frame(r, bg=PANEL, padx=14, pady=8)
        und.pack(fill="x", padx=16, pady=(0, 10))
        self.undo_btn = self._btn(und, "Annulla ultima modifica", self.undo, big=True)
        self.undo_btn.pack(side="left")
        self.undo_lbl = tk.Label(und, text="", fg=DIM, bg=PANEL, font=(FONT, 11), anchor="w")
        self.undo_lbl.pack(side="left", fill="x", expand=True, padx=(10, 0))
        self._undone = None        # (etichetta, momento): "Annullato: ..." resta qualche secondo

        foot = tk.Frame(r, bg=BG)
        foot.pack(fill="x", padx=16, pady=(0, 14))
        self.req = tk.BooleanVar(value=self.app.devices.require)
        tk.Checkbutton(foot, text="Richiedi approvazione per i nuovi dispositivi", variable=self.req,
                       command=self.toggle_require, fg=TEXT, bg=BG, selectcolor=PANEL2, activebackground=BG,
                       activeforeground=TEXT, font=(FONT, 10)).pack(side="left")
        self._btn(foot, "Esci", self.quit, fg=ERR).pack(side="right")
        self._btn(foot, "Riavvia", self.restart).pack(side="right", padx=6)
        self._btn(foot, "Registro", self.show_log).pack(side="right")

    # --- ciclo ---
    def _tick_fast(self):
        try:
            while True:
                self.q.get_nowait()()
        except queue.Empty:
            pass
        if self.app.show_requested():
            self.show()
        self.root.after(200, self._tick_fast)

    def _tick(self):
        try:
            self.refresh()
        except Exception as e:   # un errore di disegno non deve fermare il ciclo
            print("finestra: %s" % e)
        self.root.after(1000, self._tick)

    def refresh(self):
        now = time.time()
        st = self.app.status()
        text = {"listening": "In ascolto su %s:%s" % (st.get("ip"), st.get("port")),
                "waiting": "In attesa della rete (%s)" % (st.get("ip") or "nessuna rete"),
                "blocked": "Rete non consentita (%s): TabDeck non ascolta qui" % st.get("ip")}.get(st.get("state"), "Avvio...")
        self.stat.configure(text=text, fg=OK if st.get("state") == "listening" else WARN)
        self.upd.configure(text=("Aggiornamento disponibile: %s" % st["update"]) if st.get("update") else "")
        adb = st.get("adb") or []
        self.adb.configure(text=("Tablet via USB: " + ", ".join(adb)) if adb else "")
        self.paint_undo(now)
        url = self.app.pair_url()
        self.openpc.configure(fg=AMBER if url else DIM)
        if url != getattr(self, "_url", None):
            self._url = url
            self.url.configure(text=url or "(nessuna rete)")
            self.draw_qr(url)
        store = self.app.devices
        if self.req.get() != store.require:
            self.req.set(store.require)
        rows = device_rows(store, now)
        new = [p for p in rows if p["kind"] == "pending" and p["id"] not in self.seen_pending]
        for p in new:
            self.seen_pending.add(p["id"])
            if self.tray:
                self.tray.notify("Nuovo dispositivo", "%s - codice %s" % (p["name"], p["code"]))
            if should_autoshow(self.last_show, now):
                self.last_show = now
                self.show()
        locked = store.locked_until > now
        sig = (locked, tuple((r["kind"], r["id"], r["name"], r.get("active"), r.get("code"),
                              _ago(r.get("last"), now)) for r in rows))
        if sig != self.sig:
            self.sig = sig
            self.draw_list(rows, locked, now)

    # --- disegno ---
    def draw_qr(self, url):
        c = self.qr
        c.delete("all")
        if not url:
            return
        m = self.app.qr_matrix(url)
        n = len(m)
        cell = max(1, 232 // (n + 8))      # 4 moduli di margine bianco per lato: i telefoni lo leggono meglio
        off = (232 - cell * n) // 2
        for y, line in enumerate(m):
            for x, on in enumerate(line):
                if on:
                    c.create_rectangle(off + x * cell, off + y * cell, off + (x + 1) * cell, off + (y + 1) * cell,
                                       fill="#000000", width=0)

    def draw_list(self, rows, locked, now):
        for w in self.banner.winfo_children() + self.list.winfo_children():
            w.destroy()
        if locked:
            b = tk.Frame(self.banner, bg="#3a1512", padx=10, pady=6)
            b.pack(fill="x", pady=(6, 0))
            tk.Label(b, text="Richieste sospese — qualcuno ha il tuo link", fg=ERR, bg="#3a1512",
                     font=(FONT, 10, "bold")).pack(side="left")
            self._btn(b, "Riprendi", self.app.devices.resume).pack(side="right")
        if not rows:
            tk.Label(self.list, text="Nessun dispositivo ancora.", fg=DIM, bg=PANEL, font=(FONT, 10)).pack(anchor="w")
        for r in rows[:12]:
            pend = r["kind"] == "pending"
            bg = "#2e2a10" if pend else PANEL2
            f = tk.Frame(self.list, bg=bg, padx=10, pady=6)
            f.pack(fill="x", pady=2)
            dot = tk.Canvas(f, width=10, height=10, bg=bg, highlightthickness=0)
            dot.create_oval(1, 1, 9, 9, fill=WARN if pend else (OK if r["active"] else LINE), width=0)
            dot.pack(side="left", padx=(0, 8))
            info = tk.Frame(f, bg=bg)
            info.pack(side="left", fill="x", expand=True)
            title = ("Nuovo dispositivo: %s" % r["name"]) if pend else r["name"]
            tk.Label(info, text=title, fg=TEXT, bg=bg, font=(FONT, 10, "bold"), anchor="w").pack(fill="x")
            sub = ("%s — codice %s" % (r["ip"], r["code"])) if pend else ("%s — visto %s" % (r["ip"], _ago(r["last"], now)))
            tk.Label(info, text=sub, fg=WARN if pend else DIM, bg=bg, font=(MONO if pend else FONT, 10 if pend else 9),
                     anchor="w").pack(fill="x")
            i = r["id"]
            if pend:
                self._btn(f, "Rifiuta", lambda i=i: self.app.devices.refuse(i), fg=ERR).pack(side="right")
                self._btn(f, "Approva", lambda i=i: self.app.devices.approve(i), fg=OK).pack(side="right", padx=6)
            else:
                self._btn(f, "Rimuovi", lambda i=i, n=r["name"]: self.remove(i, n)).pack(side="right")
                self._btn(f, "Rinomina", lambda i=i, n=r["name"]: self.rename(i, n)).pack(side="right", padx=6)

    # --- azioni ---
    def show(self):
        r = self.root
        self.app.hidden = False
        r.deiconify()
        r.lift()
        r.attributes("-topmost", True)
        r.after(300, lambda: r.attributes("-topmost", False))
        r.focus_force()

    def hide(self):
        self.root.withdraw()
        self.app.hidden = True
        if not self.told_tray and self.tray:
            self.told_tray = True
            self.tray.notify("TabDeck", "TabDeck resta attivo qui. Clic destro per uscire.")

    def copy_link(self):
        if self._url:
            self.root.clipboard_clear()
            self.root.clipboard_append(self._url)

    def new_link(self):
        store = self.app.devices
        if store.require:
            if not messagebox.askyesno("Nuovo link", "Creo un nuovo link e un nuovo QR?\n\nIl link vecchio smette di "
                                       "funzionare per i dispositivi nuovi. Quelli approvati restano collegati: "
                                       "controlla l'elenco e rimuovi quelli che non riconosci.", parent=self.root):
                return
        else:
            # approvazione spenta: chi ha usato il link vecchio e' gia' nell'elenco come approvato, quindi
            # cambiare solo il link non lo fermerebbe. Si scollegano tutti.
            if not messagebox.askyesno("Nuovo link", "Creo un nuovo link e un nuovo QR?\n\nL'approvazione e' spenta, "
                                       "quindi per chiudere fuori chi ha il link vecchio scollego TUTTI i dispositivi: "
                                       "ricollegali inquadrando il nuovo QR (il tablet via USB si riapre da solo).\n\n"
                                       "Consiglio: accendi anche \"Richiedi approvazione\".", parent=self.root):
                return
            store.revoke_all()
        self.app.rotate_token()
        self.refresh()

    def paint_undo(self, now):
        info = self.app.undo_info()
        self.undo_btn.configure(fg=TEXT if info else DIM)
        if self._undone and now - self._undone[1] < 5:
            self.undo_lbl.configure(text="Annullato: %s" % self._undone[0], fg=OK)
        else:
            self.undo_lbl.configure(text=undo_text(info, now), fg=DIM)

    def undo(self):
        label = self.app.undo()
        if label:
            self._undone = (label, time.time())
        self.paint_undo(time.time())

    def open_page(self):
        if not self.app.open_page():
            messagebox.showinfo("TabDeck", "TabDeck non e' in ascolto: accendi l'hotspot e riprova.", parent=self.root)

    def toggle_require(self):
        self.app.devices.set_require(self.req.get())

    def rename(self, dev_id, name):
        n = simpledialog.askstring("Rinomina", "Nome del dispositivo:", initialvalue=name, parent=self.root)
        if n:
            self.app.devices.rename(dev_id, n)

    def remove(self, dev_id, name):
        store = self.app.devices
        if store.require:
            if messagebox.askyesno("Rimuovi", "Rimuovere %s?\n\nAlla sua prossima azione vedra' un codice e "
                                   "dovrai approvarlo di nuovo da qui." % name, parent=self.root):
                store.remove(dev_id)
            return
        # approvazione spenta: basta il link per rientrare, quindi togliere e basta non servirebbe a niente
        ans = messagebox.askyesnocancel(
            "Rimuovi", "L'approvazione e' spenta: con il link %s potrebbe rientrare subito.\n\n"
            "Si = accendo l'approvazione e lo rimuovo (dovra' essere approvato di nuovo)\n"
            "No = lo tolgo solo dall'elenco\nAnnulla = lascio tutto com'e'" % name, parent=self.root)
        if ans is None:
            return
        if ans:
            store.set_require(True)
            self.req.set(True)
        store.remove(dev_id)

    def show_log(self):
        t = tk.Toplevel(self.root, bg=BG)
        t.title("TabDeck - registro")
        t.geometry("760x420")
        txt = tk.Text(t, bg=PANEL, fg=TEXT, font=(MONO, 9), insertbackground=TEXT, relief="flat", wrap="none")
        txt.pack(fill="both", expand=True)
        txt.insert("end", "\n".join(self.app.log_tail()) or "(registro vuoto: con la console i messaggi vanno li')")
        txt.see("end")
        txt.configure(state="disabled")

    def restart(self):
        self.app.restart(hidden=self.app.hidden)

    def quit(self):
        self.app.quit()


def run(app):
    """app: version, icon_path, start_hidden, devices (DeviceStore), status() -> dict, pair_url() -> str|None,
    qr_matrix(text), rotate_token(), log_tail(), show_requested(), make_tray(on_open, on_restart, on_quit) -> Tray|None,
    restart(hidden), quit(), undo_info() -> {"label","t"}|None, undo() -> etichetta|None, open_page() -> bool."""
    w = Window(app)
    w.root.mainloop()
