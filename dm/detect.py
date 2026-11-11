"""Détections coûteuses : doublons par contenu et zips déjà extraits."""
import os
import re
import zipfile
from collections import defaultdict
from pathlib import Path

import xxhash

from .scanner import Item

CHUNK = 1 << 20
EDGE = 64 * 1024
COPY_SUFFIX = re.compile(r"\s*(\(\d+\)|- copie( \(\d+\))?|- copy( \(\d+\))?)$", re.IGNORECASE)


_cache: dict[tuple, str] = {}  # empreintes déjà calculées : un rescan ne relit pas les fichiers inchangés


def _cached(kind: str, path: str, compute) -> str:
    st = os.stat(path)
    key = (kind, path, st.st_size, st.st_mtime_ns)
    if key not in _cache:
        _cache[key] = compute()
    return _cache[key]


def _partial_hash(path: str, size: int) -> str:
    return _cached("p", path, lambda: _partial_hash_raw(path, size))


def _full_hash(path: str) -> str:
    return _cached("f", path, lambda: _full_hash_raw(path))


def _partial_hash_raw(path: str, size: int) -> str:
    h = xxhash.xxh3_64()
    with open(path, "rb") as f:
        h.update(f.read(EDGE))
        if size > 2 * EDGE:
            f.seek(-EDGE, os.SEEK_END)
            h.update(f.read(EDGE))
    return h.hexdigest()


def _full_hash_raw(path: str) -> str:
    h = xxhash.xxh3_128()
    with open(path, "rb") as f:
        while chunk := f.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()


def _group_by(items: list[Item], key) -> list[list[Item]]:
    groups: dict = defaultdict(list)
    for it in items:
        try:
            groups[key(it)].append(it)
        except OSError:
            continue
    return [g for g in groups.values() if len(g) > 1]


def find_duplicates(items: list[Item]) -> list[list[Item]]:
    """Groupes de fichiers au contenu strictement identique (taille → empreinte partielle → empreinte complète)."""
    files = [i for i in items if not i.is_dir and i.size > 0]
    result = []
    for same_size in _group_by(files, lambda i: i.size):
        for same_partial in _group_by(same_size, lambda i: _partial_hash(i.path, i.size)):
            if same_size[0].size <= EDGE:
                result.append(same_partial)  # fichier entièrement couvert par l'empreinte partielle
            else:
                result.extend(_group_by(same_partial, lambda i: _full_hash(i.path)))
    return result


def base_stem(name: str) -> str:
    """« rapport (2).pdf » → « rapport »."""
    stem = os.path.splitext(name)[0]
    return COPY_SUFFIX.sub("", stem).strip()


def pick_keeper(group: list[Item]) -> Item:
    """Garde l'exemplaire au nom le plus propre, puis le plus ancien."""
    return min(group, key=lambda i: (os.path.splitext(i.name)[0] != base_stem(i.name), i.mtime, len(i.name)))


def _strip_first(paths: set[tuple[str, int]]) -> set[tuple[str, int]]:
    return {(p.split("/", 1)[1], s) for p, s in paths if "/" in p}


def _dir_listing(root: str) -> set[tuple[str, int]]:
    out = set()
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            try:
                rel = os.path.relpath(full, root).replace("\\", "/").lower()
                out.add((rel, os.path.getsize(full)))
            except OSError:
                continue
    return out


def extracted_folder(zip_item: Item, dirs_by_name: dict[str, Item]) -> Item | None:
    """Renvoie le dossier voisin qui contient TOUT le contenu du zip (même chemins, mêmes tailles), sinon None."""
    stem = os.path.splitext(zip_item.name)[0]
    keys = dict.fromkeys([stem.lower(), base_stem(zip_item.name).lower()])
    candidates = [dirs_by_name[k] for k in keys if k in dirs_by_name]
    if not candidates:
        return None
    try:
        with zipfile.ZipFile(zip_item.path) as zf:
            entries = {(i.filename.rstrip("/").lower(), i.file_size) for i in zf.infolist() if not i.is_dir()}
    except (zipfile.BadZipFile, OSError, RuntimeError, NotImplementedError):
        return None
    if not entries:
        return None
    stripped_entries = _strip_first(entries)
    zip_has_root = len(stripped_entries) == len(entries)  # toutes les entrées sont sous un dossier racine
    for folder in candidates:
        listing = _dir_listing(folder.path)
        # extraction directe, ou avec/sans dossier racine en plus
        if entries <= listing or entries <= _strip_first(listing) or (zip_has_root and stripped_entries <= listing):
            return folder
    return None
