#!/usr/bin/env python3
"""scripts/update_readme.py
Updates dynamic sections of README.md:
  1. <!-- START_SECTION:daily_tip -->
  2. <!-- START_SECTION:recent_activity -->
Uses pure Python standard library.
"""
import datetime
import json
import os
import re
import urllib.request

USERNAME = "SankalpPandey-56"
README_PATH = os.path.join(os.path.dirname(__file__), "..", "README.md")

TIPS = [
    "In Unix, pseudo-terminals (PTYs) decouple the display terminal from the executing process, allowing programs like `termlens` to run full terminal applications headlessly with true ANSI sequence fidelity.",
    "Rust's borrow checker guarantees memory safety and data-race prevention at compile time without requiring a garbage collector.",
    "Declarative orchestration with tools like Kestra allows complex multi-step dependency graphs to be version-controlled and tested as code.",
    "Three.js leverages WebGL to render hardware-accelerated 3D scenes right inside the browser canvas without plugins.",
    "Accelerometers in modern MacBooks can be queried via low-level I/O Kit frameworks, turning physical lid taps into input triggers.",
    "Git commits are immutable snapshots of your repository tree identified by cryptographic hashes, not file diffs.",
    "Irreversible system actions (such as dropping databases or yanking packages) benefit significantly from proactive audit trails and human approval guardrails.",
    "Minimizing heap allocations in inner loops is often the fastest path to double performance in systems-level software.",
    "Using HTTP/2 or HTTP/3 multiplexing eliminates head-of-line blocking for concurrent network streams.",
    "Safe systems code isolates `unsafe` blocks into well-tested, tightly scoped abstractions that rigorously enforce invariants."
]

def get_daily_tip():
    day_of_year = datetime.datetime.now(datetime.timezone.utc).timetuple().tm_yday
    tip = TIPS[day_of_year % len(TIPS)]
    return f"> **💡 Systems Tip of the Day:** {tip}"

def get_recent_activity():
    url = f"https://api.github.com/users/{USERNAME}/events/public?per_page=30"
    req = urllib.request.Request(url, headers={"User-Agent": f"{USERNAME}-profile-updater"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            events = json.loads(resp.read().decode("utf-8"))
    except Exception as err:
        print(f"Could not fetch GitHub events: {err}")
        return "- Maintained active repositories and open-source contributions."

    items = []
    seen = set()
    for ev in events:
        repo_name = ev.get("repo", {}).get("name", "")
        repo_url = f"https://github.com/{repo_name}"
        ev_type = ev.get("type")

        key = (ev_type, repo_name)
        if key in seen or repo_name == f"{USERNAME}/{USERNAME}":
            continue
        seen.add(key)

        if ev_type == "PushEvent":
            items.append(f"- Pushed commits to [**{repo_name}**]({repo_url})")
        elif ev_type == "PullRequestEvent":
            action = ev.get("payload", {}).get("action", "contributed to")
            pr_num = ev.get("payload", {}).get("pull_request", {}).get("number")
            if pr_num:
                pr_url = f"https://github.com/{repo_name}/pull/{pr_num}"
                items.append(f"- PR [**#{pr_num}**]({pr_url}) ({action}) on [**{repo_name}**]({repo_url})")
            else:
                items.append(f"- PR ({action}) on [**{repo_name}**]({repo_url})")
        elif ev_type == "CreateEvent" and ev.get("payload", {}).get("ref_type") == "repository":
            items.append(f"- Created repository [**{repo_name}**]({repo_url})")
        elif ev_type == "ForkEvent":
            items.append(f"- Forked repository [**{repo_name}**]({repo_url})")

        if len(items) >= 5:
            break

    if not items:
        items.append("- Actively developing projects and contributing to open-source.")
    return "\n".join(items)

def replace_section(content, section_name, new_data):
    pattern = rf"(<!-- START_SECTION:{section_name} -->\n).*?(\n<!-- END_SECTION:{section_name} -->)"
    replacement = rf"\g<1>{new_data}\g<2>"
    return re.sub(pattern, replacement, content, flags=re.DOTALL)

def main():
    if not os.path.exists(README_PATH):
        print(f"File not found: {README_PATH}")
        return

    with open(README_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    tip = get_daily_tip()
    activity = get_recent_activity()

    content = replace_section(content, "daily_tip", tip)
    content = replace_section(content, "recent_activity", activity)

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    print("Successfully updated README.md with daily tip and recent activity!")

if __name__ == "__main__":
    main()
