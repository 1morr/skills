// tutor 導讀頁的互動；build.py 會把它內嵌進每一頁。
// 點翻譯過的圖：在中文和原文之間切換。書眉的按鈕：全部圖片切換、全部做法展開或收起、查表、列印速查卡、遮字板。
// 爪標：每欄的每個 h2 一格，立在書口（窄螢幕躺在畫面底下）；現在讀到的那節實心，上次讀到的那節有紅色摺角。
// 點頁內連結（§N、數字從哪來的圖）會讓另一欄跳過去；跳之前把兩欄的捲動位置記在這筆瀏覽紀錄上，按瀏覽器的上一頁就回到原位。
// 遮字板：速查卡題型表中間那欄是答案，預設打開；按書眉的「遮住答案」全部遮住，再點一格打開一格。狀態記在這台瀏覽器。
const panes = () => [...document.querySelectorAll("section.course, section.problems")];
const store = {
  key: "tutor:" + location.pathname,
  read() { try { return JSON.parse(localStorage.getItem(this.key)) || {}; } catch (e) { return {}; } },
  write(patch) { try { localStorage.setItem(this.key, JSON.stringify(Object.assign(this.read(), patch))); } catch (e) { /* 私密瀏覽：不記 */ } },
};
const last = store.read();

// 上一頁回到原位：瀏覽器只會還原整頁的捲動，兩欄各自的位置要自己記
history.scrollRestoration = "manual";
const position = () => ({ panes: panes().map((p) => p.scrollTop), y: window.scrollY });
function restore(state) {
  if (state && state.panes) {
    panes().forEach((p, i) => { p.scrollTop = state.panes[i] || 0; });
    window.scrollTo(0, state.y || 0);
  } else if (location.hash.length > 1) {
    const target = document.getElementById(decodeURIComponent(location.hash.slice(1)));
    if (target) target.scrollIntoView();
  }
}
document.addEventListener("click", (e) => {
  const a = e.target.closest('a[href^="#"]');
  if (!a || !document.getElementById(decodeURIComponent(a.getAttribute("href").slice(1)))) return;
  history.replaceState(position(), "");
});
window.addEventListener("popstate", (e) => requestAnimationFrame(() => restore(e.state)));

document.addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-act]");
  if (btn) {
    if (btn.dataset.act === "lang") {
      const en = document.body.classList.toggle("all-en");
      document.querySelectorAll("figure").forEach((f) => {
        if (f.querySelector("img.zh")) f.classList.toggle("show-en", en);
      });
      btn.textContent = en ? "圖片：原文" : "圖片：中文";
    } else if (btn.dataset.act === "toc") {
      const pane = btn.closest("section");
      const toc = pane.querySelector("details.toc");
      if (toc) toc.open = true;
      (getComputedStyle(pane).overflowY === "auto" ? pane : document.scrollingElement).scrollTo({ top: toc ? toc.offsetTop - 60 : 0 });
    } else if (btn.dataset.act === "panel") {
      document.getElementById("panel").classList.toggle("open");
    } else if (btn.dataset.act === "print") {
      document.body.classList.add("print-cheat");
      window.addEventListener("afterprint", () => document.body.classList.remove("print-cheat"), { once: true });
      window.print();
    } else if (btn.dataset.act === "answers") {
      const all = [...document.querySelectorAll("details.answer")];
      const open = !all.every((d) => d.open);
      all.forEach((d) => { d.open = open; });
      btn.textContent = open ? "收起全部做法" : "展開全部做法";
    } else if (btn.dataset.act === "cover") {
      setCover(btn.getAttribute("aria-pressed") !== "true");
    }
    return;
  }
  const cell = e.target.closest("td.covered");
  if (cell) { lift(cell); saveCover(); return; }
  const zoom = e.target.closest(".zoom-btn");
  if (zoom) {
    const on = zoom.closest("figure").classList.toggle("zoom");
    zoom.textContent = on ? "縮小" : "放大";
    return;
  }
  const tab = e.target.closest("#panel header button");
  if (tab) {
    const panel = document.getElementById("panel");
    if (tab.classList.contains("close")) { panel.classList.remove("open"); return; }
    panel.querySelectorAll("header [data-tab]").forEach((x) => x.setAttribute("aria-pressed", x === tab ? "true" : "false"));
    panel.querySelectorAll(".body figure").forEach((f) => { f.hidden = f.dataset.tab !== tab.dataset.tab; });
    return;
  }
  const fig = e.target.closest("figure");
  if (fig && fig.querySelector("img.zh") && !e.target.closest("a")) fig.classList.toggle("show-en");
});

// 「這頁重點」每一列開頭的「學到：」「考法：」排成粗體標籤
document.querySelectorAll(".summary li").forEach((li) => {
  const first = li.firstChild;
  const m = first && first.nodeType === 3 && first.nodeValue.match(/^([^：，。]{1,5})：/);
  if (!m) return;
  const b = document.createElement("b");
  b.textContent = m[1];
  first.nodeValue = first.nodeValue.slice(m[0].length);
  li.prepend(b);
});

