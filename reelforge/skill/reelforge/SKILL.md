---
name: reelforge
description: >
  Make feature videos and product films from a codebase and publish them to YouTube or
  Instagram. Use whenever someone asks for a video, short, reel, product film, demo video,
  feature video, launch video, or "something for YouTube/Instagram/TikTok" about a product
  whose code is available; also for "reelforge", "update the video", "re-render", "make it
  16:9", "publish to the channel". YOU read the repo and write the storyboard (facts with
  evidence, hook, beats, CTA, publishing copy); the `reelforge` CLI generates imagery,
  records narration, renders motion graphics in headless Chrome, checks the result against
  the video rules, and publishes. Never let the CLI's own writer (Gemini) write for you.
---

# reelforge: you write, the tool builds

The quality of a video lives in two places - understanding the product and writing the
storyboard - and both are yours. Everything mechanical is a CLI command.

```
reelforge doctor                      # tools and keys on this machine
reelforge collect <repo> [--with R2]  # evidence: README, routes, UI strings (no model)
reelforge build <repo> <storyboard>   # imagery + voice + render + checks  (~3-5 min)
reelforge sheet <repo> latest         # contact sheet -> Read it and judge
reelforge publish <repo> <job> --youtube <label> --privacy unlisted
```

## Step 0: make sure the machine is ready (do this yourself, do not send the user to a README)

Run `reelforge doctor`. If the command does not exist, install everything with ONE command
and then re-run doctor in a fresh shell:

- Windows (PowerShell): `irm https://raw.githubusercontent.com/atharellahi/reelforge/main/install.ps1 | iex`
- macOS / Linux: `curl -fsSL https://raw.githubusercontent.com/atharellahi/reelforge/main/install.sh | bash`
- If the repo is private and the raw URL is refused: `gh auth login` once, then
  `gh api -H "Accept: application/vnd.github.raw" repos/atharellahi/reelforge/contents/install.sh | bash`
  (or `... install.ps1 | iex` on Windows).

If `reelforge.exe` exists but is not on PATH (Windows), call it as `%USERPROFILE%\.local\bin\reelforge.exe`.

Keys: a **Gemini key is required** (imagery and voice). Look for it in `<repo>/.reelforge/.env`,
`<repo>/.env`, `~/.reelforge/.env` or `~/.reelforge/config.json` (`reelforge doctor` says
"gemini key set"). If missing, ask the user for it and write it to `<repo>/.reelforge/.env`
as `GEMINI_API_KEY=...` (that file is gitignored) - never into config files that get committed,
never echo it back. YouTube publishing additionally needs `YOUTUBE_CLIENT_SECRET=<path to the
OAuth desktop client json>` and one `reelforge accounts add --label <name>` per channel.

**Read `references/lessons.md` before your first storyboard.** It is the memory of the
sessions that built this: what the reviewer asked for, in their words, and every trap.

