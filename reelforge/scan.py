"""Read a repo and work out what it does, what it looks like, and what to film.

Three outputs, all in <repo>/.reelforge/ so the team shares them via git:

  features.json   what the product does, as FACTS with file evidence. Every
                  claim a video makes must trace back to one of these.
  brand.json      colours, fonts, logo, name - detected, then hand-edited.
  shots/          optional real screenshots, if a running URL is given.
"""
import json
import os
import re
import subprocess
from urllib.parse import urlparse

from . import config as C
from . import gemini

SKIP_DIRS = {"node_modules", ".git", ".next", "dist", "build", "out", "coverage",
             "__pycache__", "venv", ".venv", ".reelforge", "vendor", ".cache", "public"}
CODE_EXT = (".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte", ".html", ".py")


def resolve_repo(src):
    """A local path is used in place. A git URL is cloned shallowly under
    ~/.reelforge/repos and pulled on later runs."""
    if re.match(r"^(https?://|git@)", src):
        # a checkout of this URL already on this machine wins over a fresh clone
        local = C.aliases().get(src)
        if local and os.path.isdir(local):
            return local
        path = urlparse(src.replace("git@", "https://").replace(":", "/", 1)).path.strip("/")
        parts = re.sub(r"\.git$", "", path).split("/")
        # org-qualified, so acme/api and globex/api do not clone onto each other
        name = "__".join(p for p in parts[-2:] if p) or "repo"
        dest = os.path.join(C.HOME, "repos", name)
        if os.path.isdir(os.path.join(dest, ".git")):
            subprocess.run(["git", "-C", dest, "pull", "--ff-only", "-q"], check=False)
        else:
            subprocess.run(["git", "clone", "--depth", "1", src, dest], check=True)
        return dest
    p = os.path.abspath(src)
    if not os.path.isdir(p):
        raise SystemExit(f"not a directory: {p}")
    return p


def _walk(repo, max_files=4000):
    n = 0
    for root, dirs, files in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for f in files:
            n += 1
            if n > max_files:
                return
            yield os.path.join(root, f)


def _read(path, limit=20000):
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            return fh.read(limit)
    except Exception:
        return ""


def _rel(repo, p):
    return os.path.relpath(p, repo).replace("\\", "/")


# ------------------------------------------------------------ collection

def routes(repo):
    """Best-effort list of user-facing routes across common frameworks."""
    out = []
    for p in _walk(repo):
        r = _rel(repo, p)
        low = r.lower()
        # Next.js pages router
        m = re.match(r"^(?:src/)?pages/(.+)\.(jsx?|tsx?)$", r)
        if m and not m.group(1).startswith(("api/", "_")):
            route = "/" + re.sub(r"(^|/)index$", "", m.group(1))
            out.append((route or "/", r))
            continue
        # Next.js app router
        m = re.match(r"^(?:src/)?app/(.*?)/?page\.(jsx?|tsx?)$", r)
        if m:
            seg = re.sub(r"\(.*?\)/?", "", m.group(1))  # drop route groups
            out.append(("/" + seg.strip("/"), r))
            continue
        if low.endswith(CODE_EXT) and any(k in low for k in ("router", "routes", "urls.py", "app.py", "main.py", "server", "views", "api")):
            src = _read(p, 60000)
            # express/react-router `path: "/x"`, Django `path('x/')`, Flask and
            # FastAPI `@app.get("/x")` - a back-end's routes are evidence too
            for mm in re.finditer(r"""(?:path|route)\s*[:=(]\s*['"]([^'"\s]{1,80})['"]""", src):
                out.append(("/" + mm.group(1).lstrip("/"), r))
            for mm in re.finditer(r"""\.(?:get|post|put|patch|delete|route)\(\s*['"](/[^'"\s]{0,80})['"]""", src):
                out.append((mm.group(1), r))
    seen, uniq = set(), []
    for route, file in out:
        if route not in seen and not route.startswith("/api"):
            seen.add(route); uniq.append({"route": route, "file": file})
    return uniq[:80]


