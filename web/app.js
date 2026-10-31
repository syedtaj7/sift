"use strict";

const $ = (s) => document.querySelector(s);
const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
const fmt = (n) => Number(n).toLocaleString("en-IN");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const thumbUrl = (id) => `/thumb/${id}`;
const peekUrl = (file) => `/api/peek?file=${encodeURIComponent(file)}`;
const STEP = (n) => `steps(${n})`;
const icon = (name) => `<i class="pixelart-icons-font-${name}"></i>`;

const COLORS = {
  yellow: "#ffe14d", orange: "#ffa62b", red: "#ff4d6d", pink: "#ff7ac6",
  purple: "#a26bff", blue: "#4d7bff", cyan: "#2ec4ff", green: "#3ddc84",
};
const TRIP_COLORS = ["yellow", "cyan", "red", "green", "pink", "orange", "purple", "blue"];

// How long each beat of the show takes. "scan" is the time a photo sits on stage being analysed.
const SPEEDS = {
  chill: { scan: 1500, flight: 950, gap: 0 },
  quick: { scan: 600, flight: 720, gap: 0 },
  turbo: { scan: 0, flight: 640, gap: 45 },
};

// Everything that is NOT kept. These stay in Google Photos and are only counted.
const SKIPS = [
  { key: "people", title: "People", icon: "users", color: "pink" },
  { key: "home", title: "Around home", icon: "home", color: "green" },
  { key: "received", title: "WhatsApp and received", icon: "message", color: "cyan" },
  { key: "screens", title: "Screenshots and blurry", icon: "device-phone", color: "purple" },
  { key: "nolocation", title: "No location", icon: "map", color: "orange" },
  { key: "duplicate", title: "Duplicates", icon: "copy", color: "blue" },
];

const state = {
  speed: "quick", paused: false, queue: [], total: 0, checked: 0, kept: 0, shown: 0,
  finished: false, flying: 0, src: "", out: "", isZip: false, zipGb: 0, mode: "zip",
  tiles: new Map(), seen: [], tripIndex: 0, skipped: {}, places: new Set(),
  combo: { key: "", n: 0 }, segs: [],
};

/* ================================================================ logo */

function pixelWord(el, text, colors) {
  el.textContent = "";
  [...text].forEach((ch, i) => {
    const s = document.createElement("span");
    s.className = "ch";
    if (ch === " ") s.innerHTML = "&nbsp;";
    else s.textContent = ch;
    s.style.setProperty("--c", COLORS[colors[i % colors.length]]);
    s.style.animationDelay = `${i * 0.12}s, ${1.2 + i * 0.15}s`;
    el.append(s);
  });
}

/* ================================================================ setup */

// Zip mode reads Takeout zips; Photos mode reads a plain folder (and its subfolders).
const MODES = {
  zip: { label: "Takeout zip", icon: "archive", empty: "Choose a zip", hint: "Pick one Takeout zip. You can do the next one after.",
         title: "Choose a Takeout zip", next: "Next zip", missing: "Pick a Takeout zip first." },
  folder: { label: "Photos folder", icon: "image", empty: "Choose a folder", hint: "Pick a folder of photos and videos. Its subfolders are sorted too.",
            title: "Choose a photos folder", next: "Next folder", missing: "Pick a photos folder first." },
};

function setMode(mode, animate = true) {
  state.mode = mode;
  try { localStorage.setItem("sift-mode", mode); } catch {}
  const m = MODES[mode];
  document.querySelectorAll(".mode button").forEach((b) => {
    const on = b.dataset.mode === mode;
    b.classList.toggle("on", on);
    b.setAttribute("aria-checked", on);
    if (on && animate) {
      const r = b.getBoundingClientRect();
      FX.burst(r.left + r.width / 2, r.top + r.height / 2, [getComputedStyle(b).getPropertyValue("--c").trim() || COLORS.yellow, COLORS.yellow], 16);
    }
  });
  $("#srcLabel").textContent = m.label;
  $("#srcIcon").className = `pixelart-icons-font-${m.icon}`;
  $("#presets").hidden = mode !== "zip";
  // A zip chosen in Zip mode doesn't belong in Photos mode, and the other way round.
  setPath("src", state.src && /\.zip$/i.test(state.src) !== (mode === "zip") ? "" : state.src);
  const hint = $("#srcHint");
  if (!state.src) { hint.className = "hint"; hint.textContent = m.hint; }
  renderCollection(defaults.existing, defaults.zips_done);
}

let defaults = {};
// Tells the desktop app this window is still open; it closes itself a while after the window goes.
setInterval(() => fetch("/api/ping").catch(() => {}), 20000);

async function initSetup() {
  pixelWord($("#logo"), "SIFT", ["yellow", "pink", "cyan", "green"]);
  defaults = await (await fetch("/api/defaults")).json();
  setPath("out", defaults.output);
  setPath("src", "");
  if (defaults.demo) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "tag-btn";
    b.style.setProperty("--c", COLORS.yellow);
    b.textContent = "Try the demo zip";
    b.onclick = () => { setPath("src", defaults.demo); checkSource(); };
    $("#presets").append(b);
  }
  let mode = "zip";
  try { mode = localStorage.getItem("sift-mode") === "folder" ? "folder" : "zip"; } catch {}
  setMode(mode, false);
  document.querySelectorAll(".mode button").forEach((b) => (b.onclick = () => b.dataset.mode !== state.mode && setMode(b.dataset.mode)));
  document.querySelectorAll("[data-target]").forEach((b) => (b.onclick = () => openBrowser(b.dataset.target)));
  initHome(defaults.home);
  $("#setupForm").addEventListener("submit", startSort);
}

