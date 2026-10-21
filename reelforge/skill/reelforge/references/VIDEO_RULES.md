# Video rules

The standards a generated video must meet. Written to be **checkable**, not
admired — a rule nobody can test is a rule that gets skipped.

Sources: what repeatedly failed review in this project, plus published motion
and short-form guidance (see the end). Where the two disagreed, the review
feedback won, because it came from watching actual output.

---

## 1 · Hooks

**A hook must not be text on a background.** This failed review twice. Research
agrees that the strongest openers pair a visual interrupt with on-screen text,
not text alone.

| Required | Why |
|---|---|
| Something **moves or changes** in the first 0.5s | Static frames lose the scroll |
| The visual **dramatises the line** | A clock counting to 40 min, a wardrobe draining to grey |
| Text **arrives with** the visual, never instead of it | Text carries the claim; the visual earns the stop |
| Hook ends on the narrator's own pause | Measure it; do not guess a fixed 3.0s |

**Avoid:** a talking head whose lips do not match the narration. Generated faces
cannot lip-sync to TTS, and a mouth out of time is worse than no face.

**Check:** sample frames at 0.3s and 1.5s. If they are identical apart from
text, the hook fails.

---

## 2 · Motion

**Nothing on screen for more than ~1.5s may be still.** This is the single most
repeated piece of review feedback.

- The **frame itself drifts** — a 2–4% scale across the scene, so no beat is frozen
- Elements **enter with momentum**: slide, overshoot, settle. Never a plain fade
- **Stagger** list items 60–90ms apart, never together
- **Punctuate every ~2s** — a chip lands, a counter ticks, a card whips past
- Motion must behave **like real software**: panels slide, values count up,
  state changes transition rather than cut

**Check:** sample ~4 frames/second and compute the mean inter-frame pixel
difference. Any step below ~0.15 (on a 0-255 grey scale) is a frozen frame.

Do **not** use ffmpeg's `select='gt(scene,...)'` for this. It detects *cuts*,
so a correctly drifting scene reports long "gaps" and looks like a failure when
it is passing. Measured on a real short: the scene detector reported an 8.1s
gap where actual inter-frame motion never dropped below 0.376.

---

## 3 · Showing the product

- **Start the scene where it animates.** Scenes animate early then hold; entering
  late captures the finished, static state. This made six shorts look dead.
- The **real UI**, with **real labels** read from the codebase — not invented ones
- Show the **outcome**, not the clicks

**Check:** the scene's first animated keyframe must fall inside the clip.

---

## 4 · Imagery

- **Never crop a product.** Match the frame to the source ratio. `object-fit:
  cover` in a mismatched box cuts the legs off a full-length shot;
  `contain` in a wide box shows a mid-body sliver.
- **One product per panel.** Copy, packshot and lifestyle shots must all be the
  same item. Three near-misses shipped before this was caught.
- **Open every image before using it.** A file named `hero_1` was a tan tote in a
  panel about a green dress.

**Check:** assert the source aspect ratio is within 15% of its frame.

---

## 5 · Narration

- **One continuous take per video**, split at pauses. Per-line calls start cold
  and end flat; the result sounds like separate announcements.
- Script at **~150 words/minute**; count words before animating, because a long
  script cannot be trimmed after the animation is built
- **Voice follows the scene:** every beat change needs a line change. A scene that
  holds while narration continues reads as broken.
- **Verify by transcription.** A duration check cannot catch a split that lands
  mid-sentence — the piece is still the right length, just the wrong words.

**Check:** transcribe each clip, compare to its intended line, fail below 0.80
similarity.

---

## 6 · Pacing

- Feature beat: **3–7s**. Benefit or transformation: **8–12s**
- A cut or camera move every **1–2s**
- Total: **under 60s** for a feature short, **60–90s** for a product film
- Cut real-time friction — real software is slower than watchable software

---

## 7 · Type

- **Size to the frame.** Arial Bold fits ~11 characters at 190px in a 1080 frame.
  Overflowing type looked amateur and was called out directly.
- **Light weight, wide tracking, lower third** for captions. A slab of bold text
  over footage reads as a ten-year-old made it.
- **Two lines maximum**, wrapped on a word boundary

---

## 8 · Claims

Every claim must be **traceable to the codebase**. Features that do not exist
must never appear. In this project: no calendar sync, no per-item price
tracking, and hidden surfaces are never shown.

**Check:** flag any claim not matched to a UI string or code path.

---

## Tuning memory

These are defaults, not law. When someone corrects the output — "slower",
"less type", "more cuts" — that correction is **stored per project** and applied
to later renders. The rules above are where a project starts, not where it stays.

---

## Sources

The review feedback in this project, plus:
[Motion the Agency](https://www.motiontheagency.com/blog/best-product-demo-videos-that-convert-with-expert-tips) ·
[Vidico](https://vidico.com/news/best-product-demo-video-examples/) ·
[Content Beta](https://www.contentbeta.com/blog/animated-product-demo-videos-examples/) ·
[vidpal hooks](https://www.vidpal.ai/blog/video-hooks-that-stop-the-scroll-2026) ·
[cloudix 3-second rule](https://cloudixdigital.com/short-form-video-mastery-how-the-3-second-hook-rule-drives-social-discovery-and-roi/)

Most are agency or vendor blogs and their retention figures are unverified —
treat the numbers as directional. No source I found directly compares a
visual-first hook against a text-first one; that remains worth A/B testing.

---

## Backlog — stitching on trending hooks

Idea: let the agent find and download popular TikTok/Instagram videos worth
stitching onto, and use one as the hook with our content built on top.

Not built. Before it is, two things need answering, and neither is technical:

1. **Rights.** Republishing someone else's video with our content attached is
   their copyright, not ours. Platform stitch/duet features carry a licence;
   a downloaded file does not.
2. **Terms of service.** Scraping downloads is against TikTok's and Instagram's
   terms independently of copyright.

The safe version of this is the platforms' own stitch/duet/remix features,
which grant the licence and keep attribution. That is a publishing-side feature,
not a rendering one.
