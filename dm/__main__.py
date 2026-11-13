"""Lancement : python -m dm (ou pythonw -m dm, sans console).

Serveur local + fenêtre de l'appli (WebView2) + tri automatique + icône près de l'horloge + notifications Windows.
Une seule instance : si l'appli tourne déjà, on ramène simplement sa fenêtre.
"""
import os
import socket
import sys
import json
import threading
import time
import urllib.request
import webbrowser

import uvicorn

from .autostart import ICON, app_icon, refresh, set_startup, startup_enabled
from .config import load_config
from .i18n import tr
from .server import APP_HEADER, create_app

PORT = int(os.environ.get("DM_PORT", 8765))  # DM_PORT : autre instance (démo)
URL = f"http://127.0.0.1:{PORT}"


def already_running() -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", PORT)) == 0


def show_running():
    """Deuxième lancement : demande à l'appli déjà ouverte de montrer sa fenêtre (navigateur si elle n'en a pas)."""
    try:
        with urllib.request.urlopen(urllib.request.Request(f"{URL}/api/show", method="POST", headers={APP_HEADER: "1"}), timeout=5) as r:
            if json.load(r).get("window"):
                return
    except (OSError, ValueError):
        pass
    webbrowser.open(URL)


def open_window(cfg, hidden: bool):
    """La fenêtre WebView2, ou None si elle n'est pas disponible (on passera alors par le navigateur)."""
    try:
        from .window import AppWindow
        return AppWindow(URL, hidden, cfg.data_dir / "webview", ICON)
    except Exception as e:  # pywebview absent ou WebView2 indisponible
        print(f"fenêtre de l'appli indisponible, navigateur à la place : {e}")
        return None


def notifier(app, open_ui):
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
        title = (tr("{n} téléchargements rangés automatiquement", n=n) if n > 1
                 else tr("{n} téléchargement rangé automatiquement", n=n))
        toast = Toast([title, f"→ {where}", ", ".join(names[:3]) + (" …" if len(names) > 3 else "")])
        ids = ",".join(str(b["batch_id"]) for b in batches)
        toast.AddAction(ToastButton(tr("Annuler"), f"undo:{ids}"))
        toast.AddAction(ToastButton(tr("Ouvrir"), "open"))

        def activated(args):
            arg = getattr(args, "arguments", "") or "open"
            if arg.startswith("undo:"):
                for batch_id in arg[5:].split(","):  # via l'API : même chemin que le bouton Annuler de l'interface
                    try:
                        urllib.request.urlopen(urllib.request.Request(f"{URL}/api/undo/{batch_id}", method="POST", headers={APP_HEADER: "1"}), timeout=600)
                    except OSError:
                        pass
                toaster.show_toast(Toast([tr("Tri automatique annulé"), tr("Les fichiers sont revenus dans Téléchargements.")]))
            else:
                open_ui()

        toast.on_activated = activated
        toaster.show_toast(toast)

    return notify


def main():
    hidden = "--hidden" in sys.argv  # --hidden : lancé à l'ouverture de session, juste l'icône
    if already_running():
        if not hidden:
            show_running()
        return

    cfg = load_config()
    if sys.stderr is None:  # pythonw : pas de console, on écrit les journaux dans un fichier
        cfg.data_dir.mkdir(parents=True, exist_ok=True)
        sys.stdout = sys.stderr = open(cfg.data_dir / "downloads-manager.log", "a", encoding="utf-8", buffering=1)
    app = create_app(cfg, start_auto=True)
    if getattr(sys, "frozen", False):
        threading.Thread(target=refresh, daemon=True).start()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(100):  # la fenêtre charge la page dès son ouverture : on attend que le serveur réponde
        if server.started:
            break
        time.sleep(0.1)

    window = open_window(cfg, hidden)

    def open_ui():
        if window:
            window.show()
        else:
            webbrowser.open(URL)

    app.state.show_window = window.show if window else None
    app.state.notify = notifier(app, open_ui)
    if not window and not hidden:
        webbrowser.open(URL)

    try:
        import pystray
    except ImportError:  # pas d'icône : la fenêtre (ou le serveur) garde la main
        if window:
            window.run()
        else:
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
        if window:
            window.quit()

    menu = pystray.Menu(
        pystray.MenuItem(tr("Ouvrir Downloads Manager"), lambda: open_ui(), default=True),
        pystray.MenuItem(tr("Tri automatique"), toggle, checked=lambda _: auto.enabled),
        pystray.MenuItem(tr("Trier maintenant"), run_now),
        pystray.MenuItem(tr("Lancer au démarrage de Windows"), toggle_startup, checked=lambda _: startup_enabled()),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(tr("Quitter"), quit_app),
    )
    tray = pystray.Icon("downloads-manager", app_icon(64), "Downloads Manager", menu)
    if window:  # la fenêtre a besoin du fil principal ; l'icône tourne à côté
        tray.run_detached()
        window.run()
    else:
        tray.run()


if __name__ == "__main__":
    main()