/** Trips already collected from earlier zips, shown on the first page. */
function renderCollection(trips, zipsDone) {
  const el = $("#collection");
  $("#formTitle").textContent = state.mode === "folder" ? "Load photos" : "Load zip";
  if (!trips || !trips.length) { el.hidden = true; return; }
  const total = trips.reduce((a, t) => a + t.count, 0);
  el.hidden = false;
  el.innerHTML = `<div class="col-head">${icon("trophy")}<span>Your collection: <b>${fmt(total)}</b> trip shots${zipsDone ? ` from ${zipsDone} zip${zipsDone === 1 ? "" : "s"}` : ""}</span></div>
    <div class="col-list">${trips.map((t, i) => `<span class="col-chip" style="--c:${COLORS[TRIP_COLORS[i % TRIP_COLORS.length]]}">${escapeHtml(t.region)} <b>${fmt(t.count)}</b></span>`).join("")}</div>`;
  $("#formTitle").textContent = state.mode === "folder" ? "Load photos" : zipsDone ? `Load zip ${zipsDone + 1}` : "Load zip";
}

function setPath(which, path) {
  state[which] = path;
  const box = $(`#${which}Box`);
  box.classList.toggle("empty", !path);
  $(`#${which}Text`).textContent = path ? `‎${path}` : which === "src" ? MODES[state.mode].empty : "Choose a folder";
  box.title = path;
}

/* Home is chosen once, on the first run, from Sift's offline place list, and saved on this PC. */
const home = { value: null, options: [], active: -1, timer: 0 };

function initHome(saved) {
  home.value = saved;
  if (saved) $("#rad").value = String(saved.radius);
  renderHome();
  toggleHomeEdit(!saved);
  $("#homeChange").onclick = () => toggleHomeEdit($("#homeEdit").hidden);
  $("#rad").onchange = () => { if (home.value) saveHome({ ...home.value, radius: +$("#rad").value }); };
  const input = $("#homeSearch");
  input.addEventListener("input", () => {
    clearTimeout(home.timer);
    home.timer = setTimeout(() => searchHome(input.value), 140);
  });
  input.addEventListener("keydown", (e) => {
    if (!home.options.length) return;
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      home.active = (home.active + (e.key === "ArrowDown" ? 1 : -1) + home.options.length) % home.options.length;
      paintHomeList();
    } else if (e.key === "Enter") {
      e.preventDefault();
      pickHome(home.options[Math.max(0, home.active)]);
    } else if (e.key === "Escape") {
      closeHomeList();
    }
  });
}

function renderHome() {
  const h = home.value;
  $("#home").classList.toggle("unset", !h);
  $("#homeSummary").innerHTML = h
    ? `Home is <b id="homeName">${escapeHtml(h.name)}</b>, within <b id="homeRadiusLabel">${h.radius} km</b>`
    : `<b id="homeName">Where's home?</b> Set it once so Sift can skip photos taken there`;
  $("#homeChange").hidden = !h;
}

function toggleHomeEdit(open) {
  $("#homeEdit").hidden = !open;
  $("#homeChange").setAttribute("aria-expanded", open);
  $("#homeChange").textContent = open ? "Done" : "Change";
  if (open) setTimeout(() => $("#homeSearch").focus(), 30);
  else closeHomeList();
}

async function searchHome(q) {
  if (q.trim().length < 2) { closeHomeList(); return; }
  home.options = await (await fetch(`/api/cities?q=${encodeURIComponent(q)}`)).json();
  home.active = home.options.length ? 0 : -1;
  paintHomeList(q);
}

function paintHomeList(q) {
  const list = $("#homeList");
  list.hidden = false;
  $("#homeSearch").setAttribute("aria-expanded", "true");
  if (!home.options.length) {
    list.innerHTML = `<div class="home-empty">No town called "${escapeHtml(q || $("#homeSearch").value)}" in Sift's list. Try a bigger nearby city.</div>`;
    return;
  }
  list.innerHTML = "";
  home.options.forEach((c, i) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "home-opt" + (i === home.active ? " active" : "");
    b.setAttribute("role", "option");
    b.setAttribute("aria-selected", i === home.active);
    b.innerHTML = `<span>${escapeHtml(c.name)}</span><small>${escapeHtml(c.where)}</small>`;
    b.onmousedown = (e) => e.preventDefault();
    b.onclick = () => pickHome(c);
    list.append(b);
  });
}

function closeHomeList() {
  $("#homeList").hidden = true;
  $("#homeSearch").setAttribute("aria-expanded", "false");
  home.options = [];
}

async function pickHome(c) {
  if (!c) return;
  await saveHome({ name: c.name, lat: c.lat, lon: c.lon, radius: +$("#rad").value });
  $("#homeSearch").value = "";
  toggleHomeEdit(false);
  $("#formError").textContent = "";
  const r = $("#home").getBoundingClientRect();
  FX.burst(r.left + 24, r.top + r.height / 2, [COLORS.green, COLORS.yellow, COLORS.cyan], 20);
}

async function saveHome(h) {
  const res = await fetch("/api/settings", { method: "POST", body: JSON.stringify({ home: h }) });
  const data = await res.json();
  if (!res.ok) { $("#formError").textContent = data.error || "Couldn't save your home."; return; }
  home.value = data.home;
  renderHome();
}

async function checkSource() {
  const hint = $("#srcHint");
  if (!state.src) return;
  hint.className = "hint";
  hint.textContent = "Looking inside...";
  const r = await (await fetch(`/api/check?path=${encodeURIComponent(state.src)}`)).json();
  state.isZip = !!r.zip;
  state.zipGb = r.gb || 0;
  if (!r.exists) { hint.className = "hint bad"; hint.textContent = state.mode === "zip" ? "Can't find that zip." : "Can't find that folder."; return; }
  if (r.error) { hint.className = "hint bad"; hint.textContent = r.error; return; }
  if (!r.count) { hint.className = "hint bad"; hint.textContent = "No photos or videos in here."; return; }
  hint.className = r.done_before ? "hint bad" : "hint ok";
  hint.textContent = `${fmt(r.count)}${r.partial ? "+" : ""} photos and videos${r.zip ? ` in this ${r.gb} GB zip` : " in this folder and its subfolders"}` +
    (r.done_before ? ". You already sorted this zip, duplicates will be skipped." : "");
}

