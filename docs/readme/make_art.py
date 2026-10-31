"""Draws the README's animated pixel art as plain SVG files (no dependencies).

GitHub shows SVGs in a README as images, and CSS animations inside them still play, so
the banner, section headers and badges can move without any GIFs. All lettering is drawn
from a 5x7 bitmap font so it looks the same everywhere. Run:  python docs/readme/make_art.py
"""
import math
import random
from pathlib import Path

OUT = Path(__file__).parent
INK, NIGHT, SKY, PANEL, PANEL2, LINE = "#0f0920", "#1d1238", "#160d2e", "#271a4d", "#33245f", "#4a3a85"
TEXT, MUTED = "#fff1e8", "#bfb2e3"
YELLOW, PINK, CYAN, GREEN, ORANGE, PURPLE, RED, BLUE = ("#ffcd3c", "#ff77a8", "#29adff", "#00e436", "#ffa300",
                                                         "#b28cff", "#ff004d", "#5f7bff")

FONT = {
    "A": "01110 10001 10001 11111 10001 10001 10001", "B": "11110 10001 10001 11110 10001 10001 11110",
    "C": "01110 10001 10000 10000 10000 10001 01110", "D": "11110 10001 10001 10001 10001 10001 11110",
    "E": "11111 10000 10000 11110 10000 10000 11111", "F": "11111 10000 10000 11110 10000 10000 10000",
    "G": "01110 10001 10000 10111 10001 10001 01111", "H": "10001 10001 10001 11111 10001 10001 10001",
    "I": "01110 00100 00100 00100 00100 00100 01110", "J": "00111 00010 00010 00010 00010 10010 01100",
    "K": "10001 10010 10100 11000 10100 10010 10001", "L": "10000 10000 10000 10000 10000 10000 11111",
    "M": "10001 11011 10101 10101 10001 10001 10001", "N": "10001 10001 11001 10101 10011 10001 10001",
    "O": "01110 10001 10001 10001 10001 10001 01110", "P": "11110 10001 10001 11110 10000 10000 10000",
    "Q": "01110 10001 10001 10001 10101 10010 01101", "R": "11110 10001 10001 11110 10100 10010 10001",
    "S": "01111 10000 10000 01110 00001 00001 11110", "T": "11111 00100 00100 00100 00100 00100 00100",
    "U": "10001 10001 10001 10001 10001 10001 01110", "V": "10001 10001 10001 10001 10001 01010 00100",
    "W": "10001 10001 10001 10101 10101 10101 01010", "X": "10001 10001 01010 00100 01010 10001 10001",
    "Y": "10001 10001 01010 00100 00100 00100 00100", "Z": "11111 00001 00010 00100 01000 10000 11111",
    "0": "01110 10001 10011 10101 11001 10001 01110", "1": "00100 01100 00100 00100 00100 00100 01110",
    "2": "01110 10001 00001 00010 00100 01000 11111", "3": "11111 00010 00100 00010 00001 10001 01110",
    "4": "00010 00110 01010 10010 11111 00010 00010", "5": "11111 10000 11110 00001 00001 10001 01110",
    "6": "00110 01000 10000 11110 10001 10001 01110", "7": "11111 00001 00010 00100 01000 01000 01000",
    "8": "01110 10001 10001 01110 10001 10001 01110", "9": "01110 10001 10001 01111 00001 00010 01100",
    " ": "00000 00000 00000 00000 00000 00000 00000", ",": "00000 00000 00000 00000 01100 00100 01000",
    ".": "00000 00000 00000 00000 00000 01100 01100", "!": "00100 00100 00100 00100 00100 00000 00100",
    "-": "00000 00000 00000 11111 00000 00000 00000", ":": "00000 01100 01100 00000 01100 01100 00000",
    "&": "01100 10010 10100 01000 10101 10010 01101", "/": "00001 00010 00010 00100 01000 01000 10000",
    "+": "00000 00100 00100 11111 00100 00100 00000", ">": "01000 00100 00010 00001 00010 00100 01000",
    "'": "00100 00100 01000 00000 00000 00000 00000",
}

