"""Sift sorting engine: trips only.

Feed it one Google Takeout zip (or a folder) at a time. It keeps ONLY travel photos and
videos and writes them to  <output>/Trips/<Region>/<City>/ . Everything else stays in
Google Photos and is just counted.

How a photo is judged
1. Metadata pass (cheap, no image decoding): read the time and GPS of every item from the
   Takeout JSON sidecars, falling back to EXIF. WhatsApp/received images, screenshots and
   duplicates (Takeout copies every album photo twice) are dropped here.
2. Location repair, using every GPS point Sift has ever seen (this zip plus earlier zips):
   - no GPS: borrow the location of a photo taken within 3 hours, or sitting between two
     photos up to 12 hours apart that agree on the place
   - suspicious GPS: if the photos just before and after agree with each other but this one
     is hundreds of km away, trust the neighbours
3. A photo is a trip candidate if its (repaired) location is outside the home radius.
4. Vision pass, only for candidates: drop selfies / people-heavy shots and blurry or dark ones.
5. Keepers are extracted straight from the zip into the Trips folders. Nothing is unzipped
   in bulk, nothing else is written, originals are never touched.
"""

from __future__ import annotations

import bisect
import io
import json
import math
import os
import posixpath
import re
import sys
import tempfile
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
from PIL import ExifTags, Image, ImageOps

# HEIC decoding. pi-heif is the decode-only build of pillow-heif: it leaves out the GPL
# x265 encoder, so the packaged app only carries LGPL libraries (libheif, libde265).
try:
    from pi_heif import register_heif_opener

    register_heif_opener()
except Exception:
    pass

import reverse_geocoder as rg

# Inside the packaged app the data files live in PyInstaller's unpack folder.
ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
PHOTO_EXT = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp", ".gif", ".bmp"}
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".3gp", ".avi", ".mkv"}
MEDIA_EXT = PHOTO_EXT | VIDEO_EXT
SKIP_DIRS = {"node_modules", ".git", "__pycache__", ".sift", ".sift_cache"}

HOUR = 3600
FILL_NEAR = 3 * HOUR       # borrow a neighbour's location if it is this close in time
FILL_BETWEEN = 12 * HOUR   # or if two agreeing neighbours sit within this window
AGREE_KM = 60
OUTLIER_KM = 300

COUNTRY_NAMES = {"IN": "India", "SA": "Saudi Arabia", "AE": "UAE", "US": "USA", "GB": "UK", "QA": "Qatar",
                 "OM": "Oman", "TH": "Thailand", "SG": "Singapore", "MY": "Malaysia", "NP": "Nepal",
                 "LK": "Sri Lanka", "TR": "Turkey", "EG": "Egypt", "PK": "Pakistan", "BD": "Bangladesh",
                 "BT": "Bhutan", "MV": "Maldives", "KW": "Kuwait", "BH": "Bahrain", "JO": "Jordan", "IR": "Iran",
                 "IQ": "Iraq", "AF": "Afghanistan", "CN": "China", "JP": "Japan", "KR": "South Korea",
                 "VN": "Vietnam", "ID": "Indonesia", "PH": "Philippines", "AU": "Australia", "NZ": "New Zealand",
                 "CA": "Canada", "MX": "Mexico", "BR": "Brazil", "DE": "Germany", "FR": "France", "IT": "Italy",
                 "ES": "Spain", "NL": "Netherlands", "CH": "Switzerland", "AT": "Austria", "RU": "Russia",
                 "ZA": "South Africa", "KE": "Kenya", "TZ": "Tanzania", "MA": "Morocco"}
REGION_ALIASES = {
    "Jammu and Kashmir": "Kashmir", "Ladakh": "Ladakh", "Himachal Pradesh": "Himachal & Spiti",
    "National Capital Territory of Delhi": "Delhi", "Delhi": "Delhi", "NCT": "Delhi",
    "Makkah Region": "Makkah", "Mecca Region": "Makkah",
    "Al Madinah al Munawwarah": "Madinah", "Al Madinah Region": "Madinah", "Medina Region": "Madinah",
}
SKIP_REASONS = ["people", "home", "received", "screens", "nolocation", "duplicate"]


