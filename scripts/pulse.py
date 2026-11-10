"""Draw the last 30 days of GitHub contributions as an ECG-style trace.

Each day is one heartbeat; the height of the spike follows that day's
contribution count. Output: assets/pulse.svg

Usage:
    GH_TOKEN=<token> python scripts/pulse.py [login]

In GitHub Actions the built-in GITHUB_TOKEN is enough.
"""

import json
import math
import os
import sys
import urllib.request
from datetime import date
from pathlib import Path

LOGIN = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("PULSE_LOGIN", "elaina-agi")
DAYS = 30
OUT = Path(__file__).resolve().parent.parent / "assets" / "pulse.svg"

W, H = 1200, 300
LEFT, RIGHT = 60, 1140
BASE = 214          # y of the flat baseline
MAX_SPIKE = 128     # tallest spike, in px

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


def fetch_days():
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("Set GH_TOKEN or GITHUB_TOKEN")
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": LOGIN}}).encode(),
        headers={"Authorization": f"bearer {token}", "User-Agent": "pulse-svg"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if payload.get("errors"):
        sys.exit(f"GraphQL error: {payload['errors']}")
    weeks = payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    days = [d for w in weeks for d in w["contributionDays"]]
    return [(date.fromisoformat(d["date"]), d["contributionCount"]) for d in days][-DAYS:]


def beat(x0, w, h):
    """Points of one heartbeat (P-QRS-T) starting at x0, w wide, R peak h tall."""
    if h == 0:
        return [(x0 + w, BASE)]
    return [
        (x0 + 0.16 * w, BASE),
        (x0 + 0.23 * w, BASE - 0.07 * h),   # P wave
        (x0 + 0.30 * w, BASE),
        (x0 + 0.38 * w, BASE + 0.09 * h),   # Q
        (x0 + 0.46 * w, BASE - h),          # R
        (x0 + 0.54 * w, BASE + 0.20 * h),   # S
        (x0 + 0.62 * w, BASE),
        (x0 + 0.72 * w, BASE - 0.13 * h),   # T wave
        (x0 + 0.84 * w, BASE),
        (x0 + w, BASE),
    ]


def build(days):
    counts = [c for _, c in days]
    total, peak = sum(counts), max(counts) or 1
    active = sum(1 for c in counts if c)
    step = (RIGHT - LEFT) / len(days)

    points = [(LEFT, BASE)]
    labels = []
    for i, (day, count) in enumerate(days):
        x0 = LEFT + i * step
        # sqrt scale keeps quiet days visible next to busy ones
        h = 0 if count == 0 else 16 + (MAX_SPIKE - 16) * math.sqrt(count / peak)
        points += beat(x0, step, h)
        if i % 5 == 0 or i == len(days) - 1:
            labels.append((x0 + step / 2, f"{day:%b} {day.day}"))
        if count == peak and count > 0 and not any(l[0] == "peak" for l in labels):
            labels.append(("peak", x0 + 0.46 * step, BASE - h - 12, count))

    path = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in points)

    grid = "".join(
        f'<line x1="{LEFT}" y1="{y}" x2="{RIGHT}" y2="{y}"/>' for y in range(70, 260, 24)
    ) + "".join(
        f'<line x1="{LEFT + i * step * 5:.1f}" y1="62" x2="{LEFT + i * step * 5:.1f}" y2="246"/>'
        for i in range(len(days) // 5 + 1)
    )

    ticks, peak_label = "", ""
    for label in labels:
        if label[0] == "peak":
            _, x, y, count = label
            peak_label = (
                f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="middle" class="mono" '
                f'font-size="13" fill="#ffd76a">{count}</text>'
            )
        else:
            x, text = label
            ticks += f'<text x="{x:.1f}" y="270" text-anchor="middle">{text}</text>'

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="Contribution pulse: {total} contributions in the last {len(days)} days, {active} active days, peak {peak} in one day">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#14122b"/>
      <stop offset="1" stop-color="#2b2256"/>
    </linearGradient>
    <linearGradient id="fade" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#a996ff" stop-opacity="0.35"/>
      <stop offset="1" stop-color="#a996ff"/>
    </linearGradient>
    <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="3" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <clipPath id="frame"><rect width="{W}" height="{H}" rx="20"/></clipPath>
    <path id="trace" pathLength="1000" d="{path}"/>
    <style>
      .sans {{ font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, 'Helvetica Neue', Arial, sans-serif; }}
      .mono {{ font-family: ui-monospace, 'SF Mono', 'Cascadia Code', Consolas, 'Liberation Mono', monospace; }}
      .grid line {{ stroke: #ffffff; stroke-opacity: 0.05; }}
      .ghost {{ fill: none; stroke: #a996ff; stroke-opacity: 0.22; stroke-width: 2; stroke-linejoin: round; }}
      .live {{ fill: none; stroke: url(#fade); stroke-width: 2.6; stroke-linejoin: round; stroke-linecap: round;
               stroke-dasharray: 1000; stroke-dashoffset: 1000; animation: draw 7s linear infinite; }}
      .heart {{ transform-origin: 72px 38px; animation: beat 1.1s ease-in-out infinite; }}
      .dot {{ opacity: 0; }}
      @keyframes draw {{ 0% {{ stroke-dashoffset: 1000; }} 72% {{ stroke-dashoffset: 0; }} 92% {{ stroke-dashoffset: 0; opacity: 1; }} 100% {{ stroke-dashoffset: 0; opacity: 0; }} }}
      @keyframes beat {{ 0%, 100% {{ transform: scale(1); }} 14% {{ transform: scale(1.28); }} 28% {{ transform: scale(1); }} 42% {{ transform: scale(1.16); }} 56% {{ transform: scale(1); }} }}
      @media (prefers-reduced-motion: reduce) {{
        .live {{ animation: none; stroke-dashoffset: 0; }}
        .heart {{ animation: none; }}
      }}
    </style>
  </defs>

  <g clip-path="url(#frame)">
    <rect width="{W}" height="{H}" fill="url(#bg)"/>
    <g class="grid">{grid}</g>

    <path class="heart" fill="#ff7a9c" d="M72 46 l-9.4 -9.2 a5.6 5.6 0 0 1 7.9 -7.9 l1.5 1.5 1.5 -1.5 a5.6 5.6 0 0 1 7.9 7.9z"/>
    <text x="92" y="44" class="mono" font-size="17" fill="#b9a9ff" letter-spacing="2">CONTRIBUTION PULSE</text>
    <text x="{RIGHT}" y="44" class="sans" font-size="17" fill="#d6d0f2" text-anchor="end"><tspan fill="#ffd76a" font-weight="700">{total}</tspan> contributions · {active} active days · last {len(days)} days</text>

    <use href="#trace" class="ghost"/>
    <use href="#trace" class="live" filter="url(#glow)"/>
    {peak_label}

    <circle class="dot" r="5" fill="#ffd76a" filter="url(#glow)">
      <animateMotion dur="7s" repeatCount="indefinite" keyPoints="0;1;1" keyTimes="0;0.72;1" calcMode="linear"><mpath href="#trace"/></animateMotion>
      <animate attributeName="opacity" dur="7s" repeatCount="indefinite" values="1;1;0;0" keyTimes="0;0.72;0.76;1"/>
    </circle>

    <g class="mono" font-size="12" fill="#8d84b8">{ticks}</g>
  </g>
</svg>
"""


def main():
    days = fetch_days()
    OUT.write_text(build(days), encoding="utf-8", newline="\n")
    print(f"wrote {OUT} ({sum(c for _, c in days)} contributions over {len(days)} days)")


if __name__ == "__main__":
    main()
