#!/usr/bin/env python3
"""Tabbed "inbox" tile for the dashboard (kitty window, class dash-inbox).

Tabs (switch with the mouse wheel, click the tab name, or the arrow keys):
  Notifications  recent desktop notifications (from notify-log.py)
  Clipboard      cliphist history; click or Enter copies an entry back
  Ask            chat with a local ollama model (or OpenRouter when configured)
  Journal        warnings and errors from this boot, newest first

Env: INBOX_MODEL          ollama model for the Ask tab (default: llama3.2:1b)
     OPENROUTER_API_KEY   enables OpenRouter as a second model (Ctrl+O cycles)
     INBOX_OR_MODEL       OpenRouter model id (default: meta-llama/llama-3.2-3b-instruct:free)
Keys: ←/→ tabs, ↑/↓ scroll, Enter send / copy, Ctrl+O next model, Ctrl+L clear chat, q quit.
"""
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
import time
import tty
import unicodedata
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inbox_context import build_context  # noqa: E402  (read-only local file context)
from inbox_api import ensure_file, load as load_api  # noqa: E402  (OpenRouter key + model)

HOME = os.path.expanduser("~")
NOTIF_LOG = os.path.join(HOME, ".cache", "inbox", "notifications.jsonl")
OLLAMA = "http://localhost:11434/api/chat"
OPENROUTER = "https://openrouter.ai/api/v1/chat/completions"
LOCAL_MODEL = os.environ.get("INBOX_MODEL", "llama3.2:1b")
# OpenRouter is always listed; without a key, switching to it opens the setup popup.
MODELS = [("ollama", LOCAL_MODEL), ("openrouter", None)]
TABS = ["Notifications", "Clipboard", "Ask", "Journal"]

RST, BOLD, DIM = "\x1b[0m", "\x1b[1m", "\x1b[2m"
ACC, ACC2, SUB = "\x1b[38;5;12m", "\x1b[38;5;13m", "\x1b[38;5;8m"
RED, YEL = "\x1b[38;5;9m", "\x1b[38;5;11m"
REV = "\x1b[7m"
MOUSE = re.compile(r"\x1b\[<(\d+);(\d+);(\d+)([Mm])")
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def cw(c):
    return 0 if unicodedata.combining(c) else (2 if unicodedata.east_asian_width(c) in "WF" else 1)


def wlen(s):
    return sum(cw(c) for c in ANSI.sub("", s))


def clip(s, w):
    out, n = "", 0
    for c in s:
        if n + cw(c) > w:
            break
        out += c
        n += cw(c)
    return out


def ago(ts):
    s = max(time.time() - ts, 0)
    if s < 60:
        return f"{int(s)}s"
    if s < 3600:
        return f"{int(s // 60)}m"
    if s < 86400:
        return f"{int(s // 3600)}h"
    return f"{int(s // 86400)}d"


# ---------------------------------------------------------------- data sources
def load_notifications(limit=60):
    try:
        with open(NOTIF_LOG, encoding="utf-8") as f:
            lines = f.readlines()[-limit:]
    except OSError:
        return []
    out = []
    for ln in lines:
        try:
            out.append(json.loads(ln))
        except ValueError:
            pass
    return out[::-1]                       # newest first


def load_clipboard(limit=30):
    try:
        raw = subprocess.run(["cliphist", "list"], capture_output=True, text=True, timeout=3).stdout
    except Exception:
        return []
    items = []
    for ln in raw.splitlines():
        if "\t" not in ln:
            continue
        cid, text = ln.split("\t", 1)
        if text.startswith("[[ binary data"):
            continue                       # images are not shown
        items.append((cid, text.strip()))
        if len(items) >= limit:
            break
    return items


def copy_clip(cid):
    dec = subprocess.run(["cliphist", "decode", cid], capture_output=True, timeout=3)
    subprocess.run(["wl-copy"], input=dec.stdout, timeout=3)


PRIO = {"0": ("emerg", RED), "1": ("alert", RED), "2": ("crit", RED), "3": ("error", RED),
        "4": ("warn", YEL)}


def load_journal(limit=80):
    try:
        raw = subprocess.run(["journalctl", "-b", "-p", "warning", "-o", "json", "-n", str(limit), "--no-pager"],
                             capture_output=True, text=True, timeout=8).stdout
    except Exception:
        return []
    out = []
    for ln in raw.splitlines():
        try:
            e = json.loads(ln)
        except ValueError:
            continue
        ts = int(e.get("__REALTIME_TIMESTAMP", "0")) / 1e6
        unit = e.get("_SYSTEMD_USER_UNIT") or e.get("SYSLOG_IDENTIFIER") or e.get("_COMM") or "?"
        msg = e.get("MESSAGE", "")
        if isinstance(msg, list):
            msg = bytes(msg).decode(errors="replace")
        out.append({"ts": ts, "prio": str(e.get("PRIORITY", "4")),
                    "unit": unit.replace(".service", ""), "msg": str(msg)})
    return out[::-1]                       # newest first


