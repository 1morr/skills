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
JS = Path(__file__).resolve().parents[1] / "assets" / "lesson.js"

# 頁面分左右兩欄：左邊課件導讀，右邊例題和作業，各自捲動，連結可以跨欄跳
PANES = ("course", "problems")
# 每個 h2 段落的字數上限，單位見 text_units。整頁不設上限：課件導讀要教完宣告的每一頁，由頁數覆蓋把關
PER_SECTION = 2000

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "param", "source", "track", "wbr"}
# 這些元素裡的字不算散文：圖、表、公式、程式碼、答案紙樣本、課件譯文（長短由截圖決定）
SKIP_TAGS = {"figure", "table", "pre", "code", "style", "script", "svg", "math", "title"}
SKIP_CLASSES = {"sheet", "tr"}
# 題目欄裡有這些 class 的段落在教一題怎麼做，就要講為什麼、交代不明顯的數字從哪來
METHOD_CLASSES = {"calc", "sheet"}
# 題目欄裡會洩漏做法或答案的區塊，要收進 <details class="answer">，先自己做再打開
ANSWER_ONLY = {"calc", "sheet", "origin", "trap"}
# 「數字從哪來」表只列不明顯的數字：查表、要數的（n、df）、慣例、經驗法則、公式裡的常數。
# 題目直接給的、上面算出來的不列，算式就在旁邊
FROM_KINDS = {"table", "count", "convention", "rule", "constant"}
# 這兩種在材料或算式上看得到，要連到同一段裡圈出它的 figure 或算出它的 .calc
LINKED_FROM = {"table", "count"}

