// 練習頁：每題一張畫布（手寫、打字、橡皮擦、復原、自動儲存、複製成圖片給 Claude 批改）、填答格在頁面上對答案、書眉寫現在第幾題、查表面板、點圖切換中英文。
(function () {
  "use strict";
  const KEY = document.body.dataset.key;
  const TITLE = document.body.dataset.title || document.title;
  const MOCK = document.body.dataset.mode === "mock";  // 模擬卷：交卷才對答案
  const mockChecks = [];  // 交卷時把每個填答格對一次
  const COLORS = { black: "#1d2433", red: "#c62828", blue: "#1f5fd1" };
  const FAMILY = getComputedStyle(document.body).fontFamily;
  const FONT = 18;  // 打字的字級和行高，單位是畫布座標
  const LINE = 26;
  const CJK = "㐀-鿿豈-﫿　-〿＀-￯";
  const TOKEN = new RegExp("[" + CJK + "]|[^\\s" + CJK + "]+\\s*|\\s+", "g");
  const measure = document.createElement("canvas").getContext("2d");
  let lastPad = null;
  const fillLines = {};  // 題目代號 → 回傳這題每個填答格的結果（一格一行字）
  const modelLines = {};  // 題目代號 → 回傳這題對範本答案的自評（一行字）

  // 題目導覽鈕的狀態：填答格全對是 ok、有答錯是 no、對過範本答案是 graded
  function mark(section) {
    const link = document.querySelector('nav.jump a[href="#' + section.id + '"]');
    if (!link) return;
    const fills = Array.from(section.querySelectorAll(".fill"));
    link.classList.toggle("ok", fills.length > 0 && fills.every(function (f) { return f.classList.contains("ok"); }));
    link.classList.toggle("no", fills.some(function (f) { return f.classList.contains("no"); }));
    link.classList.toggle("graded", section.classList.contains("graded"));
  }

  // 填答格：全形轉半形、不分大小寫、不管空白；兩邊都是數字就比數值（data-tol 是容許誤差）
  function norm(s) {
    return s.normalize("NFKC").toLowerCase().replace(/\s+/g, "").replace(/[−–]/g, "-");
  }
  function matches(given, answers, tol) {
    const g = norm(given);
    return answers.some(function (ans) {
      const a = norm(ans);
      if (g === a) return true;
      const x = Number(g), y = Number(a);
      return g !== "" && a !== "" && isFinite(x) && isFinite(y) && Math.abs(x - y) <= tol + 1e-9;
    });
  }
  function round(r) {
    if (!r.tries.length) return "還沒做";
    const wrong = r.ok ? r.tries.slice(0, -1) : r.tries;
    return (r.ok ? "第 " + r.tries.length + " 次答對" : "錯 " + r.tries.length + " 次") +
      (wrong.length ? "，答錯過：" + wrong.join("、") : "");
  }
  // 重做不丟掉之前的紀錄：第一次錯在哪才是 Claude 要記的
  function describe(f) {
    const past = (f.rounds || []).map(round);
    return past.length ? "重做第 " + past.length + " 次：" + round(f) + "；之前：" + past.join("；") : round(f);
  }
  // 基本功錯兩次就公布答案和原因；整題的填答格只說對不對，步驟要貼給 Claude 批改
  function makeFills(section) {
    const id = section.dataset.id;
    const drill = section.classList.contains("drill");
    const store = KEY + ":" + id + ":fill";
    const els = Array.from(section.querySelectorAll(".fill"));
    const saved = JSON.parse(localStorage.getItem(store) || "[]");
    const state = els.map(function (_, i) { return saved[i] || { tries: [], ok: false }; });
    fillLines[id] = function () {
      return els.map(function (el, i) { return el.dataset.label + " " + describe(state[i]); });
    };
    els.forEach(function (el, i) {
      const f = state[i];
      const answers = el.dataset.answer.split("|").filter(function (a) { return a.trim(); });
      const tol = parseFloat(el.dataset.tol) || 0;
      el.dataset.label = el.textContent.trim();
      const input = document.createElement("input");
      input.type = "text";
      input.autocomplete = "off";
      input.setAttribute("aria-label", el.dataset.label || "答案");
      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = "對答案";
      const out = document.createElement("span");
      out.className = "result";
      out.setAttribute("aria-live", "polite");
      const redo = document.createElement("button");
      redo.type = "button";
      redo.textContent = "再做一次";
      el.append(" ", input, " ", btn, " ", redo, out);
      if (MOCK) {
        btn.hidden = redo.hidden = true;
        input.value = f.draft || "";
        input.addEventListener("input", function () {
          f.draft = input.value;
          localStorage.setItem(store, JSON.stringify(state));
        });
        mockChecks.push(function () {
          const v = (f.draft || "").trim();
          f.tries = v ? [v] : [];
          f.ok = !!v && matches(v, answers, tol);
          localStorage.setItem(store, JSON.stringify(state));
          input.disabled = true;
          el.classList.toggle("ok", f.ok);
          el.classList.toggle("no", !f.ok);
          out.textContent = f.ok ? "對。" : (v ? "不對" : "沒填") + "，答案是 " + answers[0].trim() + "。";
          mark(section);
        });
        return;
      }
      function show() {
        const why = el.dataset.why ? " " + el.dataset.why : "";
        const done = f.ok || (drill && f.tries.length >= 2);
        input.disabled = btn.disabled = done;
        redo.hidden = !done;
        input.value = f.tries.length ? f.tries[f.tries.length - 1] : "";
        el.classList.toggle("ok", f.ok);
        el.classList.toggle("no", !f.ok && f.tries.length > 0);
        if (f.ok) out.textContent = "對。" + why;
        else if (!f.tries.length) out.textContent = "";
        else if (done) out.textContent = "答案是 " + answers[0].trim() + "。" + why;
        else if (drill || f.tries.length < 2) out.textContent = "不對，再想一次。";
        else out.textContent = "還是不對：寫完打開下面的範本答案對步驟，或按「複製給 Claude」貼到對話。";
        mark(section);
      }
      function check() {
        const v = input.value.trim();
        if (!v || input.disabled) return;
        f.tries.push(v);
        f.ok = matches(v, answers, tol);
        localStorage.setItem(store, JSON.stringify(state));
        show();
      }
      btn.addEventListener("click", check);
      redo.addEventListener("click", function () {
        f.rounds = (f.rounds || []).concat({ tries: f.tries, ok: f.ok });
        f.tries = [];
        f.ok = false;
        localStorage.setItem(store, JSON.stringify(state));
        show();
        input.focus();
      });
      input.addEventListener("keydown", function (e) { if (e.key === "Enter") check(); });
      show();
    });
  }

  // 範本答案：讀者寫完才打開；給分點變成勾選，自評分數存起來，也進「複製填答結果」
  function makeModel(section) {
    const box = section.querySelector("details.model");
    if (!box) return;
    const id = section.dataset.id;
    const store = KEY + ":" + id + ":model";
    const st = JSON.parse(localStorage.getItem(store) || "null") || { seen: false, got: [] };
    const items = Array.from(box.querySelectorAll(".rubric li"));
    const total = items.reduce(function (n, li) { return n + (+li.dataset.marks || 0); }, 0);
    const score = document.createElement("p");
    score.className = "score";
    score.setAttribute("aria-live", "polite");
    box.append(score);
    function earned() {
      return items.reduce(function (n, li, i) { return n + (st.got[i] ? +li.dataset.marks : 0); }, 0);
    }
    function show() {
      score.textContent = "自評：" + earned() + " / " + total + " 分";
      section.classList.toggle("graded", st.seen);
      mark(section);
    }
    items.forEach(function (li, i) {
      const label = document.createElement("label");
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.checked = !!st.got[i];
      const marks = document.createElement("span");
      marks.className = "marks";
      marks.textContent = "[" + li.dataset.marks + " 分]";
      li.dataset.label = li.textContent.trim();
      label.append(cb, " ");
      while (li.firstChild) label.append(li.firstChild);
      label.append(" ", marks);
      li.append(label);
      cb.addEventListener("change", function () {
        st.got[i] = cb.checked;
        localStorage.setItem(store, JSON.stringify(st));
        show();
      });
    });
    box.addEventListener("toggle", function () {
      if (!box.open || st.seen) return;
      st.seen = true;
      localStorage.setItem(store, JSON.stringify(st));
      show();
    });
    show();
    modelLines[id] = function () {
      if (!st.seen) return ["範本答案還沒打開"];
      const lost = items.filter(function (_, i) { return !st.got[i]; }).map(function (li) { return li.dataset.label; });
      return ["自評 " + earned() + "/" + total + " 分" + (lost.length ? "；沒拿到：" + lost.join("、") : "")];
    };
  }

  // 打的字自動換行：中文一字一斷，英文整個字一起換；單一個字比一行還寬才逐字切
  function wrap(text, width) {
    measure.font = FONT + "px " + FAMILY;
    const lines = [];
    for (const para of text.split("\n")) {
      let line = "";
      for (const tok of para.match(TOKEN) || []) {
        if (measure.measureText(line + tok).width <= width || !line.trim()) {
          line += tok;
        } else {
          lines.push(line.trimEnd());
          line = tok.trimStart();
        }
        while (measure.measureText(line).width > width && line.length > 1) {
          let i = line.length - 1;
          while (i > 1 && measure.measureText(line.slice(0, i)).width > width) i--;
          lines.push(line.slice(0, i));
          line = line.slice(i);
        }
      }
      lines.push(line);
    }
    return lines;
  }

  function drawItem(ctx, it) {
    ctx.save();
    if (it.tool === "text") {
      ctx.fillStyle = COLORS.black;
      ctx.font = FONT + "px " + FAMILY;
      ctx.textBaseline = "middle";
      wrap(it.text, it.w).forEach(function (line, i) { ctx.fillText(line, it.x, it.y + i * LINE + LINE / 2); });
    } else {
      ctx.globalCompositeOperation = it.tool === "eraser" ? "destination-out" : "source-over";
      ctx.strokeStyle = it.tool === "eraser" ? "#000" : COLORS[it.tool];
      ctx.lineWidth = it.tool === "eraser" ? 22 : 2.4;
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      ctx.beginPath();
      const p = it.pts;
      ctx.moveTo(p[0][0], p[0][1]);
      if (p.length === 1) ctx.lineTo(p[0][0] + 0.01, p[0][1]);
      for (let i = 1; i < p.length; i++) ctx.lineTo(p[i][0], p[i][1]);
      ctx.stroke();
    }
    ctx.restore();
  }

  function textBottom(it) {
    return it.y + wrap(it.text, it.w).length * LINE;
  }

  function makePad(host) {
    const id = host.dataset.id;
    const section = host.closest("section.q");
    const question = section ? section.querySelector("h2").textContent.trim() : id;
    const store = KEY + ":" + id;
    const saved = JSON.parse(localStorage.getItem(store) || "null");
    const st = { items: saved ? saved.items : [], h: saved ? saved.h : +host.dataset.h, w: saved ? saved.w : 0, tool: "black" };

    host.innerHTML =
      '<div class="tools">' +
      '<button type="button" data-tool="black" aria-pressed="true"><span class="dot" style="background:' + COLORS.black + '"></span>黑筆</button>' +
      '<button type="button" data-tool="red" aria-pressed="false"><span class="dot" style="background:' + COLORS.red + '"></span>紅筆</button>' +
      '<button type="button" data-tool="blue" aria-pressed="false"><span class="dot" style="background:' + COLORS.blue + '"></span>藍筆</button>' +
      '<button type="button" data-tool="text" aria-pressed="false">文字</button>' +
      '<button type="button" data-tool="eraser" aria-pressed="false">橡皮擦</button>' +
      '<span class="sep"></span>' +
      '<button type="button" data-act="undo">復原</button>' +
      '<button type="button" data-act="grow">加長</button>' +
      '<button type="button" data-act="clear" class="danger">清空</button>' +
      '<button type="button" data-act="send" class="send">複製給 Claude</button>' +
      '<span class="status" aria-live="polite"></span></div>' +
      '<div class="board"><canvas></canvas></div>';
    const board = host.querySelector(".board");
    const canvas = host.querySelector("canvas");
    const ctx = canvas.getContext("2d");
    const status = host.querySelector(".status");
    let current = null;  // 正在畫的一筆
    let editing = null;  // 正在打的字：{ item, index, ta }
    let scale = 1;

    function say(msg) { status.textContent = msg; }
    function save() {
      localStorage.setItem(store, JSON.stringify({ w: st.w, h: st.h, items: st.items }));
      say("已自動儲存");
    }
    function redraw() {
      ctx.save();
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.restore();
      st.items.forEach(function (it, i) { if (!editing || editing.index !== i) drawItem(ctx, it); });
    }
    // 畫布座標固定是第一次打開時的寬度 st.w；版面變窄變寬時整張等比例縮放，字不會被切掉
    function resize() {
      const cw = board.clientWidth;
      if (!cw) return;
      if (!st.w) st.w = cw;
      scale = cw / st.w;
      const k = scale * (window.devicePixelRatio || 1);
      canvas.style.height = st.h * scale + "px";
      canvas.width = Math.round(st.w * k);
      canvas.height = Math.round(st.h * k);
      ctx.setTransform(k, 0, 0, k, 0, 0);
      if (editing) placeEditor();
      redraw();
    }
    function pos(e) {
      const r = canvas.getBoundingClientRect();
      return [Math.round((e.clientX - r.left) / scale * 10) / 10, Math.round((e.clientY - r.top) / scale * 10) / 10];
    }

    // 打字：文字工具下點空白處開一個輸入框，點已有的字就改那段字；點別處或按 Esc 就收起來畫上去
    function placeEditor() {
      const { item, ta } = editing;
      Object.assign(ta.style, {
        left: item.x * scale + "px", top: item.y * scale + "px", width: item.w * scale + "px",
        fontSize: FONT * scale + "px", lineHeight: LINE * scale + "px"
      });
      ta.style.height = "auto";
      ta.style.height = Math.max(LINE * scale, ta.scrollHeight) + "px";
    }
    function openEditor(item, index) {
      const ta = document.createElement("textarea");
      ta.value = item.text;
      ta.setAttribute("aria-label", question + " 的文字");
      board.appendChild(ta);
      editing = { item: item, index: index, ta: ta };
      placeEditor();
      redraw();
      ta.addEventListener("input", placeEditor);
      ta.addEventListener("keydown", function (e) {
        if (e.key === "Escape") { e.preventDefault(); ta.blur(); }
      });
      ta.addEventListener("blur", commitEditor);
      ta.focus();
    }
    function commitEditor() {
      if (!editing) return;
      const { item, index, ta } = editing;
      editing = null;
      const text = ta.value.replace(/\s+$/, "");
      ta.remove();
      if (index < 0) {
        if (text) st.items.push(Object.assign(item, { text: text }));
      } else if (text) {
        st.items[index].text = text;
      } else {
        st.items.splice(index, 1);
      }
      if (text && st.h < textBottom(item) + LINE) st.h = textBottom(item) + LINE * 2;
      resize();
      save();
    }
    function textAt(p) {
      for (let i = st.items.length - 1; i >= 0; i--) {
        const it = st.items[i];
        if (it.tool === "text" && p[0] >= it.x && p[0] <= it.x + it.w && p[1] >= it.y && p[1] <= textBottom(it)) return i;
      }
      return -1;
    }

    canvas.addEventListener("click", function (e) {
      if (st.tool !== "text") return;
      lastPad = api;
      const p = pos(e);
      const hit = textAt(p);
      if (hit >= 0) { openEditor(st.items[hit], hit); return; }
      const x = Math.max(4, Math.min(p[0], st.w - 160));
      openEditor({ tool: "text", x: x, y: Math.max(0, p[1] - LINE / 2), w: st.w - x - 12, text: "" }, -1);
    });
    canvas.addEventListener("pointerdown", function (e) {
      if (e.button !== 0 || st.tool === "text") return;
      canvas.setPointerCapture(e.pointerId);
      current = { tool: st.tool, pts: [pos(e)] };
      lastPad = api;
      drawItem(ctx, current);
    });
    canvas.addEventListener("pointermove", function (e) {
      if (!current) return;
      const events = e.getCoalescedEvents ? e.getCoalescedEvents() : [e];
      for (const ev of events) current.pts.push(pos(ev));
      const p = current.pts;
      drawItem(ctx, { tool: current.tool, pts: p.slice(Math.max(0, p.length - events.length - 1)) });
    });
    function finish() {
      if (!current) return;
      st.items.push(current);
      current = null;
      save();
    }
    canvas.addEventListener("pointerup", finish);
    canvas.addEventListener("pointercancel", finish);

    // 複製給 Claude：題目名稱、題目代號和這張畫布合成一張圖，只裁到寫過的高度
    function snapshot() {
      const notes = fillLines[id] ? fillLines[id]().map(function (s) { return "填答：" + s; }) : [];
      const k = 2, head = 58 + notes.length * 20;
      let bottom = 0;
      for (const it of st.items) {
        if (it.tool === "text") bottom = Math.max(bottom, textBottom(it));
        else if (it.tool !== "eraser") for (const p of it.pts) bottom = Math.max(bottom, p[1]);
      }
      const h = Math.min(st.h, Math.max(120, bottom + 24));
      const layer = document.createElement("canvas");
      layer.width = st.w * k;
      layer.height = h * k;
      const lc = layer.getContext("2d");
      lc.scale(k, k);
      st.items.forEach(function (it) { drawItem(lc, it); });  // 橡皮擦只擦這一層，不會擦到白底和標題
      const out = document.createElement("canvas");
      out.width = st.w * k;
      out.height = (h + head) * k;
      const oc = out.getContext("2d");
      oc.scale(k, k);
      oc.fillStyle = "#fff";
      oc.fillRect(0, 0, st.w, h + head);
      oc.fillStyle = COLORS.black;
      oc.font = "600 17px " + FAMILY;
      oc.fillText(TITLE + " · " + question, 12, 24);
      oc.fillStyle = "#5b6475";
      oc.font = "13px " + FAMILY;
      oc.fillText("題目代號：" + id, 12, 46);
      notes.forEach(function (s, i) { oc.fillText(s, 12, 66 + i * 20); });
      oc.fillRect(0, head - 1, st.w, 1);
      oc.drawImage(layer, 0, head, st.w, h);
      return new Promise(function (res) { out.toBlob(res, "image/png"); });
    }
    async function send() {
      if (editing) editing.ta.blur();
      if (!st.items.length) { say("畫布是空的"); return; }
      try {
        await navigator.clipboard.write([new ClipboardItem({ "image/png": snapshot() })]);
        say("已複製：到對話裡按 Ctrl+V 貼上");
      } catch (err) {
        const url = URL.createObjectURL(await snapshot());
        const a = document.createElement("a");
        a.href = url;
        a.download = KEY + "-" + id + ".png";
        a.click();
        setTimeout(function () { URL.revokeObjectURL(url); }, 2000);
        say("瀏覽器不讓複製，已下載成圖片：把它拖進對話");
      }
    }

    host.querySelector(".tools").addEventListener("click", function (e) {
      const b = e.target.closest("button");
      if (!b) return;
      lastPad = api;
      if (b.dataset.tool) {
        st.tool = b.dataset.tool;
        host.querySelectorAll("[data-tool]").forEach(function (x) { x.setAttribute("aria-pressed", x === b ? "true" : "false"); });
        canvas.classList.toggle("erasing", st.tool === "eraser");
        canvas.classList.toggle("typing", st.tool === "text");
      } else if (b.dataset.act === "undo") {
        api.undo();
      } else if (b.dataset.act === "grow") {
        st.h += 400; resize(); save();
      } else if (b.dataset.act === "send") {
        send();
      } else if (b.dataset.act === "clear") {
        if (b.classList.contains("armed")) {
          st.items = []; st.h = +host.dataset.h; resize(); save();
          b.classList.remove("armed"); b.textContent = "清空";
        } else {
          b.classList.add("armed"); b.textContent = "再按一次清空";
          setTimeout(function () { b.classList.remove("armed"); b.textContent = "清空"; }, 2500);
        }
      }
    });

    const api = {
      undo: function () {
        if (!st.items.length) return;
        st.items.pop();
        redraw(); save();
      },
      resize: resize
    };
    resize();
    return api;
  }

  const sections = Array.from(document.querySelectorAll("section.q"));
  sections.forEach(makeFills);
  sections.forEach(makeModel);
  const pads = Array.from(document.querySelectorAll(".pad")).map(makePad);

  // 模擬卷：按「開始計時」才看得到題目，頂端倒數；按「交卷」才對填答格、才出現範本答案
  let mockLine = null;
  const clock = document.querySelector(".clock");
  if (MOCK && clock) {
    const store = KEY + ":mock";
    const limit = +clock.dataset.minutes * 60;
    const st = JSON.parse(localStorage.getItem(store) || "null") || { start: 0, end: 0 };
    const left = clock.querySelector(".left");
    const start = clock.querySelector('[data-act="start"]');
    const submit = clock.querySelector('[data-act="submit"]');
    const status = clock.querySelector(".status");
    const mmss = function (sec) { return Math.floor(sec / 60) + ":" + String(Math.floor(sec % 60)).padStart(2, "0"); };
    let timer = 0;
    function tick() {
      const used = ((st.end || Date.now()) - st.start) / 1000;
      const over = used > limit;
      clock.classList.toggle("over", over);
      left.textContent = st.end ? "用時 " + mmss(used) + "（限時 " + mmss(limit) + "）"
        : over ? "時間到，已超過 " + mmss(used - limit) : "剩 " + mmss(limit - used);
    }
    function show() {
      document.body.classList.toggle("started", !!st.start);
      document.body.classList.toggle("submitted", !!st.end);
      start.hidden = !!st.start;
      submit.hidden = !st.start || !!st.end;
      clearInterval(timer);
      if (st.start) tick(); else left.textContent = "限時 " + mmss(limit);
      if (st.start && !st.end) timer = setInterval(tick, 1000);
      if (st.end) {
        mockChecks.forEach(function (check) { check(); });
        status.textContent = "已交卷：往下看每題的範本答案，照給分點勾。";
      }
      pads.forEach(function (p) { p.resize(); });
    }
    start.addEventListener("click", function () {
      st.start = Date.now();
      localStorage.setItem(store, JSON.stringify(st));
      show();
    });
    submit.addEventListener("click", function () {
      if (!submit.classList.contains("armed")) {  // 交卷不能反悔，要連按兩下
        submit.classList.add("armed"); submit.textContent = "再按一次交卷";
        setTimeout(function () { submit.classList.remove("armed"); submit.textContent = "交卷"; }, 2500);
        return;
      }
      st.end = Date.now();
      localStorage.setItem(store, JSON.stringify(st));
      show();
    });
    mockLine = function () {
      return st.end ? "模擬卷用時 " + mmss((st.end - st.start) / 1000) + "，限時 " + mmss(limit) : "模擬卷還沒交卷";
    };
    show();
  }

  // 複製填答結果：每題一行字，貼到對話讓 Claude 記進學習紀錄
  const report = document.getElementById("report");
  if (report) report.addEventListener("click", async function () {
    const status = report.parentNode.querySelector(".status");
    const lines = [TITLE + " 填答結果"].concat(mockLine ? [mockLine()] : []);
    sections.forEach(function (sec) {
      const got = fillLines[sec.dataset.id]().concat(modelLines[sec.dataset.id] ? modelLines[sec.dataset.id]() : []);
      const name = sec.dataset.id + "（" + sec.querySelector("h2").textContent.trim() + "）";
      got.forEach(function (s) { lines.push(name + "：" + s); });
    });
    try {
      await navigator.clipboard.writeText(lines.join("\n"));
      status.textContent = "已複製：到對話裡貼上";
    } catch (err) {
      let box = report.parentNode.querySelector("textarea");
      if (!box) { box = document.createElement("textarea"); box.readOnly = true; report.parentNode.append(box); }
      box.value = lines.join("\n");
      box.rows = lines.length;
      box.select();
      status.textContent = "瀏覽器不讓複製：全選下面的字自己複製";
    }
  });
  let timer;
  window.addEventListener("resize", function () {
    clearTimeout(timer);
    timer = setTimeout(function () { pads.forEach(function (p) { p.resize(); }); }, 120);
  });
  document.addEventListener("keydown", function (e) {
    if (e.target.closest("textarea, input")) return;  // 打字時的 Ctrl+Z 是輸入框自己的復原
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z" && lastPad) {
      e.preventDefault();
      lastPad.undo();
    }
  });

  function toggleLang(img) {
    img.src = img.getAttribute("src") === img.dataset.zh ? img.dataset.en : img.dataset.zh;
  }
  document.querySelector("main").addEventListener("click", function (e) {
    const img = e.target.closest("figure img[data-zh]");
    if (img) toggleLang(img);
  });

  // 書眉：寫現在第幾題，題號格上那一格畫紅底線；按書眉回到題號格
  const here = document.querySelector(".here");
  if (here) {
    const strip = here.parentElement;
    const sections = Array.from(document.querySelectorAll("section.q"));
    const links = Array.from(document.querySelectorAll("nav.jump a"));
    let queued = false;
    let last = null;  // 回到題號格時還看得出剛才做到哪一題
    const sync = function () {
      queued = false;
      const line = strip.getBoundingClientRect().bottom + 28;
      let current = null;
      sections.forEach(function (s) { if (s.offsetParent && s.getBoundingClientRect().top <= line) current = s; });
      here.textContent = current ? current.querySelector("h2").textContent.trim() : "共 " + sections.length + " 題";
      if (current) last = current;
      links.forEach(function (a) {
        if (last && a.getAttribute("href") === "#" + last.id) a.setAttribute("aria-current", "true");
        else a.removeAttribute("aria-current");
      });
    };
    here.addEventListener("click", function () {
      const nav = document.querySelector("nav.jump");
      if (nav && nav.offsetParent) nav.scrollIntoView({ block: "center" }); else window.scrollTo({ top: 0 });
    });
    window.addEventListener("scroll", function () { if (!queued) { queued = true; requestAnimationFrame(sync); } }, { passive: true });
    window.addEventListener("resize", sync);
    sync();
  }

  const panel = document.getElementById("panel");
  if (!panel) return;
  function setOpen(on) {
    panel.classList.toggle("open", on);
    document.body.classList.toggle("panel-open", on);
    pads.forEach(function (p) { p.resize(); });
  }
  document.getElementById("panel-btn").addEventListener("click", function () { setOpen(!panel.classList.contains("open")); });
  panel.addEventListener("click", function (e) {
    const b = e.target.closest("button");
    if (b && b.classList.contains("close")) { setOpen(false); return; }
    if (b && b.dataset.tab) {
      panel.querySelectorAll("header [data-tab]").forEach(function (x) { x.setAttribute("aria-pressed", x === b ? "true" : "false"); });
      panel.querySelectorAll("figure").forEach(function (f) { f.hidden = f.dataset.tab !== b.dataset.tab; });
      return;
    }
    const img = e.target.closest("img[data-zh]");
    if (img) toggleLang(img);
  });
})();
