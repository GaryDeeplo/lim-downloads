"""Reçus de quarantaine : un CSV lisible dans Excel qui garde nom, taille et lien d'origine de tout ce qui part."""
import csv
import time
from pathlib import Path

RECEIPT_NAME = "Reçus de quarantaine.csv"
HEADER = ["date", "nom", "taille", "octets", "source", "lien de téléchargement", "page d'origine", "lot",
          "emplacement d'origine", "emplacement en quarantaine"]


def human(n: float) -> str:
    for unit in ("o", "Ko", "Mo", "Go", "To"):
        if n < 1024 or unit == "To":
            return f"{n:.1f} {unit}".replace(".0 ", " ").replace(".", ",")
        n /= 1024
    return str(n)


def write_receipts(path: Path, rows: list[dict]):
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8-sig" if new else "utf-8") as f:
        w = csv.writer(f, delimiter=";")
        if new:
            w.writerow(HEADER)
        stamp = time.strftime("%Y-%m-%d %H:%M")
        for r in rows:
            w.writerow([stamp, r["name"], human(r["size"]), r["size"], r.get("source", ""), r.get("url") or "",
                        r.get("page") or "", r["label"], r["src"], r["dst"]])
