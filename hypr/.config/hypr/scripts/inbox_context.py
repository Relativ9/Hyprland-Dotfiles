"""Read-only local context for the Ask tab.

A 1B local model can't drive tool calls reliably, so the tile decides what to
read and puts it into the prompt. Everything here is read-only and limited to
the home directory. Secrets and binaries are skipped.

  build_context(question) -> str   (empty if nothing relevant was found)
"""
import fnmatch
import os
import re

HOME = os.path.expanduser("~")
MAX_FILE = 4000          # bytes per file included in the prompt
MAX_FILES = 6            # files per question
MAX_TREE = 120           # lines in a directory tree
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".cache", ".local", "Cursor", ".mozilla",
             ".zen", ".steam", ".npm", ".rustup", ".cargo", "lazy", ".venv", "venv"}
SKIP_FILES = ("*.env", "*.key", "*.pem", "*secret*", "*token*", "*password*", "*.kdbx",
              "*.png", "*.jpg", "*.jpeg", "*.gif", "*.webp", "*.mp4", "*.mkv", "*.zip",
              "*.tar*", "*.pdf", "*.oga", "*.mp3", "*.ipynb", "*.kra", "*.so*", "*.bin")
TEXT_EXT = {".lua", ".conf", ".sh", ".py", ".md", ".txt", ".json", ".jsonc", ".toml", ".yaml", ".yml",
            ".css", ".rasi", ".ini", ".zsh", ".bash", ".vim", ".js", ".ts", ".rs", ".c", ".h", ".cpp",
            ".java", ".html", ".xml", ".csv", ".log", ""}
ALIASES = {"hyprland": ".config/hypr", "hypr": ".config/hypr", "waybar": ".config/waybar",
           "swaync": ".config/swaync", "notifications": ".config/swaync", "rofi": ".config/rofi",
           "kitty": ".config/kitty", "nvim": ".config/nvim", "neovim": ".config/nvim",
           "dotfiles": "dotfiles", "themes": ".config/themes", "wallpapers": "Pictures/wallpapers",
           "pictures": "Pictures", "documents": "Documents", "downloads": "Downloads",
           "desktop": "Desktop", "music": "Music", "obsidian": "Documents"}
PATH_RE = re.compile(r"(~?/[\w./-]+|[\w.-]+/[\w./-]+|[\w.-]+\.(?:lua|conf|sh|py|md|json|jsonc|toml|css|rasi|ini|txt|yaml|yml))")
TREE_WORDS = re.compile(r"\b(my (config|setup|dotfiles|files|folder|system)|what('s| is) (in|on) my|list (my )?(files|folders)|project structure|where is|directory|tree)\b", re.I)


def _safe(path):
    real = os.path.realpath(os.path.expanduser(path))
    return real if real == HOME or real.startswith(HOME + os.sep) else None


def _skip_file(name):
    return any(fnmatch.fnmatch(name.lower(), p) for p in SKIP_FILES)


def _tree(root, depth=3):
    lines, count = [], 0
    base = root.rstrip(os.sep)
    for dirpath, dirnames, filenames in os.walk(base):
        rel = os.path.relpath(dirpath, base)
        level = 0 if rel == "." else rel.count(os.sep) + 1
        if level >= depth:
            dirnames[:] = []
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("."))
        indent = "  " * level
        if rel != ".":
            lines.append(f"{indent}{os.path.basename(dirpath)}/")
            count += 1
        for f in sorted(filenames):
            if _skip_file(f) or f.startswith("."):
                continue
            lines.append(f"{indent}  {f}")
            count += 1
            if count >= MAX_TREE:
                lines.append("  ...")
                return lines
    return lines


def _read(path):
    try:
        if os.path.getsize(path) > 200_000:
            return None
        if os.path.splitext(path)[1].lower() not in TEXT_EXT:
            return None
        with open(path, encoding="utf-8", errors="strict") as f:
            return f.read(MAX_FILE)
    except (OSError, UnicodeDecodeError):
        return None


def build_context(question):
    parts, files = [], 0
    mentioned = set()

    for token in PATH_RE.findall(question):
        mentioned.add(token)
    for word, rel in ALIASES.items():
        if re.search(rf"\b{word}\b", question, re.I):
            mentioned.add(os.path.join(HOME, rel))

    # explicit paths first (files before folders), then topic aliases
    explicit = [t for t in mentioned if t not in {os.path.join(HOME, v) for v in ALIASES.values()}]
    aliased = [t for t in mentioned if t not in explicit]
    for token in sorted(explicit, key=lambda t: 0 if t.endswith(tuple(TEXT_EXT - {""})) else 1) + \
            sorted(aliased):
        cand = token if token.startswith(("/", "~")) else os.path.join(HOME, token)
        path = _safe(cand)
        if not path or not os.path.exists(path):
            continue
        if os.path.isfile(path):
            if _skip_file(os.path.basename(path)):
                continue
            text = _read(path)
            if text is not None and files < MAX_FILES:
                files += 1
                parts.append(f"File {path}:\n```\n{text}\n```")
        elif os.path.isdir(path):
            parts.append(f"Directory {path}:\n" + "\n".join(_tree(path, depth=2)))

    if TREE_WORDS.search(question):
        for root in (os.path.join(HOME, "dotfiles"), os.path.join(HOME, ".config")):
            if os.path.isdir(root):
                parts.append(f"Directory tree {root}:\n" + "\n".join(_tree(root, depth=3)))
    return "\n\n".join(parts)
