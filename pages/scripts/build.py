"""把解說頁的原始 HTML 組成單一檔案：不准載入外部資源；有 Mermaid 圖就內嵌 Mermaid、Panzoom 和
同資料夾的 diagram.js、diagram.css（瀏覽器打開時畫圖、可縮放拖動），再用本機的 Chrome 或 Edge
無頭打開組好的頁，確認每張圖都畫出來、縮放按鈕都掛上了。

    python build.py <page-src.html> [-o <page.html>]

成功時印出輸出檔路徑和「N 張圖都畫出來了」，退出碼 0。有問題時印到 stderr、退出碼 1：
- 原始頁會從外部載入東西：不產出。頁面要離線也能看。
- 找不到瀏覽器或圖畫不出來：照樣產出。

組好的頁約 3.6 MB（多半是 Mermaid）。Orca 從另一台機器預覽工作區的檔案時只讀 512 KiB 以內，
打不開；交付時開本機 http server、給網址就沒有這個限制（HANDOFF.md）。

為什麼用瀏覽器的命令列檢查：playwright 不讓開 file://，得另開 http server，用完常忘了關，
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
                self.problems.append(f"<{tag} {k}=\"{v}\"> 會從外部載入：頁面要離線也能看，改成內嵌或拿掉")
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


def build(html: str, load) -> str:
    """有 <pre class="mermaid"> 才呼叫 load(pkg) 取 Mermaid、Panzoom，連同 diagram.css、diagram.js 放在 </body> 前。"""
    if not scan(html).diagrams:
        return html
    css = (HERE / "diagram.css").read_text(encoding="utf-8")
    js = (HERE / "diagram.js").read_text(encoding="utf-8")
    return before_body_end(html, "".join([
        "<style>\n", css, "</style>\n",
        inline_script(load(MERMAID)), "\n",
        inline_script(load(PANZOOM)), "\n",
        inline_script(js), "\n",
    ]))


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
    """收集畫好的頁上每個 <pre class="mermaid">：裡面有沒有 svg、有沒有縮放按鈕列、svg 裡寫了什麼字。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.diagrams = []
        self.depth = 0  # 在 mermaid 的 <pre> 裡面幾層

    def handle_starttag(self, tag, attrs):
        if tag == "pre":
            if self.depth:
                self.depth += 1
            elif "mermaid" in (dict(attrs).get("class") or "").split():
                self.diagrams.append({"svg": False, "zoom": False, "text": []})
                self.depth = 1
        elif tag == "svg" and self.depth:
            self.diagrams[-1]["svg"] = True
        elif self.depth and "dz-bar" in (dict(attrs).get("class") or "").split():
            self.diagrams[-1]["zoom"] = True

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
        elif not d["zoom"]:
            problems.append(f"第 {i} 張圖沒掛上縮放按鈕：diagram.js 沒跑完")
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
    out.write_text(build(src, load), encoding="utf-8")
    print(out)
    diagrams = scan(src).diagrams
    if not diagrams:
        return 0
    dom = render(out)
    if dom is None:
        print("找不到 Chrome 或 Edge，沒檢查圖有沒有畫出來：照 PAGE.md〈交出前〉的退路檢查", file=sys.stderr)
        return 1
    problems = render_problems(dom, diagrams)
    if problems:
        report(out, problems, "渲染問題")
        return 1
    print(f"{diagrams} 張圖都畫出來了")
    return 0


if __name__ == "__main__":
    sys.exit(main())
