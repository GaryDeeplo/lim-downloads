import os
import time
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dm.actions import Journal, Op
from dm.config import Config
from dm.rules import build_plan
from dm.scanner import scan
from dm.server import create_app

LATER = time.time() + 400 * 86400  # tout paraît « vieux » pour les règles basées sur l'âge


@pytest.fixture
def cfg(tmp_path: Path) -> Config:
    dl = tmp_path / "Downloads"
    dl.mkdir()
    return Config(downloads=dl, data_dir=tmp_path / "data", videos_dest=tmp_path / "Videos",
                  pictures_dest=tmp_path / "Pictures", music_dest=tmp_path / "Music",
                  documents_dest=tmp_path / "Documents", onedrive_dest=None, detect_remote=False, backup_roots=[],
                  auto_enabled=True)


def write(path: Path, data: bytes = b"x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def buckets(cfg, now=LATER):
    return {b.key: b for b in build_plan(scan(cfg.downloads), cfg, now) if b.entries}


def names(bucket):
    return sorted(e.item.name for e in bucket.entries)


def test_duplicates_keep_clean_name(cfg):
    big = os.urandom(300_000)
    write(cfg.downloads / "rapport.pdf", big)
    write(cfg.downloads / "rapport (1).pdf", big)
    write(cfg.downloads / "autre.pdf", big[:-1] + b"\0")      # même taille, contenu différent
    b = buckets(cfg)
    assert names(b["duplicates"]) == ["rapport (1).pdf"]
    assert "rapport.pdf" in names(b["documents"]) and "autre.pdf" in names(b["documents"])


def _make_zip(path: Path, files: dict[str, bytes]):
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)


def test_extracted_zip_detection(cfg):
    files = {"proj/a.txt": b"aaa", "proj/sub/b.txt": b"bbbb"}
    _make_zip(cfg.downloads / "proj.zip", files)
    for name, data in files.items():                          # extraction « Extraire tout » de Windows : proj/proj/...
        write(cfg.downloads / "proj" / name, data)

    _make_zip(cfg.downloads / "flat.zip", {"x.txt": b"1", "y.txt": b"22"})
    write(cfg.downloads / "flat" / "x.txt", b"1")
    write(cfg.downloads / "flat" / "y.txt", b"22")

    _make_zip(cfg.downloads / "partiel.zip", {"x.txt": b"1", "y.txt": b"333"})
    write(cfg.downloads / "partiel" / "x.txt", b"1")          # y.txt manquant → pas proposé

    b = buckets(cfg)
    assert names(b["extracted_zips"]) == ["flat.zip", "proj.zip"]
    assert "partiel.zip" in names(b["archives"])


def test_misc_rules_and_sensitive(cfg):
    write(cfg.downloads / "film.mkv.crdownload", b"abc")
    write(cfg.downloads / "facture.part", b"abc")
    write(cfg.downloads / "vide.txt", b"")
    write(cfg.downloads / "setup.exe", b"MZ")
    write(cfg.downloads / "photo.jpg", b"jpg")
    b = buckets(cfg)
    inc = {e.item.name: e for e in b["incomplete"].entries}
    assert set(inc) == {"film.mkv.crdownload", "facture.part", "vide.txt"}
    assert inc["facture.part"].checked is False and inc["film.mkv.crdownload"].checked is True
    assert names(b["installers"]) == ["setup.exe"]
    assert b["images"].entries[0].dest.startswith(str(cfg.pictures_dest))


def test_recent_files_are_protected(cfg):
    write(cfg.downloads / "setup.exe", b"MZ")
    write(cfg.downloads / "dl.crdownload", b"..")
    b = buckets(cfg, now=time.time())
    assert set(b) == {"recent"}
    assert all(not e.checked for e in b["recent"].entries)


def test_quarantine_undo_and_purge(cfg):
    f = write(cfg.downloads / "a.exe", b"MZ")
    j = Journal(cfg)
    r = j.apply("test", "quarantine", [Op(str(f), None, 2, 0, False)])
    assert r["done"] == 1 and not f.exists()
    assert j.quarantine_stats()["count"] == 1
    j.undo(r["batch_id"])
    assert f.read_bytes() == b"MZ"
    with pytest.raises(ValueError):
        j.undo(r["batch_id"])

    r = j.apply("test", "quarantine", [Op(str(f), None, 2, 0, False)])
    assert j.purge(older_than_days=1)["batches"] == 0       # trop récent
    assert j.purge(older_than_days=0)["batches"] == 1
    assert not (cfg.quarantine_dir / str(r["batch_id"])).exists()


