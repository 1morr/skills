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

MODES = {"read", "learn"}
# 每個 h2 段落的字數上限，單位見 text_units。整頁不設上限：課件導讀要教完宣告的每一頁，由頁數覆蓋把關
PER_SECTION = 2000

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "param", "source", "track", "wbr"}
# 這些元素裡的字不算散文：圖、表、公式、程式碼、答案紙樣本、課件譯文（長短由截圖決定）
SKIP_TAGS = {"figure", "table", "pre", "code", "style", "script", "svg", "math", "title"}
SKIP_CLASSES = {"sheet", "tr"}
# 有這些 class 的段落在教一個算法，就要講為什麼、交代每個數字從哪來
METHOD_CLASSES = {"calc", "sheet"}
# 「數字從哪來」表裡，在任何材料上都看不到、所以不必附圖的數字
NO_FIGURE_FROM = {"calc", "convention", "constant"}

CJK = re.compile(r"[㐀-鿿豈-﫿]")
WORD = re.compile(r"[A-Za-z0-9]+")
PAGE_REF = re.compile(r"\bp{1,2}\.\s*\d+")
# data-pages 的一項：「檔名 p.3」或「檔名 p.1-8」
PAGES_ITEM = re.compile(r"^(.+?)\s+p\.\s*(\d+)(?:\s*-\s*(\d+))?$")
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
        self.pages = None  # <body data-pages>：課件導讀要涵蓋的頁
        self.page_captions = []  # 每張 figure.page 的 figcaption
        self.stack = []  # [(tag, skip, classes)]
        self.prev = [set()]  # prev[d]：stack 第 d 層裡最後一個結束的子元素的 class
        self.sections = []  # [{"title", "units", "method", "why", "origin", "figs", "rows"}]
        self.row = None  # 正在讀的「數字從哪來」表格列
        self.heading = None  # 正在讀的 h2 標題
        self.prelude = 0  # 第一個 h2 之前的字數
        self.figures = []  # 每個開著的 figure：[figcaption 文字, 是否在 figcaption 內, 是否整頁圖]

    def skipping(self) -> bool:
        return any(skip for _, skip, _ in self.stack)

    def inside(self, tag) -> bool:
        return any(t == tag for t, _, _ in self.stack)

    def in_origin(self) -> bool:
        return any(t == "table" and "origin" in c for t, _, c in self.stack)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = classes(attrs)
        if tag == "body":
            self.mode = a.get("data-mode")
            self.pages = a.get("data-pages")
        for key in ("src", "href"):
            if tag in ("img", "script", "link", "source") and a.get(key) and REMOTE.match(a[key]):
                self.problems.append(f"外部資源 <{tag} {key}={a[key]!r}>：頁面要能離線打開，請改成本機檔案")
        if tag == "img" and not self.figures:
            self.problems.append(f"圖片 {a.get('src', '')!r} 不在 <figure> 裡：每張圖都要有寫出處的 figcaption")
        if tag in ("input", "textarea", "select") or (tag == "details" and "check" in cls):
            self.problems.append(f"頁面不能有練習（<{tag}>）：read 不出練習，learn 的練習在對話裡做")
        if "sheet" in cls and self.mode == "learn" and not self.inside("details"):
            self.problems.append("learn 模式的答案紙要收在 <details> 裡：使用者要先在對話裡自己做")
        sec = self.sections[-1] if self.sections else None
        if tag == "figure":
            self.figures.append(["", False, "page" in cls])
            # 同一段已經放過整頁圖和整頁譯文，之後截這頁的小塊不用再翻
            translated = sec is not None and sec["page"]
            if a.get("data-tr") != "none" and not translated and "tr" not in self.prev[len(self.stack)]:
                self.problems.append(f"圖片前面沒有譯文（figure {a.get('id') or ''}）：先放 class=\"tr\" 的譯文，再放原圖；"
                                     '圖上沒有要翻的字才寫 data-tr="none"')
        if tag == "figcaption" and self.figures:
            self.figures[-1][1] = True
        if tag == "h2":
            self.heading = ""
            self.sections.append({"title": "", "units": 0, "method": False, "why": False, "origin": False,
                                  "page": False, "figs": set(), "rows": []})
        if self.sections:
            sec = self.sections[-1]
            sec["method"] |= bool(cls & METHOD_CLASSES)
            sec["why"] |= "why" in cls
            sec["origin"] |= "origin" in cls
            sec["page"] |= tag == "figure" and "page" in cls
            if tag == "figure" and a.get("id"):
                sec["figs"].add(a["id"])
            if tag == "tr" and self.in_origin():
                self.row = {"text": "", "from": a.get("data-from"), "links": [], "cells": 0}
                sec["rows"].append(self.row)
            if self.row is not None:
                if tag == "td":
                    self.row["cells"] += 1
                if tag == "a" and (a.get("href") or "").startswith("#"):
                    self.row["links"].append(a["href"][1:])
        if tag in VOID:
            self.prev[len(self.stack)] = cls
        else:
            self.stack.append((tag, tag in SKIP_TAGS or bool(cls & SKIP_CLASSES), cls))
            self.prev.append(set())

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        # 容許省略結束標籤：往回找到同名的那層再收
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                cls = self.stack[i][2]
                del self.stack[i:]
                del self.prev[i + 1:]
                self.prev[i] = cls
                break
        if tag == "tr":
            self.row = None
        if tag == "figcaption" and self.figures:
            self.figures[-1][1] = False
        if tag == "figure" and self.figures:
            caption, _, whole = self.figures.pop()
            if whole:
                self.page_captions.append(caption)
            if not PAGE_REF.search(caption):
                self.problems.append(f"figure 的出處沒有頁碼（figcaption：{caption.strip()[:40]!r}）：要寫檔名和 p.頁碼")
        if tag == "h2" and self.heading is not None:
            self.sections[-1]["title"] = self.heading.strip()
            self.heading = None

    def handle_data(self, data):
        if self.row is not None:
            self.row["text"] += data
        for fig in self.figures:
            if fig[1]:
                fig[0] += data
        if self.heading is not None:
            self.heading += data
        if self.skipping():
            return
        n = text_units(data)
        if self.sections:
            self.sections[-1]["units"] += n
        else:
            self.prelude += n