## Opening the UI for the user
When asked for the UI, or when a visual review is easier than describing it, run
`reelforge ui --repo <repo> --no-open` **in the background** and give the user the URL it
prints (http://127.0.0.1:7733/). It stays up until the session ends. The Library tab shows
every render with a player, the drafted copy, and the publish buttons.

## Repos
A local path or a GitHub URL both work everywhere a repo is expected; URLs are cloned under
`~/.reelforge/repos/`. A product that depends on another repo (its API, its mobile app) is
registered once with `reelforge products add <repo> --with <other-repo-url>`; after that
`collect` reads both. Private repos need the user's own git access (`gh auth login`).

## Workflow

### 1. Know what you are filming
- Resolve the repo(s). A product can span several (front-end + back-end): `reelforge products add <repo> --name X --with <repo2-url>`.
- `reelforge collect <repo>` writes `.reelforge/evidence.md`, `ui_strings.json`, `routes.json`, and drafts `brand.json`.
- **Read evidence.md, then read the code it points at.** Open the pages, components and
  README. Learn what a user actually sees and the exact labels on screen.
- If `.reelforge/features.json` is missing, **write it** - see `references/storyboard.md`
  for the schema. Every fact must be something you saw: a real label, a real behaviour, a
  real number, with the file path as evidence. Prefer outcomes over mechanics. If it is not
  in the code, it is not a fact.
- Check `brand.json`: name, **url** (what the CTA shows; blank = no link), colours, fonts,
  logo. Ask the user for the url if the code does not say.
- Read `.reelforge/memory.json` if present: team corrections, apply all of them.
- If `features.json` is missing but exists on another branch, say so instead of rewriting it.

### 2. Agree the shape
Ask only what you cannot infer: which feature (or the whole product), aspect
(9:16 default; 16:9 for YouTube proper), length (30s feature short; 60-90s product film),
and any angle ("lead with the time saved"). One question, not a form.

### 3. Write the storyboard
Save to `.reelforge/storyboards/<slug>.json`, schema in `references/storyboard.md`.
Before writing, read `references/VIDEO_RULES.md`. The rules that matter most:

- **The hook is a visual, not a sentence.** Pick `counter` (needs a real number),
  `cards`, `grid`, `clash` or `typed`; `text` is the claim the viewer feels, never the
  feature's name. The hook `line` is ONE spoken sentence, <= 14 words.
- **One spoken line per beat; the voice changes when the picture does.** 3-7s per beat.
- **Budget:** ~150 words per minute, times 0.9. A 30s short is ~67 words total. Count.
- **Every beat cites `fact_ids`.** Every card title, callout label and list item must be a
  string that exists in the product (facts or `ui_strings.json`) - the build drops any
  that is not, and tells you.
- **`stat` only when a cited fact contains that exact number.**
- **`image_prompt`s describe photographs of people, places, objects** - never a screen,
  phone, app, chart or written word. The renderer draws the UI; the photo is the human context.
- **CTA `text` is an imperative line; the url comes from brand.json** (never write one).
- Headings <= 7 words, two lines max on screen. Don't repeat the product name every line.
- Product film (`feature_id: "all"`): 4-7 beats, one feature per beat in the order a new
  user meets them, vary beat types, use at least 75% of the word budget.
- **The beat that carries the feature deserves a custom scene.** The generic beat types
  are templates; they cannot show *this* feature's moment. For the one or two beats that
  matter, reconstruct the real UI from the code and choreograph it in a small JS file:
  `type: "custom", scene: "scenes/<name>.js"`. See `references/scenes.md` and copy
  `references/example_scene.js`. This is where the motion-graphics quality comes from;
  a video made only of generic beats will look like a template, because it is one.

### 4. Build, then LOOK
```
reelforge build <repo> .reelforge/storyboards/<slug>.json [--aspect 16:9] [--voice edge]
reelforge sheet <repo> latest
```
Read the sheet image (the path is printed). Judge it against this list, in this order:
1. Hook: is something other than text moving between 0.3s and 1.5s?
2. Is every photo a photo (no fake UI, no garbled text)? Is the product cropped?
3. Do captions overlap cards or the device? Is any label a slogan rather than a real string?
4. Brand: right name, colours, logo, url pill present?
5. Does it look like a product film or a slideshow? Nothing may sit still.
The log also prints three measured checks (hook, motion, voice). A FAIL names the second.
Fix the storyboard, rebuild. Images are cached by prompt, so rebuilds are cheap and fast.
Two or three rounds is normal; say what you changed each time.

### 5. Publish only when told
`reelforge publish <repo> <job> --youtube <label> --privacy private|unlisted|public`.
Confirm channel and visibility with the user first. `reelforge accounts list` shows
channels; `reelforge accounts add --label <name>` adds one (browser consent).
Edit the publishing copy in the job's `meta.json` (`youtube_title`, `youtube_description`,
`tags`, `instagram_caption`) - you drafted it in the storyboard's `meta`.

### 6. Leave the project better
Offer to commit `.reelforge/` (features, brand, storyboards, memory, image cache; renders are
ignored). If the user corrected you ("slower", "never show X"), store it:
`reelforge tune <repo> "<correction>"` - it applies to every later storyboard.

## When things go wrong
- *No features.json on this branch* - it is on another branch; check it out or merge, do not rewrite.
- *dropped untraceable labels* - use the exact string from `ui_strings.json` or a fact.
- *motion FAIL at Ns* - find the beat at that time in `storyboard.json`'s timeline; a
  `list` or `cards` beat with one item tends to sit still - add items or change type.
- *voice FAIL* - almost always the transcriber mishearing the brand; `reelforge check` re-runs it.
- *CTA has no link* - `brand.json` has no `url`.
- *16:9 looks top-heavy* - rebuild; landscape hooks centre in the right column.