CJK = re.compile(r"[㐀-鿿豈-﫿]")
WORD = re.compile(r"[A-Za-z0-9]+")
PAGE_REF = re.compile(r"\bp{1,2}\.\s*\d+")
# data-pages 的一項：「檔名 p.3」或「檔名 p.1-8」
PAGES_ITEM = re.compile(r"^(.+?)\s+p\.\s*(\d+)(?:\s*-\s*(\d+))?$")
SECTION_REF = re.compile(r"§(\d+(?:\.\d+)?)")
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
        self.pages = None  # <body data-pages>：課件導讀要涵蓋的頁
        self.page_captions = []  # 每張 figure.page 的 figcaption
        self.stack = []  # [(tag, skip, classes)]
        self.prev = [set()]  # prev[d]：stack 第 d 層裡最後一個結束的子元素的 class
        self.sections = []  # 每個 h2 段落，欄位見 handle_starttag
        self.row = None  # 正在讀的「數字從哪來」表格列
        self.defs = []  # 開著的 .def：{"dfn": 個數, "test": 文字}
        self.calcs = []  # 開著的 .calc：{"formula": 文字, "subst": 文字}
        self.refs = []  # 內文提到的 §N、§N.M
        self.heading = None  # 正在讀的 h2 標題
        self.prelude = 0  # 第一個 h2 之前的字數
        self.figures = []  # 每個開著的 figure，欄位見 handle_starttag

    def skipping(self) -> bool:
        return any(skip for _, skip, _ in self.stack)

    def inside(self, tag) -> bool:
        return any(t == tag for t, _, _ in self.stack)

    def inside_class(self, name) -> bool:
        return any(name in c for _, _, c in self.stack)

    def in_origin(self) -> bool:
        return any(t == "table" and "origin" in c for t, _, c in self.stack)

    def in_answer(self) -> bool:
        return any(t == "details" and "answer" in c for t, _, c in self.stack)

    def pane(self):
        for _, _, c in reversed(self.stack):
            for name in PANES:
                if name in c:
                    return name
        return None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = classes(attrs)
        if tag == "body":
            self.pages = a.get("data-pages")
        if self.stack and self.stack[-1][0] == "body" and not (
                tag in ("script", "style") or (tag == "section" and cls & set(PANES))):
            self.problems.append(f'<body> 底下只能放 <section class="course"> 和 <section class="problems">（現在有 <{tag}>）：'
                                 "標題和範圍表放進課件欄的開頭")
        for key in ("src", "href", "data-zh"):
            if tag in ("img", "script", "link", "source") and a.get(key) and REMOTE.match(a[key]):
                self.problems.append(f"外部資源 <{tag} {key}={a[key]!r}>：頁面要能離線打開，請改成本機檔案")
        if tag == "img":
            if not self.figures:
                self.problems.append(f"圖片 {a.get('src', '')!r} 不在 <figure> 裡：每張圖都要有寫出處的 figcaption")
            elif a.get("data-zh"):
                self.figures[-1]["zh"] = True
        if tag in ("input", "textarea", "select") or (tag == "details" and "check" in cls):
            self.problems.append(f"頁面不能有練習（<{tag}>）：練習在對話裡做")
        if cls & ANSWER_ONLY and self.pane() == "problems" and not self.in_answer():
            what = ", ".join(sorted(cls & ANSWER_ONLY))
            self.problems.append(f'題目欄的 .{what} 要收在 <details class="answer"> 裡：先自己做，做完再打開')
        if tag == "figure":
            self.figures.append({"caption": "", "in_caption": False, "page": "page" in cls, "id": a.get("id") or "",
                                 "tr": "tr" in self.prev[len(self.stack)], "none": a.get("data-tr") == "none",
                                 "zh": False})
            if "page" in cls and not self.inside("details"):
                self.problems.append('整頁圖 <figure class="page"> 要收在 <details> 裡：正文逐塊講，整頁只在需要時打開')
        if tag == "figcaption" and self.figures:
            self.figures[-1]["in_caption"] = True
        if tag == "dfn":
            if self.defs:
                self.defs[-1]["dfn"] += 1
            else:
                self.problems.append('<dfn> 不在 class="def" 的定義框裡：術語要有「是什麼、怎樣才算、例子」')
        if "def" in cls:
            self.defs.append({"dfn": 0, "test": ""})
        if "calc" in cls:
            self.calcs.append({"formula": "", "subst": ""})
        if tag == "h2":
            self.heading = ""
            self.sections.append({"title": "", "units": 0, "method": False, "why": False, "origin": False,
                                  "figs": set(), "calcs": set(), "rows": [], "h3": 0, "why_refs": [], "calc_first": False,
                                  "pane": self.pane(), "depth": len(self.stack), "last": set(),
                                  "last_inner": set(), "recap": "recap" in cls})
        if self.sections:
            sec = self.sections[-1]
            sec["method"] |= bool(cls & METHOD_CLASSES)
            sec["why"] |= "why" in cls
            if "calc" in cls and not sec["origin"]:
                sec["calc_first"] = True  # 題目欄要先列出要用的數字從哪來，再代公式
            sec["origin"] |= "origin" in cls
            if tag == "h3":
                sec["h3"] += 1
            if tag == "figure" and a.get("id"):
                sec["figs"].add(a["id"])
            if "calc" in cls and a.get("id"):
                sec["calcs"].add(a["id"])
            if tag == "tr" and self.in_origin():
                self.row = {"text": "", "from": a.get("data-from"), "links": [], "cells": 0}
                sec["rows"].append(self.row)
            if self.row is not None:
                if tag == "td":
                    self.row["cells"] += 1
                if tag == "a" and (a.get("href") or "").startswith("#"):
                    self.row["links"].append(a["href"][1:])
        if tag in VOID:
            self.closed(len(self.stack), cls, set())
        else:
            self.stack.append((tag, tag in SKIP_TAGS or bool(cls & SKIP_CLASSES), cls))
            self.prev.append(set())

    def closed(self, depth, cls, inner):
        """第 depth 層有一個元素結束：記成那一層最後一個子元素；和 h2 同層的，就是這一段目前的最後一塊。
        inner 是這個元素自己最後一個子元素的 class（最後一塊是摺起來的答案時，要看它裡面的最後一塊）。"""
        self.prev[depth] = cls
        if self.sections and self.sections[-1]["depth"] == depth:
            self.sections[-1]["last"] = cls
            self.sections[-1]["last_inner"] = inner

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        # 容許省略結束標籤：往回找到同名的那層再收
        cls = None
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                cls = self.stack[i][2]
                inner = self.prev[i + 1] if len(self.prev) > i + 1 else set()
                del self.stack[i:]
                del self.prev[i + 1:]
                self.closed(i, cls, inner)
                break
        if cls is None:
            return
        if tag == "tr":
            self.row = None
        if "def" in cls and self.defs:
            d = self.defs.pop()
            if d["dfn"] != 1:
                self.problems.append(f'定義框裡有 {d["dfn"]} 個 <dfn>：一個 class="def" 只定義一個術語')
            if not d["test"].strip():
                self.problems.append('定義框沒有 class="test" 的「怎樣才算」：要寫讀者能拿來檢查的判斷標準')
        if "calc" in cls and self.calcs:
            c = self.calcs.pop()
            what = " ".join((c["formula"] + c["subst"]).split())[:30]
            if not re.search(r"[=＝]", c["formula"]):
                self.problems.append(f'計算「{what}」沒有寫出公式：.calc 裡要有含「=」的 class="formula"，不寫「用 §N 的公式」')
            if not re.search(r"\d", c["subst"]):
                self.problems.append(f'計算「{what}」沒有代入數字：.calc 裡要有 class="subst"，把數字代進公式')
        if tag == "figcaption" and self.figures:
            self.figures[-1]["in_caption"] = False
        if tag == "figure" and self.figures:
            fig = self.figures.pop()
            caption = fig["caption"]
            if fig["page"]:
                self.page_captions.append(caption)
            if not (fig["zh"] or fig["tr"] or fig["none"]):
                self.problems.append(f"圖片沒有翻譯（figure {fig['id']}）：用 crop.py cut --zh 產生翻譯圖，"
                                     '寫成 <img src="原圖" data-zh="翻譯圖">；做不出翻譯圖才在前面緊接著放 class="tr" 的譯文；'
                                     '圖上沒有要翻的字寫 data-tr="none"')
            if not PAGE_REF.search(caption):
                self.problems.append(f"figure 的出處沒有頁碼（figcaption：{caption.strip()[:40]!r}）：要寫檔名和 p.頁碼")
        if tag == "h2" and self.heading is not None:
            self.sections[-1]["title"] = self.heading.strip()
            self.heading = None

    def handle_data(self, data):
        if self.row is not None:
            self.row["text"] += data
        for fig in self.figures:
            if fig["in_caption"]:
                fig["caption"] += data
        if self.heading is not None:
            self.heading += data
        if self.defs and self.inside_class("test"):
            self.defs[-1]["test"] += data
        if self.calcs:
            if self.inside_class("formula"):
                self.calcs[-1]["formula"] += data
            elif self.inside_class("subst"):
                self.calcs[-1]["subst"] += data
        found = SECTION_REF.findall(data)
        self.refs += found
        if self.sections and self.inside_class("why"):
            self.sections[-1]["why_refs"] += found
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
    problems += coverage(p.pages, p.page_captions)
    problems += panes(p.sections)
    course = {f"{i}" for i, sec in enumerate(p.sections, 1) if sec["pane"] == "course"}
    for sec in p.sections:
        title, n = sec["title"][:30], sec["units"]
        if n > PER_SECTION:
            problems.append(f"§「{title}」有 {n} 字，每段上限 {PER_SECTION}：拆成幾段，或刪掉不是在教這頁的東西")
        if sec["pane"] == "problems" and sec["method"]:
            if not sec["why"]:
                problems.append(f'§「{title}」有計算或答案紙，卻沒有 class="why" 的區塊：要講這題在問什麼、用到課件哪裡')
            elif not any(r.split(".")[0] in course for r in sec["why_refs"]):
                problems.append(f"§「{title}」的「為什麼」沒有連到課件欄：寫出用到課件的 §N，讀者點了左欄就跳過去")
            if not sec["origin"]:
                problems.append(f'§「{title}」有計算或答案紙，卻沒有 class="origin" 的「數字從哪來」表')
            elif sec["calc_first"]:
                problems.append(f"§「{title}」的「數字從哪來」表排在算式後面：先列出要用的數字從哪來，再代公式，"
                                "讀者算到那一步時才知道每個數字的來源")
        ends = "summary" in sec["last"] or ("answer" in sec["last"] and "summary" in sec["last_inner"])
        if not sec["recap"] and not ends:
            problems.append(f'§「{title}」最後一塊不是 class="summary" 的「這段記住」：每段結尾都要有總結'
                            "（題目欄可以放在 details.answer 的最後）")
        for row in sec["rows"]:
            if not row["cells"]:  # 表頭
                continue
            what = " ".join(row["text"].split())[:30]
            missing = [x for x in row["links"] if x not in sec["figs"] | sec["calcs"]]
            if row["from"] not in FROM_KINDS:
                problems.append(f'§「{title}」數字從哪來的「{what}」要寫 data-from="{"|".join(sorted(FROM_KINDS))}"：'
                                "這張表只列不明顯的數字，題目直接給的、上面算出來的不用列")
            elif missing:
                problems.append(f"§「{title}」數字從哪來的「{what}」連到 #{missing[0]}，這一段沒有這個 id 的 figure 或 .calc")
            elif row["from"] in LINKED_FROM and not row["links"]:
                problems.append(f"§「{title}」數字從哪來的「{what}」沒有附圖：連到這一段圈出它的 figure，"
                                '或算出它的 .calc（<a href="#id">）')
    if not p.sections or not p.sections[-1]["recap"]:
        problems.append('最後一段要是 <h2 class="recap"> 的整個 topic 總結')
    labels = {f"{i}" for i in range(1, len(p.sections) + 1)}
    labels |= {f"{i}.{j}" for i, sec in enumerate(p.sections, 1) for j in range(1, sec["h3"] + 1)}
    for ref in sorted(set(p.refs) - labels):
        problems.append(f"內文提到 §{ref}，但頁面沒有這一段：§ 編號由 build 依 h2、h3 的順序產生")
    return problems


