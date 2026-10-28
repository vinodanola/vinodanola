"""Generate terminal-style SVG cards for the GitHub profile README.

Outputs:
  assets/contributions.svg  - contribution heatmap
  assets/ascii.svg          - ASCII-art avatar in a terminal window
  assets/stats.svg          - streaks, totals and monthly bar chart

Env: GITHUB_TOKEN (required), GH_USER (default: vinodanola)
"""

import io
import json
import os
import urllib.request
from collections import OrderedDict
from datetime import date, timedelta
from html import escape

USER = os.environ.get("GH_USER", "vinodanola")
PROMPT = f"{USER.split('-')[0][:12].lower()}@github ~ $"
OUT = os.path.join(os.path.dirname(__file__), "..", "assets")

BG = "#0d1117"
PANEL = "#161b22"
BORDER = "#30363d"
TEXT = "#e6edf3"
MUTED = "#7d8590"
ACCENT = "#3fb950"
LEVELS = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]
# Fraction box (left, top, right, bottom) cropped from the GitHub avatar; ignored for a custom avatar.png
AVATAR_CROP = (0.25, 0.06, 0.75, 0.62)
CARD_W = 460
FONT = "ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,'Liberation Mono',monospace"


def graphql(query):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query}).encode(),
        headers={"Authorization": f"bearer {os.environ['GITHUB_TOKEN']}"},
    )
    with urllib.request.urlopen(req) as r:
        body = json.load(r)
    if "errors" in body:
        raise SystemExit(body["errors"])
    return body["data"]


def fetch():
    q = """{ user(login: "%s") { name avatarUrl
      contributionsCollection { contributionCalendar { totalContributions
        weeks { contributionDays { date contributionCount weekday } } } } } }""" % USER
    u = graphql(q)["user"]
    weeks = [
        [(date.fromisoformat(d["date"]), d["contributionCount"], d["weekday"]) for d in w["contributionDays"]]
        for w in u["contributionsCollection"]["contributionCalendar"]["weeks"]
    ]
    return u, weeks


def level(count, maxc):
    if count == 0:
        return 0
    return min(4, 1 + int(3 * count / max(maxc, 1)))


