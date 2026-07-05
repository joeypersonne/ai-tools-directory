/* AI Radar — client-side search, filtering, and tabs.
   All data is embedded at build time (window.__TOOLS__). */

(function () {
  "use strict";

  const TOOLS = window.__TOOLS__ || [];
  const CATEGORIES = window.__CATEGORIES__ || [];
  const PAGE_SIZE = 48;
  const NEW_WINDOW_DAYS = 21; // tools added within this window count as "new"

  const state = { tab: "all", query: "", category: "all", pricing: "all", limit: PAGE_SIZE };

  const grid = document.getElementById("grid");
  const resultCount = document.getElementById("result-count");
  const loadMoreBtn = document.getElementById("load-more");

  const daysSince = (iso) => (Date.now() - new Date(iso + "T00:00:00Z").getTime()) / 86400000;
  const isNew = (t) => daysSince(t.dateAdded) <= NEW_WINDOW_DAYS;
  const domainOf = (url) => { try { return new URL(url).hostname; } catch { return ""; } };

  /* ---------- category chips ---------- */
  const catRow = document.getElementById("category-filters");
  const catChips = ['<button class="chip active" data-category="all">All categories</button>']
    .concat(CATEGORIES.map((c) => `<button class="chip" data-category="${c}">${c}</button>`));
  catRow.innerHTML = catChips.join("");

  /* ---------- filtering & sorting ---------- */
  function visibleTools() {
    let list = TOOLS.slice();

    if (state.tab === "all") {
      // featured (paid) placements pin to the top, always labeled
      list.sort((a, b) => (b.featured === true) - (a.featured === true) || b.popularity - a.popularity || a.name.localeCompare(b.name));
    } else if (state.tab === "new") {
      list = list.filter(isNew);
      list.sort((a, b) => b.dateAdded.localeCompare(a.dateAdded) || b.popularity - a.popularity);
    } else if (state.tab === "trending") {
      list = list.filter((t) => t.trendingScore > 0 || t.popularity >= 75);
      list.sort((a, b) => (b.trendingScore - a.trendingScore) || (b.popularity - a.popularity));
    } else if (state.tab === "popular") {
      list.sort((a, b) => b.popularity - a.popularity);
    }

    if (state.category !== "all") list = list.filter((t) => t.category === state.category);
    if (state.pricing !== "all") list = list.filter((t) => t.pricing === state.pricing);

    if (state.query) {
      const q = state.query.toLowerCase();
      const terms = q.split(/\s+/).filter(Boolean);
      list = list.filter((t) => {
        const hay = `${t.name} ${t.description} ${t.category} ${(t.tags || []).join(" ")} ${t.pricing}`.toLowerCase();
        return terms.every((term) => hay.includes(term));
      });
    }
    return list;
  }

  /* ---------- rendering ---------- */
  const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

  function cardHTML(t) {
    const domain = domainOf(t.url);
    const initial = esc(t.name.charAt(0).toUpperCase());
    const favicon = domain
      ? `<img class="favicon" loading="lazy" alt="" src="https://www.google.com/s2/favicons?domain=${encodeURIComponent(domain)}&sz=64"
           onerror="this.outerHTML='<div class=\\'favicon-fallback\\'>${initial}</div>'">`
      : `<div class="favicon-fallback">${initial}</div>`;

    const badges = [];
    if (t.featured) badges.push('<span class="badge sponsored-badge">Featured</span>');
    if (isNew(t)) badges.push('<span class="badge new-badge">New</span>');
    if (t.trendingScore >= 40) badges.push('<span class="badge hot-badge">Hot</span>');
    const pricingLabel = t.pricing === "unknown" ? "" : `<span class="badge ${t.pricing}">${t.pricing}</span>`;

    // affiliate link when configured, official site otherwise — always disclosed via rel
    const visitHref = esc(t.affiliateUrl || t.url);
    const visitRel = t.affiliateUrl ? "sponsored noopener" : "noopener nofollow";

    return `<div class="card${t.featured ? " featured-card" : ""}">
      <div class="card-head">
        ${favicon}
        <div class="card-title"><a class="card-main-link" href="tool/${esc(t.id)}/">${esc(t.name)}</a></div>
        <a class="visit-btn" href="${visitHref}" target="_blank" rel="${visitRel}" title="Open the official ${esc(t.name)} website">Visit ↗</a>
      </div>
      <p class="card-desc">${esc(t.description)}</p>
      <div class="card-foot">
        ${pricingLabel}
        ${badges.join("")}
        <span class="cat-tag">${esc(t.category)}</span>
      </div>
    </div>`;
  }

  function render() {
    const list = visibleTools();
    const shown = list.slice(0, state.limit);

    grid.innerHTML = shown.length
      ? shown.map(cardHTML).join("")
      : '<p class="empty">No tools match your filters. Try clearing the search or picking another category.</p>';

    const label = { all: "tools", new: "new tools", trending: "trending tools", popular: "popular tools" }[state.tab];
    resultCount.textContent = list.length === shown.length
      ? `${list.length} ${label}`
      : `Showing ${shown.length} of ${list.length} ${label}`;

    loadMoreBtn.hidden = list.length <= state.limit;
  }

  /* ---------- events ---------- */
  function activate(container, target, attr) {
    container.querySelectorAll(".active").forEach((el) => el.classList.remove("active"));
    target.classList.add("active");
    state.limit = PAGE_SIZE;
    state[attr] = target.dataset[attr];
    render();
  }

  document.getElementById("tabs").addEventListener("click", (e) => {
    const btn = e.target.closest(".tab");
    if (btn) activate(e.currentTarget, btn, "tab");
  });
  document.getElementById("pricing-filters").addEventListener("click", (e) => {
    const btn = e.target.closest(".chip");
    if (btn) activate(e.currentTarget, btn, "pricing");
  });
  catRow.addEventListener("click", (e) => {
    const btn = e.target.closest(".chip");
    if (btn) activate(catRow, btn, "category");
  });

  let debounce;
  document.getElementById("search").addEventListener("input", (e) => {
    clearTimeout(debounce);
    debounce = setTimeout(() => {
      state.query = e.target.value.trim();
      state.limit = PAGE_SIZE;
      render();
    }, 120);
  });

  loadMoreBtn.addEventListener("click", () => {
    state.limit += PAGE_SIZE;
    render();
  });

  render();
})();
