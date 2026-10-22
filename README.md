# reelforge

Feature videos from a codebase, made on your own machine.

Point it at a repo. It works out what the product does, writes a short video
for a feature, generates the imagery, records the narration, renders motion
graphics in headless Chrome, checks the result against a set of rules, and
publishes to whichever YouTube channel or Instagram account you choose.

Nothing runs on a server. Each person installs it, adds their own keys, and
the project's shared state (features, brand, corrections) lives in the repo.

## For teammates: getting started in five minutes

You need Claude Code and a Gemini key. Then:

1. **One command** (Windows PowerShell / macOS Terminal):
   `irm https://raw.githubusercontent.com/atharellahi/reelforge/main/install.ps1 | iex`
   `curl -fsSL https://raw.githubusercontent.com/atharellahi/reelforge/main/install.sh | bash`
   It installs anything missing (Python, git, ffmpeg, Chrome), reelforge, and the
   Claude skill. Safe to re-run. (Private repo? `gh auth login` first - see below.)
2. **Put your Gemini key** in `~/.reelforge/.env`: `GEMINI_API_KEY=...`
   (https://aistudio.google.com/apikey). Nothing else is required to make videos.
3. **Open a new terminal**, `cd` into the product repo, run `claude`, and ask:
   *"make a 30-second short about the upload feature"* ·
   *"a 75-second product film in 16:9"* · *"open the reelforge UI"*.
   Claude reads the code, writes the storyboard, builds, shows you a contact
   sheet, and iterates. Say what you'd change; it stores corrections for the team.
4. **To publish**, once: copy the team's YouTube `client_secret.json` somewhere,
   add `YOUTUBE_CLIENT_SECRET=<path>` to the same `.env`, and run
   `reelforge accounts add --label <channel-name>` (browser consent; pick the
   account AND the channel). Then ask Claude to publish - it confirms channel and
   visibility before it does.
5. **Commit `.reelforge/`** in the product repo when you're done; renders are
   ignored, everything else (facts, brand, scenes, storyboards, corrections) is
   shared.

## Install: one command

Installs whatever is missing (Python, git, ffmpeg, Chrome), then reelforge and
its Claude Code skill. Safe to re-run.

    # Windows (PowerShell)
    irm https://raw.githubusercontent.com/atharellahi/reelforge/main/install.ps1 | iex

    # macOS / Linux
    curl -fsSL https://raw.githubusercontent.com/atharellahi/reelforge/main/install.sh | bash

While the repo is private the raw URLs need GitHub access: run `gh auth login`
once, then `gh api -H "Accept: application/vnd.github.raw"
repos/atharellahi/reelforge/contents/install.sh | bash` (Windows: `install.ps1 | iex`).

Then put your Gemini key in `~/.reelforge/.env` (the installer creates the
file), open Claude Code in your project and ask for a video. Claude does the
rest, including opening the UI if you ask for it.

### Manual install

    pip install pipx && pipx ensurepath          # new terminal after this
    pipx install git+https://github.com/atharellahi/reelforge.git
    pipx inject reelforge faster-whisper          # optional: exact cuts + voice check
    reelforge skill install
    reelforge doctor

### Keys

Read from, nearest first: `<repo>/.reelforge/.env` (gitignored), `<repo>/.env`,
`~/.reelforge/.env`, then `~/.reelforge/config.json`. Names: `GEMINI_API_KEY`,
`YOUTUBE_CLIENT_SECRET` (path), `INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_USER_ID`,
`VEO_API_KEY`, `VEO_PROJECT`. The process environment overrides all of them.

## The Claude Code skill (recommended)

The two steps that decide quality - understanding the product and writing the
storyboard - are better done by Claude Code, which explores the repo as an
agent, than by the CLI's built-in writer. The skill hands those two steps to
Claude and keeps everything mechanical in the CLI.

    reelforge skill install            # into ~/.claude/skills (every project)
    reelforge skill install --project <repo>   # or just this repo

Then, in Claude Code, ask for a video: *"make a 30s short about the upload
feature"*, *"a 75s product film in 16:9"*, *"re-render with a calmer hook"*.
Claude runs `reelforge collect`, reads the code, writes `features.json` and the
storyboard, runs `reelforge build`, looks at `reelforge sheet`, iterates, and
publishes only when you say so. The claims rule is enforced by the build either
way: a beat without a cited fact is cut and a label that is not in the product
is dropped, whoever wrote it.

**Custom scenes.** The beat that carries a feature can be a small JS file Claude
writes (`type: "custom", scene: "scenes/x.js"`): the real UI reconstructed from
the code, choreographed - photos flying into a drop zone, a cursor pressing the
real button, a pill confirming. The engine loads it like any beat, the same
checks apply, and a missing or broken file falls back to a generic beat. This is
where motion-graphics quality comes from; generic beats are for context. See
the skill's `references/scenes.md` and `example_scene.js`.

`reelforge make` (Gemini writes) still works for one-click use in the UI.

## Fresh machine, step by step

Nothing here depends on any other machine being on.

**1. Prerequisites** (one time per machine)

    # Windows                                 # macOS
    winget install Python.Python.3.12         brew install python git ffmpeg
    winget install Git.Git
    winget install Gyan.FFmpeg
    # plus Google Chrome from google.com/chrome (Edge or Chromium also work)

**2. Install reelforge** - the repo is private, so you need to be a collaborator
and signed in to GitHub in git (it will prompt once).

    pip install git+https://github.com/atharellahi/reelforge.git
    pip install faster-whisper          # optional: exact narration cuts + voice check
    reelforge doctor                    # if "reelforge" is not found: python -m reelforge.cli doctor

`doctor` lists ffmpeg, Chrome, keys and accounts. Fix anything marked MISSING.

**3. The one required key**

    reelforge config set gemini_api_key <key>      # https://aistudio.google.com/apikey

**4. Point it at the repo** - a local checkout or a git URL.

    reelforge scan ./the-repo --url http://localhost:3000 --brief "the product is X; ignore the admin area"
    reelforge features ./the-repo

`--url` is optional but worth it: real screenshots beat generated mock
screens. Then open `the-repo/.reelforge/brand.json` and check **name, url,
colours, fonts, logo**. The `url` is what the CTA shows - leave it blank and
the video has no link.

**5. Tell it what you know that the code does not say** (optional, remembered)

    reelforge tune ./the-repo "never mention the beta features"
    reelforge tune ./the-repo "audience is small business owners, keep it plain"

**6. Make a video**

    reelforge make ./the-repo --feature <id-from-step-4>
    reelforge make ./the-repo --prompt "lead with how much time it saves"      # free brief
    reelforge make ./the-repo --feature <id> --aspect 16:9 --seconds 60          # landscape, longer

Takes about three minutes. Ends with `all checks passed` or `CHECKS FAILED`
with the reason. Output in `the-repo/.reelforge/out/<job>/final.mp4`.

**7. Review, then publish**

    reelforge ui --repo ./the-repo

Library tab: watch it, edit the title / description / tags it drafted, pick a
channel, publish. Or from the terminal:

    reelforge publish ./the-repo <job> --youtube <label> --privacy unlisted

**8. YouTube, one time per machine** - an OAuth *Desktop app* client from
Google Cloud Console with the YouTube Data API v3 enabled (any existing one
works; the json is not tied to a machine). While that OAuth app is in
"Testing", the Google accounts that will publish must be listed as test users.

    reelforge config set youtube_client_secret ~/Downloads/client_secret.json
    reelforge accounts add --label work         # browser opens: pick the account AND the channel
    reelforge accounts add --label personal     # another channel is another label
    reelforge accounts list

**9. Commit the shared state** so teammates start where you left off:

    git add .reelforge && git commit -m "reelforge project state"

Renders are ignored automatically; features, brand, tuning notes and the
image cache are what gets shared.

## Keys

| Key | Needed for | Where |
|---|---|---|
| Gemini API key | **everything** - writing, imagery, voice | https://aistudio.google.com/apikey |
| YouTube OAuth client (Desktop app) | publishing to YouTube | Google Cloud Console, YouTube Data API v3 |
| Instagram token + user id | publishing Reels | Meta developer app, Business account linked to a Page |
| Veo key + project | optional live-action hook plate | Vertex AI; billed per second |

    reelforge config set gemini_api_key AIza...
    reelforge config set youtube_client_secret ~/Downloads/client_secret.json

Keys live in `~/.reelforge/config.json`, never in the repo.

## Use

    reelforge scan ./my-app --url http://localhost:3000
    reelforge make ./my-app --feature outfit_of_the_day
    reelforge publish ./my-app <job-id> --youtube work --privacy unlisted

Or the local web app, which does the same with buttons:

    reelforge ui --repo ./my-app

### Products with more than one repo

A front-end and its back-end are one product. The first repo is the
**primary** - its `.reelforge/` holds the shared state - and every other repo
is read as evidence too (README, routes including Flask/FastAPI/Django,
strings), cited as `repo/path`.

    reelforge products add ./web --name Pixigen --with ./api --with ../mobile
    reelforge scan ./web                 # scans web + api + mobile as one product

In the UI: **+ Product**, name, primary repo, extra repos one per line, *Add
and scan*. The product switcher in the header moves between products.

### Many products on one machine

Each product's state is in its own repo, so facts, brand, tuning notes and
image caches never mix. What IS shared per machine: your keys and your
YouTube accounts. To stop a video going to the wrong channel, give each
product a default:

    reelforge products default-channel ./web --name pixigen
    reelforge publish ./web <job> --youtube default

Repos cloned from URLs are stored org-qualified (`~/.reelforge/repos/org__name`),
so two orgs' `api` repos cannot clone onto each other.

### scan

Reads the README, routes, user-visible UI strings and the folder tree, and asks
Gemini for the product's features **as facts with evidence**. Also detects the
brand (CSS variables, Google Fonts link, logo file). With `--url` it captures
real screenshots of each route, mobile and desktop.

Output: `.reelforge/features.json`, `.reelforge/brand.json`, `.reelforge/shots/`.
Edit `brand.json` by hand if detection got a colour wrong.

### make

    reelforge make <repo> --feature <id> [--aspect 9:16|16:9|1:1|4:5]
                          [--seconds 30] [--voice gemini|edge] [--veo]
                          [--prompt "lead with the time saved"]

1. **Storyboard.** Gemini writes a hook, 2-6 beats and a CTA. Every beat must
   cite a fact from the scan; a beat with no fact is cut. Every label the
   viewer reads (card titles, callout chips) must exist in the product's facts
   or its UI strings, or it is dropped; a `stat` must quote a number a fact
   contains. That is how the "never claim what the product does not do" rule
   is enforced - mechanically, not by asking nicely.
2. **Imagery.** Real screenshots where they exist; generated images otherwise,
   sized to fit their slot (a portrait card gets a portrait image). Cached by
   prompt, so a re-render never pays twice.
3. **Narration.** One continuous take (Gemini voice, or edge-tts free
   fallback), then each spoken line is located in the audio. The picture is
   timed from the voice, not the other way round.
4. **Render.** `scene.html` draws the storyboard as a pure function of time;
   Chrome is seeked once per frame; ffmpeg assembles. Captions on by default.
5. **Checks.** Hook has a moving visual in the first 1.5s; nothing holds
   still for more than 1.5s; narration matches the script (if whisper is
   installed). A failed check blocks `publish` unless you pass `--force`.

Output: `.reelforge/out/<job>/final.mp4`, `thumb.jpg`, `meta.json` (title,
description, tags, caption - drafted, editable).

    reelforge check <repo> <job>     # re-run the checks on an existing render

**Whole-product film:** `--feature all` (or ★ Whole product in the UI) draws
two facts from every feature, writes 4-7 beats in the order a new user meets
them, and targets 60-90s. Aspect ratios: `--aspect 9:16` (default), `16:9`,
`1:1`, `4:5` - each is its own layout, not a crop.

**Branches:** `make` refuses to run on a branch that has no `.reelforge/`
state and names the branch that has it. It used to re-scan silently, which
forked the facts, replaced the brand with defaults and dropped the tuning
notes without anyone noticing.

The on-screen URL comes from `brand.json` and nowhere else. If it is blank the
CTA shows no link and the job records a warning, rather than letting the
writer invent one.

### publish

    reelforge accounts add --label work        # browser consent on this machine
    reelforge accounts add --label personal    # a second channel is a second label
    reelforge accounts list
    reelforge publish <repo> <job> --youtube work [--privacy private|unlisted|public]
    reelforge publish <repo> <job> --instagram

YouTube uploads default to **private**. Google asks which account and channel
at the consent screen, including Brand Account channels, so there is no limit
to how many you add. Each job records where it went, so nothing uploads twice
by accident.

Instagram needs the file at a public URL (Meta fetches it). reelforge uses S3
if configured, a `public_base_url` if you host `.reelforge/out` somewhere, or
a temporary Cloudflare quick tunnel if `cloudflared` is on PATH.

### tune

    reelforge tune <repo> "slower pace, fewer words per beat"
    reelforge tune <repo> "always end on the pricing page"
    reelforge tune <repo> list

Corrections are stored in `.reelforge/memory.json` **inside the repo**, so one
person's review improves everyone's next render.

## The rules

`reelforge/rules/VIDEO_RULES.md` is included in every storyboard prompt and
three of its rules are measured after the render. Short version: a hook is a
visual, not a sentence; nothing holds still; one take of narration; never crop
a product; every claim traces to the code.

## What runs where

| Piece | Where | Cost |
|---|---|---|
| writing, imagery, voice | Gemini, your key | pennies per video |
| rendering | headless Chrome + ffmpeg on your machine | free |
| voice fallback | edge-tts | free, no key |
| transcription check | faster-whisper, local | free, optional extra |
| live-action hook | Veo, your key | per second, opt-in |

## Limits, honestly

- Instagram publishing is wired to the Graph API but has not been exercised
  end to end; it needs a Business account, a Page and an app review for
  `instagram_content_publish`.
- Generated screens are labelled "illustration" in the video. Give `--url`
  and the real ones are used instead.
- The Gemini TTS voice is the one worth shipping; edge-tts is a fallback.
- No After Effects. If you have it and an MCP bridge, that is a layer on top,
  not a requirement.