async function startSort(e) {
  e.preventDefault();
  $("#formError").textContent = "";
  if (!state.src) { $("#formError").textContent = MODES[state.mode].missing; openBrowser("src"); return; }
  if (!state.out) { $("#formError").textContent = "Pick your trip collection folder."; openBrowser("out"); return; }
  if (!home.value) { $("#formError").textContent = "Set your home city first."; toggleHomeEdit(true); return; }
  const btn = $("#startBtn");
  btn.disabled = true;
  const body = { source: state.src, output: state.out };
  const res = await fetch("/api/start", { method: "POST", body: JSON.stringify(body) });
  const data = await res.json();
  btn.disabled = false;
  if (!res.ok) { $("#formError").textContent = data.error || "Something went wrong."; return; }
  const r = btn.getBoundingClientRect();
  FX.burst(r.left + r.width / 2, r.top + r.height / 2, Object.values(COLORS), 40);
  await transitionToSorting();
  listen();
  runShow();
}

async function transitionToSorting() {
  const setup = $("#setup");
  if (!reduceMotion) {
    const out = setup.animate([{ opacity: 1, transform: "none" }, { opacity: 0, transform: "translateY(-30px)" }], { duration: 360, easing: STEP(4), fill: "forwards" });
    await Promise.race([out.finished, sleep(450)]);
  }
  setup.hidden = true;
  $("#sorting").hidden = false;
  pixelWord(document.querySelector(".hud .logo"), "SIFT", ["yellow", "pink", "cyan", "green"]);
  buildXp();
  buildBins();
  $("#leftTitle").textContent = state.mode === "zip" ? "Left in Google Photos" : "Left where they were";
  $("#card").classList.add("is-empty");
  sizeCard(4, 3);
  if (!reduceMotion) {
    document.querySelectorAll(".bin").forEach((b, i) =>
      b.animate([{ opacity: 0, transform: "translateY(20px)" }, { opacity: 1, transform: "none" }], { duration: 400, delay: 150 + i * 70, easing: STEP(4), fill: "backwards" }));
  }
}

/* ================================================================ file browser */

const browser = { target: "src", path: "", data: null, zip: "" };

function openBrowser(target) {
  browser.target = target;
  browser.zip = "";
  $("#brTitle").textContent = target === "src" ? MODES[state.mode].title : "Choose your trip collection folder";
  $("#browser").hidden = false;
  let start = state[target] || "";
  if (target === "src" && state.mode === "zip") start = start ? start.replace(/\\[^\\]+\.zip$/i, "") : defaults.browse_start || "";
  if (target === "src" && state.mode === "folder") start = start || defaults.pictures || defaults.browse_start || "";
  loadDir(start).catch(() => loadDir(""));
  document.addEventListener("keydown", browserKeys);
}

function closeBrowser() {
  $("#browser").hidden = true;
  document.removeEventListener("keydown", browserKeys);
}

function browserKeys(e) {
  if (e.key === "Escape") closeBrowser();
  if (e.key === "Backspace" && document.activeElement?.tagName !== "INPUT" && browser.data) {
    e.preventDefault();
    loadDir(browser.data.parent ?? "");
  }
}

