"""把解說頁的原始 HTML 組成單一檔案：不准載入外部資源；有 Mermaid 圖就用本機的 Chrome 或 Edge
無頭跑 Mermaid，把畫好的 svg 直接寫進頁面，確認每張圖都畫出來。

    python build.py <page-src.html> [-o <page.html>]

成功時印出輸出檔路徑和「N 張圖都畫出來了」，退出碼 0。有問題時印到 stderr、退出碼 1：
- 原始頁會從外部載入東西：不產出。
- 找不到瀏覽器或圖畫不出來：產出內嵌整份 Mermaid 的頁（約 3.6 MB，本機瀏覽器看得到圖）。
- 組好的頁超過 512 KiB：照樣產出。

為什麼預先畫好：Orca 從另一台機器開工作區的 HTML 時走隔離預覽，CSP 只放行頁內的 script，
其他請求一律取消，所以 Mermaid 不能從 CDN 載入；而且它只讀 512 KiB 以內的檔
（Orca main/index.js 的 readDocPreviewFile 傳 maxTextBytes 524288），內嵌整份 Mermaid 也打不開。
深色模式跟著 prefers-color-scheme，所以每張圖畫淺色（neutral）、深色（dark）兩份，用 CSS 切換。
圖可以縮放拖動：頁上內嵌 Panzoom 和同資料夾的 diagram.js、diagram.css。

為什麼用瀏覽器的命令列：playwright 不讓開 file://，得另開 http server，用完常忘了關，
截圖也會留在 repo 裡；`--dump-dom` 直接開檔案、跑完 JS 就交回 DOM，什麼都不留。

Mermaid 和 Panzoom 第一次用時從 npm registry 下載固定版本、驗 sha512，存在使用者快取目錄。
只用標準函式庫，CI 才能直接跑測試。
"""

import argparse
import base64
import hashlib
import io
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import NamedTuple

class Pkg(NamedTuple):
    name: str
    version: str
    sha512: str  # npm registry 的 dist.integrity
    member: str  # tarball 裡要的檔

    @property
    def tarball(self) -> str:
        return f"https://registry.npmjs.org/{self.name}/-/{self.name.split('/')[-1]}-{self.version}.tgz"


MERMAID = Pkg("mermaid", "11.17.2",
              "V6K3C8EBdEsPFZXSKMJe6ppQOENxuHARr9GvHX4hh47lAbhMRD9qf4oEK7LoaRQxULMa80/qt5gHO73aCleBBg==",
              "package/dist/mermaid.min.js")
PANZOOM = Pkg("@panzoom/panzoom", "4.6.2",
              "Zn3B5/hwa6eYIPRSKX0xf2clv8nviTX8AnAU5kU/EugiTDhG41ya2wlBqYrZJYCWQROr/5XkWObZhIkepi89qw==",
              "package/dist/panzoom.min.js")
HERE = Path(__file__).resolve().parent
AUTO_THEME = 'matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "neutral"'
# 每張圖畫兩份：data-theme 的值 → Mermaid 主題
THEMES = {"light": "neutral", "dark": "dark"}
# Orca 遠端預覽讀檔的上限（main/index.js readDocPreviewFile 的 maxTextBytes）
ORCA_REMOTE_MAX = 524288

REMOTE = re.compile(r"^\s*(https?:)?//", re.I)
# 這些屬性的網址會被瀏覽器自動載入；<a href> 是讀者自己點的，不算
LOADING_ATTRS = {"src", "srcset", "poster", "data"}
# 從遠端載東西的寫法：script 裡的 import … from "…"、import("…")；style 裡的 @import、url(…)
REMOTE_IN_CODE = {
    "script": re.compile(r"""\bimport\b[^;"'`]*?["'`](https?:)?//""", re.I),
    "style": re.compile(r"""(@import\s+(url\(\s*)?|\burl\(\s*)["']?(https?:)?//""", re.I),
}