def lint(src: str) -> list:
    p = Lint()
    p.feed(src)
    p.close()
    problems = list(p.problems)
    if p.mode not in MODES:
        problems.insert(0, f'<body> 要有 data-mode="read" 或 "learn"（現在是 {p.mode!r}）')
        return problems
    problems += coverage(p.pages, p.page_captions)
    for sec in p.sections:
        title, n = sec["title"][:30], sec["units"]
        if n > PER_SECTION:
            problems.append(f"§「{title}」有 {n} 字，每段上限 {PER_SECTION}：拆成幾段，或刪掉不是在教這頁的東西")
        if sec["page"] and not sec["why"]:
            problems.append(f'§「{title}」是課件導讀頁，卻沒有 class="why" 的區塊：要講這頁的東西為什麼這樣、什麼意思')
        elif sec["method"] and not sec["why"]:
            problems.append(f'§「{title}」有計算或答案紙，卻沒有 class="why" 的區塊：要講這個方法在回答什麼、公式為什麼長這樣')
        if sec["method"] and not sec["origin"]:
            problems.append(f'§「{title}」有計算或答案紙，卻沒有 class="origin" 的「數字從哪來」表')
        for row in sec["rows"]:
            if not row["cells"]:  # 表頭
                continue
            what = " ".join(row["text"].split())[:30]
            missing = [x for x in row["links"] if x not in sec["figs"]]
            if missing:
                problems.append(f"§「{title}」數字從哪來的「{what}」連到 #{missing[0]}，這一段沒有這個 id 的 figure")
            elif not row["links"] and row["from"] not in NO_FIGURE_FROM:
                problems.append(f"§「{title}」數字從哪來的「{what}」沒有附圖：連到這一段圈出它的 figure（<a href=\"#id\">），"
                                '材料上看不到的數字才寫 data-from="calc|convention|constant"')
    return problems


def coverage(pages, captions) -> list:
    """data-pages 宣告的每一頁，都要有一張 figcaption 寫著那個檔名和頁碼的 figure.page。"""
    if not (pages or "").strip():
        return ['<body> 要有 data-pages，宣告課件導讀涵蓋哪些頁，例如 "Classnote Topic 3 p.1-8; Topic 4 Summary p.1-10"']
    problems = []
    for item in filter(None, (x.strip() for x in pages.split(";"))):
        m = PAGES_ITEM.match(item)
        if not m:
            problems.append(f"data-pages 的「{item}」看不懂：要寫成「檔名 p.3」或「檔名 p.1-8」，多份用 ; 分開")
            continue
        name, first = m.group(1), int(m.group(2))
        for n in range(first, int(m.group(3) or first) + 1):
            page = re.compile(rf"\bp\.\s*{n}(?!\d)")
            if not any(name in c and page.search(c) for c in captions):
                problems.append(f'課件導讀少了「{name} p.{n}」：要有一張 figcaption 寫著它的 <figure class="page"> 整頁圖')
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