async function loadDir(path) {
  const res = await fetch(`/api/ls?path=${encodeURIComponent(path)}`);
  if (!res.ok) throw new Error("not found");
  const d = await res.json();
  browser.path = d.path;
  browser.data = d;
  browser.zip = "";

  const places = $("#brPlaces");
  places.innerHTML = "";
  const placeColors = ["green", "cyan", "yellow", "pink", "orange", "blue", "purple", "red"];
  [{ name: "This PC", path: "", icon: "monitor" }, ...d.places].forEach((p, i) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "place";
    b.style.setProperty("--c", COLORS[placeColors[i % placeColors.length]]);
    b.innerHTML = `${icon(p.icon)}<span>${escapeHtml(p.name)}</span>`;
    b.classList.toggle("on", p.path ? d.path.toLowerCase() === p.path.toLowerCase() : !d.path);
    b.onclick = () => loadDir(p.path);
    places.append(b);
  });

  const crumbs = $("#brCrumbs");
  crumbs.innerHTML = "";
  [{ name: "This PC", path: "" }, ...d.crumbs].forEach((c, i) => {
    if (i) crumbs.insertAdjacentHTML("beforeend", '<span class="crumb-sep">/</span>');
    const b = document.createElement("button");
    b.type = "button";
    b.className = "crumb";
    b.textContent = c.name;
    b.onclick = () => loadDir(c.path);
    crumbs.append(b);
  });
  $("#brUp").disabled = !d.path;
  $("#brUp").onclick = () => loadDir(d.parent ?? "");

  const pickingZip = browser.target === "src" && state.mode === "zip";
  const pickingPhotos = browser.target === "src" && state.mode === "folder";
  const pv = $("#brPreview");
  pv.innerHTML = "";
  if (browser.target === "out") {
    d.samples.forEach((f, i) => {
      const t = document.createElement("div");
      t.className = "pv";
      t.style.animationDelay = `${i * 40}ms`;
      t.style.backgroundImage = `url(${peekUrl(f)})`;
      pv.append(t);
    });
  }

  const list = $("#brList");
  list.innerHTML = "";
  const dirColors = ["yellow", "cyan", "pink", "green", "orange", "purple"];
  // Zip mode lists only zips (first, they're what you're looking for) and folders;
  // Photos mode lists only folders and the photos and videos Sift can sort.
  (pickingZip ? d.zips || [] : []).forEach((z, i) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "dir zipfile";
    b.style.setProperty("--c", COLORS.green);
    b.style.animationDelay = `${i * 18}ms`;
    b.innerHTML = `${icon("archive")}<span title="${escapeHtml(z.name)}">${escapeHtml(z.name)}</span><small class="has">${z.gb} GB zip</small>`;
    b.onclick = () => selectZip(z, b);
    b.ondblclick = () => { selectZip(z, b); $("#brPick").click(); };
    list.append(b);
  });
  const items = d.path ? d.dirs : d.places.map((p) => ({ name: p.name, path: p.path, media: 0, icon: p.icon }));
  items.forEach((it, i) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "dir";
    b.style.setProperty("--c", COLORS[dirColors[i % dirColors.length]]);
    b.style.animationDelay = `${Math.min(i + (pickingZip ? (d.zips || []).length : 0), 24) * 18}ms`;
    const count = it.media ? `<small class="has">${it.media >= 999 ? "999+" : fmt(it.media)} photos</small>` : `<small>${it.icon ? "&nbsp;" : "folder"}</small>`;
    b.innerHTML = `${icon(it.icon || "folder")}<span title="${escapeHtml(it.name)}">${escapeHtml(it.name)}</span>${count}`;
    b.onclick = () => loadDir(it.path);
    list.append(b);
  });
  (pickingPhotos ? d.files || [] : []).forEach((f, i) => {
    const t = document.createElement("div");
    t.className = "dir mediafile";
    t.style.setProperty("--c", f.video ? COLORS.pink : COLORS.cyan);
    t.style.animationDelay = `${Math.min(i + items.length, 24) * 18}ms`;
    const thumb = !f.video && !/\.hei[cf]$/i.test(f.name)
      ? `<img src="${peekUrl(f.path)}" alt="" loading="lazy" decoding="async">` : icon(f.video ? "video" : "image");
    t.innerHTML = `${thumb}<span title="${escapeHtml(f.name)}">${escapeHtml(f.name)}</span><small>${f.video ? "video" : "photo"}</small>`;
    list.append(t);
  });
  if (pickingPhotos && d.media_here > (d.files || []).length) {
    list.insertAdjacentHTML("beforeend", `<div class="br-empty">and ${fmt(d.media_here - d.files.length)} more</div>`);
  }
  if (!list.children.length) list.innerHTML = `<div class="br-empty">${pickingZip ? "No zips or folders in here" : pickingPhotos ? "No photos, videos or folders in here" : "Nothing in here"}</div>`;
  list.scrollTop = 0;
  updateBrowserFoot();
}

function selectZip(z, el) {
  browser.zip = z.path;
  document.querySelectorAll(".dir.zipfile").forEach((b) => b.classList.toggle("picked", b === el));
  updateBrowserFoot(z);
}

function updateBrowserFoot(zip) {
  const d = browser.data;
  const pick = $("#brPick");
  if (browser.target === "src" && state.mode === "folder") {
    $("#brSelIcon").className = "pixelart-icons-font-image";
    $("#brSel").textContent = d.path ? `‎${d.path}` : "Open the folder with your photos";
    $("#brCount").textContent = d.media_here ? `${fmt(d.media_here)} here` : "";
    pick.querySelector("span").textContent = "Sort this folder";
    pick.disabled = !d.path;
  } else if (browser.target === "src") {
    $("#brSelIcon").className = `pixelart-icons-font-${zip ? "archive" : "folder"}`;
    $("#brSel").textContent = zip ? `‎${zip.path}` : d.path ? (d.zips?.length ? "Click a zip to choose it" : "No zips here yet. Open the folder you downloaded them to.") : "This PC";
    $("#brCount").textContent = zip ? `${zip.gb} GB` : "";
    pick.querySelector("span").textContent = "Use this zip";
    pick.disabled = !zip;
  } else {
    $("#brSelIcon").className = "pixelart-icons-font-folder";
    $("#brSel").textContent = d.path ? `‎${d.path}` : "This PC";
    $("#brCount").textContent = "";
    pick.querySelector("span").textContent = "Collect trips here";
    pick.disabled = !d.path;
  }
}

$("#brClose").onclick = closeBrowser;
$("#browser").addEventListener("click", (e) => { if (e.target.id === "browser") closeBrowser(); });
$("#brPick").onclick = () => {
  if (browser.target === "src") {
    const pick = state.mode === "zip" ? browser.zip : browser.path;
    if (!pick) return;
    setPath("src", pick);
    checkSource();
  } else {
    if (!browser.path) return;
    setPath("out", browser.path);
  }
  const r = $("#brPick").getBoundingClientRect();
  FX.burst(r.left + r.width / 2, r.top + r.height / 2, [COLORS.yellow, COLORS.green, COLORS.cyan], 22);
  closeBrowser();
};

/* ================================================================ events */

function listen() {
  const es = new EventSource("/api/events?since=0");
  es.onmessage = (m) => {
    const ev = JSON.parse(m.data);
    switch (ev.type) {
      case "existing":
        ev.trips.forEach((t) => createTripTile(t.region, t.cover ? peekUrl(t.cover) : null, t.cities, t.count, false));
        break;
      case "phase":
        setStatus(ev.text);
        break;
      case "start":
        state.total = ev.total;
        $("#pTotal").textContent = fmt(ev.total);
        break;
      case "tally":
        state.checked = ev.done;
        applySkips(ev.skipped);
        break;
      case "item":
        state.checked = Math.max(state.checked, ev.done);
        state.queue.push(ev);
        new Image().src = thumbUrl(ev.id); // preload so flying frames never appear empty
        break;
      case "finished":
        state.finished = true;
        state.checked = ev.done;
        applySkips(ev.skipped);
        es.close();
        break;
    }
    updateProgress();
  };
}

