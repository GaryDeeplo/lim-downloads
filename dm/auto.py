"""Tri automatique en continu.

Garde-fous : ne touche qu'aux éléments arrivés APRÈS l'activation (l'arriéré reste au tri manuel), attend le délai
configuré, n'applique que les actions autorisées, saute les noms sensibles, journalise tout (annulable) et écrit
un reçu avant toute quarantaine.
"""
import dataclasses
import json
import os
import threading
import time
from collections import defaultdict
from typing import Callable

from .actions import Journal, Op
from .config import Config
from .receipts import RECEIPT_NAME, write_receipts
from .rules import QUARANTINE, TARGETS, build_plan, target_dest
from .scanner import scan

# Action autorisée → lots concernés
ACTION_BUCKETS = {
    "sort": {"videos", "images", "documents", "audio"},
    "duplicates": {"duplicates"},
    "installers": {"installers"},
    "backed_up": {"backed_up"},
}


class AutoSorter:
    def __init__(self, cfg: Config, journal: Journal, on_batches: Callable[[list[dict]], None] = lambda _: None):
        self.cfg = cfg
        self.journal = journal
        self.on_batches = on_batches
        self.file = cfg.data_dir / "auto.json"
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.wake = threading.Event()
        self.last_run: float | None = None
        self.last_error: str | None = None
        self.preview: dict | None = None      # ce qui attend son tour, recalculé à chaque passe
        self.computing = False
        saved = self._load()
        # Tant qu'il n'a pas été réglé dans l'appli, le tri auto suit config.json (éteint par défaut).
        self.configured: bool = saved.get("configured", False)
        self.enabled: bool = saved.get("enabled", cfg.auto_enabled) if self.configured else cfg.auto_enabled
        self.since: float = saved.get("since", time.time())
        self._delay: float | None = saved.get("delay_hours")      # réglé dans l'appli ; sinon config.json
        self._actions: list[str] | None = saved.get("actions")
        self._save()

    @property
    def delay_hours(self) -> float:
        return self.cfg.auto_delay_hours if self._delay is None else self._delay

    @property
    def actions(self) -> list[str]:
        return list(self.cfg.auto_actions) if self._actions is None else self._actions

    def _load(self) -> dict:
        try:
            return json.loads(self.file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _save(self):
        self.file.parent.mkdir(parents=True, exist_ok=True)
        data = {"enabled": self.enabled, "since": self.since, "configured": self.configured}
        if self._delay is not None:
            data["delay_hours"] = self._delay
        if self._actions is not None:
            data["actions"] = self._actions
        self.file.write_text(json.dumps(data), encoding="utf-8")

    def set_enabled(self, enabled: bool):
        self.update(enabled=enabled)

    def update(self, enabled: bool | None = None, delay_hours: float | None = None, actions: list[str] | None = None):
        with self.lock:
            if enabled is not None:
                if enabled and not self.enabled:
                    self.since = time.time()  # rien de ce qui est arrivé pendant la pause n'est trié sans toi
                self.enabled = enabled
            if delay_hours is not None:
                self._delay = max(1.0, float(delay_hours))
            if actions is not None:
                self._actions = [a for a in ACTION_BUCKETS if a in actions]
            self.configured = True
            self._save()
        if self.enabled:
            self.wake.set()

    def status(self) -> dict:
        return {"enabled": self.enabled, "configured": self.configured, "since": self.since, "delay_hours": self.delay_hours,
                "actions": self.actions, "interval_minutes": self.cfg.auto_interval_minutes,
                "last_run": self.last_run, "last_error": self.last_error, "preview": self.preview,
                "computing": self.computing}

    def _allowed(self) -> set[str]:
        return set().union(*(ACTION_BUCKETS[a] for a in self.actions if a in ACTION_BUCKETS))

    def _plan(self, items: list, now: float):
        delay_days = self.delay_hours / 24
        plan_cfg = dataclasses.replace(self.cfg, protect_days=delay_days,
                                       installer_days=min(self.cfg.installer_days, delay_days))
        return build_plan(items, plan_cfg, now=now)

    def compute_preview(self, now: float | None = None, limit: int = 300) -> dict:
        """Ce que le tri auto fera de chaque fichier arrivé depuis son activation, et quand."""
        self.computing = True
        try:
            now = now or time.time()
            delay = self.delay_hours * 3600
            items = scan(self.cfg.downloads)
            undone = self.journal.restored_paths()
            new = {i.path for i in items if i.mtime >= self.since and os.path.normcase(i.path) not in undone}
            allowed = self._allowed()
            out = []
            if new:
                for bucket in self._plan(items, now + delay):  # dans « délai » heures, tout ce qui est arrivé sera dû
                    for e in bucket.entries:
                        if e.item.path not in new:
                            continue
                        ok = bool(bucket.key in allowed and bucket.target and e.checked and not e.item.members)
                        if ok:
                            why = None
                        elif e.item.members:
                            why = "export en plusieurs parties : à trier à la main"
                        elif bucket.key not in allowed or not bucket.target:
                            why = f"« {bucket.title} » n'est pas trié automatiquement"
                        else:
                            why = e.reason or "décoché par sécurité"
                        out.append({"name": e.item.name, "size": e.item.size, "is_dir": e.item.is_dir, "ext": e.item.ext,
                                    "arrived": e.item.mtime, "due": e.item.mtime + delay, "bucket": bucket.title,
                                    "target": bucket.target if ok else None, "skip": why})
            out.sort(key=lambda x: (x["target"] is None, x["due"]))
            self.preview = {"computed": time.time(), "total": len(out), "items": out[:limit]}
            return self.preview
        finally:
            self.computing = False

    def refresh_preview_async(self):
        if not self.computing:
            threading.Thread(target=self._safe_preview, daemon=True, name="tri-auto-apercu").start()

    def _safe_preview(self):
        try:
            self.compute_preview()
        except Exception as e:  # l'aperçu ne doit jamais casser l'appli
            self.last_error = f"aperçu : {e}"

    def run_once(self, now: float | None = None) -> list[dict]:
        """Une passe de tri. Renvoie les lots appliqués."""
        with self.lock:
            if not self.enabled:
                return []
            now = now or time.time()
            self.last_run = now
            delay = self.delay_hours * 3600
            items = scan(self.cfg.downloads)
            undone = self.journal.restored_paths()  # annulé une fois = laissé tranquille
            due = {i.path for i in items
                   if i.mtime >= self.since and now - i.mtime >= delay and os.path.normcase(i.path) not in undone}
            if not due:
                return []
            # Le plan complet sert à trouver doublons et copies ; seuls les éléments « dus » peuvent bouger.
            plan = self._plan(items, now)
            allowed = self._allowed()
            by_target: dict[str, list] = defaultdict(list)
            for bucket in plan:
                if bucket.key not in allowed or not bucket.target:
                    continue
                for e in bucket.entries:
                    if e.checked and not e.item.members and e.item.path in due:
                        by_target[bucket.target].append((bucket, e))
            batches = [self._apply(t, entries) for t, entries in by_target.items()]
        batches = [b for b in batches if b["done"]]
        if batches:
            self.on_batches(batches)
        return batches

    def _apply(self, tkey: str, entries: list) -> dict:
        label_t = "Quarantaine" if tkey == QUARANTINE else TARGETS[tkey].label
        titles = sorted({b.title for b, _ in entries})
        label = f"Auto · {', '.join(titles)} → {label_t}"
        ops = [Op(e.item.path, str(d) if (d := target_dest(tkey, e.item, self.cfg)) else None, e.item.size,
                  e.item.mtime, e.item.is_dir) for _, e in entries]
        result = self.journal.apply(label, QUARANTINE if tkey == QUARANTINE else "move", ops)
        if tkey == QUARANTINE:
            rows = []
            for (b, e), r in zip(entries, result["results"]):
                if r["ok"]:
                    src = e.item.source
                    rows.append({"name": e.item.name, "size": e.item.size, "label": label, "src": e.item.path,
                                 "dst": r["dst"], "source": src.label if src else "", "url": src.url if src else None,
                                 "page": src.page if src else None})
            try:
                write_receipts(self.cfg.documents_dest / RECEIPT_NAME, rows)
            except OSError:
                pass
        return {"batch_id": result["batch_id"], "label": label, "target": tkey, "done": result["done"],
                "bytes": result["bytes"], "paths": [r["src"] for r in result["results"] if r["ok"]],
                "names": [e.item.name for (_, e), r in zip(entries, result["results"]) if r["ok"]]}

    def loop(self):
        while not self.stop_event.is_set():
            try:
                self.run_once()
                self.last_error = None
                if self.enabled:
                    self.compute_preview()
            except Exception as e:  # une passe ratée ne doit pas arrêter la surveillance
                self.last_error = str(e)
            self.wake.wait(self.cfg.auto_interval_minutes * 60)
            self.wake.clear()

    def start(self):
        threading.Thread(target=self.loop, daemon=True, name="tri-auto").start()

    def stop(self):
        self.stop_event.set()
        self.wake.set()
