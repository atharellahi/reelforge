"""reelforge command line.

  reelforge doctor                         what is installed, what is missing
  reelforge config set <key> <value>       keys and paths (stored in ~/.reelforge)
  reelforge scan <repo> [--url BASE]       detect features + brand (+ screenshots)
  reelforge make <repo> --feature <id>     write, voice, render, check one video
  reelforge make <repo> --prompt "..."     same, from a free brief
  reelforge jobs <repo>                    what has been made
  reelforge publish <repo> <job> --youtube <label> [--privacy unlisted]
  reelforge publish <repo> <job> --instagram
  reelforge accounts add --label work      add a YouTube channel (browser consent)
  reelforge tune <repo> "less text"        remember a correction for this project
  reelforge ui [--repo <repo>]             the local web app
"""
import argparse
import json
import os
import shutil
import sys

from . import __version__, config as C


def _log(msg):
    print(msg, flush=True)


# ------------------------------------------------------------- commands

def cmd_doctor(a):
    cfg = C.load()
    rows = []
    rows.append(("ffmpeg", shutil.which("ffmpeg") or cfg.get("ffmpeg_path") or "MISSING"))
    try:
        rows.append(("chrome", C.find_chrome(cfg)))
    except SystemExit as e:
        rows.append(("chrome", "MISSING"))
    rows.append(("gemini key", "set" if cfg["gemini_api_key"] else "MISSING (required)"))
    rows.append(("veo", "configured" if cfg["veo_api_key"] and cfg["veo_project"] else "off (optional)"))
    try:
        from .publish import youtube
        rows.append(("youtube client", youtube.secret_path()))
        accs = youtube.accounts()
        rows.append(("youtube accounts", ", ".join(f"{x['label']} -> {x['channel_title']}" for x in accs) or "none yet"))
    except SystemExit:
        rows.append(("youtube client", "not set (needed only to publish)"))
    rows.append(("instagram", "configured" if cfg["instagram_access_token"] else "off"))
    try:
        import faster_whisper  # noqa
        rows.append(("faster-whisper", "installed (exact narration cuts + voice check)"))
    except Exception:
        rows.append(("faster-whisper", "not installed (pip install reelforge[check])"))
    rows.append(("cloudflared", shutil.which("cloudflared") or "not found (Instagram without S3 needs it)"))
    rows.append(("config", C.CONFIG))
    for k, v in rows:
        print(f"  {k:18s} {v}")


def cmd_config(a):
    if a.action == "show":
        print(json.dumps(C.masked(C.load()), indent=1))
    elif a.action == "set":
        if not a.key or a.value is None:
            sys.exit("usage: reelforge config set <key> <value>")
        C.set_value(a.key, a.value)
        print(f"  {a.key} saved to {C.CONFIG}")
    elif a.action == "get":
        print(C.masked(C.load()).get(a.key))
    elif a.action == "path":
        print(C.CONFIG)


def cmd_scan(a):
    from . import scan
    repo = scan.resolve_repo(a.repo)
    project = C.project_dir(repo)
    out = scan.scan(repo, project, brief=a.brief, log=_log)
    if a.url:
        routes = [r["route"] for r in out.get("routes", [])][: a.max_shots]
        routes = routes or ["/"]
        scan.screenshots(project, a.url, routes, log=_log)
    print()
    for f in out["features"]:
        print(f"  {f['id']:28s} {f['name']}  ({len(f.get('facts', []))} facts)")


def cmd_features(a):
    from . import scan
    repo = scan.resolve_repo(a.repo)
    d = C.read_json(os.path.join(C.project_dir(repo), "features.json"))
    if not d:
        sys.exit("not scanned yet: reelforge scan <repo>")
    for f in d["features"]:
        print(f"\n{f['id']}  -  {f['name']}\n  {f['one_line']}")
        for i, fact in enumerate(f.get("facts", [])):
            print(f"   [{i}] {fact['text']}   <- {fact['evidence']}")


def cmd_make(a):
    from . import make, scan
    repo = scan.resolve_repo(a.repo)
    meta = make.make(repo, feature_id=a.feature, prompt=a.prompt or "", aspect=a.aspect,
                     platform=a.platform, seconds=a.seconds, voice=a.voice, veo=a.veo,
                     captions=not a.no_captions, log=_log, base_url=a.url)
    print(f"\njob {meta['id']}  {'all checks passed' if meta['check']['ok'] else 'CHECKS FAILED - review before publishing'}")


