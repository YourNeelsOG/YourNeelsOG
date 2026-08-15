#!/usr/bin/env python3
"""Generates assets/terminal.svg: an animated fastfetch-style terminal profile.

Timeline (driven by a self-restarting SMIL master clock so the whole
animation loops):
  1. Command types out character-by-character with jittered delay.
  2. Enter is simulated; the typing cursor is hidden.
  3. fastfetch-style output pops in line-by-line.
  4. The final prompt appears with a blinking cursor, holds, then loops.
"""
import json
import random
import xml.sax.saxutils as sax
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "profile.json"
OUT_PATH = ROOT / "assets" / "terminal.svg"
AVATAR_ASCII_PATH = ROOT / "assets" / "avatar_ascii.txt"

HEADER_H = 40
PAD_X = 28
PAD_TOP = 22
PAD_BOTTOM = 22
LINE_H = 20
FONT_BODY = 14
FONT_PROMPT = 15
CHAR_W = FONT_PROMPT * 0.62  # monospace advance width estimate, matches prompt-text size
PROMPT_PREFIX = "➜  ~ "  # "➜  ~ "
FONT_STACK = "'JetBrains Mono','Fira Code','Cascadia Code',monospace"

# The ascii-art logo is much higher-resolution than the info column's text
# grid, so it gets its own (smaller, tighter) font/line-height rather than
# sharing LINE_H — otherwise a 90+ column logo would blow the layout out to
# an unreasonable width. Sized so individual characters stay legible at
# GitHub's actual README display width (~830px) — denser than this and it
# blurs into gray texture with no readable facial detail.
LOGO_FONT_SIZE = 11
LOGO_LINE_H = 12
LOGO_CHAR_W = LOGO_FONT_SIZE * 0.56

LOGO_X = PAD_X
TEXT_COL_W = 430  # budget for the label/value column, to the right of the logo
HOLD_MS = 3000  # how long the final prompt stays before looping


def esc(s):
    return sax.escape(str(s))


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def load_avatar_ascii():
    return AVATAR_ASCII_PATH.read_text().splitlines()


def build_fastfetch_rows(cfg):
    """Returns list of (label, value, kind) for the info column, in real
    fastfetch style: left-aligned "Label: Value" lines, no column padding,
    values start right after the colon rather than at a fixed offset."""
    rows = []
    title = f"{cfg['username'].lower()}@{cfg['host'].lower()}"
    rows.append((None, title, "title"))
    rows.append((None, "─" * len(title), "sep"))
    rows.append((None, "", "blank"))

    rows.append(("OS", cfg["os"], "row"))
    rows.append(("Host", cfg["host"], "row"))
    rows.append(("Kernel", cfg["kernel"], "row"))
    rows.append(("Shell", cfg["shell"], "row"))
    rows.append(("DE", cfg["desktop"], "row"))
    rows.append(("Terminal", cfg["terminal"], "row"))
    rows.append((None, "", "blank"))

    langs = cfg["languages"]
    rows.append(("Languages", langs[0], "row"))
    for extra in langs[1:]:
        rows.append((None, extra, "cont"))
    rows.append((None, "", "blank"))

    tools = cfg["tools"]
    rows.append(("Tools", tools[0], "row"))
    for extra in tools[1:]:
        rows.append((None, extra, "cont"))
    rows.append((None, "", "blank"))

    rows.append((None, "GitHub", "title2"))
    stats = cfg["stats"]
    stat_lines = [
        ("Repositories", stats["repositories"]),
        ("Contributions", stats["contributions"]),
        ("Stars", stats["stars"]),
        ("Followers", stats["followers"]),
    ]
    for label, value in stat_lines:
        rows.append((label, value, "row"))

    return rows


def jittered_typing(command, base_ms, jitter_ms, seed=42):
    rng = random.Random(seed)
    cumulative = [0]
    t = 0
    for _ in command:
        delay = max(20, base_ms + rng.randint(-jitter_ms, jitter_ms))
        t += delay
        cumulative.append(t)
    return cumulative


def discrete_animate(attr, key_times, values, dur_s, begin_expr, extra=""):
    kt = ";".join(f"{k:.4f}" for k in key_times)
    vals = ";".join(str(v) for v in values)
    return (
        f'<animate attributeName="{attr}" calcMode="discrete" '
        f'keyTimes="{kt}" values="{vals}" dur="{dur_s:.3f}s" '
        f'begin="{begin_expr}" fill="freeze" {extra}/>'
    )


def flash(attr, base_value, target_value, target_begin_expr):
    """A one-shot attribute change (used for freeze-and-forget reveals/hides)
    needs an explicit reset back to its base value at the top of every loop
    cycle — otherwise fill="freeze" leaves last cycle's end value on screen
    until the new instance fires, so old output bleeds into the next replay."""
    reset = (
        f'<animate attributeName="{attr}" values="{base_value};{base_value}" '
        f'dur="0.01s" begin="masterClock.begin" fill="freeze"/>'
    )
    transition = (
        f'<animate attributeName="{attr}" values="{base_value};{target_value}" '
        f'dur="0.01s" begin="{target_begin_expr}" fill="freeze"/>'
    )
    return reset + transition


