"""把講解頁的原始 HTML 組成單一檔案，並檢查寫作規則；規則不過就不產出。

    python build.py <src.html> [-o <out.html>]

只用標準函式庫，CI 才能直接跑測試。
"""

import argparse
import base64
import mimetypes
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

CSS = Path(__file__).resolve().parents[1] / "assets" / "lesson.css"

# (每個 h2 段落上限, 整頁上限)，單位見 text_units
LIMITS = {"rush": (900, 12000), "learn": (600, 3000)}

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "param", "source", "track", "wbr"}
# 這些元素裡的字不算散文：圖、表、公式、程式碼、答案紙樣本
SKIP_TAGS = {"figure", "table", "pre", "code", "style", "script", "svg", "math", "title"}
SKIP_CLASSES = {"sheet"}

CJK = re.compile(r"[㐀-鿿豈-﫿]")
WORD = re.compile(r"[A-Za-z0-9]+")
PAGE_REF = re.compile(r"\bp{1,2}\.\s*\d+")
REMOTE = re.compile(r"^\s*(https?:)?//", re.I)


def text_units(s: str) -> int:
    """一個中日韓字算 1，一個英文字或數字串算 1。"""
    return len(CJK.findall(s)) + len(WORD.findall(s))


def classes(attrs) -> set:
    return set((dict(attrs).get("class") or "").split())


class Lint(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.problems = []
        self.mode = None
        self.stack = []  # [(tag, skip)]
        self.sections = []  # [[標題, 字數]]
        self.heading = None  # 正在讀的 h2 標題
        self.prelude = 0  # 第一個 h2 之前的字數
        self.figures = []  # 每個開著的 figure：[figcaption 文字, 是否在 figcaption 內]
        self.checks = 0

    def skipping(self) -> bool:
        return any(skip for _, skip in self.stack)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = classes(attrs)
        if tag == "body":
            self.mode = a.get("data-mode")
        for key in ("src", "href"):
            if tag in ("img", "script", "link", "source") and a.get(key) and REMOTE.match(a[key]):
                self.problems.append(f"外部資源 <{tag} {key}={a[key]!r}>：頁面要能離線打開，請改成本機檔案")
        if tag == "img" and not self.figures:
            self.problems.append(f"圖片 {a.get('src', '')!r} 不在 <figure> 裡：每張圖都要有寫出處的 figcaption")
        if tag in ("input", "textarea", "select"):
            if self.mode == "rush":
                self.problems.append(f"rush 模式不能有 <{tag}>：趕時間時不讓使用者做練習")
        if tag == "details" and "check" in cls:
            self.checks += 1
            if self.mode == "rush":
                self.problems.append("rush 模式不能有 <details class=\"check\"> 回想題")
        if tag == "figure":
            self.figures.append(["", False])
        if tag == "figcaption" and self.figures:
            self.figures[-1][1] = True
        if tag == "h2":
            self.heading = ""
            self.sections.append(["", 0])
        if tag not in VOID:
            self.stack.append((tag, tag in SKIP_TAGS or bool(cls & SKIP_CLASSES)))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        # 容許省略結束標籤：往回找到同名的那層再收
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break
        if tag == "figcaption" and self.figures:
            self.figures[-1][1] = False
        if tag == "figure" and self.figures:
            caption, _ = self.figures.pop()
            if not PAGE_REF.search(caption):
                self.problems.append(f"figure 的出處沒有頁碼（figcaption：{caption.strip()[:40]!r}）：要寫檔名和 p.頁碼")
        if tag == "h2" and self.heading is not None:
            self.sections[-1][0] = self.heading.strip()
            self.heading = None

    def handle_data(self, data):
        for fig in self.figures:
            if fig[1]:
                fig[0] += data
        if self.heading is not None:
            self.heading += data
        if self.skipping():
            return
        n = text_units(data)
        if self.sections:
            self.sections[-1][1] += n
        else:
            self.prelude += n


def lint(src: str) -> list:
    p = Lint()
    p.feed(src)
    p.close()
    problems = list(p.problems)
    if p.mode not in LIMITS:
        problems.insert(0, f'<body> 要有 data-mode="rush" 或 "learn"（現在是 {p.mode!r}）')
        return problems
    per, total = LIMITS[p.mode]
    for title, n in p.sections:
        if n > per:
            problems.append(f"§「{title[:30]}」有 {n} 字，{p.mode} 模式每段上限 {per}：砍掉地圖外的東西，或拆段")
    whole = p.prelude + sum(n for _, n in p.sections)
    if whole > total:
        problems.append(f"整頁 {whole} 字，{p.mode} 模式上限 {total}：這是在寫參考書，不是在教")
    if p.mode == "learn" and p.checks == 0:
        problems.append('learn 模式至少要有一題 <details class="check"> 回想題')
    return problems


def number_headings(src: str) -> str:
    counters = [0, 0]

    def repl(m):
        level, attrs = int(m.group(1)), m.group(2) or ""
        if level == 2:
            counters[0] += 1
            counters[1] = 0
            label, anchor = f"§{counters[0]}", f"s{counters[0]}"
        else:
            counters[1] += 1
            label, anchor = f"§{counters[0]}.{counters[1]}", f"s{counters[0]}-{counters[1]}"
        if not re.search(r"\bid\s*=", attrs):
            attrs += f' id="{anchor}"'
        return f'<h{level}{attrs}><span class="num">{label}</span> '

    return re.sub(r"<h([23])(\s[^>]*)?>", repl, src)


def inline_images(src: str, base: Path) -> str:
    def repl(m):
        path = m.group(2)
        if path.startswith("data:"):
            return m.group(0)
        f = (base / path).resolve()
        if not f.is_file():
            raise SystemExit(f"找不到圖片：{f}")
        mime = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
        data = base64.b64encode(f.read_bytes()).decode()
        return f"{m.group(1)}data:{mime};base64,{data}{m.group(3)}"

    return re.sub(r'(<img\b[^>]*?\bsrc=")([^"]+)(")', repl, src)


def inject_css(src: str) -> str:
    style = f"<style>\n{CSS.read_text(encoding='utf-8')}</style>\n"
    if re.search(r"</head>", src, re.I):
        return re.sub(r"</head>", lambda _: style + "</head>", src, count=1, flags=re.I)
    return style + src


def build(src: str, base: Path) -> str:
    return inject_css(inline_images(number_headings(src), base))


def main(argv=None) -> int:
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
    out.write_text(build(src, args.src.parent), encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
