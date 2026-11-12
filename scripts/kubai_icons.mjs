#!/usr/bin/env node
// Icon evaluation for LFR-13: renders the 27 shell icons from the Kubai Icons sources in
// `docs/kubai-icons/` (pinned by the repository commit) next to the current Lucide paths in
// `lindra/templates/icons.html`, recoloured to the brand kit at build time, and checks the
// contrast of the recoloured icons. Needs Node 20 or newer and nothing from the network.
//
//   node scripts/kubai_icons.mjs            writes docs/ui/icon-comparison/
//   node scripts/kubai_icons.mjs --names    prints every Kubai icon name, for the mapping
//   node scripts/kubai_icons.mjs --check    exits non-zero when a mapped name does not exist
//
// The output is documentation. Nothing under `lindra/static/` is written, so the comparison
// page is never served by the application.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { loadIcons } from '../docs/kubai-icons/tools/registry.mjs';
import { renderSVG, renderInner } from '../docs/kubai-icons/packages/core/src/render.js';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const outDir = path.join(root, 'docs/ui/icon-comparison');

// Brand kit tokens (docs/ui/contrast.md). Kubai's own blue is the reference colour.
const SURFACES = { Paper: '#F7F5F0', White: '#FFFFFF' };
const ACCENTS = { 'Kubai blue': '#5393FF', Teal: '#245B57', Ink: '#243331' };

// Lucide name used by `lindra/templates/icons.html` -> closest Kubai name, how close it is.
// "exact": same object. "near": same idea, different drawing. "none": no Kubai icon does the job.
const MAPPING = [
  ['menu', 'menu', 'exact'],
  ['chevron-left', 'chevron-left', 'exact'],
  ['chevron-right', 'chevron-right', 'exact'],
  ['mic', 'mic', 'exact'],
  ['circle-check', 'circle-check', 'exact'],
  ['circle-alert', 'circle-alert', 'exact'],
  ['plus', 'circle-plus', 'near'],
  ['pencil', 'pencil', 'exact'],
  ['trash', 'trash', 'exact'],
  ['file', 'file', 'exact'],
  ['file-text', 'file-text', 'exact'],
  ['loader-circle', 'loader', 'near'],
  ['cloud-off', 'cloud-off', 'exact'],
  ['rotate-cw', 'rotate-cw', 'exact'],
  ['log-out', 'log-out', 'exact'],
  ['copy', 'copy', 'exact'],
  ['clipboard-check', 'clipboard-check', 'exact'],
  ['circle-help', 'circle-help', 'exact'],
  ['circle-minus', 'circle-minus', 'exact'],
  ['clock', 'clock', 'exact'],
  ['triangle-alert', 'triangle-alert', 'exact'],
  ['file-check', 'file-check', 'exact'],
  ['file-diff', 'file-diff', 'exact'],
  ['x', 'circle-x', 'near'],
  ['check', 'circle-check', 'near'],
  ['refresh-cw', 'sync', 'near'],
  ['file-pen', 'notebook-pen', 'near']
];

const { icons } = await loadIcons();
const byName = new Map(icons.map((ic) => [ic.name, ic]));
const args = process.argv.slice(2);

if (args.includes('--names')) {
  console.log(icons.map((ic) => ic.name).join('\n'));
  process.exit(0);
}
const missing = MAPPING.filter(([, kubai]) => kubai && !byName.has(kubai));
if (missing.length) {
  console.error(`No Kubai icon named: ${missing.map(([l, k]) => `${l} -> ${k}`).join(', ')}`);
  if (args.includes('--check')) process.exit(1);
}
if (args.includes('--check')) process.exit(0);

// ---------- Current Lucide paths, read from the macro so the page cannot drift from it ----------
const macro = fs.readFileSync(path.join(root, 'lindra/templates/icons.html'), 'utf8');
const lucide = new Map();
for (const m of macro.matchAll(/\{%-?\s*(?:el)?if name == "([^"]+)"\s*-?%\}\s*([\s\S]*?)\s*\{%-?\s*(?:elif|endif)/g)) lucide.set(m[1], m[2].trim());
for (const [name] of MAPPING) if (!lucide.has(name)) throw new Error(`icons.html has no icon "${name}"`);

let uid = 0;
const lucideSVG = (name, size, color) => `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="${color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${lucide.get(name)}</svg>`;
// Every placement needs its own gradient and filter ids, or two icons on one page share them.
const kubaiSVG = (name, size, opts) => renderSVG(byName.get(name), { size, k: `p${uid++}`, ...opts });
// The live form of an icon, as Kubai's own element writes it: one markup string whose fills are
// colour-mix() steps over `color`, so it follows currentColor like the Lucide icons do, and the
// box has no padding. This is what an inline Jinja macro would emit.
const inlineSVG = (name, size, { color, hover = false, soft = false } = {}) => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 -3 31 31" width="${size}" height="${size}" fill="none" overflow="visible" aria-hidden="true" focusable="false" style="color:${color}${soft ? ';--ki-c:color-mix(in srgb,currentColor 90%,#fff);--ki-e:color-mix(in srgb,currentColor 84%,#000);--ki-w:color-mix(in srgb,currentColor 65%,#000);--ki-l:72%' : ''}">${renderInner(byName.get(name), { k: `p${uid++}`, hover, paint: 'css', names: false })}</svg>`;

// ---------- Contrast ----------
const lin = (c) => { const v = c / 255; return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
const lum = (h) => { const [r, g, b] = [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16)); return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b); };
const ratio = (a, b) => { const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x); return (hi + 0.05) / (lo + 0.05); };

