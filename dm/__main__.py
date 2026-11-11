"""Lancement : python -m dm (ou pythonw -m dm, sans console).

Serveur local + tri automatique + icône dans la barre des tâches + notifications Windows.
Une seule instance : si l'appli tourne déjà, on ouvre simplement l'interface.
"""
import os
import socket
import sys
import threading
import urllib.request
import webbrowser

import uvicorn

from .autostart import app_icon, refresh, set_startup, startup_enabled
from .config import load_config
from .server import create_app

PORT = int(os.environ.get("DM_PORT", 8765))  # DM_PORT : autre instance (démo)
URL = f"http://127.0.0.1:{PORT}"


def already_running() -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", PORT)) == 0


def notifier(app):
    """Notification Windows après un tri auto, avec « Annuler » et « Ouvrir »."""
    try:
        from windows_toasts import InteractableWindowsToaster, Toast, ToastButton
    except ImportError:
        return None
    toaster = InteractableWindowsToaster("Downloads Manager")

    def notify(batches: list[dict]):
        n = sum(b["done"] for b in batches)
        names = [name for b in batches for name in b["names"]]
        where = ", ".join(sorted({b["label"].split("→")[-1].strip() for b in batches}))
        toast = Toast([f"{n} téléchargement{'s' if n > 1 else ''} rangé{'s' if n > 1 else ''} automatiquement",
                       f"→ {where}", ", ".join(names[:3]) + (" …" if len(names) > 3 else "")])
        ids = ",".join(str(b["batch_id"]) for b in batches)
        toast.AddAction(ToastButton("Annuler", f"undo:{ids}"))
        toast.AddAction(ToastButton("Ouvrir", "open"))

        def activated(args):
            arg = getattr(args, "arguments", "") or "open"
            if arg.startswith("undo:"):
                for batch_id in arg[5:].split(","):  # via l'API : même chemin que le bouton Annuler de l'interface
                    try:
                        urllib.request.urlopen(urllib.request.Request(f"{URL}/api/undo/{batch_id}", method="POST"), timeout=600)
                    except OSError:
                        pass
                toaster.show_toast(Toast(["Tri automatique annulé", "Les fichiers sont revenus dans Téléchargements."]))
            else:
                webbrowser.open(URL)

        toast.on_activated = activated
        toaster.show_toast(toast)

    return notify


def main():
    hidden = "--hidden" in sys.argv  # --hidden : lancé à l'ouverture de session, juste l'icône
    if already_running():
        if not hidden:
            webbrowser.open(URL)
        return

    cfg = load_config()
    if sys.stderr is None:  # pythonw : pas de console, on écrit les journaux dans un fichier
        cfg.data_dir.mkdir(parents=True, exist_ok=True)
        sys.stdout = sys.stderr = open(cfg.data_dir / "downloads-manager.log", "a", encoding="utf-8", buffering=1)
    app = create_app(cfg, start_auto=True)
    if getattr(sys, "frozen", False):
        threading.Thread(target=refresh, daemon=True).start()
    app.state.notify = notifier(app)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    if not hidden:
        threading.Timer(1.2, lambda: webbrowser.open(URL)).start()

    try:
        import pystray
    except ImportError:  # pas d'icône : on garde le serveur au premier plan
        threading.Event().wait()
        return

    auto = app.state.auto

    def toggle(icon, _item):
        auto.set_enabled(not auto.enabled)
        icon.update_menu()

    def toggle_startup(icon, _item):
        try:
            set_startup(not startup_enabled())
        except Exception as e:
            print(f"démarrage avec Windows : {e}")
        icon.update_menu()

    def run_now(_icon, _item):
        threading.Thread(target=auto.run_once, daemon=True).start()

    def quit_app(icon, _item):
        auto.stop()
        server.should_exit = True
        icon.stop()

    menu = pystray.Menu(
        pystray.MenuItem("Ouvrir Downloads Manager", lambda: webbrowser.open(URL), default=True),
        pystray.MenuItem("Tri automatique", toggle, checked=lambda _: auto.enabled),
        pystray.MenuItem("Trier maintenant", run_now),
        pystray.MenuItem("Lancer au démarrage de Windows", toggle_startup, checked=lambda _: startup_enabled()),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quitter", quit_app),
    )
    pystray.Icon("downloads-manager", app_icon(64), "Downloads Manager", menu).run()


if __name__ == "__main__":
    main()