def ui_strings(repo, cap=900):
    """Text a user actually sees - the labels a video is allowed to quote.

    JSX text and attributes from components and pages, plus short Title-Case
    string literals from config/data files: option lists like aesthetics or
    categories live there as data, not markup, and they are UI text too.
    """
    found = {}
    for p in _walk(repo):
        r = _rel(repo, p)
        low = r.lower()
        if not low.endswith((".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte", ".html", ".json")):
            continue
        in_ui = any(seg in r for seg in ("component", "pages", "app/", "src/", "views", "templates"))
        in_data = any(seg in low for seg in ("config", "data", "constant", "content", "copy", "options", "i18n", "locale"))
        if not (in_ui or in_data):
            continue
        src = _read(p, 60000)
        if in_ui:
            for m in re.finditer(r">\s*([A-Z][^<>{}\n]{6,90}?)\s*<", src):
                found.setdefault(m.group(1).strip(), r)
            for m in re.finditer(r"""(?:title|placeholder|aria-label|alt|label)=["']([A-Z][^"'{}\n]{3,90})["']""", src):
                found.setdefault(m.group(1).strip(), r)
        if in_data or low.endswith(".json"):
            # 'Minimalist', "Date Night", 'Business Wear' - 1-4 capitalised words
            for m in re.finditer(r"""['"]([A-Z][a-z0-9&'’-]+(?: [A-Za-z0-9&'’-]+){0,3})['"]""", src):
                found.setdefault(m.group(1).strip(), r)
        if len(found) > cap * 4:
            break
    items = sorted(found.items(), key=lambda kv: (len(kv[0]) > 60, kv[0]))[:cap]
    return [{"text": t, "file": f} for t, f in items]


def readme(repo):
    for n in ("README.md", "readme.md", "README.rst", "README.txt", "README"):
        p = os.path.join(repo, n)
        if os.path.exists(p):
            return _read(p, 9000)
    return ""


def package_meta(repo):
    pj = os.path.join(repo, "package.json")
    if os.path.exists(pj):
        try:
            d = json.loads(_read(pj, 20000))
            return {"name": d.get("name", ""), "description": d.get("description", ""),
                    "deps": sorted(list((d.get("dependencies") or {}).keys()))[:60]}
        except Exception:
            pass
    pp = os.path.join(repo, "pyproject.toml")
    if os.path.exists(pp):
        s = _read(pp)
        m = re.search(r'name\s*=\s*"([^"]+)"', s); d = re.search(r'description\s*=\s*"([^"]+)"', s)
        return {"name": m.group(1) if m else "", "description": d.group(1) if d else "", "deps": []}
    return {"name": os.path.basename(repo), "description": "", "deps": []}


def tree(repo, depth=2, cap=120):
    lines = []
    base = repo.rstrip("/\\")
    for root, dirs, files in os.walk(repo):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
        level = root[len(base):].count(os.sep)
        if level >= depth:
            dirs[:] = []
            continue
        for d in dirs:
            lines.append("  " * level + d + "/")
        if len(lines) > cap:
            break
    return "\n".join(lines[:cap])


# ----------------------------------------------------------------- brand

