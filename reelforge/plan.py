"""Turn a feature into a storyboard: what is said, what is shown, when.

The storyboard is the contract between the writer (Gemini) and the renderer
(scene.html). Everything the renderer draws is in here, and every claim in here
cites a fact from features.json - that is the claims rule, enforced at write
time rather than hoped for.
"""
import math
import os
import re

from . import config as C
from . import gemini, memory

RULES = open(os.path.join(os.path.dirname(__file__), "rules", "VIDEO_RULES.md"), encoding="utf-8").read()

WPM = 150
BEAT_TYPES = ("screen", "cards", "stat", "list", "quote")
HOOK_VISUALS = ("counter", "cards", "grid", "clash", "typed")

SYSTEM = """You write short product videos that a motion-graphics renderer will
build exactly as specified. You are given the product's FACTS (with evidence),
its brand, the house rules, team preferences, and a brief. Produce ONE storyboard
as strict JSON.

Non-negotiable:
- Every beat's `fact_ids` must list the facts it relies on. A beat with no fact
  is cut. Never claim anything not in the facts.
- The HOOK is a visual, not a sentence on a background. Pick a hook visual that
  dramatises the line. `counter` needs a number worth counting to.
- Narration is ONE continuous take later, so write it to be SPOKEN: short
  sentences, no bullet fragments, no URLs spelled with slashes (say "at drezily
  dot com slash stylist" style only in the CTA line).
- Budget: total narration <= word_budget words. Count.
- Headings <= 7 words. Subheads <= 14 words. Two lines maximum on screen.
- Each beat is 3-7 seconds of speech; a transformation beat may be 8-12.
- Voice follows the scene: each beat has its own line. Never let one line span
  two beats.
- Show the outcome, not the clicks.
- The hook `line` is ONE spoken sentence, at most 14 words. The hook `text` is
  the CLAIM on screen - a question or a bold statement the viewer feels - never
  the feature's name or a label.
- `stat` is allowed ONLY when a cited fact contains that exact number. Never
  invent a percentage or a count.
- Do not repeat the product name in every line. The hook names the problem;
  the beats show what the user gets; the CTA names the product once.
- Every `image_prompt` describes a PHOTOGRAPH of people, places or objects in
  the real world - a woman choosing a coat, a rail of clothes in morning light.
  Never a screen, phone, monitor, app, grid, chart, poster or any written word.
  The renderer draws the UI itself; the photograph is the human context.
- `items` (cards/list) must be taken from the cited facts - a real label, a
  real behaviour - never generic slogans like "Always on trend".

JSON shape:
{
 "title": "internal title",
 "hook": {"line": "spoken hook, 1-2 sentences",
          "visual": "counter|cards|grid|clash|typed",
          "text": "on-screen words, <= 9 words",
          "value": 40, "unit": "min",            // counter only
          "image_prompt": "photoreal image for the hook, no text in image"},
 "beats": [
   {"type": "screen|cards|stat|list|quote",
    "line": "one spoken sentence or two short ones",
    "heading": "<= 7 words", "sub": "<= 14 words or empty",
    "fact_ids": [0,2],
    "screenshot": "/route or empty",          // screen: prefer a real route
    "callouts": [{"label": "<= 4 words", "x": 0.5, "y": 0.4}],  // screen, 0-3 items, fractions
    "items": [{"title": "<= 4 words", "sub": "<= 8 words", "image_prompt": "..."}],  // cards/list, 2-4
    "value": 1, "unit": "", "label": "<= 6 words",          // stat
    "image_prompt": "photoreal supporting image, no text in image"}
 ],
 "cta": {"line": "spoken CTA with the url said naturally", "text": "<= 6 words", "url": "domain/path"},
 "meta": {"youtube_title": "<= 70 chars, specific, no clickbait",
          "youtube_description": "2-4 sentences then a blank line then 5-10 hashtags",
          "tags": ["8-15 tags"], "instagram_caption": "<= 2200 chars, hashtags at end"}
}"""


def _facts_block(feature):
    lines = []
    for i, f in enumerate(feature.get("facts", [])):
        lines.append(f"[{i}] {f.get('text')}  (evidence: {f.get('evidence')})")
    return "\n".join(lines)


def write(project, feature, brief="", aspect="9:16", platform="shorts", seconds=30, shots=None):
    brand = C.read_json(os.path.join(project, "brand.json"), {})
    word_budget = int(seconds / 60 * WPM * 0.9)
    shots = shots or []
    prompt = f"""# Product
{brand.get('name','')} - {brand.get('tagline','')}
URL: {brand.get('url') or '(ask the brief)'}

# Feature
{feature.get('name')}: {feature.get('one_line')}
Why it matters: {feature.get('why_it_matters','')}
Routes: {', '.join(feature.get('routes', []) or [])}
What is on screen: {feature.get('visual','')}

# Facts (cite by index)
{_facts_block(feature)}

# Real screenshots available (use their route in `screenshot` when relevant)
{chr(10).join(shots) or '(none - screens will be generated as illustrative mockups)'}

# Format
aspect {aspect}, platform {platform}, target {seconds}s, word_budget {word_budget}

# Brief from the team
{brief or '(none)'}

{memory.as_prompt(project)}

# House rules (abridged)
{RULES[:6000]}
"""
    sb = gemini.text(prompt, system=SYSTEM, as_json=True, temperature=0.7)
    return normalize(sb, feature, aspect, platform, seconds, word_budget, project=project)


def _words(s):
    return len(re.findall(r"[A-Za-z0-9']+", s or ""))


