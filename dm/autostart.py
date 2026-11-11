"""Raccourcis Windows : menu Démarrer (ouvre l'interface) et dossier Démarrage (icône seule, à l'ouverture de session)."""
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

from .config import FROZEN, PROJECT_DIR as PROJECT

APPDATA = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
START_MENU = APPDATA / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Downloads Manager.lnk"
STARTUP = APPDATA / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "Downloads Manager.lnk"
ICON = (Path(sys.executable) if FROZEN else PROJECT / "assets" / "downloads-manager.ico")  # l'exe porte son icône


def app_icon(size: int = 256) -> Image.Image:
    """Dossier orange avec une feuille qui dépasse : même dessin que l'icône de la barre des tâches."""
    k = size / 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((14 * k, 6 * k, 50 * k, 34 * k), 4 * k, fill=(251, 250, 246))
    d.rounded_rectangle((4 * k, 16 * k, 28 * k, 28 * k), 5 * k, fill=(196, 61, 12))
    d.rounded_rectangle((4 * k, 22 * k, 60 * k, 58 * k), 8 * k, fill=(255, 90, 31))
    return img


def _launcher(args: str) -> tuple[str, str]:
    """(cible, arguments) : l'exe lui-même, ou pythonw -m dm depuis les sources."""
    if FROZEN:
        return sys.executable, args
    exe = Path(sys.executable)
    pythonw = exe.with_name("pythonw.exe")
    return str(pythonw if pythonw.exists() else exe), f"-m dm {args}".strip()


def _make_shortcut(path: Path, args: str, description: str):
    target, args = _launcher(args)
    if not ICON.exists():
        ICON.parent.mkdir(parents=True, exist_ok=True)
        app_icon().save(ICON, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (256, 256)])
    path.parent.mkdir(parents=True, exist_ok=True)
    q = lambda v: str(v).replace("'", "''")
    script = (
        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}'); "
        "$s.TargetPath = '{target}'; $s.Arguments = '{args}'; $s.WorkingDirectory = '{cwd}'; "
        "$s.IconLocation = '{icon}'; $s.Description = '{desc}'; $s.Save()"
    ).format(lnk=q(path), target=q(target), args=q(args), cwd=q(PROJECT), icon=q(ICON), desc=q(description))
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], check=True,
                   capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)


def startup_enabled() -> bool:
    return STARTUP.exists()


def set_startup(enabled: bool):
    if enabled:
        _make_shortcut(STARTUP, "--hidden", "Downloads Manager : tri automatique au démarrage")
    elif STARTUP.exists():
        STARTUP.unlink()


def install():
    """Menu Démarrer + lancement à l'ouverture de session."""
    _make_shortcut(START_MENU, "", "Downloads Manager : trier le dossier Téléchargements")
    set_startup(True)


def points_here(path: Path) -> bool:
    """Le raccourci lance-t-il bien ce programme-ci (exe ou sources) ?"""
    if not path.exists():
        return False
    target, _ = _launcher("")
    script = f"(New-Object -ComObject WScript.Shell).CreateShortcut('{str(path).replace(chr(39), chr(39) * 2)}').TargetPath"
    out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], capture_output=True,
                         text=True, creationflags=subprocess.CREATE_NO_WINDOW).stdout.strip()
    return os.path.normcase(out) == os.path.normcase(target)


def refresh():
    """Au lancement de l'exe : les raccourcis existants sont repointés vers lui (ex. après passage des sources à l'exe)."""
    if not points_here(START_MENU):
        _make_shortcut(START_MENU, "", "Downloads Manager : trier le dossier Téléchargements")
    if STARTUP.exists() and not points_here(STARTUP):
        set_startup(True)


if __name__ == "__main__":
    install()
    print(f"Raccourcis créés :\n  {START_MENU}\n  {STARTUP}")