class Chat:
    """Chat history plus a background request thread, so typing never blocks."""

    def __init__(self):
        self.msgs = []                     # {"role", "content"}
        self.busy = False
        self.error = ""
        self.model_i = 0
        self.show_setup = False            # popup with the API key link is open
        self.lock = threading.Lock()

    @property
    def model(self):
        backend, name = MODELS[self.model_i]
        if backend == "openrouter":
            name = load_api()["model"]
        return backend, name

    def api_ready(self):
        return bool(load_api()["key"])

    def next_model(self):
        """Advance to the next model. Returns 'setup' when the API model needs a key."""
        self.model_i = (self.model_i + 1) % len(MODELS)
        if MODELS[self.model_i][0] == "openrouter" and not self.api_ready():
            ensure_file()
            self.show_setup = True
            return "setup"
        self.show_setup = False
        return "ok"

    def clear(self):
        with self.lock:
            self.msgs, self.error = [], ""

    def send(self, text):
        if self.busy or not text.strip():
            return
        with self.lock:
            self.msgs.append({"role": "user", "content": text.strip()})
            self.msgs.append({"role": "assistant", "content": ""})
            self.busy, self.error = True, ""
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        backend, name = self.model
        system = {"role": "system", "content":
                  "You are a concise assistant for a Linux desktop user (Arch, Hyprland). "
                  "Give short, correct answers. Shell commands must be exact and runnable. "
                  "Check the flags carefully (for example ls -lS sorts by size, largest first). "
                  "If you are not sure, say so instead of guessing."}
        with self.lock:
            past = [m for m in self.msgs[:-1] if m["content"]]   # drop empty placeholders
            history = [system] + past[-8:]                       # last few turns for context
            question = self.msgs[-2]["content"] if len(self.msgs) >= 2 else ""
        # read-only local files the question refers to (see inbox-context.py)
        try:
            ctx = build_context(question)
        except Exception:
            ctx = ""
        if ctx:
            # small models follow a short, direct instruction placed right before the question
            history.insert(1, {"role": "system", "content":
                               "Local files from the user's computer:\n\n" + ctx[:6000] +
                               "\n\nUse only these files to answer. Quote the exact line you rely on. "
                               "If the answer is not in them, say so."})
        try:
            if backend == "ollama":
                body = {"model": name, "stream": True, "messages": history,
                        "options": {"num_predict": 400, "temperature": 0.3}}
                # (kept in sync with the OpenRouter branch below)
                req = urllib.request.Request(OLLAMA, data=json.dumps(body).encode(),
                                             headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=120) as r:
                    for raw in r:
                        ev = json.loads(raw)
                        self._append(ev.get("message", {}).get("content", ""))
                        if ev.get("done"):
                            break
            else:
                key = load_api()["key"]
                if not key:
                    raise RuntimeError("no OpenRouter key yet (Ctrl+O shows how to add one)")
                body = {"model": name, "stream": True, "messages": history}
                req = urllib.request.Request(OPENROUTER, data=json.dumps(body).encode(), headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer " + key})
                with urllib.request.urlopen(req, timeout=120) as r:
                    for raw in r:
                        line = raw.decode("utf-8", "ignore").strip()
                        if not line.startswith("data:") or line.endswith("[DONE]"):
                            continue
                        ev = json.loads(line[5:])
                        self._append(ev["choices"][0].get("delta", {}).get("content", "") or "")
        except Exception as e:
            with self.lock:
                self.error = f"{backend} error: {str(e)[:110]}"
        finally:
            with self.lock:
                self.busy = False

    def _append(self, piece):
        with self.lock:
            if self.msgs:
                self.msgs[-1]["content"] += piece


# ---------------------------------------------------------------- rendering
class State:
    def __init__(self):
        self.tab = 0
        self.scroll = {t: 0 for t in range(len(TABS))}
        self.input = ""
        self.chat = Chat()
        self.cache = {}                    # tab -> (ts, data)
        self.hits = []                     # (row, col_lo, col_hi, action)
        self.clip_sel = 0
        self.wrap_cache = {}               # chat message -> wrapped lines


def fresh(state, name, loader, ttl):
    ts, data = state.cache.get(name, (0, None))
    if time.time() - ts > ttl or data is None:
        data = loader()
        state.cache[name] = (time.time(), data)
    return state.cache[name][1]


def tab_bar(state, cols):
    parts, col, hits = [], 1, []
    for i, name in enumerate(TABS):
        label = f" {name} "
        style = (BOLD + ACC2 + REV) if i == state.tab else (ACC if i != 3 else YEL)
        parts.append(style + label + RST)
        hits.append((col, col + len(label) - 1, i))
        col += len(label) + 1
    line = " ".join(parts)
    return line, hits


def wrap(text, width, indent=""):
    return textwrap.wrap(text, max(width, 10), subsequent_indent=indent) or [""]


def body_notifications(state, cols, h):
    items = fresh(state, "notif", load_notifications, ttl=2)
    if not items:
        return [f"{DIM}  No notifications yet. They appear here as they arrive.{RST}"]
    lines, w = [], max(cols - 4, 20)
    for n in items:
        head = f"  {ACC2}{clip(n.get('app', ''), 18)}{RST} {SUB}{ago(n.get('t', 0))} ago{RST}"
        lines.append(head)
        lines.append(f"  {BOLD}{clip(n.get('summary', ''), w)}{RST}")
        for ln in wrap(n.get("body", ""), w, indent="  "):
            if ln:
                lines.append(f"  {DIM}{ln}{RST}")
        lines.append("")
    return lines


def body_clipboard(state, cols, h):
    items = fresh(state, "clip", load_clipboard, ttl=3)
    if not items:
        return [f"{DIM}  No text entries in clipboard history yet.{RST}", f"{DIM}  (images are hidden; copy some text to see it here){RST}"]
    w = max(cols - 8, 20)
    lines = []
    for i, (cid, text) in enumerate(items):
        one = " ".join(text.split())
        mark = REV if i == state.clip_sel else ""
        lines.append(f"  {mark}{ACC}{i + 1:>2}{RST} {mark}{clip(one, w)}{RST}")
        state.hits.append(("clip", i, cid))
    return lines


def osc8(url, text):
    """Clickable hyperlink (OSC 8), supported by kitty."""
    return f"\x1b]8;;{url}\x1b\\{text}\x1b]8;;\x1b\\"


def setup_popup(cols):
    """Panel shown when switching to OpenRouter without a key. Returns its lines."""
    path = ensure_file()
    link = osc8("file://" + path, path.replace(HOME, "~"))
    w = min(cols - 4, 60)
    inner = [
        f"{BOLD}{ACC2}OpenRouter needs an API key{RST}",
        "",
        f"1. Get a key at {osc8('https://openrouter.ai/keys', 'openrouter.ai/keys')}",
        f"2. Open the settings file:",
        f"   {link}",
        "   (click it, or open it in nvim)",
        "3. Paste the key after OPENROUTER_API_KEY= and save",
        "",
        f"{DIM}Esc closes this · Ctrl+O goes back to the local model{RST}",
    ]
    box = ["╭" + "─" * (w - 2) + "╮"]
    link_row = None
    for ln in inner:
        # strip colour codes AND hyperlink (OSC 8) wrappers before measuring the visible width
        bare = re.sub(r"\x1b\]8;;[^\x1b]*\x1b\\", "", ANSI.sub("", ln))
        pad = max(w - 4 - wlen(bare), 0)
        if link in ln:
            link_row = len(box)            # index inside the popup
        box.append("│ " + ln + " " * pad + " │")
    box.append("╰" + "─" * (w - 2) + "╯")
    STATE_LINK_ROW[0] = link_row
    return [" " * max((cols - w) // 2, 0) + ln for ln in box]


STATE_LINK_ROW = [None]


def body_ask(state, cols, h):
    if state.chat.show_setup:
        return setup_popup(cols)
    chat = state.chat
    w = max(cols - 4, 20)
    lines = []
    if not chat.msgs:
        lines.append(f"{DIM}  Ask anything about your system or commands.{RST}")
        lines.append(f"{DIM}  Try: \"what is in my hyprland config?\"{RST}")
        lines.append(f"{DIM}  Model: {chat.model[1]} ({chat.model[0]})  ·  Ctrl+O switches{RST}")
    # finished messages are wrapped once and cached; only the streaming one is re-wrapped
    cache = state.wrap_cache
    for idx, m in enumerate(chat.msgs):
        streaming = chat.busy and idx == len(chat.msgs) - 1
        key = (idx, len(m["content"]), w, streaming)
        if key not in cache:
            if m["role"] == "user":
                body = [f"  {ACC}you{RST}"] + [f"  {ln}" for ln in wrap(m["content"], w)]
            else:
                head = f"  {ACC2}ai{RST}" + (f" {DIM}…{RST}" if streaming else "")
                text = m["content"] or ""
                body = [head] + ([f"  {ln}" for ln in wrap(text, w)] if text else [])
            cache[key] = body + [""]
            if len(cache) > 400:
                cache.clear()
        lines += cache[key]
    if chat.error:
        lines.append(f"  {RED}{clip(chat.error, w)}{RST}")
    return lines


def body_journal(state, cols, h):
    items = fresh(state, "journal", load_journal, ttl=10)
    if not items:
        return [f"{GRN_OK}  No warnings or errors this boot.{RST}"]
    w = max(cols - 22, 20)
    lines = []
    for e in items:
        label, col = PRIO.get(e["prio"], ("info", DIM))
        when = time.strftime("%H:%M", time.localtime(e["ts"]))
        lines.append(f"  {DIM}{when}{RST} {col}{label:<5}{RST} {ACC}{clip(e['unit'], 14):<14}{RST}")
        for ln in wrap(e["msg"], cols - 6, indent="        "):
            lines.append(f"      {ln}")
    return lines


GRN_OK = "\x1b[38;5;10m"
BODIES = [body_notifications, body_clipboard, body_ask, body_journal]


def render(state, cols, rows):
    L = []
    state.hits = []
    bar, hits = tab_bar(state, cols)
    state.tab_hits = hits
    L.append(" " + bar)
    L.append(DIM + "─" * cols + RST)

    # input line lives on the Ask tab only
    input_h = 2 if state.tab == 2 else 0
    body_h = rows - len(L) - input_h - 1
    lines = BODIES[state.tab](state, cols, body_h)
    top = state.scroll[state.tab]
    top = max(0, min(top, max(len(lines) - body_h, 0)))
    state.scroll[state.tab] = top
    view = lines[top:top + body_h]
    L += view + [""] * max(body_h - len(view), 0)

    footer = {0: "↑↓ scroll · ←→ tabs", 1: "Enter copy · ↑↓ select", 2: "Enter send · Ctrl+L clear",
              3: "↑↓ scroll · ←→ tabs"}[state.tab]
    if state.tab == 2:
        L.append(DIM + "─" * cols + RST)
        prompt = "› " + state.chat.model[1][:20] + " "
        room = max(cols - wlen(prompt) - 1, 5)
        shown = state.input[-room:]
        L.append(f"{ACC2}{prompt}{RST}{shown}{REV} {RST}")
    L.append(f"{SUB}{clip(footer, cols)}{RST}")
    return "\x1b[H" + "\n".join(ln + "\x1b[K" for ln in L[:rows]) + "\x1b[J"


# ---------------------------------------------------------------- input
SETTINGS_WORKSPACE = os.environ.get("INBOX_SETTINGS_WS", "1")


def open_settings_in_nvim():
    """Opens the settings file in nvim on a normal workspace (not the dashboard).

    The window is launched directly on the target workspace with a `workspace` rule
    so it appears in front, and that workspace is brought into view.
    """
    path = ensure_file()
    cmd = f"kitty --class inbox-settings nvim {path}"
    # Same call shape that works from the shell: exec_cmd with a workspace option
    subprocess.run(["hyprctl", "dispatch",
                    f'hl.dsp.exec_cmd("{cmd}", {{ workspace = "{SETTINGS_WORKSPACE}" }})'],
                   capture_output=True, timeout=3)
    # bring that workspace into view so the editor is visible
    subprocess.run(["hyprctl", "dispatch",
                    f'hl.dsp.focus({{ workspace = {SETTINGS_WORKSPACE} }})'],
                   capture_output=True, timeout=3)


def handle_click(state, x, y):
    # tab bar is row 1 (1-based)
    if y == 1:
        for lo, hi, i in getattr(state, "tab_hits", []):
            if lo <= x <= hi:
                state.tab = i
        return
    if state.tab == 2 and state.chat.show_setup:
        # only the file-path line of the popup is clickable (it's the 5th line of the body)
        # body starts on screen row 3 (1-based: tab bar, rule, then content)
        if STATE_LINK_ROW[0] is not None and y == 3 + STATE_LINK_ROW[0]:
            open_settings_in_nvim()
        return
    if state.tab == 1:
        row = y - 3                        # first clipboard line is row 3
        items = state.cache.get("clip", (0, []))[1] or []
        if 0 <= row < len(items):
            state.clip_sel = row
            copy_clip(items[row][0])


def handle_key(state, k):
    """Returns False to quit."""
    if k == "\x03":                        # Ctrl+C (raw mode: not a signal any more)
        return False
    if k == "q" and state.tab != 2:
        return False
    if k == "\x09":                        # Tab: next tab (works everywhere)
        state.tab = (state.tab + 1) % len(TABS)
        return True
    if k == "\x1b[C":                      # right arrow
        state.tab = (state.tab + 1) % len(TABS)
    elif k == "\x1b[D":                    # left arrow
        state.tab = (state.tab - 1) % len(TABS)
    elif k == "\x1b[A":                    # up
        if state.tab == 1:
            state.clip_sel = max(state.clip_sel - 1, 0)
        state.scroll[state.tab] = max(state.scroll[state.tab] - 1, 0)
    elif k == "\x1b[B":                    # down
        if state.tab == 1:
            state.clip_sel += 1
        state.scroll[state.tab] += 1
    elif k == "\x0f":                      # Ctrl+O: next model (opens the setup popup for OpenRouter)
        state.chat.next_model()
    elif k == "\x1b" and state.chat.show_setup:
        state.chat.show_setup = False      # Esc closes the popup
    elif k == "\x0c":                      # Ctrl+L: clear chat
        state.chat.clear()
    elif state.tab == 1 and k in ("\r", "\n"):
        items = state.cache.get("clip", (0, []))[1] or []
        if 0 <= state.clip_sel < len(items):
            copy_clip(items[state.clip_sel][0])
    elif state.tab == 2:
        if k in ("\r", "\n"):
            state.chat.send(state.input)
            state.input = ""
        elif k in ("\x7f", "\b"):
            state.input = state.input[:-1]
        elif k.isprintable() and len(k) == 1:
            state.input += k
    return True


KEY_RE = re.compile(r"\x1b\[<(\d+);(\d+);(\d+)([Mm])|\x1b\[([ABCD])|\x1b.|(.)", re.S)


def tokenize(data):
    """Splits raw terminal input into ('mouse', b, x, y, M) / ('key', str) events."""
    events = []
    for m in KEY_RE.finditer(data):
        if m.group(1) is not None:
            events.append(("mouse", int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4) == "M"))
        elif m.group(5):
            events.append(("key", "\x1b[" + m.group(5)))
        elif m.group(6) is not None:
            events.append(("key", m.group(6)))
    return events


def redraw(out, state):
    cols, rows = shutil.get_terminal_size((60, 30))
    out.write(render(state, cols, rows))
    out.flush()


def main():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    state = State()
    out = sys.stdout
    out.write("\x1b[?25l\x1b[?1049h\x1b[?1000h\x1b[?1006h")
    out.flush()
    try:
        # raw mode: the tty driver must not eat Ctrl+O / Ctrl+L / Ctrl+C-style keys
        tty.setraw(fd)
        # setraw also disables output processing, so "\n" stops returning to column 1.
        # Turn it back on: input stays raw (keys like Ctrl+O reach us), output renders normally.
        attrs = termios.tcgetattr(fd)
        attrs[1] |= termios.OPOST | termios.ONLCR
        termios.tcsetattr(fd, termios.TCSADRAIN, attrs)
        redraw(out, state)
        last_busy, last_draw = False, 0.0
        while True:
            ready, _, _ = select.select([fd], [], [], 0.1)
            dirty = False
            if ready:
                data = os.read(fd, 4096).decode(errors="ignore")
                for ev in tokenize(data):
                    if ev[0] == "key":
                        if not handle_key(state, ev[1]):
                            return
                    else:
                        _, b, x, y, press = ev
                        if press and b == 64:
                            state.scroll[state.tab] = max(state.scroll[state.tab] - 3, 0)
                        elif press and b == 65:
                            state.scroll[state.tab] += 3
                        elif press and b == 0:
                            handle_click(state, x, y)
                dirty = True
            # redraw while the model is streaming, but at most ~15 fps
            now = time.monotonic()
            if state.chat.busy != last_busy:
                last_busy, dirty = state.chat.busy, True
            if state.chat.busy and now - last_draw >= 0.066:
                dirty = True
            if dirty and now - last_draw >= 0.03:
                last_draw = now
                redraw(out, state)
    except KeyboardInterrupt:
        pass
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        out.write("\x1b[?1000l\x1b[?1006l\x1b[?1049l\x1b[?25h")
        out.flush()


if __name__ == "__main__":
    main()