// 遮字板
const answers = [...document.querySelectorAll("table.types tbody td:nth-child(2)")];
const coverBtn = document.createElement("button");
const coverNote = document.createElement("p");
function lift(cell) {
  cell.classList.remove("covered");
  cell.classList.add("lifting");
  cell.addEventListener("animationend", () => cell.classList.remove("lifting"), { once: true });
  setTimeout(() => cell.classList.remove("lifting"), 500);
  cell.removeAttribute("tabindex");
  syncCover();
}
function syncCover() {
  const left = answers.filter((c) => c.classList.contains("covered")).length;
  coverBtn.setAttribute("aria-pressed", left > 0 ? "true" : "false");
  coverBtn.textContent = left > 0 ? "答案：已遮住" : "遮住答案";
  coverNote.textContent = left > 0
    ? `中間那欄的答案遮住了。先自己說一次，再點紅色的格子打開；還剩 ${left} 格。`
    : "想考自己：按上面的「遮住答案」，中間那欄會遮起來，點一格打開一格。";
}
function saveCover() { store.write({ covered: answers.map((c) => c.classList.contains("covered")) }); }
function setCover(on) {
  answers.forEach((c) => {
    c.classList.toggle("covered", on);
    if (on) c.tabIndex = 0; else c.removeAttribute("tabindex");
  });
  syncCover();
  saveCover();
}
if (answers.length) {
  answers.forEach((c, i) => {
    const ink = document.createElement("span");
    ink.className = "ink";
    ink.append(...c.childNodes);
    c.append(ink);
    if (last.covered && last.covered[i]) { c.classList.add("covered"); c.tabIndex = 0; }
  });
  coverBtn.type = "button";
  coverBtn.dataset.act = "cover";
  const bar = document.querySelector("section.problems > .bar");
  if (bar) bar.querySelector(".here").after(coverBtn);
  coverNote.className = "cover-note";
  answers[0].closest("table").after(coverNote);
  syncCover();
  document.addEventListener("keydown", (e) => {
    if ((e.key === "Enter" || e.key === " ") && e.target.matches && e.target.matches("td.covered")) { e.preventDefault(); lift(e.target); saveCover(); }
  });
}

// 圖說加上「放大」（查表面板和整頁圖本來就是全尺寸）
document.querySelectorAll("figure:not(.page) > figcaption").forEach((cap) => {
  if (cap.closest("#panel")) return;
  const b = document.createElement("button");
  b.type = "button";
  b.className = "zoom-btn";
  b.textContent = "放大";
  cap.append(b);
});

// 爪標
const strips = panes().map((pane, i) => {
  const name = pane.classList.contains("course") ? "course" : "problems";
  const nav = document.createElement("nav");
  nav.className = "tabs " + name;
  nav.setAttribute("aria-label", name === "course" ? "課件的節" : "題目的節");
  pane.querySelectorAll("h2[id]").forEach((h, j) => {
    const a = document.createElement("a");
    a.href = "#" + h.id;
    const num = h.querySelector(".num");
    a.textContent = num ? num.textContent.trim() : h.textContent.trim().slice(0, 2);
    a.title = h.textContent.trim();
    if (j === 0 && i > 0) a.className = "first";
    if (last.at && last.at[name] === h.id) a.classList.add("mark");
    nav.append(a);
  });
  return nav;
});
// 窄螢幕只有一條：題目的格子接在課件後面
if (strips.length === 2) {
  const all = strips[0].cloneNode(true);
  all.className = "tabs all";
  all.append(...[...strips[1].children].map((a) => a.cloneNode(true)));
  document.body.append(all);
}
strips.forEach((nav) => document.body.append(nav));

// 書眉上的「現在讀到哪一節」和爪標的實心格：這一欄裡最後一個捲過書眉的 h2
let moved = false;
function here() {
  const at = {};
  panes().forEach((pane) => {
    const bar = pane.querySelector(".bar");
    if (!bar) return;
    const line = bar.getBoundingClientRect().bottom + 28; // 跳到某節時，標題停在書眉下面 1rem 多一點
    let current = null;
    pane.querySelectorAll("h2").forEach((h) => { if (h.getBoundingClientRect().top <= line) current = h; });
    const label = bar.querySelector(".here");
    const top = pane.classList.contains("course") ? document.title : (pane.querySelector(".cheat") ? "速查卡" : "目錄");
    if (label) label.textContent = current ? current.textContent.trim() : top;
    const name = pane.classList.contains("course") ? "course" : "problems";
    if (current && current.id) at[name] = current.id;
  });
  const ids = Object.values(at);
  // 窄螢幕兩欄接成一頁：只有畫面上這一欄的節算現在
  const single = panes().every((p) => getComputedStyle(p).overflowY !== "auto");
  const now = single ? [at.problems || at.course] : ids;
  document.querySelectorAll(".tabs a").forEach((a) => {
    const on = now.includes(a.hash.slice(1));
    if (on) a.setAttribute("aria-current", "true"); else a.removeAttribute("aria-current");
    const strip = on && a.closest(".all");
    if (strip && strip.offsetParent !== null) strip.scrollLeft = a.offsetLeft - strip.clientWidth / 2 + a.offsetWidth / 2;
  });
  if (moved) store.write({ at });
}
let ticking = false;
function onScroll() {
  moved = true;
  if (ticking) return;
  ticking = true;
  requestAnimationFrame(() => { ticking = false; here(); });
}
panes().forEach((p) => p.addEventListener("scroll", onScroll, { passive: true }));
window.addEventListener("scroll", onScroll, { passive: true });
window.addEventListener("resize", () => requestAnimationFrame(here));
here();
