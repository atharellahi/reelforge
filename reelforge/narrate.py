"""Record the narration as ONE take, then find where each unit starts and ends.

Why one take: per-line TTS calls start cold and end flat, and the result sounds
like separate announcements. One take keeps the voice identical throughout.

Why measure: the picture is timed FROM the voice, not the other way round. Each
spoken unit maps to one visual beat, so beat boundaries are read off the audio.

  Gemini voice  -> words located by faster-whisper if installed, else by
                   silence detection snapped to the script's word proportions
  edge-tts      -> SentenceBoundary events give exact sentence times for free
"""
import asyncio
import difflib
import os
import re
import subprocess

from . import config as C
from . import gemini


def _norm_words(s):
    return re.findall(r"[a-z0-9']+", (s or "").lower().replace(".com", " dot com").replace("/", " slash "))


def _ffprobe_dur(ffmpeg, path):
    ffprobe = os.path.join(os.path.dirname(ffmpeg), "ffprobe" + (".exe" if ffmpeg.endswith(".exe") else ""))
    if not os.path.exists(ffprobe):
        ffprobe = "ffprobe"
    out = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", path], capture_output=True, text=True)
    return float(out.stdout.strip() or 0)


# ---------------------------------------------------------- alignment

def align(units, words):
    """units: [text,...]; words: [(start,end,text),...] from the audio.
    Returns [(start,end),...] per unit. Matches script words to heard words
    with difflib, so a mis-heard word here or there does not move a boundary."""
    script = []
    owner = []
    for i, u in enumerate(units):
        ws = _norm_words(u)
        script += ws
        owner += [i] * len(ws)
    heard = [_norm_words(w[2]) for w in words]
    heard_flat, heard_owner = [], []
    for j, ws in enumerate(heard):
        for w in ws:
            heard_flat.append(w); heard_owner.append(j)
    if not script or not heard_flat:
        total = words[-1][1] if words else 1.0
        n = max(1, len(units))
        return [(total * i / n, total * (i + 1) / n) for i in range(n)]

    sm = difflib.SequenceMatcher(None, script, heard_flat, autojunk=False)
    s2h = {}
    for a, b, size in sm.get_matching_blocks():
        for k in range(size):
            s2h[a + k] = b + k

    def heard_idx(si, direction):
        # nearest matched script word, looking forward or back a few words
        for d in range(0, 6):
            k = si + d * direction
            if 0 <= k < len(script) and k in s2h:
                return s2h[k]
        return None

    bounds = []
    cum = 0
    counts = [len(_norm_words(u)) for u in units]
    for i, c in enumerate(counts):
        first, last = cum, cum + c - 1
        cum += c
        hs = heard_idx(first, +1)
        he = heard_idx(last, -1)
        bounds.append([hs, he])
    # fill gaps proportionally, then make monotonic
    n_h = len(heard_flat)
    for i, (hs, he) in enumerate(bounds):
        if hs is None:
            bounds[i][0] = int(sum(counts[:i]) / max(1, len(script)) * n_h)
        if he is None:
            bounds[i][1] = int((sum(counts[:i + 1]) / max(1, len(script))) * n_h) - 1
    for i in range(1, len(bounds)):
        bounds[i][0] = max(bounds[i][0], bounds[i - 1][1] + 1)
        bounds[i][1] = max(bounds[i][1], bounds[i][0])
    times = []
    for hs, he in bounds:
        hs = min(max(hs, 0), n_h - 1); he = min(max(he, hs), n_h - 1)
        times.append((words[heard_owner[hs]][0], words[heard_owner[he]][1]))
    return times


# ---------------------------------------------------------- transcribe

def whisper_words(wav):
    try:
        from faster_whisper import WhisperModel
    except Exception:
        return None
    model = WhisperModel("base.en", device="cpu", compute_type="int8")
    segs, _ = model.transcribe(wav, word_timestamps=True)
    out = []
    for s in segs:
        for w in (s.words or []):
            out.append((float(w.start), float(w.end), w.word))
    return out or None


