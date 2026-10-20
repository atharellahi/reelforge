"""Where things live, and how to find the tools.

Two kinds of state, kept deliberately apart:

  ~/.reelforge/            PERSONAL. API keys, OAuth tokens, cloned repos.
                           Never inside a project, never committed.

  <repo>/.reelforge/       SHARED. Detected features, brand, tuning memory,
                           rendered output. Lives in the project so the whole
                           team sees the same facts and the same corrections
                           through git.
"""
import glob
import json
import os
import platform
import shutil
import sys

HOME = os.path.expanduser(os.environ.get("REELFORGE_HOME", "~/.reelforge"))
CONFIG = os.path.join(HOME, "config.json")

DEFAULTS = {
    "gemini_api_key": "",
    "gemini_mode": "auto",          # auto | vertex | studio
    "gemini_text_model": "gemini-2.5-flash",
    "gemini_image_model": "gemini-2.5-flash-image",
    "gemini_tts_voice": "Sulafat",
    "edge_voice": "en-US-AvaMultilingualNeural",
    "veo_api_key": "",
    "veo_project": "",
    "veo_location": "us-central1",
    "veo_model": "veo-3.1-lite-generate-001",
    "youtube_client_secret": "",    # path to the OAuth desktop client json
    "instagram_access_token": "",
    "instagram_user_id": "",
    "s3_bucket": "", "s3_region": "us-east-1",
    "s3_access_key_id": "", "s3_secret_access_key": "", "s3_prefix": "reelforge",
    "public_base_url": "",          # if renders are hosted somewhere already
    "chrome_path": "",
    "ffmpeg_path": "",
    "ui_port": 7733,
}


def ensure_home():
    os.makedirs(HOME, exist_ok=True)
    os.makedirs(os.path.join(HOME, "youtube"), exist_ok=True)
    os.makedirs(os.path.join(HOME, "repos"), exist_ok=True)


def load():
    ensure_home()
    cfg = dict(DEFAULTS)
    if os.path.exists(CONFIG):
        try:
            with open(CONFIG, encoding="utf-8") as fh:
                cfg.update(json.load(fh))
        except Exception as e:  # a corrupt config should not brick the tool
            print(f"warning: could not read {CONFIG}: {e}", file=sys.stderr)
    # environment wins, so CI and shared machines need no file at all
    for k in DEFAULTS:
        env = os.environ.get("REELFORGE_" + k.upper())
        if env:
            cfg[k] = env
    if not cfg["gemini_api_key"]:
        cfg["gemini_api_key"] = os.environ.get("GEMINI_API_KEY", "")
    return cfg


def save(cfg):
    ensure_home()
    keep = {k: v for k, v in cfg.items() if k in DEFAULTS and v != DEFAULTS[k]}
    with open(CONFIG, "w", encoding="utf-8") as fh:
        json.dump(keep, fh, indent=1)
    try:
        os.chmod(CONFIG, 0o600)
    except Exception:
        pass


def set_value(key, value):
    if key not in DEFAULTS:
        raise KeyError(f"unknown setting {key!r}. Known: {', '.join(sorted(DEFAULTS))}")
    cfg = load()
    if isinstance(DEFAULTS[key], int) and not isinstance(DEFAULTS[key], bool):
        value = int(value)
    cfg[key] = value
    save(cfg)
    return cfg


def masked(cfg):
    """Config safe to print or send to the local UI."""
    out = {}
    for k, v in cfg.items():
        if isinstance(v, str) and v and any(s in k for s in ("key", "secret", "token")):
            out[k] = v[:4] + "…" + v[-3:] if len(v) > 10 else "•••"
        else:
            out[k] = v
    return out


# ------------------------------------------------------------------ tools

def find_ffmpeg(cfg=None):
    cfg = cfg or load()
    if cfg.get("ffmpeg_path") and os.path.exists(cfg["ffmpeg_path"]):
        return cfg["ffmpeg_path"]
    p = shutil.which("ffmpeg")
    if p:
        return p
    raise SystemExit(
        "ffmpeg not found. Install it (winget install ffmpeg / brew install ffmpeg / "
        "apt install ffmpeg) or set chrome via: reelforge config set ffmpeg_path <path>")


def find_chrome(cfg=None):
    cfg = cfg or load()
    cands = [cfg.get("chrome_path"), os.environ.get("CHROME_PATH")]
    sysname = platform.system()
    if sysname == "Windows":
        cands += [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ]
        cands += glob.glob(os.path.expandvars(
            r"%LOCALAPPDATA%\ms-playwright\chromium*\chrome-win*\chrome.exe"))
        cands += glob.glob(os.path.expandvars(
            r"%LOCALAPPDATA%\ms-playwright\chromium_headless_shell*\chrome-headless-shell-win64\chrome-headless-shell.exe"))
    elif sysname == "Darwin":
        cands += [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        ]
        cands += glob.glob(os.path.expanduser(
            "~/Library/Caches/ms-playwright/chromium*/chrome-mac*/Chromium.app/Contents/MacOS/Chromium"))
    else:
        for n in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge"):
            p = shutil.which(n)
            if p:
                cands.append(p)
        cands += glob.glob(os.path.expanduser("~/.cache/ms-playwright/chromium*/chrome-linux/chrome"))
    for c in cands:
        if c and os.path.exists(c):
            return c
    raise SystemExit(
        "No Chrome/Chromium/Edge found. Install Chrome, or point at one with:\n"
        "  reelforge config set chrome_path <path-to-chrome>")


# --------------------------------------------------------------- project

def project_dir(repo):
    d = os.path.join(os.path.abspath(repo), ".reelforge")
    for sub in ("out", "assets", "shots", "looks"):
        os.makedirs(os.path.join(d, sub), exist_ok=True)
    gi = os.path.join(d, ".gitignore")
    if not os.path.exists(gi):
        # renders are large and regenerable; everything else is worth sharing
        with open(gi, "w", encoding="utf-8") as fh:
            fh.write("out/\nshots/\n")
    return d


def read_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1, ensure_ascii=False)
