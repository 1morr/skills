/* build.py 內嵌進組好的頁，放在 Mermaid 和 Panzoom 之後：先畫每張 <pre class="mermaid">
   （深淺色跟著 prefers-color-scheme），再讓畫好的圖可以拖動平移、⌘/Ctrl＋滾輪或觸控板捏合縮放
   （單純滾輪照常捲頁）、雙擊重設；右上角的按鈕放大、縮小、重設、放大檢視（鋪滿視窗，Esc 或再按一次關閉）。 */
(async () => {
  const dark = matchMedia("(prefers-color-scheme: dark)").matches;
  mermaid.initialize({ startOnLoad: false, theme: dark ? "dark" : "neutral" });
  // 有一張語法錯誤時照樣畫其他張；錯的那張畫成 Mermaid 的錯誤圖示
  await mermaid.run({ querySelector: "pre.mermaid", suppressErrors: true });

  const zh = /^zh/i.test(document.documentElement.lang || navigator.language || "");
  const L = zh
    ? { in: "放大", out: "縮小", reset: "重設", open: "放大檢視", close: "關閉（Esc）" }
    : { in: "Zoom in", out: "Zoom out", reset: "Reset", open: "Expand", close: "Close (Esc)" };
  let opened = null;

  function setOpen(pre, on) {
    const { pz, toggle } = pre.dz;
    pre.classList.toggle("dz-open", on);
    document.documentElement.classList.toggle("dz-lock", on);
    toggle.textContent = on ? "✕" : "⤢";
    toggle.title = on ? L.close : L.open;
    toggle.setAttribute("aria-label", toggle.title);
    opened = on ? pre : null;
    pz.reset();
  }

  document.querySelectorAll("pre.mermaid").forEach((pre) => {
    const svg = pre.querySelector(":scope > svg");
    if (!svg) return;
    const stage = document.createElement("span");
    stage.className = "dz-stage";
    pre.insertBefore(stage, svg);
    stage.append(svg);
    // canvas：在整個框裡按住都能拖，不必剛好按在圖上
    const pz = Panzoom(stage, { canvas: true, cursor: "grab", minScale: 0.3, maxScale: 10 });
    pre.addEventListener("wheel", (e) => {
      if (!e.ctrlKey && !e.metaKey) return; // 觸控板捏合在 Chromium 送的是 ctrlKey 的 wheel
      e.preventDefault();
      const d = Math.max(-50, Math.min(50, e.deltaY));
      pz.zoomToPoint(pz.getScale() * Math.exp(-d * 0.006), e);
    }, { passive: false });
    pre.addEventListener("dblclick", (e) => {
      if (!e.target.closest(".dz-bar")) pz.reset();
    });

    const bar = document.createElement("span");
    bar.className = "dz-bar";
    const button = (glyph, label, onClick) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "panzoom-exclude"; // 不讓按鈕上的按下變成拖動
      b.textContent = glyph;
      b.title = label;
      b.setAttribute("aria-label", label);
      b.addEventListener("click", onClick);
      bar.append(b);
      return b;
    };
    button("+", L.in, () => pz.zoomIn());
    button("−", L.out, () => pz.zoomOut());
    button("↺", L.reset, () => pz.reset());
    const toggle = button("⤢", L.open, () => {
      if (opened && opened !== pre) setOpen(opened, false);
      setOpen(pre, opened !== pre);
    });
    pre.append(bar);
    pre.dz = { pz, toggle };
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && opened) setOpen(opened, false);
  });
})();
