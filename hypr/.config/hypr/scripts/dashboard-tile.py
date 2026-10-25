#!/usr/bin/env python3
"""Info tiles for the dashboard (each runs in its own kitty window).

  dashboard-tile.py cal       big clock + month calendar (today highlighted)
                              + Wikipedia "on this day" for today's date
  dashboard-tile.py weather   current weather (wttr.in) + local news (Google News RSS)
  dashboard-tile.py system    CPU, memory, GPU, disks, network and estimated power

Env: DASH_WEATHER_LOCATION  wttr.in location          (default: Oradea)
     DASH_NEWS_QUERY        Google News search query   (default: Oradea OR Bihor)
     DASH_NEWS_LANG         news language/region       (default: ro / RO)
     DASH_WIKI_LANG         Wikipedia language         (default: en)
     DASH_PAGE_SECONDS      seconds per page of items  (default: 20, 0 = no paging)
     DASH_CPU_TDP           CPU TDP in watts           (default: 120)
Data is fetched in background threads and cached, so the clock never stalls.
Mouse wheel scrolls through paginated feeds (cal history, weather news).
"""
import calendar
import datetime as dt
import email.utils
import html
import json
import os
import re
import select
import shutil
import subprocess
import sys
import termios
import textwrap
import threading
import tty
import time
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

UA = "hyprland-dashboard/1.0"
LOC = os.environ.get("DASH_WEATHER_LOCATION", "Oradea")
QUERY = os.environ.get("DASH_NEWS_QUERY", "Oradea OR Bihor")
LANG = os.environ.get("DASH_NEWS_LANG", "ro")
REGION = os.environ.get("DASH_NEWS_REGION", "RO")
WIKI = os.environ.get("DASH_WIKI_LANG", "en")
PAGE = float(os.environ.get("DASH_PAGE_SECONDS", "20"))
CPU_TDP = float(os.environ.get("DASH_CPU_TDP", "120"))

RST, BOLD, DIM, REV = "\x1b[0m", "\x1b[1m", "\x1b[2m", "\x1b[7m"
ACC, ACC2, SUB = "\x1b[38;5;12m", "\x1b[38;5;13m", "\x1b[38;5;8m"
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")

# Clock font: 3x5 pixel digits, each pixel 2 cells wide, two pixel rows per text row
# (half blocks), so a digit is 6 columns x 3 rows.
PIX = {
    "0": ("###", "# #", "# #", "# #", "###"), "1": (" # ", "## ", " # ", " # ", "###"),
    "2": ("###", "  #", "###", "#  ", "###"), "3": ("###", "  #", "###", "  #", "###"),
    "4": ("# #", "# #", "###", "  #", "  #"), "5": ("###", "#  ", "###", "  #", "###"),
    "6": ("###", "#  ", "###", "# #", "###"), "7": ("###", "  #", "  #", "  #", "  #"),
    "8": ("###", "# #", "###", "# #", "###"), "9": ("###", "# #", "###", "  #", "###"),
    ":": (" ", "#", " ", "#", " "),
}
HALF = {(0, 0): " ", (1, 0): "▀", (0, 1): "▄", (1, 1): "█"}


def glyph(ch):
    """3 text rows for one character."""
    px = PIX[ch]
    wide = 1 if ch == ":" else 2
    rows = []
    for r in range(0, 6, 2):
        top = px[r] if r < 5 else " " * len(px[0])
        bot = px[r + 1] if r + 1 < 5 else " " * len(px[0])
        rows.append("".join(HALF[(top[i] == "#", bot[i] == "#")] * wide for i in range(len(px[0]))))
    return rows


def cw(c):
    return 0 if unicodedata.combining(c) else (2 if unicodedata.east_asian_width(c) in "WF" else 1)


def wlen(s):
    return sum(cw(c) for c in ANSI.sub("", s))


