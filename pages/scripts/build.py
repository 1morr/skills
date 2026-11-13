"""把解說頁的原始 HTML 組成可以交付的頁：在 <head> 內嵌同資料夾的 tokens.css 和 page.css（配色、字體、
文章頁的元件；原始頁只寫內容，自己的 <style> 只補這兩份沒有的東西）。原始頁自己不准載入外部資源；有 Mermaid 圖就在頁尾放上
從 jsDelivr 載入 Mermaid、Panzoom 的 <script>（固定版本、附 integrity），再內嵌同資料夾的 diagram.js、
diagram.css（瀏覽器打開時畫圖、可縮放拖動）。組好之後用本機的 Chrome 或 Edge 無頭打開，確認每張圖
都畫出來、縮放按鈕都掛上了，並在寬螢幕和手機寬各量一次水平溢出（overflow.py）。

    python build.py <page-src.html> [-o <page.html>]

成功時印出輸出檔路徑和「N 張圖都畫出來了」，退出碼 0。有問題時印到 stderr、退出碼 1：
- 原始頁會從外部載入東西，或自己重新定義配色變數：不產出。外部資源只有這支放的兩個函式庫。
- 有水平溢出：不產出，逐條印出哪個元素在哪個寬度超出幾 px。
- 找不到瀏覽器或圖畫不出來：照樣產出。

打開組好的頁和這裡的檢查都要連得到 cdn.jsdelivr.net。寫法照 jsDelivr 的建議：網址釘完整版本號，
<script> 帶 integrity（檔案的 sha384）和 crossorigin="anonymous"，CDN 給的檔不一樣瀏覽器就不執行。
換版本時兩個都要改：integrity 用
    curl -sL <網址> | openssl dgst -sha384 -binary | openssl base64 -A
算，並對一次 npm registry 上同版本 tarball 裡的那個檔。

為什麼從 CDN 載入：頁面照 HANDOFF.md 經 localhost 網址交付，做的人和讀的人當下都連著網路。
走過又放棄的做法（要改回去之前先看理由還在不在）：
- 內嵌整套 Mermaid（eb01d56）：為了 Orca 遠端的檔案預覽，它的 CSP 擋掉所有外部請求。一頁 3.6 MB。
- 組頁時預先畫成 svg（5b70244）：那個預覽只讀 512 KiB 以內的檔。圖一多照樣超過，也不能縮放拖動。
- 經 localhost 網址看（906498f、c9f2fed）之後，頁面不再走檔案預覽，上面兩個限制都碰不到。

為什麼用瀏覽器的命令列檢查：playwright 不讓開 file://，得另開 http server，用完常忘了關，
截圖也會留在 repo 裡；`--dump-dom` 直接開檔案、跑完 JS 就交回 DOM，什麼都不留。

只用標準函式庫，CI 才能直接跑測試。
"""

import argparse
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import NamedTuple

HERE = Path(__file__).resolve().parent
STYLES = ("tokens.css", "page.css")
sys.path.insert(0, str(HERE))
import overflow  # noqa: E402  同資料夾的 overflow.py：找瀏覽器、無頭打開、量水平溢出

class Pkg(NamedTuple):
    name: str
    version: str
    path: str       # 套件裡要的檔
    integrity: str  # 那個檔的 sha384，寫進 <script integrity>

    @property
    def url(self) -> str:
        return f"https://cdn.jsdelivr.net/npm/{self.name}@{self.version}/{self.path}"

    @property
    def tag(self) -> str:
        return f'<script src="{self.url}" integrity="{self.integrity}" crossorigin="anonymous"></script>'


MERMAID = Pkg("mermaid", "11.17.2", "dist/mermaid.min.js",
              "sha384-EOXBFmc3gx5mb+vn0vPvvGqACToJD24hhacX5Yx+8NUUQrHIle/Qi5Bg9o3zKwW2")
PANZOOM = Pkg("@panzoom/panzoom", "4.6.2", "dist/panzoom.min.js",
              "sha384-irdz3GZoyr9anVd5nSLy63Z39tLtMTNQFFKxhx/KM08C8NkKpZre6M/m4QCUeeB3")

