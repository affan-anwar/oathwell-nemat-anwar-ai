// Owner theme tokens become CSS variables. Components never hard-code colours.
export const VARS = { bg: "--bg", surface: "--sf", surface2: "--sf2", text: "--ink", muted: "--mu", border: "--ln", primary: "--pri", primaryText: "--btnt", success: "--ok", warning: "--wn", danger: "--bd", accent: "--ai", sidebar: "--side", chart1: "--c1", chart2: "--c2" };

export function tokensToCss(tokens) {
  return ["dark", "light"].map((mode) => {
    const t = tokens?.[mode];
    if (!t) return "";
    const decl = Object.entries(VARS).filter(([k]) => t[k]).map(([k, v]) => `${v}:${t[k]}`);
    if (t.primary) decl.push(`--btn:${t.primary}`);
    return `[data-theme=${mode}]{${decl.join(";")}}`;
  }).join("\n");
}

export function setStyle(id, css) {
  let el = document.getElementById(id);
  if (!css) { el?.remove(); return; }
  if (!el) { el = document.createElement("style"); el.id = id; document.head.appendChild(el); }
  el.textContent = css;
}

const lum = (h) => { const c = [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16) / 255).map((x) => (x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4)); return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]; };
export const contrast = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return Math.round(((x + 0.05) / (y + 0.05)) * 100) / 100; };
export const isHex = (v) => /^#[0-9a-fA-F]{6}$/.test(v || "");
// Same pairs and thresholds the server enforces, so the preview can warn before saving.
export const PAIRS = [["text", "bg", 4.5], ["text", "surface", 4.5], ["text", "surface2", 4.5], ["muted", "bg", 4.5], ["muted", "surface", 4.5], ["muted", "surface2", 4.5], ["primary", "bg", 5], ["primary", "surface", 5], ["primaryText", "primary", 4.5], ["success", "surface", 5], ["warning", "surface", 5], ["danger", "surface", 5], ["accent", "surface", 5], ["text", "sidebar", 4.5], ["muted", "sidebar", 4.5]];
export function problems(t, labels = {}) {
  const out = [];
  for (const [k, v] of Object.entries(t)) if (!isHex(v)) out.push(`${labels[k] || k} must be a colour like #1a2b3c`);
  if (out.length) return out;
  for (const [f, b, need] of PAIRS) { const r = contrast(t[f], t[b]); if (r < need) out.push(`${labels[f] || f} on ${(labels[b] || b).toLowerCase()} is ${r}:1. At least ${need}:1 is needed`); }
  return out;
}
