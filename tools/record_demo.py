r"""Enregistre le GIF de démo du README (docs/demo.gif) sur les fausses données de make_demo.py.

Les images viennent du moteur web de la fenêtre de démo (protocole DevTools, « screencast ») et jamais de
l'écran : aucune autre fenêtre, notification ou donnée personnelle ne peut se retrouver dans le GIF.
Un scénario JavaScript pilote l'interface : rangement des images, doublons en quarantaine, quarantaine, Lim.

Prérequis : ffmpeg dans le PATH, et le serveur de démo sur le port 8766 :
    python tools\make_demo.py
    set DM_CONFIG=%TEMP%\dm-demo\config.json
    python -c "import uvicorn; from dm.server import create_app; from dm.config import load_config; uvicorn.run(create_app(load_config()), port=8766)"
Usage : .venv\Scripts\python tools\record_demo.py [--lang en|fr]
"""
import argparse
import base64
import json
import shutil
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

import webview
from websockets.sync.client import connect

ROOT = Path(__file__).resolve().parent.parent
URL = "http://127.0.0.1:8766"
DEBUG_PORT = 9223
W, H = 1280, 760
SECONDS = 20
HOLD_LAST = 1.5  # la dernière image reste affichée un instant avant que le GIF reboucle

# Préparation (avant l'enregistrement) : fermer Lim, outils de pilotage, chemin anonyme, lot Images
SETUP = (
    "document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape'}));"
          "window.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape'}));"
          "window.__nav = (t) => { const b = [...document.querySelectorAll('nav button')].find(x => x.textContent.trim().startsWith(t)); b && b.click() };"
          "window.__hold = (t, ms) => { const b = [...document.querySelectorAll('button')].find(x => x.textContent.trim().startsWith(t)); if (!b) return;"
          "  b.focus(); b.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true}));"
          "  setTimeout(() => { b.dispatchEvent(new KeyboardEvent('keyup', {key: 'Enter', bubbles: true})); b.blur() }, ms) };"
          "const p = [...document.querySelectorAll('header div')].find(d => d.title && d.title.includes('dm-demo'));"
          "if (p) p.textContent = 'C:\\\\Users\\\\you\\\\Downloads';"
          "__nav(window.__t.images)"
)

# Scénario : [délai depuis le début de l'enregistrement en s, code JS]
STEPS = [
    (1.2, "__hold(window.__t.sort, 1100)"),
    (4.7, "__nav(window.__t.dups)"),
    (6.2, "__hold(window.__t.quarantine, 1100)"),
    (9.2, "document.querySelector('[data-target=\"quarantine\"]').click()"),
    (12.2, "document.querySelector('[data-tour=\"guide\"]').click()"),
    (15.7, "window.dispatchEvent(new KeyboardEvent('keydown', {key: 'ArrowRight'}))"),
]

LABELS = {
    "en": {"images": "Images", "sort": "Sort", "dups": "Exact duplicates", "quarantine": "Move to quarantine"},
    "fr": {"images": "Images", "sort": "Ranger", "dups": "Doublons exacts", "quarantine": "Mettre en quarantaine"},
}


