#!/usr/bin/env python3
"""Logs desktop notifications to ~/.cache/inbox/notifications.jsonl.

Listens on the session bus (dbus-monitor) for org.freedesktop.Notifications.Notify
calls. It only observes: swaync still shows the notifications as before.
Started from hyprland.lua autostart.
"""
import json
import os
import subprocess
import time

DIR = os.path.expanduser("~/.cache/inbox")
LOG = os.path.join(DIR, "notifications.jsonl")


def unquote(s):
    s = s.rstrip("\n")
    return s[1:-1] if len(s) >= 2 and s[0] == '"' and s[-1] == '"' else s


def main():
    os.makedirs(DIR, exist_ok=True)
    proc = subprocess.Popen(
        ["dbus-monitor", "--session", "interface=org.freedesktop.Notifications,member=Notify"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
    collecting, strs = False, []
    with open(LOG, "a", encoding="utf-8", buffering=1) as out:
        for line in proc.stdout:
            if "method call" in line and "member=Notify" in line:
                collecting, strs = True, []
                continue
            if not collecting:
                continue
            if line.startswith("   string "):
                strs.append(unquote(line[len("   string "):]))
            # Notify args: app_name, replaces_id, app_icon, summary, body, ...
            # string args in order: app_name, app_icon, summary, body
            if len(strs) >= 4:
                collecting = False
                rec = {"t": time.time(), "app": strs[0], "summary": strs[2], "body": strs[3]}
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
