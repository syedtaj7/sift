"""Sift desktop launcher: the entry point of the packaged Sift.exe.

- First run from anywhere else (e.g. Downloads): offers to install itself to
  %LOCALAPPDATA%\\Programs\\Sift with Desktop and Start menu shortcuts.
- Starts the local server and opens Sift in its own app window (Edge app mode,
  no tabs or address bar). Falls back to the default browser.
- Quits when the window is closed, unless a sort is still running.
- A second launch just brings up a window on the running copy.
"""

from __future__ import annotations

import ctypes
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

APP_NAME = "Sift"
LOCAL = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
INSTALL_DIR = LOCAL / "Programs" / APP_NAME
DATA_DIR = LOCAL / APP_NAME
FROZEN = getattr(sys, "frozen", False)

# A windowed exe has no console: send output to a log file so errors aren't lost.
if sys.stdout is None or sys.stderr is None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    sys.stdout = sys.stderr = open(DATA_DIR / "sift.log", "a", encoding="utf-8", buffering=1)

import server  # noqa: E402  (after the log redirect so import errors are logged too)

URL = f"http://127.0.0.1:{server.PORT}"
IDLE_QUIT = 150  # seconds without a ping from the window before Sift closes itself


def message_box(text: str, title: str = APP_NAME, yes_no: bool = False) -> bool:
    MB_YESNO, MB_ICONQUESTION, MB_ICONINFO, IDYES = 0x04, 0x20, 0x40, 6
    flags = (MB_YESNO | MB_ICONQUESTION) if yes_no else MB_ICONINFO
    return ctypes.windll.user32.MessageBoxW(None, text, title, flags) == IDYES


def shortcut(link: Path, target: Path):
    """Create a .lnk with Windows' own scripting host (no extra packages needed)."""
    link.parent.mkdir(parents=True, exist_ok=True)
    ps = (
        "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:SIFT_LNK);"
        "$s.TargetPath=$env:SIFT_EXE;$s.WorkingDirectory=$env:SIFT_DIR;"
        "$s.IconLocation=$env:SIFT_EXE+',0';$s.Description='Sift: keep only your trip photos';$s.Save()"
    )
    env = dict(os.environ, SIFT_LNK=str(link), SIFT_EXE=str(target), SIFT_DIR=str(target.parent))
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], env=env,
                   creationflags=subprocess.CREATE_NO_WINDOW, check=False)


def desktop_dir() -> Path:
    buf = ctypes.create_unicode_buffer(260)
    ctypes.windll.shell32.SHGetFolderPathW(None, 0x0010, None, 0, buf)  # CSIDL_DESKTOPDIRECTORY
    return Path(buf.value) if buf.value else Path.home() / "Desktop"


def maybe_install() -> bool:
    """Returns True if this process should exit because the installed copy was started."""
    exe = Path(sys.executable)
    if not FROZEN or exe.parent.resolve() == INSTALL_DIR.resolve():
        return False
    installed = INSTALL_DIR / f"{APP_NAME}.exe"
    verb = "Update" if installed.exists() else "Install"
    if "--install" not in sys.argv and not message_box(f"{verb} Sift on this PC?\n\nIt adds Sift to your Desktop and Start menu so you can open "
                       "it like any app. Choose No to just run it this once.", yes_no=True):
        return False
    try:
        INSTALL_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(exe, installed)
        start_menu = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
        shortcut(start_menu / f"{APP_NAME}.lnk", installed)
        shortcut(desktop_dir() / f"{APP_NAME}.lnk", installed)
    except OSError as e:
        message_box(f"Couldn't install Sift ({e}). It will just run this once.")
        return False
    subprocess.Popen([str(installed)], cwd=str(INSTALL_DIR))
    return True


def already_running() -> bool:
    try:
        with urllib.request.urlopen(f"{URL}/api/defaults", timeout=2) as r:
            return r.status == 200
    except OSError:
        return False


def port_free() -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", server.PORT)) != 0


def find_edge() -> str | None:
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"), str(LOCAL)):
        if base:
            p = Path(base) / "Microsoft" / "Edge" / "Application" / "msedge.exe"
            if p.exists():
                return str(p)
    return None


def open_window() -> subprocess.Popen | None:
    edge = find_edge()
    if edge:
        profile = DATA_DIR / "window"
        return subprocess.Popen([edge, f"--app={URL}", f"--user-data-dir={profile}", "--no-first-run",
                                 "--window-size=1280,860", "--disable-features=Translate"])
    webbrowser.open(URL)
    return None


def watch(window: subprocess.Popen | None, httpd):
    """Close Sift once its window is gone and nothing is sorting."""
    opened = time.time()
    while True:
        time.sleep(3)
        job = server.state["job"]
        busy = job is not None and not job.finished
        if busy:
            continue
        # Edge's own process ends when the app window closes (if it stayed attached to it).
        if window is not None and window.poll() is not None and time.time() - opened > 8:
            break
        if time.time() - server.last_ping > IDLE_QUIT:
            break
    httpd.shutdown()


def main():
    if maybe_install():
        return
    if not port_free():
        if already_running():
            open_window()
        else:
            message_box(f"Port {server.PORT} is used by another program, so Sift can't start.")
        return
    httpd = server.make_server()
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    server.last_ping = time.time()
    window = open_window()
    watch(window, httpd)


if __name__ == "__main__":
    main()
