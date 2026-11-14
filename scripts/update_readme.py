#!/usr/bin/env python3
"""scripts/update_readme.py
Updates dynamic sections of README.md:
  1. <!-- START_SECTION:daily_tip -->
  2. <!-- START_SECTION:pr_telemetry -->
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

REPO_DESCRIPTIONS = {
    "batrapulkit/squidbrake": "AI agent change control, human-in-the-loop governance & audit trails",
    "vyncint/termlens": "Headless end-to-end testing engine for CLI & TUI apps in Rust",
    "Avenx-JS/avenx-js": "Compiler-driven JavaScript framework with proxy-based reactivity",
    "activist-org/activist": "Community platform connecting grassroots activists & organizations",
    "kestra-io/blueprints": "Official declarative workflow blueprints for Kestra orchestration",
    "supabase/supabase-js": "Official isomorphic JavaScript/TypeScript client for Supabase",
    "pypa/twine": "Standard utility for publishing Python packages to PyPI",
    "arc53/DocsGPT": "Open-source documentation assistant and knowledge-base search engine"
}

def get_daily_tip():
    day_of_year = datetime.datetime.now(datetime.timezone.utc).timetuple().tm_yday
    tip = TIPS[day_of_year % len(TIPS)]
    return f"> **💡 Systems Tip of the Day:** {tip}"

def get_pr_telemetry():
    token = os.environ.get("GITHUB_TOKEN")
    headers = {"User-Agent": f"{USERNAME}-profile-updater"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    def fetch_json(url):
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))

    try:
        total = fetch_json(f"https://api.github.com/search/issues?q=author:{USERNAME}+type:pr")["total_count"]
        merged = fetch_json(f"https://api.github.com/search/issues?q=author:{USERNAME}+type:pr+is:merged")["total_count"]
        open_prs = fetch_json(f"https://api.github.com/search/issues?q=author:{USERNAME}+type:pr+is:open")["total_count"]
        ratio = round((merged / total * 100)) if total > 0 else 0

        merged_data = fetch_json(f"https://api.github.com/search/issues?q=author:{USERNAME}+type:pr+is:merged&sort=updated&order=desc&per_page=100")
        items = merged_data.get("items", [])

        repo_counts = {}
        for it in items:
            repo = "/".join(it["repository_url"].split("/")[-2:])
            repo_counts[repo] = repo_counts.get(repo, 0) + 1

        top_3 = sorted(repo_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        repo_info = []
        medals = ["🥇", "🥈", "🥉"]

        for idx, (repo, count) in enumerate(top_3):
            desc = REPO_DESCRIPTIONS.get(repo)
            if not desc:
                try:
                    d = fetch_json(f"https://api.github.com/repos/{repo}")
                    desc = d.get("description") or "Open-source software repository"
                    if len(desc) > 75:
                        desc = desc[:72] + "..."
                except Exception:
                    desc = "Open-source software repository"
            desc = desc.replace("|", "\\|")
            repo_info.append((medals[idx], repo, count, desc))

        latest_5 = []
        for it in items[:5]:
            repo = "/".join(it["repository_url"].split("/")[-2:])
            title = it["title"]
            title = re.sub(r"\s*\([#\d\s]+\)$", "", title).strip()
            title = title.replace("|", "\\|")
            if len(title) > 85:
                title = title[:82] + "..."
            date_str = it.get("closed_at", "")
            if date_str:
                dt = datetime.datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                formatted_date = dt.strftime("%b %d, %Y")
            else:
                formatted_date = "Recent"
            latest_5.append({
                "number": it["number"],
                "title": title,
                "html_url": it["html_url"],
                "repo": repo,
                "date": formatted_date
            })

        lines = []
        lines.append('<div align="center">\n\n')
        lines.append(f'<a href="https://github.com/search?q=author%3A{USERNAME}+type%3Apr"><img src="https://img.shields.io/badge/PRs_Sent-{total}-0d1117?style=for-the-badge&logo=git&logoColor=38bdf8&labelColor=161b22" alt="PRs Sent" /></a> ')
        lines.append(f'<a href="https://github.com/search?q=author%3A{USERNAME}+type%3Apr+is%3Amerged"><img src="https://img.shields.io/badge/Merged_%26_Shipped-{merged}-8957e5?style=for-the-badge&logo=gitpullrequest&logoColor=white&labelColor=161b22" alt="PRs Merged" /></a> ')
        lines.append(f'<a href="https://github.com/search?q=author%3A{USERNAME}+type%3Apr+is%3Aopen"><img src="https://img.shields.io/badge/In_Flight-{open_prs}-238636?style=for-the-badge&logo=gitpullrequest&logoColor=3fb950&labelColor=161b22" alt="PRs Open" /></a> ')
        lines.append(f'<a href="https://github.com/search?q=author%3A{USERNAME}+type%3Apr"><img src="https://img.shields.io/badge/Merge_Rate-{ratio}%25-38bdf8?style=for-the-badge&logo=github&logoColor=white&labelColor=161b22" alt="Merge Rate" /></a>\n\n')
        lines.append('</div>\n\n')

        lines.append("| Rank | Target Repository | Merged PRs | Focus / Ecosystem |\n")
        lines.append("| :---: | :--- | :---: | :--- |\n")
        for medal, repo, count, desc in repo_info:
            lines.append(f"| {medal} | [**{repo}**](https://github.com/{repo}) | `{count} merged` | {desc} |\n")

        lines.append("\n")
        lines.append("| PR | Target Repository | Merged Contribution | Shipped Date |\n")
        lines.append("| :---: | :--- | :--- | :---: |\n")
        for pr in latest_5:
            lines.append(f"| [**#{pr['number']}**]({pr['html_url']}) | [`{pr['repo']}`](https://github.com/{pr['repo']}) | {pr['title']} | `{pr['date']}` |\n")

        return "".join(lines)
    except Exception as err:
        print(f"Error fetching PR telemetry: {err}")
        return None

def replace_section(content, section_name, new_data):
    pattern = rf"<!-- START_SECTION:{section_name} -->.*?<!-- END_SECTION:{section_name} -->"
    if not re.search(pattern, content, flags=re.DOTALL):
        return content
    replacement = f"<!-- START_SECTION:{section_name} -->\n{new_data}\n<!-- END_SECTION:{section_name} -->"
    return re.sub(pattern, replacement, content, flags=re.DOTALL)

def main():
    if not os.path.exists(README_PATH):
        print(f"File not found: {README_PATH}")
        return

    with open(README_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    tip = get_daily_tip()
    telemetry = get_pr_telemetry()

    content = replace_section(content, "daily_tip", tip)
    if telemetry:
        content = replace_section(content, "pr_telemetry", telemetry)

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    print("Successfully updated README.md with daily tip and live PR telemetry!")

if __name__ == "__main__":
    main()
