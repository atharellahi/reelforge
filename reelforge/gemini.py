"""One place that talks to Gemini: text, images, speech.

A Gemini key is the one thing reelforge requires. It supplies three things no
free tool covers together - writing the storyboard from the code, generating
imagery a fresh repo does not have, and a narration voice worth shipping.
"""
import io
import json
import re
import time
import wave

from . import config as C

_client = None


def client():
    global _client
    if _client is not None:
        return _client
    cfg = C.load()
    key = cfg["gemini_api_key"]
    if not key:
        raise SystemExit(
            "No Gemini key. Set one with:\n  reelforge config set gemini_api_key <key>\n"
            "Get a key at https://aistudio.google.com/apikey")
    from google import genai
    mode = cfg["gemini_mode"]
    if mode == "auto":
        # Vertex express keys start with "AQ."; AI Studio keys with "AIza"
        mode = "vertex" if key.startswith("AQ.") else "studio"
    _client = genai.Client(vertexai=(mode == "vertex"), api_key=key)
    _client._reelforge_mode = mode
    return _client


def _strip_fences(s):
    s = s.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    return s.strip()


def text(prompt, system=None, as_json=False, model=None, temperature=0.6, tries=3):
    from google.genai import types
    c = client()
    model = model or C.load()["gemini_text_model"]
    cfg = types.GenerateContentConfig(
        temperature=temperature,
        system_instruction=system,
        response_mime_type="application/json" if as_json else None,
    )
    last = None
    for n in range(tries):
        try:
            r = c.models.generate_content(model=model, contents=prompt, config=cfg)
            out = _strip_fences(r.text or "")
            if as_json:
                return json.loads(out)
            return out
        except Exception as e:
            last = e
            time.sleep(1.5 * (n + 1))
    raise RuntimeError(f"gemini text failed: {last}")


def image(prompt, aspect="2:3", model=None, tries=3):
    """Returns a PIL image. Aspect is enforced after decode, because a wrong
    ratio is cheaper to catch here than in a rendered frame."""
    from google.genai import types
    from PIL import Image
    c = client()
    model = model or C.load()["gemini_image_model"]
    want = {"2:3": 2 / 3, "3:2": 1.5, "1:1": 1.0, "16:9": 16 / 9, "9:16": 9 / 16, "4:5": 0.8}[aspect]
    last = None
    for n in range(tries):
        try:
            r = c.models.generate_content(
                model=model, contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    image_config=types.ImageConfig(aspect_ratio=aspect)))
            cand = (r.candidates or [None])[0]
            content = getattr(cand, "content", None)
            parts = [p for p in (getattr(content, "parts", None) or []) if getattr(p, "inline_data", None)]
            if not parts:
                raise RuntimeError(f"no image ({getattr(cand, 'finish_reason', 'empty')})")
            im = Image.open(io.BytesIO(parts[0].inline_data.data)).convert("RGB")
            if abs(im.width / im.height - want) > 0.15 * want:
                raise RuntimeError(f"wrong aspect {im.width}x{im.height}")
            return im
        except Exception as e:
            last = e
            time.sleep(2 + 2 * n)
    raise RuntimeError(f"gemini image failed: {last}")


# Tried in order; the first that answers is remembered for the session. Vertex
# and AI Studio name the TTS models differently.
TTS_MODELS = ["gemini-2.5-pro-tts", "gemini-2.5-pro-preview-tts",
              "gemini-2.5-flash-tts", "gemini-2.5-flash-preview-tts"]
_tts_model = None

DIRECTION = (
    "You are a professional narrator recording the voiceover for a polished product "
    "film, in ONE continuous take. Keep exactly the same voice, tone, energy and pace "
    "from the first line to the last. Warm, clear, articulate and quietly upbeat, at a "
    "brisk conversational pace. Leave a clear pause of about one second between "
    "paragraphs and only short natural pauses inside them. Read the following:\n\n")


def tts(script, wav_path, voice=None):
    """One continuous take of `script` -> 24k mono wav at wav_path."""
    global _tts_model
    from google.genai import types
    c = client()
    voice = voice or C.load()["gemini_tts_voice"]
    order = [_tts_model] + [m for m in TTS_MODELS if m != _tts_model] if _tts_model else TTS_MODELS
    last = None
    for model in order:
        try:
            r = c.models.generate_content(
                model=model, contents=DIRECTION + script,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)))))
            data = r.candidates[0].content.parts[0].inline_data.data
            with wave.open(wav_path, "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(data)
            _tts_model = model
            return wav_path
        except Exception as e:
            last = e
    raise RuntimeError(f"gemini tts failed on every model: {last}")
