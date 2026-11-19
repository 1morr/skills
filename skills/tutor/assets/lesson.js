// tutor 導讀頁的互動；build.py 會把它內嵌進每一頁。目錄、頁眉、課件欄、對照欄的 HTML 由 build.py 產生。
// 目錄和頁眉跟著捲動顯示現在在哪；一路讀下來的段落打勾，記在瀏覽器。
// 課件欄跟著正文：捲到寫了 data-at 的那一塊，課件欄就走到它講的那一頁。那一塊後面的小標籤按了也會回到那一頁；
// 課件欄的圖點了放大，圖說上的 § 跳到講它的段落。「跟著正文」關掉後課件欄只聽讀者的。
// 內文的 § 連結、頁眉的「速查卡」「名詞表」「查表」都在對照欄打開，正文不動；對照欄裡再跳可以按「返回」。跨段跳轉走瀏覽器的上一頁。
// 正文裡翻譯過的圖預設顯示原文，點圖換成翻譯、再點換回來；圖說上的按鈕做同一件事，鍵盤按得到。
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
const deckBody = $(".deck-body");
const marks = deckBody ? $$("main [data-at]") : [];
let follow = true, onMark = null, zoom = null, zoomFig = null;

// 標題的字：不含 § 編號和課件頁碼的小標籤
const textOf = (h) => [...h.childNodes].filter((x) => !x.matches?.(".num, .at")).map((x) => x.textContent).join("").trim();
const titleOf = (h) => h.dataset.short || textOf(h);
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
    + (sub ? `<span class="sep">/</span><span class="h3">${$(".num", sub)?.textContent || ""} ${textOf(sub)}</span>` : "");
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
  let mark = null;
  for (const m of marks) {
    if (!m.getClientRects().length) continue; // 摺起來的、只看重點時收掉的
    if (m.getBoundingClientRect().top <= line) mark = m; else break;
  }
  if (mark) setMark(mark);
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

// 版面會變的動作（對照欄、只看重點）前後，讓讀者正在看的東西留在畫面上同一個位置
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
  let title, sub = "";
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
    const whole = target.tagName !== "H3";
    const { stop, nodes } = blockOf(target, whole);
    body.textContent = "";
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
    $(".peek-acts .go").hidden = false;
    $(".peek-acts .go").href = `#${id}`;
  }
  peekId = id;
  $(".peek-head h2").innerHTML = title;
  $(".peek-head p").textContent = sub;
  opener = from || null;
  document.body.classList.add("peeking");
  body.scrollTop = 0;
  $(".peek-acts .back").hidden = !trail.length;
  $(".peek-head .close").focus({ preventScroll: true });
  return true;
}
function closePeek() {
  if (!document.body.classList.contains("peeking")) return;
  trail = [];
  keep(opener || anchor(), () => document.body.classList.remove("peeking"));
  opener?.focus({ preventScroll: true });
  opener = null;
}
// 課件欄。marks 是正文裡講某一頁課件的元素，data-at 是那幾張圖的 id（build.py 寫的）
function showSlide(id, smooth = true, flash = false) {
  const fig = document.getElementById(id);
  if (!fig || !fig.getClientRects().length) return; // 只看必記時，正文講到別的頁就留在原地
  const calm = matchMedia("(prefers-reduced-motion: reduce)").matches;
  deckBody.scrollTo({ top: fig.offsetTop - deckBody.offsetTop - 12, behavior: smooth && !calm ? "smooth" : "auto" });
  if (flash) {
    fig.classList.remove("hit");
    void fig.offsetWidth; // 重新觸發動畫
    fig.classList.add("hit");
  }
}
function setMark(m) {
  if (m === onMark) return;
  onMark?.classList.remove("at-on");
  onMark = m;
  m.classList.add("at-on");
  const ids = m.dataset.at.split(" ");
  $$(".deck figure.now").forEach((f) => f.classList.remove("now"));
  ids.forEach((id) => document.getElementById(id)?.classList.add("now"));
  if (follow) showSlide(ids[0]);
}
function setDeckKey(on) {
  document.body.classList.toggle("deck-key", on);
  $("[data-act='deck-key']")?.setAttribute("aria-pressed", String(on));
  if (onMark) showSlide(onMark.dataset.at.split(" ")[0], false);
}
// 窄畫面的課件欄是從下面拉上來的一塊；寬螢幕一直都在，這個開關沒有作用
function setDeck(open) {
  document.body.classList.toggle("deck-open", open);
  $("[data-act='deck']")?.setAttribute("aria-pressed", String(open));
  if (open && onMark) showSlide(onMark.dataset.at.split(" ")[0], false);
}
function paintZoom() {
  const zh = zoomFig.classList.contains("show-zh") && $("img.zh", zoomFig);
  $("img", zoom).src = (zh || $("img", zoomFig)).src;
  $("b", zoom).textContent = $("figcaption b", zoomFig).textContent;
  const lang = $("[data-zoom='lang']", zoom);
  lang.hidden = !$("img.zh", zoomFig);
  lang.textContent = zh ? "看原文" : "看中文";
}
function stepZoom(by) {
  const figs = $$(".deck figure").filter((f) => f.getClientRects().length);
  const next = figs[figs.indexOf(zoomFig) + by];
  if (!next) return;
  zoomFig = next;
  paintZoom();
  showSlide(next.id, false);
}
function openZoom(fig) {
  if (!zoom) {
    zoom = document.createElement("dialog");
    zoom.className = "zoom";
    zoom.innerHTML = '<div class="zoom-bar"><b></b><span><button type="button" class="btn" data-zoom="prev">上一頁</button>'
      + '<button type="button" class="btn" data-zoom="next">下一頁</button><button type="button" class="btn" data-zoom="lang"></button>'
      + '<button type="button" class="btn" data-zoom="close">關閉</button></span></div><img alt="">';
    document.body.append(zoom);
    zoom.addEventListener("click", (e) => {
      const act = e.target.closest("[data-zoom]")?.dataset.zoom;
      if (act === "close" || e.target === zoom) zoom.close(); // 點到圖外面的暗處
      else if (act === "lang") { zoomFig.classList.toggle("show-zh"); paintLang(zoomFig); paintZoom(); }
      else if (act) stepZoom(act === "next" ? 1 : -1);
    });
    zoom.addEventListener("keydown", (e) => {
      if (e.key === "ArrowRight" || e.key === "ArrowDown") { e.preventDefault(); stepZoom(1); }
      if (e.key === "ArrowLeft" || e.key === "ArrowUp") { e.preventDefault(); stepZoom(-1); }
    });
  }
  zoomFig = fig;
  paintZoom();
  if (!zoom.open) zoom.showModal();
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
  if (on) [...$(".page").children].forEach(mark);
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
  // 課件欄的圖點了是放大，換語言只靠按鈕
  if (b) b.textContent = (f.closest(".deck") ? "看" : "點圖看") + (f.classList.contains("show-zh") ? "原文" : "中文");
}
function setLang(zh) {
  $$("figure").forEach((f) => { if ($("img.zh", f)) { f.classList.toggle("show-zh", zh); paintLang(f); } });
  $$("[data-act='lang-zh']").forEach((b) => b.setAttribute("aria-pressed", String(zh)));
  $$("[data-act='lang-en']").forEach((b) => b.setAttribute("aria-pressed", String(!zh)));
}
// 選擇題：選錯的劃掉、可以再選；選對了整題結束，理由出現
function answer(li) {
  const quiz = li.closest(".quiz");
  if (quiz.classList.contains("done")) return;
  const ok = li.hasAttribute("data-ok");
  li.classList.add(ok ? "right" : "wrong");
  if (ok) quiz.classList.add("done");
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
  if (e.target.closest(".peek-acts .go, .rail a, .resume a, .deck a.to")) {
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
  if (act === "slide") {
    e.preventDefault(); // 標籤在 <summary> 裡時不要順便開合
    closePeek();
    setDeck(true);
    if (!document.getElementById(btn.dataset.id)?.classList.contains("key")) setDeckKey(false); // 讀者指名要看這一頁
    showSlide(btn.dataset.id, true, true);
    return;
  }
  if (act === "follow") {
    follow = !follow;
    btn.setAttribute("aria-pressed", String(follow));
    if (follow && onMark) showSlide(onMark.dataset.at.split(" ")[0]);
    return;
  }
  if (act === "deck-key") { setDeckKey(!document.body.classList.contains("deck-key")); return; }
  if (act === "deck") { setDeck(!document.body.classList.contains("deck-open")); return; }
  if (act === "deck-close") { setDeck(false); return; }
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
  const pick = e.target.closest(".quiz li");
  if (pick) { answer(pick); return; }
  const fig = e.target.closest("figure");
  if (!fig) return;
  if (fig.closest(".deck") && e.target.closest("img")) { openZoom(fig); return; }
  if ($("img.zh", fig) && e.target.closest("button.lang, img")) { fig.classList.toggle("show-zh"); paintLang(fig); }
});
addEventListener("keydown", (e) => {
  if ((e.key === "Enter" || e.key === " ") && e.target.matches?.(".quiz li")) { e.preventDefault(); answer(e.target); }
  if (e.key === "Escape") { closePeek(); document.body.classList.remove("nav-open"); }
});

