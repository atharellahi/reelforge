# Custom scenes: when the generic beats are not good enough

The built-in beat types (`screen`, `cards`, `stat`, `list`, `quote`) are templates.
They are fine for context beats. They cannot know that THIS feature's moment is a
drop zone filling with photos and collapsing into grouped products, or a cursor
pressing *Shop* and a pill confirming it. For the beat that carries the feature -
usually one per video, sometimes two - write a scene.

A scene is a small JS file in the project, `<repo>/.reelforge/scenes/<name>.js`,
that the renderer loads and calls once per frame. You reconstruct the real UI
from the code you read, in the brand's own tokens, and choreograph it.

```js
registerScene('scenes/<name>.js', function (g, lt, d, ctx) {
  // g   : the <div> for this beat (absolutely positioned children, px units)
  // lt  : seconds since the beat began; d: the beat's length in seconds
  // ctx : helpers and facts (below)
});
```

Storyboard side:
```json
{"type": "custom", "scene": "scenes/<name>.js",
 "line": "...", "heading": "...", "sub": "...", "fact_ids": [..],
 "image_prompts": ["photo 1 ...", "photo 2 ..."]}       // arrive as ctx.beat.images, same order
```
A hook can be custom too: `"visual": "custom", "scene": "scenes/<name>.js"`.
If the file is missing or throws, the renderer draws the generic `cards` beat
instead and records a warning - never a blank frame.

## ctx

| name | what |
|---|---|
| `W`, `H`, `MODE` | frame size; `'port'` (9:16, 4:5), `'land'` (16:9), `'square'` |
| `LAY` | layout: `pad`, `top` (first safe y), `bottom`, `capY` (caption band top - stay above it), `h1`, `h2` |
| `B` | brand: `primary`, `accent`, `bg`, `name`, `tagline`, `logo`, fonts (also CSS vars `--p --a --bg --pS --line --fh --fb`) |
| `beat` / `hook` | the storyboard object: `heading`, `sub`, `items`, `images`, `image` |
| `el(tag, cls, html, style)` | make an element; classes available: `abs card pill pill.on chip hd sub eyebrow num tag` |
| `img(path, objectPosition)` | an `<img>` html string that covers its box |
| `heading(g, text, sub, lt, y)` | the standard animated heading; returns the next free y |
| `lockup(g, x, y, size, align)` | the brand lockup |
| `cursor(g, x, y, pressed, opacity)` | a pointer; set `pressed` for ~0.2s to show the click |
| `ease easeIO easeBack lerp clamp` | the easings every built-in beat uses |
| `rise(p, dist)` `pop(p)` | style strings: enter from below / scale in with overshoot |
| `typed(text, lt, start, perChar)` | `{text, done, on}` for typewriter text; `caret(h)` |
| `fit(text, base, maxChars)` | font size that fits a line |
| `fmtNum(n)` | 1,234 |

The group `g` already drifts (slow 3.5% scale across the beat) - that is the
engine's baseline motion. You add the choreography.

## Rules that apply to scenes exactly as to everything else
- **Something moves at every moment.** After elements land, keep them breathing
  (a 3-6px sine bob, a 1-2% pulse). The motion check samples 4 frames a second
  and fails any step that is near-still; it has failed real scenes.
- **Enter with momentum** (`easeBack`), stagger lists 80-120ms, punctuate every ~2s
  (a chip pops, a counter ticks, a cursor presses).
- **Real labels only.** Every word on screen is a string you read in the code or a
  fact. Sample user content (product names, prices) is allowed if it is clearly
  the user's own data, never an invented feature.
- **Stay inside `LAY.top .. LAY.capY`** in portrait; captions sit below `capY`.
- **Budget the choreography to the line.** The beat lasts as long as its spoken
  line (3-7s). Finish the story by ~`d - 0.5` and keep breathing after.
- **Landscape:** put words in the left `LAY.col` and the visual on the right, or
  check `MODE` and lay out separately. Test both if the user wants both.
- Brand colours from `B`, never hard-coded.

## Worked example
`references/example_scene.js` - the Pixigen batch-upload moment: zone pops,
six photos fly in staggered while a counter ticks, pairs collapse into three
product cards, labels and a "Grouped Products" chip arrive, the Enrich button
appears, a cursor travels to it and presses, a pill confirms. About 80 lines.
Copy it, keep its structure (timings as `lt` thresholds, every element's position
a function of `lt`), and replace the story.

## Workflow
1. Read the component that renders the real screen. Note labels, order, colours, what changes when the user acts.
2. Write the beat's spoken line first; its length is your time budget.
3. Write the scene as a timeline of thresholds (0.0, 0.3, 1.6, 2.8 ...). One idea per threshold.
4. `reelforge build`, then `reelforge sheet` and READ it. Check: does the moment read without sound? Is anything still? Anything under the captions? Any invented label?
5. Two or three rounds is normal.
