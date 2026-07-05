#!/usr/bin/env python3
"""Build the static site into dist/ from data/tools.json and src/ assets.

Generates:
  dist/index.html                    interactive homepage
  dist/tool/<id>/index.html          one SEO page per tool
  dist/category/<slug>/index.html    one page per category
  dist/free|freemium|paid/index.html pricing pages
  dist/advertise/index.html          "feature your tool" page
  dist/sitemap.xml, robots.txt, feed.xml

Run:  python scripts/build.py
"""

import hashlib
import html
import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "tools.json"
SRC = ROOT / "src"
DIST = ROOT / "dist"

SITE_NAME = "AI Radar"
CONTACT_EMAIL = "joeypersonne@gmail.com"
# Change this once when you buy a custom domain (or set the BASE_URL env var)
BASE_URL = os.environ.get("BASE_URL", "https://joeypersonne.github.io/ai-tools-directory").rstrip("/")

# Cache-buster appended to asset URLs; set from file contents in main().
# GitHub Pages caches for 10 minutes, so without this a fresh deploy can pair
# new HTML with a stale cached stylesheet.
ASSET_V = "dev"

PRICING_PAGES = {
    "free": ("Free AI Tools", "Completely free AI tools — no credit card, no trial limits."),
    "freemium": ("Freemium AI Tools", "AI tools with a solid free tier, upgradeable when you need more."),
    "paid": ("Paid AI Tools", "Premium AI tools that are worth paying for."),
}


def esc(s):
    return html.escape(str(s), quote=True)


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def domain_of(url):
    m = re.match(r"https?://([^/]+)", url or "")
    return m.group(1) if m else ""


def visit_url(tool):
    """Affiliate link if one is set, otherwise the official site."""
    return tool.get("affiliateUrl") or tool["url"]


def visit_rel(tool):
    return "sponsored noopener" if tool.get("affiliateUrl") else "noopener nofollow"


def favicon_img(tool, size=64):
    dom = domain_of(tool["url"])
    if dom:
        return (f'<img class="favicon" loading="lazy" alt="" '
                f'src="https://www.google.com/s2/favicons?domain={esc(dom)}&sz={size}">')
    return f'<div class="favicon-fallback">{esc(tool["name"][:1].upper())}</div>'


def badges_html(tool):
    out = []
    if tool.get("featured"):
        out.append('<span class="badge sponsored-badge">Featured</span>')
    if tool.get("pricing") in ("free", "freemium", "paid"):
        out.append(f'<span class="badge {tool["pricing"]}">{tool["pricing"]}</span>')
    if tool.get("trendingScore", 0) >= 40:
        out.append('<span class="badge hot-badge">Hot</span>')
    return "".join(out)


def card_html(tool, rel_prefix):
    """Static tool card matching the JS-rendered ones on the homepage."""
    return f'''<div class="card{' featured-card' if tool.get('featured') else ''}">
      <div class="card-head">
        {favicon_img(tool)}
        <div class="card-title"><a class="card-main-link" href="{rel_prefix}tool/{esc(tool["id"])}/">{esc(tool["name"])}</a></div>
        <a class="visit-btn" href="{esc(visit_url(tool))}" target="_blank" rel="{visit_rel(tool)}">Visit ↗</a>
      </div>
      <p class="card-desc">{esc(tool["description"])}</p>
      <div class="card-foot">
        {badges_html(tool)}
        <span class="cat-tag">{esc(tool["category"])}</span>
      </div>
    </div>'''


def shell(title, description, canonical_path, body, rel_prefix, extra_head=""):
    """Shared page chrome for all generated (non-homepage) pages."""
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(description)}">
  <link rel="canonical" href="{BASE_URL}{canonical_path}">
  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(description)}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{BASE_URL}{canonical_path}">
  <link rel="stylesheet" href="{rel_prefix}styles.css?v={ASSET_V}">
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🛰️</text></svg>">
  {extra_head}
</head>
<body>
  <header class="topbar">
    <div class="container topbar-inner">
      <a class="brand" href="{rel_prefix}"><span class="brand-mark">🛰️</span><span class="brand-name">AI&nbsp;Radar</span></a>
      <a class="advertise-link" href="{rel_prefix}advertise/">📣 Feature your tool</a>
    </div>
  </header>
  <main class="container page-main">
  {body}
  </main>
  {footer_html(rel_prefix)}
