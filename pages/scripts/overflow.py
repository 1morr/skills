"""量一頁 HTML 有沒有水平溢出：用本機的 Chrome 或 Edge 無頭打開，寬螢幕和手機寬各量一次。

    python overflow.py <page.html>

沒有溢出印「沒有水平溢出」，退出碼 0。有溢出時逐條印到 stderr、退出碼 1，每條寫視窗寬、
哪個容器被撐寬、超出最多的幾個元素和各超出幾 px。找不到瀏覽器印一句提醒，退出碼 2。

算溢出的是「直向捲動的容器」被撐寬：整頁，或自己上下捲動的欄。摺疊的 <details> 會先全部打開再量。
表格、算式、程式碼放在自己橫向捲動的容器裡（overflow-x: auto）不算。

組頁腳本（pages/scripts/build.py、tutor 的 build.py 和 practice.py）用 render()、problems()、measure()、deliverable()；
量的程式是加在暫存的副本上，不會留在交付的頁裡。只用標準函式庫。
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

WIDTHS = (1440, 390)
HEIGHT = 900
META = "overflow-report"

# 依序找；第一個找得到的就用
BROWSER_NAMES = ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge", "msedge"]
MAC_APPS = ["Google Chrome", "Microsoft Edge", "Chromium"]
WIN_EXES = [("Google", "Chrome", "chrome.exe"), ("Microsoft", "Edge", "msedge.exe")]

# 加在副本的 </body> 前：量完把結果寫進 <meta name="overflow-report">
PROBE = r"""<script>
addEventListener("load", () => setTimeout(() => {
  document.querySelectorAll("details").forEach((d) => { d.open = true; });
  /*PREPARE*/
  const root = document.documentElement;
  const name = (e) => e.tagName.toLowerCase() + (e.id ? "#" + e.id : "")
    + (typeof e.className === "string" && e.className.trim() ? "." + e.className.trim().split(/\s+/).join(".") : "");
  const found = [];
  for (const box of [root, ...document.querySelectorAll("body, body *")]) {
    const isRoot = box === root;
    if (!isRoot) {
      // 自己上下捲動的欄才算；只橫向捲動的容器（表格、算式）差不到一條捲軸的高度
      if (!/auto|scroll/.test(getComputedStyle(box).overflowY) || box.scrollHeight <= box.clientHeight + 40) continue;
    }
    const width = isRoot ? innerWidth : box.clientWidth;
    if (box.scrollWidth <= width + 1) continue;
    const edge = isRoot ? innerWidth : box.getBoundingClientRect().left + box.clientLeft + box.clientWidth;
    const wide = [];
    for (const e of box.querySelectorAll("*")) {
      const r = e.getBoundingClientRect();
      if (!r.width || r.right <= edge + 1 || getComputedStyle(e).position === "fixed") continue;
      let held = false; // 在自己橫向捲動或裁切的容器裡
      for (let p = e.parentElement; p && p !== box; p = p.parentElement) {
        if (getComputedStyle(p).overflowX !== "visible") { held = true; break; }
      }
      if (!held) wide.push({ e, over: Math.round(r.right - edge) });
    }
    // 只報最外層：<math> 超出時不必再列它裡面的每個符號
    const leaves = wide.filter((w) => !wide.some((o) => o !== w && o.e.contains(w.e)));
    leaves.sort((a, b) => b.over - a.over);
    found.push({
      box: isRoot ? "整頁" : name(box), over: box.scrollWidth - width,
      items: leaves.slice(0, 5).map((w) => ({ el: name(w.e), over: w.over, text: (w.e.textContent || "").trim().replace(/\s+/g, " ").slice(0, 40) })),
    });
  }
  const meta = document.createElement("meta");
  meta.name = "overflow-report";
  meta.content = JSON.stringify(found);
  document.head.append(meta);
}, 1500));
</script>"""

REPORT = re.compile(r'<meta name="' + META + r'" content="([^"]*)"')


def find_browser():
    for name in BROWSER_NAMES:
        found = shutil.which(name)
        if found:
            return found
    candidates = []
    for app in MAC_APPS:
        for root in (Path("/Applications"), Path.home() / "Applications"):
            candidates.append(root / f"{app}.app" / "Contents" / "MacOS" / app)
    for env in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        if os.environ.get(env):
            for vendor, product, exe in WIN_EXES:
                candidates.append(Path(os.environ[env]) / vendor / product / "Application" / exe)
    return next((str(c) for c in candidates if c.is_file()), None)


def with_probe(html: str, prepare: str = "") -> str:
    probe = PROBE.replace("/*PREPARE*/", prepare)
    ends = [m.start() for m in re.finditer(r"</body\s*>", html, re.I)]
    return html[:ends[-1]] + probe + html[ends[-1]:] if ends else html + probe


def render(page: Path, width: int = WIDTHS[0], prepare: str = ""):
    """用無頭瀏覽器在 width 寬的視窗打開 page 的副本（加了量測）、跑完 JS，回傳畫好的 DOM；找不到瀏覽器回傳 None。
    prepare 是量之前先跑的一段 JS：頁面有要按了才出現的內容時，用它先讓內容出現。"""
    browser = find_browser()
    if not browser:
        return None
    # 自己的 profile：使用者的瀏覽器開著也不會搶同一個 profile
    work = Path(tempfile.mkdtemp(prefix="page-render-"))
    try:
        # 副本放在原檔旁邊，頁面用相對路徑引用的圖才找得到
        copy = Path(tempfile.mkstemp(prefix=".overflow-", suffix=".html", dir=page.resolve().parent)[1])
        try:
            copy.write_text(with_probe(page.read_text(encoding="utf-8"), prepare), encoding="utf-8")
            r = subprocess.run(
                [browser, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check", "--hide-scrollbars",
                 f"--user-data-dir={work}", f"--window-size={width},{HEIGHT}", "--virtual-time-budget=15000",
                 "--dump-dom", copy.as_uri()],
                capture_output=True, timeout=180)
        finally:
            copy.unlink(missing_ok=True)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return r.stdout.decode("utf-8", "replace")


def problems(dom: str, width: int) -> list:
    """render() 回傳的 DOM 裡量到的溢出，一條一句。"""
    m = REPORT.search(dom)
    if not m:
        return [f"視窗寬 {width}px：量測沒有跑完（頁面的 JS 可能出錯了）"]
    out = []
    for box in json.loads(m.group(1).replace("&quot;", '"').replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")):
        items = "；".join(f"<{i['el']}> 超出 {i['over']}px「{i['text']}」" for i in box["items"]) or "找不到是哪個元素"
        out.append(f"視窗寬 {width}px：{box['box']}被撐寬 {box['over']}px，出現水平捲軸。{items}。"
                   "讓它換行，或放進自己橫向捲動的容器（overflow-x: auto）")
    return out


def measure(page: Path, widths=WIDTHS, prepare: str = ""):
    """每個寬度量一次，回傳全部的溢出；找不到瀏覽器回傳 None。"""
    out = []
    for width in widths:
        dom = render(page, width, prepare)
        if dom is None:
            return None
        out += problems(dom, width)
    return out


def deliverable(out: Path, src, found) -> bool:
    """組頁腳本寫出 out 之後呼叫，found 是 measure(out) 的結果。有溢出就刪掉 out、逐條印到 stderr，回傳 False；
    找不到瀏覽器（None）印一句提醒、照樣交付。"""
    if found is None:
        print("提醒：找不到 Chrome 或 Edge，沒有量水平溢出；用瀏覽器自動化工具在寬螢幕和手機寬各確認一次沒有水平捲軸", file=sys.stderr)
        return True
    if not found:
        return True
    out.unlink()
    print(f"{src}：{len(found)} 處水平溢出，沒有產出", file=sys.stderr)
    for p in found:
        print(f"  - {p}", file=sys.stderr)
    return False


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")  # Windows 終端機預設不是 UTF-8
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    found = measure(Path(args[0]))
    if found is None:
        print("找不到 Chrome 或 Edge，沒有量水平溢出", file=sys.stderr)
        return 2
    if found:
        print(f"{args[0]}：{len(found)} 處水平溢出", file=sys.stderr)
        for p in found:
            print(f"  - {p}", file=sys.stderr)
        return 1
    print("沒有水平溢出")
    return 0


if __name__ == "__main__":
    sys.exit(main())
