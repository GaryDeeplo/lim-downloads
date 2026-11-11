"""API locale + interface web. N'écoute que sur 127.0.0.1."""
import itertools
import os
import subprocess
import threading
import time
import zipfile
from collections import defaultdict
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .actions import Journal, Op
from .auto import AutoSorter
from .config import Config, load_config
from .foreground import launch
from .receipts import RECEIPT_NAME, write_receipts
from .remote import find_remotes, free_local_copy
from .rules import (ARCHIVES, AUDIO, DOCUMENTS, IMAGES, INSTALLERS, QUARANTINE, TARGETS, VIDEOS, Bucket, build_plan,
                    target_dest)
from .scanner import scan
from .thumbs import ThumbCache

STATIC = Path(__file__).parent / "static"
EXECUTABLE = INSTALLERS | {".bat", ".cmd", ".ps1", ".vbs", ".js", ".jse", ".wsf", ".lnk", ".url", ".scr",
                           ".com", ".jar", ".hta", ".reg", ".msp", ".appinstaller", ".html", ".htm", ".svg"}
THUMB_SIZES = {128, 256, 512}
FAMILIES = [("videos", "Vidéos", VIDEOS), ("images", "Images", IMAGES), ("audio", "Audio", AUDIO),
            ("documents", "Documents", DOCUMENTS), ("archives", "Archives", ARCHIVES)]
MAX_LISTED = 20000


class AutoRequest(BaseModel):
    enabled: bool | None = None
    delay_hours: float | None = None
    actions: list[str] | None = None


class ApplyRequest(BaseModel):
    ids: list[int]
    target: str | None = None   # None = la cible par défaut du lot de chaque élément


def _family(name: str) -> str:
    ext = os.path.splitext(name)[1].lower()
    return next((k for k, _, exts in FAMILIES if ext in exts), "other")