</body>
</html>'''


def footer_html(rel_prefix, categories=None):
    cats = categories or footer_html.categories
    cat_links = "".join(
        f'<a href="{rel_prefix}category/{slugify(c)}/">{esc(c)}</a>' for c in cats
    )
    return f'''<footer class="footer">
    <div class="container">
      <nav class="footer-nav">
        <div class="footer-col"><h4>Browse</h4>
          <a href="{rel_prefix}">All tools</a>
          <a href="{rel_prefix}free/">Free AI tools</a>
          <a href="{rel_prefix}freemium/">Freemium AI tools</a>
          <a href="{rel_prefix}paid/">Paid AI tools</a>
          <a href="{rel_prefix}feed.xml">RSS feed</a>
        </div>
        <div class="footer-col wide"><h4>Categories</h4><div class="footer-cats">{cat_links}</div></div>
        <div class="footer-col"><h4>About</h4>
          <a href="{rel_prefix}advertise/">Feature your tool</a>
          <a href="https://github.com/joeypersonne/ai-tools-directory" rel="noopener">Open source</a>
        </div>
      </nav>
      <p class="fineprint">{SITE_NAME} — a self-updating directory of AI tools. New tools are discovered automatically every day.
      Some outbound links may be affiliate links that support the site at no cost to you.</p>
    </div>
  </footer>'''


footer_html.categories = []


def tool_page(tool, tools_by_category):
    t = tool
    related = [r for r in tools_by_category.get(t["category"], []) if r["id"] != t["id"]][:6]
    related_html = "".join(card_html(r, "../../") for r in related)
    pricing_word = {"free": "Free", "freemium": "Freemium (free tier available)",
                    "paid": "Paid"}.get(t["pricing"], "See website")
    schema = {
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        "name": t["name"],
        "url": t["url"],
        "description": t["description"],
        "applicationCategory": t["category"],
        "offers": {"@type": "Offer", "price": "0" if t["pricing"] == "free" else "", "priceCurrency": "USD"},
    }
    body = f'''
    <nav class="breadcrumb"><a href="../../">Home</a> › <a href="../../category/{slugify(t["category"])}/">{esc(t["category"])}</a> › {esc(t["name"])}</nav>
    <article class="tool-hero">
      <div class="tool-hero-head">
        {favicon_img(t, 128)}
        <div>
          <h1>{esc(t["name"])}</h1>
          <div class="card-foot">{badges_html(t)}<span class="cat-tag">{esc(t["category"])}</span></div>
        </div>
      </div>
      <p class="tool-desc">{esc(t["description"])}</p>
      <a class="cta-btn" href="{esc(visit_url(t))}" target="_blank" rel="{visit_rel(t)}">Visit {esc(t["name"])} ↗</a>
      <dl class="tool-facts">
        <div><dt>Pricing</dt><dd>{pricing_word}</dd></div>
        <div><dt>Category</dt><dd>{esc(t["category"])}</dd></div>
        <div><dt>Listed since</dt><dd>{esc(t["dateAdded"])}</dd></div>
        <div><dt>Website</dt><dd>{esc(domain_of(t["url"]))}</dd></div>
      </dl>
    </article>
    <section>
      <h2 class="section-title">Alternatives to {esc(t["name"])}</h2>
      <div class="grid">{related_html}</div>
    </section>'''
    title = f'{t["name"]} — {pricing_word} {t["category"]} AI Tool | {SITE_NAME}'
    desc = f'{t["name"]}: {t["description"]} Pricing: {pricing_word}. Discover alternatives on {SITE_NAME}.'
    extra = f'<script type="application/ld+json">{json.dumps(schema, ensure_ascii=False)}</script>'
    return shell(title, desc[:300], f'/tool/{t["id"]}/', body, "../../", extra)


def listing_page(title, description, canonical_path, tools_subset):
    cards = "".join(card_html(t, "../") for t in tools_subset)
    body = f'''
    <nav class="breadcrumb"><a href="../">Home</a> › {esc(title)}</nav>
    <h1>{esc(title)}</h1>
    <p class="page-sub">{esc(description)} ({len(tools_subset)} tools, updated daily)</p>
    <div class="grid">{cards}</div>'''
    return shell(f"{title} ({len(tools_subset)}) | {SITE_NAME}", description, canonical_path, body, "../")


def advertise_page():
    body = f'''
    <nav class="breadcrumb"><a href="../">Home</a> › Feature your tool</nav>
    <h1>Get your AI tool in front of daily visitors</h1>
    <p class="page-sub">{SITE_NAME} is a self-updating AI tools directory. Listings are free and automatic —
    but you can fast-track and boost your tool.</p>
    <div class="pricing-cards">
      <div class="price-card">
        <h3>Standard listing</h3>
        <p class="price">Free</p>
        <ul><li>Discovered automatically, or submit it yourself</li><li>Permanent listing with a direct link</li><li>Included in category &amp; search results</li></ul>
        <a class="cta-btn secondary" href="https://github.com/joeypersonne/ai-tools-directory/issues/new?title=Tool%20submission:%20&body=Name:%0AWebsite:%0ADescription:%0APricing%20(free/freemium/paid):" rel="noopener">Submit your tool</a>
      </div>
      <div class="price-card highlight">
        <h3>Featured listing</h3>
        <p class="price">$29<span>/month</span></p>
        <ul><li>Pinned to the top of the homepage with a Featured badge</li><li>Highlighted card design</li><li>Listed within 24 hours</li></ul>
        <a class="cta-btn" href="mailto:{CONTACT_EMAIL}?subject=Featured%20listing%20on%20AI%20Radar">Get featured</a>
      </div>
    </div>
    <p class="fineprint">Featured placements are always labeled. Rankings and the daily discovery pipeline are never for sale.</p>'''
    return shell(f"Feature your AI tool | {SITE_NAME}",
                 f"Promote your AI tool on {SITE_NAME} — free standard listings, paid featured placement.",
                 "/advertise/", body, "../")


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main():
    global ASSET_V
    ASSET_V = hashlib.md5(
        (SRC / "styles.css").read_bytes() + (SRC / "app.js").read_bytes()
    ).hexdigest()[:8]

    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    tools = sorted(data["tools"], key=lambda t: -t["popularity"])
    categories = sorted({t["category"] for t in tools})
    footer_html.categories = categories

    last_updated = data["meta"].get("lastUpdated", "")
    try:
        nice_date = datetime.fromisoformat(last_updated.replace("Z", "+00:00")).strftime("%B %d, %Y")
    except ValueError:
        nice_date = datetime.now(timezone.utc).strftime("%B %d, %Y")

    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()

    # ---- homepage (interactive) ----
    page = (SRC / "template.html").read_text(encoding="utf-8")
    page = page.replace("__TOOLS_JSON__", json.dumps(tools, ensure_ascii=False))
    page = page.replace("__CATEGORIES_JSON__", json.dumps(categories, ensure_ascii=False))
    page = page.replace("__TOOL_COUNT__", str(len(tools)))
    page = page.replace("__CATEGORY_COUNT__", str(len(categories)))
    page = page.replace("__LAST_UPDATED__", nice_date)
    page = page.replace("__BASE_URL__", BASE_URL)
    page = page.replace("__FOOTER__", footer_html("", categories))
    page = page.replace("__ASSET_V__", ASSET_V)
    write(DIST / "index.html", page)

    shutil.copy(SRC / "styles.css", DIST / "styles.css")
    shutil.copy(SRC / "app.js", DIST / "app.js")
    (DIST / ".nojekyll").write_text("", encoding="utf-8")

    # ---- tool pages ----
    by_category = {}
    for t in tools:
        by_category.setdefault(t["category"], []).append(t)
    for t in tools:
        write(DIST / "tool" / t["id"] / "index.html", tool_page(t, by_category))

    # ---- category pages ----
    for cat in categories:
        subset = by_category[cat]
        write(DIST / "category" / slugify(cat) / "index.html",
              listing_page(f"{cat} AI Tools",
                           f"The best {cat.lower()} AI tools — free and paid, refreshed every day.",
                           f"/category/{slugify(cat)}/", subset))

    # ---- pricing pages ----
    for key, (title, desc) in PRICING_PAGES.items():
        subset = [t for t in tools if t["pricing"] == key]
        write(DIST / key / "index.html", listing_page(title, desc, f"/{key}/", subset))

    # ---- advertise page ----
    write(DIST / "advertise" / "index.html", advertise_page())

    # ---- robots.txt + sitemap.xml ----
    write(DIST / "robots.txt", f"User-agent: *\nAllow: /\nSitemap: {BASE_URL}/sitemap.xml\n")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    urls = ["/", "/advertise/"] + [f"/{k}/" for k in PRICING_PAGES] \
        + [f"/category/{slugify(c)}/" for c in categories] \
        + [f"/tool/{t['id']}/" for t in tools]
    entries = "\n".join(
        f"  <url><loc>{BASE_URL}{u}</loc><lastmod>{today}</lastmod></url>" for u in urls
    )
    write(DIST / "sitemap.xml",
          f'<?xml version="1.0" encoding="UTF-8"?>\n'
          f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{entries}\n</urlset>\n')

    # ---- RSS feed of newest tools ----
    newest = sorted(tools, key=lambda t: t["dateAdded"], reverse=True)[:30]
    items = "\n".join(
        f"""  <item>
    <title>{esc(t['name'])} — {esc(t['category'])}</title>
    <link>{BASE_URL}/tool/{t['id']}/</link>
    <guid>{BASE_URL}/tool/{t['id']}/</guid>
    <description>{esc(t['description'])}</description>
  </item>""" for t in newest
    )
    write(DIST / "feed.xml",
          f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>{SITE_NAME} — New AI Tools</title>
  <link>{BASE_URL}/</link>
  <description>New AI tools discovered daily by {SITE_NAME}</description>
{items}
</channel></rss>\n''')

    total_pages = 1 + len(tools) + len(categories) + len(PRICING_PAGES) + 1
    print(f"[build] {total_pages} pages written — {len(tools)} tools, {len(categories)} categories")
    print(f"[build] base URL: {BASE_URL}")


if __name__ == "__main__":
    main()