def test_move_with_collision_and_undo(cfg):
    dest = cfg.documents_dest / "2026"
    write(dest / "doc.pdf", b"existant")
    f = write(cfg.downloads / "doc.pdf", b"nouveau")
    j = Journal(cfg)
    r = j.apply("docs", "move", [Op(str(f), str(dest), 7, 0, False)])
    assert (dest / "doc (2).pdf").read_bytes() == b"nouveau"
    assert (dest / "doc.pdf").read_bytes() == b"existant"
    j.undo(r["batch_id"])
    assert f.read_bytes() == b"nouveau"


def test_refuses_changed_or_outside_files(cfg, tmp_path):
    f = write(cfg.downloads / "a.bin", b"1234")
    outside = write(tmp_path / "ailleurs.bin", b"1")
    j = Journal(cfg)
    r = j.apply("t", "quarantine", [Op(str(f), None, 999, 0, False), Op(str(outside), None, 1, 0, False)])
    assert (r["done"], r["errors"], r["bytes"]) == (0, 2, 0)
    assert f.exists() and outside.exists()


def _ready_client(cfg):
    client = TestClient(create_app(cfg))
    client.post("/api/scan")
    for _ in range(100):
        plan = client.get("/api/plan").json()
        if plan["status"] == "ready":
            return client, plan
        time.sleep(0.05)
    raise AssertionError(plan)


def test_api_apply_and_undo_restores_plan(cfg):
    cfg.protect_days = 0
    write(cfg.downloads / "dl.crdownload", b"..")
    write(cfg.downloads / "keep.pdf", b"%PDF")
    client, plan = _ready_client(cfg)
    assert {t["key"] for t in plan["targets"]} >= {"images", "quarantine"}
    inc = next(b for b in plan["buckets"] if b["key"] == "incomplete")
    ids = [e["id"] for e in inc["entries"]]
    r = client.post("/api/apply", json={"ids": ids}).json()
    assert r["moved"] == ids and r["target"] == "quarantine" and not (cfg.downloads / "dl.crdownload").exists()
    assert not next(b for b in client.get("/api/plan").json()["buckets"] if b["key"] == "incomplete")["entries"]
    u = client.post(f"/api/undo/{r['batch_id']}").json()
    assert u["ids"] == ids and not u["rescan"] and (cfg.downloads / "dl.crdownload").exists()
    assert next(b for b in client.get("/api/plan").json()["buckets"] if b["key"] == "incomplete")["entries"]


def test_api_drag_to_explicit_target(cfg):
    cfg.protect_days = 0
    write(cfg.downloads / "notes.xyz", b"?")
    client, plan = _ready_client(cfg)
    other = next(b for b in plan["buckets"] if b["key"] == "other")
    assert client.post("/api/apply", json={"ids": [other["entries"][0]["id"]]}).status_code == 400   # pas de cible par défaut
    assert client.post("/api/apply", json={"ids": [other["entries"][0]["id"]], "target": "nope"}).status_code == 400
    r = client.post("/api/apply", json={"ids": [other["entries"][0]["id"]], "target": "folders"}).json()
    assert r["done"] == 1 and (cfg.documents_dest / "Dossiers" / "notes.xyz").exists()


def test_api_rejects_mixed_targets(cfg):
    cfg.protect_days = 0
    write(cfg.downloads / "a.jpg", b"j")
    write(cfg.downloads / "b.mp3", b"m")
    client, plan = _ready_client(cfg)
    ids = [e["id"] for b in plan["buckets"] for e in b["entries"]]
    assert client.post("/api/apply", json={"ids": ids}).status_code == 400


# ——— Gros volumes : sources, exports Drive, copies sauvegardées, retéléchargeable, reçus, distant ———

from dm import actions as actions_mod
from dm.sources import detect as detect_source


def zone(path: Path, url: str, referrer: str = ""):
    with open(str(path) + ":Zone.Identifier", "w", encoding="utf-8") as f:
        f.write(f"[ZoneTransfer]\nZoneId=3\nReferrerUrl={referrer}\nHostUrl={url}\n")