/* ================================================================ the show */

async function runShow() {
  while (true) {
    if (state.paused) { await sleep(150); continue; }
    const item = state.queue.shift();
    if (!item) {
      if (state.finished && state.flying === 0) return finish();
      await sleep(120);
      continue;
    }
    renderDeck();
    showBacklog();
    const sp = SPEEDS[state.speed];
    if (reduceMotion) {
      present(item, sp, true);
      land(item);
      await sleep(30);
    } else if (state.speed === "turbo") {
      turboStep(item);
      await sleep(sp.gap);
    } else {
      await present(item, sp);
      fly(item, $("#card").getBoundingClientRect(), sp.flight, true);
      await sleep(80);
    }
  }
}

let lastTurboFrame = 0;
function turboStep(item) {
  const card = $("#card");
  if (performance.now() - lastTurboFrame > 260) {
    lastTurboFrame = performance.now();
    present(item, SPEEDS.turbo, true);
  }
  card.style.opacity = 1;
  const r = card.getBoundingClientRect();
  const size = Math.min(r.width, r.height) * 0.4;
  fly(item, {
    left: r.left + r.width / 2 - size / 2 + (Math.random() - 0.5) * r.width * 0.5,
    top: r.top + r.height / 2 - size / 2 + (Math.random() - 0.5) * r.height * 0.5,
    width: size, height: size,
  }, SPEEDS.turbo.flight, false);
}

/** Put a trip photo on stage: drop it in, sweep the scanner, reveal where it's going. */
async function present(item, sp, quiet = false) {
  const card = $("#card");
  const color = tripColor(item.folder[1]);
  card.classList.remove("is-empty");
  sizeCard(item.fw || 4, item.fh || 3);
  card.style.setProperty("--c", "#fff4e0");
  $("#cardImg").style.backgroundImage = `url(${thumbUrl(item.id)})`;
  $("#cardVideo").hidden = !item.video;
  const chips = $("#chips"), verdict = $("#verdict");
  $("#faces").innerHTML = "";
  chips.innerHTML = "";
  verdict.innerHTML = `${icon("map")}${escapeHtml(item.folder[1])} <small>${escapeHtml(item.folder[2])}</small>`;
  verdict.style.setProperty("--c", color);

  if (quiet) {
    card.style.opacity = 1;
    card.style.setProperty("--c", color);
    verdict.style.opacity = state.speed === "turbo" ? 0 : 1;
    return;
  }
  const t = sp.scan;
  card.getAnimations().forEach((a) => a.cancel());
  card.style.opacity = 1;
  card.animate([{ opacity: 0, transform: "translateY(40px) scale(.9)" }, { opacity: 1, transform: "none" }], { duration: Math.min(360, t * 0.5), easing: STEP(4) });
  $("#scan").animate(
    [{ top: "0%", opacity: 1 }, { top: "100%", opacity: 1, offset: 0.95 }, { top: "100%", opacity: 0 }],
    { duration: t * 0.6, delay: t * 0.1, easing: STEP(14) }
  );
  chipList(item).forEach((c, i) => {
    const el = document.createElement("span");
    el.className = "chip";
    el.style.setProperty("--c", COLORS[c.color]);
    el.innerHTML = `${icon(c.icon)}${escapeHtml(c.text)}`;
    chips.append(el);
    el.animate([{ opacity: 0, transform: "translateY(10px)" }, { opacity: 1, transform: "none" }], { duration: 200, delay: t * 0.2 + i * t * 0.1, easing: STEP(2), fill: "backwards" });
  });
  verdict.style.opacity = 0;
  setTimeout(() => card.style.setProperty("--c", color), t * 0.6);
  verdict.animate([{ opacity: 0, transform: "scale(.5)" }, { opacity: 1, transform: "scale(1.15)", offset: 0.7 }, { opacity: 1, transform: "none" }], { duration: 260, delay: t * 0.62, easing: STEP(4), fill: "forwards" });
  await sleep(t);
}

function chipList(item) {
  const list = [{ icon: "pin", text: item.place.city, color: "yellow" }];
  if (item.ts) list.push({ icon: "calendar", text: new Date(item.ts * 1000).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }), color: "cyan" });
  if (item.loc_how === "nearby") list.push({ icon: "gps", text: "Place from nearby photos", color: "green" });
  else if (item.loc_how === "fixed") list.push({ icon: "gps", text: "Wrong GPS fixed", color: "orange" });
  if (item.video) list.push({ icon: "video", text: "Video", color: "red" });
  return list;
}

function sizeCard(w, h) {
  const stage = $("#stage").getBoundingClientRect();
  const s = Math.min(Math.min(stage.width * 0.66, 580) / w, (stage.height * 0.56) / h);
  const card = $("#card");
  card.style.width = `${Math.round(w * s)}px`;
  card.style.height = `${Math.round(h * s)}px`;
}

