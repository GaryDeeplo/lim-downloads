"""Configuration : chemins, seuils et mots-clés. Surchargeable via config.json à la racine du projet."""
import json
import os
import sys
from dataclasses import dataclass, field, fields
from pathlib import Path

from .i18n import set_language, tr

FROZEN = getattr(sys, "frozen", False)  # lancé depuis Lim.exe
PROJECT_DIR = Path(sys.executable).parent if FROZEN else Path(__file__).resolve().parent.parent
CONFIG_FILE = PROJECT_DIR / "config.json"  # à côté de l'exe, ou à la racine du projet


def _shell_folder(name: str, fallback: str) -> Path:
    """Dossier utilisateur Windows (gère les redirections type OneDrive)."""
    try:
        import winreg

        key = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as k:
            value, _ = winreg.QueryValueEx(k, name)
            return Path(os.path.expandvars(value))
    except OSError:
        return Path.home() / fallback


DOWNLOADS_GUID = "{374DE290-123F-4565-9164-39C4925E467B}"


def _dest(name: str, fallback: str) -> Path:
    """Sous-dossier « Téléchargements » (« Downloads » en anglais) d'un dossier utilisateur Windows."""
    return _shell_folder(name, fallback) / tr("Téléchargements")


def archive_dir_name() -> str:
    """Nom du dossier d'archives sur OneDrive, Google Drive ou un disque externe, dans la langue de l'appli."""
    return tr("Téléchargements archivés")


@dataclass
class Config:
    downloads: Path = field(default_factory=lambda: _shell_folder(DOWNLOADS_GUID, "Downloads"))
    data_dir: Path = field(default_factory=lambda: Path(os.environ.get("LOCALAPPDATA", Path.home())) / "DownloadsManager")
    videos_dest: Path = field(default_factory=lambda: _dest("My Video", "Videos"))
    pictures_dest: Path = field(default_factory=lambda: _dest("My Pictures", "Pictures"))
    music_dest: Path = field(default_factory=lambda: _dest("My Music", "Music"))
    documents_dest: Path = field(default_factory=lambda: _dest("Personal", "Documents"))

    # Destinations distantes : affichées dans le dock quand elles sont disponibles.
    onedrive_dest: Path | None = field(default_factory=lambda: Path(os.environ["OneDrive"]) / archive_dir_name()
                                       if os.environ.get("OneDrive") else None)
    external_dest: Path | None = None   # sinon : premier disque externe détecté, dossier « Téléchargements archivés »
    language: str = "auto"              # auto (langue de Windows) | fr | en
    detect_remote: bool = True          # détection auto de Google Drive et des disques externes

    # Où chercher des copies déjà sauvegardées.
    backup_roots: list[Path] = field(default_factory=lambda: [
        _shell_folder("Personal", "Documents"), _shell_folder("My Pictures", "Pictures"),
        _shell_folder("My Video", "Videos"), _shell_folder("My Music", "Music"),
    ] + ([Path(os.environ["OneDrive"])] if os.environ.get("OneDrive") else []))

    protect_days: int = 7          # rien de plus récent n'est proposé
    installer_days: int = 30       # installeurs plus vieux → quarantaine
    old_archive_days: int = 180    # archives non extraites plus vieilles → rangées
    quarantine_days: int = 30      # durée de rétention avant purge définitive
    redownload_min_mb: int = 50    # « Retéléchargeable » : seulement les gros éléments

    # Tri automatique : uniquement ce qui arrive après son activation, une fois le délai passé.
    auto_enabled: bool = False   # éteint tant que tu ne l'as pas réglé dans l'appli
    auto_delay_hours: float = 168  # 7 jours
    auto_interval_minutes: float = 15
    auto_actions: list[str] = field(default_factory=lambda: ["sort", "duplicates", "installers", "backed_up"])

    # Fichiers dont le nom contient un de ces mots : jamais cochés par défaut pour la quarantaine.
    sensitive_keywords: list[str] = field(default_factory=lambda: [
        "contrat", "contract", "facture", "invoice", "devis", "passeport", "passport",
        "identite", "identité", "carte_id", "rib", "iban", "bank", "banque", "impot", "impôt",
        "tax", "fiche de paie", "payslip", "salaire", "acte", "notaire", "bail", "assurance",
        "certificat", "diplome", "diplôme", "permis", "medical", "médical", "ordonnance",
        "recovery", "codes", "password", "mot de passe", "2fa", "seed", "wallet", "clé", "license", "licence",
        # équivalents anglais (et quelques mots français de plus)
        "salary", "payroll", "pay slip", "bank statement", "statement", "relevé", "releve", "id card", "id_card",
        "id-card", "identity", "lease agreement", "rental agreement", "tenancy", "insurance", "certificate",
        "diploma", "driving licence", "driving license", "permis de conduire", "prescription", "recovery codes",
        "seed phrase", "private key", "notary", "mortgage", "hypothèque", "hypotheque",
    ])

    @property
    def quarantine_dir(self) -> Path:
        return self.data_dir / "quarantaine"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "journal.db"


def load_config() -> Config:
    config_file = Path(os.environ.get("DM_CONFIG", CONFIG_FILE))  # DM_CONFIG : autre config (démo, tests)
    overrides = json.loads(config_file.read_text(encoding="utf-8")) if config_file.exists() else {}
    # La langue d'abord : les noms des dossiers par défaut en dépendent.
    set_language(overrides.get("language", "auto"))
    cfg = Config()
    if overrides:
        path_fields = {f.name for f in fields(Config) if f.name.endswith(("_dest", "_dir")) or f.name == "downloads"}
        to_path = lambda v: Path(os.path.expandvars(v))
        for key, value in overrides.items():
            if not hasattr(cfg, key):
                raise ValueError(tr("config.json : clé inconnue « {key} »", key=key))
            if key == "backup_roots":
                value = [to_path(v) for v in value]
            elif key in path_fields and value is not None:
                value = to_path(value)
            setattr(cfg, key, value)
    set_language(cfg.language)
    return cfg