def test_source_detection(cfg):
    a = write(cfg.downloads / "export.zip", b"z")
    zone(a, "https://drive.usercontent.google.com/download?id=1", "https://drive.google.com/")
    b = write(cfg.downloads / "photos.zip", b"z")
    zone(b, "https://download.wetransfer.com/eu2/abc")
    assert detect_source(str(a), a.name, False).redownloadable
    wt = detect_source(str(b), b.name, False)
    assert wt.expirable and not wt.redownloadable
    assert detect_source("x", "Film.2020.1080p.WEB-DL.x264", True).kind == "torrent"
    assert detect_source("x", "drive-download-20251202T130731Z-1-001", True).kind == "drive"
    assert detect_source("x", "swisstransfer_123.zip", False).expirable


def test_drive_export_parts_are_one_item(cfg):
    cfg.redownload_min_mb = 0
    for n in (1, 2, 3):
        _make_zip(cfg.downloads / f"drive-download-20251202T130731Z-1-00{n}.zip", {f"f{n}.txt": os.urandom(100)})
    b = buckets(cfg)
    entries = b["redownload"].entries
    assert len(entries) == 1 and len(entries[0].item.members) == 3 and not entries[0].checked
    assert entries[0].item.name.endswith("(3 parties)")


def test_backed_up_elsewhere(cfg, tmp_path):
    backup = tmp_path / "Backup"
    cfg.backup_roots = [backup]
    data = os.urandom(5000)
    write(backup / "deep" / "rapport.pdf", data)
    write(cfg.downloads / "rapport-copie.pdf", data)                      # même contenu, autre nom
    _make_zip(cfg.downloads / "lot.zip", {"x/rapport.pdf": data})        # contenu du zip déjà sauvegardé
    write(cfg.downloads / "projet" / "a.pdf", data)
    write(cfg.downloads / "projet" / "b.pdf", os.urandom(77))            # un fichier introuvable → pas proposé
    b = buckets(cfg)
    assert names(b["backed_up"]) == ["lot.zip", "rapport-copie.pdf"]
    assert all(e.checked for e in b["backed_up"].entries)
    assert "projet" in names(b["folders"])


def test_quarantine_writes_receipt(cfg):
    cfg.protect_days = 0
    f = write(cfg.downloads / "film.crdownload", b"..")
    zone(f, "https://example.org/film.mkv", "https://example.org/")
    client, plan = _ready_client(cfg)
    inc = next(b for b in plan["buckets"] if b["key"] == "incomplete")
    client.post("/api/apply", json={"ids": [e["id"] for e in inc["entries"]]})
    text = (cfg.documents_dest / "Reçus de quarantaine.csv").read_text(encoding="utf-8-sig")
    assert "film.crdownload" in text and "https://example.org/film.mkv" in text


def test_drive_parts_move_and_undo_together(cfg):
    cfg.protect_days = 0
    cfg.redownload_min_mb = 0
    for n in (1, 2):
        _make_zip(cfg.downloads / f"x-20251202T130731Z-1-00{n}.zip", {f"f{n}.txt": os.urandom(50)})
    client, plan = _ready_client(cfg)
    entry = next(b for b in plan["buckets"] if b["key"] == "redownload")["entries"][0]
    assert entry["parts"] == 2 and entry["source"]["kind"] == "drive"
    r = client.post("/api/apply", json={"ids": [entry["id"]], "target": "archives"}).json()
    assert r["done"] == 1 and not list(cfg.downloads.glob("*.zip"))
    u = client.post(f"/api/undo/{r['batch_id']}").json()
    assert u["ids"] == [entry["id"]] and not u["rescan"] and len(list(cfg.downloads.glob("*.zip"))) == 2


