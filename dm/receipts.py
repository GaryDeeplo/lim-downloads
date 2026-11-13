"""Reçus de quarantaine : un CSV lisible dans Excel qui garde nom, taille et lien d'origine de tout ce qui part."""
import csv
import time
from pathlib import Path

from .i18n import lang, tr

RECEIPT_NAME = "Reçus de quarantaine.csv"  # nom de fichier conservé tel quel, quelle que soit la langue
HEADER = ["date", "nom", "taille", "octets", "source", "lien de téléchargement", "page d'origine", "lot",
          "emplacement d'origine", "emplacement en quarantaine"]  # traduit à l'écriture


def human(n: float) -> str:
    en = lang() == "en"
    units = ("B", "KB", "MB", "GB", "TB") if en else ("o", "Ko", "Mo", "Go", "To")
    for unit in units:
        if n < 1024 or unit == units[-1]:
            text = f"{n:.1f} {unit}".replace(".0 ", " ")
            return text if en else text.replace(".", ",")
        n /= 1024
    return str(n)


def write_receipts(path: Path, rows: list[dict]):
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    # Séparateur attendu par Excel : « ; » en français, « , » en anglais. Un reçu existant garde le sien.
    delimiter = ";" if lang() == "fr" else ","
    if not new:
        with open(path, encoding="utf-8-sig") as f:
            first = f.readline()
        delimiter = ";" if first.count(";") >= first.count(",") else ","
    with open(path, "a", newline="", encoding="utf-8-sig" if new else "utf-8") as f:
        w = csv.writer(f, delimiter=delimiter)
        if new:
            w.writerow([tr(h) for h in HEADER])
        stamp = time.strftime("%Y-%m-%d %H:%M")
        for r in rows:
            w.writerow([stamp, r["name"], human(r["size"]), r["size"], r.get("source", ""), r.get("url") or "",
                        r.get("page") or "", r["label"], r["src"], r["dst"]])
