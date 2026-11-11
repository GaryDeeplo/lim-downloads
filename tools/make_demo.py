r"""Crée un faux dossier Téléchargements pour tester l'interface sans toucher aux vrais fichiers.

Usage : python tools/make_demo.py  puis  set DM_CONFIG=%TEMP%\dm-demo\config.json && python -m dm
"""
import json
import os
import random
import shutil
import tempfile
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(tempfile.gettempdir()) / "dm-demo"
DL = ROOT / "Downloads"
PALETTE = [(255, 90, 31), (13, 154, 128), (91, 87, 217), (201, 143, 0), (217, 61, 113), (46, 114, 179)]


def image(path: Path, seed: int, size=(900, 640)):
    rnd = random.Random(seed)
    img = Image.new("RGB", size, rnd.choice(PALETTE))
    d = ImageDraw.Draw(img)
    for _ in range(14):
        x, y, r = rnd.randrange(size[0]), rnd.randrange(size[1]), rnd.randrange(40, 260)
        d.ellipse((x - r, y - r, x + r, y + r), fill=rnd.choice(PALETTE))
    img.save(path)


def zone(path: Path, url: str, referrer: str = ""):
    """Simule la provenance qu'un navigateur enregistre (flux Zone.Identifier)."""
    with open(str(path) + ":Zone.Identifier", "w", encoding="utf-8") as f:
        f.write(f"[ZoneTransfer]\nZoneId=3\nReferrerUrl={referrer}\nHostUrl={url}\n")


def main():
    shutil.rmtree(ROOT, ignore_errors=True)
    DL.mkdir(parents=True)
    for i in range(36):
        name = f"photo_{i:02d}.{'png' if i % 3 else 'jpg'}"
        image(DL / name, i)
        if i % 4 == 0:
            zone(DL / name, f"https://images.pexels.com/photos/{i}.jpg", "https://www.pexels.com/")
    for i in (1, 4, 7):
        shutil.copy(DL / f"photo_{i:02d}.png", DL / f"photo_{i:02d} (1).png")
    for name in ("Facture_2025-03.pdf", "Rapport annuel.pdf", "Brief client.docx", "Budget.xlsx", "Pitch.pptx", "notes.txt"):
        (DL / name).write_bytes(os.urandom(random.randint(20_000, 400_000)))
    zone(DL / "Facture_2025-03.pdf", "https://mail-attachment.googleusercontent.com/x", "https://mail.google.com/")
    for name in ("Setup-Outil.exe", "Installer.msi"):
        (DL / name).write_bytes(b"MZ" + os.urandom(300_000))
    for name in ("podcast.mp3", "voix-off.wav"):
        (DL / name).write_bytes(os.urandom(500_000))
    (DL / "film.mp4.crdownload").write_bytes(os.urandom(50_000))
    (DL / "vide.txt").write_bytes(b"")
    (DL / "Projet site").mkdir()
    for i in range(5):
        image(DL / "Projet site" / f"maquette_{i}.png", 100 + i, (400, 300))
    with zipfile.ZipFile(DL / "Projet site.zip", "w") as zf:
        for f in (DL / "Projet site").iterdir():
            zf.write(f, f.name)
    with zipfile.ZipFile(DL / "vieille-archive.zip", "w") as zf:
        zf.writestr("readme.txt", "x" * 5000)
    (DL / "mystere.xyz").write_bytes(b"?")

    # Gros volumes : torrent, export Drive en plusieurs zips, transfert expiré
    serie = DL / "[ Torrent911.io ] Ma Serie.S01.INTEGRALE.1080p.WEB.x264"
    serie.mkdir()
    for ep in range(1, 7):
        (serie / f"Ma.Serie.S01E{ep:02d}.1080p.mkv").write_bytes(os.urandom(400_000))
    for part in range(1, 5):
        z = DL / f"drive-download-20251202T130731Z-1-00{part}.zip"
        with zipfile.ZipFile(z, "w") as zf:
            for k in range(3):
                zf.writestr(f"Clients/dossier-{part}/photo-{k}.jpg", os.urandom(80_000))
        zone(z, "https://drive.usercontent.google.com/download?id=demo", "https://drive.google.com/")
    (DL / "wetransfer_rushes-tournage.zip").write_bytes(os.urandom(600_000))
    zone(DL / "wetransfer_rushes-tournage.zip", "https://download.wetransfer.com/eu2/demo")

    # Copies déjà sauvegardées ailleurs
    backup = ROOT / "Documents" / "CLIENTS" / "Archive"
    backup.mkdir(parents=True)
    contrat = os.urandom(90_000)
    (backup / "Contrat signé.pdf").write_bytes(contrat)
    (DL / "Contrat signé (1).pdf").write_bytes(contrat)
    (DL / "Logos client").mkdir()
    for i in range(3):
        data = os.urandom(30_000 + i)
        (DL / "Logos client" / f"logo-{i}.png").write_bytes(data)
        (backup / f"logo-{i}.png").write_bytes(data)

    (ROOT / "OneDrive").mkdir()
    (ROOT / "Externe").mkdir()
    paths = {"downloads": "Downloads", "data_dir": "data", "videos_dest": "Videos", "pictures_dest": "Pictures",
             "music_dest": "Music", "documents_dest": "Documents/Téléchargements",
             "onedrive_dest": "OneDrive/Téléchargements archivés", "external_dest": "Externe/Téléchargements archivés"}
    cfg = {k: str(ROOT / v) for k, v in paths.items()}
    cfg.update(protect_days=0, installer_days=0, old_archive_days=0, redownload_min_mb=0, detect_remote=False,
               backup_roots=[str(ROOT / "Documents"), str(ROOT / "OneDrive")])
    (ROOT / "config.json").write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    print(ROOT / "config.json")


if __name__ == "__main__":
    main()
