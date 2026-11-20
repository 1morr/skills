// tutor 導讀頁的互動；build.py 會把它內嵌進每一頁。目錄、頁眉、課件欄、對照欄的 HTML 由 build.py 產生。
// 目錄和頁眉跟著捲動顯示現在在哪；一路讀下來的段落打勾，記在瀏覽器。
// 課件欄跟著正文：寫了 data-at 的那一塊在講哪一頁，課件欄就停在那一頁、把它框起來；下一塊快捲到時，
// 課件欄照正文捲動的距離滑到下一頁（隔得遠的等捲到了再一次滑過去）。那一塊後面的小標籤按了也會回到那一頁；
// 課件欄的圖點了放大，圖說上的 § 跳到講它的段落。「跟著正文」關掉後課件欄只聽讀者的。
// 內文的 § 連結、頁眉的「速查卡」「名詞表」「查表」都在對照欄打開，正文不動；對照欄裡再跳可以按「返回」。跨段跳轉走瀏覽器的上一頁。
// 正文裡翻譯過的圖預設顯示原文，點圖換成翻譯、再點換回來；圖說上的按鈕做同一件事，鍵盤按得到。
// 「只看重點」只留標題、重點框、定義、表格、常見錯誤、講必記那一頁課件的那一塊。深淺色由讀者切換，和練習頁共用 tutor-theme。
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
const KEEP = "h1, h2, h3, .meta, .part, .summary, .def, .defs, .trap, table, [data-key], .cheat, .terms, .digest-note";
let current = null, currentSub = null, jumping = 0;
let opener = null, peekId = null, trail = [];
const deckBody = $(".deck-body");
const marks = deckBody ? $$("main [data-at]") : [];
let follow = true, onMark = null, zoom = null, zoomFig = null;
let goal = 0, followed = null, chasing = 0, chased = 0;

