"""Langue du serveur : la même que l'interface. Français sur un Windows français, anglais sinon ; surchargeable
via config.json (« language » : auto | fr | en).

Le texte français exact sert de clé : tr("…") le renvoie tel quel en français et cherche sa traduction dans EN
en anglais (le français reste affiché si une clé manque). Les {variables} sont remplies après la traduction.
"""
import ctypes

LANG_FR, LANG_EN = "fr", "en"
LANG_FRENCH_PRIMARY = 0x0C  # identifiant de langue principal du français (LANGID & 0x3FF)


def _windows_language() -> str:
    """Langue d'affichage de Windows ; anglais si elle est illisible (autre système, appel refusé…)."""
    try:
        langid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        return LANG_FR if langid & 0x3FF == LANG_FRENCH_PRIMARY else LANG_EN
    except Exception:
        return LANG_EN


def _resolve(value: str | None) -> str:
    value = (value or "auto").strip().lower()[:2]
    return value if value in (LANG_FR, LANG_EN) else _windows_language()


_lang = _resolve("auto")  # résolu dès l'import : les dossiers par défaut de Config en dépendent


def set_language(value: str | None):
    """« auto » (langue de Windows), « fr » ou « en »."""
    global _lang
    _lang = _resolve(value)


def lang() -> str:
    return _lang


LANG = lang


class _Keep(dict):
    """Laisse intacte une {variable} non fournie plutôt que de planter."""
    def __missing__(self, key):
        return "{" + key + "}"


def tr(fr: str, **vars) -> str:
    text = EN.get(fr, fr) if _lang == LANG_EN else fr
    return text.format_map(_Keep(vars)) if vars else text


