// tutor 講解頁的互動；build.py 會把它內嵌進每一頁。
// 點翻譯過的圖：在中文和原文之間切換。工具列按鈕：全部圖片切換、全部做法展開或收起。
// 點頁內連結（§N、數字從哪來的圖）會讓另一欄跳過去：先記下兩欄的捲動位置，右下角出現「回到剛才」。
// 每欄工具列顯示現在讀到哪一段；圖說上的「放大」解除圖片的高度上限；「查表」打開統計表面板；「列印速查卡」只印那張卡。
const back = document.createElement("button");
back.type = "button";
back.className = "back";
back.hidden = true;
back.textContent = "回到剛才";
document.body.append(back);
let saved = null;
const panes = () => [...document.querySelectorAll("section.course, section.problems")];
document.addEventListener("click", (e) => {
  const a = e.target.closest('a[href^="#"]');
  if (!a || !document.getElementById(decodeURIComponent(a.getAttribute("href").slice(1)))) return;
  saved = { panes: panes().map((p) => p.scrollTop), y: window.scrollY };
  back.hidden = false;
});
back.addEventListener("click", () => {
  if (!saved) return;
  history.replaceState(null, "", location.pathname + location.search); // 拿掉 #，目標的強調色也跟著消失
  panes().forEach((p, i) => { p.scrollTop = saved.panes[i]; });
  window.scrollTo(0, saved.y);
  saved = null;
  back.hidden = true;
});
document.addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-act]");
  if (btn) {
    if (btn.dataset.act === "lang") {
      const en = document.body.classList.toggle("all-en");
      document.querySelectorAll("figure").forEach((f) => {
        if (f.querySelector("img.zh")) f.classList.toggle("show-en", en);
      });
      btn.textContent = en ? "圖片：原文（點這裡全部換成中文）" : "圖片：中文（點這裡全部換成原文）";
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
    }
    return;
  }
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

// 圖說加上「放大」（查表面板和整頁圖本來就是全尺寸）
document.querySelectorAll("figure:not(.page) > figcaption").forEach((cap) => {
  if (cap.closest("#panel")) return;
  const b = document.createElement("button");
  b.type = "button";
  b.className = "zoom-btn";
  b.textContent = "放大";
  cap.append(b);
});
// 工具列上的「現在讀到哪一段」：這一欄裡最後一個捲過工具列的 h2
function here() {
  panes().forEach((pane) => {
    const label = pane.querySelector(".bar .here");
    if (!label) return;
    const line = pane.querySelector(".bar").getBoundingClientRect().bottom + 8;
    let current = null;
    pane.querySelectorAll("h2").forEach((h) => { if (h.getBoundingClientRect().top <= line) current = h; });
    label.textContent = current ? current.textContent.trim() : "目錄";
  });
}
let ticking = false;
function onScroll() {
  if (ticking) return;
  ticking = true;
  requestAnimationFrame(() => { ticking = false; here(); });
}
panes().forEach((p) => p.addEventListener("scroll", onScroll, { passive: true }));
window.addEventListener("scroll", onScroll, { passive: true });
window.addEventListener("resize", onScroll);
here();