// 標題的字：不含 § 編號和課件頁碼的小標籤
const textOf = (h) => [...h.childNodes].filter((x) => !x.matches?.(".num, .at")).map((x) => x.textContent).join("").trim();
const titleOf = (h) => h.dataset.short || textOf(h);
const stopOf = (el) => stops.filter((s) => s === el || (s.compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING)).pop() || stops[0];
function subsOf(stop) {
  const next = stops[stops.indexOf(stop) + 1];
  return $$("main h3[id]").filter((h) => (stop.compareDocumentPosition(h) & Node.DOCUMENT_POSITION_FOLLOWING)
    && (!next || (h.compareDocumentPosition(next) & Node.DOCUMENT_POSITION_FOLLOWING)));
}
function paintStatus() {
  const done = numbered.filter((s) => store.read.includes(s.id));
  const status = $(".status");
  if (status) status.innerHTML = `<b>讀了 ${done.length} / ${numbered.length} 段</b>`;
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
    if (!h.getClientRects().length) continue; // 在摺起來的區塊裡
    if (h.getBoundingClientRect().top <= line) sub = h; else break;
  }
  setCurrent(stop, sub);
  let mark = null, markTop = 0, after = null, afterTop = 0;
  for (const m of marks) {
    if (!m.getClientRects().length) continue; // 摺起來的、只看重點時收掉的
    const y = m.getBoundingClientRect().top;
    if (y <= line) { mark = m; markTop = y; } else { after = m; afterTop = y; break; }
  }
  if (mark) setMark(mark);
  if (mark) followDeck(deckAt(mark, line - markTop, after, afterTop - markTop));
  else if (after) followDeck(deckAt(null, GLIDE() - (afterTop - line), after, GLIDE()));
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
const slideTop = (fig) => fig.offsetTop - deckBody.offsetTop - 12;
const GLIDE = () => innerHeight * 0.3; // 下一塊離閱讀線這麼近時，課件欄開始滑向它的那一頁
// 一塊講連續的幾頁時，[第一頁, 最後一頁]；用「;」列的別份課件不算進來
function runOf(m) {
  const figs = m.dataset.at.split(" ").map((id) => document.getElementById(id));
  let last = figs[0];
  for (const f of figs.slice(1)) { if (f && last.nextElementSibling === f) last = f; else break; }
  return [figs[0], last];
}
// 課件欄該捲到哪：into 是閱讀線進了 mark 這一塊多遠，span 是這一塊到下一塊 after 的距離。
// 停在這一塊的第一頁。下一塊的頁就在附近時，最後 GLIDE 那一段距離照正文捲動的距離滑過去；
// 隔得遠就留在原地，等閱讀線到了下一塊再一次滑過去：中間那些頁和正文無關，不停在上面
function deckAt(mark, into, after, span) {
  const from = mark ? slideTop(runOf(mark)[0]) : 0;
  if (!after) return from;
  const next = slideTop(runOf(after)[0]);
  const near = Math.abs(next - (mark ? slideTop(runOf(mark)[1]) : 0)) <= deckBody.clientHeight * 1.5;
  const hold = span - Math.min(span * 0.6, GLIDE()); // 再短的一塊，它的那一頁也先停一下
  if (!near || into <= hold) return from;
  return from + (next - from) * ((into - hold) / (span - hold));
}
// 朝 goal 追過去，越近越慢：正文一格一格捲，課件欄是連續地滑
function chase(now) {
  const gap = goal - deckBody.scrollTop;
  const k = 1 - Math.exp(-(now - chased) / 70);
  chased = now;
  if (Math.abs(gap) < 1.5) { deckBody.scrollTop = goal; chasing = 0; return; }
  deckBody.scrollTop += Math.sign(gap) * Math.max(1, Math.abs(gap) * k);
  chasing = requestAnimationFrame(chase);
}
function aim(top, smooth = true) {
  goal = Math.max(0, Math.min(deckBody.scrollHeight - deckBody.clientHeight, Math.round(top)));
  cancelAnimationFrame(chasing);
  chasing = 0;
  if (!smooth || matchMedia("(prefers-reduced-motion: reduce)").matches) { deckBody.scrollTop = goal; return; }
  chased = performance.now();
  chasing = requestAnimationFrame(chase);
}
// 正文講到的位置變了才動課件欄：停在同一頁的時候，讀者自己把課件欄捲去看別頁，就留在他看的地方
function followDeck(at) {
  at = Math.round(at);
  if (at === followed) return;
  const first = followed === null;
  followed = at;
  if (follow) aim(at, !first);
}
function showSlide(id, smooth = true, flash = false) {
  const fig = document.getElementById(id);
  if (!fig) return;
  aim(slideTop(fig), smooth);
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
  $$(".deck figure.now").forEach((f) => f.classList.remove("now"));
  m.dataset.at.split(" ").forEach((id) => document.getElementById(id)?.classList.add("now"));
}
// 窄畫面的課件欄是從下面拉上來的一塊；寬螢幕一直都在，這個開關沒有作用
function setDeck(open) {
  document.body.classList.toggle("deck-open", open);
  $("[data-act='deck']")?.setAttribute("aria-pressed", String(open));
  if (open && followed !== null) aim(followed, false);
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

// 只看重點：留下標題、重點框、定義、表格、常見錯誤、講必記那一頁課件的那一塊，其餘的區塊收起來；摺著的做法先打開，裡面的「這題記住」才看得到
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
    showSlide(btn.dataset.id, true, true);
    return;
  }
  if (act === "follow") {
    follow = !follow;
    btn.setAttribute("aria-pressed", String(follow));
    if (follow && followed !== null) aim(followed);
    return;
  }
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
  if (m.hasAttribute("data-key")) { b.classList.add("key"); b.textContent += " 必記"; }
  host.append(b);
});
// 沒有重點框、定義框、表格、常見錯誤、必記的頁，「只看重點」會只剩標題：把開關收起來
if (!$("main .summary, main .def, main .trap, main table, main [data-key]")) {
  $$("[data-act^='digest']").forEach((b) => { (b.closest(".seg") || b).hidden = true; });
  store.digest = false;
}
// 讀者自己動手捲課件欄時，正在滑的那一下讓給他
["wheel", "touchstart", "pointerdown"].forEach((type) => deckBody?.addEventListener(type, () => {
  cancelAnimationFrame(chasing);
  chasing = 0;
}, { passive: true }));
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
