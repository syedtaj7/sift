"""Sift local server. Serves the web UI and streams sorting events.

Run:  python server.py   then open http://127.0.0.1:8765
"""

from __future__ import annotations

import json
import mimetypes
import os
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import engine

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
WEB = ROOT / "web"
PORT = 8765
HOME = Path.home()

DEFAULT_OUTPUT = str(HOME / "Pictures" / "Sift Trips")
DATA_DIR = Path(os.environ.get("LOCALAPPDATA", HOME / "AppData" / "Local")) / "Sift"
SETTINGS_FILE = DATA_DIR / "settings.json"

# Only Sift's own window may use this server (see Handler.allowed).
ALLOWED_HOSTS = {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}
ALLOWED_ORIGINS = {f"http://{h}" for h in ALLOWED_HOSTS}
CSP = ("default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; script-src 'self'; "
       "font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")
DEMO_ZIP = HOME / "PhotoWork" / "sift-demo" / "takeout-demo-001.zip"

mimetypes.add_type("font/woff2", ".woff2")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("text/javascript", ".js")

state = {"job": None}
last_ping = 0.0  # when the window last talked to us; the desktop launcher quits after a long silence

MEDIA_EXT = engine.PHOTO_EXT | engine.VIDEO_EXT
HIDDEN_NAMES = {"AppData", "Application Data", "Local Settings", "$Recycle.Bin", "System Volume Information",
                "node_modules", "__pycache__", "Windows", "ProgramData", "Recovery", "PerfLogs"}


def quick_places():
    one = HOME / "OneDrive"
    places = [
        ("Home", HOME, "home"),
        ("Desktop", one / "Desktop" if (one / "Desktop").is_dir() else HOME / "Desktop", "monitor"),
        ("Downloads", HOME / "Downloads", "download"),
        ("Pictures", one / "Pictures" if (one / "Pictures").is_dir() else HOME / "Pictures", "image"),
        ("Documents", one / "Documents" if (one / "Documents").is_dir() else HOME / "Documents", "folder"),
        ("OneDrive", one, "cloud"),
        ("PhotoWork", HOME / "PhotoWork", "image-multiple"),
    ]
    out = [{"name": n, "path": str(p), "icon": i} for n, p, i in places if p.is_dir()]
    for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
        root = f"{letter}:\\"
        if os.path.exists(root):
            out.append({"name": f"Drive {letter}:", "path": root, "icon": "save"})
    return out


def media_count(path: Path, cap: int = 999) -> int:
    n = 0
    try:
        with os.scandir(path) as it:
            for e in it:
                if e.is_file(follow_symlinks=False) and os.path.splitext(e.name)[1].lower() in MEDIA_EXT:
                    n += 1
                    if n >= cap:
                        break
    except OSError:
        pass
    return n


def list_dir(path_str: str):
    if not path_str:
        return {"path": "", "parent": None, "crumbs": [], "dirs": [], "media_here": 0, "samples": [], "places": quick_places()}
    path = Path(path_str)
    if not path.is_dir():
        raise FileNotFoundError(path_str)
    dirs, samples, media_here, zips, files = [], [], 0, [], []
    try:
        entries = sorted(os.scandir(path), key=lambda e: e.name.lower())
    except PermissionError:
        entries = []
    for e in entries:
        name = e.name
        try:
            if e.is_dir(follow_symlinks=False):
                if name.startswith((".", "$")) or name in HIDDEN_NAMES:
                    continue
                if len(dirs) < 400:
                    dirs.append({"name": name, "path": e.path, "media": media_count(Path(e.path))})
            elif name.lower().endswith(".zip"):
                zips.append({"name": name, "path": e.path, "gb": round(e.stat().st_size / 1e9, 2)})
            elif (ext := os.path.splitext(name)[1].lower()) in MEDIA_EXT:
                media_here += 1
                if len(samples) < 8 and ext in engine.PHOTO_EXT - {".heic", ".heif"}:
                    samples.append(e.path)
                if len(files) < 300:
                    files.append({"name": name, "path": e.path, "video": ext in engine.VIDEO_EXT})
        except OSError:
            continue
    crumbs, p = [], path
    while True:
        crumbs.append({"name": p.name or str(p).rstrip("\\"), "path": str(p)})
        if p.parent == p:
            break
        p = p.parent
    crumbs.reverse()
    parent = str(path.parent) if path.parent != path else ""
    return {"path": str(path), "parent": parent, "crumbs": crumbs, "dirs": dirs, "zips": zips, "files": files,
            "media_here": media_here, "samples": samples, "places": quick_places()}


