// Custom scene: the batch-upload moment, choreographed rather than templated.
//
//   0.0  heading rises; a dashed drop zone pops in with "Drag & Drop Here"
//   0.3  six product photos fly in from off-screen, staggered, and land in a grid
//        while a counter ticks "n / 300 photos"
//   1.6  the grid collapses: pairs of photos gather into three product cards
//   2.2  each card gets its label; a "Grouped Products" chip pops
//   2.8  the Enrich button appears; a cursor travels to it and presses
//   3.9  "Enriching 3 products" confirms
//   throughout: the frame drifts (engine), cards bob, the button breathes
//
// Everything on screen is a real label from the product (ui_strings.json):
// "Drag & Drop Here", "Grouped Products", "Enrich". The photos come from the
// storyboard's image_prompts as beat.images.
registerScene('scenes/upload_dropzone.js', function (g, lt, d, ctx) {
  const { W, H, MODE, LAY, B, el, img, esc, ease, easeIO, easeBack, lerp, clamp, pop, heading, cursor } = ctx;
  const b = ctx.beat;
  const imgs = b.images && b.images.length ? b.images : [b.image].filter(Boolean);
  const port = MODE === 'port';

  // heading, then the zone fills the space above the caption band
  const y = heading(g, b.heading, b.sub, lt, LAY.top);
  const px = LAY.pad, pw = port ? W - LAY.pad * 2 : 980;
  const zx = port ? px : W - LAY.pad - pw;
  const zy = port ? y + 10 : LAY.top + 110;
  // the button and its confirmation pill live below the zone; leave them room
  // above the caption band (LAY.capY) rather than letting the pill touch it
  const zoneH = port ? Math.min(580, LAY.capY - 240 - zy) : 520;

  g.appendChild(el('div', 'abs', '',
    `left:${zx}px;top:${zy}px;width:${pw}px;height:${zoneH}px;border:3px dashed ${B.primary};border-radius:28px;background:rgba(255,255,255,.72);${pop(lt / .5)}`));

  // the prompt inside the zone fades as the first photo lands
  const lblOp = 1 - ease((lt - .9) / .4);
  if (lblOp > 0) g.appendChild(el('div', 'abs',
    `<div style="font-size:30px;font-weight:700;color:${B.primary};text-align:center">Drag &amp; Drop Here</div>` +
    `<div style="font-size:22px;color:#6b6560;text-align:center;margin-top:8px">folders or up to 300 photos</div>`,
    `left:${zx}px;top:${zy + zoneH / 2 - 40}px;width:${pw}px;opacity:${lblOp}`));

  // six photos, three columns, flying in from bottom-right
  const n = 6, cols = 3, gap = 22;
  const tw = port ? 210 : 150, th = Math.round(tw * 1.25);
  const gx = zx + (pw - (cols * tw + (cols - 1) * gap)) / 2, gy = zy + 44;
  const collapse = ease((lt - 1.6) / .55);
  const cardW = port ? 290 : 210, cardH = Math.round(cardW * 1.25);
  const base = zx + (pw - (3 * cardW + 2 * gap)) / 2;
  for (let i = 0; i < n; i++) {
    const p = easeBack((lt - .3 - i * .1) / .55);
    if (p <= 0) continue;
    const c = i % cols, r = Math.floor(i / cols);
    const x0 = gx + c * (tw + gap), y0 = gy + r * (th + gap);
    const k = Math.floor(i / 2);                       // which product card this photo joins
    const tx = base + k * (cardW + gap) + (i % 2) * 10, ty = zy + 40 + (i % 2) * 10;
    const x = lerp(x0, tx, collapse), yy = lerp(y0, ty, collapse);
    const sx = lerp(W + 120, x, p), sy = lerp(H + 240, yy, p);
    const rot = lerp(24, (i % 2 ? 3 : -3), p) * (1 - collapse * .6);
    const bob = Math.sin(lt * 1.5 + i * 1.3) * 4;      // never fully still, before or after
    g.appendChild(el('div', 'card', img(imgs[i % Math.max(1, imgs.length)], '50% 20%'),
      `left:${sx}px;top:${sy + bob}px;width:${lerp(tw, cardW, collapse)}px;height:${lerp(th, cardH, collapse)}px;` +
      `transform:rotate(${rot}deg);opacity:${clamp(p * 1.5)};z-index:${10 + i}`));
  }

  // the counter ticks as photos land, then yields to the group chip
  const landed = Math.round(clamp((lt - .3) / (.1 * n + .4)) * n);
  if (lt > .3 && collapse < 1) g.appendChild(el('div', 'pill on', `${landed} / 300 photos`,
    `left:${zx + pw - 26}px;top:${zy + zoneH - 72}px;transform:translateX(-100%);font-size:26px;padding:12px 20px;opacity:${1 - collapse}`));

  if (collapse > 0) {
    for (let k = 0; k < 3; k++) {
      const lp = ease((lt - 2.2 - k * .1) / .4);
      if (lp <= 0) continue;
      g.appendChild(el('div', 'abs',
        `<div style="font-size:24px;font-weight:700;color:${B.primary}">Product ${k + 1}</div><div style="font-size:19px;color:#6b6560">2 photos</div>`,
        `left:${base + k * (cardW + gap)}px;top:${zy + 40 + cardH + 26}px;width:${cardW}px;opacity:${lp};transform:translateY(${(1 - lp) * 14}px)`));
    }
    const chp = easeBack((lt - 2.5) / .45);
    if (chp > 0) g.appendChild(el('div', 'pill on', 'Grouped Products',
      `left:${zx + pw / 2}px;top:${zy + zoneH - 96}px;transform:translateX(-50%) scale(${chp});font-size:26px;padding:12px 22px;opacity:${clamp(chp * 1.4)}`));
  }

  // Enrich: the button arrives, the cursor comes for it, it presses, it confirms
  const bw = port ? 420 : 320, bx = zx + pw / 2 - bw / 2, by = zy + zoneH + 36;
  const bp = easeBack((lt - 2.8) / .5);
  const pressed = lt > 3.7 && lt < 3.92;
  const breathe = 1 + Math.sin(Math.max(0, lt - 3.3) * 3) * .012;
  if (bp > 0) g.appendChild(el('div', 'abs', 'Enrich',
    `left:${bx}px;top:${by}px;width:${bw}px;height:76px;border-radius:16px;background:${B.primary};color:#fff;display:flex;align-items:center;justify-content:center;` +
    `font-size:30px;font-weight:700;box-shadow:0 18px 40px rgba(0,0,0,.18);opacity:${clamp(bp * 1.4)};transform:scale(${lerp(.9, 1, bp) * (pressed ? .94 : breathe)})`));
  if (lt > 3.0 && lt < 4.6) {
    const cp = easeIO((lt - 3.0) / .7);
    cursor(g, lerp(zx + pw * .8, bx + bw / 2 + 40, cp), lerp(by + 240, by + 44, cp), pressed, 1 - ease((lt - 4.2) / .4));
  }
  const pp = ease((lt - 3.95) / .4);
  if (pp > 0) g.appendChild(el('div', 'pill on', '✓ Enriching 3 products',
    `left:${zx + pw / 2}px;top:${by + 98}px;transform:translate(-50%,${(1 - pp) * 12}px);font-size:26px;padding:12px 24px;opacity:${pp}`));
});
