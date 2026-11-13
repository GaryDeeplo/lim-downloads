"""Transforme l'index en lots d'actions proposées. Chaque élément tombe dans un seul lot (le premier qui matche)."""
import os
import re
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from .backup import BackupIndex
from .config import Config
from .detect import extracted_folder, find_duplicates, pick_keeper
from .i18n import tr
from .scanner import Item
from .sources import detect as detect_source

DAY = 86400

INCOMPLETE = {".crdownload", ".opdownload", ".part", ".partial", ".download", ".tmp"}
INSTALLERS = {".exe", ".msi", ".msix", ".appx", ".dmg", ".pkg", ".deb", ".rpm"}
VIDEOS = {".mkv", ".mp4", ".mov", ".avi", ".wmv", ".webm", ".m4v", ".flv"}
IMAGES = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".bmp", ".tif", ".tiff", ".svg", ".nef", ".cr2", ".arw", ".dng", ".raw", ".avif"}
AUDIO = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".opus", ".aiff"}
DOCUMENTS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".ppt", ".pptx", ".odt", ".ods", ".odp", ".txt", ".rtf", ".md", ".epub",
             ".xlsm", ".pages", ".numbers", ".key"}
ARCHIVES = {".zip", ".rar", ".7z", ".tar", ".gz", ".tgz", ".bz2", ".xz"}

QUARANTINE, MOVE = "quarantine", "move"


def _month(item: Item) -> str:
    return datetime.fromtimestamp(item.mtime).strftime("%Y-%m")


def _year(item: Item) -> str:
    return datetime.fromtimestamp(item.mtime).strftime("%Y")


@dataclass(frozen=True)
class Target:
    key: str
    label_fr: str                   # libellé français ; `label` le donne dans la langue de l'appli
    root: Callable[[Config], Path]
    sub: Callable[[Item], str] | None = None

    @property
    def label(self) -> str:
        return tr(self.label_fr)


# Destinations du dock. La quarantaine est une cible à part (pas de dossier final).
TARGETS: dict[str, Target] = {t.key: t for t in [
    Target("videos", "Vidéos", lambda c: c.videos_dest),
    Target("images", "Images", lambda c: c.pictures_dest, _month),
    Target("documents", "Documents", lambda c: c.documents_dest, _year),
    Target("audio", "Audio", lambda c: c.music_dest),
    Target("archives", "Archives", lambda c: c.documents_dest / "Archives"),
    Target("folders", "Dossiers", lambda c: c.documents_dest / "Dossiers"),
]}


def target_dest(target: str, item: Item, cfg: Config, remotes: dict[str, Path] | None = None) -> Path | None:
    """Dossier final d'un élément envoyé vers une cible ; None pour la quarantaine.
    `remotes` : racines des destinations distantes disponibles (OneDrive, Google Drive, disque externe)."""
    if target == QUARANTINE:
        return None
    if remotes and target in remotes:
        return remotes[target]
    t = TARGETS[target]
    return t.root(cfg) / t.sub(item) if t.sub else t.root(cfg)


DRIVE_PART = re.compile(r"^(?P<base>.+-\d{8}T\d{6}Z)-\d+-\d{3}\.zip$", re.IGNORECASE)


def group_exports(items: list[Item]) -> list[Item]:
    """Les zips d'un même export Google Drive (…Z-1-001.zip, …Z-1-002.zip) deviennent un seul élément."""
    groups: dict[str, list[Item]] = defaultdict(list)
    rest = []
    for it in items:
        m = None if it.is_dir else DRIVE_PART.match(it.name)
        if m:
            groups[m.group("base")].append(it)
        else:
            rest.append(it)
    for base, parts in groups.items():
        if len(parts) == 1:
            rest.append(parts[0])
            continue
        parts.sort(key=lambda i: i.name)
        rest.append(Item(parts[0].path, tr("{base} ({n} parties)", base=base, n=len(parts)), False, sum(p.size for p in parts),
                         max(p.mtime for p in parts), ".zip", len(parts), members=parts))
    return rest


def _count(n: int, one: str, many: str) -> str:
    """« 1 fichier » / « 3 fichiers », dans la langue de l'appli."""
    return tr(one if n == 1 else many, n=n)


def _short(path: str) -> str:
    home = os.path.expanduser("~")
    return "~" + path[len(home):] if path.lower().startswith(home.lower()) else path


@dataclass
class Entry:
    item: Item
    reason: str = ""
    dest: str | None = None
    checked: bool = True
    keeper: Item | None = None  # doublons : l'exemplaire gardé


@dataclass
class Bucket:
    key: str
    title: str
    description: str
    target: str | None          # clé de TARGETS, QUARANTINE, ou None (pas d'action proposée)
    entries: list[Entry] = field(default_factory=list)

    @property
    def action(self) -> str | None:
        return None if self.target is None else (QUARANTINE if self.target == QUARANTINE else MOVE)


def _is_sensitive(name: str, cfg: Config) -> bool:
    low = name.lower()
    return any(k in low for k in cfg.sensitive_keywords)


