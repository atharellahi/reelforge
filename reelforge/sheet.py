"""A contact sheet of a render, so whoever wrote the storyboard can LOOK.

One image, frames sampled at the moments that matter: 0.3s and 1.5s (the
hook rule), then the entry and the middle of every beat. Every bug found
while building reelforge was found this way, not from a log.
"""
import json
import os


def make(job_dir, out=None, tile_h=420):
    from PIL import Image, ImageDraw
    sb = json.load(open(os.path.join(job_dir, "storyboard.json"), encoding="utf-8"))
    tl, fps = sb["timeline"], sb.get("fps", 30)
    frames = os.path.join(job_dir, "frames")
    if not os.path.isdir(frames):
        raise SystemExit("frames were cleaned up; re-render first")
    times = [0.3, 1.5]
    for i, t in enumerate(tl):
        d = t["end"] - t["start"]
        times += [t["start"] + min(0.9, d * 0.3), t["start"] + d * 0.65]
    times = sorted(set(round(x, 1) for x in times))
    W, H = sb.get("width", 1080), sb.get("height", 1920)
    tw = int(tile_h * W / H)
    tiles = []
    for t in times:
        f = os.path.join(frames, f"f{int(t * fps):05d}.jpg")
        if not os.path.exists(f):
            continue
        im = Image.open(f).convert("RGB").resize((tw, tile_h))
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, 64, 22], fill=(0, 0, 0))
        d.text((5, 5), f"{t:.1f}s", fill=(255, 255, 255))
        tiles.append(im)
    cols = 8 if W < H else 4
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (tw + 6), rows * (tile_h + 6)), (40, 40, 40))
    for i, im in enumerate(tiles):
        sheet.paste(im, ((i % cols) * (tw + 6) + 3, (i // cols) * (tile_h + 6) + 3))
    out = out or os.path.join(job_dir, "sheet.jpg")
    sheet.save(out, quality=86)
    return out, times