def silence_words(ffmpeg, wav, units):
    """No transcriber: fake 'words' from silence gaps and word proportions. Each
    unit gets one pseudo-word spanning its estimated range, snapped to gaps."""
    total = _ffprobe_dur(ffmpeg, wav)
    log = subprocess.run([ffmpeg, "-i", wav, "-af", "silencedetect=n=-40dB:d=0.22", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    st = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", log)]
    en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", log)]
    gaps = [((s + e) / 2, e - s) for s, e in zip(st, en) if s > 0.2 and e < total - 0.05]
    counts = [max(1, len(_norm_words(u))) for u in units]
    S = sum(counts)
    cuts, cum = [], 0
    for c in counts[:-1]:
        cum += c
        est = total * cum / S
        near = [g for g in gaps if abs(g[0] - est) < 0.9]
        cuts.append(max(near, key=lambda g: g[1])[0] if near else est)
    edges = [0.0] + cuts + [total]
    return [(edges[i], edges[i + 1], units[i]) for i in range(len(units))]


# ---------------------------------------------------------------- edge

async def _edge(script, voice):
    import edge_tts
    com = edge_tts.Communicate(script, voice)
    audio, marks = b"", []
    async for ch in com.stream():
        if ch["type"] == "audio":
            audio += ch["data"]
        elif ch["type"] == "SentenceBoundary":
            s = ch["offset"] / 1e7
            marks.append((s, s + ch["duration"] / 1e7, ch["text"]))
    if not audio:
        raise RuntimeError("edge-tts returned no audio")
    return audio, marks


def _edge_words(marks):
    """Spread each sentence's words evenly inside its measured span, so the
    alignment sees word-level input. Sentence edges stay exact."""
    out = []
    for s, e, text in marks:
        ws = text.split()
        if not ws:
            continue
        step = (e - s) / len(ws)
        for i, w in enumerate(ws):
            out.append((s + i * step, s + (i + 1) * step, w))
    return out


# ---------------------------------------------------------------- main

def narrate(job_dir, units, prefer="gemini", log=print):
    """units: [text,...] -> (vo_wav_48k, [(start,end),...], engine)."""
    cfg = C.load()
    ffmpeg = C.find_ffmpeg(cfg)
    os.makedirs(job_dir, exist_ok=True)
    raw = os.path.join(job_dir, "vo_raw.wav")
    script = "\n\n".join(units)
    engine = None

    if prefer == "gemini" and cfg["gemini_api_key"]:
        try:
            gemini.tts(script, raw, voice=cfg["gemini_tts_voice"])
            engine = "gemini"
        except Exception as e:
            log(f"  gemini voice failed ({str(e)[:80]}) - falling back to edge-tts")
    if engine is None:
        audio, marks = asyncio.run(_edge(script, cfg["edge_voice"]))
        mp3 = os.path.join(job_dir, "vo_raw.mp3")
        with open(mp3, "wb") as fh:
            fh.write(audio)
        subprocess.run([ffmpeg, "-v", "error", "-y", "-i", mp3, raw], check=True)
        engine = "edge"
        words = _edge_words(marks)
    else:
        words = whisper_words(raw)
        if words is None:
            log("  faster-whisper not installed: splitting by silence (pip install reelforge[check] for exact cuts)")
            words = silence_words(ffmpeg, raw, units)

    times = align(units, words)

    vo = os.path.join(job_dir, "vo.wav")
    subprocess.run([ffmpeg, "-v", "error", "-y", "-i", raw,
                    "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
                    "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", vo], check=True)
    total = _ffprobe_dur(ffmpeg, vo)
    log(f"  voice: {engine}, {total:.1f}s, {len(units)} units")
    for (s, e), u in zip(times, units):
        log(f"    {s:6.2f}-{e:6.2f}  {u[:60]}")
    return vo, times, engine