# ------------------------------------------------------------------ geocoder

def _build_geocoder():
    base = (Path(rg.__file__).parent / "rg_cities1000.csv").read_text(encoding="utf-8")
    extra = (ROOT / "travel_places.csv").read_text(encoding="utf-8").split("\n", 1)[1]
    return rg.RGeocoder(mode=1, verbose=False, stream=io.StringIO(base.rstrip("\n") + "\n" + extra))


_geo = None
_geo_lock = threading.Lock()


def place_for(gps):
    global _geo
    with _geo_lock:
        if _geo is None:
            _geo = _build_geocoder()
        r = _geo.query([gps])[0]
    region = REGION_ALIASES.get(r.get("admin1", ""), r.get("admin1") or r.get("name"))
    country = COUNTRY_NAMES.get(r.get("cc", ""), r.get("cc", ""))
    if r.get("cc") not in ("IN", "") and region not in ("Makkah", "Madinah"):
        region = f"{region}, {country}"
    return {"city": r.get("name", ""), "region": region, "country": country}


def haversine_km(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


# ------------------------------------------------------------------ sources

@dataclass
class Item:
    key: int
    name: str            # file name
    ref: str             # zip member name or absolute file path
    size: int
    is_video: bool
    sidecar: str | None = None
    ts: int | None = None
    gps: tuple | None = None
    loc: tuple | None = None
    loc_how: str = ""     # "gps", "nearby", "fixed"
    skip: str = ""


class Source:
    """A Takeout zip or a plain folder, read without unzipping anything to disk."""

    def __init__(self, path: str):
        self.path = path
        self.is_zip = path.lower().endswith(".zip")
        self._local = threading.local()
        self.items: list[Item] = []
        self._index()

    def zf(self) -> zipfile.ZipFile:
        # ZipFile objects aren't safe to share between threads, so each thread opens its own.
        if not hasattr(self._local, "zf"):
            self._local.zf = zipfile.ZipFile(self.path)
        return self._local.zf

    def _index(self):
        names: list[tuple[str, int]] = []
        if self.is_zip:
            for info in self.zf().infolist():
                if not info.is_dir():
                    names.append((info.filename, info.file_size))
        else:
            for root, dirs, files in os.walk(self.path):
                dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
                for f in files:
                    p = os.path.join(root, f)
                    try:
                        names.append((p, os.path.getsize(p)))
                    except OSError:
                        pass
        # zip members always use "/" while disk paths use "\"
        pathmod = posixpath if self.is_zip else os.path
        jsons_by_dir: dict[str, list[str]] = {}
        for n, _ in names:
            if n.lower().endswith(".json"):
                d, b = pathmod.split(n)
                jsons_by_dir.setdefault(d, []).append(b)
        k = 0
        for n, size in names:
            ext = os.path.splitext(n)[1].lower()
            if ext not in MEDIA_EXT:
                continue
            d, b = pathmod.split(n)
            side = find_sidecar(b, jsons_by_dir.get(d, []))
            self.items.append(Item(k, b, n, size, ext in VIDEO_EXT, pathmod.join(d, side) if side else None))
            k += 1

    def copy_to(self, ref: str, dest: Path):
        """Stream a member straight to disk (videos can be hundreds of MB)."""
        import shutil
        if self.is_zip:
            with self.zf().open(ref) as f, open(dest, "wb") as o:
                shutil.copyfileobj(f, o, 1024 * 1024)
        else:
            shutil.copyfile(ref, dest)

    def read(self, ref: str, limit: int | None = None) -> bytes:
        if self.is_zip:
            with self.zf().open(ref) as f:
                return f.read(limit) if limit else f.read()
        with open(ref, "rb") as f:
            return f.read(limit) if limit else f.read()


def find_sidecar(b: str, jsons: list[str]) -> str | None:
    """Return the JSON file name (in the same folder) for media file b.
    Takeout's naming varies: photo.jpg.json, photo.jpg.supplemental-metadata.json,
    truncated versions of those, photo.jpg(1).json for duplicates, and edited copies share
    the original's JSON."""
    if not jsons:
        return None
    js = set(jsons)
    join = lambda x: x
    m = re.match(r"^(.*)\((\d+)\)(\.[^.]+)$", b)
    candidates = [b, re.sub(r"-edited(\.[^.]+)$", r"\1", b, flags=re.I)]
    if m:
        candidates.insert(0, f"{m.group(1)}{m.group(3)}({m.group(2)})")
    for c in candidates:
        for suffix in (".json", ".supplemental-metadata.json"):
            if c + suffix in js:
                return join(c + suffix)
        for j in jsons:  # truncated names, e.g. photo.jpg.supplemental-metad.json
            if j.startswith(c[:46]) and j.lower().endswith(".json") and (len(c) > 46 or j.startswith(c + ".")):
                return join(j)
    return None


GPS_TAG = next(k for k, v in ExifTags.TAGS.items() if v == "GPSInfo")


def exif_gps_time(data: bytes):
    try:
        img = Image.open(io.BytesIO(data))
        exif = img.getexif()
    except Exception:
        return None, None
    gps = None
    try:
        g = exif.get_ifd(GPS_TAG)
        if g and 2 in g and 4 in g:
            dms = lambda v: float(v[0]) + float(v[1]) / 60 + float(v[2]) / 3600
            lat, lon = dms(g[2]), dms(g[4])
            if g.get(1) == "S":
                lat = -lat
            if g.get(3) == "W":
                lon = -lon
            if lat or lon:
                gps = (lat, lon)
    except Exception:
        pass
    ts = None
    raw = exif.get_ifd(0x8769).get(36867) or exif.get(306)
    if raw:
        try:
            ts = int(time.mktime(time.strptime(str(raw)[:19], "%Y:%m:%d %H:%M:%S"))) - 19800  # IST to UTC
        except Exception:
            pass
    return gps, ts


# ------------------------------------------------------------------ catalog (memory across zips)

class Catalog:
    """Remembers every GPS point and every kept file across runs, so later zips can borrow
    locations from earlier ones and duplicates are never kept twice."""

    def __init__(self, out: Path):
        self.file = out / ".sift" / "catalog.json"
        data = {}
        if self.file.exists():
            try:
                data = json.loads(self.file.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        self.points: list[list] = data.get("points", [])  # [ts, lat, lon]
        self.seen: set[str] = set(data.get("seen", []))
        self.zips: list[str] = data.get("zips", [])

    def save(self):
        self.file.parent.mkdir(parents=True, exist_ok=True)
        pts = sorted({(int(t), round(a, 5), round(b, 5)) for t, a, b in self.points})
        self.file.write_text(json.dumps({"points": pts, "seen": sorted(self.seen), "zips": self.zips}), encoding="utf-8")


# ------------------------------------------------------------------ job

@dataclass
class Settings:
    source: str
    output: str
    home_lat: float  # set by the user on first run (server.py keeps it in settings.json)
    home_lon: float
    home_radius_km: float = 60.0


@dataclass
class Job:
    settings: Settings
    events: list = field(default_factory=list)
    cond: threading.Condition = field(default_factory=threading.Condition)
    total: int = 0
    done: int = 0
    kept: int = 0
    skipped: dict = field(default_factory=lambda: {r: 0 for r in SKIP_REASONS})
    paused: threading.Event = field(default_factory=threading.Event)
    stopped: bool = False
    finished: bool = False

    def emit(self, event: dict):
        with self.cond:
            event["seq"] = len(self.events)
            self.events.append(event)
            self.cond.notify_all()

    def tally(self):
        self.emit({"type": "tally", "done": self.done, "total": self.total, "kept": self.kept, "skipped": dict(self.skipped)})


def existing_trips(out: Path):
    """Trips already collected from earlier zips, so the UI can show them from the start."""
    trips = []
    root = out / "Trips"
    if not root.is_dir():
        return trips
    for region in sorted(p for p in root.iterdir() if p.is_dir()):
        cities, count, cover = {}, 0, None
        for city in region.iterdir():
            if not city.is_dir():
                continue
            files = [f for f in city.iterdir() if f.suffix.lower() in MEDIA_EXT]
            if files:
                cities[city.name] = len(files)
                count += len(files)
                cover = cover or next((str(f) for f in files if f.suffix.lower() in PHOTO_EXT - {".heic", ".heif"}), None)
        if count:
            trips.append({"region": region.name, "cities": cities, "count": count, "cover": cover})
    return trips


def count_media(path: str, time_cap: float = 3.0):
    """Quick count for the setup screen. Returns (count, partial)."""
    t0 = time.time()
    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            n = sum(1 for i in z.infolist() if os.path.splitext(i.filename)[1].lower() in MEDIA_EXT)
        return n, False
    n = 0
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        n += sum(1 for f in files if os.path.splitext(f)[1].lower() in MEDIA_EXT)
        if time.time() - t0 > time_cap:
            return n, True
    return n, False


def is_received(name: str) -> bool:
    n = name.lower()
    return bool(re.search(r"-wa\d{3,}", n)) or n.startswith(("whatsapp image", "whatsapp video", "received_", "fb_img", "download"))


def is_screen(name: str) -> bool:
    n = name.lower()
    return "screenshot" in n or "screen_recording" in n or "screenrecord" in n or n.startswith("scr_")


CASCADE_PATH = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
_local = threading.local()


def face_detector():
    # OpenCV detectors are not thread-safe, so each worker thread gets its own.
    if not hasattr(_local, "cascade"):
        _local.cascade = cv2.CascadeClassifier(CASCADE_PATH)
    return _local.cascade


YUNET_PATH = ROOT / "models" / "face_detection_yunet_2023mar.onnx"


def yunet(w: int, h: int):
    """OpenCV's YuNet face detector, used when its small model file is present.
    It finds smaller and angled faces far better than the classic detector."""
    if not YUNET_PATH.exists():
        return None
    if not hasattr(_local, "yunet"):
        _local.yunet = cv2.FaceDetectorYN.create(str(YUNET_PATH), "", (w, h), 0.75, 0.3, 50)
    _local.yunet.setInputSize((w, h))
    return _local.yunet


def yunet_boxes(rgb: np.ndarray):
    h, w = rgb.shape[:2]
    _, found = yunet(w, h).detect(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
    return [] if found is None else [f[:4] for f in found if f[-1] >= 0.75]


def find_faces(rgb: np.ndarray):
    """Faces as [x, y, w, h] in the coordinates of rgb. Looks at up to 1024px so the small
    faces of people posing in full-body shots are still found."""
    h, w = rgb.shape[:2]
    scale = min(1.0, 1024 / max(w, h)) if max(w, h) > 1024 else 1024 / max(w, h)
    big = cv2.resize(rgb, (int(w * scale), int(h * scale)))
    H, W = big.shape[:2]
    if YUNET_PATH.exists():
        boxes = yunet_boxes(big)
        if not boxes:
            # A face filling the whole frame is too big for YuNet at 1024px; look again small.
            small_scale = 320 / max(W, H)
            small = cv2.resize(big, (int(W * small_scale), int(H * small_scale)))
            boxes = [[v / small_scale for v in b] for b in yunet_boxes(small)]
    else:
        gray = cv2.cvtColor(big, cv2.COLOR_RGB2GRAY)
        boxes = face_detector().detectMultiScale(gray, scaleFactor=1.08, minNeighbors=6, minSize=(max(18, int(H * 0.025)),) * 2)
    return [[int(x / scale), int(y / scale), int(bw / scale), int(bh / scale)] for (x, y, bw, bh) in boxes]


def analyse(rgb: np.ndarray):
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    h, w = gray.shape
    faces = find_faces(rgb)
    # How big is the biggest face relative to the photo's height? A person posing for the
    # camera has a face of 4%+ of the frame; strangers in the background are far smaller.
    face_height = max((fh for (_, _, _, fh) in faces), default=0) / float(h)
    return {"w": w, "h": h, "sharp": float(cv2.Laplacian(gray, cv2.CV_64F).var()), "bright": float(gray.mean()),
            "faces": faces, "face_height": face_height, "n_faces": len(faces)}


def safe(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "", name or "").strip(" .") or "Unknown"


def unique_dest(d: Path, name: str) -> Path:
    dest, n = d / name, 1
    while dest.exists():
        dest = d / f"{Path(name).stem} ({n}){Path(name).suffix}"
        n += 1
    return dest


def run(job: Job):
    s = job.settings
    out = Path(s.output)
    thumbs = out / ".sift" / "thumbs"
    thumbs.mkdir(parents=True, exist_ok=True)
    home = (s.home_lat, s.home_lon)
    catalog = Catalog(out)

    job.emit({"type": "existing", "trips": existing_trips(out), "zips": len(catalog.zips)})
    job.emit({"type": "phase", "text": "Opening"})
    src = Source(s.source)
    items = src.items
    job.total = len(items)
    job.emit({"type": "start", "total": job.total, "zip": src.is_zip})

    # ---- 1. metadata pass
    job.emit({"type": "phase", "text": "Reading dates and places"})
    seen_now = set()
    for it in items:
        dkey = f"{it.name.lower()}|{it.size}"
        if dkey in seen_now or dkey in catalog.seen:
            it.skip = "duplicate"
        seen_now.add(dkey)
        if it.sidecar:
            try:
                meta = json.loads(src.read(it.sidecar))
                for k in ("geoData", "geoDataExif"):
                    g = meta.get(k) or {}
                    if g.get("latitude") or g.get("longitude"):
                        it.gps = (float(g["latitude"]), float(g["longitude"]))
                        break
                t = (meta.get("photoTakenTime") or {}).get("timestamp")
                it.ts = int(t) if t else None
            except Exception:
                pass
        if (it.gps is None or it.ts is None) and not it.is_video and not it.skip:
            gps, ts = exif_gps_time(src.read(it.ref, 256 * 1024))
            it.gps = it.gps or gps
            it.ts = it.ts or ts
        if not it.skip and is_received(it.name):
            it.skip = "received"
        elif not it.skip and is_screen(it.name):
            it.skip = "screens"

    # ---- 2. location repair using this zip's and earlier zips' GPS points
    job.emit({"type": "phase", "text": "Fixing locations"})
    for it in items:
        if it.gps and it.ts:
            catalog.points.append([it.ts, it.gps[0], it.gps[1]])
    catalog.points.sort(key=lambda p: p[0])
    times = [p[0] for p in catalog.points]

    def neighbours(ts, own=None):
        i = bisect.bisect_left(times, ts)
        prev = nxt = None
        j = i - 1
        while j >= 0:
            p = catalog.points[j]
            if own is None or (p[1], p[2]) != own or p[0] != ts:
                prev = p
                break
            j -= 1
        j = i
        while j < len(times):
            p = catalog.points[j]
            if own is None or (p[1], p[2]) != own or p[0] != ts:
                nxt = p
                break
            j += 1
        return prev, nxt

    # 2a. correct bad GPS first, so it can't spread to photos that borrow a location
    bad = set()
    for it in items:
        if it.skip or not it.gps:
            continue
        it.loc, it.loc_how = it.gps, "gps"
        if it.ts:
            prev, nxt = neighbours(it.ts, it.gps)
            if (prev and nxt and it.ts - prev[0] < 6 * HOUR and nxt[0] - it.ts < 6 * HOUR
                    and haversine_km(prev[1:], nxt[1:]) < AGREE_KM * 2
                    and haversine_km(it.gps, prev[1:]) > OUTLIER_KM and haversine_km(it.gps, nxt[1:]) > OUTLIER_KM):
                it.loc, it.loc_how = (prev[1], prev[2]), "fixed"
                bad.add((it.ts, it.gps[0], it.gps[1]))
    if bad:
        catalog.points = [p for p in catalog.points if (p[0], p[1], p[2]) not in bad]
        times[:] = [p[0] for p in catalog.points]

    # 2b. fill missing locations from the cleaned timeline, then decide trip or not
    for it in items:
        if it.skip:
            continue
        if it.gps:
            pass
        elif it.ts:
            prev, nxt = neighbours(it.ts)
            near = [p for p in (prev, nxt) if p and abs(p[0] - it.ts) <= FILL_NEAR]
            if near:
                p = min(near, key=lambda p: abs(p[0] - it.ts))
                it.loc, it.loc_how = (p[1], p[2]), "nearby"
            elif (prev and nxt and nxt[0] - prev[0] <= FILL_BETWEEN
                  and haversine_km(prev[1:], nxt[1:]) < AGREE_KM):
                it.loc, it.loc_how = (prev[1], prev[2]), "nearby"
        if not it.loc:
            it.skip = "nolocation"
        elif haversine_km(it.loc, home) <= s.home_radius_km:
            it.skip = "home"

    # count everything skipped so far
    for it in items:
        if it.skip:
            job.skipped[it.skip] += 1
            job.done += 1
    job.tally()

    # ---- 3. vision pass + extraction, only for trip candidates
    job.emit({"type": "phase", "text": "Collecting trip photos"})
    candidates = [it for it in items if not it.skip]
    lock = threading.Lock()

    def work(it: Item):
        while job.paused.is_set() and not job.stopped:
            time.sleep(0.2)
        if job.stopped:
            return
        try:
            keep(it)
        except Exception as exc:
            job.emit({"type": "error", "name": it.name, "message": str(exc)[:160]})
            with lock:
                job.done += 1
        if job.done % 25 == 0:
            job.tally()

    def keep(it: Item):
        place = place_for(it.loc)
        folder = ["Trips", safe(place["region"]), safe(place["city"])]
        dest_dir = out.joinpath(*folder)
        data = None
        if it.is_video:
            # Videos: stream to disk first, then look at one frame.
            dest_dir.mkdir(parents=True, exist_ok=True)
            with lock:
                dest = unique_dest(dest_dir, it.name)
                dest.touch()
            src.copy_to(it.ref, dest)
            cap = cv2.VideoCapture(str(dest))
            n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            if n > 2:
                cap.set(cv2.CAP_PROP_POS_FRAMES, min(n // 3, 90))
            ok, frame = cap.read()
            cap.release()
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB) if ok else None
        else:
            data = src.read(it.ref)
            img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
            img.thumbnail((640, 640))
            rgb = np.asarray(img)
            dest = None

        px = analyse(rgb) if rgb is not None else {"w": 4, "h": 3, "faces": [], "face_height": 0,
                                                   "n_faces": 0, "sharp": 999, "bright": 99}
        reason = None
        # Anyone posing for the camera (selfie, portrait, group shot) makes it a people photo.
        if px["face_height"] >= 0.04 or px["n_faces"] >= 3:
            reason = "people"
        elif not it.is_video and (px["sharp"] < 35 or px["bright"] < 28):
            reason = "screens"
        if reason:
            if dest is not None:
                dest.unlink(missing_ok=True)
            with lock:
                job.skipped[reason] += 1
                job.done += 1
            return

        if dest is None:
            dest_dir.mkdir(parents=True, exist_ok=True)
            with lock:
                dest = unique_dest(dest_dir, it.name)
                dest.write_bytes(data)
        if it.ts:
            os.utime(dest, (it.ts, it.ts))  # keep the real date on the file
        if rgb is not None:
            th = Image.fromarray(rgb)
            th.thumbnail((420, 420))
            th.save(thumbs / f"{it.key}.jpg", quality=82)
        with lock:
            catalog.seen.add(f"{it.name.lower()}|{it.size}")
            job.kept += 1
            job.done += 1
        how = {"gps": "GPS", "nearby": "Location from photos taken nearby", "fixed": "GPS corrected using nearby photos"}[it.loc_how]
        job.emit({
            "type": "item", "id": it.key, "name": it.name, "video": it.is_video,
            "folder": folder, "place": place, "loc_how": it.loc_how, "reason": how,
            "faces": px["faces"], "fw": px["w"], "fh": px["h"], "ts": it.ts,
            "dest": str(dest), "done": job.done, "total": job.total, "kept": job.kept,
        })

    with ThreadPoolExecutor(max_workers=max(2, (os.cpu_count() or 4) - 1)) as pool:
        list(pool.map(work, candidates))

    if src.is_zip and s.source not in catalog.zips:
        catalog.zips.append(s.source)
    catalog.save()
    job.finished = True
    job.tally()
    job.emit({"type": "finished", "done": job.done, "total": job.total, "kept": job.kept,
              "skipped": dict(job.skipped), "zip": src.is_zip, "zips": len(catalog.zips)})
