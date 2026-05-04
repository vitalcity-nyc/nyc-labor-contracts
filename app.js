/* NYC municipal labor contracts — frontend.
 * Loads contracts.json + clauses.json, builds a FlexSearch index,
 * and renders five views: results, topic-pivot, compare, contracts, expirations.
 * Permalinks via URL hash so any clause can be cited directly.
 */
(() => {
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));

  const TOPIC_LABELS = {
    "wages": "Wages & rates",
    "longevity": "Longevity",
    "overtime": "Overtime",
    "holidays": "Holidays",
    "vacation": "Vacation",
    "sick-leave": "Sick leave",
    "parental-leave": "Parental leave",
    "other-leave": "Other leave",
    "health-welfare": "Health & welfare",
    "pension": "Pension",
    "grievance": "Grievance & arbitration",
    "discipline": "Discipline & firing",
    "layoff": "Layoffs / RIF",
    "hours": "Hours & schedules",
    "shift-differential": "Shift differential",
    "uniform-allowance": "Uniform allowance",
    "training": "Training",
    "safety": "Safety",
    "no-strike": "No-strike",
    "management-rights": "Management rights",
    "work-rules": "Work rules",
    "agency-shop": "Union security",
    "recognition": "Recognition",
    "promotion": "Promotion",
    "telework": "Telework",
    "diversity": "Anti-discrimination",
    "workforce-comp": "Workforce composition"
  };

  const state = {
    contracts: [],
    contractById: {},
    clauses: [],
    index: null,
    view: "results",
    query: "",
    topic: "",
    contractFilter: "",
    compareSet: new Set(),
  };

  /* ---------- Loading ---------- */
  async function loadJSON(path) {
    const r = await fetch(path);
    if (!r.ok) throw new Error(`Failed to load ${path}: ${r.status}`);
    return r.json();
  }

  async function init() {
    let manifest = {};
    try { manifest = await loadJSON("data/manifest.json"); } catch (_) {}
    if (manifest.generated) $("#data-stamp").textContent = `Corpus generated ${manifest.generated}. ${manifest.contracts || ""} contracts, ${manifest.clauses || ""} clauses, ${manifest.ocr_pages || ""} OCR'd pages.`;

    state.contracts = await loadJSON("data/contracts.json");
    state.contractById = Object.fromEntries(state.contracts.map(c => [c.id, c]));
    state.clauses = await loadJSON("data/clauses.json");

    // Build FlexSearch document index
    state.index = new FlexSearch.Document({
      document: {
        id: "id",
        index: [
          { field: "text", tokenize: "forward" },
          { field: "heading", tokenize: "forward" },
        ],
        store: false
      },
      cache: 100
    });
    state.clauses.forEach(c => state.index.add(c));

    populateFilters();
    bindEvents();
    parseHashAndRender();
  }

  function populateFilters() {
    const tf = $("#topic-filter");
    const used = {};
    state.clauses.forEach(c => (c.topics || []).forEach(t => used[t] = (used[t] || 0) + 1));
    Object.keys(TOPIC_LABELS).filter(t => used[t]).sort().forEach(t => {
      const o = document.createElement("option");
      o.value = t; o.textContent = `${TOPIC_LABELS[t]} (${used[t]})`;
      tf.appendChild(o);
    });
    const cf = $("#contract-filter");
    state.contracts.slice().sort((a,b) => a.label.localeCompare(b.label)).forEach(c => {
      const o = document.createElement("option");
      o.value = c.id; o.textContent = c.label;
      cf.appendChild(o);
    });
  }

  /* ---------- Events ---------- */
  function bindEvents() {
    $("#q").addEventListener("input", debounce(() => {
      state.query = $("#q").value.trim();
      writeHash(); render();
    }, 150));
    $("#topic-filter").addEventListener("change", () => {
      state.topic = $("#topic-filter").value;
      writeHash(); render();
    });
    $("#contract-filter").addEventListener("change", () => {
      state.contractFilter = $("#contract-filter").value;
      writeHash(); render();
    });
    $("#view-mode").addEventListener("change", () => {
      state.view = $("#view-mode").value;
      writeHash(); render();
    });
    $("#random-btn").addEventListener("click", showRandomClause);
    window.addEventListener("hashchange", parseHashAndRender);
  }

  function debounce(fn, ms) {
    let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
  }

  /* ---------- Hash routing ---------- */
  function writeHash() {
    const params = new URLSearchParams();
    if (state.view !== "results") params.set("view", state.view);
    if (state.query) params.set("q", state.query);
    if (state.topic) params.set("topic", state.topic);
    if (state.contractFilter) params.set("contract", state.contractFilter);
    if (state.compareSet.size) params.set("compare", Array.from(state.compareSet).join(","));
    const h = params.toString();
    history.replaceState(null, "", h ? "#" + h : "#");
  }

  function parseHashAndRender() {
    const params = new URLSearchParams(location.hash.replace(/^#/, ""));
    state.view = params.get("view") || "results";
    state.query = params.get("q") || "";
    state.topic = params.get("topic") || "";
    state.contractFilter = params.get("contract") || "";
    const cmp = params.get("compare");
    state.compareSet = new Set(cmp ? cmp.split(",").filter(Boolean) : []);
    $("#q").value = state.query;
    $("#topic-filter").value = state.topic;
    $("#contract-filter").value = state.contractFilter;
    $("#view-mode").value = state.view;

    // Direct clause permalink: #/clause/<id>
    if (location.hash.startsWith("#/clause/")) {
      const id = decodeURIComponent(location.hash.slice("#/clause/".length));
      renderSingleClause(id);
      return;
    }
    if (location.hash.startsWith("#/contract/")) {
      const id = decodeURIComponent(location.hash.slice("#/contract/".length));
      renderContractDetail(id);
      return;
    }
    render();
  }

  /* ---------- Filtering ---------- */
  function applyFilters(clauses) {
    let out = clauses;
    if (state.topic) out = out.filter(c => (c.topics || []).includes(state.topic));
    if (state.contractFilter) out = out.filter(c => c.contract_id === state.contractFilter);
    return out;
  }

  function searchHits() {
    if (!state.query) return null;
    const results = state.index.search(state.query, { limit: 500, suggest: true });
    const ids = new Set();
    results.forEach(r => r.result.forEach(id => ids.add(id)));
    return state.clauses.filter(c => ids.has(c.id));
  }

  /* ---------- Rendering ---------- */
  function render() {
    const root = $("#results");
    root.innerHTML = "";
    switch (state.view) {
      case "topic-pivot": return renderTopicPivot(root);
      case "compare":     return renderCompare(root);
      case "contracts":   return renderContracts(root);
      case "expirations": return renderExpirations(root);
      default:            return renderResults(root);
    }
  }

  function renderResults(root) {
    let clauses = searchHits();
    if (!clauses) clauses = state.clauses.slice();
    clauses = applyFilters(clauses);
    $("#result-count").textContent = state.query
      ? `${clauses.length} clauses matching "${state.query}"`
      : `${clauses.length} clauses (no search)`;
    if (clauses.length === 0) {
      root.innerHTML = `<div class="clause"><p>No clauses match. Try a broader search, or use the topic pivot view to browse all clauses on a single topic across every contract.</p></div>`;
      return;
    }
    clauses.slice(0, 200).forEach(c => root.appendChild(clauseCard(c, state.query)));
    if (clauses.length > 200) {
      const more = document.createElement("div");
      more.className = "clause";
      more.innerHTML = `<p style="color:var(--muted)">Showing first 200 of ${clauses.length}. Narrow your search or filter to see more.</p>`;
      root.appendChild(more);
    }
  }

  function renderTopicPivot(root) {
    const tilesWrap = document.createElement("div");
    if (!state.topic) {
      const header = document.createElement("div");
      header.className = "topic-pivot-header";
      header.innerHTML = `<h2>Topic pivot</h2><p>Pick a topic. You'll see every clause on that topic from every contract in one continuous list — sortable, comparable, citable.</p>`;
      root.appendChild(header);

      const grid = document.createElement("div");
      grid.className = "topic-tile-grid";
      const counts = {};
      state.clauses.forEach(c => (c.topics || []).forEach(t => counts[t] = (counts[t] || 0) + 1));
      Object.keys(TOPIC_LABELS).filter(t => counts[t]).sort((a,b) => counts[b]-counts[a]).forEach(t => {
        const tile = document.createElement("div");
        tile.className = "topic-tile";
        tile.innerHTML = `<div>${TOPIC_LABELS[t]}</div><div class="count">${counts[t]} clauses across ${countContractsWithTopic(t)} contracts</div>`;
        tile.addEventListener("click", () => { state.topic = t; $("#topic-filter").value = t; writeHash(); render(); });
        grid.appendChild(tile);
      });
      root.appendChild(grid);
      return;
    }
    // Topic selected: show all clauses for it
    const clauses = applyFilters(state.clauses.filter(c => (c.topics || []).includes(state.topic)));
    const header = document.createElement("div");
    header.className = "topic-pivot-header";
    header.innerHTML = `<h2>${TOPIC_LABELS[state.topic] || state.topic}</h2><p>${clauses.length} clauses across ${new Set(clauses.map(c=>c.contract_id)).size} contracts. Click any clause heading to copy a permalink.</p>`;
    root.appendChild(header);
    // Group by contract
    const byContract = {};
    clauses.forEach(c => { (byContract[c.contract_id] = byContract[c.contract_id] || []).push(c); });
    Object.entries(byContract).sort((a,b) => {
      const la = state.contractById[a[0]]?.label || a[0];
      const lb = state.contractById[b[0]]?.label || b[0];
      return la.localeCompare(lb);
    }).forEach(([cid, items]) => {
      const wrap = document.createElement("div");
      wrap.className = "clause";
      wrap.innerHTML = `<div class="clause-meta"><span class="contract">${escapeHtml(state.contractById[cid]?.label || cid)}</span><span>${items.length} clause${items.length===1?"":"s"}</span></div>`;
      items.forEach(c => wrap.appendChild(clauseCard(c, "", true)));
      root.appendChild(wrap);
    });
  }

  function countContractsWithTopic(t) {
    const s = new Set();
    state.clauses.forEach(c => { if ((c.topics || []).includes(t)) s.add(c.contract_id); });
    return s.size;
  }

  function renderCompare(root) {
    const header = document.createElement("div");
    header.className = "topic-pivot-header";
    header.innerHTML = `<h2>Compare contracts side-by-side</h2><p>Pick 2-4 contracts and a topic to see their clauses on that topic next to each other.</p>`;
    root.appendChild(header);
    const ctrl = document.createElement("div");
    ctrl.className = "controls";
    ctrl.innerHTML = `
      <p>Selected: <strong id="cmp-list">${Array.from(state.compareSet).map(id => escapeHtml(state.contractById[id]?.label || id)).join(", ") || "(none)"}</strong></p>
      <select id="cmp-add"><option value="">Add a contract…</option></select>
      <button id="cmp-clear" type="button">Clear</button>
    `;
    root.appendChild(ctrl);
    const sel = ctrl.querySelector("#cmp-add");
    state.contracts.slice().sort((a,b)=>a.label.localeCompare(b.label)).forEach(c => {
      if (state.compareSet.has(c.id)) return;
      const o = document.createElement("option"); o.value = c.id; o.textContent = c.label;
      sel.appendChild(o);
    });
    sel.addEventListener("change", () => {
      if (sel.value && state.compareSet.size < 4) state.compareSet.add(sel.value);
      writeHash(); render();
    });
    ctrl.querySelector("#cmp-clear").addEventListener("click", () => { state.compareSet.clear(); writeHash(); render(); });

    if (state.compareSet.size < 1) return;
    const grid = document.createElement("div");
    grid.className = `compare-grid cols-${Math.max(2, state.compareSet.size)}`;
    Array.from(state.compareSet).forEach(cid => {
      const col = document.createElement("div");
      col.className = "compare-col";
      const c = state.contractById[cid];
      col.innerHTML = `<h3>${escapeHtml(c?.label || cid)}</h3>`;
      const matches = state.clauses.filter(cl => cl.contract_id === cid && (state.topic ? (cl.topics||[]).includes(state.topic) : true));
      matches.slice(0, 6).forEach(cl => col.appendChild(clauseCard(cl, "", true)));
      if (matches.length === 0) col.innerHTML += `<p style="color:var(--muted)">No clauses tagged ${state.topic || "any"}.</p>`;
      grid.appendChild(col);
    });
    root.appendChild(grid);
  }

  function renderContracts(root) {
    const list = state.contracts.slice().sort((a,b)=>a.label.localeCompare(b.label));
    $("#result-count").textContent = `${list.length} contracts`;
    list.forEach(c => {
      const card = document.createElement("div");
      card.className = "contract-card";
      const clauseCount = state.clauses.filter(cl => cl.contract_id === c.id).length;
      const term = (c.term_start && c.term_end) ? `${c.term_start}–${c.term_end}` : "term n/a";
      card.innerHTML = `
        <div>
          <h3><a href="#/contract/${encodeURIComponent(c.id)}">${escapeHtml(c.label)}</a></h3>
          <div class="term">${term} · <a href="${escapeHtml(c.url)}" target="_blank" rel="noopener">source PDF</a></div>
        </div>
        <div class="stats">${clauseCount} clauses</div>
      `;
      root.appendChild(card);
    });
  }

  function renderExpirations(root) {
    const cur = new Date().getFullYear();
    const list = state.contracts.slice().filter(c => c.term_end).sort((a,b) => a.term_end - b.term_end);
    const expired = list.filter(c => c.term_end < cur);
    const expiring = list.filter(c => c.term_end === cur);
    const current = list.filter(c => c.term_end > cur);
    const wrap = document.createElement("div");
    wrap.className = "expirations";
    wrap.innerHTML = `
      <h3>Contract expirations</h3>
      <p>Under New York's Triborough Amendment, expired contracts remain in force until a successor is signed. Listing reflects stated term end dates.</p>
      <ul>
        <li><strong>${current.length}</strong> with stated term not yet expired</li>
        <li><strong>${expiring.length}</strong> expiring this year (${cur})</li>
        <li><strong>${expired.length}</strong> with stated term already expired (Triborough hold-over)</li>
      </ul>
    `;
    root.appendChild(wrap);
    [["Expired (Triborough hold-over)", expired], ["Expiring this year", expiring], ["Currently in stated term", current]].forEach(([title, items]) => {
      const sec = document.createElement("div");
      sec.className = "expirations";
      sec.innerHTML = `<h3>${title} — ${items.length}</h3>`;
      items.forEach(c => {
        const row = document.createElement("div");
        row.style.padding = "4px 0";
        row.innerHTML = `<a href="#/contract/${encodeURIComponent(c.id)}">${escapeHtml(c.label)}</a> <span style="color:var(--muted)">${c.term_start||"?"}–${c.term_end||"?"}</span>`;
        sec.appendChild(row);
      });
      root.appendChild(sec);
    });
  }

  function renderContractDetail(cid) {
    const c = state.contractById[cid];
    const root = $("#results");
    root.innerHTML = "";
    if (!c) { root.innerHTML = `<p>Contract not found.</p>`; return; }
    const head = document.createElement("div");
    head.className = "topic-pivot-header";
    const term = (c.term_start && c.term_end) ? `${c.term_start}–${c.term_end}` : "term n/a";
    head.innerHTML = `
      <h2>${escapeHtml(c.label)}</h2>
      <p>${term} · <a href="${escapeHtml(c.url)}" target="_blank" rel="noopener">View source PDF</a> · <a href="#">← back to all clauses</a></p>
      ${c.summary ? `<p><strong>Workforce:</strong> ${escapeHtml(c.summary)}</p>` : ""}
    `;
    root.appendChild(head);
    const items = state.clauses.filter(cl => cl.contract_id === cid);
    items.forEach(cl => root.appendChild(clauseCard(cl, "")));
  }

  function renderSingleClause(id) {
    const c = state.clauses.find(c => c.id === id);
    const root = $("#results");
    root.innerHTML = "";
    if (!c) { root.innerHTML = `<p>Clause not found.</p>`; return; }
    root.appendChild(clauseCard(c, "", false, true));
  }

  /* ---------- Random clause ---------- */
  function showRandomClause() {
    const pool = applyFilters(state.clauses);
    if (pool.length === 0) { alert("No clauses match the current filters."); return; }
    const c = pool[Math.floor(Math.random() * pool.length)];
    location.hash = "#/clause/" + encodeURIComponent(c.id);
  }

  /* ---------- Card ---------- */
  function clauseCard(c, query = "", compact = false, expanded = false) {
    const wrap = document.createElement("div");
    wrap.className = "clause";
    const contract = state.contractById[c.contract_id];
    const pdfUrl = contract ? `${contract.url}#page=${c.page}` : "#";
    const heading = c.heading || `${contract?.label || c.contract_id}`;
    const tags = (c.topics || []).map(t =>
      `<span class="tag" data-topic="${t}">${TOPIC_LABELS[t] || t}</span>`).join("");
    wrap.innerHTML = `
      <div class="clause-meta">
        ${compact ? "" : `<span class="contract">${escapeHtml(contract?.label || c.contract_id)}</span>`}
        <span>p. ${c.page}</span>
        ${c.ocr ? `<span class="ocr-flag" title="This page was reconstructed via optical character recognition; spelling may have minor errors">OCR</span>` : ""}
        <a class="pdf-link" href="${escapeHtml(pdfUrl)}" target="_blank" rel="noopener">View in source PDF →</a>
      </div>
      <h3 class="clause-heading"><a href="#/clause/${encodeURIComponent(c.id)}">${escapeHtml(heading)}</a></h3>
      <div class="tags">${tags}</div>
      <div class="clause-body${expanded ? " expanded":""}">${highlight(c.text, query)}</div>
      <div class="clause-actions">
        <button class="expand-btn">${expanded ? "Show less" : "Show full clause"}</button>
        <button class="copy-link">Copy permalink</button>
      </div>
    `;
    wrap.querySelector(".expand-btn").addEventListener("click", () => {
      const body = wrap.querySelector(".clause-body");
      body.classList.toggle("expanded");
      wrap.querySelector(".expand-btn").textContent = body.classList.contains("expanded") ? "Show less" : "Show full clause";
    });
    wrap.querySelector(".copy-link").addEventListener("click", () => {
      const url = `${location.origin}${location.pathname}#/clause/${encodeURIComponent(c.id)}`;
      navigator.clipboard.writeText(url).then(() => {
        wrap.querySelector(".copy-link").textContent = "Copied!";
        setTimeout(() => wrap.querySelector(".copy-link").textContent = "Copy permalink", 1500);
      });
    });
    wrap.querySelectorAll(".tag").forEach(el => el.addEventListener("click", (ev) => {
      ev.stopPropagation();
      state.topic = el.dataset.topic;
      $("#topic-filter").value = state.topic;
      state.view = "topic-pivot";
      $("#view-mode").value = "topic-pivot";
      writeHash(); render();
    }));
    return wrap;
  }

  /* ---------- Helpers ---------- */
  function escapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;" })[ch]);
  }
  function highlight(text, q) {
    const safe = escapeHtml(text || "");
    if (!q) return safe;
    const terms = q.split(/\s+/).filter(t => t.length >= 2).map(t => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
    if (!terms.length) return safe;
    return safe.replace(new RegExp(`(${terms.join("|")})`, "ig"), '<mark>$1</mark>');
  }

  init().catch(err => { console.error(err); $("#results").innerHTML = `<div class="clause"><p>Failed to load corpus: ${escapeHtml(err.message)}. The data files may not be built yet.</p></div>`; });
})();
