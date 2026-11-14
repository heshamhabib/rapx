// Red Alert: Project X site: nations dossier and Arsenal Catalogue, from data/catalogue.js (tools/make_site.py).
(() => {
  const D = window.RAPX;
  const $ = (s, el = document) => el.querySelector(s);
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

  const CATS = [
    ["Building", "Structures"], ["Defense", "Defences"], ["Infantry", "Infantry"],
    ["Vehicle", "Vehicles"], ["Aircraft", "Aircraft"], ["Ship", "Naval"],
  ];
  const SIDE = {
    Union: { c: "var(--union)", t: "var(--union-text)", label: "Union Alliance" },
    Vanguard: { c: "var(--vanguard)", t: "var(--vanguard-text)", label: "Vanguard Pact" },
  };
  const GRADE_COLOR = { S: "var(--gold)", A: "var(--good)", B: "#a6d65a", C: "#e3b04b", D: "#e07a4a", "-": "var(--faint)" };

  const nations = D.nations;
  const byId = Object.fromEntries(nations.map(n => [n.id, n]));
  const sideCount = side => nations.filter(n => n.side === side).length;
  const forNation = id => D.entries.filter(e => e.nations.includes(id));
  const isExclusive = e => e.nations.length === 1;
  const isNational = (e, n) => !isExclusive(e) && e.nations.length < sideCount(n.side);
  const img = (e, n) => `img/units/${(e.imageBy && e.imageBy[n.id]) || e.image}.jpg`;
  const flag = n => `img/flags/${n.id}.png`;
  const money = v => "$" + v.toLocaleString("en-US");
  const time = s => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}`;
  const num = v => Math.round(v).toLocaleString("en-US");
  const fix = v => (Math.round(v * 10) / 10).toString();

  // Same grading the in-game catalogue uses (PxCatalogueData.Grade): bars scale to the category's top units
  const pct = (vals, p) => {
    const v = vals.filter(x => x > 0).sort((a, b) => a - b);
    return v.length ? Math.max(.001, v[Math.min(v.length - 1, Math.round(p * (v.length - 1)))]) : 1;
  };
  const MAX = {};
  for (const [c] of CATS) {
    const list = D.entries.filter(e => e.category === c);
    MAX[c] = {
      hp: pct(list.map(e => e.hp), .95), dps: pct(list.map(e => e.dps), .95), range: pct(list.map(e => e.range), 1),
      speed: pct(list.map(e => e.speed), 1), sight: pct(list.map(e => e.sight), 1),
    };
  }

  document.querySelectorAll('[data-count="nations"]').forEach(el => el.textContent = nations.length);
  document.querySelectorAll('[data-count="entries"]').forEach(el => el.textContent = D.entries.length);

  // ---------- NATIONS ----------
  let dossierNation = byId.usa || nations[0];

  function renderFlagGrids() {
    document.querySelectorAll(".flag-grid").forEach(grid => {
      grid.innerHTML = nations.filter(n => n.side === grid.dataset.side).map(n => `
        <button class="flag-btn" data-nation="${n.id}" aria-pressed="${n.id === dossierNation.id}">
          <img src="${flag(n)}" alt="" loading="lazy"><span>${esc(n.name)}</span>
        </button>`).join("");
    });
  }

  function tiles(n) {
    const mine = forNation(n.id);
    return `<div class="dossier-tiles">
      <div class="tile"><b>${mine.length}</b><span>Entries</span></div>
      <div class="tile" style="--tc:var(--gold)"><b>${mine.filter(isExclusive).length}</b><span>Exclusive</span></div>
      <div class="tile" style="--tc:${SIDE[n.side].t}"><b>${mine.filter(e => isNational(e, n)).length}</b><span>Limited</span></div>
    </div>`;
  }

  function setSide(el, n) {
    el.style.setProperty("--side", SIDE[n.side].c);
    el.style.setProperty("--side-text", SIDE[n.side].t);
  }

  function renderDossier() {
    const n = dossierNation, el = $("#dossier");
    setSide(el, n);
    const special = forNation(n.id).filter(e => isExclusive(e) || isNational(e, n))
      .sort((a, b) => a.nations.length - b.nations.length);
    const shown = special.slice(0, 11);
    el.innerHTML = `
      <div class="dossier-flag fade-in"><img src="${flag(n)}" alt="Flag of ${esc(n.name)}"></div>
      <div class="fade-in">
        <p class="dossier-side">${SIDE[n.side].label} · National dossier</p>
        <h3>${esc(n.name)} <q>${esc(n.motto)}</q></h3>
        <p class="dossier-lore">${esc(n.lore)}</p>
        ${tiles(n)}
        ${n.specials.length ? `<ul class="dossier-specials">${n.specials.map(s => `<li>${esc(s)}</li>`).join("")}</ul>` : ""}
        ${special.length ? `<p class="strip-label">National arsenal</p>
        <div class="strip">${shown.map(e => `
          <button class="mini" data-unit="${esc(e.id)}">
            <img src="${img(e, n)}" alt="" loading="lazy">
            <span>${esc(e.name)}<small>${isExclusive(e) ? "Exclusive" : "Shared with " + (e.nations.length - 1)} · ${esc(e.category === "Ship" ? "Naval" : e.category)}</small></span>
          </button>`).join("")}${special.length > shown.length
            ? `<a class="strip-more" href="#arsenal" data-open-catalogue>+${special.length - shown.length} more<br>in the catalogue</a>` : ""}</div>` : ""}
        <div class="dossier-cta"><a class="btn btn-ghost" href="#arsenal" data-open-catalogue><span>Open ${esc(n.name)} in the catalogue</span></a></div>
      </div>`;
  }

  document.addEventListener("click", ev => {
    const fb = ev.target.closest(".flag-btn");
    if (fb) {
      dossierNation = byId[fb.dataset.nation];
      renderFlagGrids();
      renderDossier();
      return;
    }
    const mini = ev.target.closest(".mini");
    if (mini) {
      openCatalogue(dossierNation.id, mini.dataset.unit);
      return;
    }
    if (ev.target.closest("[data-open-catalogue]")) {
      ev.preventDefault();
      openCatalogue(dossierNation.id);
    }
  });

  // ---------- CATALOGUE ----------
  const S = { nation: byId.usa || nations[0], cat: "Vehicle", unit: null, q: "" };

  function renderNationList() {
    $("#cat-nation-list").innerHTML = ["Union", "Vanguard"].map(side => `
      <p class="cat-side" style="--c:${SIDE[side].c};--ct:${SIDE[side].t}">${side}<small>${sideCount(side)} nations</small></p>
      ${nations.filter(n => n.side === side).map(n => `
        <button class="cat-nation" data-cnation="${n.id}" style="--c:${SIDE[side].c}" aria-pressed="${n.id === S.nation.id}">
          <img src="${flag(n)}" alt="" loading="lazy">${esc(n.name)}
        </button>`).join("")}`).join("");
  }

  function renderBanner() {
    const n = S.nation, el = $("#cat-banner");
    setSide(el.closest(".catalogue"), n);
    el.innerHTML = `
      <img src="${flag(n)}" alt="Flag of ${esc(n.name)}">
      <div>
        <p class="dossier-side">${SIDE[n.side].label} · National dossier</p>
        <h3>${esc(n.name)} <q>${esc(n.motto)}</q></h3>
        <p>${esc(n.lore)}</p>
      </div>
      ${tiles(n)}`;
  }

  function visible() {
    const q = S.q.trim().toLowerCase();
    return forNation(S.nation.id).filter(e => q
      ? (e.name + " " + (e.role || "")).toLowerCase().includes(q)
      : e.category === S.cat);
  }

  function renderTabs() {
    const mine = forNation(S.nation.id);
    $("#cat-tabs").innerHTML = CATS.map(([c, label]) => {
      const count = mine.filter(e => e.category === c).length;
      return `<button class="cat-tab" role="tab" data-cat="${c}" aria-selected="${!S.q && c === S.cat}" ${count ? "" : "disabled"}>${label}<b>${count}</b></button>`;
    }).join("");
  }

  function renderGrid() {
    const list = visible(), n = S.nation;
    if (!list.some(e => e.id === S.unit)) S.unit = list[0]?.id ?? null;
    $("#cat-grid").innerHTML = list.length ? list.map(e => `
      <button class="card fade-in" data-unit="${esc(e.id)}" aria-pressed="${e.id === S.unit}">
        <span class="card-art">
          <img src="${img(e, n)}" alt="" loading="lazy">
          ${e.cost ? `<span class="badge badge-cost">${money(e.cost)}</span>` : ""}
          ${isExclusive(e) ? `<span class="badge badge-ex">Exclusive</span>` : isNational(e, n) ? `<span class="badge badge-nat">National</span>` : ""}
        </span>
        <span class="card-name">${esc(e.name)}</span>
      </button>`).join("") : `<p class="cat-empty">No entries match “${esc(S.q)}”.</p>`;
  }

  function bar(label, value, max, text) {
    const w = Math.max(0, Math.min(100, value / max * 100));
    return `<dt>${label}</dt><div class="bar"><i data-w="${value > 0 ? Math.max(2, w) : 0}"></i></div><dd>${text}</dd>`;
  }

  function targets(w) {
    return [w.ground && "GND", w.air && "AIR", w.naval && "SEA"].filter(Boolean).map(t => `<span class="tgt">${t}</span>`).join("");
  }

  function renderDetail() {
    const el = $("#cat-detail"), n = S.nation;
    const e = D.entries.find(x => x.id === S.unit);
    if (!e) { el.innerHTML = ""; return; }
    const m = MAX[e.category];
    const badge = isExclusive(e)
      ? `<span class="stage-badge" style="background:var(--gold);color:#1a1405">${esc(n.name)} exclusive</span>`
      : isNational(e, n) ? `<span class="stage-badge" style="background:var(--side)">National unit</span>` : "";
    const armor = e.armor && e.armor !== "None" ? e.armor : e.category === "Infantry" ? "Infantry" : "None";
    const armed = e.weapons.some(w => !w.support);

    el.innerHTML = `
      <button class="detail-close" type="button" aria-label="Close details">×</button>
      <div class="stage fade-in">
        <img src="${img(e, n)}" alt="${esc(e.name)}">
        <div class="stage-scan"></div>
        <div class="stage-corners"><i></i><i></i><i></i><i></i></div>
        <div class="stage-head">
          <p class="stage-role">${esc(e.role)}</p>
          <h3>${esc(e.name)}</h3>
          ${badge}
        </div>
        <div class="stage-foot"><span>${esc(CATS.find(c => c[0] === e.category)[1])} · ${esc(e.id)}</span><span>${esc(n.name)} arsenal</span></div>
      </div>

      <div class="stat-tiles">
        <div class="tile" style="--tc:var(--gold)"><b>${e.cost ? money(e.cost) : "Free"}</b><span>Cost</span></div>
        <div class="tile"><b>${time(e.buildSeconds)}</b><span>Build time</span></div>
        <div class="tile"><b>${num(e.hp)}</b><span>Hit points</span></div>
        <div class="tile" style="--tc:var(--holo)"><b>${esc(armor)}</b><span>Armour</span></div>
      </div>

      <p class="block-title">Performance</p>
      <dl class="perf">
        ${bar("Durability", e.hp, m.hp, num(e.hp))}
        ${bar("Firepower", e.dps, m.dps, armed ? num(e.dps) + " DPS" : "—")}
        ${bar("Range", e.range, m.range, e.range ? fix(e.range) + " cells" : "—")}
        ${bar("Speed", e.speed, m.speed, e.speed ? fix(e.speed) + " cells/s" : "Static")}
        ${bar("Vision", e.sight, m.sight, fix(e.sight) + " cells")}
      </dl>

      ${armed ? `<p class="block-title">Effective against</p>
      <div class="grades">${D.classes.map((c, i) => {
        const g = e.grades[i];
        return `<div class="grade" style="--gc:${GRADE_COLOR[g]}"><b>${g}</b><span>${esc(c)}</span></div>`;
      }).join("")}</div>` : ""}

      ${e.weapons.length ? `<p class="block-title">Weapons</p>
      <table class="weapons">
        <thead><tr><th>Weapon</th><th>Damage</th><th>Reload</th><th>Range</th></tr></thead>
        <tbody>${e.weapons.map(w => `
          <tr>
            <td>${esc(w.name)}<small>${esc(w.kind)}${targets(w)}</small></td>
            <td>${w.support ? "Support" : num(w.damage) + (w.burst > 1 ? " ×" + w.burst : "")}</td>
            <td>${fix(w.reload)} s</td>
            <td>${fix(w.range)}</td>
          </tr>`).join("")}</tbody>
      </table>` : ""}

      ${e.features.length ? `<p class="block-title">Capabilities</p>
      <ul class="chips">${e.features.map(f => `<li>${esc(f)}</li>`).join("")}</ul>` : ""}

      ${e.lore ? `<p class="block-title">Field dossier</p>
      <p class="lore">${esc(e.lore)}</p>` : ""}
      ${e.requires.length ? `<p class="lore-meta">Requires: <b>${e.requires.map(esc).join(" · ")}</b></p>` : ""}
      ${e.power ? `<p class="lore-meta">Power: <b>${e.power > 0 ? "+" : ""}${e.power}</b></p>` : ""}`;

    requestAnimationFrame(() => requestAnimationFrame(() =>
      el.querySelectorAll(".bar i").forEach(i => i.style.width = i.dataset.w + "%")));
  }

  function renderCatalogue() {
    renderNationList();
    renderBanner();
    renderTabs();
    renderGrid();
    renderDetail();
  }

  function selectUnit(id, open) {
    S.unit = id;
    document.querySelectorAll(".card").forEach(c => c.setAttribute("aria-pressed", c.dataset.unit === id));
    renderDetail();
    if (open) $("#cat-detail").classList.add("open");
    try { history.replaceState(null, "", `#arsenal/${S.nation.id}/${id}`); } catch (_) { /* file:// */ }
  }

  function openCatalogue(nationId, unitId) {
    S.nation = byId[nationId] || S.nation;
    S.q = "";
    $("#cat-search").value = "";
    const e = unitId && D.entries.find(x => x.id === unitId);
    if (e) S.cat = e.category;
    else if (!forNation(S.nation.id).some(x => x.category === S.cat)) S.cat = "Vehicle";
    S.unit = e ? e.id : null;
    renderCatalogue();
    $("#arsenal").scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
    if (e && matchMedia("(max-width: 1100px)").matches) $("#cat-detail").classList.add("open");
  }

  $("#cat-nation-list").addEventListener("click", ev => {
    const b = ev.target.closest("[data-cnation]");
    if (!b) return;
    S.nation = byId[b.dataset.cnation];
    if (!forNation(S.nation.id).some(e => e.id === S.unit)) S.unit = null;
    renderCatalogue();
  });
  $("#cat-tabs").addEventListener("click", ev => {
    const b = ev.target.closest("[data-cat]");
    if (!b || b.disabled) return;
    S.cat = b.dataset.cat;
    S.q = "";
    $("#cat-search").value = "";
    S.unit = null;
    renderTabs();
    renderGrid();
    renderDetail();
  });
  $("#cat-grid").addEventListener("click", ev => {
    const c = ev.target.closest(".card");
    if (c) selectUnit(c.dataset.unit, true);
  });
  $("#cat-detail").addEventListener("click", ev => {
    if (ev.target.closest(".detail-close")) $("#cat-detail").classList.remove("open");
  });
  $("#cat-search").addEventListener("input", ev => {
    S.q = ev.target.value;
    S.unit = null;
    renderTabs();
    renderGrid();
    renderDetail();
  });


  // ---------- CREDITS ----------
  const CD = window.RAPX_CREDITS || {};
  const C = CD.sections || [];
  const LIC = {
    "CC BY 4.0": ["lic-by4", "https://creativecommons.org/licenses/by/4.0/"],
    "CC BY 3.0": ["lic-by3", "https://creativecommons.org/licenses/by/3.0/"],
    "CC0": ["lic-cc0", "https://creativecommons.org/publicdomain/zero/1.0/"],
    "CC BY-NC": ["lic-nc", "https://creativecommons.org/licenses/by-nc/4.0/"],
    "Sketchfab Standard": ["lic-std", "https://sketchfab.com/licenses"],
    "Licence pending": ["lic-pending", null],
  };
  const CR = { group: "all", artist: null, q: "" };
  const allCredits = C.flatMap((g, gi) => g.items.map(it => ({ ...it, gi })));
  const artistCount = {};
  allCredits.forEach(it => it.artists.forEach(a => artistCount[a] = (artistCount[a] || 0) + 1));
  const artists = Object.keys(artistCount).sort((a, b) => artistCount[b] - artistCount[a] || a.localeCompare(b));

  function renderCreditStats() {
    const models = allCredits.reduce((n, it) => n + it.models.length, 0);
    const licences = new Set(allCredits.map(it => it.licence).filter(l => l && l !== "Licence pending")).size;
    $("#credit-stats").innerHTML = `
      <div class="tile"><b>${allCredits.length}</b><span>Credits</span></div>
      <div class="tile" style="--tc:var(--gold)"><b>${artists.length}</b><span>Artists</span></div>
      <div class="tile" style="--tc:var(--holo)"><b>${models}</b><span>3D models</span></div>
      <div class="tile" style="--tc:var(--good)"><b>${licences}</b><span>Licences</span></div>`;
  }

  function renderRoll() {
    $("#roll-names").innerHTML = artists.map((a, i) =>
      `<button class="roll-name${i < 12 ? " top" : ""}" data-artist="${esc(a)}" aria-pressed="${a === CR.artist}">${esc(a)}<b>${artistCount[a]}</b></button>`).join("");
  }

  function renderCreditFilters() {
    const tabs = [["all", "All", allCredits.length], ...C.map((g, i) => [String(i), g.title, g.items.length])];
    $("#credit-filters").innerHTML = tabs.map(([id, label, n]) =>
      `<button class="cat-tab" role="tab" data-group="${id}" aria-selected="${CR.group === id}">${esc(label)}<b>${n}</b></button>`).join("");
  }

  function licBadge(l) {
    if (!l) return "";
    const [cls, url] = LIC[l] || ["", null];
    return url ? `<a class="lic ${cls}" href="${url}" rel="license">${esc(l)}</a>` : `<span class="lic ${cls}">${esc(l)}</span>`;
  }

  function creditCard(it) {
    const by = it.artists.length
      ? `<p class="credit-by">by ${it.artists.map(a => `<button type="button" data-artist="${esc(a)}">${esc(a)}</button>`).join(", ")}</p>` : "";
    return `<article class="credit${it.models.length || it.artists.length ? "" : " credit-note"}">
      <p class="credit-subject">${esc(it.subject)}</p>
      ${licBadge(it.licence)}
      ${it.models.length ? `<p class="credit-models">${it.models.map(m => `<a href="${esc(m.url)}">${esc(m.title)}</a>`).join("")}</p>` : ""}
      ${it.text ? `<p class="credit-text">${esc(it.text)}</p>` : ""}
      ${by}
      ${it.changes ? `<p class="credit-changes"><b>Changes</b>${esc(it.changes)}</p>` : ""}
    </article>`;
  }

  function renderCredits() {
    const q = CR.q.trim().toLowerCase();
    const match = it => (CR.group === "all" || String(it.gi) === CR.group)
      && (!CR.artist || it.artists.includes(CR.artist))
      && (!q || [it.subject, it.text, it.changes, it.licence, ...it.artists, ...it.models.map(m => m.title)].join(" ").toLowerCase().includes(q));
    const html = C.map((g, gi) => {
      const items = allCredits.filter(it => it.gi === gi && match(it));
      if (!items.length) return "";
      return `<section class="credit-group fade-in">
        <header class="credit-group-head"><h3>${esc(g.title)}</h3><span>${items.length} ${items.length === 1 ? "credit" : "credits"}</span>
          ${g.intro && !CR.artist && !q ? `<p>${esc(g.intro)}</p>` : ""}</header>
        <div class="credit-grid">${items.map(creditCard).join("")}</div>
      </section>`;
    }).join("");
    $("#credit-list").innerHTML = html || `<p class="cat-empty">No credits match.</p>`;
    const active = $("#credit-active");
    active.hidden = !CR.artist;
    if (CR.artist) active.innerHTML = `Showing work by <b>${esc(CR.artist)}</b><button type="button" data-clear-artist>Show everyone</button>`;
    document.querySelectorAll(".roll-name").forEach(b => b.setAttribute("aria-pressed", b.dataset.artist === CR.artist));
  }

  if (CD.creator) {
    const el = $("#credit-creator");
    el.hidden = false;
    el.innerHTML = `
      <div class="creator-mark">RAPX</div>
      <div>
        <p class="kicker">Created by</p>
        <h3>${esc(CD.creator.name)}</h3>
        <p>Design, code, art pipeline and everything in between.</p>
      </div>
      <button class="btn btn-primary" type="button" data-copy="${esc(CD.creator.email)}" title="Copy email address"><span>${esc(CD.creator.email)}</span></button>`;
  }

  if (C.length) {
    renderCreditStats();
    renderRoll();
    if (matchMedia("(max-width: 760px)").matches) {
      $("#roll-names").classList.add("collapsed");
      $("#roll-more").hidden = false;
      $("#roll-more").textContent = `Show all ${artists.length} artists`;
      $("#roll-more").addEventListener("click", ev => {
        $("#roll-names").classList.remove("collapsed");
        ev.currentTarget.hidden = true;
      });
    }
    renderCreditFilters();
    renderCredits();
    $("#credits").addEventListener("click", ev => {
      const g = ev.target.closest("[data-group]");
      if (g) {
        CR.group = g.dataset.group;
        renderCreditFilters();
        renderCredits();
        return;
      }
      const a = ev.target.closest("[data-artist]");
      if (a) {
        CR.artist = CR.artist === a.dataset.artist ? null : a.dataset.artist;
        CR.group = "all";
        renderCreditFilters();
        renderCredits();
        if (!a.classList.contains("roll-name")) $("#credit-active").scrollIntoView({ block: "center" });
        return;
      }
      if (ev.target.closest("[data-clear-artist]")) {
        CR.artist = null;
        renderCredits();
      }
    });
    $("#credit-search").addEventListener("input", ev => {
      CR.q = ev.target.value;
      renderCredits();
    });
  }

  // Email buttons copy the address: a mailto: link opens a blank page when no mail app is set up
  document.addEventListener("click", async ev => {
    const b = ev.target.closest("[data-copy]");
    if (!b) return;
    const label = $("span", b), text = label.textContent;
    try {
      await navigator.clipboard.writeText(b.dataset.copy);
      label.textContent = "Copied ✓";
    } catch (_) {
      label.textContent = b.dataset.copy;
    }
    setTimeout(() => label.textContent = text, 1800);
  });

  // ---------- GALLERY, DEPLOY, MOTION ----------
  const lb = $("#lightbox");
  document.querySelectorAll(".shot").forEach(s => s.addEventListener("click", () => {
    $("img", lb).src = s.dataset.full;
    $("img", lb).alt = $("img", s).alt;
    lb.showModal();
  }));
  lb.addEventListener("click", ev => { if (ev.target === lb || ev.target.closest(".lightbox-close")) lb.close(); });

  // Each install step has its own tab set; a tab shows the matching terminal in the same step
  document.querySelectorAll(".os-tabs button").forEach(b => b.addEventListener("click", () => {
    const step = b.closest("li");
    step.querySelectorAll(".os-tabs button").forEach(x => x.setAttribute("aria-selected", x === b));
    step.querySelectorAll(".term").forEach(t => t.hidden = t.dataset.tab !== b.dataset.tab);
  }));
  if (/Win/.test(navigator.platform)) $('.os-tabs [data-tab="win"]').click();
  document.querySelectorAll(".copy").forEach(b => b.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText($("code", b.parentElement).textContent);
      b.textContent = "Copied";
    } catch (_) {
      b.textContent = "Select & copy";
    }
    setTimeout(() => b.textContent = "Copy", 1600);
  }));

  const io = "IntersectionObserver" in window && new IntersectionObserver(entries => entries.forEach(en => {
    if (en.isIntersecting) { en.target.classList.add("in"); io.unobserve(en.target); }
  }), { rootMargin: "0px 0px -8% 0px" });
  document.querySelectorAll(".reveal").forEach(el => io ? io.observe(el) : el.classList.add("in"));

  // ---------- START ----------
  renderFlagGrids();
  renderDossier();
  const m = location.hash.match(/^#arsenal\/([^/]+)\/(.+)$/);
  if (m && byId[m[1]]) {
    S.nation = byId[m[1]];
    const e = D.entries.find(x => x.id === decodeURIComponent(m[2]));
    if (e) { S.cat = e.category; S.unit = e.id; }
  }
  renderCatalogue();
})();
