"""TabDeck - icona nell'area di notifica (vicino all'orologio), solo ctypes.

Clic sinistro = apri la finestra; clic destro = menu (Apri TabDeck / Riavvia / Esci); notify() = fumetto.
Gira su un thread suo con una finestra nascosta che riceve i messaggi dell'icona. Le callback vengono chiamate
da quel thread: chi le usa deve passare al thread della finestra (Tk) da solo.
"""
import ctypes
import threading
from ctypes import wintypes as W

_u32 = ctypes.WinDLL("user32", use_last_error=True)
_sh = ctypes.WinDLL("shell32")
_k32 = ctypes.WinDLL("kernel32")

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, W.HWND, W.UINT, W.WPARAM, W.LPARAM)

WM_DESTROY, WM_CLOSE, WM_COMMAND, WM_USER, WM_NULL = 0x0002, 0x0010, 0x0111, 0x0400, 0x0000
WM_LBUTTONUP, WM_RBUTTONUP, WM_CONTEXTMENU = 0x0202, 0x0205, 0x007B
WM_TRAY, WM_NOTIFY_REQ = WM_USER + 1, WM_USER + 2
NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
NIF_MESSAGE, NIF_ICON, NIF_TIP, NIF_INFO = 0x1, 0x2, 0x4, 0x10
NIIF_INFO = 0x1
IMAGE_ICON, LR_LOADFROMFILE, LR_DEFAULTSIZE = 1, 0x10, 0x40
MF_STRING, MF_SEPARATOR = 0x0, 0x800
TPM_RIGHTBUTTON, TPM_RETURNCMD, TPM_NONOTIFY = 0x2, 0x100, 0x80
ID_OPEN, ID_RESTART, ID_QUIT = 1, 2, 3


class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", W.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int), ("hInstance", W.HINSTANCE), ("hIcon", W.HICON),
                ("hCursor", W.HANDLE), ("hbrBackground", W.HBRUSH), ("lpszMenuName", W.LPCWSTR),
                ("lpszClassName", W.LPCWSTR)]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [("cbSize", W.DWORD), ("hWnd", W.HWND), ("uID", W.UINT), ("uFlags", W.UINT),
                ("uCallbackMessage", W.UINT), ("hIcon", W.HICON), ("szTip", W.WCHAR * 128),
                ("dwState", W.DWORD), ("dwStateMask", W.DWORD), ("szInfo", W.WCHAR * 256),
                ("uVersion", W.UINT), ("szInfoTitle", W.WCHAR * 64), ("dwInfoFlags", W.DWORD),
                ("guidItem", ctypes.c_byte * 16), ("hBalloonIcon", W.HICON)]


