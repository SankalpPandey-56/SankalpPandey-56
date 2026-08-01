#!/usr/bin/env python3
"""fetch_contributions.py — scrape real daily contribution counts.

Pure standard library (no pip packages, no GitHub token). Fetches
https://github.com/users/<username>/contributions — the same public HTML
fragment the profile page itself uses — parses the day cells, and writes
data/contributions.json with the raw days plus derived stats.

The JSON schema mirrors AVIVASHISHTA29's render_heatmap_svg.py:
  days[], total_contributions, active_days, avg_per_active_day,
  current_streak{length,start,end}, longest_streak{length,start,end},
  best_day{date,count}, monthly[], range{start,end}

Run daily by .github/workflows/update-profile-art.yml.
"""
import datetime
import json
import os
import re
import sys
import urllib.request
from html.parser import HTMLParser

from config import USERNAME

URL = f"https://github.com/users/{USERNAME}/contributions"
HEADERS = {"User-Agent": "profile-readme-bot/1.0", "Accept": "text/html"}
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "contributions.json")


class ContributionsParser(HTMLParser):
    """GitHub's current markup renders each day as:

        <td id="contribution-day-component-0-0" data-date="..." data-level="0"
            class="ContributionCalendar-day"></td>
        <tool-tip for="contribution-day-component-0-0">5 contributions on …</tool-tip>

    The count lives in the <tool-tip> which is a *sibling* of the td, keyed by
    the td's id via the tooltip's `for` attribute. We map td ids -> dates,
    collect tooltip text by `for` id, then merge the two.
    """

    def __init__(self):
        super().__init__()
        self.cells = {}      # td id -> {"date", "level"}
        self.tooltips = {}   # td id -> tooltip text
        self._in_tip = False
        self._tip_for = None
        self._tip_buf = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "td" and "data-date" in attrs and \
                "ContributionCalendar-day" in attrs.get("class", ""):
            self.cells[attrs.get("id")] = {
                "date": attrs["data-date"],
                "level": int(attrs.get("data-level", "0")),
                "count": int(attrs["data-count"]) if "data-count" in attrs else None,
            }
        elif tag == "tool-tip":
            self._in_tip = True
            self._tip_for = attrs.get("for")
            self._tip_buf = []

    def handle_endtag(self, tag):
        if tag == "tool-tip" and self._in_tip:
            self._in_tip = False
            if self._tip_for:
                self.tooltips[self._tip_for] = "".join(self._tip_buf)
            self._tip_for = None

    def handle_data(self, data):
        if self._in_tip:
            self._tip_buf.append(data)


def compute_current_streak(days):
    idx = len(days) - 1
    if days[idx]["count"] == 0:
        idx -= 1  # today isn't over yet — don't break the streak on it
    streak = 0
    end_idx = idx
    while idx >= 0 and days[idx]["count"] > 0:
        streak += 1
        idx -= 1
    start_idx = idx + 1
    if streak == 0:
        return 0, None, None
    return streak, days[start_idx]["date"], days[end_idx]["date"]


def compute_longest_streak(days):
    longest = run = 0
    longest_start = longest_end = None
    run_start_idx = None
    for i, d in enumerate(days):
        if d["count"] > 0:
            if run == 0:
                run_start_idx = i
            run += 1
            if run > longest:
                longest = run
                longest_start = days[run_start_idx]["date"]
                longest_end = days[i]["date"]
        else:
            run = 0
    return longest, longest_start, longest_end


def build_data(days):
    total = sum(d["count"] for d in days)
    active_days = sum(1 for d in days if d["count"] > 0)
    best = max(days, key=lambda d: d["count"])
    cur_len, cur_start, cur_end = compute_current_streak(days)
    long_len, long_start, long_end = compute_longest_streak(days)
    monthly = {}
    for d in days:
        key = d["date"][:7]
        monthly[key] = monthly.get(key, 0) + d["count"]
    monthly_list = [{"month": k, "total": v} for k, v in sorted(monthly.items())]
    return {
        "username": USERNAME,
        "generated_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "range": {"start": days[0]["date"], "end": days[-1]["date"]},
        "total_contributions": total,
        "active_days": active_days,
        "avg_per_active_day": round(total / active_days, 1) if active_days else 0,
        "current_streak": {"length": cur_len, "start": cur_start, "end": cur_end},
        "longest_streak": {"length": long_len, "start": long_start, "end": long_end},
        "best_day": {"date": best["date"], "count": best["count"]},
        "monthly": monthly_list,
        "days": days,
    }


def main():
    if USERNAME == "YOUR_USERNAME":
        sys.exit("Set USERNAME in scripts/config.py (or GITHUB_USERNAME) first.")
    print(f"Fetching contributions for @{USERNAME} …")
    try:
        req = urllib.request.Request(URL, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=30) as resp:
            html_text = resp.read().decode("utf-8", "replace")
    except Exception as exc:  # network or HTTP errors
        sys.exit(f"Failed to fetch {URL}: {exc}")

    parser = ContributionsParser()
    parser.feed(html_text)
    days = []
    for td_id, cell in parser.cells.items():
        count = cell["count"]  # data-count attr (older markup), if present
        if count is None:
            tip = parser.tooltips.get(td_id, "")
            if re.search(r"no contributions", tip, re.I):
                count = 0
            else:
                m = re.match(r"\s*(\d+)", tip)
                count = int(m.group(1)) if m else 0
        days.append({"date": cell["date"], "count": count})
    if not days:
        sys.exit("No contribution cells found — contributions may be hidden, "
                 "or GitHub's markup changed. Check the URL in a browser.")
    days.sort(key=lambda d: d["date"])
    data = build_data(days)
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(data, f, indent=2)
    print(f"wrote {OUT_PATH}: {data['total_contributions']} contributions, "
          f"current streak {data['current_streak']['length']}, "
          f"longest streak {data['longest_streak']['length']}")


if __name__ == "__main__":
    main()