def post(path: str, body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(URL + path, data=data, method="POST",
                                 headers={"X-Downloads-Manager": "1", "Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=30).read()


def prepare(lang: str):
    """Langue, scan, et miniatures calculées d'avance (sinon les photos s'affichent d'abord en icône)."""
    post("/api/language", {"language": lang})
    time.sleep(1)
    post("/api/scan")
    time.sleep(5)
    plan = json.load(urllib.request.urlopen(URL + "/api/plan", timeout=30))
    for bucket in plan["buckets"]:
        for e in bucket["entries"]:
            try:
                urllib.request.urlopen(f"{URL}/api/thumb/{e['id']}?s=256", timeout=30).read()
            except OSError:
                pass  # pas de miniature pour ce type de fichier


def screencast(frames_dir: Path, stop: threading.Event) -> list[tuple[float, Path]]:
    """Reçoit les images de la page via DevTools jusqu'à `stop` ; renvoie (horodatage, fichier)."""
    targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{DEBUG_PORT}/json", timeout=10))
    page = next(t for t in targets if t.get("type") == "page" and t["url"].startswith(URL))
    frames = []
    with connect(page["webSocketDebuggerUrl"], max_size=None) as ws:
        ws.send(json.dumps({"id": 1, "method": "Page.startScreencast",
                            "params": {"format": "jpeg", "quality": 90, "maxWidth": W, "maxHeight": H}}))
        while not stop.is_set():
            try:
                msg = json.loads(ws.recv(timeout=0.5))
            except TimeoutError:
                continue
            if msg.get("method") != "Page.screencastFrame":
                continue
            p = msg["params"]
            path = frames_dir / f"{len(frames):05d}.jpg"
            path.write_bytes(base64.b64decode(p["data"]))
            frames.append((p["metadata"]["timestamp"], path))
            ws.send(json.dumps({"id": 2, "method": "Page.screencastFrameAck", "params": {"sessionId": p["sessionId"]}}))
        ws.send(json.dumps({"id": 3, "method": "Page.stopScreencast"}))
    return frames


def to_gif(frames: list[tuple[float, Path]], work: Path, out_gif: Path):
    """Images à intervalles irréguliers (une par changement) → GIF à 15 images/s via la liste concat de ffmpeg."""
    lines = []
    ends = [t for t, _ in frames[1:]] + [frames[-1][0] + HOLD_LAST]
    for (t, path), end in zip(frames, ends):
        lines += [f"file '{path.as_posix()}'", f"duration {max(0.01, end - t):.3f}"]
    lines.append(f"file '{frames[-1][1].as_posix()}'")
    listing = work / "frames.txt"
    listing.write_text("\n".join(lines), encoding="utf-8")
    vf = ("fps=15,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128:stats_mode=diff[p];"
          "[b][p]paletteuse=dither=bayer:bayer_scale=4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
                    "-vf", vf, str(out_gif)], check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", default="en", choices=["en", "fr"])
    args = ap.parse_args()
    out_gif = ROOT / "docs" / ("demo.gif" if args.lang == "en" else "demo.fr.gif")
    work = ROOT / "build" / f"demo-{args.lang}"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)

    prepare(args.lang)
    webview.settings["REMOTE_DEBUGGING_PORT"] = DEBUG_PORT
    win = webview.create_window("Lim demo", URL, width=W, height=H, x=0, y=0, on_top=True, resizable=False)
    result: dict = {}

    def run():
        stop = threading.Event()
        try:
            win.events.loaded.wait(20)
            time.sleep(3)  # Lim se présente au premier lancement : on le laisse arriver, le scénario le ferme
            win.evaluate_js(f"window.__t = {json.dumps(LABELS[args.lang])}")
            win.evaluate_js(SETUP)
            time.sleep(2.5)  # le temps que les miniatures s'affichent
            cast = threading.Thread(target=lambda: result.update(frames=screencast(work, stop)))
            cast.start()
            time.sleep(0.5)
            t0 = time.time()
            for at, js in STEPS:
                time.sleep(max(0, at - (time.time() - t0)))
                win.evaluate_js(js)
            time.sleep(max(0, SECONDS - (time.time() - t0)))
            stop.set()
            cast.join()
        except Exception as e:  # une étape ratée : on le dit, et le GIF partiel n'est pas gardé
            result["error"] = repr(e)
            stop.set()
        finally:
            win.destroy()

    threading.Thread(target=run, daemon=True).start()
    webview.start(private_mode=True)

    frames = result.get("frames") or []
    if "error" in result:
        raise SystemExit(f"scénario interrompu : {result['error']} — GIF non créé")
    if len(frames) < 10:
        raise SystemExit(f"trop peu d'images reçues ({len(frames)}) : GIF non créé")
    to_gif(frames, work, out_gif)
    print(f"{out_gif} ({out_gif.stat().st_size / 1e6:.1f} Mo, {len(frames)} images)")


if __name__ == "__main__":
    main()