class Scan(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.problems = []
        self.diagrams = 0
        self.code_tag = None  # 正在讀的 script 或 style

    def handle_starttag(self, tag, attrs):
        a = {k: v or "" for k, v in attrs}
        for k, v in a.items():
            if (k in LOADING_ATTRS or (tag == "link" and k == "href")) and REMOTE.match(v):
                self.problems.append(f"<{tag} {k}=\"{v}\"> 會從外部載入：Orca 遠端預覽會擋，改成內嵌或拿掉")
        if tag == "pre" and "mermaid" in a.get("class", "").split():
            self.diagrams += 1
        if tag in ("script", "style"):
            self.code_tag = tag

    def handle_endtag(self, tag):
        if tag == self.code_tag:
            self.code_tag = None

    def handle_data(self, data):
        if not self.code_tag:
            return
        m = REMOTE_IN_CODE[self.code_tag].search(data)
        if m:
            self.problems.append(f"<{self.code_tag}> 裡從外部載入（{m.group(0)}…）：Orca 遠端預覽會擋，改成內嵌或拿掉")
        if self.code_tag == "script" and "mermaid.initialize" in data:
            self.problems.append("頁面自己載入了 Mermaid：拿掉，build.py 會放")


def scan(html: str) -> Scan:
    s = Scan()
    s.feed(html)
    s.close()
    return s


def lint(html: str) -> list:
    return scan(html).problems


def inline_script(js: str) -> str:
    """把 JS 包成 <script>，不讓內容提早結束 script 元素。"""
    if re.search(r"<script", js, re.I):
        # HTML 解析器在 <!-- 之後遇到 <script 會進入 double-escaped 狀態，跳脫 </script 也救不回來
        raise ValueError("內嵌的 JS 含有 <script，無法安全放進 <script> 元素")
    return "<script>" + re.sub(r"</(script)", r"<\\/\1", js, flags=re.I) + "</script>"


def before_body_end(html: str, tail: str) -> str:
    ends = [m.start() for m in re.finditer(r"</body\s*>", html, re.I)]
    if not ends:
        return html + tail
    return html[:ends[-1]] + tail + html[ends[-1]:]


def with_mermaid(html: str, js: str, theme=None) -> str:
    """把 Mermaid 原始碼和初始化放在 </body> 前；theme 是 None 時跟著 prefers-color-scheme。"""
    t = f'"{theme}"' if theme else AUTO_THEME
    return before_body_end(html, inline_script(js) + "\n<script>\n  mermaid.initialize({ startOnLoad: true, theme: "
                           + t + " });\n</script>\n")


PRE = re.compile(r"(<pre\b[^>]*>)(.*?)(</pre\s*>)", re.I | re.S)


def is_mermaid(start_tag: str) -> bool:
    s = Scan()
    s.feed(start_tag)
    return s.diagrams == 1


def mermaid_blocks(html: str) -> list:
    """頁上每個 <pre class="mermaid"> 的 match：group 1 開始標籤、2 內容、3 結束標籤。"""
    return [m for m in PRE.finditer(html) if is_mermaid(m.group(1))]


def drawn(dom: str) -> list:
    """畫好的頁上每張圖的內容（Mermaid 畫的 svg）。"""
    return [m.group(2).strip() for m in mermaid_blocks(dom)]


def rename(svg: str, new_id: str) -> str:
    """換掉 svg 的 id：svg 內的樣式和 url(#…) 都以它為前綴，兩份同一張圖才不會互相套到。"""
    m = re.search(r'<svg\b[^>]*?\sid="([^"]+)"', svg)
    return svg.replace(m.group(1), new_id) if m else svg


def embed(html: str, light: list, dark: list, panzoom_js: str) -> str:
    """把每個 <pre class="mermaid"> 的內容換成畫好的淺色、深色兩份 svg，
    前面放 diagram.css，</body> 前放 Panzoom 和 diagram.js（縮放拖動）。"""
    blocks = mermaid_blocks(html)
    if not (len(blocks) == len(light) == len(dark)):
        raise ValueError(f"頁上有 {len(blocks)} 張圖，畫好的淺色 {len(light)} 張、深色 {len(dark)} 張")
    out, pos = [], 0
    for i, (m, l, d) in enumerate(zip(blocks, light, dark), 1):
        out.append(html[pos:m.start()])
        if i == 1:
            out.append("<style>\n" + (HERE / "diagram.css").read_text(encoding="utf-8") + "</style>\n")
        out.append(m.group(1) + '<span class="dz-stage">'
                   + f'<span data-theme="light">{rename(l, f"diagram-{i}-light")}</span>'
                   + f'<span data-theme="dark">{rename(d, f"diagram-{i}-dark")}</span>'
                   + "</span>" + m.group(3))
        pos = m.end()
    page = "".join(out) + html[pos:]
    if not blocks:
        return page
    return before_body_end(page, inline_script(panzoom_js) + "\n"
                           + inline_script((HERE / "diagram.js").read_text(encoding="utf-8")) + "\n")


def verify(tarball: bytes, sha512: str) -> bool:
    return base64.b64encode(hashlib.sha512(tarball).digest()).decode() == sha512


def cache_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return base / "1morr"


def load_npm(pkg: Pkg) -> str:
    cached = cache_dir() / f"{pkg.name.lstrip('@').replace('/', '-')}-{pkg.version}.min.js"
    if cached.exists():
        return cached.read_text(encoding="utf-8")
    with urllib.request.urlopen(pkg.tarball, timeout=60) as r:
        tarball = r.read()
    if not verify(tarball, pkg.sha512):
        raise RuntimeError(f"{pkg.tarball} 的 sha512 對不上，不使用")
    with tarfile.open(fileobj=io.BytesIO(tarball), mode="r:gz") as t:
        js = t.extractfile(pkg.member).read().decode("utf-8")
    cached.parent.mkdir(parents=True, exist_ok=True)
    tmp = cached.with_suffix(".tmp")
    tmp.write_text(js, encoding="utf-8")
    tmp.replace(cached)
    return js


# 依序找；第一個找得到的就用
BROWSER_NAMES = ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge", "msedge"]
MAC_APPS = ["Google Chrome", "Microsoft Edge", "Chromium"]
WIN_EXES = [("Google", "Chrome", "chrome.exe"), ("Microsoft", "Edge", "msedge.exe")]


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


def render_dom(page: Path):
    """用無頭瀏覽器打開 page、跑完 JS，回傳畫好的 DOM；找不到瀏覽器回傳 None。"""
    browser = find_browser()
    if not browser:
        return None
    # 自己的 profile：使用者的瀏覽器開著也不會搶同一個 profile
    profile = tempfile.mkdtemp(prefix="explain-render-")
    try:
        r = subprocess.run(
            [browser, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
             f"--user-data-dir={profile}", "--virtual-time-budget=15000", "--dump-dom", page.resolve().as_uri()],
            capture_output=True, timeout=120)
    finally:
        shutil.rmtree(profile, ignore_errors=True)
    return r.stdout.decode("utf-8", "replace")


class Rendered(HTMLParser):
    """收集畫好的頁上每個 <pre class="mermaid">：裡面有沒有 svg、svg 裡寫了什麼字。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.diagrams = []
        self.depth = 0  # 在 mermaid 的 <pre> 裡面幾層

    def handle_starttag(self, tag, attrs):
        if tag == "pre":
            if self.depth:
                self.depth += 1
            elif "mermaid" in (dict(attrs).get("class") or "").split():
                self.diagrams.append({"svg": False, "text": []})
                self.depth = 1
        elif tag == "svg" and self.depth:
            self.diagrams[-1]["svg"] = True

    def handle_endtag(self, tag):
        if tag == "pre" and self.depth:
            self.depth -= 1

    def handle_data(self, data):
        if self.depth:
            self.diagrams[-1]["text"].append(data)


def render_problems(dom: str, expected: int) -> list:
    r = Rendered()
    r.feed(dom)
    r.close()
    if len(r.diagrams) != expected:
        return [f"原始頁有 {expected} 張圖，畫好的頁上找到 {len(r.diagrams)} 張：頁面的 JS 可能出錯了"]
    problems = []
    for i, d in enumerate(r.diagrams, 1):
        if not d["svg"]:
            problems.append(f"第 {i} 張圖沒畫出來，還是原始碼：Mermaid 沒執行或被擋")
        elif "Syntax error" in "".join(d["text"]):
            problems.append(f"第 {i} 張圖有語法錯誤，Mermaid 畫出的是錯誤圖示")
    return problems


def report(path, problems, what) -> None:
    print(f"{path}：{len(problems)} 個{what}", file=sys.stderr)
    for p in problems:
        print(f"  - {p}", file=sys.stderr)


def main(argv=None, load=load_npm, render=render_dom) -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")  # Windows 終端機預設不是 UTF-8
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("src", type=Path)
    ap.add_argument("-o", "--out", type=Path)
    args = ap.parse_args(argv)
    src = args.src.read_text(encoding="utf-8")
    problems = lint(src)
    if problems:
        report(args.src, problems, "問題，沒有產出")
        return 1
    out = args.out or args.src.with_name(args.src.stem.removesuffix("-src") + ".html")
    if out.resolve() == args.src.resolve():
        print(f"輸出會蓋掉原始檔 {args.src}：原始檔名要以 -src.html 結尾，或用 -o 指定", file=sys.stderr)
        return 1
    diagrams = scan(src).diagrams
    if not diagrams:
        return finish(out, src, 0)
    js = load(MERMAID)
    svgs = {}
    with tempfile.TemporaryDirectory(prefix="pages-build-") as d:
        for name, theme in THEMES.items():
            draft = Path(d) / f"{name}.html"
            draft.write_text(with_mermaid(src, js, theme), encoding="utf-8")
            dom = render(draft)
            if dom is None:
                out.write_text(with_mermaid(src, js), encoding="utf-8")
                print(out)
                print("找不到 Chrome 或 Edge，圖沒有預先畫好：產出的頁內嵌整份 Mermaid，"
                      "Orca 遠端預覽打不開；照 PAGE.md〈交出前〉的退路檢查", file=sys.stderr)
                return 1
            problems = render_problems(dom, diagrams)
            if problems:
                out.write_text(with_mermaid(src, js), encoding="utf-8")
                print(out)
                report(out, problems, f"渲染問題（{theme} 主題）")
                return 1
            svgs[name] = drawn(dom)
    return finish(out, embed(src, svgs["light"], svgs["dark"], load(PANZOOM)), diagrams)


def finish(out: Path, page: str, diagrams: int) -> int:
    out.write_text(page, encoding="utf-8")
    print(out)
    problems = lint(page)
    size = len(page.encode("utf-8"))
    if size > ORCA_REMOTE_MAX:
        problems.append(f"組好的頁 {size} bytes，超過 Orca 遠端預覽的上限 {ORCA_REMOTE_MAX}：拆頁或縮小")
    if problems:
        report(out, problems, "問題")
        return 1
    if diagrams:
        print(f"{diagrams} 張圖都畫出來了")
    return 0


if __name__ == "__main__":
    sys.exit(main())