def detect_brand(repo, project):
    name = package_meta(repo)["name"] or os.path.basename(repo)
    name = re.sub(r"[-_]+", " ", re.sub(r"^@[^/]+/", "", name)).strip().title()
    brand = {"name": name, "tagline": "", "url": "",
             "primary": "#1F2937", "accent": "#C9A961", "bg": "#FAF7F2",
             "font_head": "Comfortaa", "font_body": "Quicksand", "logo": ""}

    # colours: CSS custom properties first, then tailwind
    hexre = r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b"
    css_files = [p for p in _walk(repo) if p.lower().endswith((".css", ".scss"))][:60]
    text = "\n".join(_read(p, 30000) for p in css_files)
    for key, pats in (("primary", [r"--primary\s*:\s*(" + hexre + ")", r"--brand\s*:\s*(" + hexre + ")", r"--color-primary\s*:\s*(" + hexre + ")"]),
                      ("accent", [r"--accent\s*:\s*(" + hexre + ")", r"--secondary\s*:\s*(" + hexre + ")"]),
                      ("bg", [r"--bg\s*:\s*(" + hexre + ")", r"--background\s*:\s*(" + hexre + ")"])):
        for pat in pats:
            m = re.search(pat, text)
            if m:
                brand[key] = m.group(1); break
    tw = os.path.join(repo, "tailwind.config.js")
    if os.path.exists(tw) and brand["primary"] == "#1F2937":
        m = re.search(r"primary\s*:\s*['\"](" + hexre + ")", _read(tw))
        if m:
            brand["primary"] = m.group(1)

    # fonts: whatever Google Fonts link the app loads
    allsrc = text + "\n".join(_read(p, 20000) for p in _walk(repo) if p.lower().endswith((".js", ".jsx", ".tsx", ".html")))[:400000]
    fams = re.findall(r"fonts\.googleapis\.com/css2?\?[^\"'\s]*?family=([A-Za-z+]+)", allsrc)
    fams = [f.replace("+", " ") for f in fams]
    if fams:
        brand["font_head"] = fams[0]
        brand["font_body"] = fams[1] if len(fams) > 1 else fams[0]

    # logo: copy into the project so the scene can serve it
    for p in _walk(repo):
        r = _rel(repo, p).lower()
        if "logo" in os.path.basename(r) and r.endswith((".png", ".svg", ".jpg", ".jpeg")) and "node_modules" not in r:
            ext = os.path.splitext(r)[1]
            dest = os.path.join(project, "assets", "logo" + ext)
            try:
                import shutil; shutil.copyfile(p, dest)
                brand["logo"] = "assets/logo" + ext
            except Exception:
                pass
            break
    # public/ is skipped by _walk, which is exactly where logos usually live
    if not brand["logo"]:
        pub = os.path.join(repo, "public")
        if os.path.isdir(pub):
            for root, _d, files in os.walk(pub):
                for f in files:
                    if "logo" in f.lower() and f.lower().endswith((".png", ".svg", ".jpg", ".jpeg")):
                        ext = os.path.splitext(f)[1]
                        dest = os.path.join(project, "assets", "logo" + ext)
                        import shutil; shutil.copyfile(os.path.join(root, f), dest)
                        brand["logo"] = "assets/logo" + ext
                        break
                if brand["logo"]:
                    break
    rd = readme(repo)
    m = re.search(r"^(?!#)([A-Z][^\n]{20,140}\.)", rd, re.M)
    if m:
        brand["tagline"] = m.group(1).strip()
    return brand


# -------------------------------------------------------------- features

FEATURE_SYSTEM = """You are a senior product marketer who reads code. You will be given
evidence from a software repository: README, routes, user-visible UI strings, and
the folder tree. Produce a list of the product's FEATURES as a shopper or user
would experience them.

Rules:
- Only include features the evidence supports. If you cannot point to a route,
  UI string or README line, leave it out. Never invent.
- Each feature needs 3-6 concrete FACTS. A fact is something a video could show
  or say without lying: a real label, a real number, a real behaviour.
- Each fact cites its evidence: the file path or "README".
- Prefer outcomes over mechanics: "one outfit per day, built for the weather"
  beats "calls the recommendation endpoint".
Return JSON: {"product": {"name","one_line","audience"}, "features": [
  {"id": "snake_case", "name": "...", "one_line": "...", "why_it_matters": "...",
   "routes": ["/path"], "facts": [{"text": "...", "evidence": "path or README"}],
   "visual": "what is on screen when this feature is used, in one sentence"}]}
Return at most 12 features, best first."""


def _evidence(repo, label, budget):
    rd = readme(repo)
    rt = routes(repo)
    st = ui_strings(repo)
    pm = package_meta(repo)
    text = (
        f"# repo: {label}\n## package\n{json.dumps(pm)[:1500]}\n\n## README\n{rd}\n\n"
        f"## routes ({len(rt)})\n" + "\n".join(f"{r['route']}  <- {label}/{r['file']}" for r in rt) +
        f"\n\n## UI strings ({len(st)})\n" + "\n".join(f"{s['text']}  <- {label}/{s['file']}" for s in st) +
        f"\n\n## tree\n{tree(repo)}"
    )
    return text[:budget], rt, st, (len(rd), len(rt), len(st))


