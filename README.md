# 🛰️ AI Radar — Self-Updating AI Tools Directory

A directory website of AI tools (like [aixploria.com](https://www.aixploria.com/en/)) that **updates itself every day**. It lists new, trending, popular, free and paid AI tools with direct links to each tool's official website.

No frameworks, no npm, no database — just Python (standard library only), a JSON data file, and free GitHub hosting.

## How it works

```
data/tools.json      ← the database (one entry per tool)
scripts/update.py    ← discovers new tools daily from public APIs
scripts/build.py     ← generates the website into dist/
src/                 ← page template, styles, and front-end logic
.github/workflows/   ← the daily automation (GitHub Actions)
```

Every day at 6:00 UTC, GitHub Actions:
1. Runs `update.py` — pulls candidates from **Hacker News** (Show HN launches), **GitHub** (fast-growing new AI repos), and **Hugging Face** (trending Spaces). It filters junk, de-duplicates against existing tools, decays old trending scores, and adds up to 20 new tools.
2. Runs `build.py` — regenerates the site.
3. Commits the updated `tools.json` and deploys to GitHub Pages.

## Run locally

```powershell
python scripts/update.py    # fetch today's new/trending tools
python scripts/build.py     # generate the site into dist/
python -m http.server 4321 --directory dist   # open http://localhost:4321
```

## Publish (free hosting on GitHub Pages)

```powershell
git add -A
git commit -m "Initial commit"
gh repo create ai-tools-directory --public --source . --push
# or create a repo on github.com and: git remote add origin <url>; git push -u origin main
```

Then on GitHub: **Settings → Pages → Source: "GitHub Actions"**. That's it — the site goes live at `https://<your-username>.github.io/ai-tools-directory/` and refreshes itself daily. You can trigger an update anytime from the **Actions** tab → "Daily update & deploy" → **Run workflow**.

## SEO pages

`build.py` generates a full static page structure, not just the homepage: one page per tool (`/tool/<id>/`), per category (`/category/<slug>/`), and per pricing tier (`/free/`, `/freemium/`, `/paid/`), plus `sitemap.xml`, `robots.txt`, an RSS feed (`feed.xml`), JSON-LD schema, and an `/advertise/` page. When you buy a custom domain, change `BASE_URL` at the top of `scripts/build.py` (one line) so canonicals and the sitemap point to it.

## Monetization fields

Two optional per-tool fields in `data/tools.json`:

- `"featured": true` — pins the tool to the top of the homepage with a labeled **Featured** badge and highlighted card (sell this as a monthly placement).
- `"affiliateUrl": "https://..."` — when set, all **Visit** buttons for that tool use this link (marked `rel="sponsored"`; a disclosure line is in the footer). The internal tool page and data keep the official URL.

## Customize

- **Add/edit a tool by hand**: edit `data/tools.json` (fields: `name`, `url`, `description`, `category`, `pricing` = `free` | `freemium` | `paid`, `popularity` 0–100).
- **Change the schedule**: edit the `cron` line in `.github/workflows/daily-update.yml` ([crontab syntax](https://crontab.guru)).
- **Tune discovery**: in `scripts/update.py`, adjust `MIN_HN_POINTS`, `MIN_GITHUB_STARS`, `MAX_NEW_PER_RUN`, or the `CATEGORY_RULES` keyword map.
- **Rename the site**: search for "AI Radar" in `src/template.html`.

## Update locally instead of GitHub (optional)

If you'd rather run the daily update on this PC, create a Windows scheduled task:

```powershell
schtasks /create /tn "AI Radar Update" /sc daily /st 08:00 `
  /tr "python C:\Users\joeyp\ai-tools-directory\scripts\update.py"
```

(You'd still need to build and re-upload the site afterwards — the GitHub Actions route does all of this for you, even while your PC is off.)
