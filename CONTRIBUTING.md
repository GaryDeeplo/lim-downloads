# Contributing

Thanks for helping. Bug reports, ideas and pull requests are all welcome.

## Set up

```bat
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
cd web && npm ci
```

- Back end: `python -m dm` (or `start.bat`) serves the app on `http://127.0.0.1:8765`.
- Front end: `cd web && npm run dev` while working on the interface, `npm run build` to update `dm/static`.
- Demo data: `python tools\make_demo.py`, then `set DM_CONFIG=%TEMP%\dm-demo\config.json` so you never touch your real Downloads folder.
- README GIFs: `python tools\record_demo.py --lang en` (or `fr`) with the demo server on port 8766. Frames come from the app's web view only (DevTools screencast), never from the screen; keep the screen awake while it records.

## Before you open a pull request

- Run the tests: `.venv\Scripts\python -m pytest`. Add a test for any new rule or action.
- If you changed the front end, run `npm run build` in `web/` and commit the updated `dm/static`.
- Keep the safety promise: nothing may be deleted outside the quarantine, and every action must stay undoable.
- Keep pull requests focused on one change.

## Where things live

| Path | Content |
|---|---|
| `dm/rules.py`, `dm/detect.py`, `dm/scanner.py` | Batch rules, duplicates, extracted zips |
| `dm/actions.py` | Moves, quarantine, undo and purge (SQLite journal) |
| `dm/auto.py` | Auto-sort |
| `dm/server.py` | Local API |
| `web/src/` | Interface |
| `tests/test_dm.py` | Tests |
