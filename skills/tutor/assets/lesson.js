// tutor 導讀頁的互動；build.py 會把它內嵌進每一頁。目錄、頁眉、對照欄的 HTML 由 build.py 產生。
// 目錄和頁眉跟著捲動顯示現在在哪；一路讀下來的段落打勾，記在瀏覽器。
// 內文的 § 連結、頁眉的「速查卡」「名詞表」「查表」都在對照欄打開，正文不動；對照欄裡再跳可以按「返回」。
// 「並排」把對照欄變成右半邊，顯示那一整段。跨段跳轉走瀏覽器的上一頁。
// 翻譯過的圖預設顯示原文，圖說上的「看中文」切換；講義原文的小圖按一下搬進正文放大。
// 「只看重點」每段只留標題、重點、定義。深淺色由讀者切換，和練習頁共用 tutor-theme。
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const KEY = `tutor-guide:${document.title}`;
const store = (() => { try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch { return {}; } })();
const save = () => { try { localStorage.setItem(KEY, JSON.stringify(store)); } catch { /* 私密模式存不了就只管這一次 */ } };
store.read = store.read || [];

// 一「段」從一個 h1 或 h2 開始，到下一個為止
const stops = $$("main h1[id], main h2[id]");
const numbered = stops.filter((s) => s.dataset.n);
const railLinks = new Map($$(".rail a[href^='#']").map((a) => [a.getAttribute("href").slice(1), a]));
const head = $(".head");
const KEEP = "h1, h2, .meta, .part, .summary, .def, .defs, .cheat, .terms, .digest-note";
let current = null, currentSub = null, jumping = 0;
let opener = null, peekId = null, trail = [];

const titleOf = (h) => h.dataset.short || [...h.childNodes].filter((x) => !x.classList?.contains("num")).map((x) => x.textContent).join("").trim();
const stopOf = (el) => stops.filter((s) => s === el || (s.compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING)).pop() || stops[0];
function subsOf(stop) {
  const next = stops[stops.indexOf(stop) + 1];
  return $$("main h3[id]").filter((h) => (stop.compareDocumentPosition(h) & Node.DOCUMENT_POSITION_FOLLOWING)
    && (!next || (h.compareDocumentPosition(next) & Node.DOCUMENT_POSITION_FOLLOWING)));
}
function fmt(min) {
  const h = Math.floor(min / 60), m = min % 60;
  return (h ? ` ${h} 小時` : "") + (m || !h ? ` ${m} 分` : "");
}
function paintStatus() {
  const done = numbered.filter((s) => store.read.includes(s.id));
  const left = numbered.filter((s) => !store.read.includes(s.id)).reduce((t, s) => t + Number(s.dataset.min || 0), 0);
  const status = $(".status");
  if (status) status.innerHTML = `<b>讀了 ${done.length} / ${numbered.length} 段</b> <span>還剩約${fmt(left)}</span>`;
  stops.forEach((s) => {
    railLinks.get(s.id)?.parentElement.classList.toggle("read", store.read.includes(s.id));
    const cell = $(`.strip i[data-for="${s.id}"]`);
    if (cell) cell.className = s === current ? "now" : store.read.includes(s.id) ? "read" : "";
  });
}
function setCurrent(stop, sub) {
  if (stop !== current) {
    // 一路讀下來、從這段走進下一段，才算讀過；用目錄跳過去的不算
    if (current && !jumping && stops.indexOf(stop) === stops.indexOf(current) + 1 && !store.read.includes(current.id)) {
      store.read.push(current.id);
    }
    railLinks.forEach((a) => { a.removeAttribute("aria-current"); a.parentElement.classList.remove("now"); });
    current = stop;
    const a = railLinks.get(stop.id);
    if (a) {
      a.setAttribute("aria-current", "location");
      a.parentElement.classList.add("now");
      const rail = $(".rail"), top = $(".rail-top")?.offsetHeight || 0, r = a.getBoundingClientRect(), box = rail.getBoundingClientRect();
      if (r.top < box.top + top + 8 || r.bottom > box.bottom - 8) rail.scrollTop += r.top - box.top - top - 40;
    }
    if (stop !== stops[0]) store.last = stop.id;
    save();
    paintStatus();
  }
  if (sub !== currentSub) {
    if (currentSub) railLinks.get(currentSub.id)?.removeAttribute("aria-current");
    currentSub = sub;
    if (sub) railLinks.get(sub.id)?.setAttribute("aria-current", "location");
  }
  const n = stop.dataset.n;
  $(".crumb").innerHTML = `<b>${n ? `<span class="n">§${n}</span>` : ""}${titleOf(stop)}</b>`
    + (sub ? `<span class="sep">/</span><span class="h3">${sub.textContent.trim()}</span>` : "");
  $(".count").textContent = n ? `${n} / ${numbered.length}` : "";
}
function spy() {
  const top = head.getBoundingClientRect().bottom;
  // 讀的位置大約在畫面上面三分之一，標題過了這條線才算讀到那一段
  const line = top + innerHeight * 0.38;
  let stop = stops[0];
  for (const s of stops) {
    if (!s.getClientRects().length) continue;
    if (s.getBoundingClientRect().top <= line) stop = s; else break;
  }
  let sub = null;
  for (const h of subsOf(stop)) {
    if (!h.getClientRects().length) continue; // 只看重點時小節標題收起來了
    if (h.getBoundingClientRect().top <= line) sub = h; else break;
  }
  setCurrent(stop, sub);
  // 頁眉的線是「這一段讀到多少」；整份的進度在目錄上
  const next = stops.slice(stops.indexOf(stop) + 1).find((s) => s.getClientRects().length);
  const from = stop.getBoundingClientRect().top;
  const to = next ? next.getBoundingClientRect().top : document.documentElement.scrollHeight - scrollY;
  $(".head .bar").style.transform = `scaleX(${Math.max(0, Math.min(1, (top - from) / Math.max(1, to - from - (innerHeight - top))))})`;
  const max = document.documentElement.scrollHeight - innerHeight;
  if (max > 0 && scrollY >= max - 4 && !store.read.includes(stop.id)) { store.read.push(stop.id); save(); paintStatus(); }
}
let ticking = false;
addEventListener("scroll", () => {
  if (ticking) return;
  ticking = true;
  requestAnimationFrame(() => { ticking = false; spy(); });
}, { passive: true });
addEventListener("resize", spy);
function jumped() {
  jumping = Date.now();
  setTimeout(() => { if (Date.now() - jumping >= 700) jumping = 0; }, 800);
}
addEventListener("hashchange", jumped);