def test_safe_move_across_disks(tmp_path, monkeypatch):
    real_rename = os.rename

    def no_rename(a, b):
        err = OSError("autre disque")
        err.winerror = actions_mod.ERROR_NOT_SAME_DEVICE
        raise err

    monkeypatch.setattr(actions_mod.os, "rename", no_rename)
    src = write(tmp_path / "a" / "dossier" / "f.bin", os.urandom(20_000)).parent
    seen = []
    actions_mod.safe_move(str(src), str(tmp_path / "b"), seen.append)
    assert not src.exists() and (tmp_path / "b" / "f.bin").stat().st_size == 20_000 and sum(seen) == 20_000

    src2 = write(tmp_path / "c.bin", b"x" * 100)
    monkeypatch.setattr(actions_mod, "_copy_file", lambda *a: (_ for _ in ()).throw(OSError("disque plein")))
    with pytest.raises(OSError):
        actions_mod.safe_move(str(src2), str(tmp_path / "d.bin"))
    assert src2.exists() and not (tmp_path / "d.bin").exists()   # source intacte, pas de copie partielle
    monkeypatch.setattr(actions_mod.os, "rename", real_rename)


def test_remote_target_onedrive(cfg, tmp_path):
    cfg.protect_days = 0
    (tmp_path / "OneDrive").mkdir()
    cfg.onedrive_dest = tmp_path / "OneDrive" / "Archivés"
    write(cfg.downloads / "gros.mkv", b"v" * 10)
    client, plan = _ready_client(cfg)
    od = next(t for t in plan["targets"] if t["key"] == "onedrive")
    assert od["available"] and od["remote"]
    assert not next(t for t in plan["targets"] if t["key"] == "gdrive")["available"]
    vid = next(b for b in plan["buckets"] if b["key"] == "videos")["entries"][0]
    r = client.post("/api/apply", json={"ids": [vid["id"]], "target": "onedrive"}).json()
    assert r["done"] == 1 and (cfg.onedrive_dest / "gros.mkv").exists()
    assert client.post("/api/apply", json={"ids": [vid["id"]], "target": "gdrive"}).status_code == 400


def test_cross_disk_move_runs_as_job(cfg, tmp_path, monkeypatch):
    cfg.protect_days = 0
    ext = tmp_path / "Externe"
    ext.mkdir()
    cfg.external_dest = ext / "Archivés"
    cfg.detect_remote = True
    import dm.remote as remote_mod
    monkeypatch.setattr(remote_mod, "_drives", lambda: [])
    real_split = os.path.splitdrive
    monkeypatch.setattr(os.path, "splitdrive", lambda p: ("x:", p) if "Externe" in str(p) else real_split(p))
    write(cfg.downloads / "film.mkv", b"v" * 1000)
    client, plan = _ready_client(cfg)
    vid = next(b for b in plan["buckets"] if b["key"] == "videos")["entries"][0]
    r = client.post("/api/apply", json={"ids": [vid["id"]], "target": "external"}).json()
    assert "job" in r and r["total"] == 1000
    for _ in range(100):
        job = client.get(f"/api/jobs/{r['job']}").json()
        if job["status"] != "running":
            break
        time.sleep(0.05)
    assert job["status"] == "done" and job["result"]["moved"] == [vid["id"]] and job["done"] == 1000
    assert (cfg.external_dest / "film.mkv").exists()


def test_contents_of_folder_and_zip(cfg):
    cfg.protect_days = 0
    write(cfg.downloads / "pack" / "a.mp4", b"v" * 300)
    write(cfg.downloads / "pack" / "b.jpg", b"i" * 100)
    _make_zip(cfg.downloads / "z.zip", {"doc.pdf": b"p" * 50})
    client, plan = _ready_client(cfg)
    entries = {e["name"]: e for b in plan["buckets"] for e in b["entries"]}
    c = client.get(f"/api/contents/{entries['pack']['id']}").json()
    assert c["files"] == 2 and c["families"][0]["key"] == "videos" and c["top"][0]["name"] == "a.mp4"
    assert client.get(f"/api/contents/{entries['z.zip']['id']}").json()["families"][0]["key"] == "documents"


# ——— Tri automatique ———

from dm.auto import AutoSorter


