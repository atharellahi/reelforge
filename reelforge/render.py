"""Headless Chrome over the DevTools protocol, driven from Python.

scene.html draws the storyboard as a pure function of time. A whole video is
captured by seeking the same page once per frame. No browser-automation
dependency: Chrome is launched with a debugging port and spoken to directly.
"""
import http.server
import json
import os
import shutil
import socket
import socketserver
import subprocess
import threading
import time

from . import config as C

SIZES = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080), "4:5": (1080, 1350)}


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Chrome:
    def __init__(self, width, height, chrome=None):
        self.port = _free_port()
        self.width, self.height = width, height
        exe = chrome or C.find_chrome()
        # one profile per instance: Chrome refuses a second process on the
        # same profile, which would make two renders at once (or a UI taking
        # screenshots during a make) fail in a confusing way
        import tempfile
        self.profile = tempfile.mkdtemp(prefix="rf-chrome-", dir=C.HOME)
        self.proc = subprocess.Popen([
            exe, f"--remote-debugging-port={self.port}", "--headless=new", "--hide-scrollbars",
            "--force-device-scale-factor=1", f"--window-size={width},{height}",
            "--disable-gpu", "--no-sandbox", "--force-color-profile=srgb",
            "--font-render-hinting=none", "--no-first-run", "--disable-extensions",
            f"--user-data-dir={self.profile}", "about:blank",
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        import urllib.request
        target = None
        for _ in range(100):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/json/list", timeout=1) as r:
                    for t in json.load(r):
                        if t.get("type") == "page":
                            target = t; break
                if target:
                    break
            except Exception:
                pass
            time.sleep(0.2)
        if not target:
            self.close()
            raise RuntimeError("Chrome did not open its debugging port")
        from websockets.sync.client import connect
        self.ws = connect(target["webSocketDebuggerUrl"], max_size=None, open_timeout=20)
        self._id = 0
        self.send("Page.enable")
        # --window-size includes browser chrome; the layout viewport must be set
        # explicitly or the page renders short and the capture pads it
        self.send("Emulation.setDeviceMetricsOverride",
                  {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": False})

    def send(self, method, params=None):
        self._id += 1
        my = self._id
        self.ws.send(json.dumps({"id": my, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(self.ws.recv(timeout=120))
            if msg.get("id") == my:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    def evaluate(self, expr, await_promise=False):
        r = self.send("Runtime.evaluate", {"expression": expr, "awaitPromise": await_promise,
                                           "returnByValue": True})
        return (r.get("result") or {}).get("value")

    def navigate(self, url, wait_expr="document.readyState==='complete'", timeout=30):
        self.send("Page.navigate", {"url": url})
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                if self.evaluate(wait_expr):
                    return
            except Exception:
                pass
            time.sleep(0.15)
        raise RuntimeError(f"page did not become ready: {url}")

    def screenshot(self, fmt="jpeg", quality=94):
        import base64
        r = self.send("Page.captureScreenshot", {"format": fmt, "quality": quality,
                                                 "captureBeyondViewport": False})
        return base64.b64decode(r["data"])

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass
        try:
            self.proc.terminate(); self.proc.wait(timeout=5)
        except Exception:
            pass
        shutil.rmtree(self.profile, ignore_errors=True)


# ----------------------------------------------------------- static server

class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def serve_dir(directory):
    port = _free_port()
    handler = lambda *a, **k: _Quiet(*a, directory=directory, **k)
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", port), handler)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, port


# ----------------------------------------------------------------- render

ENGINE = os.path.join(os.path.dirname(__file__), "www", "scene.html")


def render(project, job_dir, sb, fps=30, log=print):
    cfg = C.load()
    ffmpeg = C.find_ffmpeg(cfg)
    W, H = SIZES[sb.get("aspect", "9:16")]
    sb["fps"] = fps
    sb["width"], sb["height"] = W, H

    # the engine is served from inside the project so one server covers both
    # the page and every asset it references
    eng_dir = os.path.join(project, "_engine")
    os.makedirs(eng_dir, exist_ok=True)
    shutil.copyfile(ENGINE, os.path.join(eng_dir, "scene.html"))
    job_rel = os.path.relpath(job_dir, project).replace("\\", "/")
    C.write_json(os.path.join(job_dir, "storyboard.json"), sb)

    frames = os.path.join(job_dir, "frames")
    shutil.rmtree(frames, ignore_errors=True)
    os.makedirs(frames)

    srv, port = serve_dir(project)
    chrome = Chrome(W, H, cfg.get("chrome_path") or None)
    try:
        url = f"http://127.0.0.1:{port}/_engine/scene.html?sb=/{job_rel}/storyboard.json&t=0"
        chrome.navigate(url, wait_expr="window.__ready===true", timeout=60)
        chrome.evaluate("document.fonts.ready.then(()=>true)", await_promise=True)
        total = int(round(sb["duration"] * fps))
        log(f"  rendering {total} frames at {W}x{H} @ {fps}fps")
        t0 = time.time()
        for f in range(total):
            t = f / fps
            chrome.evaluate(f"window.__seek({t:.4f})")
            # images are recreated per seek; wait for the ones on screen
            chrome.evaluate("window.__imagesReady()", await_promise=True)
            with open(os.path.join(frames, f"f{f:05d}.jpg"), "wb") as fh:
                fh.write(chrome.screenshot())
            if f % 90 == 0 and f:
                rate = f / (time.time() - t0)
                log(f"    {f}/{total}  ({rate:.1f} fps, ~{(total - f) / max(rate, 0.1):.0f}s left)")
    finally:
        chrome.close()
        srv.shutdown()

    dur = sb["duration"]
    video = os.path.join(job_dir, "video.mp4")
    subprocess.run([ffmpeg, "-v", "error", "-y", "-framerate", str(fps),
                    "-i", os.path.join(frames, "f%05d.jpg"),
                    "-vf", f"fade=t=in:st=0:d=0.3,fade=t=out:st={max(0, dur - 0.4):.2f}:d=0.4,format=yuv420p",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-r", str(fps), video], check=True)

    final = os.path.join(job_dir, "final.mp4")
    vo = os.path.join(job_dir, "vo.wav")
    lead_ms = int(sb.get("lead", 0.3) * 1000)
    if os.path.exists(vo):
        subprocess.run([ffmpeg, "-v", "error", "-y", "-i", video, "-i", vo,
                        "-af", f"adelay={lead_ms}|{lead_ms},apad", "-t", f"{dur:.3f}",
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                        "-shortest", "-movflags", "+faststart", final], check=True)
    else:
        shutil.copyfile(video, final)

    # thumbnail: the hook at its loudest moment
    hook_end = sb["timeline"][0]["end"]
    tf = max(0, min(total - 1, int((hook_end - 0.35) * fps)))
    shutil.copyfile(os.path.join(frames, f"f{tf:05d}.jpg"), os.path.join(job_dir, "thumb.jpg"))
    log(f"  -> {final}  ({os.path.getsize(final) / 1e6:.1f} MB, {dur:.1f}s)")
    return final


def capture_page(url, out_png, width=430, height=932, settle=1.4):
    chrome = Chrome(width, height)
    try:
        chrome.navigate(url, timeout=40)
        time.sleep(settle)
        data = chrome.screenshot(fmt="png")
        os.makedirs(os.path.dirname(out_png), exist_ok=True)
        with open(out_png, "wb") as fh:
            fh.write(data)
    finally:
        chrome.close()
    return out_png
