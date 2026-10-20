"""Does the render meet the rules? Measured, not eyeballed.

Three checks that correspond to rules which failed review repeatedly:
  hook     - something other than text must change in the first 1.5 seconds
  motion   - nothing may hold still for more than ~1.5 seconds
  voice    - what was spoken is what was scripted (optional, needs whisper)
"""
import difflib
import os
import re


def _grey(path, width):
    from PIL import Image
    im = Image.open(path).convert("L")
    h = max(1, int(im.height * width / im.width))
    return im.resize((width, h))


def _diff(a, b):
    from PIL import ImageChops
    d = ImageChops.difference(a, b)
    px = list(d.getdata())
    return sum(px) / len(px)


def hook(frames_dir, fps):
    """Compare 0.3s and 1.5s at 64px wide. At that scale typed text barely
    registers, so a high difference means the VISUAL moved, which is the rule."""
    a = os.path.join(frames_dir, f"f{int(0.3 * fps):05d}.jpg")
    b = os.path.join(frames_dir, f"f{int(1.5 * fps):05d}.jpg")
    if not (os.path.exists(a) and os.path.exists(b)):
        return {"ok": False, "why": "frames missing"}
    d = _diff(_grey(a, 64), _grey(b, 64))
    return {"ok": d >= 0.8, "diff": round(d, 2), "why": "visual changes in the first 1.5s" if d >= 0.8 else "hook is static apart from text"}


def motion(frames_dir, fps, duration):
    """Sample 4 frames a second; a step below 0.3 is a frozen frame. The fades
    at either end are excluded. 0.15 let a 3% drift pass that looked frozen to
    the eye; a hand-built short that read as alive never dropped below 0.37."""
    step = max(1, fps // 4)
    files = sorted(f for f in os.listdir(frames_dir) if f.endswith(".jpg"))
    total = len(files)
    lo, hi = int(0.4 * fps), total - int(0.5 * fps)
    prev, stills, mins = None, [], []
    for i in range(lo, hi, step):
        g = _grey(os.path.join(frames_dir, files[i]), 270)
        if prev is not None:
            d = _diff(prev, g)
            mins.append(d)
            if d < 0.3:
                stills.append(round(i / fps, 2))
        prev = g
    return {"ok": not stills, "min_step": round(min(mins), 3) if mins else None,
            "still_at": stills[:12], "why": "frame never freezes" if not stills else f"{len(stills)} frozen steps"}


def voice(vo_wav, units):
    try:
        from faster_whisper import WhisperModel
    except Exception:
        return {"ok": None, "why": "faster-whisper not installed (pip install reelforge[check])"}
    model = WhisperModel("base.en", device="cpu", compute_type="int8")
    segs, _ = model.transcribe(vo_wav)
    heard = " ".join(s.text for s in segs)
    norm = lambda s: " ".join(re.findall(r"[a-z0-9']+", s.lower().replace(".com", " dot com").replace("/", " slash ")))
    sim = difflib.SequenceMatcher(None, norm(" ".join(units)), norm(heard)).ratio()
    return {"ok": sim >= 0.80, "similarity": round(sim, 2), "why": "narration matches script" if sim >= 0.8 else "narration drifted from script"}


def run(job_dir, sb, units, log=print):
    fps = sb.get("fps", 30)
    frames = os.path.join(job_dir, "frames")
    report = {"hook": hook(frames, fps), "motion": motion(frames, fps, sb["duration"])}
    vo = os.path.join(job_dir, "vo.wav")
    if os.path.exists(vo):
        report["voice"] = voice(vo, units)
    for k, v in report.items():
        mark = "PASS" if v.get("ok") else ("skip" if v.get("ok") is None else "FAIL")
        extra = {kk: vv for kk, vv in v.items() if kk not in ("ok", "why")}
        log(f"  {k:7s} {mark:4s} {v.get('why')} {extra if extra else ''}")
    report["ok"] = all(v.get("ok") is not False for v in report.values())
    return report
