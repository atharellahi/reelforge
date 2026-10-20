"""The pipeline, end to end: feature -> storyboard -> pictures -> voice ->
frames -> mp4 -> checks. One function, so the CLI and the UI do the same thing.

Order matters: the voice is recorded BEFORE the timeline is built, because the
picture is timed from the narration rather than the narration squeezed into a
guessed duration.
"""
import os
import re
import time

from . import assets, check, config as C, gemini, memory, narrate, plan, render, scan


def pick_feature(project, features, feature_id=None, prompt=""):
    feats = features.get("features", [])
    if feature_id:
        for f in feats:
            if f["id"] == feature_id:
                return f
        raise SystemExit(f"no feature {feature_id!r}. Known: {', '.join(f['id'] for f in feats)}")
    if not prompt:
        if not feats:
            raise SystemExit("no features scanned and no prompt given")
        return feats[0]
    # a free prompt: let the writer pick the closest scanned feature, or build
    # an ad-hoc one whose facts are the team's own words (evidence: brief)
    menu = "\n".join(f"{f['id']}: {f['name']} - {f['one_line']}" for f in feats) or "(none)"
    r = gemini.text(
        f"Features:\n{menu}\n\nRequest: {prompt}\n\n"
        "Return JSON {\"id\": \"<feature id or none>\"} - the single feature this request is about, "
        "or none if it is about something not listed.", as_json=True, temperature=0)
    fid = (r or {}).get("id")
    for f in feats:
        if f["id"] == fid:
            return f
    facts = [{"text": s.strip(), "evidence": "brief"} for s in re.split(r"[.\n;]+", prompt) if len(s.strip()) > 12]
    return {"id": "custom_" + re.sub(r"[^a-z0-9]+", "_", prompt.lower())[:24].strip("_"),
            "name": prompt[:60], "one_line": prompt, "facts": facts, "routes": [], "visual": ""}


def list_jobs(project):
    out = os.path.join(project, "out")
    jobs = []
    for d in sorted(os.listdir(out), reverse=True) if os.path.isdir(out) else []:
        m = C.read_json(os.path.join(out, d, "meta.json"))
        if m:
            jobs.append(m)
    return jobs


def job_meta(project, job_id):
    return C.read_json(os.path.join(project, "out", job_id, "meta.json"))


def save_meta(project, job_id, patch):
    p = os.path.join(project, "out", job_id, "meta.json")
    m = C.read_json(p, {})
    for k, v in patch.items():
        if k == "meta" and isinstance(v, dict):
            m.setdefault("meta", {}).update(v)
        else:
            m[k] = v
    C.write_json(p, m)
    return m


def make(repo, feature_id=None, prompt="", aspect="9:16", platform="shorts", seconds=30,
         voice="gemini", veo=False, captions=True, log=print, job_id=None, base_url=None):
    t0 = time.time()
    project = C.project_dir(repo)
    features = C.read_json(os.path.join(project, "features.json"))
    if not features:
        log("no features.json yet - scanning the repo first")
        features = scan.scan(repo, project, log=log)
    feature = pick_feature(project, features, feature_id, prompt)
    log(f"feature: {feature['name']}  ({len(feature.get('facts', []))} facts)")

    shots = []
    if base_url and feature.get("routes"):
        shots = scan.screenshots(project, base_url, feature["routes"][:3], log=log)
    sd = os.path.join(project, "shots")
    shot_routes = sorted({f.rsplit("_", 1)[0] for f in os.listdir(sd)}) if os.path.isdir(sd) else []
    shot_hint = [f"/{s.replace('_', '/')}" if s != "home" else "/" for s in shot_routes]

    log("writing storyboard")
    sb = plan.write(project, feature, brief=prompt, aspect=aspect, platform=platform,
                    seconds=seconds, shots=shot_hint)
    log(f"  {len(sb['beats'])} beats, hook={sb['hook']['visual']}, {sb['word_count']}/{sb['word_budget']} words")

    job_id = job_id or time.strftime("%Y%m%d-%H%M%S") + "_" + re.sub(r"[^a-z0-9]+", "-", feature["id"])[:30]
    job_dir = os.path.join(project, "out", job_id)
    os.makedirs(job_dir, exist_ok=True)

    log("imagery")
    assets.ensure(project, sb, log=log)

    if veo:
        try:
            plate = assets.veo_plate(sb["hook"].get("image_prompt") or sb["hook"]["text"],
                                     os.path.join(job_dir, "plate.mp4"), log=log)
            n = assets.plate_frames(plate, os.path.join(job_dir, "plate"), 30, C.find_ffmpeg())
            sb["hook"]["plate_frames"] = n
        except Exception as e:
            log(f"  veo skipped: {str(e)[:100]}")

    log("narration")
    units = [u for _k, u in plan.units(sb)]
    vo, times, engine = narrate.narrate(job_dir, units, prefer=voice, log=log)
    sb["lead"] = 0.3
    sb["captions_on"] = bool(captions)
    plan.build_timeline(sb, times, lead=sb["lead"])

    log("render")
    final = render.render(project, job_dir, sb, fps=30, log=log)

    log("checks")
    report = check.run(job_dir, sb, units, log=log)

    meta = {
        "id": job_id, "feature_id": feature["id"], "feature": feature["name"],
        "title": sb.get("title") or feature["name"], "created": time.strftime("%Y-%m-%d %H:%M"),
        "aspect": aspect, "platform": platform, "duration": sb["duration"],
        "file": "final.mp4", "thumb": "thumb.jpg", "voice": engine, "veo": bool(sb["hook"].get("plate_frames")),
        "meta": {
            "youtube_title": (sb.get("meta") or {}).get("youtube_title", "")[:100],
            "youtube_description": (sb.get("meta") or {}).get("youtube_description", "")[:5000],
            "tags": ((sb.get("meta") or {}).get("tags") or [])[:30],
            "instagram_caption": (sb.get("meta") or {}).get("instagram_caption", "")[:2200],
            "privacy": "private",
        },
        "check": report, "published": [], "seconds_to_make": round(time.time() - t0),
        "warnings": sb.get("warnings", []),
    }
    for w in meta["warnings"]:
        log(f"  warning: {w}")
    C.write_json(os.path.join(job_dir, "meta.json"), meta)
    log(f"done in {meta['seconds_to_make']}s -> {final}")
    return meta
