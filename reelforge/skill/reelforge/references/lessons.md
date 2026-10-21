# What we learned making these videos

The memory of the sessions that built reelforge, written for a Claude that was
not there. Read it before your first storyboard. Every entry below was a real
correction from the person reviewing the output, or a real bug found by
rendering and looking - not a guideline someone imagined.

## What the reviewer kept asking for, in their own words

- *"Good hook, good meat, and then a good CTA."* Three parts, always.
- *"The hook is just text. No one's going to stick to it."* A hook needs a
  moving visual that dramatises the line. Text arrives with it, never alone.
- *"Look up how crazy hooks work."* Pattern interrupt in the first second.
- *"The product ... they are cropped."* Never crop a product. A full-length
  shot cropped to a wide tile lost the shoes. Match the frame to the image.
- *"You show the product of a bag. What are you doing?"* Copy about a dress
  beside a photo of a tote. One product per panel, same product in every shot.
- *"The voiceover doesn't match the lips."* No talking heads. Generated faces
  cannot lip-sync to TTS and a mouth out of time is worse than no face.
- *"Things should move around."* Nothing holds still for more than ~1.5s.
  Static screens were called out again and again; it is the most repeated note.
- *"The voiceover should change with the scenes."* One spoken line per visual
  beat. A scene that holds while narration continues reads as broken.
- *"Make like one video for each feature."* And later: whole-product films too.
- *"Make good hooks ... randomly generate a ton of videos."* Variety: several
  hook visuals, several CTA treatments, so twenty shorts are not one short.
- *"Stop making one step purple ... it looks like we are showing steps."*
  Do not imply sequence where there is none.
- *"This won't do, please understand the stylist."* Generic beats drawn from
  an abstract were rejected. Read the code; use the real numbers and rules you
  find there (a deck of 20 drawn from 105; +2 per matched aesthetic; one slot
  that excludes the others). A technical audience learns nothing from
  "Grounding -> Confidence -> Fallback".
- *"I don't think Gemini will do as good a job."* Correct. You write the
  storyboard; the tool builds it.

## Traps the pipeline fell into (all fixed, all worth knowing)

Writing
- The writer invented a "100%" stat, "Boho Chic" labels, and a CTA url
  (`pixigenweb.com/upload`) when the brand file was blank. The build now cuts
  beats without a cited fact, drops labels not found in the product, demotes a
  stat without its number, and takes the url from brand.json or shows none.
  Do not rely on being told; the checks exist because telling did not work.
- Hook lines came back as two sentences and the picture sat still for six
  seconds. One sentence, <= 14 words.
- The hook `text` came back as the feature's name ("Daily Style Edits"). It is
  the claim the viewer feels, never a label.
- Whole-product films came back at 33s against a 75s brief, then 41s. Use the
  word budget; two spoken sentences per beat.
- All five beats were `screen`. Vary types; no more than two screens in a row.

Imagery
- Asking the image model for an app screen produced fake UI with garbled text
  every time. Screens are BUILT as HTML around a photograph; `image_prompt`
  describes a photograph of people, places, objects - never a screen or word.
- "Variation 2" returns the same image. Hook variants need concrete directions
  (wide / detail / a person in the scene / flat-lay).
- A prompt made mostly of prohibitions ("no text, no logos, no blue...")
  returns an EMPTY response. Phrase positively, one short exclusion at the end.
- Square images cropped to a tall card lose the shoes. Images are generated
  at the aspect of their slot.

Narration
- Per-line TTS calls start cold and end flat. One continuous take, split at
  the lines. Durations are measured from the audio; never guessed.
- A split that lands mid-sentence is still the right LENGTH; only
  transcription catches it.
- The transcriber hears "Drezily" as "Dresley" - the voice check forgives the
  brand name and compares words, not characters (character comparison scored a
  correct read at 0.65).

Rendering
- Chrome's `--window-size` includes browser chrome: the layout viewport came
  out 929px for a 1080px capture and every poster had a dead band at the foot.
  Always set the viewport explicitly.
- Adding the voice lead to both a beat's end and the next beat's start left
  0.3s of nothing between beats - the one frozen step the motion check caught.
- A CSS rule for real screenshots dragged the HTML mock's own photo and logo
  to the corner. Scope rules to what they are for.
- Portrait layouts must size themselves against the caption band or the third
  card ends up under the captions. Landscape hooks must centre in the right
  column or the bottom 60% of the frame is empty.
- A `list` beat went still eight seconds in and failed the motion check at
  0.299. Every beat type needs motion after its elements land.

Process
- Verify by rendering and looking. Every bug above was found in a contact
  sheet, not a log. Two or three rounds per video is normal.
- A branch without the committed `.reelforge/` state once caused a silent
  re-scan: default grey brand, no url, and a beat about a feature the tuning
  notes forbid. The build now refuses and names the branch that has the state.
- Feature ids drifted between scans and orphaned jobs; previous ids are now
  handed to the writer. Keep them stable when you edit features.json.
- Image caches grow with every iteration's rejects. `reelforge prune` before
  committing.

## House facts for the two products this was built on
Drezily AI Stylist (drezily.com/stylist): Closet and Discover are hidden - never
show them. No calendar sync, no per-item price tracking. Brand: wine #5C1A3D,
champagne #C9A961, Comfortaa + Quicksand; the DREZILY / AI·STYLIST lockup stays.
Pixigen (app.pixigen.ai): Shopify fashion enrichment; up to 300 photos per
upload; no competitor pages; everything an error is a toast.