// 版面會變的動作（並排、只看重點）前後，讓讀者正在看的東西留在畫面上同一個位置
function keep(el, change) {
  const before = el?.getBoundingClientRect().top;
  change();
  if (el && el.isConnected && el.getClientRects().length) scrollBy(0, el.getBoundingClientRect().top - before);
}
function anchor() {
  const line = head.getBoundingClientRect().bottom + 8;
  return $$("main h2, main h3, main p, main li, main figure, main table, main details").find((x) => x.getClientRects().length && x.getBoundingClientRect().bottom > line) || current;
}

// 對照欄：把那一段原文複製到旁邊。id 是標題的 id，或 "panel"（查表）
function blockOf(target, whole) {
  const stop = stopOf(target);
  const start = whole ? stop : target;
  const nodes = [];
  // 標題包在自己的 <section> 裡時，那個 <section> 就是整段
  const until = start.tagName === "H3" ? "h2, h3" : "h1, h2, .part";
  for (let n = start.nextElementSibling; n && !n.matches(until) && !n.querySelector(":scope > h2, :scope > h1"); n = n.nextElementSibling) nodes.push(n);
  return { stop, nodes };
}
function openPeek(id, from) {
  const body = $(".peek-body");
  const split = document.body.classList.contains("split");
  let title, sub = "", hit = null;
  if (id === "panel") {
    const figs = $$("#panel figure");
    if (!figs.length) return false;
    body.textContent = "";
    const tabs = document.createElement("div");
    tabs.className = "tabs";
    figs.forEach((f, i) => {
      const b = document.createElement("button");
      b.type = "button"; b.className = "btn"; b.dataset.tab = i; b.textContent = f.dataset.tab;
      b.setAttribute("aria-pressed", String(i === 0));
      tabs.append(b);
      const c = f.cloneNode(true);
      c.hidden = i !== 0;
      body.append(c);
    });
    body.prepend(tabs);
    title = "查表";
    $(".peek-acts .go").hidden = true;
  } else {
    const target = document.getElementById(id);
    if (!target) return false;
    const whole = target.tagName !== "H3" || split; // 並排時右半邊是講義欄：放那一整段，再捲到被點的那一塊
    const { stop, nodes } = blockOf(target, whole);
    body.textContent = "";
    body.classList.toggle("course", !!target.closest("section.course")); // 重點框的名字跟著原來那一部
    nodes.forEach((n) => {
      const c = n.cloneNode(true);
      [c, ...c.querySelectorAll("[id]")].forEach((x) => { if (x.id) { x.dataset.was = x.id; x.removeAttribute("id"); } });
      c.classList.remove("open", "dg");
      c.querySelectorAll(".dg").forEach((x) => x.classList.remove("dg"));
      body.append(c);
    });
    const n = stop.dataset.n;
    if (whole) title = `<span class="num">${n ? `§${n}` : ""}</span>${titleOf(stop)}`;
    else {
      title = `<span class="num">${$(".num", target)?.textContent.trim() || ""}</span>${titleOf(target)}`;
      sub = `${n ? `§${n} ` : ""}${titleOf(stop)}`;
    }
    if (whole && target.tagName === "H3") hit = $(`[data-was="${id}"]`, body);
    $(".peek-acts .go").hidden = false;
    $(".peek-acts .go").href = `#${id}`;
  }
  peekId = id;
  $(".peek-head h2").innerHTML = title;
  $(".peek-head p").textContent = sub;
  opener = from || null;
  document.body.classList.add("peeking");
  body.scrollTop = 0;
  if (hit) {
    body.scrollTop = hit.getBoundingClientRect().top - body.getBoundingClientRect().top - 12;
    hit.classList.add("hit");
  }
  $(".peek-acts .back").hidden = !trail.length;
  $(".peek-head .close").focus({ preventScroll: true });
  return true;
}
function closePeek() {
  if (!document.body.classList.contains("peeking")) return;
  trail = [];
  keep(opener || anchor(), () => document.body.classList.remove("peeking", "split"));
  paintSplit();
  opener?.focus({ preventScroll: true });
  opener = null;
}
function paintSplit() {
  const on = document.body.classList.contains("split");
  const b = $(".peek-acts .split");
  b.setAttribute("aria-pressed", String(on));
  b.textContent = on ? "取消並排" : "並排";
}
function setSplit(on) {
  const from = opener;
  keep(from || anchor(), () => document.body.classList.toggle("split", on));
  paintSplit();
  if (peekId) openPeek(peekId, from);
}

