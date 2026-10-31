"""Builds website/ (the download page for Vercel, Netlify or any static host) from site/index.html.

site/index.html is a page fragment (it is also published as a claude.ai artifact, which adds
its own <html>/<head>), so this wraps it in a full document and adds the favicon and share tags.
"""
import shutil
from pathlib import Path

ROOT = Path(__file__).parent
SRC = ROOT / "site" / "index.html"
OUT = ROOT / "website"
URL = "https://github.com/syedtaj7/sift"

page = SRC.read_text(encoding="utf-8")
split = page.index('<canvas id="sky"')
head, body = page[:split].strip(), page[split:].strip()
head = head.replace('<meta name="claude:viewport-fit-sides" content="cover">\n', "")

doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
{head}
<meta property="og:title" content="Sift: keep only your trip photos">
<meta property="og:description" content="A free Windows app that pulls just the travel photos and videos out of your Google Takeout zips, filed by place.">
<meta property="og:type" content="website">
<meta property="og:image" content="/og.png">
<meta name="theme-color" content="#1d1238">
<link rel="icon" type="image/png" href="/favicon.png">
<style>[hidden] {{ display: none !important; }} img {{ max-width: 100%; }}</style>
</head>
<body>
{body}
</body>
</html>
"""

OUT.mkdir(exist_ok=True)
(OUT / "index.html").write_text(doc, encoding="utf-8")
shutil.copy2(ROOT / "web" / "icon.png", OUT / "favicon.png")
shutil.copy2(ROOT / "icon-256.png", OUT / "og.png")
print("website/ written,", len(doc) // 1024, "KB")
