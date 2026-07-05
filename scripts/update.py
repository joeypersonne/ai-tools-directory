#!/usr/bin/env python3
"""Daily updater for the AI tools directory.

Fetches newly launched / trending AI tools from free public APIs
(no API keys required), merges them into data/tools.json, refreshes
trending scores, and stamps the update time.

Sources:
  - Hacker News (Algolia API): "Show HN" launches mentioning AI
  - GitHub Search API: new repositories tagged with AI topics
  - Hugging Face API: trending Spaces (live AI demos)

Run:  python scripts/update.py
"""

import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "tools.json"

USER_AGENT = "ai-tools-directory-bot/1.0 (personal project)"
MAX_NEW_PER_RUN = 15          # cap additions per run so the directory grows sanely
MAX_PER_SOURCE = 6            # no single source may flood the directory
TRENDING_DECAY = 0.85         # older buzz fades a little every day
MIN_HN_POINTS = 25
MIN_GITHUB_STARS = 150
MIN_HF_LIKES = 30

# Names that are demos/artifacts rather than real products (mostly HF spaces)
JUNK_NAME = re.compile(
    r"leaderboard|benchmark|arena|\bdemo\b|\btest\b|\bpreview\b|fp8|int4|gguf|"
    r"aoti|webgpu|kernel|\bv?\d+\.\d+|comparison|playground\b|\btemplate\b",
    re.IGNORECASE,
)

# Skip low-quality / off-topic / NSFW entries
BLOCKLIST = re.compile(
    r"nsfw|uncensored|nude|undress|deepfake|jailbreak|crack|hack.?tool|betting|casino",
    re.IGNORECASE,
)

AI_HINT = re.compile(
    r"\bAI\b|\bA\.I\.\b|GPT|LLM|artificial intelligence|machine learning|neural|"
    r"diffusion|transformer|copilot|chatbot|agent|text.to.|image.gen|voice.clone",
    re.IGNORECASE,
)

# Keyword → category mapping used to classify auto-discovered tools
CATEGORY_RULES = [
    ("Image Generation", r"image|photo|picture|diffusion|art gen|illustration|wallpaper|avatar gen"),
    ("Video", r"video|film|clip|animation|lip.?sync|subtitle"),
    ("Audio & Music", r"music|audio|voice|speech|song|podcast|tts|text.to.speech|sound"),
    ("Coding & Development", r"code|coding|developer|programming|ide|sdk|api|framework|debug|sql|terminal|cli\b"),
    ("Agents & Automation", r"agent|automat|workflow|autonomous|browser.?use|rpa\b"),
    ("Writing & Content", r"writ|copy|blog|article|content|grammar|translat|summar"),
    ("Search & Research", r"search|research|paper|question|answer engine|knowledge"),
    ("Design", r"design|logo|ui\b|ux\b|mockup|figma|font|brand"),
    ("Data & Analytics", r"data|analytic|chart|dashboard|spreadsheet|excel|csv"),
    ("Productivity", r"meeting|note|email|calendar|slide|presentation|productiv|schedul"),
    ("Marketing & Sales", r"marketing|seo\b|sales|lead|ad copy|social media|outreach"),
    ("Education", r"learn|tutor|student|course|study|flashcard|homework"),
    ("3D & Avatars", r"\b3d\b|mesh|texture|avatar|blender|game asset"),
]

DEFAULT_CATEGORY = "Chatbots & Assistants"


def log(msg):
    print(f"[update] {msg}")


def get_json(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def normalize_url(url):
    """Canonical form used for de-duplication."""
    if not url:
        return ""
    url = url.strip().lower().rstrip("/")
    url = re.sub(r"^https?://", "", url)
    url = re.sub(r"^www\.", "", url)
    url = url.split("?")[0].split("#")[0]
    return url


def slugify(name):
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:60] or "tool"


def classify(text):
    for category, pattern in CATEGORY_RULES:
        if re.search(pattern, text, re.IGNORECASE):
            return category
    return DEFAULT_CATEGORY


def clean_title(title):
    """'Show HN: Foo – an AI thing' -> ('Foo', 'an AI thing')"""
    title = re.sub(r"^show\s*hn\s*:?\s*", "", title, flags=re.IGNORECASE).strip()
    parts = re.split(r"\s+[–—-]\s+|:\s+", title, maxsplit=1)
    name = parts[0].strip()
    desc = parts[1].strip() if len(parts) > 1 else ""
    if desc:
        desc = desc[0].upper() + desc[1:]
        if not desc.endswith("."):
            desc += "."
    return name[:60], desc[:180]