SPRITES = {  # 8x8; "." is transparent
    "face": ("..pppp.. .pppppp. ppkppkpp pppppppp pkppppkp ppkkkkpp .pppppp. ..pppp..", {"p": "#f5b88a", "k": INK}),
    "home": ("...rr... ..rrrr.. .rrrrrr. rrrrrrrr .oooooo. .ookkoo. .ookkoo. .ookkoo.", {"r": RED, "o": ORANGE, "k": INK}),
    "chat": (".gggggg. gggggggg ggwgwgwg gggggggg .gggggg. ..gg.... .gg..... ........", {"g": GREEN, "w": TEXT}),
    "phone": (".kkkkkk. .kppppk. .kpwwpk. .kppppk. .kpwwpk. .kppppk. .kkwwkk. .kkkkkk.", {"k": INK, "p": PURPLE, "w": TEXT}),
    "pin": ("..oooo.. .oooooo. .ookkoo. .ookkoo. .oooooo. ..oooo.. ...oo... ...oo...", {"o": ORANGE, "k": INK}),
    "dupe": ("bbbbb... b...b... b.yyyyy. b.y...y. bby...y. ..y...y. ..yyyyy. ........", {"b": CYAN, "y": YELLOW}),
    "folder": ("yyy..... yyyyyyyy yddddddy yddddddy yddddddy yddddddy yyyyyyyy ........", {"y": YELLOW, "d": "#e09a00"}),
    "star": ("...y.... ...y.... ..yyy... yyyyyyy. .yyyyy.. .yy.yy.. .y...y.. ........", {"y": YELLOW}),
    "arrow": ("..kkkk.. ..kkkk.. ..kkkk.. kkkkkkkk .kkkkkk. ..kkkk.. ...kk... ........", {"k": INK}),
    "lock": ("..kkkk.. .k....k. .k....k. gggggggg ggggkggg ggggkggg gggggggg gggggggg", {"k": TEXT, "g": GREEN}),
    "wrench": (".....cc. ....c..c ....c.cc ...ccc.. ..ccc... .ccc.... ccc..... .c......", {"c": CYAN}),
    "map": ("yyy.ccc. yyycccgg yyycccgg ykyccckg yyyckcgg yyycccgg yyy.ccc. ........", {"y": YELLOW, "c": CYAN, "g": GREEN, "k": INK}),
    "moon": ("..wwww.. .wwwwww. wwwwwwww wwwwwwww wwwwwwww wwwwwwww .wwwwww. ..wwww..", {"w": "#fff1d0"}),
    "cloud": ("........ ...ww... .wwwww.. wwwwwwww wwwwwwww .wwwwww. ........ ........", {"w": "#3a2a6e"}),
}


def runs(row: str):
    """Yield (start, length, char) for runs of the same non-transparent character."""
    i = 0
    while i < len(row):
        c = row[i]
        j = i
        while j < len(row) and row[j] == c:
            j += 1
        if c not in ".0":
            yield i, j - i, c
        i = j


def sprite(name, x, y, b, cls=""):
    rows, pal = SPRITES[name]
    rects = [f'<rect x="{x + s * b}" y="{y + r * b}" width="{n * b}" height="{b}" fill="{pal[c]}"/>'
             for r, row in enumerate(rows.split()) for s, n, c in runs(row)]
    return f'<g class="{cls}">{"".join(rects)}</g>'


def text(s, x, y, b, color, cls="", shadow=None):
    """Pixel text from the 5x7 font; one rect per horizontal run."""
    out = []
    for dx, dy, col in ([(b, b, shadow)] if shadow else []) + [(0, 0, color)]:
        rects = []
        for i, ch in enumerate(s.upper()):
            glyph = FONT.get(ch, FONT[" "]).split()
            for r, row in enumerate(glyph):
                for st, n, _ in runs(row):
                    rects.append(f'<rect x="{x + dx + (i * 6 + st) * b}" y="{y + dy + r * b}" width="{n * b}" height="{b}"/>')
        out.append(f'<g fill="{col}">{"".join(rects)}</g>')
    return f'<g class="{cls}">{"".join(out)}</g>'


def text_width(s, b):
    return (len(s) * 6 - 1) * b