def test_auto_only_touches_new_files_after_delay(cfg):
    old = os.urandom(3000)
    write(cfg.downloads / "ancien.pdf", old)
    write(cfg.downloads / "vieux-setup.exe", b"MZ1")
    time.sleep(0.05)
    auto = AutoSorter(cfg, Journal(cfg))
    time.sleep(0.05)
    write(cfg.downloads / "photo.jpg", b"img")
    write(cfg.downloads / "outil-setup.exe", b"MZ2")
    write(cfg.downloads / "facture-setup.exe", b"MZ3")          # nom sensible : jamais en quarantaine auto
    write(cfg.downloads / "ancien (1).pdf", old)                # doublon d'un ancien fichier
    write(cfg.downloads / "projet" / "a.txt", b"a")              # dossiers : jamais en auto
    _make_zip(cfg.downloads / "pack.zip", {"x.txt": b"x"})

    assert auto.run_once(now=time.time() + 3600) == []          # délai pas encore écoulé
    batches = auto.run_once(now=time.time() + 8 * 86400)
    moved = sorted(n for b in batches for n in b["names"])
    assert moved == ["ancien (1).pdf", "outil-setup.exe", "photo.jpg"]
    assert all(b["label"].startswith("Auto · ") for b in batches)
    left = sorted(p.name for p in cfg.downloads.iterdir())
    assert left == ["ancien.pdf", "facture-setup.exe", "pack.zip", "projet", "vieux-setup.exe"]
    receipt = (cfg.documents_dest / "Reçus de quarantaine.csv").read_text(encoding="utf-8-sig")
    assert "outil-setup.exe" in receipt and "ancien (1).pdf" in receipt


def test_auto_disabled_and_reenable_resets_start(cfg):
    auto = AutoSorter(cfg, Journal(cfg))
    auto.set_enabled(False)
    write(cfg.downloads / "photo.jpg", b"img")
    assert auto.run_once(now=time.time() + 8 * 86400) == []
    time.sleep(0.05)
    auto.set_enabled(True)                                       # arrivé pendant la pause : pas trié
    assert auto.run_once(now=time.time() + 8 * 86400) == []
    assert AutoSorter(cfg, Journal(cfg)).enabled                 # l'état est mémorisé


def test_auto_api_and_undo(cfg):
    client = TestClient(create_app(cfg))
    assert client.get("/api/auto").json()["enabled"] is True
    assert client.post("/api/auto", json={"enabled": False}).json()["enabled"] is False
    assert client.post("/api/auto/run").json() == {"batches": []}
    client.post("/api/auto", json={"enabled": True})
    time.sleep(0.05)
    write(cfg.downloads / "photo.jpg", b"img")
    cfg.auto_delay_hours = 0
    r = client.post("/api/auto/run").json()
    assert r["batches"] and r["batches"][0]["target"] == "images"
    events = client.get("/api/auto").json()["events"]
    assert events[-1]["batches"][0]["batch_id"] == r["batches"][0]["batch_id"]
    client.post(f"/api/undo/{r['batches'][0]['batch_id']}")
    assert (cfg.downloads / "photo.jpg").exists()


def test_auto_never_resorts_an_undone_file(cfg):
    auto = AutoSorter(cfg, Journal(cfg))
    time.sleep(0.05)
    write(cfg.downloads / "photo.jpg", b"img")
    later = time.time() + 8 * 86400
    batch = auto.run_once(now=later)[0]
    auto.journal.undo(batch["batch_id"])
    assert (cfg.downloads / "photo.jpg").exists()
    assert auto.run_once(now=later) == []


def test_purge_one_batch_now(cfg):
    a = write(cfg.downloads / "a.exe", b"MZ")
    b = write(cfg.downloads / "b.exe", b"MZ")
    j = Journal(cfg)
    ra = j.apply("t", "quarantine", [Op(str(a), None, 2, 0, False)])
    rb = j.apply("t", "quarantine", [Op(str(b), None, 2, 0, False)])
    assert j.purge_batch(ra["batch_id"])["bytes"] == 2
    assert not (cfg.quarantine_dir / str(ra["batch_id"])).exists()
    assert (cfg.quarantine_dir / str(rb["batch_id"]) / "b.exe").exists()   # l'autre lot reste
    with pytest.raises(ValueError):
        j.undo(ra["batch_id"])
    with pytest.raises(ValueError):
        j.purge_batch(ra["batch_id"])
    m = j.apply("t", "move", [Op(str(write(cfg.downloads / "c.pdf", b"p")), str(cfg.documents_dest), 1, 0, False)])
    with pytest.raises(ValueError):
        j.purge_batch(m["batch_id"])                                        # un rangement ne se purge pas