def fetch_hackernews():
    """Show HN launches from the last 7 days that look like AI tools."""
    since = int((datetime.now(timezone.utc) - timedelta(days=7)).timestamp())
    url = (
        "https://hn.algolia.com/api/v1/search_by_date?"
        + urllib.parse.urlencode({
            "tags": "show_hn",
            "numericFilters": f"created_at_i>{since},points>{MIN_HN_POINTS}",
            "hitsPerPage": "100",
        })
    )
    found = []
    for hit in get_json(url).get("hits", []):
        title = hit.get("title") or ""
        link = hit.get("url") or ""
        if not link or not AI_HINT.search(title) or BLOCKLIST.search(title):
            continue
        name, desc = clean_title(title)
        found.append({
            "name": name,
            "url": link,
            "description": desc or "New AI tool launched on Hacker News.",
            "pricing": "unknown",
            "source": "hackernews",
            "signal": min(100, int(hit.get("points", 0))),
        })
    return found[:MAX_PER_SOURCE * 2]


def fetch_github():
    """New AI repositories (last 30 days) gaining stars fast."""
    since = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
    url = (
        "https://api.github.com/search/repositories?"
        + urllib.parse.urlencode({
            "q": f"topic:ai created:>{since} stars:>{MIN_GITHUB_STARS}",
            "sort": "stars",
            "order": "desc",
            "per_page": "30",
        })
    )
    found = []
    for repo in get_json(url).get("items", []):
        desc = repo.get("description") or ""
        name = repo.get("name", "")
        if BLOCKLIST.search(f"{name} {desc}") or JUNK_NAME.search(name):
            continue
        link = repo.get("homepage") or repo.get("html_url")
        found.append({
            "name": name[:60],
            "url": link,
            "description": (desc[:180] or "Fast-growing open-source AI project."),
            "pricing": "free",  # open-source
            "source": "github",
            "signal": min(95, int(repo.get("stargazers_count", 0) / 25)),
        })
    return found


def fetch_huggingface():
    """Trending Hugging Face Spaces (live AI demos)."""
    for sort_key in ("trendingScore", "likes"):
        try:
            url = f"https://huggingface.co/api/spaces?sort={sort_key}&direction=-1&limit=30"
            spaces = get_json(url)
            break
        except Exception:
            spaces = []
    found = []
    for space in spaces:
        space_id = space.get("id") or ""
        short = space_id.split("/")[-1]
        likes = int(space.get("likes", 0))
        if (not space_id or likes < MIN_HF_LIKES or len(short) < 4
                or BLOCKLIST.search(space_id) or JUNK_NAME.search(short)):
            continue
        pretty = short.replace("-", " ").replace("_", " ").title()
        found.append({
            "name": pretty[:60],
            "url": f"https://huggingface.co/spaces/{space_id}",
            "description": f"Trending Hugging Face Space by {space_id.split('/')[0]} — try it live in the browser.",
            "pricing": "free",
            "source": "huggingface",
            "signal": min(70, likes // 3),  # keep demos below real product launches
        })
    return found


def main():
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    tools = data["tools"]
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    by_url = {normalize_url(t["url"]): t for t in tools}
    by_name = {t["name"].lower(): t for t in tools}
    existing_ids = {t["id"] for t in tools}

    # 1. Decay yesterday's trending scores so the Trending tab stays fresh
    for t in tools:
        t["trendingScore"] = int(t.get("trendingScore", 0) * TRENDING_DECAY)

    # 2. Pull candidates from every source (one failing source never kills the run)
    candidates = []
    for fetch in (fetch_hackernews, fetch_github, fetch_huggingface):
        try:
            batch = fetch()
            log(f"{fetch.__name__}: {len(batch)} candidates")
            candidates.extend(batch)
        except Exception as exc:
            log(f"WARNING {fetch.__name__} failed: {exc}")

    # 3. Merge: bump trending for known tools, queue genuinely new ones
    fresh = []
    for c in candidates:
        key = normalize_url(c.get("url"))
        if not key or len(c["name"]) < 2:
            continue
        known = by_url.get(key) or by_name.get(c["name"].lower())
        if known:
            known["trendingScore"] = min(100, max(known["trendingScore"], c["signal"]) + 5)
        else:
            fresh.append(c)
            by_url[key] = c  # avoid dupes within the same run

    # 4. Add the strongest new discoveries (capped overall and per source)
    fresh.sort(key=lambda c: c["signal"], reverse=True)
    added = 0
    per_source = {}
    for c in fresh:
        if added >= MAX_NEW_PER_RUN:
            break
        if per_source.get(c["source"], 0) >= MAX_PER_SOURCE:
            continue
        per_source[c["source"]] = per_source.get(c["source"], 0) + 1
        tool_id = slugify(c["name"])
        while tool_id in existing_ids:
            tool_id += "-2"
        existing_ids.add(tool_id)
        tools.append({
            "id": tool_id,
            "name": c["name"],
            "url": c["url"],
            "description": c["description"],
            "category": classify(f"{c['name']} {c['description']}"),
            "tags": [c["source"]],
            "pricing": c["pricing"],
            "dateAdded": today,
            "popularity": min(50, 20 + c["signal"] // 4),
            "trendingScore": c["signal"],
            "source": c["source"],
        })
        added += 1
        log(f"+ added: {c['name']}  ({c['source']}, signal {c['signal']})")

    data["meta"]["lastUpdated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    DATA_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    log(f"done — {added} new tools, {len(tools)} total")


if __name__ == "__main__":
    sys.exit(main())