_u32.DefWindowProcW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]
_u32.DefWindowProcW.restype = LRESULT
_u32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
_u32.RegisterClassW.restype = W.ATOM
_u32.CreateWindowExW.argtypes = [W.DWORD, W.LPCWSTR, W.LPCWSTR, W.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                 ctypes.c_int, W.HWND, W.HMENU, W.HINSTANCE, W.LPVOID]
_u32.CreateWindowExW.restype = W.HWND
_u32.LoadImageW.argtypes = [W.HINSTANCE, W.LPCWSTR, W.UINT, ctypes.c_int, ctypes.c_int, W.UINT]
_u32.LoadImageW.restype = W.HANDLE
_u32.GetMessageW.argtypes = [ctypes.POINTER(W.MSG), W.HWND, W.UINT, W.UINT]
_u32.TranslateMessage.argtypes = _u32.DispatchMessageW.argtypes = [ctypes.POINTER(W.MSG)]
_u32.PostMessageW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]
_u32.DestroyWindow.argtypes = [W.HWND]
_u32.CreatePopupMenu.restype = W.HMENU
_u32.AppendMenuW.argtypes = [W.HMENU, W.UINT, ctypes.c_size_t, W.LPCWSTR]
_u32.TrackPopupMenu.argtypes = [W.HMENU, W.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int, W.HWND, W.LPVOID]
_u32.DestroyMenu.argtypes = [W.HMENU]
_u32.SetForegroundWindow.argtypes = [W.HWND]
_u32.GetCursorPos.argtypes = [ctypes.POINTER(W.POINT)]
_u32.RegisterWindowMessageW.argtypes = [W.LPCWSTR]
_u32.RegisterWindowMessageW.restype = W.UINT
_u32.DestroyIcon.argtypes = [W.HICON]
_k32.GetModuleHandleW.argtypes = [W.LPCWSTR]
_k32.GetModuleHandleW.restype = W.HMODULE
_sh.Shell_NotifyIconW.argtypes = [W.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
_sh.Shell_NotifyIconW.restype = W.BOOL


class Tray:
    _n = 0

    def __init__(self, icon_path, tooltip, on_open, on_restart, on_quit):
        self.icon_path, self.tooltip = icon_path, tooltip[:127]
        self.on_open, self.on_restart, self.on_quit = on_open, on_restart, on_quit
        self.hwnd = None
        self.added = False
        self.ready = threading.Event()
        self.thread = None
        self._balloon = ("", "")
        self._proc = WNDPROC(self._wndproc)    # riferimento tenuto: senza, il callback verrebbe liberato
        self._taskbar_created = _u32.RegisterWindowMessageW("TaskbarCreated")

    def start(self):
        self.thread = threading.Thread(target=self._run, name="tray", daemon=True)
        self.thread.start()

    def notify(self, title, text):
        self._balloon = (title[:63], text[:255])
        if self.hwnd:
            _u32.PostMessageW(self.hwnd, WM_NOTIFY_REQ, 0, 0)

    def stop(self):
        if self.hwnd:
            _u32.PostMessageW(self.hwnd, WM_CLOSE, 0, 0)

    # --- thread dell'icona ---
    def _nid(self, flags):
        n = NOTIFYICONDATAW()
        n.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        n.hWnd, n.uID, n.uFlags = self.hwnd, 1, flags
        n.uCallbackMessage, n.hIcon = WM_TRAY, self._hicon
        n.szTip = self.tooltip
        return n

    def _add(self):
        self.added = bool(_sh.Shell_NotifyIconW(NIM_ADD, ctypes.byref(self._nid(NIF_MESSAGE | NIF_ICON | NIF_TIP))))

    def _run(self):
        hinst = _k32.GetModuleHandleW(None)
        Tray._n += 1
        cls = "TabDeckTray%d" % Tray._n
        wc = WNDCLASSW()
        wc.lpfnWndProc, wc.hInstance, wc.lpszClassName = self._proc, hinst, cls
        _u32.RegisterClassW(ctypes.byref(wc))
        self.hwnd = _u32.CreateWindowExW(0, cls, "TabDeck", 0, 0, 0, 0, 0, None, None, hinst, None)
        self._hicon = _u32.LoadImageW(None, self.icon_path, IMAGE_ICON, 0, 0, LR_LOADFROMFILE | LR_DEFAULTSIZE)
        self._add()
        self.ready.set()
        msg = W.MSG()
        while _u32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            _u32.TranslateMessage(ctypes.byref(msg))
            _u32.DispatchMessageW(ctypes.byref(msg))

    def _menu(self):
        m = _u32.CreatePopupMenu()
        _u32.AppendMenuW(m, MF_STRING, ID_OPEN, "Apri TabDeck")
        _u32.AppendMenuW(m, MF_STRING, ID_RESTART, "Riavvia")
        _u32.AppendMenuW(m, MF_SEPARATOR, 0, None)
        _u32.AppendMenuW(m, MF_STRING, ID_QUIT, "Esci")
        pt = W.POINT()
        _u32.GetCursorPos(ctypes.byref(pt))
        _u32.SetForegroundWindow(self.hwnd)    # senza, il menu non si chiude cliccando fuori
        cmd = _u32.TrackPopupMenu(m, TPM_RIGHTBUTTON | TPM_RETURNCMD | TPM_NONOTIFY, pt.x, pt.y, 0, self.hwnd, None)
        _u32.PostMessageW(self.hwnd, WM_NULL, 0, 0)
        _u32.DestroyMenu(m)
        return cmd

    def _call(self, fn):
        try:
            fn()
        except Exception as e:   # una callback rotta non deve far sparire l'icona
            print("tray: %s" % e)

    def _wndproc(self, hwnd, msg, wp, lp):
        if msg == WM_TRAY:
            ev = lp & 0xFFFF
            if ev == WM_LBUTTONUP:
                self._call(self.on_open)
            elif ev in (WM_RBUTTONUP, WM_CONTEXTMENU):
                cmd = self._menu()
                if cmd:
                    self._call({ID_OPEN: self.on_open, ID_RESTART: self.on_restart, ID_QUIT: self.on_quit}[cmd])
            return 0
        if msg == WM_NOTIFY_REQ:
            n = self._nid(NIF_INFO)
            n.szInfoTitle, n.szInfo = self._balloon
            n.dwInfoFlags = NIIF_INFO
            _sh.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(n))
            return 0
        if msg == self._taskbar_created and msg:   # Esplora risorse riavviato: l'icona va rimessa
            self._add()
            return 0
        if msg == WM_CLOSE:
            _sh.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._nid(0)))
            self.added = False
            if self._hicon:
                _u32.DestroyIcon(self._hicon)
            _u32.DestroyWindow(hwnd)
            return 0
        if msg == WM_DESTROY:
            _u32.PostQuitMessage(0)
            return 0
        return _u32.DefWindowProcW(hwnd, msg, wp, lp)
