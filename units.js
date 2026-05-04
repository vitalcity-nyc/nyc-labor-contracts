/* Bargaining units browser — standalone page. */
(() => {
  const $ = (s) => document.querySelector(s);

  const SECTOR_LABELS = {
    "uniformed-police": "Uniformed — Police",
    "uniformed-fire": "Uniformed — Fire",
    "uniformed-sanitation": "Uniformed — Sanitation",
    "uniformed-correction": "Uniformed — Correction",
    "uniformed-pattern": "Uniformed — Coalition / pattern",
    "education": "Education",
    "education-management": "Education — Supervisors",
    "health": "Health (non-physician)",
    "health-professional": "Health — Physicians",
    "clerical-and-professional": "Clerical & professional",
    "clerical-and-special-officer": "Clerical & special officer",
    "supervisory-clerical": "Supervisory clerical",
    "skilled-trades": "Skilled trades",
    "professional": "Professional",
    "other": "Other / specialty",
  };

  const state = { units: [], sector: "", sort: "size", query: "" };

  async function init() {
    const r = await fetch("data/units.json");
    state.units = await r.json();
    populateSectorFilter();
    bind();
    parseQuery();
    render();
  }

  function populateSectorFilter() {
    const counts = {};
    state.units.forEach(u => counts[u.sector] = (counts[u.sector] || 0) + 1);
    const sel = $("#sector-filter");
    Object.keys(counts).sort().forEach(s => {
      const o = document.createElement("option");
      o.value = s; o.textContent = `${SECTOR_LABELS[s] || s} (${counts[s]})`;
      sel.appendChild(o);
    });
  }

  function bind() {
    $("#sector-filter").addEventListener("change", () => { state.sector = $("#sector-filter").value; writeQuery(); render(); });
    $("#sort-mode").addEventListener("change", () => { state.sort = $("#sort-mode").value; render(); });
    $("#q").addEventListener("input", debounce(() => { state.query = $("#q").value.trim().toLowerCase(); render(); }, 120));
  }

  function debounce(fn, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }

  function parseQuery() {
    const p = new URLSearchParams(location.search);
    if (p.get("sector")) { state.sector = p.get("sector"); $("#sector-filter").value = state.sector; }
  }

  function writeQuery() {
    const p = new URLSearchParams();
    if (state.sector) p.set("sector", state.sector);
    history.replaceState(null, "", p.toString() ? `?${p.toString()}` : location.pathname);
  }

  function render() {
    let units = state.units.slice();
    if (state.sector) units = units.filter(u => u.sector === state.sector);
    if (state.query) {
      units = units.filter(u => {
        const blob = [u.contract_label, u.union_full, u.local, u.employer, u.summary, (u.titles || []).join(" ")].join(" ").toLowerCase();
        return blob.includes(state.query);
      });
    }
    if (state.sort === "size") {
      units.sort((a, b) => (b.headcount || 0) - (a.headcount || 0) || a.contract_label.localeCompare(b.contract_label));
    } else if (state.sort === "alpha") {
      units.sort((a, b) => a.contract_label.localeCompare(b.contract_label));
    } else if (state.sort === "term") {
      units.sort((a, b) => (a.term_end || 9999) - (b.term_end || 9999) || a.contract_label.localeCompare(b.contract_label));
    }

    $("#result-count").textContent = `${units.length} bargaining unit${units.length === 1 ? "" : "s"}` +
      (state.sector ? ` in ${SECTOR_LABELS[state.sector] || state.sector}` : "") +
      (state.query ? ` matching "${state.query}"` : "");

    const root = $("#units");
    root.innerHTML = "";
    if (units.length === 0) {
      root.innerHTML = `<div class="unit-card"><div class="unit-body"><p>No units match. Clear filters or try a broader search.</p></div></div>`;
      return;
    }
    units.forEach(u => root.appendChild(card(u)));
  }

  function card(u) {
    const div = document.createElement("div");
    div.className = "unit-card";
    const headcount = u.headcount
      ? `<div class="unit-headcount"><span class="unit-headcount-num">${u.headcount.toLocaleString()}</span><span class="unit-headcount-label">covered employees${u.curated ? "" : " (estimate)"}</span></div>`
      : `<div class="unit-headcount unit-headcount-tbd"><span class="unit-headcount-num">—</span><span class="unit-headcount-label">headcount being sourced</span></div>`;
    const titles = (u.titles && u.titles.length)
      ? `<p class="unit-titles"><strong>Titles:</strong> ${u.titles.map(escapeHtml).join(" · ")}</p>` : "";
    const term = (u.term_start && u.term_end) ? `${u.term_start}–${u.term_end}` : "term n/a";
    const headNote = u.headcount_note
      ? `<p class="unit-headcount-note">${escapeHtml(u.headcount_note)}</p>` : "";
    div.innerHTML = `
      ${headcount}
      <div class="unit-body">
        <p class="unit-sector">${SECTOR_LABELS[u.sector] || u.sector}</p>
        <h3><a href="index.html#/contract/${encodeURIComponent(u.contract_id)}">${escapeHtml(u.contract_label)}</a></h3>
        ${u.union_full ? `<p class="unit-union"><strong>${escapeHtml(u.union_full)}</strong>${u.local && u.local !== u.union_full ? " — " + escapeHtml(u.local) : ""}</p>` : ""}
        ${u.employer ? `<p class="unit-employer"><strong>Employer:</strong> ${escapeHtml(u.employer)}</p>` : ""}
        <p class="unit-summary">${escapeHtml(u.summary)}</p>
        ${titles}
        ${headNote}
        <p class="unit-term">Current agreement: ${term} · <a href="index.html#/contract/${encodeURIComponent(u.contract_id)}">browse clauses →</a></p>
      </div>
    `;
    return div;
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;"})[ch]);
  }

  init().catch(err => { $("#units").innerHTML = `<div class="unit-card"><div class="unit-body"><p>Failed to load: ${escapeHtml(err.message)}</p></div></div>`; });
})();