def load_settings() -> dict:
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_settings(data: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def clean_home(h) -> dict | None:
    try:
        home = {"name": str(h.get("name", ""))[:80], "lat": float(h["lat"]), "lon": float(h["lon"]),
                "radius": float(h.get("radius", 60))}
    except (AttributeError, KeyError, TypeError, ValueError):
        return None
    ok = -90 <= home["lat"] <= 90 and -180 <= home["lon"] <= 180 and 1 <= home["radius"] <= 500
    return home if ok else None


_cities: list[tuple] | None = None


def search_cities(q: str, limit: int = 8):
    """Home-city search over the same offline place list Sift uses to name trips."""
    global _cities
    if _cities is None:
        import csv
        import reverse_geocoder as rg
        rows = []
        for f in (Path(rg.__file__).parent / "rg_cities1000.csv", ROOT / "travel_places.csv"):
            with open(f, encoding="utf-8") as fh:
                for r in csv.DictReader(fh):
                    rows.append((r["name"].lower(), r["name"], r["admin1"], r["cc"], float(r["lat"]), float(r["lon"])))
        _cities = rows
    q = q.strip().lower()
    if len(q) < 2:
        return []
    hits = [c for c in _cities if c[0].startswith(q)]
    hits.sort(key=lambda c: (c[0] != q, len(c[0]), c[1]))
    out, seen = [], set()
    for low, name, admin1, cc, lat, lon in hits:
        key = (low, admin1, cc)
        if key in seen:
            continue
        seen.add(key)
        country = engine.COUNTRY_NAMES.get(cc, cc)
        out.append({"name": name, "where": ", ".join(x for x in (admin1, country) if x), "lat": lat, "lon": lon})
        if len(out) >= limit:
            break
    return out


_peek_cache: dict[str, bytes] = {}


def peek_thumb(file: str) -> bytes:
    if file in _peek_cache:
        return _peek_cache[file]
    from io import BytesIO
    from PIL import Image, ImageOps
    img = ImageOps.exif_transpose(Image.open(file)).convert("RGB")
    img.thumbnail((220, 220))
    buf = BytesIO()
    img.save(buf, "JPEG", quality=78)
    data = buf.getvalue()
    if len(_peek_cache) > 300:
        _peek_cache.clear()
    _peek_cache[file] = data
    return data


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # keep the console quiet
        pass

    # ------------------------------------------------------------ safety
    def allowed(self) -> bool:
        """Only Sift's own window may talk to this server. The Host check stops DNS-rebinding
        sites, and the Origin and Sec-Fetch-Site checks stop other pages open in the browser
        from sending commands or loading your file list and thumbnails."""
        if self.headers.get("Host", "") not in ALLOWED_HOSTS:
            return False
        origin = self.headers.get("Origin")
        if origin and origin not in ALLOWED_ORIGINS:
            return False
        site = self.headers.get("Sec-Fetch-Site")
        return not site or site in ("same-origin", "none")

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Content-Security-Policy", CSP)
        super().end_headers()

    # ------------------------------------------------------------ helpers
    def send_json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def send_file(self, path: Path, ctype: str | None = None):
        if not path.is_file():
            self.send_error(404)
            return
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype or mimetypes.guess_type(str(path))[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    # ------------------------------------------------------------ routes
    def do_GET(self):
        global last_ping
        if not self.allowed():
            return self.send_error(403)
        last_ping = time.time()
        url = urlparse(self.path)
        p = url.path
        if p == "/api/ping":
            return self.send_json({"ok": True})
        if p == "/licenses":
            text = "\n\n".join((ROOT / f).read_text(encoding="utf-8") for f in ("LICENSE", "THIRD_PARTY_NOTICES.md")
                               if (ROOT / f).is_file())
            body = text.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if p == "/api/cities":
            return self.send_json(search_cities(parse_qs(url.query).get("q", [""])[0]))
        if p in ("/", "/index.html"):
            return self.send_file(WEB / "index.html", "text/html; charset=utf-8")
        if p.startswith("/web/"):
            target = (WEB / p[5:]).resolve()
            if WEB.resolve() in target.parents:
                return self.send_file(target)
            return self.send_error(404)
        if p == "/api/defaults":
            out = Path(DEFAULT_OUTPUT)
            return self.send_json({
                "output": DEFAULT_OUTPUT,
                "browse_start": str(HOME / "Downloads"),
                "pictures": next((p["path"] for p in quick_places() if p["name"] == "Pictures"), ""),
                "demo": str(DEMO_ZIP) if DEMO_ZIP.is_file() else "",
                "existing": engine.existing_trips(out),
                "zips_done": len(engine.Catalog(out).zips),
                "home": clean_home(load_settings().get("home")),
            })
        if p == "/api/check":
            path = Path(parse_qs(url.query).get("path", [""])[0])
            is_zip = path.suffix.lower() == ".zip" and path.is_file()
            if not (is_zip or path.is_dir()):
                return self.send_json({"exists": False, "count": 0})
            try:
                count, partial = engine.count_media(str(path))
            except Exception:
                return self.send_json({"exists": True, "count": 0, "error": "That zip can't be read. Is it fully downloaded?"})
            gb = round(path.stat().st_size / 1e9, 2) if is_zip else None
            done = is_zip and str(path) in engine.Catalog(Path(DEFAULT_OUTPUT)).zips
            return self.send_json({"exists": True, "count": count, "partial": partial, "zip": is_zip, "gb": gb, "done_before": done})
        if p == "/api/ls":
            q = parse_qs(url.query)
            try:
                return self.send_json(list_dir(q.get("path", [""])[0]))
            except (FileNotFoundError, OSError):
                return self.send_json({"error": "That folder can't be opened."}, 404)
        if p == "/api/peek":
            f = parse_qs(url.query).get("file", [""])[0]
            if not f or os.path.splitext(f)[1].lower() not in MEDIA_EXT or not os.path.isfile(f):
                return self.send_error(404)
            try:
                data = peek_thumb(f)
            except Exception:
                return self.send_error(404)
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "max-age=3600")
            self.end_headers()
            self.wfile.write(data)
            return
        if p.startswith("/thumb/"):
            job = state["job"]
            if not job:
                return self.send_error(404)
            name = p.split("/")[-1]
            if not name.isdigit():
                return self.send_error(404)
            return self.send_file(Path(job.settings.output) / ".sift" / "thumbs" / f"{int(name)}.jpg", "image/jpeg")
        if p == "/api/events":
            return self.stream_events(int(parse_qs(url.query).get("since", ["0"])[0]))
        self.send_error(404)

    def do_POST(self):
        if not self.allowed():
            return self.send_error(403)
        p = urlparse(self.path).path
        job = state["job"]
        if p == "/api/settings":
            home = clean_home(self.read_json().get("home"))
            if not home:
                return self.send_json({"error": "That home location isn't valid."}, 400)
            save_settings({**load_settings(), "home": home})
            return self.send_json({"ok": True, "home": home})
        if p == "/api/start":
            if job and not job.finished:
                return self.send_json({"error": "A sort is already running."}, 409)
            body = self.read_json()
            src = Path(body.get("source", ""))
            if not (src.is_dir() or (src.is_file() and src.suffix.lower() == ".zip")):
                return self.send_json({"error": "Pick a Takeout zip or a photos folder."}, 400)
            home = clean_home(load_settings().get("home"))
            if not home:
                return self.send_json({"error": "Set your home city first."}, 400)
            out = Path(body.get("output") or DEFAULT_OUTPUT)
            settings = engine.Settings(
                source=str(src),
                output=str(out),
                home_lat=home["lat"],
                home_lon=home["lon"],
                home_radius_km=home["radius"],
            )
            job = engine.Job(settings)
            state["job"] = job
            threading.Thread(target=engine.run, args=(job,), daemon=True).start()
            return self.send_json({"ok": True})
        if p == "/api/pause" and job:
            job.paused.set()
            return self.send_json({"ok": True})
        if p == "/api/resume" and job:
            job.paused.clear()
            return self.send_json({"ok": True})
        if p == "/api/stop" and job:
            job.stopped = True
            job.paused.clear()
            return self.send_json({"ok": True})
        if p == "/api/delete-zip":
            # Only ever deletes the zip that was just sorted, and only when the user clicks the button.
            body = self.read_json()
            target = Path(body.get("path", ""))
            if (not job or not job.finished or job.stopped or str(target) != job.settings.source
                    or target.suffix.lower() != ".zip" or not target.is_file()):
                return self.send_json({"error": "Only the zip you just finished can be deleted."}, 400)
            gb = round(target.stat().st_size / 1e9, 2)
            target.unlink()
            return self.send_json({"ok": True, "freed_gb": gb})
        if p == "/api/open":
            # Shows a folder (or a file, selected) in Explorer, and only inside the trip collection.
            # Files are never launched, so this can't be used to run anything.
            body = self.read_json()
            root = Path(job.settings.output if job else DEFAULT_OUTPUT).resolve()
            target = Path(body.get("path", ""))
            if not target.is_absolute():
                target = root.joinpath(*[str(x) for x in body.get("folder", [])])
            target = target.resolve()
            if target != root and root not in target.parents:
                return self.send_json({"error": "Sift only opens your trip folders."}, 403)
            if target.exists():
                if target.is_file():
                    subprocess.Popen(["explorer", "/select,", str(target)])
                else:
                    os.startfile(str(target))
                return self.send_json({"ok": True})
            return self.send_json({"error": "Not found"}, 404)
        self.send_error(404)

    def stream_events(self, since: int):
        job = state["job"]
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        if not job:
            self.wfile.write(b"event: idle\ndata: {}\n\n")
            return
        i = since
        try:
            while True:
                with job.cond:
                    while i >= len(job.events):
                        if not job.cond.wait(timeout=15):
                            break
                    batch = job.events[i:]
                if not batch:
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
                    continue
                for ev in batch:
                    self.wfile.write(f"data: {json.dumps(ev)}\n\n".encode())
                self.wfile.flush()
                i += len(batch)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            return


def make_server():
    return ThreadingHTTPServer(("127.0.0.1", PORT), Handler)


def main():
    server = make_server()
    url = f"http://127.0.0.1:{PORT}"
    print(f"Sift is running at {url}  (close this window to stop)")
    if "--no-browser" not in sys.argv and os.environ.get("SIFT_NO_BROWSER") != "1":
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    server.serve_forever()


if __name__ == "__main__":
    main()
