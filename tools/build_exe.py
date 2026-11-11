"""Construit dist/Downloads Manager.exe (un seul fichier, sans console).

Usage : .venv\\Scripts\\python tools\\build_exe.py   (reconstruit d'abord l'interface si `web/` a changé : npm run build)
"""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ICON = ROOT / "assets" / "downloads-manager.ico"


def main():
    if not (ROOT / "dm" / "static" / "index.html").exists():
        sys.exit("Interface absente : lance d'abord `npm run build` dans web/.")
    if not ICON.exists():
        sys.path.insert(0, str(ROOT))
        from dm.autostart import app_icon
        ICON.parent.mkdir(parents=True, exist_ok=True)
        app_icon().save(ICON, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (256, 256)])
    shutil.rmtree(ROOT / "build", ignore_errors=True)
    subprocess.run([
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--windowed",
        "--name", "Downloads Manager",
        "--icon", str(ICON),
        "--add-data", f"{ROOT / 'dm' / 'static'};dm/static",
        "--collect-submodules", "uvicorn",
        "--collect-all", "winrt",
        "--collect-all", "windows_toasts",
        "--hidden-import", "pystray._win32",
        "--distpath", str(ROOT / "dist"),
        "--workpath", str(ROOT / "build"),
        "--specpath", str(ROOT / "build"),
        str(ROOT / "launcher.py"),
    ], check=True, cwd=ROOT)
    print(f"\nOK : {ROOT / 'dist' / 'Downloads Manager.exe'}")


if __name__ == "__main__":
    main()
