#!/usr/bin/env python3
"""Now-playing tile for the dashboard (runs in a kitty window).

  * 60 fps audio spectrum from `cava` (pacman -S cava)
  * title / artist, seekable progress bar, clickable prev / play-pause / next
  * time-synced lyrics from LRCLIB (https://lrclib.net), cached on disk

Keys: space = play/pause   n = next   p = previous   q = quit
Mouse: click a button, or click the progress bar to seek.

Env: NOWPLAYING_PLAYER      playerctl player name        (default: spotify)
     NOWPLAYING_WAVE_DELAY  seconds to delay the wave    (default: 0; try 0.2
                            with Bluetooth audio, where the sound lags behind)
     NOWPLAYING_LYRIC_LEAD  seconds lyrics show early    (default: 0.3)
"""
import bisect
import ctypes
import hashlib
import json
import os
import re
import select
import shutil
import subprocess
import sys
import termios
import threading
import time
import tty
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import deque

PLAYER = os.environ.get("NOWPLAYING_PLAYER", "spotify")
FPS = 60
BARS = 96
WAVE_DELAY = float(os.environ.get("NOWPLAYING_WAVE_DELAY", "0"))
LYRIC_LEAD = float(os.environ.get("NOWPLAYING_LYRIC_LEAD", "0.3"))
CACHE = os.path.expanduser("~/.cache/dashboard-lyrics")
UA = "hyprland-dashboard/1.0"

BLOCKS = " ▁▂▃▄▅▆▇█"
# Nerd Font (Material Design) glyphs: single-cell in the "Nerd Font Mono" family
I_PREV, I_PLAY, I_PAUSE, I_NEXT = "\U000F04AE", "\U000F040A", "\U000F03E4", "\U000F04AD"
RST, BOLD, DIM = "\x1b[0m", "\x1b[1m", "\x1b[2m"
ACC = "\x1b[38;5;12m"    # terminal palette colours -> follow the kitty theme
ACC2 = "\x1b[38;5;13m"
MOUSE = re.compile(r"\x1b\[<(\d+);(\d+);(\d+)([Mm])")


# --------------------------------------------------------------------------- text helpers
def fmt(sec):
    sec = int(max(sec, 0))
    return f"{sec // 60}:{sec % 60:02d}"


def cw(c):
    return 2 if unicodedata.east_asian_width(c) in "WF" else 1


def wlen(s):
    return sum(cw(c) for c in s)


def clip(s, w):
    if wlen(s) <= w:
        return s
    out, n = "", 0
    for c in s:
        if n + cw(c) > w - 1:
            break
        out += c
        n += cw(c)
    return out + "…"


def center(s, cols, style=""):
    s = clip(s, max(cols - 2, 1))
    return " " * ((cols - wlen(s)) // 2) + style + s + RST


# --------------------------------------------------------------------------- lyrics
LRC = re.compile(r"\[(\d+):(\d+(?:\.\d+)?)\]")


def parse_lrc(text):
    lines = []
    for raw in text.splitlines():
        stamps = LRC.findall(raw)
        txt = LRC.sub("", raw).strip() or "♪"
        for m, s in stamps:
            lines.append((int(m) * 60 + float(s), txt))
    lines.sort(key=lambda x: x[0])
    return lines


def http_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=8) as r:
        return json.load(r)


def lookup_lyrics(artist, title, album, length):
    """Returns (state, lines, cacheable). state: synced | plain | none."""
    q = urllib.parse.urlencode
    first_artist = re.split(r",|&| feat\.?", artist)[0].strip()
    clean = re.sub(r"\s*[\(\[-].*$", "", title).strip() or title
    get = {"artist_name": artist, "track_name": title, "album_name": album}
    if length:
        get["duration"] = int(round(length))
    urls = ["https://lrclib.net/api/get?" + q(get)]
    for t in dict.fromkeys([title, clean]):
        urls.append("https://lrclib.net/api/search?" + q({"track_name": t, "artist_name": first_artist}))

    reached = False
    plain = None
    for url in urls:
        try:
            data = http_json(url)
            reached = True
        except urllib.error.HTTPError:
            reached = True
            continue
        except Exception:
            continue
        cands = data if isinstance(data, list) else [data]
        if length:
            cands = [c for c in cands if abs((c.get("duration") or 0) - length) <= 6] or cands[:1]
        for c in cands:
            if c.get("instrumental"):
                return "none", [], True
            if c.get("syncedLyrics"):
                lines = parse_lrc(c["syncedLyrics"])
                if lines:
                    return "synced", lines, True
            if c.get("plainLyrics") and plain is None:
                plain = [(0.0, ln) for ln in c["plainLyrics"].splitlines()]
    if plain:
        return "plain", plain, True
    return "none", [], reached


