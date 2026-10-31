"""Draws Sift's 16x16 pixel-art icon (a framed trip photo: night sky, sun, mountains)
and writes sift.ico plus web/icon.png. Run once after changing the art."""
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).parent
ART = [
    "................",
    ".KKKKKKKKKKKKKK.",
    ".KWWWWWWWWWWWWK.",
    ".KWNNNNNNNNNNWK.",
    ".KWNNsNNNNYYNWK.",
    ".KWNNNNNNYYYYWK.",
    ".KWNNNsNNYYYYWK.",
    ".KWNNNNNNNYYNWK.",
    ".KWNNNPNNNNNNWK.",
    ".KWNNPPPNNNGNWK.",
    ".KWNPPPPPNGGGWK.",
    ".KWPPPPPPGGGGWK.",
    ".KWCCCCCCCCCCWK.",
    ".KWWWWWWWWWWWWK.",
    ".KKKKKKKKKKKKKK.",
    "................",
]
COLORS = {
    ".": (0, 0, 0, 0), "K": (26, 28, 44, 255), "W": (255, 241, 232, 255), "N": (41, 24, 84, 255),
    "s": (255, 241, 232, 255), "Y": (255, 205, 60, 255), "P": (255, 119, 168, 255),
    "G": (0, 228, 54, 255), "C": (41, 173, 255, 255),
}

img = Image.new("RGBA", (16, 16))
img.putdata([COLORS[c] for row in ART for c in row])
big = img.resize((256, 256), Image.NEAREST)
big.save(ROOT / "sift.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
img.resize((64, 64), Image.NEAREST).save(ROOT / "web" / "icon.png")
big.save(ROOT / "icon-256.png")
print("icon written")
