"""Indexation du dossier : chaque élément de premier niveau (fichier OU dossier entier) est une unité."""
import os
from dataclasses import dataclass, field
from pathlib import Path

IGNORED_NAMES = {"desktop.ini", "thumbs.db", ".ds_store"}


@dataclass
class Item:
    path: str
    name: str
    is_dir: bool
    size: int
    mtime: float        # date d'arrivée : max(modification, création), et le plus récent du contenu pour un dossier
    ext: str
    file_count: int = 1
    members: list["Item"] = field(default_factory=list)  # export Drive en plusieurs zips : les parties
    source: object = None                                 # sources.Source, renseigné au classement


def _arrival(st: os.stat_result) -> float:
    birth = getattr(st, "st_birthtime", None) or st.st_ctime
    return max(st.st_mtime, birth)


def _dir_stats(path: str) -> tuple[int, int, float]:
    """Taille totale, nombre de fichiers et date la plus récente d'un dossier (sans suivre liens ni jonctions)."""
    size = count = 0
    newest = 0.0
    stack = [path]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                for entry in it:
                    try:
                        if entry.is_symlink() or entry.is_junction():
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                        else:
                            st = entry.stat(follow_symlinks=False)
                            size += st.st_size
                            count += 1
                            newest = max(newest, _arrival(st))
                    except OSError:
                        continue
        except OSError:
            continue
    return size, count, newest


def scan(root: Path) -> list[Item]:
    items: list[Item] = []
    with os.scandir(root) as it:
        for entry in it:
            if entry.name.lower() in IGNORED_NAMES:
                continue
            try:
                if entry.is_symlink() or entry.is_junction():
                    continue
                st = entry.stat(follow_symlinks=False)
                if entry.is_dir(follow_symlinks=False):
                    size, count, newest = _dir_stats(entry.path)
                    items.append(Item(entry.path, entry.name, True, size, max(_arrival(st), newest), "", count))
                else:
                    items.append(Item(entry.path, entry.name, False, st.st_size, _arrival(st),
                                      os.path.splitext(entry.name)[1].lower()))
            except OSError:
                continue
    return items
