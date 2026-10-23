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

HOME = os.path.expanduser("~")
NOTIF_LOG = os.path.join(HOME, ".cache", "inbox", "notifications.jsonl")
OLLAMA = "http://localhost:11434/api/chat"
OPENROUTER = "https://openrouter.ai/api/v1/chat/completions"
MODELS = [("ollama", os.environ.get("INBOX_MODEL", "llama3.2:1b"))]
if os.environ.get("OPENROUTER_API_KEY"):
    MODELS.append(("openrouter", os.environ.get("INBOX_OR_MODEL", "meta-llama/llama-3.2-3b-instruct:free")))
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
        self.lock = threading.Lock()

    @property
    def model(self):
        return MODELS[self.model_i]

    def next_model(self):
        self.model_i = (self.model_i + 1) % len(MODELS)

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
            history = [system] + self.msgs[:-1][-8:]      # last few turns for context
        try:
            if backend == "ollama":
                body = {"model": name, "stream": True, "messages": history,
                        "options": {"num_predict": 400, "temperature": 0.3}}
                req = urllib.request.Request(OLLAMA, data=json.dumps(body).encode(),
                                             headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=120) as r:
                    for raw in r:
                        ev = json.loads(raw)
                        self._append(ev.get("message", {}).get("content", ""))
                        if ev.get("done"):
                            break
            else:
                body = {"model": name, "stream": True, "messages": history}
                req = urllib.request.Request(OPENROUTER, data=json.dumps(body).encode(), headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer " + os.environ["OPENROUTER_API_KEY"]})
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


def body_ask(state, cols, h):
    chat = state.chat
    w = max(cols - 4, 20)
    lines = []
    if not chat.msgs:
        lines.append(f"{DIM}  Ask anything about your system or commands.{RST}")
        lines.append(f"{DIM}  Model: {chat.model[1]} ({chat.model[0]})  ·  Ctrl+O switches{RST}")
    for m in chat.msgs:
        if m["role"] == "user":
            lines.append(f"  {ACC}you{RST}")
            lines += [f"  {ln}" for ln in wrap(m["content"], w)]
        else:
            lines.append(f"  {ACC2}ai{RST}" + (f" {DIM}…{RST}" if chat.busy and m is chat.msgs[-1] else ""))
            text = m["content"] or ""
            lines += [f"  {ln}" for ln in wrap(text, w)] if text else [""]
        lines.append("")
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
def handle_click(state, x, y):
    # tab bar is row 1 (1-based)
    if y == 1:
        for lo, hi, i in getattr(state, "tab_hits", []):
            if lo <= x <= hi:
                state.tab = i
        return
    if state.tab == 1:
        row = y - 3                        # first clipboard line is row 3
        items = state.cache.get("clip", (0, []))[1] or []
        if 0 <= row < len(items):
            state.clip_sel = row
            copy_clip(items[row][0])


def handle_key(state, k):
    """Returns False to quit."""
    if k in ("q",) and state.tab != 2:
        return False
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
    elif k == "\x0f":                      # Ctrl+O: next model
        state.chat.next_model()
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


def main():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    state = State()
    out = sys.stdout
    out.write("\x1b[?25l\x1b[?1049h\x1b[?1000h\x1b[?1006h")
    out.flush()
    try:
        tty.setcbreak(fd)
        last = 0.0
        while True:
            ready, _, _ = select.select([fd], [], [], 0.05)
            if ready:
                data = os.read(fd, 1024).decode(errors="ignore")
                pos = 0
                # split out mouse reports, then process the remaining keys
                for m in MOUSE.finditer(data):
                    for ch in data[pos:m.start()]:
                        if not handle_key(state, ch):
                            return
                    if m.group(4) == "M":
                        b = int(m.group(1))
                        if b == 64:
                            state.scroll[state.tab] = max(state.scroll[state.tab] - 3, 0)
                        elif b == 65:
                            state.scroll[state.tab] += 3
                        elif b == 0:
                            handle_click(state, int(m.group(2)), int(m.group(3)))
                    pos = m.end()
                tail = data[pos:]
                i = 0
                while i < len(tail):
                    if tail.startswith("\x1b[", i) and i + 2 < len(tail) and tail[i + 2] in "ABCD":
                        if not handle_key(state, tail[i:i + 3]):
                            return
                        i += 3
                        continue
                    if not handle_key(state, tail[i]):
                        return
                    i += 1
            now = time.monotonic()
            if now - last >= 0.2:
                last = now
                cols, rows = shutil.get_terminal_size((60, 30))
                out.write(render(state, cols, rows))
                out.flush()
    except KeyboardInterrupt:
        pass
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        out.write("\x1b[?1000l\x1b[?1006l\x1b[?1049l\x1b[?25h")
        out.flush()


if __name__ == "__main__":
    main()