def landscape(x, y, b, seed, w=12, h=9):
    r = random.Random(seed)
    rects = [f'<rect x="{x}" y="{y}" width="{w * b}" height="{h * b}" fill="#2a1854"/>',
             f'<rect x="{x}" y="{y + 4 * b}" width="{w * b}" height="{(h - 4) * b}" fill="#4b2a7a"/>']
    sx = r.randint(6, 9)
    rects.append(f'<rect x="{x + sx * b}" y="{y + b}" width="{2 * b}" height="{2 * b}" fill="{YELLOW}"/>')
    for k, col in enumerate((PINK, GREEN)):
        peak = r.randint(1, w - 2)
        for c in range(w):
            top = max(2, round(5 + k * 1.5 - max(0, 4 - abs(c - peak)) * 0.9))
            rects.append(f'<rect x="{x + c * b}" y="{y + top * b}" width="{b}" height="{(h - top) * b}" fill="{col}"/>')
    rects.append(f'<rect x="{x}" y="{y + (h - 1) * b}" width="{w * b}" height="{b}" fill="{CYAN}"/>')
    return "".join(rects)


def svg(w, h, body, css="", label=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
            f'shape-rendering="crispEdges" role="img" aria-label="{label.replace("&", "&amp;")}">'
            f'<style>{css}@media (prefers-reduced-motion: reduce) {{ * {{ animation: none !important; }} }}</style>'
            f'{body}</svg>')


def stars(w, h, n, seed, max_y=None):
    r = random.Random(seed)
    out = []
    for _ in range(n):
        s = r.choice((4, 4, 4, 8))
        col = r.choice((TEXT, TEXT, YELLOW, CYAN, PINK))
        out.append(f'<rect class="tw" style="animation-delay:-{r.uniform(0, 3):.2f}s" x="{r.randrange(0, w, 4)}" '
                   f'y="{r.randrange(0, max_y or h, 4)}" width="{s}" height="{s}" fill="{col}"/>')
    return "".join(out)


TWINKLE = ".tw { animation: tw 2.6s steps(2, jump-none) infinite; } @keyframes tw { 50% { opacity: .15; } }"


