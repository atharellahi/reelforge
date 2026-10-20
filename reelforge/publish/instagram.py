"""Instagram Reels through the Graph API.

Meta does not accept an upload. It FETCHES the video from a public URL, so a
file on a laptop has to become reachable first. Three ways, tried in order:

  1. a URL you pass in (already hosted somewhere)
  2. S3, if credentials are configured (hand-signed PUT, no SDK)
  3. a temporary Cloudflare quick tunnel, if `cloudflared` is on PATH - free,
     no account, exists only for the minutes the publish takes

Needs an Instagram Business/Creator account linked to a Facebook Page, a
long-lived access token with instagram_content_publish, and the IG user id.
"""
import os
import re
import shutil
import subprocess
import time

import requests

from .. import config as C

GRAPH = "https://graph.facebook.com/v21.0"


def _need(cfg):
    if not (cfg.get("instagram_access_token") and cfg.get("instagram_user_id")):
        raise SystemExit(
            "Instagram needs instagram_access_token and instagram_user_id:\n"
            "  reelforge config set instagram_access_token <token>\n"
            "  reelforge config set instagram_user_id <id>")


class _Tunnel:
    """Serve one directory and expose it with a cloudflared quick tunnel."""

    def __init__(self, directory):
        from ..render import serve_dir
        self.srv, self.port = serve_dir(directory)
        exe = shutil.which("cloudflared")
        if not exe:
            self.srv.shutdown()
            raise RuntimeError("cloudflared not found")
        self.proc = subprocess.Popen([exe, "tunnel", "--url", f"http://127.0.0.1:{self.port}", "--no-autoupdate"],
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.url = None
        t0 = time.time()
        while time.time() - t0 < 40:
            line = self.proc.stdout.readline()
            m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line or "")
            if m:
                self.url = m.group(0); break
        if not self.url:
            self.close()
            raise RuntimeError("cloudflared did not report a URL")

    def close(self):
        try:
            self.proc.terminate()
        except Exception:
            pass
        try:
            self.srv.shutdown()
        except Exception:
            pass


def public_url_for(file, cfg, log=print):
    """Returns (url, cleanup_callable)."""
    if cfg.get("s3_bucket") and cfg.get("s3_access_key_id") and cfg.get("s3_secret_access_key"):
        from . import s3
        key = f"{cfg.get('s3_prefix', 'reelforge').strip('/')}/{int(time.time())}_{os.path.basename(file)}"
        with open(file, "rb") as fh:
            url = s3.put_object(cfg["s3_bucket"], cfg.get("s3_region", "us-east-1"),
                                cfg["s3_access_key_id"], cfg["s3_secret_access_key"], key, fh.read())
        log(f"  hosted on S3: {url}")
        return url, (lambda: None)
    if cfg.get("public_base_url"):
        # the user hosts <repo>/.reelforge/out somewhere already
        rel = os.path.basename(os.path.dirname(file)) + "/" + os.path.basename(file)
        return cfg["public_base_url"].rstrip("/") + "/" + rel, (lambda: None)
    t = _Tunnel(os.path.dirname(file))
    log(f"  temporary tunnel: {t.url}")
    return f"{t.url}/{os.path.basename(file)}", t.close


def publish_reel(file=None, url=None, caption="", log=print, share_to_feed=True):
    cfg = C.load()
    _need(cfg)
    tok, uid = cfg["instagram_access_token"], cfg["instagram_user_id"]
    cleanup = lambda: None
    if not url:
        url, cleanup = public_url_for(file, cfg, log)
    try:
        r = requests.post(f"{GRAPH}/{uid}/media", data={
            "media_type": "REELS", "video_url": url, "caption": caption[:2200],
            "share_to_feed": "true" if share_to_feed else "false", "access_token": tok}, timeout=60).json()
        if "id" not in r:
            raise RuntimeError(f"container failed: {r}")
        cid = r["id"]
        log(f"  container {cid}, waiting for Meta to fetch and process")
        for _ in range(120):
            s = requests.get(f"{GRAPH}/{cid}", params={"fields": "status_code,status", "access_token": tok}, timeout=30).json()
            code = s.get("status_code")
            if code == "FINISHED":
                break
            if code in ("ERROR", "EXPIRED"):
                raise RuntimeError(f"processing {code}: {s.get('status')}")
            time.sleep(5)
        else:
            raise RuntimeError("timed out waiting for Instagram processing")
        p = requests.post(f"{GRAPH}/{uid}/media_publish", data={"creation_id": cid, "access_token": tok}, timeout=60).json()
        if "id" not in p:
            raise RuntimeError(f"publish failed: {p}")
        mid = p["id"]
        link = requests.get(f"{GRAPH}/{mid}", params={"fields": "permalink", "access_token": tok}, timeout=30).json().get("permalink", "")
        return {"platform": "instagram", "id": mid, "url": link, "at": time.strftime("%Y-%m-%d %H:%M")}
    finally:
        cleanup()
