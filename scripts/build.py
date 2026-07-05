#!/usr/bin/env python3
"""Build the static site into dist/ from data/tools.json and src/ assets.

Run:  python scripts/build.py
"""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "tools.json"
SRC = ROOT / "src"
DIST = ROOT / "dist"


def main():
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    tools = data["tools"]
    categories = sorted({t["category"] for t in tools})

    last_updated = data["meta"].get("lastUpdated", "")
    try:
        nice_date = datetime.fromisoformat(last_updated.replace("Z", "+00:00")).strftime("%B %d, %Y")
    except ValueError:
        nice_date = datetime.now(timezone.utc).strftime("%B %d, %Y")

    html = (SRC / "template.html").read_text(encoding="utf-8")
    html = html.replace("__TOOLS_JSON__", json.dumps(tools, ensure_ascii=False))
    html = html.replace("__CATEGORIES_JSON__", json.dumps(categories, ensure_ascii=False))
    html = html.replace("__TOOL_COUNT__", str(len(tools)))
    html = html.replace("__CATEGORY_COUNT__", str(len(categories)))
    html = html.replace("__LAST_UPDATED__", nice_date)

    DIST.mkdir(exist_ok=True)
    (DIST / "index.html").write_text(html, encoding="utf-8")
    shutil.copy(SRC / "styles.css", DIST / "styles.css")
    shutil.copy(SRC / "app.js", DIST / "app.js")
    (DIST / ".nojekyll").write_text("", encoding="utf-8")  # required for GitHub Pages

    print(f"[build] dist/index.html written — {len(tools)} tools, {len(categories)} categories")


if __name__ == "__main__":
    main()