/** Every colour an icon paints with, counted by how many shapes use it. White marks are left out. */
function paints(svg) {
  const count = new Map();
  for (const m of svg.matchAll(/(?:fill|stroke|stop-color)="(#[0-9A-Fa-f]{6})"/g)) {
    const c = m[1].toUpperCase();
    if (c !== '#FFFFFF') count.set(c, (count.get(c) || 0) + 1);
  }
  return count;
}
function summary(svg) {
  const count = paints(svg);
  const all = [...count.keys()];
  const body = [...count].sort((a, b) => b[1] - a[1])[0][0];
  const dark = all.reduce((a, b) => (lum(a) <= lum(b) ? a : b));
  const light = all.reduce((a, b) => (lum(a) >= lum(b) ? a : b));
  return { body, dark, light };
}

const f2 = (n) => n.toFixed(2);
const rows = MAPPING.map(([l, k, fit]) => {
  const out = { lucide: l, kubai: k, fit };
  for (const accent of ['Teal', 'Ink']) {
    const s = summary(kubaiSVG(k, 24, { accent: ACCENTS[accent] }));
    out[accent] = { ...s, body: { hex: s.body, paper: ratio(s.body, SURFACES.Paper), white: ratio(s.body, SURFACES.White) }, dark: { hex: s.dark, paper: ratio(s.dark, SURFACES.Paper), white: ratio(s.dark, SURFACES.White) }, light: { hex: s.light, paper: ratio(s.light, SURFACES.Paper), white: ratio(s.light, SURFACES.White) } };
  }
  return out;
});

// ---------- Results document ----------
let md = `# Icon comparison results (LFR-13)

Generated by \`scripts/kubai_icons.mjs\` from \`docs/kubai-icons/\` (kubai-icons-static 0.5.1 sources) and \`lindra/templates/icons.html\`. Do not edit by hand. Open \`index.html\` next to this file for the side-by-side renders.

## Mapping: 27 current icons to Kubai names

| # | Lucide (now) | Kubai | Fit |
| --- | --- | --- | --- |
${rows.map((r, i) => `| ${i + 1} | \`${r.lucide}\` | ${r.kubai ? `\`${r.kubai}\`` : 'none'} | ${r.fit} |`).join('\n')}

## Contrast of the recoloured icons

WCAG 2 relative luminance, same formula as \`scripts/contrast_check.py\`. Kubai icons are not one stroke colour. Each icon has an outline in a deep shade of the accent, gradient fills that run from the accent toward white, and white marks inside. The table gives three colours per icon: the **outline** (darkest paint), the **body** (the colour most shapes use) and the **lightest** fill, each against Paper \`${SURFACES.Paper}\` and White. WCAG asks 3 to 1 for a graphic that carries meaning (1.4.11); the shell's icons are decorative next to text, so this is the bar the outline has to clear to stay visible, and the body is what fills the shape.

`;
for (const accent of ['Teal', 'Ink']) {
  md += `### Recoloured to ${accent} \`${ACCENTS[accent]}\`\n\n| Kubai icon | Outline | on Paper | on White | Body | on Paper | on White | Lightest | on Paper | on White |\n| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n`;
  for (const r of rows) {
    const a = r[accent];
    md += `| \`${r.kubai}\` | \`${a.dark.hex}\` | ${f2(a.dark.paper)} | ${f2(a.dark.white)} | \`${a.body.hex}\` | ${f2(a.body.paper)} | ${f2(a.body.white)} | \`${a.light.hex}\` | ${f2(a.light.paper)} | ${f2(a.light.white)} |\n`;
  }
  const min = (key, surf) => Math.min(...rows.map((r) => r[accent][key][surf]));
  md += `\nRange over the 27 icons: outline ${f2(min('dark', 'paper'))} to 1 on Paper, body ${f2(min('body', 'paper'))} to 1 on Paper, lightest fill ${f2(min('light', 'paper'))} to 1 on Paper.\n\n`;
}
md += `### For reference, the current Lucide strokes

| Stroke colour | on Paper | on White |
| --- | --- | --- |
| Ink \`#243331\` | ${f2(ratio('#243331', SURFACES.Paper))} | ${f2(ratio('#243331', SURFACES.White))} |
| Ink secondary \`#4F5F5D\` | ${f2(ratio('#4F5F5D', SURFACES.Paper))} | ${f2(ratio('#4F5F5D', SURFACES.White))} |
| Teal \`#245B57\` | ${f2(ratio('#245B57', SURFACES.Paper))} | ${f2(ratio('#245B57', SURFACES.White))} |
`;
fs.mkdirSync(outDir, { recursive: true });
fs.writeFileSync(path.join(outDir, 'results.md'), md);