// 只看重點：留下標題、重點、定義，其餘的區塊收起來；摺著的做法先打開，裡面的「這題記住」才看得到
function mark(el) {
  if (el.matches(KEEP)) return;
  if (el.querySelector(KEEP)) {
    if (el.tagName === "DETAILS" && !el.open) { el.dataset.wasClosed = "1"; el.open = true; }
    [...el.children].forEach(mark);
  } else el.classList.add("dg");
}
function setDigest(on) {
  const at = current || stops[0];
  document.body.classList.toggle("digest", on);
  if (on) $$(".page > section").forEach((pane) => [...pane.children].forEach(mark));
  else {
    $$(".dg").forEach((x) => x.classList.remove("dg"));
    $$("details[data-was-closed]").forEach((d) => { d.open = false; delete d.dataset.wasClosed; });
  }
  $$("[data-act='digest-on'], [data-act='digest-toggle']").forEach((b) => b.setAttribute("aria-pressed", String(on)));
  $$("[data-act='digest-off']").forEach((b) => b.setAttribute("aria-pressed", String(!on)));
  store.digest = on; save();
  at.scrollIntoView();
  spy();
}
function paintLang(f) {
  const b = $("button.lang", f);
  if (b) b.textContent = f.classList.contains("show-zh") ? "看原文" : "看中文";
}
function setLang(zh) {
  $$("figure").forEach((f) => { if ($("img.zh", f)) { f.classList.toggle("show-zh", zh); paintLang(f); } });
  $$("[data-act='lang-zh']").forEach((b) => b.setAttribute("aria-pressed", String(zh)));
  $$("[data-act='lang-en']").forEach((b) => b.setAttribute("aria-pressed", String(!zh)));
}
function setTheme(dark) {
  if (dark) document.documentElement.dataset.theme = "dark"; else delete document.documentElement.dataset.theme;
  try { localStorage.setItem("tutor-theme", dark ? "dark" : "light"); } catch { /* 存不了就只管這一次 */ }
  $$("[data-act='theme-dark']").forEach((b) => b.setAttribute("aria-pressed", String(dark)));
  $$("[data-act='theme-light']").forEach((b) => b.setAttribute("aria-pressed", String(!dark)));
}

