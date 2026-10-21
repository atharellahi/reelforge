# Storyboard and features schemas

Both files live in `<repo>/.reelforge/`. The build validates the storyboard against
`features.json` and `ui_strings.json`: beats without a cited fact are cut, labels that do
not exist in the product are dropped, a stat without its number becomes a quote, and the
CTA url is taken from `brand.json`.

## features.json

```json
{
 "product": {"name": "Pixigen", "one_line": "AI product enrichment for Shopify fashion stores",
             "audience": "Shopify fashion merchants"},
 "features": [
  {"id": "batch_upload",
   "name": "Batch upload",
   "one_line": "Drop in folders or up to 300 photos; they are grouped into products.",
   "why_it_matters": "Listing one product at a time is the job merchants hate.",
   "routes": ["/upload"],
   "visual": "A drop zone, then photos grouped into product cards.",
   "facts": [
     {"text": "Users can drag images and folders, up to 300 photos, for upload.",
      "evidence": "components/BatchStudio.js"},
     {"text": "Images can be grouped into a product.", "evidence": "components/BatchStudio.js"}
   ]}
 ]
}
```
Rules: ids are `snake_case` and must stay stable across edits (jobs refer to them). 3-6
facts per feature, each with the file you read it in. A fact is something a video could
show or say without lying. Keep facts in the user's language, not the code's.

## brand.json

```json
{"name": "Pixigen", "tagline": "AI product enrichment for Shopify", "url": "app.pixigen.ai",
 "primary": "#5C1A3D", "accent": "#E0557B", "bg": "#FAF6F0",
 "font_head": "Comfortaa", "font_body": "Quicksand", "logo": "assets/logo.png"}
```
`url` is what the CTA shows. `logo` is relative to `.reelforge/` (copy the file into
`.reelforge/assets/`). Fonts are Google Fonts family names.

## storyboard.json

```json
{
 "author": "claude",
 "feature_id": "batch_upload",            // or "all" for a whole-product film
 "aspect": "9:16",                        // 9:16 | 16:9 | 1:1 | 4:5
 "seconds": 30,                           // 30 feature short; 60-90 product film
 "title": "Batch upload - 300 photos in one drop",

 "hook": {
   "line": "Three hundred product photos, one drag, and your afternoon back.",   // ONE sentence, <= 14 words
   "visual": "counter",                   // counter | cards | grid | clash | typed
   "text": "One drop. Three hundred photos.",                                   // the claim, <= 9 words
   "value": 300, "unit": "photos",        // counter only; the number must be in a fact
   "image_prompt": "A fashion merchant at a bright studio table sliding a tall stack of printed garment photos into one folder, soft daylight"
 },

 "beats": [
   {"type": "screen",                     // screen | cards | stat | list | quote
    "line": "Drag in folders or loose images, up to three hundred at once.",
    "heading": "Drop in everything", "sub": "Folders or loose images, up to 300",
    "fact_ids": [0],
    "screenshot": "/upload",              // a route; used if a real screenshot exists in .reelforge/shots
    "callouts": [{"label": "Drag & drop here", "x": 0.5, "y": 0.45}],   // labels must exist in the product
    "image_prompt": "Hands arranging a grid of printed garment photos on a white table, overhead, soft light"},

   {"type": "cards",
    "line": "Every angle of the same piece is grouped into one product, automatically.",
    "heading": "Grouped into products", "sub": "Every angle, one listing",
    "fact_ids": [1],
    "items": [
      {"title": "Grouped Products", "sub": "Every angle together",
       "image_prompt": "Three photographs of the same camel coat from different angles laid side by side on linen"},
      {"title": "All One", "sub": "Treat a set as one item",
       "image_prompt": "A folded knit sweater beside a close detail of its ribbing, flat lay"}
    ]},

   {"type": "quote",
    "line": "Then enrich the whole batch in one go, instead of one listing at a time.",
    "heading": "Enrich the whole batch at once", "sub": "",
    "fact_ids": [1],
    "image_prompt": "A long rail of garments in a sunlit studio, a stylist walking past, slight motion blur"}
 ],

 "cta": {"line": "Upload your catalog at app dot pixigen dot ai.",
         "text": "Upload your catalog."},     // url is NOT written here; it comes from brand.json

 "meta": {
   "youtube_title": "Upload 300 product photos at once - Pixigen batch upload",   // <= 70 chars
   "youtube_description": "Drop in folders or up to 300 photos... \n\n#shopify #ecommerce #productphotos",
   "tags": ["pixigen", "shopify", "batch upload", "product photos"],
   "instagram_caption": "300 photos. One drag. ... #shopify #fashionbrand"
 }
}
```

### Beat types and what each needs
| type | shows | needs |
|---|---|---|
| `screen` | the product UI in a phone (9:16) or browser (16:9) frame; a real screenshot if one exists, else a built HTML mock around your photo | `heading`, `sub`, `callouts` (0-3, real labels), `image_prompt` |
| `cards` | 1-4 cards, image + title + sub | `items` (titles must be real strings) or a single `image_prompt` |
| `list` | a photo and 2-4 chips | `items` |
| `stat` | one big number counting up | `value`, `unit`, `label`; the number must appear in a cited fact |
| `quote` | a full-bleed photo with a short promise | `heading`, `image_prompt` |

### Timing you do not write
Beat durations come from the narration: the voice is recorded as one take, each line is
located in the audio, and the picture cuts when the line starts. You control pacing only
through how much you write per beat (3-7s of speech; a transformation beat 8-12s).

### Word budget
`seconds / 60 * 150 * 0.9`. 30s -> 67 words. 75s -> 168 words. Count hook + every beat
line + CTA. Over by more than 25% and the build drops the last beats.