# ----------------------------------------------------------------------------- banner
def banner():
    W, H = 1280, 440
    body = [f'<rect width="{W}" height="{H}" fill="{SKY}"/>',
            f'<rect y="150" width="{W}" height="140" fill="{NIGHT}"/>',
            f'<rect y="290" width="{W}" height="150" fill="#23164a"/>',
            stars(W, H, 90, 7, 300), sprite("moon", 740, 40, 6)]
    body.append('<g class="drift">' + sprite("cloud", 0, 70, 10) + sprite("cloud", 520, 30, 7) + "</g>")
    for k, (col, base, amp, per) in enumerate((("#2c1a57", 380, 70, 22), ("#34205f", 410, 45, 13))):
        for c in range(0, W, 16):
            top = base - round(abs(math.sin((c / 16 + k * 9) / per * math.pi)) * amp / 8) * 8
            body.append(f'<rect x="{c}" y="{top}" width="16" height="{H - top}" fill="{col}"/>')

    # logo, each letter bobbing in turn
    for i, (ch, col) in enumerate(zip("SIFT", (YELLOW, PINK, CYAN, GREEN))):
        body.append(f'<g class="bob" style="animation-delay:{i * .18:.2f}s">{text(ch, 70 + i * 96, 58, 14, col, shadow=INK)}</g>')
    body.append(text("7,000 photos in.", 72, 196, 5, TEXT, shadow=INK))
    body.append(text("Only the trips", 72, 246, 5, YELLOW, shadow=INK))
    body.append(text("come out.", 72, 296, 5, YELLOW, shadow=INK))
    body.append(text("A free Windows app for your Google Takeout", 74, 356, 2, MUTED))

    # the sorting machine
    px, py = 800, 52
    body += [f'<rect x="{px + 10}" y="{py + 10}" width="430" height="330" fill="{INK}"/>',
             f'<rect x="{px}" y="{py}" width="430" height="330" fill="{PANEL}" stroke="{INK}" stroke-width="6"/>',
             f'<rect x="{px + 3}" y="{py + 3}" width="424" height="30" fill="{PURPLE}"/>',
             text("takeout-001.zip", px + 14, py + 11, 2, INK),
             f'<rect x="{px + 360}" y="{py + 10}" width="14" height="14" fill="{YELLOW}" stroke="{INK}" stroke-width="3"/>',
             f'<rect x="{px + 382}" y="{py + 10}" width="14" height="14" fill="{GREEN}" stroke="{INK}" stroke-width="3"/>',
             f'<rect x="{px + 404}" y="{py + 10}" width="14" height="14" fill="{CYAN}" stroke="{INK}" stroke-width="3"/>']
    sx, sy, cw, ch = px + 20, py + 56, 168, 126          # scanner window, card size (12x9 at 14px)
    body += [f'<rect x="{sx - 4}" y="{sy - 4}" width="{cw + 8}" height="{ch + 8}" fill="{INK}"/>']
    tiles = [("Srinagar", GREEN), ("Sonamarg", CYAN), ("Kaza", YELLOW)]
    tx, ty0, tw_, th = px + 214, py + 56, 196, 64
    targets = []
    for k, (name, col) in enumerate(tiles):
        ty = ty0 + k * 80
        body += [f'<rect x="{tx + 4}" y="{ty + 4}" width="{tw_}" height="{th}" fill="{INK}"/>',
                 f'<rect x="{tx}" y="{ty}" width="{tw_}" height="{th}" fill="{PANEL2}" stroke="{INK}" stroke-width="4"/>',
                 f'<rect class="flash f{k}" x="{tx}" y="{ty}" width="{tw_}" height="{th}" fill="{col}"/>',
                 sprite("folder", tx + 12, ty + 16, 4), text(name, tx + 54, ty + 25, 3, TEXT)]
        targets.append((tx + tw_ / 2, ty + th / 2))
    bx, by, bw, bh = sx - 4, sy + ch + 52, cw + 8, 56
    body += [f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" fill="{INK}" stroke="{LINE}" stroke-width="3"/>',
             f'<rect class="flash f3" x="{bx}" y="{by}" width="{bw}" height="{bh}" fill="{PINK}"/>',
             text("Left in", bx + 12, by + 10, 2, MUTED), text("Google Photos", bx + 12, by + 30, 2, PINK)]
    targets.append((bx + bw / 2, by + bh / 2))

    # four photos take turns: three trips fly to their folders, the selfie goes to the bin
    chips = [("Srinagar", GREEN), ("Sonamarg", CYAN), ("Kaza, Spiti", YELLOW), ("Faces found", PINK)]
    css = [TWINKLE,
           ".bob { animation: bob 1.8s steps(2, jump-none) infinite; } @keyframes bob { 50% { transform: translateY(-8px); } }",
           ".drift { animation: drift 60s steps(240) infinite; } @keyframes drift { from { transform: translateX(-700px); } to { transform: translateX(1300px); } }",
           ".scan { animation: scan 1.1s steps(12) infinite alternate; } @keyframes scan { to { transform: translateY(" + str(ch - 6) + "px); } }",
           ".card, .flash, .chip { opacity: 0; } .card { transform-box: fill-box; transform-origin: center; }"]
    T = 10  # seconds per full loop
    for k in range(4):
        s = k * 25
        cx, cy = sx + cw / 2, sy + ch / 2
        dx, dy = targets[k][0] - cx, targets[k][1] - cy
        card = landscape(sx, sy, 14, 40 + k) if k < 3 else (
            f'<rect x="{sx}" y="{sy}" width="{cw}" height="{ch}" fill="#7a4fbf"/>' + sprite("face", sx + 44, sy + 22, 10))
        body.append(f'<g class="card c{k}">{card}</g>')
        name, col = chips[k]
        cwid = text_width(name, 2) + 20
        body.append(f'<g class="chip h{k}"><rect x="{sx - 4}" y="{sy + ch + 14}" width="{cwid}" height="26" fill="{col}" '
                    f'stroke="{INK}" stroke-width="3"/>{text(name, sx + 6, sy + ch + 20, 2, INK)}</g>')
        css.append(
            f".c{k} {{ animation: c{k} {T}s infinite; }} @keyframes c{k} {{ "
            f"0%{f', {s - 0.01}%' if s else ''} {{ opacity: 0; transform: none; }} "
            f"{s}% {{ opacity: 1; transform: none; animation-timing-function: steps(1); }} "
            f"{s + 13}% {{ opacity: 1; transform: none; animation-timing-function: steps(5); }} "
            f"{s + 18}% {{ opacity: 1; transform: translate({dx * .5:.0f}px, {dy * .5 - 60:.0f}px) scale(.55) rotate(-8deg); animation-timing-function: steps(5); }} "
            f"{s + 23}% {{ opacity: 1; transform: translate({dx:.0f}px, {dy:.0f}px) scale(.12); }} "
            f"{s + 23.5}% {{ opacity: 0; transform: translate({dx:.0f}px, {dy:.0f}px) scale(.12); }} 100% {{ opacity: 0; }} }}")
        css.append(f".h{k} {{ animation: h{k} {T}s steps(1) infinite; }} @keyframes h{k} {{ "
                   f"0%, {s + 6}% {{ opacity: 0; }} {s + 6.01}%, {s + 18}% {{ opacity: 1; }} {s + 18.01}%, 100% {{ opacity: 0; }} }}")
        css.append(f".f{k} {{ animation: f{k} {T}s steps(1) infinite; }} @keyframes f{k} {{ "
                   f"0%, {s + 23}% {{ opacity: 0; }} {s + 23.01}%, {s + 25}% {{ opacity: .85; }} {s + 25.01}%, 100% {{ opacity: 0; }} }}")
    body.append(f'<rect class="scan" x="{sx}" y="{sy}" width="{cw}" height="6" fill="{CYAN}" opacity=".8"/>')
    return svg(W, H, "".join(body), " ".join(css), "Sift: 7,000 photos in, only the trips come out")