document.addEventListener("click", (e) => {
  const ref = e.target.closest("a.ref");
  if (ref && !e.metaKey && !e.ctrlKey && !e.shiftKey && !e.altKey) {
    // 在對照欄裡按 §：記下現在這一段和捲到哪，之後可以按「返回」
    const inside = !!ref.closest(".peek");
    if (inside) trail.push({ id: peekId, top: $(".peek-body").scrollTop }); else trail = [];
    if (openPeek(decodeURIComponent(ref.getAttribute("href").slice(1)), inside ? opener : ref)) e.preventDefault();
    else if (inside) trail.pop();
    return;
  }
  if (e.target.closest(".peek-acts .go, .rail a, .resume a")) {
    jumped();
    closePeek();
    document.body.classList.remove("nav-open");
    return;
  }
  const btn = e.target.closest("[data-act]");
  const act = btn?.dataset.act;
  if (act === "peek-close" || act === "scrim") { closePeek(); document.body.classList.remove("nav-open"); return; }
  if (act === "nav") { document.body.classList.toggle("nav-open"); return; }
  if (act === "cheat" || act === "terms" || act === "panel") {
    trail = [];
    document.body.classList.remove("nav-open");
    openPeek(act, btn.closest(".head") ? btn : null);
    return;
  }
  if (act === "peek-back") {
    const prev = trail.pop();
    if (prev) { openPeek(prev.id, opener); $(".peek-body").scrollTop = prev.top; }
    return;
  }
  if (act === "split") { setSplit(!document.body.classList.contains("split")); return; }
  if (act === "digest-on" || act === "digest-off") { setDigest(act === "digest-on"); return; }
  if (act === "digest-toggle") { setDigest(!document.body.classList.contains("digest")); return; }
  if (act === "lang-zh" || act === "lang-en") { setLang(act === "lang-zh"); return; }
  if (act === "theme-light" || act === "theme-dark") { setTheme(act === "theme-dark"); return; }
  if (act === "print") {
    document.body.classList.add("print-cheat");
    addEventListener("afterprint", () => document.body.classList.remove("print-cheat"), { once: true });
    print();
    return;
  }
  if (act === "answers") {
    const all = $$("main details.answer");
    const open = !all.every((d) => d.open);
    all.forEach((d) => { d.open = open; });
    btn.textContent = open ? "收起全部做法" : "展開全部做法";
    return;
  }
  if (act === "reset") { store.read = []; save(); paintStatus(); return; }
  const tab = e.target.closest(".peek-body .tabs button");
  if (tab) {
    $$(".peek-body .tabs button").forEach((b) => b.setAttribute("aria-pressed", String(b === tab)));
    $$(".peek-body > figure").forEach((f, i) => { f.hidden = String(i) !== tab.dataset.tab; });
    return;
  }
  const fig = e.target.closest("figure");
  if (!fig) return;
  if (e.target.closest("button.lang")) { fig.classList.toggle("show-zh"); paintLang(fig); }
});
addEventListener("keydown", (e) => {
  if (e.key === "Escape") { closePeek(); document.body.classList.remove("nav-open"); }
});

// 圖說上的按鈕：翻譯過的圖加「看中文」
$$("figure").forEach((f) => {
  const cap = $("figcaption", f);
  if (!cap || !$("img.zh", f)) return;
  const b = document.createElement("button");
  b.type = "button"; b.className = "lang"; b.textContent = "看中文";
  cap.append(b);
});
// 上次讀到哪
if (!location.hash && store.last && $(".resume")) {
  const s = document.getElementById(store.last);
  if (s) {
    const a = $(".resume a");
    a.href = `#${s.id}`;
    a.textContent = `從 ${s.dataset.n ? `§${s.dataset.n} ` : ""}${titleOf(s)} 繼續`;
    $(".resume").hidden = false;
  }
}
if (document.documentElement.dataset.theme === "dark") setTheme(true);
if (store.digest) setDigest(true);
// 剛打開時瀏覽器會自己捲回上次的位置，那一下不算「讀過」
jumping = Date.now();
setTimeout(() => { jumping = 0; }, 1000);
paintStatus();
spy();
