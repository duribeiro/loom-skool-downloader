# AGENTS.md

## Repo Structure

Two independent sub-projects (each has its own `.git`):

- **`hsl-lab/`** — Full-stack: Python Flask server + Chrome extension. The main project.
- **`loom-dl-extension/`** — Standalone Chrome extension (no server, in-browser conversion via mux.js).

No root-level git, no monorepo tooling, no shared config.

## Python Server

### Entry point

```
python loom-downloader-tool/server/app.py
```

Flask server on **port 5000**. Requires **FFmpeg in PATH** (exits immediately if missing).

### Setup

```bash
cd hsl-lab
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

Dependencies: `flask`, `flask-cors`, `requests`, `rich`. No pinned versions.

### Key quirks

- `use_reloader=False` is set in `app.run()` — **never remove this**, it duplicates the Rich dashboard thread.
- Dashboard runs in a daemon thread via `rich.live.Live`. It refreshes 4x/second and blocks the terminal. The server and dashboard share `DASHBOARD_DATA` (a plain list in `dashboard.py`) — thread-safe only because CPython GIL; do not introduce async or multiprocessing here.
- `ThreadPoolExecutor(max_workers=3)` in `routes.py` limits concurrent downloads. Segment-level parallelism uses 12 workers inside `downloader.py`.
- Temp files go to `hls-temp/` (relative to `loom-downloader-tool/`). Cleaned on startup and on Ctrl+C (`SIGINT`/`SIGTERM` handlers in `app.py`).
- Final output goes to `loom-downloader-tool/output/` with structure: `output/<Comunidade>/<Curso>/<Aula>.mp4`.
- Duplicate detection: skips download if final `.mp4` exists and is >1MB.
- No tests, no linting, no type checking configured.

### File map

| File | Role |
|------|------|
| `loom-downloader-tool/server/app.py` | Flask app, FFmpeg check, signal handlers, entry point |
| `loom-downloader-tool/server/routes.py` | `POST /baixar` endpoint, worker orchestration |
| `loom-downloader-tool/server/dashboard.py` | Rich terminal UI, `DASHBOARD_DATA` shared state |
| `loom-downloader-tool/server/services/utils.py` | HTTP headers (spoofed Chrome UA), filename sanitization, metadata extraction |
| `loom-downloader-tool/server/services/downloader.py` | HLS playlist parsing, multi-threaded .ts download |
| `loom-downloader-tool/server/services/converter.py` | FFmpeg invocation (TS→MP4, stream copy) |

## Chrome Extension (Embedded)

Located at `loom-downloader-tool/extension/`. Sends requests to the local Flask server (does NOT use mux.js). Its `content.js` posts to `http://localhost:5000/baixar`.

## Standalone Extension (sibling repo)

Located at `../loom-dl-extension/`. Manifest V3. Uses `lib/mux.min.js` (mux.js) for in-browser TS→MP4 transmuxing — no server needed. Load as unpacked in `chrome://extensions`.

## Language

Code comments and UI strings are in **Brazilian Portuguese**. Keep this consistent when modifying.
