"""D'où vient un téléchargement ? Lu dans le flux Zone.Identifier que Windows attache aux fichiers des navigateurs,
complété par des motifs de nom (torrents, exports Drive, transferts)."""
import re
from dataclasses import dataclass
from urllib.parse import urlparse

# kind : drive | torrent | public | transfer | mail | generated | site | unknown
REDOWNLOADABLE = {"drive", "torrent", "public"}


@dataclass
class Source:
    kind: str
    label: str              # ce qu'on affiche : « Google Drive », « torrent », « pexels.com »…
    url: str | None = None  # lien de téléchargement d'origine
    page: str | None = None # page d'où il a été lancé
    expirable: bool = False # lien qui expire (WeTransfer…) : ne pas compter dessus

    @property
    def redownloadable(self) -> bool:
        return self.kind in REDOWNLOADABLE and not self.expirable


DRIVE_EXPORT = re.compile(r"-\d{8}T\d{6}Z-\d+-\d{3}(\.zip)?$", re.IGNORECASE)
TORRENT_NAME = re.compile(
    r"torrent|\byts\b|\bx26[45]\b|\bhevc\b|\b(480|720|1080|2160)p\b|\bbluray\b|\bweb-?dl\b|\bwebrip\b|\btruefrench\b"
    r"|\bmulti\b.*\b(1080|720)p|\bs\d{2}e\d{2}\b|\bintegrale\b|\bdvdrip\b|\bbrrip\b", re.IGNORECASE)
TRANSFER_NAME = re.compile(r"^(wetransfer|swisstransfer|transfer-|smash|transfernow|filemail)", re.IGNORECASE)

HOSTS: list[tuple[str, str, str, bool]] = [  # (fragment d'hôte, kind, label, expirable)
    ("drive.usercontent.google", "drive", "Google Drive", False),
    ("drive.google", "drive", "Google Drive", False),
    ("takeout-download", "drive", "Google Drive (export)", False),
    ("docs.google", "drive", "Google Docs", False),
    ("wetransfer", "transfer", "WeTransfer", True),
    ("we.tl", "transfer", "WeTransfer", True),
    ("swisstransfer", "transfer", "SwissTransfer", True),
    ("transfernow", "transfer", "TransferNow", True),
    ("smash", "transfer", "Smash", True),
    ("filemail", "transfer", "Filemail", True),
    ("mail-attachment.googleusercontent", "mail", "pièce jointe Gmail", False),
    ("mail.google", "mail", "Gmail", False),
    ("outlook", "mail", "Outlook", False),
    ("mail.", "mail", "webmail", False),
    ("whatsapp", "mail", "WhatsApp", False),
    ("messenger", "mail", "Messenger", False),
    ("claude.ai", "generated", "Claude", False),
    ("chatgpt", "generated", "ChatGPT", False),
    ("canva", "generated", "Canva", False),
    ("photopea", "generated", "Photopea", False),
    ("elevenlabs", "generated", "ElevenLabs", False),
    ("pexels", "public", "Pexels", False),
    ("unsplash", "public", "Unsplash", False),
    ("pixabay", "public", "Pixabay", False),
    ("codeload.github", "public", "GitHub", False),
    ("github", "public", "GitHub", False),
    ("archive.org", "public", "archive.org", False),
]


def _zone_identifier(path: str) -> tuple[str | None, str | None]:
    try:
        with open(path + ":Zone.Identifier", encoding="utf-8", errors="replace") as f:
            text = f.read(4096)
    except OSError:
        return None, None
    host = re.search(r"^HostUrl=(.+)$", text, re.MULTILINE)
    ref = re.search(r"^ReferrerUrl=(.+)$", text, re.MULTILINE)
    clean = lambda m: m.group(1).strip() if m and "://" in m.group(1) else None
    return clean(host), clean(ref)


def detect(path: str, name: str, is_dir: bool) -> Source:
    url, page = (None, None) if is_dir else _zone_identifier(path)
    if TRANSFER_NAME.match(name):
        return Source("transfer", "transfert (lien expiré)", url, page, expirable=True)
    for value in (url, page):
        host = urlparse(value).netloc.lower() if value else ""
        if not host:
            continue
        if host.endswith(".torrent") or "torrent" in host:
            return Source("torrent", "torrent", url, page)
        for fragment, kind, label, expirable in HOSTS:
            if fragment in host:
                return Source(kind, label, url, page, expirable)
    if url and url.lower().endswith(".torrent"):
        return Source("torrent", "torrent", url, page)
    if DRIVE_EXPORT.search(name.rsplit(".zip", 1)[0] if name.lower().endswith(".zip") else name) or name.startswith("drive-download-"):
        return Source("drive", "Google Drive (export)", url, page)
    if TORRENT_NAME.search(name.replace(".", " ").replace("_", " ")):
        return Source("torrent", "torrent", url, page)
    if url:
        host = urlparse(url).netloc.lower().removeprefix("www.")
        return Source("site", host, url, page)
    return Source("unknown", "", None, None)