def create_app(cfg: Config | None = None, start_auto: bool = False) -> FastAPI:
    """start_auto : lance la surveillance en tâche de fond (l'appli réelle ; pas les tests)."""
    cfg = cfg or load_config()
    journal = Journal(cfg)
    thumbs = ThumbCache(cfg.data_dir / "miniatures")
    receipts_path = cfg.documents_dest / RECEIPT_NAME
    app = FastAPI(title="Downloads Manager")
    lock = threading.Lock()          # état du plan
    job_ids = itertools.count(1)
    state = {"status": "idle", "phase": "", "error": None, "buckets": [], "entries": {}, "removed": {},
             "pending": set(), "jobs": {}, "scanned_at": None, "duration": 0, "auto_events": []}
    auto_seq = itertools.count(1)

    def on_auto_batches(batches: list[dict]):
        """Un tri auto a eu lieu : retire ces éléments du plan affiché et prévient l'interface (et la notification)."""
        moved = {p for b in batches for p in b["paths"]}
        with lock:
            for b in state["buckets"]:
                b.entries = [e for e in b.entries if e.item.path not in moved]
            state["entries"] = {i: (b, e) for i, (b, e) in state["entries"].items() if e.item.path not in moved}
            state["auto_events"] = (state["auto_events"] + [{"id": next(auto_seq), "time": time.time(),
                                                               "batches": batches}])[-20:]
        notify = getattr(app.state, "notify", None)
        if notify:
            notify(batches)

    auto = AutoSorter(cfg, journal, on_auto_batches)

    def remotes():
        return find_remotes(cfg)

    def targets() -> list[dict]:
        out = [{"key": t.key, "label": t.label, "path": str(t.root(cfg)), "available": True, "remote": False}
               for t in TARGETS.values()]
        out += [{"key": r.key, "label": r.label, "path": str(r.root) if r.root else "", "available": r.available,
                 "remote": True, "free": r.free, "hint": r.hint} for r in remotes()]
        return out + [{"key": QUARANTINE, "label": "Quarantaine", "path": str(cfg.quarantine_dir), "available": True,
                       "remote": False}]

    def target_label(key: str) -> str:
        if key == QUARANTINE:
            return "Quarantaine"
        if key in TARGETS:
            return TARGETS[key].label
        return next((r.label for r in remotes() if r.key == key), key)

    def run_scan():
        t0 = time.time()
        set_phase = lambda p: state.__setitem__("phase", p)
        try:
            set_phase("Indexation")
            items = scan(cfg.downloads)
            buckets = build_plan(items, cfg, progress=set_phase)
            entries = {}
            for b in buckets:
                for e in b.entries:
                    entries[len(entries)] = (b, e)
            with lock:
                state.update(status="ready", phase="", error=None, buckets=buckets, entries=entries, removed={},
                             pending=set(), scanned_at=time.time(), duration=round(time.time() - t0, 1))
        except Exception as e:
            with lock:
                state.update(status="error", phase="", error=str(e))

    def source_dict(src) -> dict | None:
        if not src or src.kind == "unknown":
            return None
        return {"kind": src.kind, "label": src.label, "url": src.url, "page": src.page, "expirable": src.expirable,
                "redownloadable": src.redownloadable}

    def serialize(buckets: list[Bucket], entries: dict) -> list[dict]:
        ids = {id(e): i for i, (_, e) in entries.items()}
        by_path = {e.item.path: i for i, (_, e) in entries.items()}
        return [{
            "key": b.key, "title": b.title, "description": b.description, "target": b.target, "action": b.action,
            "entries": [{
                "id": ids[id(e)], "name": e.item.name, "is_dir": e.item.is_dir, "size": e.item.size,
                "mtime": e.item.mtime, "ext": e.item.ext, "reason": e.reason, "dest": e.dest,
                "checked": e.checked, "files": e.item.file_count, "parts": len(e.item.members),
                "source": source_dict(e.item.source),
                "keeper": by_path.get(e.keeper.path) if e.keeper else None,
            } for e in b.entries],
        } for b in buckets]

    def reveal_in_explorer(path: str):
        launch(lambda: subprocess.Popen(["explorer", "/select,", path]), Path(path).parent.name)

    def get_entry(entry_id: int):
        with lock:
            found = state["entries"].get(entry_id)
        if not found:
            raise HTTPException(404, "élément inconnu, relance un scan")
        return found

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})

    @app.get("/favicon.svg")
    def favicon():
        return FileResponse(STATIC / "favicon.svg")

    if (STATIC / "assets").exists():
        app.mount("/assets", StaticFiles(directory=STATIC / "assets"), name="assets")

    @app.post("/api/scan")
    def start_scan():
        with lock:
            if state["status"] == "scanning":
                return {"status": "scanning"}
            if state["pending"]:
                raise HTTPException(409, "un transfert est en cours")
            state["status"] = "scanning"
        threading.Thread(target=run_scan, daemon=True).start()
        return {"status": "scanning"}

    @app.get("/api/plan")
    def plan():
        with lock:
            payload = {k: state[k] for k in ("status", "phase", "error", "scanned_at", "duration")}
            payload["root"] = str(cfg.downloads)
            payload["targets"] = targets()
            payload["receipts"] = str(receipts_path) if receipts_path.exists() else None
            if state["status"] == "ready":
                payload["buckets"] = serialize(state["buckets"], state["entries"])
        return payload

    def finalize(result: dict, chosen: list, op_owner: list[int], tkey: str, label: str) -> dict:
        """Regroupe les résultats par élément (un export Drive = plusieurs fichiers) et met le plan à jour."""
        per_entry: dict[int, list[dict]] = defaultdict(list)
        for owner, r in zip(op_owner, result["results"]):
            per_entry[owner].append(r)
        moved, failed, removed, receipt_rows = [], [], [], []
        with lock:
            for n, (i, b, e) in enumerate(chosen):
                rs = per_entry[n]
                if all(r["ok"] for r in rs):
                    moved.append(i)
                    b.entries = [x for x in b.entries if x is not e]
                    state["entries"].pop(i, None)
                    removed.append((i, b, e))
                    src = e.item.source
                    receipt_rows.append({"name": e.item.name, "size": e.item.size, "label": label,
                                         "source": src.label if src else "", "url": src.url if src else None,
                                         "page": src.page if src else None, "src": e.item.path, "dst": rs[0]["dst"]})
                else:
                    failed.append({"id": i, "error": next(r["error"] for r in rs if not r["ok"])})
            state["removed"][result["batch_id"]] = (tkey, removed)
            state["pending"] -= {i for i, _, _ in chosen}
        if tkey == QUARANTINE:
            try:
                write_receipts(receipts_path, receipt_rows)
            except OSError:
                pass  # le reçu ne doit jamais bloquer : le journal SQLite garde aussi chaque chemin
        return {"batch_id": result["batch_id"], "target": tkey, "done": len(moved), "errors": len(failed),
                "bytes": result["bytes"], "moved": moved, "failed": failed}

    @app.post("/api/apply")
    def apply(req: ApplyRequest):
        available = {r.key: r.root for r in remotes() if r.available}
        if req.target is not None and req.target != QUARANTINE and req.target not in TARGETS and req.target not in available:
            raise HTTPException(400, "cible inconnue ou indisponible")
        with lock:
            chosen = [(i, *state["entries"][i]) for i in req.ids if i in state["entries"] and i not in state["pending"]]
            chosen = [(i, b, e, req.target or b.target) for i, b, e in chosen if (req.target or b.target)]
            if not chosen:
                raise HTTPException(400, "aucun élément applicable")
            tkeys = {t for *_, t in chosen}
            if len(tkeys) > 1:
                raise HTTPException(400, "un seul dossier cible par action")
            state["pending"] |= {i for i, *_ in chosen}
        tkey = tkeys.pop()
        chosen = [(i, b, e) for i, b, e, _ in chosen]
        sources = {b.title for _, b, _ in chosen}
        label = f"{sources.pop() if len(sources) == 1 else 'Sélection'} → {target_label(tkey)}"

        ops, op_owner = [], []
        for n, (_, _, e) in enumerate(chosen):
            dest = target_dest(tkey, e.item, cfg, available)
            for part in e.item.members or [e.item]:
                ops.append(Op(part.path, str(dest) if dest else None, part.size, part.mtime, part.is_dir))
                op_owner.append(n)
        after = free_local_copy if tkey == "onedrive" else None
        action = QUARANTINE if tkey == QUARANTINE else "move"
        root = (cfg.quarantine_dir if tkey == QUARANTINE else TARGETS[tkey].root(cfg) if tkey in TARGETS
                else available[tkey])
        dest_drive = os.path.splitdrive(str(root))[0].lower()
        cross = any(os.path.splitdrive(op.src)[0].lower() != dest_drive for op in ops)

        if not cross:
            try:
                result = journal.apply(label, action, ops, after_move=after)
            except Exception:
                with lock:
                    state["pending"] -= {i for i, _, _ in chosen}
                raise
            return finalize(result, chosen, op_owner, tkey, label)

        # Autre disque : copie longue, en tâche de fond avec progression.
        job_id = next(job_ids)
        job = {"status": "running", "total": sum(op.size for op in ops), "done": 0, "target": tkey,
               "ids": [i for i, _, _ in chosen], "result": None, "error": None}
        state["jobs"][job_id] = job

        def progress(n: int):
            job["done"] += n

        def run():
            try:
                result = journal.apply(label, action, ops, progress=progress, after_move=after)
                job["result"] = finalize(result, chosen, op_owner, tkey, label)
                job["status"] = "done"
            except Exception as e:
                with lock:
                    state["pending"] -= set(job["ids"])
                job.update(status="error", error=str(e))

        threading.Thread(target=run, daemon=True).start()
        return {"job": job_id, "target": tkey, "total": job["total"], "ids": job["ids"]}

    @app.get("/api/jobs/{job_id}")
    def job_status(job_id: int):
        job = state["jobs"].get(job_id)
        if not job:
            raise HTTPException(404)
        return job

    @app.get("/api/auto")
    def auto_status():
        with lock:
            events = state["auto_events"][-5:]
        recent = [b for b in journal.history(200) if b["label"].startswith("Auto · ")][:10]
        return auto.status() | {"events": events, "recent": recent}

    @app.post("/api/auto")
    def auto_update(req: AutoRequest):
        auto.update(enabled=req.enabled, delay_hours=req.delay_hours, actions=req.actions)
        if req.delay_hours is not None or req.actions is not None or req.enabled:
            auto.refresh_preview_async()
        return auto_status()

    @app.post("/api/auto/preview")
    def auto_preview():
        auto.refresh_preview_async()
        return auto_status()

    @app.post("/api/auto/run")
    def auto_run():
        if state["pending"]:
            raise HTTPException(409, "un transfert est en cours")
        batches = auto.run_once()
        auto.refresh_preview_async()
        return {"batches": batches}

    @app.get("/api/history")
    def history():
        return {"batches": journal.history(), "quarantine": journal.quarantine_stats(),
                "quarantine_days": cfg.quarantine_days, "quarantine_dir": str(cfg.quarantine_dir),
                "receipts": str(receipts_path) if receipts_path.exists() else None}

    @app.post("/api/undo/{batch_id}")
    def undo(batch_id: int):
        try:
            result = journal.undo(batch_id)
        except ValueError as e:
            raise HTTPException(400, str(e))
        restored_at = dict(result["paths"])
        ids = []
        with lock:  # remet les éléments dans leur lot pour qu'ils réapparaissent sans rescanner
            tkey, removed = state["removed"].pop(batch_id, (None, []))
            for i, b, e in removed:
                parts = e.item.members or [e.item]
                if all(p.path in restored_at for p in parts):
                    for p in parts:
                        p.path = restored_at[p.path]
                        p.name = os.path.basename(p.path)
                    if e.item.members:
                        e.item.path = parts[0].path
                    else:
                        e.item.name = os.path.basename(e.item.path)
                    b.entries.append(e)
                    b.entries.sort(key=lambda x: x.item.size, reverse=True)
                    state["entries"][i] = (b, e)
                    ids.append(i)
        restored_entries = sum(len(e.item.members) or 1 for i, _, e in removed if i in ids)
        return {"restored": len(ids), "errors": result["errors"], "ids": ids, "target": tkey,
                "rescan": result["restored"] > restored_entries}

    @app.get("/api/quarantine")
    def quarantine():
        batches = {}
        for r in journal.quarantine_items():
            b = batches.setdefault(r["batch_id"], {"id": r["batch_id"], "label": r["label"], "created": r["created"],
                                                   "expires": r["created"] + cfg.quarantine_days * 86400,
                                                   "count": 0, "bytes": 0, "items": []})
            name = os.path.basename(r["dst"])
            is_dir = os.path.isdir(r["dst"])
            b["count"] += 1
            b["bytes"] += r["size"]
            b["items"].append({"op": r["id"], "name": name, "size": r["size"], "is_dir": is_dir,
                               "ext": "" if is_dir else os.path.splitext(name)[1].lower(),
                               "origin": os.path.dirname(r["src"]), "exists": os.path.exists(r["dst"])})
        return {"days": cfg.quarantine_days, "dir": str(cfg.quarantine_dir), "batches": list(batches.values())}

    @app.get("/api/quarantine/{op_id}/thumb")
    def quarantine_thumb(op_id: int, s: int = 256):
        try:
            row = journal.quarantine_op(op_id)
        except ValueError:
            raise HTTPException(404)
        if s not in THUMB_SIZES or not os.path.exists(row["dst"]):
            raise HTTPException(404)
        out = thumbs.get(row["dst"], row["size"], os.path.getmtime(row["dst"]), s)
        if not out:
            raise HTTPException(404)
        return FileResponse(out, media_type="image/webp", headers={"Cache-Control": "max-age=86400"})

    @app.post("/api/quarantine/{op_id}/restore")
    def quarantine_restore(op_id: int):
        try:
            result = journal.restore_op(op_id)
        except ValueError as e:
            raise HTTPException(400, str(e))
        except OSError as e:
            raise HTTPException(500, f"restauration impossible : {e}")
        ids = []
        with lock:  # l'élément reprend sa place dans son lot si c'était un fichier seul
            tkey, removed = state["removed"].get(result["batch_id"], (None, []))
            for i, b, e in list(removed):
                if not e.item.members and e.item.path == result["src"]:
                    e.item.path = result["path"]
                    e.item.name = os.path.basename(result["path"])
                    b.entries.append(e)
                    b.entries.sort(key=lambda x: x.item.size, reverse=True)
                    state["entries"][i] = (b, e)
                    removed.remove((i, b, e))
                    ids.append(i)
            if result["batch_empty"]:
                state["removed"].pop(result["batch_id"], None)
        return {"name": os.path.basename(result["path"]), "ids": ids, "rescan": not ids}

    @app.post("/api/purge/{batch_id}")
    def purge_batch(batch_id: int):
        try:
            result = journal.purge_batch(batch_id)
        except ValueError as e:
            raise HTTPException(400, str(e))
        with lock:
            state["removed"].pop(batch_id, None)
        return result

    @app.post("/api/purge")
    def purge(all: bool = False):
        """Supprime ce qui a dépassé le délai ; all=true vide toute la quarantaine tout de suite."""
        result = journal.purge(older_than_days=0 if all else None)
        with lock:
            for i in result["ids"]:
                state["removed"].pop(i, None)
        return result

    @app.get("/api/contents/{entry_id}")
    def contents(entry_id: int):
        """Ce qu'il y a dedans : répartition par type et plus gros fichiers (dossier, zip ou export Drive)."""
        _, e = get_entry(entry_id)
        files: list[tuple[str, int]] = []
        truncated = False
        if e.item.is_dir:
            for dirpath, _, filenames in os.walk(e.item.path):
                for fn in filenames:
                    full = os.path.join(dirpath, fn)
                    try:
                        files.append((os.path.relpath(full, e.item.path), os.path.getsize(full)))
                    except OSError:
                        continue
                    if len(files) >= MAX_LISTED:
                        truncated = True
                        break
                if truncated:
                    break
        elif e.item.ext == ".zip":
            for part in e.item.members or [e.item]:
                try:
                    with zipfile.ZipFile(part.path) as zf:
                        files += [(i.filename, i.file_size) for i in zf.infolist() if not i.is_dir()]
                except (zipfile.BadZipFile, OSError):
                    continue
        else:
            raise HTTPException(404)
        fam: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        for name, size in files:
            f = fam[_family(name)]
            f[0] += 1
            f[1] += size
        labels = {k: label for k, label, _ in FAMILIES} | {"other": "Autres"}
        return {
            "files": len(files), "bytes": sum(s for _, s in files), "truncated": truncated,
            "families": sorted(({"key": k, "label": labels[k], "count": c, "bytes": s} for k, (c, s) in fam.items()),
                               key=lambda x: -x["bytes"]),
            "top": [{"name": n, "size": s} for n, s in sorted(files, key=lambda x: -x[1])[:12]],
        }

    @app.get("/api/thumb/{entry_id}")
    def thumb(entry_id: int, s: int = 256):
        _, e = get_entry(entry_id)
        if s not in THUMB_SIZES or not os.path.exists(e.item.path):
            raise HTTPException(404)
        out = thumbs.get(e.item.path, e.item.size, e.item.mtime, s)
        if not out:
            raise HTTPException(404)
        return FileResponse(out, media_type="image/webp", headers={"Cache-Control": "max-age=86400"})

    @app.post("/api/open/{entry_id}")
    def open_entry(entry_id: int):
        _, e = get_entry(entry_id)
        if e.item.is_dir or e.item.ext not in EXECUTABLE:  # jamais lancer un installeur ou un script
            if os.path.exists(e.item.path):
                launch(lambda: os.startfile(e.item.path), Path(e.item.path).name if e.item.is_dir else None)
        else:
            reveal_in_explorer(e.item.path)
        return {"ok": True}

    @app.post("/api/reveal/{entry_id}")
    def reveal(entry_id: int):
        _, e = get_entry(entry_id)
        reveal_in_explorer(e.item.path)
        return {"ok": True}

    @app.post("/api/open-target/{key}")
    def open_target(key: str):
        roots = {r.key: r.root for r in remotes() if r.available}
        path = (cfg.quarantine_dir if key == QUARANTINE else TARGETS[key].root(cfg) if key in TARGETS
                else roots.get(key))
        if path is None:
            raise HTTPException(404, "destination indisponible")
        path.mkdir(parents=True, exist_ok=True)
        launch(lambda: os.startfile(path), path.name)
        return {"ok": True}

    @app.post("/api/show")
    def show_window():
        """Un deuxième lancement de l'exe ramène la fenêtre déjà ouverte."""
        show = getattr(app.state, "show_window", None)
        if show:
            show()
        return {"window": bool(show)}

    @app.post("/api/open-receipts")
    def open_receipts():
        if not receipts_path.exists():
            raise HTTPException(404, "aucun reçu pour l'instant")
        launch(lambda: os.startfile(receipts_path))
        return {"ok": True}

    app.state.auto = auto
    app.state.journal = journal
    if start_auto:
        auto.start()
    return app
