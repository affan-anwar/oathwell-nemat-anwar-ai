"""Theme tokens and the accessibility rules every saved theme must pass."""
import re

KEYS = ["bg", "surface", "surface2", "text", "muted", "border", "primary", "primaryText", "success", "warning", "danger", "accent", "sidebar", "chart1", "chart2"]
DEFAULTS = {  # premium black and emerald. No blue, cyan or purple unless the Owner chooses them.
    "dark": {"bg": "#030907", "surface": "#08130f", "surface2": "#0d1d17", "text": "#f1f5f3", "muted": "#9db3aa", "border": "#16382c",
             "primary": "#10e08a", "primaryText": "#03120b", "success": "#34d399", "warning": "#fbbf24", "danger": "#f87171", "accent": "#6ee7b7",
             "sidebar": "#020605", "chart1": "#10e08a", "chart2": "#e5efe9"},
    "light": {"bg": "#eef5f1", "surface": "#ffffff", "surface2": "#f4f9f6", "text": "#0a1f17", "muted": "#4b6358", "border": "#d3e2da",
              "primary": "#046c4e", "primaryText": "#ffffff", "success": "#047857", "warning": "#92400e", "danger": "#b91c1c", "accent": "#065f46",
              "sidebar": "#ffffff", "chart1": "#046c4e", "chart2": "#0a1f17"},
}
LABELS = {"bg": "Page background", "surface": "Card surface", "surface2": "Raised surface", "text": "Text", "muted": "Secondary text", "border": "Borders",
          "primary": "Primary / buttons", "primaryText": "Text on buttons", "success": "Success", "warning": "Warning", "danger": "Error", "accent": "AI accent",
          "sidebar": "Sidebar", "chart1": "Chart line 1", "chart2": "Chart line 2"}
# (foreground, background, minimum ratio, plain-English name). WCAG AA for text is 4.5.
PAIRS = [("text", "bg", 4.5), ("text", "surface", 4.5), ("text", "surface2", 4.5), ("muted", "bg", 4.5), ("muted", "surface", 4.5), ("muted", "surface2", 4.5),
         ("primary", "bg", 5.0), ("primary", "surface", 5.0), ("primaryText", "primary", 4.5), ("success", "surface", 5.0), ("warning", "surface", 5.0),
         ("danger", "surface", 5.0), ("accent", "surface", 5.0), ("text", "sidebar", 4.5), ("muted", "sidebar", 4.5)]  # coloured text needs 5:1: it also appears on tinted badges
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
MODES = ("dark", "light")


def _lum(h: str) -> float:
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contrast(a: str, b: str) -> float:
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return round((la + 0.05) / (lb + 0.05), 2)


def validate(tokens: dict | None):
    """Returns (clean, problems). `clean` always holds every key for both modes (missing ones come from the defaults)."""
    clean, problems = {}, []
    tokens = tokens or {}
    for mode in tokens:
        if mode not in MODES:
            problems.append({"mode": mode, "key": None, "message": f"Unknown mode {mode!r}"})
    for mode in MODES:
        given = tokens.get(mode) or {}
        merged = dict(DEFAULTS[mode])
        for k, v in given.items():
            if k not in KEYS:
                problems.append({"mode": mode, "key": k, "message": f"Unknown colour {k!r}"})
            elif not isinstance(v, str) or not HEX.match(v):
                problems.append({"mode": mode, "key": k, "message": f"{LABELS[k]} must be a colour like #1a2b3c"})
            else:
                merged[k] = v.lower()
        clean[mode] = merged
        if not any(p["mode"] == mode for p in problems):
            for fg, bg, need in PAIRS:
                r = contrast(merged[fg], merged[bg])
                if r < need:
                    problems.append({"mode": mode, "key": fg, "message": f"{LABELS[fg]} on {LABELS[bg].lower()} has contrast {r}:1. At least {need}:1 is needed so people can read it", "ratio": r})
    return clean, problems
