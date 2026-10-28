// tutor 講解頁的互動；build.py 會把它內嵌進每一頁。
// 點翻譯過的圖：在中文和原文之間切換。工具列按鈕：全部圖片切換、全部做法展開或收起。
document.addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-act]");
  if (btn) {
    if (btn.dataset.act === "lang") {
      const en = document.body.classList.toggle("all-en");
      document.querySelectorAll("figure").forEach((f) => {
        if (f.querySelector("img.zh")) f.classList.toggle("show-en", en);
      });
      btn.textContent = en ? "圖片：原文（點這裡全部換成中文）" : "圖片：中文（點這裡全部換成原文）";
    } else if (btn.dataset.act === "answers") {
      const all = [...document.querySelectorAll("details.answer")];
      const open = !all.every((d) => d.open);
      all.forEach((d) => { d.open = open; });
      btn.textContent = open ? "收起全部做法" : "展開全部做法";
    }
    return;
  }
  const fig = e.target.closest("figure");
  if (fig && fig.querySelector("img.zh") && !e.target.closest("a")) fig.classList.toggle("show-en");
});