// ---------- Comparison page ----------
const SIZES = [18, 24];
const cell = (svg) => `<td>${svg}</td>`;
function table(surface) {
  const head = SIZES.flatMap((s) => [`Lucide ${s}`, `Kubai blue ${s}`, `Kubai Teal ${s}`, `Kubai Ink ${s}`, `Inline, Teal ${s}`]);
  const tr = rows.map((r, i) => {
    const cells = SIZES.flatMap((s) => [
      cell(lucideSVG(r.lucide, s, '#243331')),
      cell(kubaiSVG(r.kubai, s, { accent: ACCENTS['Kubai blue'] })),
      cell(kubaiSVG(r.kubai, s, { accent: ACCENTS.Teal })),
      cell(kubaiSVG(r.kubai, s, { accent: ACCENTS.Ink })),
      cell(inlineSVG(r.kubai, s, { color: ACCENTS.Teal }))
    ]);
    return `<tr><th scope="row">${i + 1}. <code>${r.lucide}</code><small>${r.kubai ? `Kubai <code>${r.kubai}</code> (${r.fit})` : 'no Kubai match'}</small></th>${cells.join('')}</tr>`;
  });
  return `<section class="surface" style="background:${SURFACES[surface]}"><h2>On ${surface} <code>${SURFACES[surface]}</code></h2><table><thead><tr><th></th>${head.map((h) => `<th scope="col">${h}</th>`).join('')}</tr></thead><tbody>${tr.join('')}</tbody></table></section>`;
}
const states = (accent) => rows.map((r) => `<tr><th scope="row"><code>${r.kubai}</code></th>${['Paper', 'White'].map((surf) => `<td style="background:${SURFACES[surf]}">${[false, true].map((hover) => kubaiSVG(r.kubai, 24, { accent: ACCENTS[accent], hover })).join('')}${kubaiSVG(r.kubai, 24, { accent: ACCENTS[accent], variant: 'soft' })}</td>`).join('')}</tr>`).join('');

const page = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Icon comparison, LFR-13</title>
<style>
  :root { color-scheme: light; --ink: #243331; --paper: #F7F5F0; --muted: #4F5F5D; }
  body { margin: 0; padding: 24px 32px 48px; background: var(--paper); color: var(--ink); font: 15px/1.5 system-ui, sans-serif; }
  h1 { font-size: 24px; margin: 0 0 8px; } h2 { font-size: 18px; margin: 0 0 12px; }
  p { max-width: 72ch; margin: 0 0 12px; } code { font-size: 13px; }
  .surface { padding: 16px; margin: 24px 0; border: 1px solid #D9D5CA; border-radius: 12px; overflow-x: auto; }
  table { border-collapse: collapse; }
  th, td { padding: 8px 12px; text-align: center; vertical-align: middle; border-bottom: 1px solid rgba(36, 51, 49, 0.08); }
  th[scope=row] { text-align: left; font-weight: 400; white-space: nowrap; } th[scope=row] small { display: block; color: var(--muted); }
  thead th { font-weight: 500; font-size: 13px; color: var(--muted); }
  td svg { display: inline-block; vertical-align: middle; margin: 0 2px; }
  .pair td { padding: 8px 24px; }
</style>
</head>
<body>
<h1>Icon comparison: current Lucide set against Kubai Icons</h1>
<p>Generated by <code>scripts/kubai_icons.mjs</code> from <code>docs/kubai-icons/</code>. Nothing here loads from the network and the page is not served by the application. Lucide is drawn in Ink. The Kubai columns are the pinned sources rendered with one accent at build time: Kubai's own blue, Teal <code>#245B57</code> and Ink <code>#243331</code>. A static Kubai file keeps room for its shadow, so at the same box size the drawing is smaller than a Lucide icon. The "Inline" column is the markup Kubai's own element writes: no padding, and the colours follow <code>currentColor</code> (here set to Teal), so a status tone could still recolour it with CSS.</p>
${table('Paper')}
${table('White')}
<section class="surface"><h2>Hover end pose and the soft variant, Teal</h2>
<p>Each cell shows rest, the end of the hover motion, then the soft variant, all in Teal. The motion itself is not in the static files: Kubai moves shapes with a script that rewrites path data and transforms every frame. With <code>prefers-reduced-motion: reduce</code> its runtime skips the motion and jumps to the end pose, so the second icon is what a reduced-motion reader sees on hover.</p>
<table><thead><tr><th></th><th scope="col">on Paper</th><th scope="col">on White</th></tr></thead><tbody class="pair">${states('Teal')}</tbody></table></section>
<section class="surface"><h2>Hover end pose and the soft variant, Ink</h2>
<table><thead><tr><th></th><th scope="col">on Paper</th><th scope="col">on White</th></tr></thead><tbody class="pair">${states('Ink')}</tbody></table></section>
</body>
</html>
`;
fs.writeFileSync(path.join(outDir, 'index.html'), page);
console.log(`wrote ${path.relative(root, outDir)}/index.html and results.md (${rows.length} icons)`);