def _corpus(project, feature):
    """Everything the product is known to say: this feature's facts, every
    feature's facts, and the UI strings the scan read from the code."""
    parts = [f.get("text", "") for f in feature.get("facts", [])]
    allf = C.read_json(os.path.join(project, "features.json"), {}) or {}
    for f in allf.get("features", []):
        parts += [x.get("text", "") for x in f.get("facts", [])]
        parts += [f.get("name", ""), f.get("one_line", "")]
    parts += (allf.get("product") or {}).values()
    parts += C.read_json(os.path.join(project, "ui_strings.json"), []) or []
    return " ".join(str(p) for p in parts).lower()


def _traceable(label, corpus):
    """A label is allowed if the product actually says it: the whole phrase, or
    every meaningful word of it, appears in the corpus."""
    s = (label or "").strip().lower()
    if not s:
        return False
    if s in corpus:
        return True
    words = [w for w in re.findall(r"[a-z0-9']+", s) if len(w) > 3]
    return bool(words) and all(w in corpus for w in words)


def normalize(sb, feature, aspect, platform, seconds, word_budget, project=None):
    facts = feature.get("facts", [])
    corpus = _corpus(project, feature) if project else " ".join(f.get("text", "") for f in facts).lower()
    sb.setdefault("hook", {}); sb.setdefault("cta", {}); sb.setdefault("meta", {})
    if sb["hook"].get("visual") not in HOOK_VISUALS:
        sb["hook"]["visual"] = "cards"
    beats = []
    for b in sb.get("beats", []):
        ids = [i for i in (b.get("fact_ids") or []) if isinstance(i, int) and 0 <= i < len(facts)]
        if not ids and facts:
            continue  # the claims rule: no fact, no beat
        if b.get("type") not in BEAT_TYPES:
            b["type"] = "screen" if b.get("screenshot") else "cards"
        b["fact_ids"] = ids
        b["facts"] = [facts[i]["text"] for i in ids]
        # a number on screen must exist in a cited fact; a made-up "100%" is
        # exactly the kind of claim the rules forbid
        if b["type"] == "stat":
            num = str(b.get("value", "")).strip()
            if not num or not any(num in f for f in b["facts"]):
                b["type"] = "quote"
                b["heading"] = b.get("label") or b.get("heading") or ""
        b["heading"] = " ".join((b.get("heading") or "").split()[:8])
        b["sub"] = " ".join((b.get("sub") or "").split()[:16])
        # labels the viewer reads must exist in the product. "Boho Chic" on a
        # beat about daily edits was a slogan the writer liked, not a fact.
        kept, dropped = [], []
        for it in (b.get("items") or [])[:4]:
            (kept if _traceable(it.get("title"), corpus) else dropped).append(it)
        b["items"] = kept
        b["dropped_items"] = [d.get("title") for d in dropped]
        b["callouts"] = [c for c in (b.get("callouts") or [])[:3] if _traceable(c.get("label"), corpus)]
        if b["type"] in ("cards", "list") and not b["items"]:
            b["type"] = "cards"  # single image + heading; the beat still stands on its fact
        beats.append(b)
    if not beats:
        raise RuntimeError("the writer produced no beat that cites a fact; add facts or a brief")
    sb["beats"] = beats[:6]
    total = _words(sb["hook"].get("line")) + sum(_words(b.get("line")) for b in sb["beats"]) + _words(sb["cta"].get("line"))
    sb["word_count"] = total
    sb["word_budget"] = word_budget
    if total > word_budget * 1.25:
        # drop the weakest beats rather than ship a rushed voice
        while len(sb["beats"]) > 2 and total > word_budget * 1.15:
            dropped = sb["beats"].pop()
            total -= _words(dropped.get("line"))
        sb["word_count"] = total
    sb["aspect"] = aspect
    sb["platform"] = platform
    sb["feature_id"] = feature.get("id")
    sb["feature_name"] = feature.get("name")
    return sb


# ------------------------------------------------------------- timeline

def units(sb):
    """The spoken units, in order. One per visual beat, so the voice changes
    exactly when the picture does."""
    u = [("hook", sb["hook"]["line"])]
    u += [("beat", b["line"]) for b in sb["beats"]]
    u += [("cta", sb["cta"]["line"])]
    return u


def build_timeline(sb, unit_times, lead=0.30, tail=0.9):
    """Place every beat from the MEASURED narration. unit_times is
    [(start, end), ...] aligned to units(sb), in raw-audio seconds.

    The mix delays the voice by `lead`, so line i is heard at s_i + lead. The
    picture for beat i cuts at s_i - so the new picture is on screen `lead`
    seconds before its line begins. Beats are CONTIGUOUS: each ends exactly
    where the next starts. An earlier version added `lead` to both the end and
    the following start, which left 0.3s between beats where nothing moved -
    the one frozen step the motion check caught.
    """
    starts = [0.0] + [max(s, 0.0) for s, _e in unit_times[1:]]
    for i in range(1, len(starts)):
        starts[i] = max(starts[i], starts[i - 1] + 1.2)  # a beat is never shorter than 1.2s
    last_end = unit_times[-1][1] + lead + tail
    tl = []
    for i, s in enumerate(starts):
        e = starts[i + 1] if i + 1 < len(starts) else last_end
        tl.append({"start": round(s, 3), "end": round(e, 3)})
    sb["timeline"] = tl
    sb["duration"] = round(tl[-1]["end"], 3)
    sb["captions"] = [{"start": round(s + lead, 3), "end": round(e + lead, 3), "text": t}
                      for (s, e), (_k, t) in zip(unit_times, units(sb))]
    return sb