def cmd_check(a):
    """Re-run the rule checks on an existing render - no re-render, no spend.
    Useful when the checker improves or a render was reviewed by hand."""
    from . import check, make, plan, scan
    repo = scan.resolve_repo(a.repo)
    project = C.project_dir(repo)
    job_dir = os.path.join(project, "out", a.job)
    sb = C.read_json(os.path.join(job_dir, "storyboard.json"))
    if not sb:
        sys.exit(f"no job {a.job}")
    if not os.path.isdir(os.path.join(job_dir, "frames")):
        sys.exit("frames were cleaned up; re-render to check again")
    units = [u for _k, u in plan.units(sb)]
    report = check.run(job_dir, sb, units, log=_log)
    make.save_meta(project, a.job, {"check": report})
    print("all checks passed" if report["ok"] else "CHECKS FAILED")


def cmd_jobs(a):
    from . import make, scan
    repo = scan.resolve_repo(a.repo)
    for m in make.list_jobs(C.project_dir(repo)):
        pub = ",".join(p["platform"] for p in m.get("published", [])) or "-"
        ok = "ok " if (m.get("check") or {}).get("ok") else "chk"
        print(f"  {m['id']:40s} {m['aspect']:5s} {m['duration']:5.1f}s {ok} {pub:12s} {m['title'][:40]}")


def cmd_publish(a):
    from . import make, scan
    repo = scan.resolve_repo(a.repo)
    project = C.project_dir(repo)
    m = make.job_meta(project, a.job)
    if not m:
        sys.exit(f"no job {a.job}")
    job_dir = os.path.join(project, "out", a.job)
    file = os.path.join(job_dir, m["file"])
    meta = m.get("meta", {})
    if a.title:
        meta["youtube_title"] = a.title
    if not m.get("check", {}).get("ok") and not a.force:
        sys.exit("this render failed its checks. Review it, then pass --force to publish anyway.")
    results = []
    if a.youtube:
        from .publish import youtube
        label = youtube.resolve(a.youtube)
        if any(p["platform"] == "youtube" and p.get("account") == label for p in m.get("published", [])) and not a.force:
            sys.exit(f"already on YouTube ({label}); pass --force to upload again")
        if not meta.get("youtube_title"):
            sys.exit("no title. Edit meta in the UI or pass --title")
        r = youtube.upload(label, file, meta["youtube_title"], meta.get("youtube_description", ""),
                           meta.get("tags", []), privacy=a.privacy or meta.get("privacy", "private"),
                           short=(m["aspect"] in ("9:16", "4:5")), thumb=os.path.join(job_dir, m.get("thumb", "")), log=_log)
        results.append(r); print(f"  YouTube: {r['url']}  ({r['privacy']})")
    if a.instagram:
        from .publish import instagram
        if any(p["platform"] == "instagram" for p in m.get("published", [])) and not a.force:
            sys.exit("already on Instagram; pass --force to post again")
        r = instagram.publish_reel(file=file, url=a.url, caption=meta.get("instagram_caption") or meta.get("youtube_title", ""), log=_log)
        results.append(r); print(f"  Instagram: {r['url']}")
    if results:
        make.save_meta(project, a.job, {"published": m.get("published", []) + results, "meta": meta})
    else:
        print("nothing to do: pass --youtube <label> and/or --instagram")


def cmd_accounts(a):
    from .publish import youtube
    if a.action == "list":
        accs = youtube.accounts(refresh=a.refresh)
        if not accs:
            print("  no YouTube accounts yet: reelforge accounts add --label <name>")
        for x in accs:
            print(f"  {x['label']:16s} {x['channel_title']:36s} {x['channel_id']}  ({x.get('videos', 0)} videos)")
    elif a.action == "add":
        if not a.label:
            sys.exit("--label is required, e.g. --label personal")
        print("  a browser window will open on this machine; choose the Google account AND the channel")
        x = youtube.add_account(a.label)
        print(f"  saved {x['label']} -> {x['channel_title']} ({x['channel_id']})")
    elif a.action == "import":
        if not (a.label and a.path):
            sys.exit("usage: reelforge accounts import <token.json> --label <name>")
        x = youtube.import_token(a.path, a.label)
        print(f"  imported {x['label']} -> {x['channel_title']} ({x['channel_id']})")
    elif a.action == "remove":
        youtube.remove_account(a.label); print("  removed")