/** Fling a thumbnail from the stage into its trip along an arc, trailing coloured pixels. */
function fly(item, from, duration, fromCard) {
  const tile = ensureTile(item);
  revealTile(tile);
  const target = tile.el.getBoundingClientRect();
  const color = tile.color;
  const el = document.createElement("div");
  el.className = "flyer";
  el.style.backgroundImage = `url(${thumbUrl(item.id)})`;
  el.style.setProperty("--c", color);
  el.style.width = `${from.width}px`;
  el.style.height = `${from.height}px`;
  $("#flights").append(el);
  if (fromCard) $("#card").style.opacity = 0;

  const endScale = (Math.min(target.width, target.height) * 0.4) / Math.max(from.width, from.height);
  const sx = from.left, sy = from.top;
  const ex = target.left + target.width / 2 - from.width / 2;
  const ey = target.top + target.height / 2 - from.height / 2;
  const mx = (sx + ex) / 2 + (Math.random() - 0.5) * 60;
  const my = Math.min(sy, ey) - Math.min(200, 70 + Math.abs(ex - sx) * 0.3);
  const spin = (Math.random() < 0.5 ? -1 : 1) * (8 + Math.random() * 14);

  state.flying++;
  const stopTrail = FX.follow(el, [color, "#fff4e0", color]);
  const anim = el.animate(
    [
      { transform: `translate(${sx}px, ${sy}px) scale(1) rotate(0deg)`, opacity: 1 },
      { transform: `translate(${sx}px, ${sy - 18}px) scale(1.05) rotate(${spin * 0.2}deg)`, offset: 0.12 },
      { transform: `translate(${mx}px, ${my}px) scale(${(1 + endScale) / 2}) rotate(${spin}deg)`, offset: 0.5 },
      { transform: `translate(${ex}px, ${ey}px) scale(${endScale}) rotate(${spin * 0.3}deg)`, opacity: 1, offset: 0.92 },
      { transform: `translate(${ex}px, ${ey}px) scale(${endScale * 0.5}) rotate(0deg)`, opacity: 0 },
    ],
    { duration, easing: "cubic-bezier(.55,.05,.35,1)" }
  );
  let landed = false;
  const arrive = () => {
    if (landed) return;
    landed = true;
    stopTrail();
    el.remove();
    state.flying--;
    land(item, tile);
  };
  anim.onfinish = arrive;
  setTimeout(arrive, duration + 400); // fallback if the window stops rendering
}

/** The photo arrives: pixel burst, the trip tile gulps, its counter ticks, the XP bar fills. */
function land(item, tile = ensureTile(item)) {
  tile.n++;
  state.shown++;
  state.seen.push(item.id);
  const city = item.folder[2];
  state.places.add(city);
  tile.cities.set(city, (tile.cities.get(city) || 0) + 1);
  tile.el.querySelector(".cities").textContent = cityLine(tile.cities);
  if (tile.n === 1 || tile.n % 6 === 0 || !tile.hasCover) setCover(tile, thumbUrl(item.id));
  const num = tile.el.querySelector(".num");
  num.textContent = fmt(tile.n);
  if (!reduceMotion) {
    restartClass(tile.el, "gulp");
    restartClass(num, "tick");
    const r = tile.el.getBoundingClientRect();
    FX.burst(r.left + r.width / 2, r.top + r.height / 2, [tile.color, "#fff4e0"], state.speed === "turbo" ? 8 : 20);
  }
  bumpCombo(tile, item.folder);
  updateProgress();
}

function bumpCombo(tile, f) {
  const key = f.slice(0, 2).join("/");
  state.combo = state.combo.key === key ? { key, n: state.combo.n + 1 } : { key, n: 1 };
  const el = $("#combo");
  if (state.combo.n >= 3 && !reduceMotion) {
    el.hidden = false;
    el.style.setProperty("--c", tile.color);
    el.textContent = `Combo x${state.combo.n}`;
    restartClass(el, "tick");
  } else {
    el.hidden = true;
  }
}

function setCover(tile, url) {
  tile.hasCover = true;
  const old = tile.el.querySelector(".cover");
  const next = document.createElement("div");
  next.className = "cover";
  next.style.backgroundImage = `url(${url})`;
  next.style.opacity = 0;
  tile.el.prepend(next);
  requestAnimationFrame(() => (next.style.opacity = 1));
  if (old) setTimeout(() => old.remove(), 600);
}

function cityLine(map) {
  const names = [...map.entries()].sort((a, b) => b[1] - a[1]).map(([c]) => c);
  return names.length > 3 ? `${names.slice(0, 3).join(", ")} and ${names.length - 3} more` : names.join(", ");
}

/* ================================================================ tiles */

function tripColor(region) {
  const t = state.tiles.get(region);
  return t ? t.color : COLORS[TRIP_COLORS[state.tripIndex % TRIP_COLORS.length]];
}

function createTripTile(region, coverUrl, cities = {}, count = 0, isNew = true) {
  $("#tripsEmpty")?.remove();
  const color = COLORS[TRIP_COLORS[state.tripIndex++ % TRIP_COLORS.length]];
  const el = document.createElement("div");
  el.className = "trip";
  el.style.setProperty("--c", color);
  el.innerHTML = `<div class="meta"><div class="name">${escapeHtml(region)}</div><div class="cities"></div></div><span class="num num-badge">${fmt(count)}</span><span class="open-hint">Open folder</span>`;
  el.onclick = () => fetch("/api/open", { method: "POST", body: JSON.stringify({ folder: ["Trips", region] }) });
  $("#trips").append(el);
  if (!reduceMotion) el.classList.add("pop-in");
  const tile = { el, n: count, cities: new Map(Object.entries(cities)), color, hasCover: false };
  el.querySelector(".cities").textContent = cityLine(tile.cities);
  if (coverUrl) setCover(tile, coverUrl);
  state.tiles.set(region, tile);
  const areas = [...state.tiles.keys()].filter((k) => !k.startsWith("skip:")).length;
  $("#tripsCount").textContent = `${areas} area${areas === 1 ? "" : "s"}`;
  if (isNew) unlockBanner(region, color);
  return tile;
}

function ensureTile(item) {
  return state.tiles.get(item.folder[1]) || createTripTile(item.folder[1], thumbUrl(item.id));
}

