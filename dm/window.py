"""Fenêtre de l'appli (WebView2, le moteur web intégré à Windows) : plus besoin d'ouvrir un navigateur.

Fermer la fenêtre la cache seulement : l'appli reste dans la zone de notification pour le tri auto.
Sans WebView2 (ou sans pywebview), on retombe sur le navigateur par défaut.
"""
import threading
from pathlib import Path


class AppWindow:
    def __init__(self, url: str, hidden: bool, storage: Path, icon: Path | None = None):
        import webview  # importé ici : l'appli doit démarrer même sans pywebview

        self.webview = webview
        self.storage = storage
        self.icon = icon
        self.quitting = False
        self.ready = threading.Event()
        self.win = webview.create_window(
            "Downloads Manager", url, width=1440, height=900, min_size=(960, 640), maximized=not hidden,
            hidden=hidden, text_select=True, draggable=True, background_color="#121211",
        )
        self.win.events.closing += self._closing
        self.win.events.shown += lambda: self.ready.set()

    def _closing(self):
        if self.quitting:
            return True
        self.win.hide()  # la croix range l'appli près de l'horloge au lieu de la quitter
        return False

    def show(self):
        self.win.show()
        self.win.restore()
        # passer devant les autres fenêtres : on bascule « toujours au-dessus » le temps d'un instant
        self.win.on_top = True
        self.win.on_top = False

    def quit(self):
        self.quitting = True
        self.win.destroy()

    def run(self):
        """Boucle de la fenêtre : bloque le fil principal jusqu'à « Quitter »."""
        self.storage.mkdir(parents=True, exist_ok=True)
        icon = str(self.icon) if self.icon and self.icon.suffix == ".ico" and self.icon.exists() else None
        # private_mode=False : le navigateur intégré garde ses réglages (zoom, guide déjà vu…) d'un lancement à l'autre
        self.webview.start(gui="edgechromium", private_mode=False, storage_path=str(self.storage), icon=icon)
