/* Combat gallery: a full-width photo strip (drag, swipe, wheel or arrows), filter chips, a progress rail and a
   full-screen viewer with a thumbnail rail. Photos come from data/gallery.js (written by the stills export). */
(() => {
  const G = window.RAPX_GALLERY || [];
  const track = document.getElementById("gx-track");
  if (!G.length || !track) return;
  const $ = s => document.querySelector(s);
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const pad2 = n => String(n).padStart(2, "0");

  const FILTERS = [["all", "All"], ["gunships", "Gunships"], ["air", "Air war"], ["artillery", "Artillery"],
    ["naval", "Naval"], ["night", "Night & snow"], ["posters", "Posters"]];
  let filter = "all";
  let shown = G;

  function renderFilters() {
    $("#gx-filters").innerHTML = FILTERS.map(([id, label]) => {
      const n = id === "all" ? G.length : G.filter(p => p.tags.includes(id)).length;
      return n ? `<button class="cat-tab" role="tab" data-gx="${id}" aria-selected="${filter === id}">${label}<b>${n}</b></button>` : "";
    }).join("");
  }

  function renderTrack() {
    shown = filter === "all" ? G : G.filter(p => p.tags.includes(filter));
    track.innerHTML = shown.map((p, i) => `
      <figure class="gx-item${p.tags.includes("posters") ? " gx-poster" : ""}" style="--ar:${p.w / p.h};--i:${i}">
        <button type="button" data-open="${i}" aria-label="Open ${esc(p.title)}">
          <img src="${p.sm}" width="${p.w}" height="${p.h}" alt="${esc(p.title)}: ${esc(p.cap)}" loading="lazy" decoding="async" draggable="false">
        </button>
        <figcaption><span class="gx-no">${pad2(i + 1)}</span><b>${esc(p.title)}</b>${esc(p.cap)}</figcaption>
      </figure>`).join("");
    track.scrollLeft = 0;
    update();
  }

  // Progress rail and "first visible / total" readout
  function update() {
    const max = track.scrollWidth - track.clientWidth;
    const k = max > 0 ? track.scrollLeft / max : 1;
    $("#gx-progress").style.transform = `scaleX(${Math.max(0.04, k)})`;
    const items = [...track.children];
    const left = track.getBoundingClientRect().left + parseFloat(getComputedStyle(track).scrollPaddingLeft || 0);
    let first = items.findIndex(el => el.getBoundingClientRect().right > left + 40);
    if (k > 0.995) first = items.length - 1;
    $("#gx-count").innerHTML = `<b>${pad2(Math.max(0, first) + 1)}</b><i>/</i>${pad2(items.length)}`;
    $("#gx-prev").disabled = track.scrollLeft < 4;
    $("#gx-next").disabled = track.scrollLeft > max - 4;
  }
  track.addEventListener("scroll", () => requestAnimationFrame(update), { passive: true });
  addEventListener("resize", update);

  const step = dir => track.scrollBy({ left: dir * track.clientWidth * 0.8, behavior: "smooth" });
  $("#gx-prev").addEventListener("click", () => step(-1));
  $("#gx-next").addEventListener("click", () => step(1));
  track.addEventListener("keydown", ev => {
    if (ev.key === "ArrowRight") { ev.preventDefault(); step(1); }
    if (ev.key === "ArrowLeft") { ev.preventDefault(); step(-1); }
  });

  // Mouse drag to scroll (touch already scrolls natively); a drag never opens a photo
  let drag = null;
  track.addEventListener("pointerdown", ev => {
    if (ev.pointerType !== "mouse" || ev.button !== 0) return;
    drag = { x: ev.clientX, left: track.scrollLeft, moved: false };
  });
  addEventListener("pointermove", ev => {
    if (!drag) return;
    const dx = ev.clientX - drag.x;
    if (!drag.moved && Math.abs(dx) > 6) { drag.moved = true; track.classList.add("dragging"); }
    if (drag.moved) track.scrollLeft = drag.left - dx;
  });
  addEventListener("pointerup", () => {
    if (!drag) return;
    const moved = drag.moved;
    drag = null;
    track.classList.remove("dragging");
    if (moved) track.addEventListener("click", ev => ev.stopPropagation(), { capture: true, once: true });
  });

  $("#gx-filters").addEventListener("click", ev => {
    const b = ev.target.closest("[data-gx]");
    if (!b) return;
    filter = b.dataset.gx;
    renderFilters();
    renderTrack();
  });

  // ---------- viewer ----------
  const viewer = $("#gx-viewer");
  const img = $("#gxv-img");
  let cur = 0;

  function show(i) {
    cur = (i + shown.length) % shown.length;
    const p = shown[cur];
    img.classList.remove("in");
    img.src = p.sm;                       // the preview appears at once, the full photo replaces it when loaded
    img.alt = `${p.title}: ${p.cap}`;
    const full = new Image();
    full.onload = () => { if (shown[cur] === p) img.src = p.src; };
    full.src = p.src;
    requestAnimationFrame(() => img.classList.add("in"));
    $("#gxv-cap").innerHTML = `<b>${esc(p.title)}</b>${esc(p.cap)}`;
    $("#gxv-count").innerHTML = `<b>${pad2(cur + 1)}</b> / ${pad2(shown.length)}`;
    document.querySelectorAll(".gxv-thumb").forEach((t, k) => t.setAttribute("aria-current", k === cur));
    const t = document.querySelectorAll(".gxv-thumb")[cur];
    if (t) t.scrollIntoView({ block: "nearest", inline: "center", behavior: "smooth" });
    [cur - 1, cur + 1].forEach(k => { const q = shown[(k + shown.length) % shown.length]; new Image().src = q.src; });
  }

  function open(i) {
    $("#gxv-thumbs").innerHTML = shown.map((p, k) =>
      `<button class="gxv-thumb" type="button" data-to="${k}" aria-label="${esc(p.title)}"><img src="${p.sm}" alt="" loading="lazy"></button>`).join("");
    viewer.showModal();
    document.documentElement.classList.add("gx-locked");
    show(i);
  }
  viewer.addEventListener("close", () => document.documentElement.classList.remove("gx-locked"));

  track.addEventListener("click", ev => {
    const b = ev.target.closest("[data-open]");
    if (b) open(+b.dataset.open);
  });
  viewer.addEventListener("click", ev => {
    if (ev.target.closest(".gxv-close") || ev.target === viewer || ev.target.classList.contains("gxv-stage")) viewer.close();
    else if (ev.target.closest(".gxv-prev")) show(cur - 1);
    else if (ev.target.closest(".gxv-next")) show(cur + 1);
    else if (ev.target.closest("[data-to]")) show(+ev.target.closest("[data-to]").dataset.to);
  });
  viewer.addEventListener("keydown", ev => {
    if (ev.key === "ArrowRight") show(cur + 1);
    if (ev.key === "ArrowLeft") show(cur - 1);
  });
  let sx = null;
  viewer.addEventListener("touchstart", ev => { sx = ev.touches[0].clientX; }, { passive: true });
  viewer.addEventListener("touchend", ev => {
    if (sx === null) return;
    const dx = ev.changedTouches[0].clientX - sx;
    if (Math.abs(dx) > 50) show(cur + (dx < 0 ? 1 : -1));
    sx = null;
  });

  renderFilters();
  renderTrack();
})();