# ----------------------------------------------------------------------------- section headers
def header(title, icon, color, seed):
    W, H = 1280, 112
    body = [f'<rect width="{W}" height="{H}" fill="{SKY}"/>', stars(W, H, 26, seed),
            f'<rect x="0" y="{H - 8}" width="{W}" height="8" fill="{color}"/>',
            f'<rect x="0" y="{H - 16}" width="{W}" height="8" fill="{INK}"/>',
            f'<g class="hop">{sprite(icon, 40, 22, 7)}</g>',
            text(title, 120, 30, 6, TEXT, shadow=INK),
            f'<rect class="cursor" x="{120 + text_width(title, 6) + 20}" y="30" width="24" height="42" fill="{color}"/>']
    css = (TWINKLE + " .hop { animation: hop 1.2s steps(2, jump-none) infinite; } @keyframes hop { 50% { transform: translateY(-8px); } }"
           " .cursor { animation: blink 1s steps(1) infinite; } @keyframes blink { 50% { opacity: 0; } }")
    return svg(W, H, "".join(body), css, title)


# ----------------------------------------------------------------------------- what stays out
def stays_out():
    items = [("People", "face", PINK), ("Home", "home", ORANGE), ("WhatsApp", "chat", GREEN),
             ("Screens", "phone", PURPLE), ("No GPS", "pin", ORANGE), ("Duplicates", "dupe", CYAN)]
    W, H = 1280, 300
    body = [f'<rect width="{W}" height="{H}" fill="{SKY}"/>']
    css = [".x { animation: x 3s steps(1) infinite; opacity: 0; }"]
    for i, (name, icon, col) in enumerate(items):
        c, r = i % 3, i // 3
        x, y = 24 + c * 416, 22 + r * 140
        body += [f'<rect x="{x + 8}" y="{y + 8}" width="392" height="116" fill="{INK}"/>',
                 f'<rect x="{x}" y="{y}" width="392" height="116" fill="{PANEL}" stroke="{INK}" stroke-width="5"/>',
                 f'<rect x="{x}" y="{y}" width="12" height="116" fill="{col}"/>',
                 sprite(icon, x + 36, y + 26, 8), text(name, x + 126, y + 44, 4, TEXT),
                 f'<g class="x" style="animation-delay:{i * .5:.1f}s">{text("X", x + 330, y + 38, 5, RED, shadow=INK)}</g>']
    css.append("@keyframes x { 0% { opacity: 0; } 8% { opacity: 1; } 70% { opacity: 1; } 78% { opacity: 0; } }")
    return svg(W, H, "".join(body), " ".join(css), "What Sift leaves out: people, home, WhatsApp, screens, no GPS, duplicates")


