"""把解說頁的原始 HTML 組成單一檔案：不准載入外部資源，有 Mermaid 圖就把 Mermaid 整份內嵌。

    python build.py <page-src.html> [-o <page.html>]

為什麼要內嵌：Orca 從另一台機器開工作區的 HTML 時走隔離預覽，CSP 只放行頁內的 script，
其他請求一律取消，從 CDN 載入的 Mermaid 會被擋，圖就變成一段原始碼。

Mermaid 第一次用時從 npm registry 下載固定版本、驗 sha512，存在使用者快取目錄。
只用標準函式庫，CI 才能直接跑測試。
"""

import argparse
import base64
import hashlib
import io
import os
import re
import sys
import tarfile
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

MERMAID_VERSION = "11.17.2"
MERMAID_TARBALL = f"https://registry.npmjs.org/mermaid/-/mermaid-{MERMAID_VERSION}.tgz"
# npm registry 的 dist.integrity
MERMAID_SHA512 = "V6K3C8EBdEsPFZXSKMJe6ppQOENxuHARr9GvHX4hh47lAbhMRD9qf4oEK7LoaRQxULMa80/qt5gHO73aCleBBg=="
MERMAID_MEMBER = "package/dist/mermaid.min.js"
INIT = ('mermaid.initialize({ startOnLoad: true, theme: '
        'matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "neutral" });')

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


def build(html: str, load_mermaid) -> str:
    """有 <pre class="mermaid"> 才呼叫 load_mermaid() 取 Mermaid 原始碼，放在 </body> 前。"""
    if not scan(html).diagrams:
        return html
    tail = inline_script(load_mermaid()) + "\n<script>\n  " + INIT + "\n</script>\n"
    ends = [m.start() for m in re.finditer(r"</body\s*>", html, re.I)]
    if not ends:
        return html + tail
    return html[:ends[-1]] + tail + html[ends[-1]:]


def verify(tarball: bytes) -> bool:
    return base64.b64encode(hashlib.sha512(tarball).digest()).decode() == MERMAID_SHA512


def cache_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return base / "1morr"


def load_mermaid() -> str:
    cached = cache_dir() / f"mermaid-{MERMAID_VERSION}.min.js"
    if cached.exists():
        return cached.read_text(encoding="utf-8")
    with urllib.request.urlopen(MERMAID_TARBALL, timeout=60) as r:
        tarball = r.read()
    if not verify(tarball):
        raise RuntimeError(f"{MERMAID_TARBALL} 的 sha512 對不上，不使用")
    with tarfile.open(fileobj=io.BytesIO(tarball), mode="r:gz") as t:
        js = t.extractfile(MERMAID_MEMBER).read().decode("utf-8")
    cached.parent.mkdir(parents=True, exist_ok=True)
    tmp = cached.with_suffix(".tmp")
    tmp.write_text(js, encoding="utf-8")
    tmp.replace(cached)
    return js


def main(argv=None, loader=load_mermaid) -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")  # Windows 終端機預設不是 UTF-8
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("src", type=Path)
    ap.add_argument("-o", "--out", type=Path)
    args = ap.parse_args(argv)
    src = args.src.read_text(encoding="utf-8")
    problems = lint(src)
    if problems:
        print(f"{args.src}：{len(problems)} 個問題，沒有產出", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    out = args.out or args.src.with_name(args.src.stem.removesuffix("-src") + ".html")
    if out.resolve() == args.src.resolve():
        print(f"輸出會蓋掉原始檔 {args.src}：原始檔名要以 -src.html 結尾，或用 -o 指定", file=sys.stderr)
        return 1
    out.write_text(build(src, loader), encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
