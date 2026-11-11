"""Ouvre un dossier ou un fichier et ramène la fenêtre au premier plan.

Lancé depuis une appli en arrière-plan (l'exe sans console), Windows refuse de donner le focus à la nouvelle
fenêtre : elle s'ouvre derrière le navigateur. On repère la fenêtre apparue puis on la passe devant
(astuce de la touche Alt simulée, qui lève le verrou de premier plan).
"""
import ctypes
import threading
import time
from ctypes import wintypes

user32 = ctypes.WinDLL("user32")
EnumProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
VK_MENU, KEYEVENTF_KEYUP, SW_RESTORE = 0x12, 0x0002, 9


def _windows() -> dict[int, str]:
    """Fenêtres de premier niveau visibles et titrées : {hwnd: titre}."""
    found = {}

    def cb(h, _):
        if user32.IsWindowVisible(h):
            buf = ctypes.create_unicode_buffer(512)
            if user32.GetWindowTextW(h, buf, 512):
                found[h] = buf.value
        return True

    user32.EnumWindows(EnumProc(cb), 0)
    return found


def _raise(hwnd: int):
    user32.keybd_event(VK_MENU, 0, 0, 0)
    user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
    user32.SetForegroundWindow(hwnd)


def launch(start, title: str | None = None, timeout: float = 4.0):
    """Exécute start() puis passe devant la fenêtre qui apparaît (titre commençant par `title` si donné).

    Si aucune nouvelle fenêtre ne vient (l'Explorateur a réutilisé une fenêtre déjà ouverte), on ramène
    celle qui porte ce titre.
    """
    before = set(_windows())
    start()

    def match(t: str) -> bool:
        return title is None or t.startswith(title + " ")

    def watch():
        t0 = time.time()
        while time.time() - t0 < timeout:
            wins = _windows()
            fresh = [h for h, t in wins.items() if h not in before and match(t)]
            old = [h for h, t in wins.items() if title and match(t)]
            if fresh or (old and time.time() - t0 > 0.8):
                _raise((fresh or old)[0])
                return
            time.sleep(0.1)

    threading.Thread(target=watch, daemon=True).start()