# ----------------------------------------------------------------------------- GPS fix
def gps():
    W, H = 1280, 300
    rows = [("10:12", "Dal Lake, Srinagar", "GPS", GREEN), ("10:41", None, "Fixed", PINK),
            ("11:30", "Nishat Bagh, Srinagar", "GPS", GREEN), ("12:05", "No GPS > Srinagar", "Nearby", CYAN)]
    body = [f'<rect width="{W}" height="{H}" fill="{INK}"/>']
    for i, (t, place, tag, col) in enumerate(rows):
        y = 24 + i * 68
        body += [f'<rect x="24" y="{y}" width="{W - 48}" height="54" fill="{PANEL if place else "#3b1838"}"/>',
                 f'<rect x="24" y="{y}" width="12" height="54" fill="{col}"/>',
                 text(t, 60, y + 13, 4, MUTED), text(tag, W - 48 - text_width(tag, 4) - 24, y + 13, 4, col)]
        if place:
            body.append(text(place, 240, y + 13, 4, TEXT))
        else:
            body += [f'<g class="bad">{text("Hyderabad", 240, y + 13, 4, RED)}'
                     f'<rect x="236" y="{y + 25}" width="{text_width("Hyderabad", 4) + 8}" height="4" fill="{RED}"/></g>',
                     f'<g class="good">{text("> Srinagar", 240 + text_width("Hyderabad", 4) + 24, y + 13, 4, GREEN)}</g>']
    css = (".good { animation: good 3s steps(1) infinite; } @keyframes good { 0%, 40% { opacity: 0; } 41%, 100% { opacity: 1; } }"
           " .bad { animation: bad 3s steps(1) infinite; } @keyframes bad { 0%, 40% { opacity: 1; } 41%, 100% { opacity: .55; } }")
    return svg(W, H, "".join(body), css, "A photo tagged Hyderabad between two Srinagar photos is moved back to Srinagar")


# ----------------------------------------------------------------------------- download button and divider
def download():
    W, H = 560, 120
    label = "Download Sift.exe"
    body = [f'<rect x="14" y="14" width="{W - 28}" height="{H - 34}" fill="{INK}"/>',
            f'<rect x="4" y="4" width="{W - 28}" height="{H - 34}" fill="{YELLOW}" stroke="{INK}" stroke-width="6"/>',
            f'<rect x="10" y="{H - 40}" width="{W - 40}" height="6" fill="#d9a400"/>',
            f'<g class="down">{sprite("arrow", 34, 26, 5)}</g>',
            text(label, 96, 32, 4, INK)]
    css = ".down { animation: down .9s steps(2, jump-none) infinite; } @keyframes down { 50% { transform: translateY(6px); } }"
    return svg(W, H, "".join(body), css, "Download Sift.exe")


def divider():
    W, H, n = 1280, 28, 40
    seg = (W - 16) / n
    body = [f'<rect width="{W}" height="{H}" fill="{INK}"/>']
    css = []
    for i in range(n):
        col = (YELLOW, PINK, CYAN, GREEN, ORANGE, PURPLE)[i * 6 // n]
        body.append(f'<rect class="s" style="animation-delay:{i * 0.06:.2f}s" x="{8 + i * seg:.0f}" y="6" width="{seg - 4:.0f}" height="16" fill="{col}"/>')
    css.append(".s { opacity: .18; animation: fill 4s steps(1) infinite; } @keyframes fill { 0% { opacity: .18; } 10%, 75% { opacity: 1; } 85%, 100% { opacity: .18; } }")
    return svg(W, H, "".join(body), " ".join(css), "")


if __name__ == "__main__":
    files = {
        "banner.svg": banner(), "stays-out.svg": stays_out(), "gps.svg": gps(),
        "download.svg": download(), "divider.svg": divider(),
        "h-how.svg": header("How it works", "map", CYAN, 1), "h-out.svg": header("What stays out", "face", PINK, 2),
        "h-gps.svg": header("Fixes bad GPS", "pin", ORANGE, 3), "h-safe.svg": header("Privacy & safety", "lock", GREEN, 4),
        "h-build.svg": header("Build it yourself", "wrench", PURPLE, 5), "h-get.svg": header("Get Sift", "star", YELLOW, 6),
    }
    for name, data in files.items():
        (OUT / name).write_text(data, encoding="utf-8")
        print(f"{name:16} {len(data) // 1024:4} KB")