EN: dict[str, str] = {
    "langue inconnue": "unknown language",
    # — Dossiers de destination par défaut —
    "Téléchargements": "Downloads",
    "Téléchargements archivés": "Archived downloads",
    "config.json : clé inconnue « {key} »": 'config.json: unknown key "{key}"',

    # — Lots (rules.py) —
    "Récents": "Recent",
    "Arrivés il y a moins de {days} jours : protégés, rien n'est coché.":
        "Arrived less than {days} days ago: protected, nothing is checked.",
    "Incomplets": "Incomplete downloads",
    "Téléchargements partiels ou fichiers vides.": "Partial downloads or empty files.",
    "Doublons exacts": "Exact duplicates",
    "Contenu identique octet par octet : un exemplaire est gardé.": "Identical byte for byte: one copy is kept.",
    "Zips déjà extraits": "Already-extracted zips",
    "Le dossier voisin contient tout le contenu du zip (mêmes fichiers, mêmes tailles).":
        "The folder next to it holds everything in the zip (same files, same sizes).",
    "Déjà sauvegardé ailleurs": "Already backed up elsewhere",
    "Tout le contenu existe déjà dans Documents, Images, OneDrive… (vérifié octet par octet). "
    "Les copies seulement « en ligne » sont décochées.":
        "Everything already exists in Documents, Pictures, OneDrive… (checked byte for byte). "
        "Online-only copies are left unchecked.",
    "Retéléchargeable": "Re-downloadable",
    "Torrents, exports Google Drive et fichiers publics de plus de {mb} Mo. Rien n'est coché : un reçu garde le lien.":
        "Torrents, Google Drive exports and public files over {mb} MB. Nothing is checked: a receipt keeps the link.",
    "Installeurs anciens": "Old installers",
    "Programmes d'installation de plus de {days} jours.": "Installers older than {days} days.",
    "Vidéos": "Videos",
    "Toutes les vidéos.": "All videos.",
    "Images": "Images",
    "Rangées par mois d'arrivée.": "Sorted by month of arrival.",
    "Documents": "Documents",
    "Rangés par année d'arrivée.": "Sorted by year of arrival.",
    "Audio": "Audio",
    "Musique, sons, enregistrements.": "Music, sounds, recordings.",
    "Archives": "Archives",
    "Archives anciennes": "Old archives",
    "Archives de plus de {days} jours, non extraites.": "Archives older than {days} days, not extracted.",
    "Dossiers": "Folders",
    "Déplacés en bloc, contenu intact.": "Moved as a whole, contents untouched.",
    "À regarder": "To review",
    "Aucune règle ne s'applique : glisse-les vers un dossier si besoin.":
        "No rule applies: drag them to a folder if needed.",
    "Quarantaine": "Quarantine",
    "{base} ({n} parties)": "{base} ({n} parts)",

    # — Raisons affichées à côté des éléments —
    "nom sensible, décoché": "sensitive name, unchecked",
    "partiel": "partial",
    "vide (0 octet)": "empty (0 bytes)",
    "copie de « {name} »": "copy of “{name}”",
    "extrait dans « {name} »": "extracted to “{name}”",
    "copie en ligne uniquement, non vérifiée": "online-only copy, not verified",
    "copie : {where}": "copy: {where}",
    "source : {source}": "source: {source}",
    "{n} fichier": "{n} file",
    "{n} fichiers": "{n} files",
    "{n} jour": "{n} day",
    "{n} jours": "{n} days",
    "archive de {n} jours, non extraite": "{n}-day-old archive, not extracted",

    # — Étapes du scan —
    "Indexation": "Indexing",
    "Fichiers incomplets": "Incomplete files",
    "Recherche des doublons": "Looking for duplicates",
    "Vérification des zips": "Checking zips",
    "Recherche de copies sauvegardées": "Looking for backed-up copies",
    "Classement": "Sorting",

    # — Sources (sources.py) —
    "transfert (lien expiré)": "transfer (expired link)",
    "pièce jointe Gmail": "Gmail attachment",

    # — Destinations distantes (remote.py) —
    "OneDrive": "OneDrive",
    "Google Drive": "Google Drive",
    "Disque externe": "External drive",
    "Disque": "Drive",
    "Envoyé puis rendu « en ligne uniquement » : l'espace local est libéré après la synchro.":
        "Uploaded, then made online-only: local space is freed once synced.",
    "OneDrive n'est pas configuré sur ce PC.": "OneDrive isn't set up on this PC.",
    "Copié dans Google Drive pour ordinateur, puis supprimé d'ici.":
        "Copied to Google Drive for desktop, then removed from here.",
    "Lance Google Drive pour ordinateur.": "Start Google Drive for desktop.",
    "Copié sur le disque, vérifié, puis supprimé d'ici.": "Copied to the drive, checked, then removed from here.",
    "Branche un disque externe.": "Plug in an external drive.",

    # — API (server.py) —
    "requête refusée : réservée à l'interface locale": "request refused: only the local app can do this",
    "élément inconnu, relance un scan": "unknown item, run a new scan",
    "un transfert est en cours": "a transfer is in progress",
    "cible inconnue ou indisponible": "unknown or unavailable destination",
    "aucun élément applicable": "nothing to apply",
    "un seul dossier cible par action": "one destination per action",
    "Sélection": "Selection",
    "restauration impossible : {error}": "couldn't restore: {error}",
    "destination indisponible": "destination unavailable",
    "aucun reçu pour l'instant": "no receipts yet",
    "Autres": "Other",

    # — Journal des actions (actions.py) —
    "copie incomplète : {path}": "incomplete copy: {path}",
    "hors du dossier Téléchargements": "outside the Downloads folder",
    "n'existe plus": "no longer exists",
    "modifié depuis le scan": "changed since the scan",
    "après déplacement : {error}": "after moving: {error}",
    "lot introuvable, déjà annulé ou purgé": "batch not found, already undone or purged",
    "restauration : {error}": "restore: {error}",
    "cet élément n'est plus en quarantaine": "this item is no longer in quarantine",
    "ce lot n'est pas (ou plus) en quarantaine": "this batch isn't in quarantine (or no longer is)",

    # — Tri auto (auto.py) —
    "export en plusieurs parties : à trier à la main": "multi-part export: sort it by hand",
    "« {title} » n'est pas trié automatiquement": "“{title}” isn't auto-sorted",
    "décoché par sécurité": "unchecked to be safe",
    "aperçu : {error}": "preview: {error}",

    # — Icône et notifications (__main__.py) —
    "{n} téléchargement rangé automatiquement": "{n} download auto-sorted",
    "{n} téléchargements rangés automatiquement": "{n} downloads auto-sorted",
    "Annuler": "Undo",
    "Ouvrir": "Open",
    "Tri automatique annulé": "Auto-sort undone",
    "Les fichiers sont revenus dans Téléchargements.": "The files are back in Downloads.",
    "Ouvrir Lim": "Open Lim",
    "Tri automatique": "Auto-sort",
    "Trier maintenant": "Sort now",
    "Lancer au démarrage de Windows": "Start with Windows",
    "Quitter": "Quit",

    # — Raccourcis Windows (autostart.py) —
    "Lim : tri automatique au démarrage": "Lim: auto-sort at startup",
    "Lim : trier le dossier Téléchargements": "Lim: tidy up the Downloads folder",

    # — Reçus de quarantaine (receipts.py) —
    "date": "date",
    "nom": "name",
    "taille": "size",
    "octets": "bytes",
    "source": "source",
    "lien de téléchargement": "download link",
    "page d'origine": "source page",
    "lot": "batch",
    "emplacement d'origine": "original location",
    "emplacement en quarantaine": "quarantine location",
}