# --------------------------------------------------------------------------- player state
class Player:
    FMT = "{{status}}\t{{artist}}\t{{title}}\t{{album}}\t{{mpris:length}}\t{{position}}"

    def __init__(self):
        self.lock = threading.Lock()
        self.wake = threading.Event()
        self.status = ""
        self.artist = self.title = self.album = ""
        self.length = 0.0
        self.pos = 0.0
        self.pos_t = time.monotonic()
        self.key = None
        self.lyr_state = "idle"          # idle | loading | none | plain | synced
        self.lyr = []
        self.lyr_times = []
        threading.Thread(target=self._poll, daemon=True).start()

    # polling runs off the UI thread so rendering never waits on playerctl
    def _poll(self):
        while True:
            try:
                out = subprocess.run(["playerctl", "-p", PLAYER, "metadata", "--format", self.FMT],
                                     capture_output=True, text=True, timeout=2).stdout.strip("\n")
            except Exception:
                out = ""
            parts = out.split("\t")
            with self.lock:
                if len(parts) == 6:
                    st, ar, ti, al, ln, ps = parts
                    self.status, self.artist, self.title, self.album = st, ar, ti, al
                    try:
                        self.length = float(ln) / 1e6
                    except ValueError:
                        self.length = 0.0
                    try:
                        self.pos = float(ps) / 1e6
                    except ValueError:
                        self.pos = 0.0
                    self.pos_t = time.monotonic()
                    key = (ar, ti, al, round(self.length))
                    if ti and key != self.key:
                        self.key = key
                        self.lyr_state, self.lyr, self.lyr_times = "loading", [], []
                        threading.Thread(target=self._lyrics, args=(key, ar, ti, al, self.length),
                                         daemon=True).start()
                else:
                    self.status = ""
            self.wake.wait(0.5)
            self.wake.clear()

    def _lyrics(self, key, artist, title, album, length):
        name = hashlib.sha1("|".join(map(str, key)).encode()).hexdigest() + ".json"
        path = os.path.join(CACHE, name)
        state, lines = None, []
        try:
            with open(path) as f:
                c = json.load(f)
            state, lines = c["state"], [tuple(x) for x in c["lines"]]
        except Exception:
            pass
        if state is None:
            state, lines, cacheable = lookup_lyrics(artist, title, album, length)
            if cacheable:
                try:
                    os.makedirs(CACHE, exist_ok=True)
                    with open(path, "w") as f:
                        json.dump({"state": state, "lines": lines}, f)
                except OSError:
                    pass
        with self.lock:
            if self.key == key:
                self.lyr_state, self.lyr = state, lines
                self.lyr_times = [t for t, _ in lines]

    def snapshot(self):
        with self.lock:
            pos = self.pos
            if self.status == "Playing":
                pos += time.monotonic() - self.pos_t
            if self.length:
                pos = min(pos, self.length)
            return {"status": self.status, "artist": self.artist, "title": self.title,
                    "length": self.length, "pos": pos, "lyr_state": self.lyr_state,
                    "lyr": self.lyr, "lyr_times": self.lyr_times}

    def act(self, name, *args):
        subprocess.Popen(["playerctl", "-p", PLAYER, name, *args],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        with self.lock:                  # optimistic UI so clicks feel instant
            now = time.monotonic()
            if name == "play-pause" and self.status in ("Playing", "Paused"):
                if self.status == "Playing":
                    self.pos += now - self.pos_t
                self.status = "Paused" if self.status == "Playing" else "Playing"
                self.pos_t = now
            elif name == "position" and args:
                try:
                    self.pos, self.pos_t = float(args[0]), now
                except ValueError:
                    pass
        threading.Timer(0.2, self.wake.set).start()


# --------------------------------------------------------------------------- cava
class Cava:
    def __init__(self):
        self.proc = None
        self.fd = None
        self.buf = b""
        self.frames = deque()
        self.last = [0.0] * BARS
        self.tried = 0.0
        self.start()

    def start(self):
        self.tried = time.monotonic()
        if not shutil.which("cava"):
            return
        cfg = f"/tmp/dash-cava-{os.getuid()}.conf"
        with open(cfg, "w") as f:
            f.write(f"[general]\nbars = {BARS}\nframerate = {FPS}\n"
                    "[smoothing]\nnoise_reduction = 60\n"
                    "[output]\nmethod = raw\nraw_target = /dev/stdout\ndata_format = ascii\n"
                    "ascii_max_range = 1000\nbar_delimiter = 59\nframe_delimiter = 10\n")
        libc = ctypes.CDLL("libc.so.6", use_errno=True)
        self.proc = subprocess.Popen(["cava", "-p", cfg], stdout=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL,
                                     preexec_fn=lambda: libc.prctl(1, 15))  # die with us
        self.fd = self.proc.stdout.fileno()
        self.buf = b""

    def read(self):
        data = os.read(self.fd, 65536)
        if not data:
            self.proc = None
            return
        self.buf += data
        *lines, self.buf = self.buf.split(b"\n")
        now = time.monotonic()
        for ln in lines:
            try:
                vals = [int(x) / 1000.0 for x in ln.decode().split(";") if x != ""]
            except ValueError:
                continue
            if vals:
                self.frames.append((now, vals))
        while self.frames and now - self.frames[0][0] > WAVE_DELAY + 1.0:
            self.frames.popleft()

    def levels(self):
        if self.proc is None and time.monotonic() - self.tried > 3:
            self.start()                 # cava exited (e.g. default sink changed)
        if not self.frames:
            return self.last
        if WAVE_DELAY > 0:
            cutoff = time.monotonic() - WAVE_DELAY
            for t, v in self.frames:
                if t <= cutoff:
                    self.last = v
                else:
                    break
        else:
            self.last = self.frames[-1][1]
        return self.last

    def close(self):
        if self.proc:
            self.proc.terminate()


# --------------------------------------------------------------------------- rendering
def lyric_block(snap, pos, h, cols):
    st = snap["lyr_state"]
    if st == "synced" and snap["lyr"]:
        idx = max(bisect.bisect_right(snap["lyr_times"], pos + LYRIC_LEAD) - 1, 0)
        block = []
        for k in range(h):
            j = idx + k - h // 2
            if j < 0 or j >= len(snap["lyr"]):
                block.append("")
            elif j == idx:
                block.append(center(snap["lyr"][j][1], cols, BOLD + ACC2))
            else:
                block.append(center(snap["lyr"][j][1], cols, DIM if abs(j - idx) < 3 else "\x1b[2;38;5;8m"))
        return block
    if st == "plain" and snap["lyr"]:
        block = [center(t, cols, DIM) for _, t in snap["lyr"][:h]]
        if len(block) == h:
            block[-1] = center("(lyrics are not time-synced)", cols, ACC)
        return block
    msg = {"loading": "fetching lyrics…", "none": "no lyrics found"}.get(st, "")
    return [""] * (h // 2) + [center(msg, cols, DIM)]


def render(snap, levels, ui, cols, rows):
    L = []

    def add(s=""):
        L.append(s + "\x1b[K")
        return len(L)                    # 1-based screen row

    playing = snap["status"] == "Playing"
    have = bool(snap["status"])
    w = max(cols - 4, 10)

    add()
    add(center(snap["title"] if have else "Nothing playing", cols, BOLD + ACC))
    add(center(snap["artist"] if have else "start Spotify", cols, DIM))
    add()

    wave_h = max(min(rows // 5, 9), 3)
    lv = [levels[min(int(i * len(levels) / w), len(levels) - 1)] for i in range(w)]
    for r in range(wave_h, 0, -1):
        row = "".join(BLOCKS[int(max(0, min(8, v * wave_h * 8 - (r - 1) * 8)))] for v in lv)
        add("  " + ACC2 + row + RST)

    length, pos = snap["length"], snap["pos"]
    frac = min(pos / length, 1.0) if length else 0.0
    filled = int(frac * w)
    ui["bar"] = (add("  " + ACC + "━" * filled + RST + DIM + "─" * (w - filled) + RST), 3, 2 + w, length)
    t1, t2 = fmt(pos), fmt(length)
    add("  " + DIM + t1 + " " * max(w - len(t1) - len(t2), 1) + t2 + RST)
    add()

    # buttons: 3-row boxes; their geometry is recorded so clicks map exactly onto them
    bw, gap = 9, 3
    x0 = max((cols - (3 * bw + 2 * gap)) // 2, 0) + 1
    icons = [(I_PREV, "previous"), (I_PAUSE if playing else I_PLAY, "play-pause"), (I_NEXT, "next")]
    top, mid, bot, btns = [], [], [], []
    for i, (ic, act) in enumerate(icons):
        col = (BOLD + ACC2) if i == 1 else ACC
        top.append(col + "╭" + "─" * (bw - 2) + "╮" + RST)
        mid.append(col + "│" + f"{ic:^{bw - 2}}" + "│" + RST)
        bot.append(col + "╰" + "─" * (bw - 2) + "╯" + RST)
        btns.append((x0 + i * (bw + gap), x0 + i * (bw + gap) + bw - 1, act))
    pad, sep = " " * (x0 - 1), " " * gap
    by = add(pad + sep.join(top))
    add(pad + sep.join(mid))
    add(pad + sep.join(bot))
    ui["buttons"], ui["brow"] = btns, (by, by + 2)
    add()

    add(center("──────  lyrics  ──────", cols, DIM))
    h = rows - len(L)
    if h > 0:
        for ln in lyric_block(snap, pos, h, cols)[:h]:
            add(ln)
    return "\x1b[H" + "\n".join(L[:rows]) + "\x1b[J"


def handle_click(ps, ui, x, y):
    b0, b1 = ui.get("brow", (0, 0))
    if b0 <= y <= b1:
        for lo, hi, act in ui.get("buttons", []):
            if lo <= x <= hi:
                ps.act(act)
                return
    row, lo, hi, length = ui.get("bar", (0, 0, 0, 0))
    if y == row and lo <= x <= hi and length:
        ps.act("position", f"{(x - lo) / max(hi - lo, 1) * length:.2f}")


def main():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    ps, cava, ui = Player(), Cava(), {}
    out = sys.stdout
    out.write("\x1b[?25l\x1b[?1049h\x1b[?1000h\x1b[?1006h")
    out.flush()
    try:
        tty.setcbreak(fd)
        last = 0.0
        while True:
            fds = [fd] + ([cava.fd] if cava.proc else [])
            ready, _, _ = select.select(fds, [], [], 1.0 / FPS)
            if fd in ready:
                data = os.read(fd, 1024).decode(errors="ignore")
                for m in MOUSE.finditer(data):
                    if m.group(4) == "M" and int(m.group(1)) == 0:
                        handle_click(ps, ui, int(m.group(2)), int(m.group(3)))
                for ch in MOUSE.sub("", data):
                    if ch == " ":
                        ps.act("play-pause")
                    elif ch == "n":
                        ps.act("next")
                    elif ch == "p":
                        ps.act("previous")
                    elif ch == "q":
                        return
            if cava.proc and cava.fd in ready:
                cava.read()
            now = time.monotonic()
            if now - last >= 1.0 / FPS:
                last = now
                cols, rows = shutil.get_terminal_size((80, 40))
                out.write(render(ps.snapshot(), cava.levels(), ui, cols, rows))
                out.flush()
    except KeyboardInterrupt:
        pass
    finally:
        cava.close()
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        out.write("\x1b[?1000l\x1b[?1006l\x1b[?1049l\x1b[?25h")
        out.flush()


if __name__ == "__main__":
    main()