def panes(sections) -> list:
    """每個 h2 都在課件欄或題目欄裡，兩欄都要有，課件欄在前。"""
    problems, seen = [], []
    for sec in sections:
        if sec["pane"] is None:
            problems.append(f'§「{sec["title"][:30]}」不在 <section class="course"> 或 <section class="problems"> 裡')
        elif sec["pane"] == "course" and "problems" in seen:
            problems.append(f"§「{sec['title'][:30]}」在課件欄，卻排在題目欄後面：課件欄在前")
        seen.append(sec["pane"])
    for name, label in (("course", "課件欄"), ("problems", "題目欄")):
        if name not in seen:
            problems.append(f'頁面沒有{label}：要有 <section class="{name}">，裡面至少一個 <h2>')
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


HEADING = re.compile(r"<h([23])(\s[^>]*)?>(.*?)</h\1\s*>", re.I | re.S)
TAG = re.compile(r"<[^>]+>")


def number_headings(src: str):
    """替 h2、h3 加上 §編號和錨點。回傳 (新的 HTML, {編號: 錨點})。"""
    counters = [0, 0]
    anchors = {}

    def repl(m):
        level, attrs, inner = int(m.group(1)), m.group(2) or "", m.group(3)
        if level == 2:
            counters[0] += 1
            counters[1] = 0
            label, anchor = f"{counters[0]}", f"s{counters[0]}"
        else:
            counters[1] += 1
            label, anchor = f"{counters[0]}.{counters[1]}", f"s{counters[0]}-{counters[1]}"
        own = re.search(r"""\bid\s*=\s*["']?([^"'\s>]+)""", attrs)
        if own:
            anchor = own.group(1)
        else:
            attrs += f' id="{anchor}"'
        anchors[label] = anchor
        return f'<h{level}{attrs}><span class="num">§{label}</span> {inner}</h{level}>'

    return HEADING.sub(repl, src), anchors