let lastUnlock = 0;
function unlockBanner(name, color) {
  if (reduceMotion || performance.now() - lastUnlock < 1400) return;
  lastUnlock = performance.now();
  const el = $("#unlock");
  $("#unlockName").textContent = name;
  el.style.background = color;
  el.hidden = false;
  el.getAnimations().forEach((a) => a.cancel());
  el.animate(
    [{ transform: "translateY(-160%)" }, { transform: "translateY(0)", offset: 0.15 }, { transform: "translateY(-6px)", offset: 0.2 }, { transform: "translateY(0)", offset: 0.25 }, { transform: "translateY(0)", offset: 0.85 }, { transform: "translateY(-160%)" }],
    { duration: 1700, easing: STEP(18) }
  ).onfinish = () => (el.hidden = true);
  setTimeout(() => (el.hidden = true), 1900);
  setTimeout(() => {
    const r = el.getBoundingClientRect();
    FX.burst(r.left + r.width / 2, r.top + r.height / 2, [color, "#fff4e0", COLORS.yellow], 30);
  }, 260);
}

function revealTile(tile) {
  const box = $("#tripsScroll");
  const b = box.getBoundingClientRect(), t = tile.el.getBoundingClientRect();
  if (t.top < b.top || t.bottom > b.bottom - 10) box.scrollTo({ top: box.scrollTop + (t.top - b.top) - 8, behavior: "auto" });
}

/* ---- "left in Google Photos" counters */

function buildBins() {
  const bins = $("#bins");
  SKIPS.forEach((b) => {
    const el = document.createElement("div");
    el.className = "bin";
    el.style.setProperty("--c", COLORS[b.color]);
    el.innerHTML = `${icon(b.icon)}<div><div class="num">0</div><div class="title">${b.title}</div></div>`;
    el.querySelector("i").classList.add("icon");
    bins.append(el);
    state.tiles.set(`skip:${b.key}`, { el, n: 0, color: COLORS[b.color] });
  });
}

/** Skipped photos never fly; their counters tick up and the stage sheds a puff of pixels toward them. */
function applySkips(skipped) {
  if (!skipped) return;
  let total = 0;
  const stage = $("#stage").getBoundingClientRect();
  SKIPS.forEach((b) => {
    const n = skipped[b.key] || 0;
    total += n;
    const tile = state.tiles.get(`skip:${b.key}`);
    if (!tile || n === tile.n) return;
    tile.n = n;
    const num = tile.el.querySelector(".num");
    num.textContent = fmt(n);
    if (!reduceMotion) {
      restartClass(num, "tick");
      const r = tile.el.getBoundingClientRect();
      FX.sparkle(r.left + r.width / 2, r.top + 14, tile.color);
      FX.burst(stage.left + stage.width * (0.3 + Math.random() * 0.4), stage.bottom - 30, [tile.color], 6);
    }
  });
  state.skipped = skipped;
  $("#cloudTotal").textContent = fmt(total);
}

/* ================================================================ HUD */

function buildXp() {
  const bar = $("#xpBar");
  bar.innerHTML = "";
  state.segs = Array.from({ length: 40 }, () => {
    const i = document.createElement("i");
    bar.append(i);
    return i;
  });
}

function updateProgress() {
  const total = state.total || 1;
  // Bar fills as photos are checked; kept photos colour it once they land.
  const shownChecked = state.checked - state.queue.length - state.flying;
  const filled = Math.floor((Math.max(0, shownChecked) / total) * state.segs.length);
  state.segs.forEach((s, k) => {
    if (k < filled && !s.classList.contains("on")) {
      s.classList.add("on");
      s.style.setProperty("--c", COLORS[TRIP_COLORS[k % TRIP_COLORS.length]]);
    }
  });
  $("#pDone").textContent = fmt(Math.max(0, shownChecked));
  $("#pKept").textContent = fmt(state.shown);
  if (!state.paused && state.total && state.finished) setStatus(state.queue.length ? "Finishing the show" : "Wrapping up");
}

function setStatus(text) { $("#pStatus").textContent = text; }

function renderDeck() {
  const deck = $("#deck");
  deck.innerHTML = "";
  state.queue.slice(0, 4).reverse().forEach((it, i, arr) => {
    const d = document.createElement("div");
    d.className = "mini";
    d.style.backgroundImage = `url(${thumbUrl(it.id)})`;
    const depth = arr.length - 1 - i;
    d.style.transform = `translate(${depth * 8}px, ${-depth * 8}px)`;
    d.style.filter = `brightness(${1 - depth * 0.15})`;
    deck.append(d);
  });
}

function showBacklog() {
  const el = $("#backlog");
  const n = state.queue.length;
  if (n > 120 && state.speed !== "turbo") {
    el.hidden = false;
    el.innerHTML = `${fmt(n)} trip photos waiting in line<button type="button">Go Turbo</button>`;
    el.querySelector("button").onclick = () => setSpeed("turbo");
  } else {
    el.hidden = true;
  }
}

function setSpeed(s) {
  state.speed = s;
  document.querySelectorAll(".seg button").forEach((b) => {
    const on = b.dataset.speed === s;
    b.classList.toggle("on", on);
    b.setAttribute("aria-checked", on);
  });
  showBacklog();
}

/* ================================================================ finish */