def cmd_tune(a):
    from . import memory, scan
    repo = scan.resolve_repo(a.repo)
    project = C.project_dir(repo)
    if a.note == "list" or not a.note:
        for i, n in enumerate(memory.load(project)["notes"]):
            print(f"  [{i}] {n['at']}  {n['text']}")
        return
    if a.note == "rm":
        memory.remove(project, int(a.extra or 0)); print("  removed"); return
    memory.add(project, a.note)
    print(f"  remembered for this project: {a.note}")


def cmd_ui(a):
    from . import ui
    ui.serve(repo=a.repo, port=a.port or C.load()["ui_port"], open_browser=not a.no_open)


# ---------------------------------------------------------------- parser

def main(argv=None):
    p = argparse.ArgumentParser(prog="reelforge", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd")

    sub.add_parser("doctor").set_defaults(fn=cmd_doctor)

    c = sub.add_parser("config"); c.add_argument("action", choices=["show", "set", "get", "path"])
    c.add_argument("key", nargs="?"); c.add_argument("value", nargs="?"); c.set_defaults(fn=cmd_config)

    s = sub.add_parser("scan"); s.add_argument("repo"); s.add_argument("--url", help="running app, for real screenshots")
    s.add_argument("--brief", help="anything the team wants the scanner to know"); s.add_argument("--max-shots", type=int, default=8)
    s.set_defaults(fn=cmd_scan)

    f = sub.add_parser("features"); f.add_argument("repo"); f.set_defaults(fn=cmd_features)

    m = sub.add_parser("make"); m.add_argument("repo")
    m.add_argument("--feature"); m.add_argument("--prompt")
    m.add_argument("--aspect", default="9:16", choices=["9:16", "16:9", "1:1", "4:5"])
    m.add_argument("--platform", default="shorts", choices=["shorts", "reels", "tiktok", "youtube", "linkedin"])
    m.add_argument("--seconds", type=int, default=30)
    m.add_argument("--voice", default="gemini", choices=["gemini", "edge"])
    m.add_argument("--veo", action="store_true", help="live-action hook plate (needs Veo key; billed per second)")
    m.add_argument("--no-captions", action="store_true"); m.add_argument("--url", help="running app, to capture real screens for this feature")
    m.set_defaults(fn=cmd_make)

    j = sub.add_parser("jobs"); j.add_argument("repo"); j.set_defaults(fn=cmd_jobs)

    k = sub.add_parser("check"); k.add_argument("repo"); k.add_argument("job"); k.set_defaults(fn=cmd_check)

    u = sub.add_parser("publish"); u.add_argument("repo"); u.add_argument("job")
    u.add_argument("--youtube", metavar="LABEL_OR_CHANNEL"); u.add_argument("--instagram", action="store_true")
    u.add_argument("--privacy", choices=["private", "unlisted", "public"]); u.add_argument("--title")
    u.add_argument("--url", help="already-hosted URL of the video (Instagram)"); u.add_argument("--force", action="store_true")
    u.set_defaults(fn=cmd_publish)

    ac = sub.add_parser("accounts"); ac.add_argument("action", choices=["list", "add", "import", "remove"])
    ac.add_argument("path", nargs="?"); ac.add_argument("--label"); ac.add_argument("--refresh", action="store_true")
    ac.set_defaults(fn=cmd_accounts)

    t = sub.add_parser("tune"); t.add_argument("repo"); t.add_argument("note", nargs="?"); t.add_argument("extra", nargs="?")
    t.set_defaults(fn=cmd_tune)

    w = sub.add_parser("ui"); w.add_argument("--repo"); w.add_argument("--port", type=int); w.add_argument("--no-open", action="store_true")
    w.set_defaults(fn=cmd_ui)

    a = p.parse_args(argv)
    if not a.cmd:
        p.print_help(); return 0
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