def link_refs(src: str, anchors: dict) -> str:
    """把內文的 §N、§N.M 換成連到那一段的連結；標籤裡、<a> 裡、標題編號不動。"""
    out, depth_a, in_num = [], 0, False
    for part in re.split(r"(<[^>]+>)", src):
        if part.startswith("<"):
            low = part.lower()
            if re.match(r"<a[\s>]", low):
                depth_a += 1
            elif low.startswith("</a"):
                depth_a = max(0, depth_a - 1)
            elif re.match(r"<span[^>]*class=\"num\"", low):
                in_num = True
            elif low.startswith("</span") and in_num:
                in_num = False
            out.append(part)
        elif depth_a or in_num:
            out.append(part)
        else:
            out.append(SECTION_REF.sub(
                lambda m: f'<a href="#{anchors[m.group(1)]}">{m.group(0)}</a>' if m.group(1) in anchors else m.group(0),
                part))
    return "".join(out)


NUMBERED_H2 = re.compile(r'<h2([^>]*)><span class="num">§(\d+)</span> (.*?)</h2\s*>', re.I | re.S)
ID_ATTR = re.compile(r"""\bid\s*=\s*["']?([^"'\s>]+)""")


def pane_start(src: str, name: str) -> int:
    """<section class="name"> 開始標籤結束的位置；沒有就回傳 -1。"""
    m = re.search(rf"""<section\b[^>]*\bclass\s*=\s*["'][^"']*\b{name}\b[^"']*["'][^>]*>""", src, re.I)
    return m.end() if m else -1