async function finish() {
  state.queue = [];
  updateProgress();
  state.segs.forEach((s, k) => { if (!s.classList.contains("on")) { s.classList.add("on"); s.style.setProperty("--c", COLORS[TRIP_COLORS[k % TRIP_COLORS.length]]); } });
  setStatus("Done");
  $("#done").hidden = false;
  pixelWord($("#clearTitle"), state.isZip ? "Zip clear" : "All clear", ["yellow", "pink", "cyan", "green", "orange", "purple", "red", "blue"]);
  const left = Object.values(state.skipped).reduce((a, b) => a + b, 0);
  const allTrips = [...state.tiles.entries()].filter(([k]) => !k.startsWith("skip:"));
  const totalCollection = allTrips.reduce((a, [, t]) => a + t.n, 0);
  const stats = [
    { n: allTrips.length, label: allTrips.length === 1 ? "trip area" : "trip areas", c: "cyan" },
    { n: state.places.size, label: state.isZip ? "places this zip" : "places this folder", c: "green" },
    { n: totalCollection, label: "in your collection", c: "yellow" },
    { n: left, label: state.isZip ? "left in Google Photos" : "left where they were", c: "pink" },
  ];
  $("#doneStats").innerHTML = stats.map((s) => `<div class="stat" style="--c:${COLORS[s.c]}"><b>${fmt(s.n)}</b><span>${s.label}</span></div>`).join("");
  $("#doneNote").textContent = state.isZip
    ? "Your trip photos are safe in the collection folder. You can delete this zip to free space, then load the next one."
    : "";
  $("#openOut").onclick = () => fetch("/api/open", { method: "POST", body: JSON.stringify({ path: `${state.out}\\Trips` }) });
  $("#again").onclick = () => location.reload();
  $("#againText").textContent = MODES[state.mode].next;
  const del = $("#delZip");
  del.hidden = !state.isZip;
  $("#delZipText").textContent = `Delete zip (${state.zipGb} GB)`;
  del.onclick = askDeleteZip;
  countUp($("#doneNum"), state.shown);
  FX.fireworks(Object.values(COLORS), 8);
  if (!reduceMotion) confetti();
}

function askDeleteZip() {
  const name = state.src.split("\\").pop();
  $("#cfText").textContent = `Delete ${name} (${state.zipGb} GB) from your PC? Your ${fmt(state.shown)} trip photos from it are already saved, and everything is still in Google Photos.`;
  $("#confirm").hidden = false;
  $("#cfNo").onclick = () => ($("#confirm").hidden = true);
  $("#cfYes").onclick = async () => {
    $("#confirm").hidden = true;
    const res = await fetch("/api/delete-zip", { method: "POST", body: JSON.stringify({ path: state.src }) });
    const data = await res.json();
    const del = $("#delZip");
    if (res.ok) {
      del.disabled = true;
      $("#delZipText").textContent = `Freed ${data.freed_gb} GB`;
      const r = del.getBoundingClientRect();
      FX.burst(r.left + r.width / 2, r.top + r.height / 2, [COLORS.red, COLORS.yellow, "#fff4e0"], 36);
    } else {
      $("#doneNote").textContent = data.error || "Couldn't delete the zip.";
    }
  };
}

function countUp(el, to) {
  if (reduceMotion) { el.textContent = fmt(to); return; }
  const start = performance.now(), dur = 1300;
  const step = (now) => {
    const p = Math.min(1, (now - start) / dur);
    el.textContent = fmt(Math.round(to * (1 - Math.pow(1 - p, 3))));
    if (p < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
  setTimeout(() => (el.textContent = fmt(to)), dur + 200);
}

/** Your own trip photos pop up from the bottom and tumble down, each framed in a pixel colour. */
function confetti() {
  const ids = [...state.seen].sort(() => Math.random() - 0.5).slice(0, 22);
  const palette = Object.values(COLORS);
  ids.forEach((id, i) => {
    const el = document.createElement("div");
    el.className = "confetti";
    el.style.backgroundImage = `url(${thumbUrl(id)})`;
    el.style.setProperty("--c", palette[i % palette.length]);
    document.body.append(el);
    const x0 = innerWidth / 2 - 30, y0 = innerHeight + 40;
    const x1 = Math.random() * innerWidth - 30, y1 = innerHeight * (0.05 + Math.random() * 0.35);
    const x2 = x1 + (Math.random() - 0.5) * 160, r = (Math.random() - 0.5) * 120;
    el.animate(
      [
        { transform: `translate(${x0}px, ${y0}px) rotate(0deg) scale(.6)`, opacity: 0 },
        { transform: `translate(${x1}px, ${y1}px) rotate(${r * 0.5}deg) scale(1)`, opacity: 1, offset: 0.35 },
        { transform: `translate(${x2}px, ${innerHeight + 120}px) rotate(${r}deg) scale(.9)`, opacity: 0.9 },
      ],
      { duration: 2600 + Math.random() * 900, delay: i * 45, easing: "cubic-bezier(.2,.7,.4,1)", fill: "forwards" }
    ).onfinish = () => el.remove();
  });
}

/* ================================================================ utils + wiring */

function restartClass(el, cls) { el.classList.remove(cls); void el.offsetWidth; el.classList.add(cls); }
function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function debounce(fn, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }

document.querySelectorAll(".seg button").forEach((b) => (b.onclick = () => setSpeed(b.dataset.speed)));
$("#pauseBtn").onclick = async () => {
  state.paused = !state.paused;
  $("#pauseBtn").innerHTML = icon(state.paused ? "play" : "pause");
  $("#pauseBtn").setAttribute("aria-label", state.paused ? "Resume" : "Pause");
  setStatus(state.paused ? "Paused" : "Collecting trip photos");
  await fetch(state.paused ? "/api/pause" : "/api/resume", { method: "POST" });
};
$("#skipBtn").onclick = () => {
  while (state.queue.length) land(state.queue.shift());
  renderDeck();
  showBacklog();
};
window.addEventListener("resize", debounce(() => {
  const c = $("#card");
  if (c && !$("#sorting").hidden) sizeCard(parseFloat(c.style.width) || 4, parseFloat(c.style.height) || 3);
}, 200));

initSetup();
