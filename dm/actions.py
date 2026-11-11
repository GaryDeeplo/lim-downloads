"""Exécution des actions avec journal SQLite : tout est réversible jusqu'à la purge de la quarantaine."""
import os
import shutil
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .config import Config

ERROR_NOT_SAME_DEVICE = 17
CHUNK = 8 << 20
Progress = Callable[[int], None]   # reçoit le nombre d'octets copiés depuis le dernier appel

SCHEMA = """
CREATE TABLE IF NOT EXISTS batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created REAL NOT NULL,
    label TEXT NOT NULL,
    action TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'done'      -- done | undone | purged
);
CREATE TABLE IF NOT EXISTS ops (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER NOT NULL REFERENCES batches(id),
    src TEXT NOT NULL,
    dst TEXT,
    size INTEGER NOT NULL,
    status TEXT NOT NULL,                   -- ok | error | restored
    error TEXT
);
"""


@dataclass
class Op:
    src: str
    dest_dir: str | None    # None = quarantaine
    size: int
    mtime: float
    is_dir: bool


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    n = 2
    while True:
        candidate = path.with_name(f"{path.stem} ({n}){path.suffix}") if path.suffix else path.with_name(f"{path.name} ({n})")
        if not candidate.exists():
            return candidate
        n += 1


def _copy_file(src: str, dst: str, progress: Progress):
    with open(src, "rb") as fi, open(dst, "wb") as fo:
        while chunk := fi.read(CHUNK):
            fo.write(chunk)
            progress(len(chunk))
    shutil.copystat(src, dst)
    if os.path.getsize(dst) != os.path.getsize(src):
        raise OSError(f"copie incomplète : {dst}")


def safe_move(src: str, dst: str, progress: Progress = lambda _: None, size: int = 0):
    """Renommage instantané sur le même disque ; sinon copie, vérification des tailles, puis suppression de la source.
    En cas d'échec, la copie partielle est effacée et la source reste intacte."""
    try:
        os.rename(src, dst)
        progress(size)
        return
    except OSError as e:
        if getattr(e, "winerror", None) != ERROR_NOT_SAME_DEVICE:
            raise
    try:
        if os.path.isdir(src):
            for dirpath, _, filenames in os.walk(src):
                target = os.path.join(dst, os.path.relpath(dirpath, src))
                os.makedirs(target, exist_ok=True)
                for fn in filenames:
                    _copy_file(os.path.join(dirpath, fn), os.path.join(target, fn), progress)
        else:
            _copy_file(src, dst, progress)
    except BaseException:
        shutil.rmtree(dst, ignore_errors=True) if os.path.isdir(dst) else (os.path.exists(dst) and os.remove(dst))
        raise
    shutil.rmtree(src) if os.path.isdir(src) else os.remove(src)


class _Rows:
    def __init__(self, cur: sqlite3.Cursor):
        self.rows = cur.fetchall()
        self.lastrowid = cur.lastrowid

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class _LockedDB:
    """Connexion partagée entre threads : chaque requête est verrouillée, jamais une opération sur les fichiers.
    Un long transfert n'empêche donc pas d'agir ailleurs dans l'interface."""
    def __init__(self, path: Path):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.RLock()

    def execute(self, sql: str, params=()) -> _Rows:
        with self.lock:
            return _Rows(self.conn.execute(sql, params))

    def executescript(self, sql: str):
        with self.lock:
            self.conn.executescript(sql)

    def commit(self):
        with self.lock:
            self.conn.commit()