def test_restore_one_item_from_quarantine(cfg):
    a = write(cfg.downloads / "a.exe", b"MZ")
    b = write(cfg.downloads / "b.exe", b"MZZ")
    j = Journal(cfg)
    r = j.apply("t", "quarantine", [Op(str(a), None, 2, 0, False), Op(str(b), None, 3, 0, False)])
    items = j.quarantine_items()
    assert [i["size"] for i in items] == [3, 2]                         # gros fichiers en tête
    first = j.restore_op(items[0]["id"])
    assert b.exists() and not first["batch_empty"]
    assert j.quarantine_stats()["count"] == 1
    with pytest.raises(ValueError):
        j.restore_op(items[0]["id"])                                     # déjà ressorti
    assert j.restore_op(items[1]["id"])["batch_empty"] and a.exists()
    assert not (cfg.quarantine_dir / str(r["batch_id"])).exists()
    assert j.history()[0]["state"] == "undone"


def test_api_quarantine_view_and_restore(cfg):
    cfg.protect_days = 0
    write(cfg.downloads / "dl.crdownload", b"..")
    client, plan = _ready_client(cfg)
    inc = next(b for b in plan["buckets"] if b["key"] == "incomplete")
    client.post("/api/apply", json={"ids": [e["id"] for e in inc["entries"]]})
    q = client.get("/api/quarantine").json()
    assert q["days"] == cfg.quarantine_days and len(q["batches"]) == 1
    item = q["batches"][0]["items"][0]
    assert item["name"] == "dl.crdownload" and item["origin"] == str(cfg.downloads) and item["exists"]
    r = client.post(f"/api/quarantine/{item['op']}/restore").json()
    assert r["ids"] == [inc["entries"][0]["id"]] and not r["rescan"] and (cfg.downloads / "dl.crdownload").exists()
    assert next(b for b in client.get("/api/plan").json()["buckets"] if b["key"] == "incomplete")["entries"]
    assert client.get("/api/quarantine").json()["batches"] == []
    assert client.post(f"/api/quarantine/{item['op']}/restore").status_code == 400


def test_api_empty_quarantine_now(cfg):
    cfg.protect_days = 0
    write(cfg.downloads / "dl.crdownload", b"..")
    client, plan = _ready_client(cfg)
    inc = next(b for b in plan["buckets"] if b["key"] == "incomplete")
    r = client.post("/api/apply", json={"ids": [e["id"] for e in inc["entries"]]}).json()
    assert client.post("/api/purge").json()["batches"] == 0                  # rien n'a dépassé le délai
    assert client.post("/api/purge?all=true").json()["batches"] == 1         # vider : tout part
    assert client.get("/api/quarantine").json()["batches"] == []
    assert not (cfg.quarantine_dir / str(r["batch_id"])).exists()


def test_auto_settings_and_preview(cfg):
    auto = AutoSorter(cfg, Journal(cfg))
    time.sleep(0.05)
    write(cfg.downloads / "photo.jpg", b"img")
    write(cfg.downloads / "outil-setup.exe", b"MZ2")
    write(cfg.downloads / "notes.xyz", b"?")
    auto.update(delay_hours=48, actions=["sort", "nope"])
    again = AutoSorter(cfg, Journal(cfg))                         # réglages mémorisés
    assert again.delay_hours == 48 and again.actions == ["sort"]
    p = auto.compute_preview()
    rows = {r["name"]: r for r in p["items"]}
    assert rows["photo.jpg"]["target"] == "images" and rows["photo.jpg"]["due"] - rows["photo.jpg"]["arrived"] == 48 * 3600
    assert rows["outil-setup.exe"]["target"] is None and "pas trié automatiquement" in rows["outil-setup.exe"]["skip"]
    assert rows["notes.xyz"]["target"] is None
    assert p["items"][0]["name"] == "photo.jpg"                   # ce qui sera rangé passe en premier


def test_auto_off_until_configured(tmp_path):
    cfg = Config(downloads=tmp_path, data_dir=tmp_path / "data", detect_remote=False, backup_roots=[])
    auto = AutoSorter(cfg, Journal(cfg))
    assert not auto.enabled and not auto.configured                # éteint par défaut, en attente de réglage
    auto.update(delay_hours=72)
    assert auto.configured and not auto.enabled
    auto.update(enabled=True)
    again = AutoSorter(cfg, Journal(cfg))
    assert again.enabled and again.configured and again.delay_hours == 72