def scan(repo, project, brief=None, log=print, extra_repos=()):
    """One product may span several repositories - a front-end and the
    back-end behind it. The primary repo owns .reelforge/; every repo's
    README, routes and strings are evidence, cited as repo/path."""
    extra = [resolve_repo(r) for r in extra_repos if r]
    repos = [repo] + extra
    labels = [os.path.basename(r.rstrip("/\\")) for r in repos]
    budget = max(40000, 150000 // len(repos))
    parts, all_routes, all_strings = [], [], []
    for r, label in zip(repos, labels):
        text, rt, st, (nrd, nrt, nst) = _evidence(r, label, budget)
        parts.append(text); all_routes += rt; all_strings += [s["text"] for s in st]
        log(f"  {label}: README {nrd} chars, {nrt} routes, {nst} UI strings")
    evidence = "\n\n".join(parts)
    if len(repos) > 1:
        evidence = ("NOTE: the evidence below comes from SEVERAL repositories of ONE product "
                    f"({', '.join(labels)}). Treat them as one product. Cite evidence as repo/path.\n\n") + evidence
    if brief:
        evidence += f"\n\n# notes from the team\n{brief}"
    # ids must survive a re-scan: jobs, tuning and teammates refer to them.
    # Left alone the model renames "product_upload_batch_processing" to
    # "batch_product_upload_processing" and every reference breaks.
    prev = C.read_json(os.path.join(project, "features.json"), {}) or {}
    if prev.get("features"):
        evidence += ("\n\n# previous feature ids - REUSE the same id for the same feature; "
                     "only new features get new ids\n" +
                     "\n".join(f"{f['id']}: {f.get('name','')}" for f in prev["features"]))
    data = gemini.text(evidence[:160000], system=FEATURE_SYSTEM, as_json=True, temperature=0.3)
    feats = data.get("features", [])
    for f in feats:
        f["id"] = re.sub(r"[^a-z0-9]+", "_", str(f.get("id") or f.get("name", "")).lower()).strip("_")[:40]
    out = {"product": data.get("product", {}), "features": feats,
           "routes": all_routes, "scanned_from": repo, "repos": repos}
    C.write_json(os.path.join(project, "features.json"), out)
    # every label a video puts on screen must exist somewhere in the product;
    # the UI strings are that somewhere, kept beside the features
    C.write_json(os.path.join(project, "ui_strings.json"), sorted(set(all_strings)))
    portable = [C.portable_repo(r) for r in extra_repos if r]
    C.save_project_meta(project, {"name": (data.get("product") or {}).get("name") or labels[0],
                                  "extra_repos": portable})
    C.remember_product((data.get("product") or {}).get("name") or labels[0], repo, portable)
    bpath = os.path.join(project, "brand.json")
    if not os.path.exists(bpath):
        b = detect_brand(repo, project)
        # package.json names are often internal ("frontend-app"); the product
        # name the scan just read from the README is what goes on screen
        pname = (out["product"] or {}).get("name", "").strip()
        if pname and (len(pname) < len(b["name"]) or any(w in b["name"].lower() for w in ("app", "frontend", "web", "next"))):
            b["name"] = pname
        if not b["tagline"]:
            b["tagline"] = out["product"].get("one_line", "")
        C.write_json(bpath, b)
        log(f"  brand: {b['name']} {b['primary']}/{b['accent']} {b['font_head']}  logo={'yes' if b['logo'] else 'no'}")
    log(f"  {len(feats)} features -> {os.path.join(project, 'features.json')}")
    return out


def screenshots(project, base_url, paths, log=print):
    """Capture real screens of a running app. These are the strongest thing a
    feature video can show, so when a URL exists, use it."""
    from . import render
    base_url = base_url.rstrip("/")
    done = []
    for path in paths:
        slug = re.sub(r"[^a-z0-9]+", "_", path.lower()).strip("_") or "home"
        for kind, (w, h) in (("mobile", (430, 932)), ("desktop", (1440, 900))):
            out = os.path.join(project, "shots", f"{slug}_{kind}.png")
            try:
                render.capture_page(base_url + path, out, w, h)
                done.append(C.os.path.relpath(out, project).replace("\\", "/"))
                log(f"  shot {path} {kind}")
            except Exception as e:
                log(f"  shot {path} {kind} failed: {str(e)[:80]}")
    return done