class Journal:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        cfg.data_dir.mkdir(parents=True, exist_ok=True)
        self.db = _LockedDB(cfg.db_path)
        self.db.executescript(SCHEMA)

    def _inside_downloads(self, path: str) -> bool:
        root = os.path.normcase(os.path.abspath(self.cfg.downloads))
        p = os.path.normcase(os.path.abspath(path))
        return os.path.dirname(p) == root

    def apply(self, label: str, action: str, ops: list[Op], progress: Progress = lambda _: None,
              after_move: Callable[[str], None] | None = None) -> dict:
        cur = self.db.execute("INSERT INTO batches(created, label, action) VALUES (?,?,?)", (time.time(), label, action))
        batch_id = cur.lastrowid
        done = errors = moved_bytes = 0
        results = []
        for op in ops:
            dst, status, error = None, "ok", None
            try:
                if not self._inside_downloads(op.src):
                    raise ValueError("hors du dossier Téléchargements")
                if not os.path.exists(op.src):
                    raise FileNotFoundError("n'existe plus")
                if not op.is_dir:
                    st = os.stat(op.src)
                    if st.st_size != op.size:
                        raise ValueError("modifié depuis le scan")
                target_dir = Path(op.dest_dir) if op.dest_dir else self.cfg.quarantine_dir / str(batch_id)
                target_dir.mkdir(parents=True, exist_ok=True)
                dst = str(unique_path(target_dir / os.path.basename(op.src)))
                safe_move(op.src, dst, progress, op.size)
                done += 1
                moved_bytes += op.size
            except Exception as e:  # on continue le lot, l'erreur est journalisée
                status, error, dst = "error", str(e), None
                errors += 1
            if dst and after_move:
                try:
                    after_move(dst)
                except Exception as e:  # le fichier est bien arrivé : on le note sans annuler
                    error = f"après déplacement : {e}"
            self.db.execute("INSERT INTO ops(batch_id, src, dst, size, status, error) VALUES (?,?,?,?,?,?)",
                            (batch_id, op.src, dst, op.size, status, error))
            results.append({"src": op.src, "dst": dst, "ok": status == "ok", "error": error})
        self.db.commit()
        return {"batch_id": batch_id, "done": done, "errors": errors, "bytes": moved_bytes, "results": results}

    def undo(self, batch_id: int) -> dict:
        batch = self.db.execute("SELECT * FROM batches WHERE id=?", (batch_id,)).fetchone()
        if not batch or batch["state"] != "done":
            raise ValueError("lot introuvable, déjà annulé ou purgé")
        restored = errors = 0
        paths = []  # (chemin d'origine, chemin réel après restauration)
        rows = self.db.execute("SELECT * FROM ops WHERE batch_id=? AND status='ok' ORDER BY id DESC", (batch_id,)).fetchall()
        for row in rows:
            try:
                target = unique_path(Path(row["src"]))  # si un fichier du même nom est revenu entre-temps
                safe_move(row["dst"], str(target))
                paths.append((row["src"], str(target)))
                self.db.execute("UPDATE ops SET status='restored', error=NULL WHERE id=?", (row["id"],))
                restored += 1
            except Exception as e:
                self.db.execute("UPDATE ops SET error=? WHERE id=?", (f"restauration : {e}", row["id"]))
                errors += 1
        if errors == 0:
            self.db.execute("UPDATE batches SET state='undone' WHERE id=?", (batch_id,))
            qdir = self.cfg.quarantine_dir / str(batch_id)
            if qdir.exists() and not any(qdir.iterdir()):
                qdir.rmdir()
        self.db.commit()
        return {"restored": restored, "errors": errors, "paths": paths}

    def restored_paths(self) -> set[str]:
        """Chemins dont un déplacement a été annulé : le tri auto ne doit plus y toucher."""
        rows = self.db.execute("SELECT DISTINCT src FROM ops WHERE status='restored'").fetchall()
        return {os.path.normcase(r["src"]) for r in rows}

    def history(self, limit: int = 50) -> list[dict]:
        rows = self.db.execute("""
            SELECT b.*, COUNT(o.id) AS count, COALESCE(SUM(o.size), 0) AS bytes,
                   SUM(o.status='error') AS errors
            FROM batches b LEFT JOIN ops o ON o.batch_id=b.id
            GROUP BY b.id ORDER BY b.id DESC LIMIT ?""", (limit,)).fetchall()
        return [dict(r) for r in rows]

    def quarantine_stats(self) -> dict:
        row = self.db.execute("""
            SELECT COUNT(o.id) AS count, COALESCE(SUM(o.size), 0) AS bytes, MIN(b.created) AS oldest
            FROM batches b JOIN ops o ON o.batch_id=b.id
            WHERE b.action='quarantine' AND b.state='done' AND o.status='ok'""").fetchone()
        return dict(row)

    def quarantine_items(self) -> list[dict]:
        """Tout ce qui dort en quarantaine, lot par lot (le plus récent d'abord), gros fichiers en tête."""
        rows = self.db.execute("""
            SELECT o.id, o.batch_id, o.src, o.dst, o.size, b.created, b.label
            FROM batches b JOIN ops o ON o.batch_id=b.id
            WHERE b.action='quarantine' AND b.state='done' AND o.status='ok'
            ORDER BY b.id DESC, o.size DESC""").fetchall()
        return [dict(r) for r in rows]

    def quarantine_op(self, op_id: int) -> dict:
        row = self.db.execute("""
            SELECT o.*, b.state, b.action FROM ops o JOIN batches b ON b.id=o.batch_id WHERE o.id=?""", (op_id,)).fetchone()
        if not row or row["action"] != "quarantine" or row["state"] != "done" or row["status"] != "ok":
            raise ValueError("cet élément n'est plus en quarantaine")
        return dict(row)

    def restore_op(self, op_id: int) -> dict:
        """Ressort UN élément de la quarantaine ; le lot passe à « annulé » quand il est vide."""
        row = self.quarantine_op(op_id)
        target = unique_path(Path(row["src"]))
        safe_move(row["dst"], str(target))
        self.db.execute("UPDATE ops SET status='restored', error=NULL WHERE id=?", (op_id,))
        left = self.db.execute("SELECT COUNT(*) FROM ops WHERE batch_id=? AND status='ok'", (row["batch_id"],)).fetchone()[0]
        if not left:
            self.db.execute("UPDATE batches SET state='undone' WHERE id=?", (row["batch_id"],))
            qdir = self.cfg.quarantine_dir / str(row["batch_id"])
            if qdir.exists() and not any(qdir.iterdir()):
                qdir.rmdir()
        self.db.commit()
        return {"batch_id": row["batch_id"], "src": row["src"], "path": str(target), "batch_empty": not left}

    def purge_batch(self, batch_id: int) -> dict:
        """Supprime définitivement UN lot de la quarantaine, sans attendre la fin du délai."""
        batch = self.db.execute("SELECT * FROM batches WHERE id=?", (batch_id,)).fetchone()
        if not batch or batch["action"] != "quarantine" or batch["state"] != "done":
            raise ValueError("ce lot n'est pas (ou plus) en quarantaine")
        freed = self.db.execute("SELECT COALESCE(SUM(size),0) FROM ops WHERE batch_id=? AND status='ok'",
                                (batch_id,)).fetchone()[0]
        shutil.rmtree(self.cfg.quarantine_dir / str(batch_id), ignore_errors=True)
        self.db.execute("UPDATE batches SET state='purged' WHERE id=?", (batch_id,))
        self.db.commit()
        return {"batches": 1, "bytes": freed}

    def purge(self, older_than_days: int | None = None) -> dict:
        days = self.cfg.quarantine_days if older_than_days is None else older_than_days
        cutoff = time.time() - days * 86400
        batches = self.db.execute("SELECT id FROM batches WHERE action='quarantine' AND state='done' AND created <= ?",
                                  (cutoff,)).fetchall()
        freed = 0
        for b in batches:
            qdir = self.cfg.quarantine_dir / str(b["id"])
            freed += self.db.execute("SELECT COALESCE(SUM(size),0) FROM ops WHERE batch_id=? AND status='ok'",
                                     (b["id"],)).fetchone()[0]
            shutil.rmtree(qdir, ignore_errors=True)
            self.db.execute("UPDATE batches SET state='purged' WHERE id=?", (b["id"],))
        self.db.commit()
        return {"batches": len(batches), "bytes": freed, "ids": [b["id"] for b in batches]}
