"""« Déjà sauvegardé ailleurs » : le contenu d'un élément existe-t-il déjà dans Documents, Images, OneDrive… ?

Fichier : même taille puis même empreinte. Zip : chaque entrée a un fichier de même taille et même CRC32.
Dossier : chaque fichier est retrouvé. Les fichiers « en ligne uniquement » (OneDrive) ne sont jamais lus,
pour ne pas les re-télécharger : ils ne comptent que comme correspondance probable (même nom + même taille).
"""
import os
import time
import zipfile
import zlib
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from .detect import _cached, _full_hash
from .scanner import Item

SKIP_DIRS = {"node_modules", ".git", ".venv", "venv", "__pycache__", ".next", ".nuxt", "dist", "build", ".cache",
             "site-packages", ".idea", ".vscode", "$recycle.bin", "appdata"}
CLOUD_ONLY = 0x00400000 | 0x00040000 | 0x00001000  # RECALL_ON_DATA_ACCESS | RECALL_ON_OPEN | OFFLINE
MAX_DIR_FILES = 5000


@dataclass
class Copy:
    path: str
    name: str
    cloud_only: bool


@dataclass
class Verdict:
    sure: bool          # tout le contenu a une copie vérifiée octet par octet (ou CRC32 pour un zip)
    where: str          # exemple d'emplacement de la copie


def _crc32(path: str) -> int:
    def compute():
        crc = 0
        with open(path, "rb") as f:
            while chunk := f.read(1 << 20):
                crc = zlib.crc32(chunk, crc)
        return crc
    return _cached("c", path, compute)


class BackupIndex:
    """Index par taille des fichiers des dossiers de sauvegarde, gardé quelques minutes entre deux scans."""
    _memo: dict[tuple, tuple[float, dict[int, list[Copy]]]] = {}
    TTL = 15 * 60

    def __init__(self, roots: list[Path], exclude: list[Path]):
        self.exclude = [os.path.normcase(os.path.abspath(p)) for p in exclude]
        self.roots = [r for r in dict.fromkeys(roots) if r.exists() and not self._excluded(str(r))]
        key = tuple(sorted(str(r) for r in self.roots))
        hit = self._memo.get(key)
        if hit and time.time() - hit[0] < self.TTL:
            self.by_size = hit[1]
        else:
            self.by_size = self._build()
            self._memo[key] = (time.time(), self.by_size)

    def _excluded(self, path: str) -> bool:
        p = os.path.normcase(os.path.abspath(path))
        return any(p == e or p.startswith(e + os.sep) for e in self.exclude)

    def _build(self) -> dict[int, list[Copy]]:
        by_size: dict[int, list[Copy]] = defaultdict(list)
        stack = [str(r) for r in self.roots]
        while stack:
            current = stack.pop()
            if self._excluded(current):
                continue
            try:
                with os.scandir(current) as it:
                    for entry in it:
                        try:
                            if entry.is_symlink() or entry.is_junction():
                                continue
                            if entry.is_dir(follow_symlinks=False):
                                if entry.name.lower() not in SKIP_DIRS and not entry.name.startswith("."):
                                    stack.append(entry.path)
                                continue
                            st = entry.stat(follow_symlinks=False)
                            if st.st_size > 0:
                                attrs = getattr(st, "st_file_attributes", 0)
                                by_size[st.st_size].append(Copy(entry.path, entry.name.lower(), bool(attrs & CLOUD_ONLY)))
                        except OSError:
                            continue
            except OSError:
                continue
        return by_size

    # — une correspondance pour un fichier isolé —
    def _match_file(self, path: str, name: str, size: int) -> tuple[str, bool] | None:
        copies = self.by_size.get(size)
        if not copies:
            return None
        weak = None
        for c in copies:
            if c.cloud_only:
                if c.name == name.lower():
                    weak = c.path
                continue
            try:
                if _full_hash(c.path) == _full_hash(path):
                    return c.path, True
            except OSError:
                continue
        return (weak, False) if weak else None

    def _match_crc(self, name: str, size: int, crc: int) -> tuple[str, bool] | None:
        copies = self.by_size.get(size)
        if not copies:
            return None
        weak = None
        for c in copies:
            if c.cloud_only:
                if c.name == name.lower():
                    weak = c.path
                continue
            try:
                if _crc32(c.path) == crc:
                    return c.path, True
            except OSError:
                continue
        return (weak, False) if weak else None

    def _combine(self, matches) -> Verdict | None:
        sure, where = True, None
        for m in matches:
            if m is None:
                return None
            where = where or m[0]
            sure = sure and m[1]
        return Verdict(sure, where) if where else None

    def check(self, item: Item) -> Verdict | None:
        if not self.by_size:
            return None
        members = item.members or [item]
        if item.is_dir:
            return self._combine(self._dir_matches(item.path))
        if all(m.ext == ".zip" for m in members):
            return self._combine(m for z in members for m in self._zip_matches(z.path))
        return self._combine(self._match_file(m.path, m.name, m.size) for m in members)

    def _dir_matches(self, root: str):
        count = 0
        for dirpath, _, filenames in os.walk(root):  # tout le contenu doit être retrouvé, rien n'est sauté
            for fn in filenames:
                count += 1
                if count > MAX_DIR_FILES:
                    yield None
                    return
                full = os.path.join(dirpath, fn)
                try:
                    size = os.path.getsize(full)
                except OSError:
                    yield None
                    return
                if size == 0:
                    continue
                yield self._match_file(full, fn, size)

    def _zip_matches(self, path: str):
        try:
            with zipfile.ZipFile(path) as zf:
                infos = [i for i in zf.infolist() if not i.is_dir() and i.file_size > 0]
        except (zipfile.BadZipFile, OSError, RuntimeError, NotImplementedError):
            yield None
            return
        if not infos:
            yield None
            return
        for i in infos:
            yield self._match_crc(os.path.basename(i.filename), i.file_size, i.CRC)