def build_plan(items: list[Item], cfg: Config, now: float | None = None,
               progress: Callable[[str], None] = lambda _: None, backup: BackupIndex | None = None) -> list[Bucket]:
    now = now or time.time()
    age = lambda i: (now - i.mtime) / DAY
    items = group_exports(items)
    with ThreadPoolExecutor(16) as pool:  # lecture des flux Zone.Identifier en parallèle
        for it, src in zip(items, pool.map(lambda i: detect_source(i.path, (i.members or [i])[0].name, i.is_dir), items)):
            it.source = src

    b = {bk.key: bk for bk in [
        Bucket("recent", tr("Récents"),
               tr("Arrivés il y a moins de {days} jours : protégés, rien n'est coché.", days=cfg.protect_days), None),
        Bucket("incomplete", tr("Incomplets"), tr("Téléchargements partiels ou fichiers vides."), QUARANTINE),
        Bucket("duplicates", tr("Doublons exacts"), tr("Contenu identique octet par octet : un exemplaire est gardé."),
               QUARANTINE),
        Bucket("extracted_zips", tr("Zips déjà extraits"),
               tr("Le dossier voisin contient tout le contenu du zip (mêmes fichiers, mêmes tailles)."), QUARANTINE),
        Bucket("backed_up", tr("Déjà sauvegardé ailleurs"),
               tr("Tout le contenu existe déjà dans Documents, Images, OneDrive… (vérifié octet par octet). "
                  "Les copies seulement « en ligne » sont décochées."), QUARANTINE),
        Bucket("redownload", tr("Retéléchargeable"),
               tr("Torrents, exports Google Drive et fichiers publics de plus de {mb} Mo. Rien n'est coché : "
                  "un reçu garde le lien.", mb=cfg.redownload_min_mb), QUARANTINE),
        Bucket("installers", tr("Installeurs anciens"),
               tr("Programmes d'installation de plus de {days} jours.", days=cfg.installer_days), QUARANTINE),
        Bucket("videos", tr("Vidéos"), tr("Toutes les vidéos."), "videos"),
        Bucket("images", tr("Images"), tr("Rangées par mois d'arrivée."), "images"),
        Bucket("documents", tr("Documents"), tr("Rangés par année d'arrivée."), "documents"),
        Bucket("audio", tr("Audio"), tr("Musique, sons, enregistrements."), "audio"),
        Bucket("archives", tr("Archives anciennes"),
               tr("Archives de plus de {days} jours, non extraites.", days=cfg.old_archive_days), "archives"),
        Bucket("folders", tr("Dossiers"), tr("Déplacés en bloc, contenu intact."), "folders"),
        Bucket("other", tr("À regarder"), tr("Aucune règle ne s'applique : glisse-les vers un dossier si besoin."), None),
    ]}
    assigned: set[str] = set()

    def put(key: str, item: Item, reason: str = "", checked: bool = True, keeper: Item | None = None):
        if item.path in assigned:
            return
        if age(item) < cfg.protect_days and key != "recent":
            key, checked = "recent", False
        bucket = b[key]
        if bucket.action == QUARANTINE and key not in ("duplicates", "backed_up") and _is_sensitive(item.name, cfg):
            checked, reason = False, (reason + " · " + tr("nom sensible, décoché")).lstrip(" ·")
        if bucket.target is None:
            checked = False
        assigned.add(item.path)
        dest = target_dest(bucket.target, item, cfg) if bucket.target else None
        bucket.entries.append(Entry(item, reason, str(dest) if dest else None, checked, keeper))

    progress(tr("Fichiers incomplets"))
    for it in items:
        if not it.is_dir and (it.ext in INCOMPLETE or it.size == 0):
            put("incomplete", it, tr("partiel") if it.size else tr("vide (0 octet)"))

    progress(tr("Recherche des doublons"))
    for group in find_duplicates([i for i in items if i.path not in assigned and not i.members]):
        keeper = pick_keeper(group)
        for it in group:
            if it is not keeper:
                put("duplicates", it, tr("copie de « {name} »", name=keeper.name), keeper=keeper)

    progress(tr("Vérification des zips"))
    dirs_by_name = {i.name.lower(): i for i in items if i.is_dir}
    for it in items:
        if it.ext == ".zip" and it.path not in assigned and not it.members:
            folder = extracted_folder(it, dirs_by_name)
            if folder:
                put("extracted_zips", it, tr("extrait dans « {name} »", name=folder.name))

    progress(tr("Recherche de copies sauvegardées"))
    if backup is None:
        backup = BackupIndex(cfg.backup_roots, [cfg.downloads, cfg.data_dir])
    for it in items:
        if it.path in assigned:
            continue
        verdict = backup.check(it)
        if verdict:
            note = "" if verdict.sure else " · " + tr("copie en ligne uniquement, non vérifiée")
            put("backed_up", it, tr("copie : {where}", where=_short(verdict.where)) + note, checked=verdict.sure)

    min_size = cfg.redownload_min_mb * 1024 * 1024
    for it in items:
        if it.path not in assigned and it.source.redownloadable and it.size >= min_size:
            put("redownload", it, tr("source : {source}", source=it.source.label), checked=False)

    progress(tr("Classement"))
    for it in items:
        if it.path in assigned:
            continue
        if it.is_dir:
            put("folders", it, _count(it.file_count, "{n} fichier", "{n} fichiers"))
        elif it.ext in INSTALLERS and age(it) >= cfg.installer_days:
            put("installers", it, _count(int(age(it)), "{n} jour", "{n} jours"))
        elif it.ext in VIDEOS:
            put("videos", it)
        elif it.ext in IMAGES:
            put("images", it)
        elif it.ext in DOCUMENTS:
            put("documents", it)
        elif it.ext in AUDIO:
            put("audio", it)
        elif it.ext in ARCHIVES and age(it) >= cfg.old_archive_days:
            put("archives", it, _count(int(age(it)), "{n} jour", "{n} jours"))
        else:
            put("other", it, tr("archive de {n} jours, non extraite", n=int(age(it))) if it.ext in ARCHIVES else "")

    for bucket in b.values():
        bucket.entries.sort(key=lambda e: e.item.size, reverse=True)
    return list(b.values())
