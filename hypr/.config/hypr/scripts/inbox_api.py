"""API model settings for the inbox Ask tab (OpenRouter).

The key and model live in ~/.config/inbox/api.env, which is created with
0600 permissions and is never stored in the dotfiles repo. Read on every
request, so edits apply without restarting the tile.

    OPENROUTER_API_KEY=sk-or-...
    OPENROUTER_MODEL=meta-llama/llama-3.2-3b-instruct:free
"""
import os

DIR = os.path.expanduser("~/.config/inbox")
ENV = os.path.join(DIR, "api.env")
TEMPLATE = """# OpenRouter settings for the inbox Ask tab (Ctrl+O switches to this model).
# Get a key at https://openrouter.ai/keys and pick a model at https://openrouter.ai/models
OPENROUTER_API_KEY=
OPENROUTER_MODEL=meta-llama/llama-3.2-3b-instruct:free
"""


def ensure_file():
    """Create the settings file (with a template) if missing. Returns its path."""
    os.makedirs(DIR, mode=0o700, exist_ok=True)
    if not os.path.exists(ENV):
        fd = os.open(ENV, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(TEMPLATE)
    os.chmod(ENV, 0o600)
    return ENV


def load():
    """Returns {'key': str, 'model': str} from the settings file (env vars override)."""
    vals = {}
    try:
        with open(ENV, encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if ln and not ln.startswith("#") and "=" in ln:
                    k, v = ln.split("=", 1)
                    vals[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    key = os.environ.get("OPENROUTER_API_KEY") or vals.get("OPENROUTER_API_KEY", "")
    model = os.environ.get("OPENROUTER_MODEL") or vals.get("OPENROUTER_MODEL", "")
    return {"key": key, "model": model or "meta-llama/llama-3.2-3b-instruct:free"}