def svg(w, h, body, extra_css=""):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="{FONT}">
<style>text{{fill:{TEXT}}} .m{{fill:{MUTED}}} .a{{fill:{ACCENT}}} {extra_css}</style>
<rect width="{w}" height="{h}" rx="12" fill="{BG}" stroke="{BORDER}"/>
{body}
</svg>
"""


def contributions_svg(weeks, total):
    cell, gap = 13, 3
    left, top = 48, 70
    days = [d for w in weeks for d in w]
    maxc = max((c for _, c, _ in days), default=0)
    w = 2 * left + len(weeks) * (cell + gap) - gap
    h = top + 7 * (cell + gap) + 46
    out = [f'<text x="{w / 2}" y="34" text-anchor="middle" font-size="15" font-weight="700">'
           f'{escape(PROMPT)} ./contributions.sh</text>']
    last_month = None
    for i, wk in enumerate(weeks):
        x = left + i * (cell + gap)
        m = wk[0][0].month
        if m != last_month and wk[0][0].day <= 7:
            out.append(f'<text x="{x}" y="{top - 10}" font-size="10" class="m">{wk[0][0]:%b}</text>')
            last_month = m
        for d, c, wd in wk:
            y = top + wd * (cell + gap)
            out.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" '
                       f'fill="{LEVELS[level(c, maxc)]}"><title>{c} on {d:%b %-d, %Y}</title></rect>')
    for wd, label in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        out.append(f'<text x="{left - 8}" y="{top + wd * (cell + gap) + 10}" text-anchor="end" '
                   f'font-size="10" class="m">{label}</text>')
    by = top + 7 * (cell + gap) + 20
    out.append(f'<text x="{left}" y="{by}" font-size="12" font-weight="700">{total:,} contribution{"" if total == 1 else "s"} in the last year</text>')
    lx = w - left - 5 * (cell + gap) - 28
    out.append(f'<text x="{lx - 8}" y="{by}" text-anchor="end" font-size="10" class="m">Less</text>')
    for i, col in enumerate(LEVELS):
        out.append(f'<rect x="{lx + i * (cell + gap)}" y="{by - 10}" width="{cell - 2}" height="{cell - 2}" rx="2" fill="{col}"/>')
    out.append(f'<text x="{lx + 5 * (cell + gap) + 2}" y="{by}" font-size="10" class="m">More</text>')
    return svg(w, h, "\n".join(out))


def window(w, h, title, body):
    dots = "".join(f'<circle cx="{20 + i * 14}" cy="18" r="4" fill="{c}"/>'
                   for i, c in enumerate(("#ff5f57", "#febc2e", "#28c840")))
    return svg(w, h, f'{dots}<text x="{w / 2}" y="22" text-anchor="middle" font-size="10" class="m">'
                     f'{escape(title)}</text><line x1="0" y1="36" x2="{w}" y2="36" stroke="{BORDER}"/>{body}',
               extra_css="@keyframes b{50%{opacity:0}} .cur{animation:b 1s step-end infinite}")


def ascii_svg(avatar_url, name, h):
    from PIL import Image, ImageOps

    custom = os.path.join(os.path.dirname(__file__), "..", "avatar.png")
    if os.path.exists(custom):
        img = Image.open(custom).convert("L")
    else:
        with urllib.request.urlopen(avatar_url.replace("v=4", "v=4&s=400")) as r:
            img = Image.open(io.BytesIO(r.read())).convert("L")
        W, H = img.size
        l, t, r_, b = AVATAR_CROP
        img = img.crop((int(l * W), int(t * H), int(r_ * W), int(b * H)))
    img = ImageOps.autocontrast(img, cutoff=2)
    img = img.point(lambda v: int(255 * (v / 255) ** 2.0))  # sink mid-tones so the background fades
    cols, cw, lh = 70, 6.0, 7.2  # monospace glyph ~0.6em wide at 10px
    rows = int(cols * img.height / img.width * cw / lh)
    max_rows = int((h - 36 - 64) / lh)
    if rows > max_rows:  # shrink width instead of squashing the picture
        rows, cols = max_rows, int(max_rows * img.width / img.height * lh / cw)
    img = img.resize((cols, rows), Image.LANCZOS)
    ramp = "   .:-=+*#%@"  # leading spaces drop dark background noise
    lines = []
    for y in range(rows):
        lines.append("".join(ramp[img.getpixel((x, y)) * (len(ramp) - 1) // 255] for x in range(cols)))
    w = CARD_W
    top = 36 + (h - 36 - 44 - rows * lh) / 2 + 8
    body = [f'<text font-size="10" class="m" xml:space="preserve" letter-spacing="0">']
    for i, line in enumerate(lines):
        body.append(f'<tspan x="{(w - cols * cw) / 2:.0f}" y="{top + i * lh:.1f}" textLength="{cols * cw:.0f}">{escape(line)}</tspan>')
    body.append("</text>")
    py = h - 18
    body.append(f'<text x="20" y="{py}" font-size="11"><tspan class="a">{escape(PROMPT)}</tspan> '
                f'whoami → <tspan font-weight="700">{escape(name)}</tspan></text>')
    body.append(f'<rect class="cur" x="{20 + (len(PROMPT) + len(name) + 11) * 6.6:.0f}" y="{py - 10}" '
                f'width="7" height="12" fill="{TEXT}"/>')
    return window(w, h, f"{USER}@github: ~/avatar", "\n".join(body))


def stats(weeks):
    days = sorted((d, c) for w in weeks for d, c, _ in w)[-365:]
    today = days[-1][0]
    active = [d for d, c in days if c]

    longest, cur_len, start, best_range = 0, 0, None, None
    for d, c in days:
        if c:
            cur_len += 1
            start = start if cur_len > 1 else d
            if cur_len > longest:
                longest, best_range = cur_len, (start, d)
        else:
            cur_len = 0

    current, cur_range = 0, None
    seq = days if days[-1][1] else days[:-1]  # today may still be in progress
    for d, c in reversed(seq):
        if not c:
            break
        current += 1
        cur_range = (d, cur_range[1] if cur_range else d)

    best_day = max(days, key=lambda x: x[1])
    total = sum(c for _, c in days)

    months = OrderedDict()
    m = date(today.year - 1, today.month, 1)
    for _ in range(13):
        months[(m.year, m.month)] = 0
        m = date(m.year + (m.month == 12), m.month % 12 + 1, 1)
    for d, c in days:
        if (d.year, d.month) in months:
            months[(d.year, d.month)] += c
    if len(months) > 12:
        months.popitem(last=False)

    rng = lambda r: f"{r[0]:%b %-d} – {r[1]:%b %-d}" if r else "—"
    return {
        "cards": [
            ("current streak", current, "day" if current == 1 else "days", rng(cur_range), True),
            ("longest streak", longest, "day" if longest == 1 else "days", rng(best_range), False),
            ("contributions", f"{total:,}", "", "in the last year", False),
            ("active days", len(active), f"/ {len(days)}", f"{round(100 * len(active) / max(len(days), 1))}% of the year", False),
            ("best day", best_day[1], "", f"{best_day[0]:%b %-d}" if best_day[1] else "—", False),
            ("avg / active day", f"{total / max(len(active), 1):.1f}", "", "contributions", False),
        ],
        "months": months,
    }


def stats_svg(s, height):
    w = CARD_W
    pad, gap = 16, 10
    cw = (w - 2 * pad - gap) / 2
    ch = 64
    out = []
    for i, (label, val, unit, sub, hl) in enumerate(s["cards"]):
        x = pad + (i % 2) * (cw + gap)
        y = 50 + (i // 2) * (ch + gap)
        out.append(f'<rect x="{x}" y="{y}" width="{cw}" height="{ch}" rx="6" fill="{PANEL}" stroke="{BORDER}"/>')
        out.append(f'<text x="{x + 12}" y="{y + 18}" font-size="10" class="m">$ {label}</text>')
        out.append(f'<text x="{x + 12}" y="{y + 42}" font-size="22" font-weight="700"{" class=\"a\"" if hl else ""}>'
                   f'{val}<tspan font-size="11" font-weight="400" class="m"> {escape(unit)}</tspan></text>')
        out.append(f'<text x="{x + 12}" y="{y + 56}" font-size="9" class="m">{escape(sub)}</text>')

    cy = 50 + 3 * (ch + gap)
    chh = height - cy - pad
    out.append(f'<rect x="{pad}" y="{cy}" width="{w - 2 * pad}" height="{chh}" rx="6" fill="{PANEL}" stroke="{BORDER}"/>')
    out.append(f'<text x="{pad + 12}" y="{cy + 18}" font-size="10" class="m">$ contributions / month</text>')
    vals = list(s["months"].items())
    peak = max((v for _, v in vals), default=0)
    plot_top, plot_bot = cy + 44, cy + chh - 24
    slot = (w - 2 * pad - 24) / len(vals)
    for i, ((yr, mo), v) in enumerate(vals):
        bh = (plot_bot - plot_top) * v / peak if peak else 0
        bh = max(bh, 2)
        x = pad + 12 + i * slot + slot * 0.18
        bw = slot * 0.64
        col = LEVELS[4] if v == peak and peak else LEVELS[3]
        out.append(f'<rect x="{x:.1f}" y="{plot_bot - bh:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="2" fill="{col}">'
                   f'<title>{v:,} in {date(yr, mo, 1):%b %Y}</title></rect>')
        if v == peak and peak:
            out.append(f'<text x="{x + bw / 2:.1f}" y="{plot_bot - bh - 5:.1f}" text-anchor="middle" font-size="9">{v:,}</text>')
        out.append(f'<text x="{x + bw / 2:.1f}" y="{plot_bot + 14}" text-anchor="middle" font-size="9" class="m">'
                   f'{date(yr, mo, 1):%b}</text>')
    return window(w, height, f"{USER}@github: ~/stats", "\n".join(out))


def main():
    os.makedirs(OUT, exist_ok=True)
    user, weeks = fetch()
    total = sum(c for w in weeks for _, c, _ in w)
    files = {"contributions.svg": contributions_svg(weeks, total)}
    # same size for both cards so they line up side by side in the README
    files["ascii.svg"] = ascii_svg(user["avatarUrl"], user["name"] or USER, 520)
    files["stats.svg"] = stats_svg(stats(weeks), 520)
    for name, content in files.items():
        with open(os.path.join(OUT, name), "w") as f:
            f.write(content)
        print("wrote", name)


if __name__ == "__main__":
    main()
