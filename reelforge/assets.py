"""Give the storyboard pictures.

Priority for any slot that shows the product:
  1. a real screenshot the scan captured (nothing beats the real UI)
  2. an image generated from the beat's prompt (cached by prompt, so a
     re-render never pays twice)

Every generated image is portrait or landscape to FIT ITS SLOT, because a
square image cropped to a tall card loses the shoes and a wide image cropped
to a phone loses the subject.
"""
import hashlib
import os
import re
import subprocess
import time

from . import config as C
from . import gemini

# Positive direction first, one short exclusion last. A prompt that is mostly
# prohibitions makes the image model return nothing at all.
NO_TEXT = (" A real-world photograph of people, places and objects: photorealistic, "
           "editorial quality, soft natural light, calm composition with generous empty "
           "space. Plain surfaces with no writing on them; no screens or devices in frame.")


def _slot_aspect(sb, kind):
    portrait = sb.get("aspect", "9:16") in ("9:16", "4:5")
    if kind == "hook":
        return "2:3" if portrait else "16:9"
    if kind == "card":
        return "2:3"
    return "2:3" if portrait else "3:2"


def _cached(project, prompt, aspect, log):
    key = hashlib.sha1((aspect + "|" + prompt).encode()).hexdigest()[:14]
    rel = f"assets/gen_{key}.jpg"
    path = os.path.join(project, rel)
    if not os.path.exists(path):
        log(f"  image: {prompt[:64]}…")
        im = gemini.image(prompt + NO_TEXT, aspect=aspect)
        im.save(path, "JPEG", quality=90)
    return rel


def _shot_for(project, route, portrait):
    if not route:
        return ""
    slug = re.sub(r"[^a-z0-9]+", "_", route.lower()).strip("_") or "home"
    kind = "mobile" if portrait else "desktop"
    rel = f"shots/{slug}_{kind}.png"
    return rel if os.path.exists(os.path.join(project, rel)) else ""


def ensure(project, sb, log=print):
    brand = C.read_json(os.path.join(project, "brand.json"), {})
    portrait = sb.get("aspect", "9:16") in ("9:16", "4:5")

    h = sb["hook"]
    imgs = []
    n_hook = {"cards": 3, "grid": 6, "clash": 2}.get(h.get("visual"), 1)
    base = h.get("image_prompt") or f"Lifestyle photograph that dramatises: {h.get('text','')}"
    # "a variation" alone returns the same picture three times; the directions
    # have to differ in a way the model cannot ignore
    angles = ["Wide establishing shot of the whole scene.",
              "Close detail shot: texture, hands, fabric, a single object.",
              "A person in the scene, candid, mid-movement, natural light.",
              "Overhead flat-lay of the objects involved.",
              "Shot through a doorway or window, the scene partly framed.",
              "Golden-hour exterior version of the same idea."]
    if h.get("image_prompts"):
        imgs = [_cached(project, p, _slot_aspect(sb, "hook"), log) for p in h["image_prompts"][:8]]
    else:
        for i in range(n_hook):
            variant = f"{base} {angles[i % len(angles)]}"
            imgs.append(_cached(project, variant, _slot_aspect(sb, "hook"), log))
    h["images"] = imgs

    for b in sb["beats"]:
        t = b.get("type")
        # any beat may ask for a list of photographs by prompt (custom scenes
        # usually do); they arrive as b.images in the same order
        if b.get("image_prompts"):
            b["images"] = [_cached(project, p, _slot_aspect(sb, "card"), log) for p in b["image_prompts"][:8]]
        if t == "custom":
            if b.get("image_prompt") and not b.get("image"):
                b["image"] = _cached(project, b["image_prompt"], _slot_aspect(sb, "beat"), log)
            for it in b.get("items", []):
                if it.get("image_prompt") and not it.get("image"):
                    it["image"] = _cached(project, it["image_prompt"], _slot_aspect(sb, "card"), log)
            continue
        if t == "screen":
            shot = _shot_for(project, b.get("screenshot"), portrait)
            if shot:
                b["image"] = shot; b["real"] = True
            else:
                # No real screen: the engine builds an HTML mock (brand lockup,
                # heading, the callout labels as chips) around a LIFESTYLE
                # image. Asking the model to draw an app screen produced fake
                # UI with garbled text every time.
                b["image"] = _cached(project, b.get("image_prompt") or b.get("heading", ""), "2:3", log)
                b["real"] = False
        elif t in ("cards", "list"):
            for it in b.get("items", []):
                p = it.get("image_prompt") or f"{it.get('title','')} - {it.get('sub','')}"
                it["image"] = _cached(project, p, _slot_aspect(sb, "card"), log)
            if not b.get("items"):
                b["image"] = _cached(project, b.get("image_prompt") or b.get("heading", ""), _slot_aspect(sb, "beat"), log)
        else:
            b["image"] = _cached(project, b.get("image_prompt") or b.get("heading", ""), _slot_aspect(sb, "beat"), log)

    # the CTA fans the images already made, so nothing new is spent on it
    pool = list(imgs)
    for b in sb["beats"]:
        pool += [it["image"] for it in b.get("items", []) if it.get("image")]
        if b.get("image") and not b.get("real"):
            pool.append(b["image"])
    seen = []
    for p in pool:
        if p not in seen:
            seen.append(p)
    sb["cta"]["images"] = seen[:5]
    sb["brand"] = brand
    return sb


# ------------------------------------------------------------------ Veo

def veo_plate(prompt, out_mp4, seconds=4, log=print):
    """Optional live-action hook plate. Only runs when a Veo key and project are
    configured; billed per second, so it is never on by default."""
    cfg = C.load()
    if not (cfg["veo_api_key"] and cfg["veo_project"]):
        raise SystemExit("Veo needs veo_api_key and veo_project in config.")
    from google import genai
    from google.genai import types
    c = genai.Client(vertexai=True, api_key=cfg["veo_api_key"],
                     project=cfg["veo_project"], location=cfg["veo_location"])
    log(f"  veo: {prompt[:70]}…")
    op = c.models.generate_videos(
        model=cfg["veo_model"], prompt=prompt,
        config=types.GenerateVideosConfig(aspect_ratio="9:16", duration_seconds=seconds,
                                          number_of_videos=1, resolution="720p"))
    for _ in range(120):
        if op.done:
            break
        time.sleep(5)
        op = c.operations.get(op)
    vids = getattr(op.result, "generated_videos", None) or []
    if not vids:
        raise RuntimeError("veo returned no video")
    c.files.download(file=vids[0].video)
    vids[0].video.save(out_mp4)
    return out_mp4


def plate_frames(mp4, out_dir, fps, ffmpeg):
    """Deterministic frames so the scene can pick one by time. A <video>
    element cannot be seeked frame-accurately from a screenshot loop."""
    os.makedirs(out_dir, exist_ok=True)
    subprocess.run([ffmpeg, "-v", "error", "-y", "-i", mp4, "-vf", f"fps={fps}",
                    os.path.join(out_dir, "p%05d.jpg")], check=True)
    return len([f for f in os.listdir(out_dir) if f.endswith(".jpg")])