// 選擇題：選項每次打開重排（寫了 data-fixed 的照原樣），鍵盤也按得到
$$(".quiz ul").forEach((ul) => {
  const items = [...ul.children];
  if (!ul.closest(".quiz").hasAttribute("data-fixed")) items.sort(() => Math.random() - 0.5).forEach((li) => ul.append(li));
  items.forEach((li) => { li.tabIndex = 0; li.setAttribute("role", "button"); });
});
// 圖說上的按鈕：翻譯過的圖可以換成中文
$$("figure").forEach((f) => {
  const cap = $("figcaption", f);
  if (!cap || !$("img.zh", f)) return;
  const b = document.createElement("button");
  b.type = "button"; b.className = "lang";
  cap.append(b);
  paintLang(f);
});
// 講某一頁課件的那一塊，後面加一個寫著頁碼的小標籤
marks.forEach((m) => {
  const host = m.tagName === "TR" ? m.lastElementChild : m;
  const ids = m.dataset.at.split(" ");
  const first = $("figcaption b", document.getElementById(ids[0]))?.textContent;
  if (!first || !host || /^(TABLE|TBODY|THEAD|UL|OL|DL|DETAILS|SECTION|FIGURE|IMG)$/.test(host.tagName)) return;
  const last = $("figcaption b", document.getElementById(ids.at(-1)))?.textContent || "";
  const sameDeck = first.split(" p.")[0] === last.split(" p.")[0];
  const b = document.createElement("button");
  b.type = "button"; b.className = "at"; b.dataset.act = "slide"; b.dataset.id = ids[0];
  b.textContent = ids.length === 1 ? first : sameDeck ? `${first}–${last.split(" p.")[1]}` : `${first}…`;
  b.title = "在課件欄看這一頁";
  host.append(b);
});
// 沒有重點框和定義框的頁，「只看重點」會只剩標題：把開關收起來
if (!$("main .summary, main .def")) {
  $$("[data-act^='digest']").forEach((b) => { (b.closest(".seg") || b).hidden = true; });
  store.digest = false;
}
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
