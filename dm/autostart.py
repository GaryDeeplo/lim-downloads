"""Raccourcis Windows : menu Démarrer (ouvre l'interface) et dossier Démarrage (icône seule, à l'ouverture de session)."""
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

from .config import FROZEN, PROJECT_DIR as PROJECT
from .i18n import tr

APPDATA = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
PROGRAMS = APPDATA / "Microsoft" / "Windows" / "Start Menu" / "Programs"
START_MENU = PROGRAMS / "Lim.lnk"
STARTUP = PROGRAMS / "Startup" / "Lim.lnk"
OLD_START_MENU, OLD_STARTUP = PROGRAMS / "Downloads Manager.lnk", PROGRAMS / "Startup" / "Downloads Manager.lnk"  # ancien nom
ICON = (Path(sys.executable) if FROZEN else PROJECT / "assets" / "lim.ico")  # l'exe porte son icône


ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)
INK, CREAM, EYE = (27, 26, 23), (251, 246, 234), (95, 240, 224)
ORANGE, ORANGE_DARK, ORANGE_LIGHT = (255, 90, 31), (178, 54, 10), (255, 138, 84)


def app_icon(size: int = 256) -> Image.Image:
    """Lim, le robot guide, qui sort du dossier orange. En petit (barre des tâches), le dessin se simplifie."""
    simple = size <= 32
    s = 8 * size / 64                      # dessiné sur une grille de 64, rendu 8× puis réduit : bords nets
    big = Image.new("RGBA", (round(64 * s), round(64 * s)), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    box = lambda x0, y0, x1, y1: (x0 * s, y0 * s, x1 * s, y1 * s)
    line = (3.2 if simple else 2.2) * s

    # dos du dossier et son onglet
    d.rounded_rectangle(box(4, 14, 28, 26), 4 * s, fill=ORANGE_DARK)
    d.rounded_rectangle(box(4, 18, 60, 58), 7 * s, fill=ORANGE_DARK)

    # Lim : antenne, oreilles, tête, visière, yeux
    if not simple:
        d.line(box(32, 9, 32, 3.5), fill=(120, 113, 102), width=round(2 * s))  # gris : visible sur fond clair comme sombre
        d.ellipse(box(29.2, 0.8, 34.8, 6.4), fill=ORANGE, outline=INK, width=round(1.3 * s))
        d.rounded_rectangle(box(9.5, 17, 14, 27), 2 * s, fill=ORANGE, outline=INK, width=round(1.4 * s))
        d.rounded_rectangle(box(50, 17, 54.5, 27), 2 * s, fill=ORANGE, outline=INK, width=round(1.4 * s))
    d.rounded_rectangle(box(12.5, 8, 51.5, 40), 11 * s, fill=CREAM, outline=INK, width=round(line))
    d.rounded_rectangle(box(17.5, 13, 46.5, 29), 7 * s, fill=INK)
    ey = (16, 26.5) if simple else (16.5, 25.5)
    d.rounded_rectangle(box(22.5, ey[0], 28.5, ey[1]), 3 * s, fill=EYE)
    d.rounded_rectangle(box(35.5, ey[0], 41.5, ey[1]), 3 * s, fill=EYE)
    if not simple:
        d.rounded_rectangle(box(23.8, 17.6, 25.6, 19.8), 0.9 * s, fill=(255, 255, 255))
        d.rounded_rectangle(box(36.8, 17.6, 38.6, 19.8), 0.9 * s, fill=(255, 255, 255))

    # rabat avant du dossier, légèrement dégradé, qui cache le bas de Lim
    front = Image.new("RGBA", big.size, (0, 0, 0, 0))
    mask = Image.new("L", big.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(box(4, 31, 60, 60), 8 * s, fill=255)
    fd = ImageDraw.Draw(front)
    top, bottom = 31 * s, 60 * s
    for y in range(round(top), round(bottom) + 1):
        t = (y - top) / (bottom - top)
        c = tuple(round(ORANGE_LIGHT[i] + (ORANGE[i] - ORANGE_LIGHT[i]) * min(1, t * 1.6)) for i in range(3))
        fd.line((0, y, big.width, y), fill=c + (255,))
    big.paste(front, (0, 0), mask)
    if not simple:  # liseré clair en haut du rabat
        d.rounded_rectangle(box(6, 31.6, 58, 33.4), 1 * s, fill=(255, 176, 138))

    return big.resize((size, size), Image.LANCZOS)


def save_icon(path: Path):
    """Fichier .ico multi-tailles, chaque taille dessinée pour elle-même."""
    path.parent.mkdir(parents=True, exist_ok=True)
    images = [app_icon(n) for n in ICON_SIZES]
    images[-1].save(path, format="ICO", sizes=[(n, n) for n in ICON_SIZES], append_images=images[:-1])


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
        save_icon(ICON)
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
        _make_shortcut(STARTUP, "--hidden", tr("Lim : tri automatique au démarrage"))
    elif STARTUP.exists():
        STARTUP.unlink()


def install():
    """Menu Démarrer + lancement à l'ouverture de session."""
    _make_shortcut(START_MENU, "", tr("Lim : trier le dossier Téléchargements"))
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
    """Au lancement de l'exe : les raccourcis existants sont repointés vers lui (ex. après passage des sources à l'exe).
    Les raccourcis de l'ancien nom « Downloads Manager » sont remplacés par ceux de Lim, démarrage compris."""
    if OLD_STARTUP.exists():
        OLD_STARTUP.unlink()
        set_startup(True)
    if OLD_START_MENU.exists():
        OLD_START_MENU.unlink()
    if not points_here(START_MENU):
        _make_shortcut(START_MENU, "", tr("Lim : trier le dossier Téléchargements"))
    if STARTUP.exists() and not points_here(STARTUP):
        set_startup(True)


if __name__ == "__main__":
    install()
    print(f"Raccourcis créés :\n  {START_MENU}\n  {STARTUP}")