def center(s, cols):
    return " " * max((cols - wlen(s)) // 2, 0) + s


def wrap(text, width, indent="", first=""):
    return textwrap.wrap(text, max(width, 10), initial_indent=first, subsequent_indent=indent) or [first]


# ---------------------------------------------------------------- background fetching
class Feed:
    """Runs fn() every `every` seconds in a thread; keeps the last good value."""

    def __init__(self, fn, every):
        self.fn, self.every, self.value, self.ok = fn, every, None, None
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        while True:
            try:
                self.value, self.ok = self.fn(), True
            except Exception:
                self.ok = False if self.value is None else True
            time.sleep(self.every if self.ok else 30)


def get(url, timeout=10, ua=UA):
    req = urllib.request.Request(url, headers={"User-Agent": ua})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def fetch_history():
    d = dt.date.today()
    url = f"https://api.wikimedia.org/feed/v1/wikipedia/{WIKI}/onthisday/selected/{d.month:02d}/{d.day:02d}"
    data = json.loads(get(url))
    items = []
    for e in data.get("selected", []):
        txt = re.sub(r"\s+", " ", e.get("text", "")).strip()
        if txt:
            items.append((e.get("year"), txt))
    items.sort(key=lambda x: -(x[0] or 0))
    return items


TR_CACHE = os.path.expanduser("~/.cache/dashboard-translations.json")
TRANSLATE = os.environ.get("DASH_NEWS_TRANSLATE", "1") != "0"
BORING = re.compile(r"weather (forecast|conditions)|live scores|odds|sofascore|predictions|britannica|\bmeteo\b", re.I)


def translate(texts, src):
    """Romanian -> English via MyMemory (free, no key). Cached on disk so each
    headline is only translated once. Falls back to the original text on failure."""
    try:
        with open(TR_CACHE) as f:
            cache = json.load(f)
    except Exception:
        cache = {}
    todo = [t for t in texts if t not in cache]

    def one(t):
        q = urllib.parse.urlencode({"q": t[:450], "langpair": f"{src}|en"})
        try:
            r = json.loads(get("https://api.mymemory.translated.net/get?" + q, 10))
            out = html.unescape(r["responseData"]["translatedText"]).strip()
            if r.get("responseStatus") == 200 and out and "MYMEMORY WARNING" not in out.upper():
                cache[t] = out
        except Exception:
            pass

    if todo:
        with ThreadPoolExecutor(max_workers=6) as ex:
            list(ex.map(one, todo))
        # keep the cache from growing without bound
        for k in list(cache)[:-600]:
            del cache[k]
        try:
            os.makedirs(os.path.dirname(TR_CACHE), exist_ok=True)
            with open(TR_CACHE, "w") as f:
                json.dump(cache, f)
        except OSError:
            pass
    return [cache.get(t) for t in texts]


def parse_rss(url):
    items = []
    for it in ET.fromstring(get(url)).iter("item"):
        title = html.unescape(it.findtext("title") or "").strip()
        src = (it.findtext("source") or "").strip()
        if src and title.endswith(" - " + src):
            title = title[: -len(src) - 3]
        try:
            when = email.utils.parsedate_to_datetime(it.findtext("pubDate")).timestamp()
        except Exception:
            when = 0
        if len(title) >= 20:
            items.append([when, title, src, False])
    return items


def gnews(query, hl, gl):
    q = urllib.parse.urlencode({"q": query + " when:3d", "hl": hl, "gl": gl, "ceid": f"{gl}:{hl.split('-')[0]}"})
    return parse_rss("https://news.google.com/rss/search?" + q)


def fetch_news():
    """Local news: Romanian-language feed translated to English, merged with English results."""
    local, english = [], []
    try:
        local = gnews(QUERY, LANG, REGION)
    except Exception:
        pass
    try:
        english = [i for i in gnews(QUERY, "en-US", "US") if not BORING.search(i[1])]
    except Exception:
        pass
    if not local and not english:
        raise ValueError("no news")
    local = local[:30]
    if TRANSLATE and LANG != "en" and local:
        for item, tr in zip(local, translate([i[1] for i in local], LANG)):
            if tr:
                item[1], item[3] = tr, True
    out, seen = [], set()
    for when, title, src, tr in sorted(local + english, key=lambda x: -x[0]):
        key = re.sub(r"\W+", "", title.lower())[:32]
        if key in seen:
            continue
        seen.add(key)
        out.append((when, title, src, tr))
    return out[:40]


def fetch_weather():
    url = f"https://wttr.in/{urllib.parse.quote(LOC)}?0&m&Q"
    txt = get(url, 8, ua="curl/8.0")   # wttr.in serves plain text only to curl-like agents
    if "<html" in txt.lower() or "Unknown location" in txt or not txt.strip():
        raise ValueError("no weather")
    return txt.rstrip("\n").split("\n")


def ago(ts):
    s = max(time.time() - ts, 0)
    return f"{int(s // 60)}m" if s < 3600 else f"{int(s // 3600)}h" if s < 86400 else f"{int(s // 86400)}d"


# ---------------------------------------------------------------- tiles
def big_clock(now, cols):
    text = now.strftime("%H:%M")
    rows = ["", "", ""]
    for n, ch in enumerate(text):
        g = glyph(ch)
        gap = " " if n < len(text) - 1 else ""
        for i in range(3):
            rows[i] += g[i] + gap
    sec = f"{now.second:02d}"
    pad = max((cols - (wlen(rows[0]) + 4)) // 2, 0)
    lines = [" " * pad + ACC2 + BOLD + r + RST for r in rows]
    lines[2] += DIM + "  " + sec + RST
    return lines


def month_lines(today):
    """Month grid with today highlighted. Returns list of (already padded) lines."""
    calendar.setfirstweekday(calendar.MONDAY)
    head = today.strftime("%B %Y")
    out = [ACC + BOLD + head.center(20) + RST, DIM + "Mo Tu We Th Fr Sa Su" + RST]
    for week in calendar.monthcalendar(today.year, today.month):
        cells = []
        for i, d in enumerate(week):
            if d == 0:
                cells.append("  ")
            elif d == today.day:
                cells.append(REV + ACC2 + BOLD + f"{d:2d}" + RST)
            elif i >= 5:
                cells.append(ACC + f"{d:2d}" + RST)
            else:
                cells.append(f"{d:2d}")
        out.append(" ".join(cells))
    return out


def tile_cal(feeds, cols, rows, now, tick, scroll_offset=0):
    L = [""]
    L += big_clock(now, cols)
    L.append(center(DIM + now.strftime("%A, %d %B %Y") + RST, cols))
    L.append("")
    mon = month_lines(now.date())
    L += [center(m, cols) for m in mon]
    L.append("")
    hist = feeds["hist"]
    used = len(L)
    room = rows - used - 2
    L.append(center(ACC + BOLD + f"On this day · {now.strftime('%d %B')}" + RST, cols))
    if hist.value:
        # page through the events: each page fills the remaining room
        w = max(cols - 4, 20)
        entries = [wrap(f"{y}  {t}", w, indent="      ", first="") for y, t in hist.value]
        pages, cur, n = [], [], 0
        for e in entries:
            if cur and n + len(e) > max(room, 3):
                pages.append(cur)
                cur, n = [], 0
            cur.append(e)
            n += len(e)
        if cur:
            pages.append(cur)
        idx = int(tick // PAGE) if PAGE > 0 else 0
        idx = (idx + scroll_offset) % len(pages)
        page = pages[idx]
        for e in page:
            year, rest = e[0].split("  ", 1) if "  " in e[0] else ("", e[0])
            L.append("  " + ACC2 + year + RST + "  " + rest)
            L += ["  " + ln for ln in e[1:]]
        L.append(center(SUB + f"{idx + 1}/{len(pages)} (scroll to navigate)" + RST, cols))
    else:
        L.append(center(DIM + ("(offline)" if hist.ok is False else "loading…") + RST, cols))
    return L


def tile_weather(feeds, cols, rows, now, tick, scroll_offset=0):
    L = [""]
    wx, news = feeds["wx"], feeds["news"]
    L.append(center(ACC + BOLD + f"󰖐  Weather · {LOC}" + RST, cols))
    if wx.value:
        L += [" " + ln for ln in wx.value[:7]]
    else:
        L.append(center(DIM + ("(offline)" if wx.ok is False else "loading…") + RST, cols))
    L.append("")
    L.append(center(ACC + BOLD + f"󰎕  News · {QUERY.split(' OR ')[0]}" + RST, cols))
    room = rows - len(L) - 2
    if news.value:
        w = max(cols - 8, 20)
        entries = []
        for when, title, src, tr in news.value:
            lines = wrap(title, w, indent="     ")
            tag = " · translated" if tr else ""
            meta = ("  " + SUB + f"     {src} · {ago(when)} ago{tag}" + RST) if src else ""
            entries.append((lines, meta))
        pages, cur, n = [], [], 0
        for e in entries:
            size = len(e[0]) + (1 if e[1] else 0)
            if cur and n + size > max(room, 3):
                pages.append(cur)
                cur, n = [], 0
            cur.append(e)
            n += size
        if cur:
            pages.append(cur)
        idx = int(tick // PAGE) if PAGE > 0 else 0
        idx = (idx + scroll_offset) % len(pages)
        page = pages[idx]
        for lines, meta in page:
            L.append("  " + ACC2 + "•" + RST + " " + lines[0])
            L += ["  " + ln for ln in lines[1:]]
            if meta:
                L.append(meta)
        L.append(center(SUB + f"{idx + 1}/{len(pages)} (scroll to navigate)" + RST, cols))
    else:
        L.append(center(DIM + ("(offline)" if news.ok is False else "loading…") + RST, cols))
    return L


# ---------------------------------------------------------------- system tile (all-in-one)
SPARK = " ▁▂▃▄▅▆▇█"
GREEN, YELLOW, RED = "\x1b[38;5;10m", "\x1b[38;5;11m", "\x1b[38;5;9m"
SYS_HIST = {"cpu": [], "mem": [], "gpu": [], "net_tx": [], "net_rx": []}


def smi(*args):
    return subprocess.run(["nvidia-smi", *args], capture_output=True, text=True, timeout=5).stdout


def fetch_system():
    try:
        import psutil
    except ImportError:
        return None
    d = {}
    # CPU
    d["cpu_pct"] = psutil.cpu_percent(interval=0.2)
    d["cpu_freq"] = psutil.cpu_freq().current if psutil.cpu_freq() else 0
    d["cpu_count"] = psutil.cpu_count()
    temps = psutil.sensors_temperatures()
    d["cpu_temp"] = temps.get("k10temp", [{}])[0].current if "k10temp" in temps else 0.0
    # Memory
    mem = psutil.virtual_memory()
    d["mem_used"], d["mem_total"], d["mem_pct"] = mem.used, mem.total, mem.percent
    swap = psutil.swap_memory()
    d["swap_used"], d["swap_total"], d["swap_pct"] = swap.used, swap.total, swap.percent
    # GPU (nvidia-smi, optional)
    try:
        q = "name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw"
        f = [x.strip() for x in smi(f"--query-gpu={q}", "--format=csv,noheader,nounits").split("\n")[0].split(",")]
        num = lambda s: float(s) if re.match(r"^[\d.]+$", s) else 0.0
        d["gpu_name"] = f[0].replace("NVIDIA GeForce ", "")
        d["gpu_util"], d["gpu_vram"], d["gpu_vram_total"] = num(f[1]), num(f[2]), num(f[3])
        d["gpu_temp"], d["gpu_power"] = num(f[4]), num(f[5])
    except Exception:
        d["gpu_name"] = None
    # Disks
    parts = [p for p in psutil.disk_partitions() if p.fstype not in ("tmpfs", "devtmpfs", "squashfs", "overlay")]
    d["disks"] = []
    for p in parts:
        try:
            u = psutil.disk_usage(p.mountpoint)
            d["disks"].append((p.mountpoint, u.total, u.used, u.percent))
        except Exception:
            pass
    # Network
    net = psutil.net_io_counters()
    d["net_tx"], d["net_rx"] = net.bytes_sent, net.bytes_recv
    # Power estimate: GPU power (if available) + CPU power (scaled by usage and TDP)
    gpu_w = d.get("gpu_power", 0.0)
    cpu_w = CPU_TDP * (d["cpu_pct"] / 100.0)
    d["power_est"] = gpu_w + cpu_w + 30   # +30W for the rest (mobo, RAM, fans, etc)
    # History
    SYS_HIST["cpu"].append(d["cpu_pct"])
    SYS_HIST["mem"].append(d["mem_pct"])
    if d["gpu_name"]:
        SYS_HIST["gpu"].append(d["gpu_util"])
    for k in SYS_HIST:
        del SYS_HIST[k][:-240]
    return d


def gauge(frac, width, thresholds=(0.6, 0.85)):
    frac = max(0.0, min(frac, 1.0))
    col = GREEN if frac < thresholds[0] else YELLOW if frac < thresholds[1] else RED
    n = int(frac * width + 0.5)
    return col + "█" * n + RST + SUB + "░" * (width - n) + RST


def tile_system(feeds, cols, rows, now, tick):
    s = feeds["sys"].value
    if not s:
        return ["", center(DIM + ("(psutil unavailable)" if feeds["sys"].ok is False else "loading…") + RST, cols)]
    w = max(cols - 32, 16)   # reserve space for label + stats
    L = ["", center(ACC + BOLD + "󰾆  System Monitor" + RST, cols), ""]

    def row(label, frac, text, thr=(0.6, 0.85)):
        L.append(f"  {DIM}{label:<6}{RST} {gauge(frac, w, thr)} {text}")

    # CPU & Memory
    row("CPU", s["cpu_pct"] / 100, f"{s['cpu_pct']:4.1f}% {s['cpu_temp']:3.0f}°C")
    row("Memory", s["mem_pct"] / 100, f"{s['mem_used'] / 1024**3:4.1f}/{s['mem_total'] / 1024**3:3.0f}G")
    if s["swap_total"]:
        row("Swap", s["swap_pct"] / 100, f"{s['swap_used'] / 1024**3:4.1f}/{s['swap_total'] / 1024**3:3.0f}G")
    # GPU
    if s["gpu_name"]:
        row("GPU", s["gpu_util"] / 100, f"{s['gpu_util']:4.1f}% {s['gpu_temp']:3.0f}°C")
        row("VRAM", s["gpu_vram"] / max(s["gpu_vram_total"], 1), f"{s['gpu_vram'] / 1024:3.1f}/{s['gpu_vram_total'] / 1024:2.0f}G")
    # Power estimate (keep it simple)
    cpu_w = s["cpu_pct"] * CPU_TDP / 100
    gpu_w = s.get("gpu_power", 0)
    L.append(f"  {DIM}Power {RST} {ACC2}~{s['power_est']:3.0f}W{RST}  {SUB}CPU {cpu_w:2.0f}W + GPU {gpu_w:2.0f}W + 30W{RST}")
    L.append("")
    # History sparklines
    sw = max(cols - 16, 10)
    for name, key in [("CPU", "cpu"), ("Memory", "mem"), ("GPU", "gpu")]:
        if key == "gpu" and not s["gpu_name"]:
            continue
        hist = SYS_HIST[key][-sw:]
        if hist:
            line = "".join(SPARK[min(int(v / 100 * 8 + 0.5), 8)] for v in hist).rjust(sw)
            L.append("  " + DIM + f"{name:<6}{RST} " + ACC2 + line + RST)
    L.append("")
    # Disks
    L.append("  " + ACC + BOLD + "Disks" + RST)
    for mount, total, used, pct in s["disks"][:4]:
        label = mount if len(mount) <= 8 else mount[:7] + "…"
        dw = max(cols - 28, 10)
        bar = gauge(pct / 100, dw, (0.7, 0.9))
        L.append(f"  {label:<8} {bar} {used / 1024**3:3.0f}/{total / 1024**3:3.0f}G")
    return L


def tile_gpu(feeds, cols, rows, now, tick):
    """Legacy GPU-only tile (now replaced by tile_system). Kept for compatibility."""
    return tile_system(feeds, cols, rows, now, tick)


def main():
    tile = sys.argv[1] if len(sys.argv) > 1 else "cal"
    feeds = {}
    if tile == "gpu":
        feeds["gpu"] = Feed(fetch_system, 1)   # reuse fetch_system for GPU data
    elif tile == "cal":
        feeds["hist"] = Feed(fetch_history, 3600)
    elif tile == "weather":
        feeds["wx"] = Feed(fetch_weather, 900)
        feeds["news"] = Feed(fetch_news, 900)
    elif tile == "system":
        feeds["sys"] = Feed(fetch_system, 1)
    else:
        print(f"unknown tile: {tile}")
        sys.exit(1)
    render_fn = {"cal": tile_cal, "weather": tile_weather, "gpu": tile_gpu, "system": tile_system}[tile]
    
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    sys.stdout.write("\x1b[?25l\x1b[?1049h\x1b[?1000h\x1b[?1006h")
    sys.stdout.flush()
    scroll_offset = 0
    t0, last_key = time.time(), None
    try:
        tty.setcbreak(fd)
        while True:
            # mouse wheel: ESC [ < 64/65 ; x ; y M -> up/down
            r, _, _ = select.select([sys.stdin], [], [], 0.02)
            if r:
                data = os.read(fd, 1024).decode(errors="ignore")
                for m in re.finditer(r"\x1b\[<(64|65);(\d+);(\d+)M", data):
                    scroll_offset += 1 if m.group(1) == "64" else -1
            now = dt.datetime.now()
            cols, rows = shutil.get_terminal_size((60, 30))
            tick = time.time() - t0
            kw = {"scroll_offset": scroll_offset} if tile in ("cal", "weather") else {}
            frame = render_fn(feeds, cols, rows, now, tick, **kw)
            key = (frame, cols, rows)
            if key != last_key:
                last_key = key
                lines = [ln + "\x1b[K" for ln in frame[:rows]]
                sys.stdout.write("\x1b[H" + "\n".join(lines) + "\x1b[J")
                sys.stdout.flush()
    except KeyboardInterrupt:
        pass
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        sys.stdout.write("\x1b[?1000l\x1b[?1006l\x1b[?1049l\x1b[?25h")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
