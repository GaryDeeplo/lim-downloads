"""Destinations hors du disque système : OneDrive, Google Drive pour ordinateur, disque externe."""
import ctypes
import os
import shutil
import string
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .config import Config

ARCHIVE_DIR = "Téléchargements archivés"
DRIVE_REMOVABLE, DRIVE_FIXED = 2, 3


@dataclass
class Remote:
    key: str                # onedrive | gdrive | external
    label: str
    root: Path | None       # None = indisponible
    free: int | None        # octets libres (quota restant pour Google Drive), None si inconnu
    hint: str               # pourquoi c'est indisponible / ce que ça fait

    @property
    def available(self) -> bool:
        return self.root is not None


def _volume_label(letter: str) -> str:
    buf = ctypes.create_unicode_buffer(261)
    ok = ctypes.windll.kernel32.GetVolumeInformationW(f"{letter}:\\", buf, 261, None, None, None, None, 0)
    return buf.value if ok else ""


def _drives() -> list[tuple[str, int, str]]:
    mask = ctypes.windll.kernel32.GetLogicalDrives()
    out = []
    for i, letter in enumerate(string.ascii_uppercase):
        if mask & (1 << i):
            dtype = ctypes.windll.kernel32.GetDriveTypeW(f"{letter}:\\")
            out.append((letter, dtype, _volume_label(letter)))
    return out


def _free(path: Path) -> int | None:
    try:
        return shutil.disk_usage(path.anchor or path).free
    except OSError:
        return None


def find_remotes(cfg: Config) -> list[Remote]:
    system = os.environ.get("SystemDrive", "C:")[0].upper()
    drives = _drives() if cfg.detect_remote else []

    gdrive = None
    for letter, _, label in drives:
        for name in ("My Drive", "Mon Drive", "Mon disque"):
            if (Path(f"{letter}:/") / name).is_dir():
                gdrive = Path(f"{letter}:/") / name / ARCHIVE_DIR
                break
        if gdrive:
            break

    external, ext_label = cfg.external_dest, "Disque externe"
    if external is not None and not Path(external.anchor).exists():
        external = None
    if external is None:
        for letter, dtype, label in drives:
            if letter == system or (gdrive and gdrive.anchor.startswith(letter)) or dtype not in (DRIVE_REMOVABLE, DRIVE_FIXED):
                continue
            if label.lower().startswith("google drive"):
                continue
            external, ext_label = Path(f"{letter}:\\") / ARCHIVE_DIR, f"{label or 'Disque'} ({letter}:)"
            break

    onedrive = cfg.onedrive_dest if cfg.onedrive_dest and cfg.onedrive_dest.parent.exists() else None
    return [
        Remote("onedrive", "OneDrive", onedrive, None,
               "Envoyé puis rendu « en ligne uniquement » : l'espace local est libéré après la synchro."
               if onedrive else "OneDrive n'est pas configuré sur ce PC."),
        Remote("gdrive", "Google Drive", gdrive, _free(gdrive) if gdrive else None,
               "Copié dans Google Drive pour ordinateur, puis supprimé d'ici." if gdrive else "Lance Google Drive pour ordinateur."),
        Remote("external", ext_label, external, _free(external) if external else None,
               "Copié sur le disque, vérifié, puis supprimé d'ici." if external else "Branche un disque externe."),
    ]


def free_local_copy(path: str):
    """OneDrive : marque « en ligne uniquement » ; le client libère l'espace une fois l'envoi terminé."""
    flags = ["/S", "/D"] if os.path.isdir(path) else []
    subprocess.run(["attrib", "+U", "-P", path], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
    if flags:
        subprocess.run(["attrib", "+U", "-P", os.path.join(path, "*"), *flags], capture_output=True,
                       creationflags=subprocess.CREATE_NO_WINDOW)
