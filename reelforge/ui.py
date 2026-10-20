"""The local web app. Standard library only, so `reelforge ui` needs nothing
beyond the package. Binds to 127.0.0.1: it is a tool on your machine, not a
service, and the keys it edits stay on your machine.
"""
import json
import mimetypes
import os
import threading
import traceback
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import config as C, make, memory, scan

JOBS = {}      # run id -> {"log": [...], "done": bool, "error": str, "result": ...}
LOCK = threading.Lock()


def _run(run_id, fn, *args, **kw):
    st = JOBS[run_id] = {"log": [], "done": False, "error": "", "result": None}

    def log(m):
        with LOCK:
            st["log"].append(str(m))

    def go():
        try:
            st["result"] = fn(*args, log=log, **kw)
        except SystemExit as e:
            st["error"] = str(e)
        except Exception as e:
            st["error"] = f"{e}\n{traceback.format_exc()[-800:]}"
        finally:
            st["done"] = True
    threading.Thread(target=go, daemon=True).start()
    return run_id


def _project(repo):
    return C.project_dir(scan.resolve_repo(repo))


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, data, code=200):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path):
        if not os.path.exists(path):
            return self._json({"error": "not found"}, 404)
        ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
        size = os.path.getsize(path)
        rng = self.headers.get("Range")
        with open(path, "rb") as fh:
            if rng:
                # <video> needs range requests to scrub
                a, b = rng.replace("bytes=", "").split("-")
                a = int(a or 0); b = int(b) if b else size - 1
                fh.seek(a); data = fh.read(b - a + 1)
                self.send_response(206)
                self.send_header("Content-Range", f"bytes {a}-{b}/{size}")
            else:
                data = fh.read(); self.send_response(200)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = dict(urllib.parse.parse_qsl(u.query))
        try:
            if u.path == "/":
                return self._file(os.path.join(os.path.dirname(__file__), "www", "ui.html"))
            if u.path == "/api/state":
                repo = q.get("repo") or self.server.repo
                st = {"config": C.masked(C.load()), "repo": repo, "home": C.HOME, "products": C.products()}
                if repo and os.path.isdir(repo):
                    project = _project(repo)
                    st["project"] = C.project_meta(project)
                    st["features"] = C.read_json(os.path.join(project, "features.json"), {})
                    st["brand"] = C.read_json(os.path.join(project, "brand.json"), {})
                    st["jobs"] = make.list_jobs(project)
                    st["memory"] = memory.load(project)["notes"]
                try:
                    from .publish import youtube
                    st["youtube_accounts"] = youtube.accounts()
                except Exception as e:
                    st["youtube_accounts"] = []; st["youtube_error"] = str(e)[:200]
                return self._json(st)
            if u.path == "/api/run":
                return self._json(JOBS.get(q.get("id"), {"error": "no such run"}))
            if u.path == "/file":
                project = _project(q["repo"])
                path = os.path.abspath(os.path.join(project, q["path"]))
                if not path.startswith(os.path.abspath(project)):
                    return self._json({"error": "forbidden"}, 403)
                return self._file(path)
            return self._json({"error": "not found"}, 404)
        except Exception as e:
            return self._json({"error": str(e)}, 500)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n) or b"{}")
        u = urllib.parse.urlparse(self.path)
        try:
            if u.path == "/api/config":
                for k, v in (body.get("values") or {}).items():
                    if v is None or (isinstance(v, str) and "…" in v):
                        continue  # masked values come back unchanged; skip them
                    C.set_value(k, v)
                return self._json({"ok": True, "config": C.masked(C.load())})
            if u.path == "/api/products":
                # register a product: primary repo (cloned if a URL) + extra repos
                repo = scan.resolve_repo(body["repo"])
                project = C.project_dir(repo)
                extra = [x for x in (body.get("extra_repos") or []) if x]
                name = body.get("name") or os.path.basename(repo)
                C.save_project_meta(project, {"name": name, "extra_repos": extra})
                C.remember_product(name, repo, extra)
                return self._json({"ok": True, "repo": repo, "products": C.products()})
            if u.path == "/api/project":
                project = _project(body["repo"])
                allowed = {k: v for k, v in (body.get("patch") or {}).items() if k in ("default_youtube", "name", "extra_repos")}
                return self._json({"ok": True, "project": C.save_project_meta(project, allowed)})
            if u.path == "/api/scan":
                repo = scan.resolve_repo(body["repo"])
                project = C.project_dir(repo)
                extra = body.get("extra_repos") or C.project_meta(project).get("extra_repos") or []

                def job(log):
                    out = scan.scan(repo, project, brief=body.get("brief"), log=log, extra_repos=extra)
                    if body.get("url"):
                        routes = [r["route"] for r in out.get("routes", [])][:8] or ["/"]
                        scan.screenshots(project, body["url"], routes, log=log)
                    return {"features": len(out["features"])}
                return self._json({"run": _run("scan-" + str(len(JOBS)), job)})
            if u.path == "/api/make":
                repo = scan.resolve_repo(body["repo"])
                rid = "make-" + str(len(JOBS))
                _run(rid, make.make, repo, feature_id=body.get("feature") or None, prompt=body.get("prompt") or "",
                     aspect=body.get("aspect", "9:16"), platform=body.get("platform", "shorts"),
                     seconds=int(body.get("seconds") or 30), voice=body.get("voice", "gemini"),
                     veo=bool(body.get("veo")), captions=body.get("captions", True), base_url=body.get("url") or None)
                return self._json({"run": rid})
            if u.path == "/api/meta":
                project = _project(body["repo"])
                return self._json({"ok": True, "meta": make.save_meta(project, body["job"], {"meta": body.get("meta", {})})})
            if u.path == "/api/tune":
                project = _project(body["repo"])
                if body.get("remove") is not None:
                    return self._json({"notes": memory.remove(project, int(body["remove"]))["notes"]})
                return self._json({"notes": memory.add(project, body["note"])["notes"]})
            if u.path == "/api/publish":
                project = _project(body["repo"])
                m = make.job_meta(project, body["job"])
                job_dir = os.path.join(project, "out", body["job"])
                file = os.path.join(job_dir, m["file"])
                meta = m.get("meta", {})

                def job(log):
                    res = []
                    if body.get("youtube"):
                        from .publish import youtube
                        label = youtube.resolve(body["youtube"])
                        r = youtube.upload(label, file, meta.get("youtube_title") or m["title"], meta.get("youtube_description", ""),
                                           meta.get("tags", []), privacy=body.get("privacy") or meta.get("privacy", "private"),
                                           short=m["aspect"] in ("9:16", "4:5"), thumb=os.path.join(job_dir, m.get("thumb", "")), log=log)
                        res.append(r); log(f"YouTube: {r['url']}")
                    if body.get("instagram"):
                        from .publish import instagram
                        r = instagram.publish_reel(file=file, caption=meta.get("instagram_caption") or meta.get("youtube_title", ""), log=log)
                        res.append(r); log(f"Instagram: {r['url']}")
                    make.save_meta(project, body["job"], {"published": m.get("published", []) + res})
                    return res
                return self._json({"run": _run("pub-" + str(len(JOBS)), job)})
            if u.path == "/api/accounts/add":
                from .publish import youtube

                def job(log):
                    log("a browser window opened on this machine - choose the account and channel")
                    x = youtube.add_account(body["label"])
                    log(f"saved {x['label']} -> {x['channel_title']}")
                    return x
                return self._json({"run": _run("acc-" + str(len(JOBS)), job)})
            return self._json({"error": "not found"}, 404)
        except SystemExit as e:
            return self._json({"error": str(e)}, 400)
        except Exception as e:
            return self._json({"error": str(e)}, 500)


def serve(repo=None, port=7733, open_browser=True):
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    srv.repo = os.path.abspath(repo) if repo else ""
    url = f"http://127.0.0.1:{port}/"
    print(f"reelforge ui  ->  {url}   (ctrl-c to stop)")
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