REMOTE = re.compile(r"^\s*(https?:)?//", re.I)
# 這些屬性的網址會被瀏覽器自動載入；<a href> 是讀者自己點的，不算
LOADING_ATTRS = {"src", "srcset", "poster", "data"}
# 從遠端載東西的寫法：script 裡的 import … from "…"、import("…")；style 裡的 @import、url(…)
# 原始頁自己定義 tokens.css 的變數：兩份對不上時，頁面會和其他頁長得不一樣
OWN_TOKEN = re.compile(r"--(paper|panel|rule|ink|ink-2|accent|font-ui|font-doc|font-code)\s*:")
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
                self.problems.append(f"<{tag} {k}=\"{v}\"> 會從外部載入：外部資源只有 build.py 放的 Mermaid 和 Panzoom，其他的改成內嵌或拿掉")
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
            self.problems.append(f"<{self.code_tag}> 裡從外部載入（{m.group(0)}…）：外部資源只有 build.py 放的 Mermaid 和 Panzoom，其他的改成內嵌或拿掉")
        if self.code_tag == "style" and OWN_TOKEN.search(data):
            self.problems.append(f"<style> 裡自己定義了配色或字體變數（{OWN_TOKEN.search(data).group(0)}…）：拿掉，build.py 會放 tokens.css")
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


def with_styles(html: str) -> str:
    """把 tokens.css 和 page.css 放在 <head> 的最前面：原始頁自己的 <style> 排在後面，補得上、也蓋得過。"""
    style = "<style>\n" + "".join((HERE / name).read_text(encoding="utf-8") for name in STYLES) + "</style>\n"
    for opener in (r"<head\b[^>]*>", r"<html\b[^>]*>", r"<!doctype[^>]*>"):
        m = re.search(opener, html, re.I)
        if m:
            return html[:m.end()] + "\n" + style + html[m.end():]
    return style + html


def build(html: str) -> str:
    """內嵌樣式；有 <pre class="mermaid"> 再在 </body> 前放 diagram.css、Mermaid 和 Panzoom 的 <script src>、diagram.js。"""
    html = with_styles(html)
    if not scan(html).diagrams:
        return html
    css = (HERE / "diagram.css").read_text(encoding="utf-8")
    js = (HERE / "diagram.js").read_text(encoding="utf-8")
    return before_body_end(html, "".join([
        "<style>\n", css, "</style>\n",
        MERMAID.tag, "\n",
        PANZOOM.tag, "\n",
        inline_script(js), "\n",
    ]))


find_browser = overflow.find_browser
render_dom = overflow.render


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
            problems.append(f"第 {i} 張圖沒畫出來，還是原始碼：Mermaid 沒執行（連不到 cdn.jsdelivr.net，或 integrity 對不上）")
        elif "Syntax error" in "".join(d["text"]):
            problems.append(f"第 {i} 張圖有語法錯誤，Mermaid 畫出的是錯誤圖示")
        elif not d["zoom"]:
            problems.append(f"第 {i} 張圖沒掛上縮放按鈕：diagram.js 沒跑完")
    return problems


def report(path, problems, what) -> None:
    print(f"{path}：{len(problems)} {what}", file=sys.stderr)
    for p in problems:
        print(f"  - {p}", file=sys.stderr)


def main(argv=None, render=render_dom) -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")  # Windows 終端機預設不是 UTF-8
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("src", type=Path)
    ap.add_argument("-o", "--out", type=Path)
    args = ap.parse_args(argv)
    src = args.src.read_text(encoding="utf-8")
    problems = lint(src)
    if problems:
        report(args.src, problems, "個問題，沒有產出")
        return 1
    out = args.out or args.src.with_name(args.src.stem.removesuffix("-src") + ".html")
    if out.resolve() == args.src.resolve():
        print(f"輸出會蓋掉原始檔 {args.src}：原始檔名要以 -src.html 結尾，或用 -o 指定", file=sys.stderr)
        return 1
    out.write_text(build(src), encoding="utf-8")
    diagrams = scan(src).diagrams
    doms = {}
    for width in overflow.WIDTHS:
        doms[width] = render(out, width)
        if doms[width] is None:
            print(out)
            print("找不到 Chrome 或 Edge，沒檢查圖有沒有畫出來、有沒有水平溢出：照 PAGE.md〈交出前〉的退路檢查", file=sys.stderr)
            return 1
    wide = [p for width, dom in doms.items() for p in overflow.problems(dom, width)]
    if wide:
        out.unlink()
        report(args.src, wide, "處水平溢出，沒有產出")
        return 1
    print(out)
    if not diagrams:
        return 0
    problems = render_problems(doms[overflow.WIDTHS[0]], diagrams)
    if problems:
        report(out, problems, "個渲染問題")
        return 1
    print(f"{diagrams} 張圖都畫出來了")
    return 0


if __name__ == "__main__":
    sys.exit(main())