def add_toc(src: str) -> str:
    """每一欄的第一個 h2 前面放一份只列這一欄 h2 的目錄，預設摺起來。"""
    cut = pane_start(src, "problems")
    parts = [src[:cut], src[cut:]] if cut >= 0 else [src]
    out = []
    for part in parts:
        items = "".join(f'<li><a href="#{ID_ATTR.search(m.group(1)).group(1)}">§{m.group(2)} '
                        f'{" ".join(TAG.sub("", m.group(3)).split())}</a></li>'
                        for m in NUMBERED_H2.finditer(part))
        if items:
            nav = f'<details class="toc"><summary>目錄</summary><ol>{items}</ol></details>\n'
            part = re.sub(r"<h2[\s>]", lambda m: nav + m.group(0), part, count=1, flags=re.I)
        out.append(part)
    return "".join(out)


def add_toolbars(src: str) -> str:
    """課件欄頂端放「圖片中文／原文」切換（有翻譯圖才放），題目欄頂端放「展開全部做法」。"""
    bars = {"problems": '<button type="button" data-act="answers">展開全部做法</button>'}
    if re.search(r"<img\b[^>]*\bdata-zh\s*=", src, re.I):
        bars["course"] = '<button type="button" data-act="lang">圖片：中文（點這裡全部換成原文）</button>'
    for name in ("problems", "course"):  # 先插後面那欄，前面那欄的位置才不會變
        at = pane_start(src, name)
        if at >= 0 and name in bars:
            src = src[:at] + f'<div class="bar">{bars[name]}</div>' + src[at:]
    return src


IMG_TAG = re.compile(r"<img\b[^>]*>", re.I)
ZH_ATTR = re.compile(r"""\sdata-zh\s*=\s*["']([^"']+)["']""", re.I)
SRC_ATTR = re.compile(r"""(\ssrc\s*=\s*["'])([^"']+)(["'])""", re.I)
CLASS_ATTR = re.compile(r"""(\sclass\s*=\s*["'])""", re.I)


def split_bilingual(src: str) -> str:
    """<img src="原圖" data-zh="翻譯圖"> 拆成兩張：翻譯圖（class zh）和原圖（class en），點圖切換。"""
    def with_class(tag, name):
        if CLASS_ATTR.search(tag):
            return CLASS_ATTR.sub(lambda m: m.group(1) + name + " ", tag, count=1)
        return re.sub(r"^<img\b", f'<img class="{name}"', tag, flags=re.I)

    def repl(m):
        tag = m.group(0)
        zh = ZH_ATTR.search(tag)
        if not zh:
            return tag
        base = ZH_ATTR.sub("", tag)
        zh_tag = SRC_ATTR.sub(lambda s: s.group(1) + zh.group(1) + s.group(3), base, count=1)
        return with_class(zh_tag, "zh") + with_class(base, "en")

    return IMG_TAG.sub(repl, src)


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


def inject_assets(src: str) -> str:
    style = f"<style>\n{CSS.read_text(encoding='utf-8')}</style>\n"
    if re.search(r"</head>", src, re.I):
        src = re.sub(r"</head>", lambda _: style + "</head>", src, count=1, flags=re.I)
    else:
        src = style + src
    script = f"<script>\n{JS.read_text(encoding='utf-8')}</script>\n"
    if re.search(r"</body>", src, re.I):
        return re.sub(r"</body>", lambda _: script + "</body>", src, count=1, flags=re.I)
    return src + script


def build(src: str, base: Path) -> str:
    src, anchors = number_headings(src)
    src = add_toolbars(add_toc(link_refs(src, anchors)))
    return inject_assets(inline_images(split_bilingual(src), base))


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
