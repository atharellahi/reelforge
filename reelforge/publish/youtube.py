"""YouTube, with as many accounts and channels as the person has.

Each OAuth consent is stored under a LABEL in ~/.reelforge/youtube/<label>.json.
Google lets you pick which identity - personal or a Brand Account channel - at
the consent screen, so "one more channel" is simply "one more label".

Uploads default to PRIVATE. Nothing goes public without a deliberate flip.
"""
import json
import os
import time

from .. import config as C

SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube.readonly"]
DIR = os.path.join(C.HOME, "youtube")


def secret_path():
    cfg = C.load()
    for p in (cfg.get("youtube_client_secret"), os.path.join(DIR, "client_secret.json")):
        if p and os.path.exists(p):
            return p
    raise SystemExit(
        "No YouTube OAuth client. In Google Cloud Console create an OAuth client of type "
        "'Desktop app' with the YouTube Data API enabled, download the JSON, then:\n"
        f"  reelforge config set youtube_client_secret <path>\n  (or save it as {os.path.join(DIR, 'client_secret.json')})")


def _token_path(label):
    return os.path.join(DIR, f"{label}.json")


def _info_path(label):
    return os.path.join(DIR, f"{label}.info.json")


def _creds(label, interactive=True):
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    os.makedirs(DIR, exist_ok=True)
    tp = _token_path(label)
    creds = Credentials.from_authorized_user_file(tp, SCOPES) if os.path.exists(tp) else None
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(tp, "w") as fh:
            fh.write(creds.to_json())
    if not creds or not creds.valid:
        if not interactive:
            raise SystemExit(f"account {label!r} needs (re)authorising: reelforge accounts add --label {label}")
        from google_auth_oauthlib.flow import InstalledAppFlow
        flow = InstalledAppFlow.from_client_secrets_file(secret_path(), SCOPES)
        creds = flow.run_local_server(port=0, prompt="consent")
        with open(tp, "w") as fh:
            fh.write(creds.to_json())
    return creds


def service(label):
    from googleapiclient.discovery import build
    return build("youtube", "v3", credentials=_creds(label, interactive=False), cache_discovery=False)


def _describe(label):
    yt = service(label)
    r = yt.channels().list(part="snippet,statistics", mine=True).execute()
    items = r.get("items") or []
    if not items:
        return {"label": label, "channel_id": "", "channel_title": "(no channel on this account)", "videos": 0}
    c = items[0]
    info = {"label": label, "channel_id": c["id"], "channel_title": c["snippet"]["title"],
            "videos": int(c["statistics"].get("videoCount", 0)), "checked": time.strftime("%Y-%m-%d")}
    C.write_json(_info_path(label), info)
    return info


def add_account(label):
    """Runs the browser consent on THIS machine and remembers it under label."""
    _creds(label, interactive=True)
    return _describe(label)


def import_token(path, label):
    """Bring an existing token.json (e.g. from another tool) in under a label."""
    os.makedirs(DIR, exist_ok=True)
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    with open(_token_path(label), "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    return _describe(label)


def accounts(refresh=False):
    out = []
    if not os.path.isdir(DIR):
        return out
    for f in sorted(os.listdir(DIR)):
        if not f.endswith(".json") or f.endswith(".info.json") or f == "client_secret.json":
            continue
        label = f[:-5]
        info = None if refresh else C.read_json(_info_path(label))
        if not info:
            try:
                info = _describe(label)
            except Exception as e:
                info = {"label": label, "channel_id": "", "channel_title": f"(error: {str(e)[:60]})", "videos": 0}
        out.append(info)
    return out


def remove_account(label):
    for p in (_token_path(label), _info_path(label)):
        if os.path.exists(p):
            os.remove(p)


def resolve(label_or_channel):
    """Accept a label OR a channel id and return the label."""
    for a in accounts():
        if label_or_channel in (a["label"], a["channel_id"]):
            return a["label"]
    raise SystemExit(f"no YouTube account {label_or_channel!r}. See: reelforge accounts list")


def upload(label, file, title, description="", tags=None, privacy="private",
           category="28", short=None, thumb=None, log=print):
    from googleapiclient.http import MediaFileUpload
    yt = service(label)
    if short is None:
        # a vertical video under 3 minutes is treated as a Short; the tag helps
        short = True
    desc = description or ""
    if short and "#Shorts" not in desc:
        desc = (desc + "\n\n#Shorts").strip()
    body = {"snippet": {"title": title[:100], "description": desc[:5000],
                        "tags": [t for t in (tags or []) if t][:40], "categoryId": str(category)},
            "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False}}
    media = MediaFileUpload(file, chunksize=4 * 1024 * 1024, resumable=True, mimetype="video/mp4")
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    log(f"  uploading {os.path.basename(file)} ({os.path.getsize(file) / 1e6:.1f} MB) as {privacy} to {label}")
    resp = None
    while resp is None:
        status, resp = req.next_chunk()
        if status:
            log(f"    {int(status.progress() * 100):3d}%")
    vid = resp["id"]
    if thumb and os.path.exists(thumb):
        try:
            yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(thumb, mimetype="image/jpeg")).execute()
        except Exception as e:
            # custom thumbnails need a verified channel; not fatal
            log(f"  thumbnail not set: {str(e)[:80]}")
    return {"platform": "youtube", "account": label, "id": vid,
            "url": f"https://youtu.be/{vid}", "studio": f"https://studio.youtube.com/video/{vid}/edit",
            "privacy": privacy, "at": time.strftime("%Y-%m-%d %H:%M")}