def generate(cfg):
    colors = cfg["colors"]
    timing = cfg["timing"]
    command = cfg["command"]

    logo_rows = load_avatar_ascii()
    logo_cols = max(len(r) for r in logo_rows)
    logo_rows = [r.ljust(logo_cols) for r in logo_rows]
    logo_px_w = logo_cols * LOGO_CHAR_W
    logo_px_h = len(logo_rows) * LOGO_LINE_H
    width = LOGO_X + logo_px_w + 30 + TEXT_COL_W + PAD_X

    info_rows = build_fastfetch_rows(cfg)
    text_px_h = len(info_rows) * LINE_H
    content_px_h = max(logo_px_h, text_px_h)

    # Push the text column as far right as the longest line allows, so it
    # finishes flush against the right border (like the padding budget
    # implied) instead of leaving a dead gap after short lines.
    char_w_body = FONT_BODY * 0.6
    char_w_title = (FONT_BODY + 2) * 0.6

    def line_extent(label, value, kind):
        value = str(value)
        if kind == "title":
            return len(value) * char_w_title
        if kind == "row":
            return (len(str(label)) + 2 + len(value)) * char_w_body
        if kind == "cont":
            return 18 + len(value) * char_w_body
        return len(value) * char_w_body  # sep, title2

    max_extent = max(
        (line_extent(label, value, kind) for label, value, kind in info_rows if kind != "blank"),
        default=0,
    )
    info_x = max(LOGO_X + logo_px_w + 30, width - PAD_X - max_extent)

    body_lines_before = 2  # command line + blank
    body_h = body_lines_before * LINE_H + content_px_h + LINE_H  # + final prompt row
    total_h = HEADER_H + PAD_TOP + body_h + PAD_BOTTOM

    # ---- timing ----
    cumulative_ms = jittered_typing(command, timing["char_delay_ms"], timing["char_jitter_ms"])
    t_type_ms = cumulative_ms[-1]
    key_times = [c / t_type_ms for c in cumulative_ms]
    key_times[-1] = 1.0
    widths = [round(i * CHAR_W, 2) for i in range(len(cumulative_ms))]

    t_enter_ms = t_type_ms + timing["post_type_pause_ms"]
    t_fastfetch_start_ms = t_enter_ms + timing["enter_pause_ms"]

    row_reveal_ms = []
    t = t_fastfetch_start_ms
    for _ in info_rows:
        row_reveal_ms.append(t)
        t += timing["fastfetch_line_delay_ms"]
    t_final_prompt_ms = t + 150

    total_cycle_ms = t_final_prompt_ms + HOLD_MS + timing["loop_pause_ms"]
    total_cycle_s = total_cycle_ms / 1000

    # ---- geometry ----
    body_top = HEADER_H + PAD_TOP
    cmd_y = body_top + LINE_H - 5
    prompt_x = PAD_X
    prompt_prefix_w = len(PROMPT_PREFIX) * CHAR_W
    cmd_text_x = prompt_x + prompt_prefix_w

    fastfetch_top = body_top + body_lines_before * LINE_H

    final_prompt_y = fastfetch_top + content_px_h + LINE_H - 5

    svg = []
    svg.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {total_h}" '
        f'width="{width}" height="{total_h}" font-family="{FONT_STACK}" xml:space="preserve">'
    )

    svg.append(f"""
<defs>
  <clipPath id="window-clip"><rect x="0" y="0" width="{width}" height="{total_h}" rx="10"/></clipPath>
  <style>
    .body-text {{ font-size: {FONT_BODY}px; }}
    .prompt-text {{ font-size: {FONT_PROMPT}px; }}
  </style>
</defs>
""")

    # master clock: self-restarting, drives every other animation's begin
    svg.append(
        f'<rect x="0" y="0" width="1" height="1" opacity="0">'
        f'<animate id="masterClock" attributeName="opacity" values="0;0" dur="{total_cycle_s:.3f}s" '
        f'begin="0s;masterClock.end"/></rect>'
    )

    svg.append('<g id="terminal-window" clip-path="url(#window-clip)">')
    svg.append(
        f'<rect x="0" y="0" width="{width}" height="{total_h}" rx="10" '
        f'fill="{colors["background"]}" stroke="{colors["border"]}" stroke-width="1"/>'
    )

    # header
    svg.append('<g id="terminal-header">')
    svg.append(f'<rect x="0" y="0" width="{width}" height="{HEADER_H}" fill="{colors["window_chrome"]}"/>')
    svg.append(f'<line x1="0" y1="{HEADER_H}" x2="{width}" y2="{HEADER_H}" stroke="{colors["border"]}"/>')
    for i, c in enumerate([colors["dot_red"], colors["dot_yellow"], colors["dot_green"]]):
        svg.append(f'<circle cx="{22 + i * 20}" cy="{HEADER_H / 2}" r="6" fill="{c}"/>')
    svg.append(
        f'<text x="{width - PAD_X}" y="{HEADER_H / 2 + 4}" text-anchor="end" '
        f'class="body-text" fill="{colors["text_secondary"]}">{esc(cfg["username"])}.sh</text>'
    )
    svg.append("</g>")

    # ---- command line (typed) ----
    svg.append(f'<g id="prompt">')
    svg.append(
        f'<text x="{prompt_x}" y="{cmd_y}" class="prompt-text" xml:space="preserve" fill="{colors["prompt"]}">'
        f'{esc(PROMPT_PREFIX)}</text>'
    )
    svg.append("</g>")

    svg.append(f'<clipPath id="typing-clip"><rect x="{cmd_text_x}" y="{cmd_y - FONT_PROMPT}" '
                f'height="{FONT_PROMPT + 8}">'
                f'{discrete_animate("width", key_times, widths, t_type_ms / 1000, "masterClock.begin")}'
                f'</rect></clipPath>')

    svg.append(
        f'<g id="command" clip-path="url(#typing-clip)">'
        f'<text x="{cmd_text_x}" y="{cmd_y}" class="prompt-text" '
        f'fill="{colors["text_primary"]}">{esc(command)}</text></g>'
    )

    # typing cursor: tracks reveal width, solid while typing, hides after enter
    cursor_xs = [cmd_text_x + w for w in widths]
    svg.append(
        f'<g id="cursor">'
        f'<rect y="{cmd_y - FONT_PROMPT + 2}" width="{CHAR_W:.1f}" height="{FONT_PROMPT}" '
        f'fill="{colors["text_primary"]}">'
        f'{discrete_animate("x", key_times, [round(x, 2) for x in cursor_xs], t_type_ms / 1000, "masterClock.begin")}'
        f'{flash("opacity", 1, 0, f"masterClock.begin+{t_enter_ms}ms")}'
        f'</rect></g>'
    )

    # ---- fastfetch output ----
    svg.append('<g id="fastfetch">')

    for i, line in enumerate(logo_rows):
        y = fastfetch_top + i * LOGO_LINE_H + LOGO_FONT_SIZE
        svg.append(
            f'<text x="{LOGO_X}" y="{y}" font-size="{LOGO_FONT_SIZE}" fill="{colors["accent"]}" '
            f'xml:space="preserve" opacity="0">'
            f'{flash("opacity", 0, 1, f"masterClock.begin+{t_fastfetch_start_ms}ms")}'
            f'{esc(line)}</text>'
        )

    for i, (label, value, kind) in enumerate(info_rows):
        y = fastfetch_top + i * LINE_H + 14
        reveal_ms = row_reveal_ms[i]
        if kind == "blank" or (not label and not value):
            continue
        if kind == "title":
            fill, size, weight = colors["accent"], FONT_BODY + 2, "700"
        elif kind == "title2":
            fill, size, weight = colors["accent"], FONT_BODY, "700"
        elif kind == "sep":
            fill, size, weight = colors["text_secondary"], FONT_BODY, "400"
        else:
            fill, size, weight = colors["text_primary"], FONT_BODY, "400"

        if kind == "row":
            svg.append(
                f'<text x="{info_x}" y="{y}" font-size="{size}" '
                f'xml:space="preserve" opacity="0">'
                f'{flash("opacity", 0, 1, f"masterClock.begin+{reveal_ms}ms")}'
                f'<tspan fill="{colors["label"]}" font-weight="700">{esc(label)}: </tspan>'
                f'<tspan fill="{colors["text_primary"]}">{esc(value)}</tspan>'
                f'</text>'
            )
        else:
            x = info_x + (18 if kind == "cont" else 0)
            svg.append(
                f'<text x="{x}" y="{y}" font-size="{size}" '
                f'font-weight="{weight}" xml:space="preserve" fill="{fill}" opacity="0">'
                f'{flash("opacity", 0, 1, f"masterClock.begin+{reveal_ms}ms")}'
                f'{esc(value)}</text>'
            )
    svg.append("</g>")

    # ---- final prompt ----
    svg.append(
        f'<g id="final-prompt" opacity="0">'
        f'{flash("opacity", 0, 1, f"masterClock.begin+{t_final_prompt_ms}ms")}'
        f'<text x="{prompt_x}" y="{final_prompt_y}" class="prompt-text" xml:space="preserve" fill="{colors["prompt"]}">'
        f'{esc(PROMPT_PREFIX)}</text>'
        f'<rect x="{prompt_x + prompt_prefix_w:.1f}" y="{final_prompt_y - FONT_PROMPT + 2}" '
        f'width="{CHAR_W:.1f}" height="{FONT_PROMPT}" fill="{colors["text_primary"]}">'
        f'<animate attributeName="opacity" values="1;1;0;0;1" '
        f'dur="{timing["final_cursor_blink_ms"] * 2 / 1000:.3f}s" '
        f'begin="masterClock.begin+{t_final_prompt_ms}ms" repeatCount="indefinite"/>'
        f'</rect></g>'
    )

    svg.append("</g>")  # terminal-window
    svg.append("</svg>")
    return "\n".join(svg)


def main():
    cfg = load_config()
    svg = generate(cfg)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(svg)
    print(f"wrote {OUT_PATH} ({len(svg)} bytes)")


if __name__ == "__main__":
    main()
