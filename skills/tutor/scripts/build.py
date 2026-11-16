"""把導讀頁的原始 HTML 組成單一檔案，並檢查寫作規則；規則不過就不產出。

原始檔分兩部：<section class="course"> 是講義導讀，<section class="problems"> 是例題和作業。
組好的頁是一條捲軸：左邊固定的目錄、中間正文、右邊的對照欄（§ 連結、速查卡、名詞表、查表都在那裡打開）。

    python build.py <src.html> [-o <out.html>]

組好之後用本機的 Chrome 或 Edge 在寬螢幕和手機寬各量一次水平溢出（pages/scripts/overflow.py）：
有溢出就不產出，逐條印出哪個元素超出幾 px；找不到瀏覽器只提醒。
寬螢幕再多查一件事：正文裡的公式、算式、表格比正文欄寬時，會在自己那一行橫向捲動，右邊看起來就是被切掉，
這也不產出（手機寬照樣可以捲）。

只用標準函式庫，CI 才能直接跑測試。
"""

import argparse
import base64
import html
import json
import mimetypes
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

# 共用的水平溢出量測在 plugin 根目錄的 pages/scripts/
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "pages" / "scripts"))
import overflow  # noqa: E402

CSS = Path(__file__).resolve().parents[1] / "assets" / "lesson.css"
JS = Path(__file__).resolve().parents[1] / "assets" / "lesson.js"

# 原始檔的兩部：講義導讀在前，例題和作業在後；組好的頁把它們接成一條捲軸
PANES = ("course", "problems")
# 每個 h2 段落的字數上限，單位見 text_units：一頁講義講到這麼長，就該拆成兩段。
# 整頁不設上限、也不提醒：講解要細，趕時間的讀者用「只看重點」和速查卡
PER_SECTION = 4000
# 一句話的字數上限：讀者是零基礎，一句一件事
MAX_SENTENCE = 50
# 估閱讀時間：一分鐘讀幾個字（單位見 text_units）。教材要邊讀邊算，比一般閱讀慢
UNITS_PER_MIN = 80
# 速查卡的公式行裡，<mspace> 寬到幾 em 就算是把兩條公式接在同一行（標籤和公式之間的小空隙不算）
JOIN_GAP_EM = 1
# 題目欄的型態：calc（算題，要有數字從哪來、算式）或 text（文科：答案是要點和句子）
KINDS = ("calc", "text")

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

# 定義框的三種（data-kind）：要分辨的東西、一個量、一個方法。每種三格 {class: 頁面上的名字}，必填的那一格排第一
DEF_KINDS = {"class": {"test": "怎樣才算", "yes": "是", "no": "不是"},
             "quantity": {"how": "怎麼算", "big": "大代表", "small": "小代表"},
             "method": {"when": "什麼時候用", "io": "做什麼", "without": "不用會怎樣"}}
DEF_SLOTS = {name for slots in DEF_KINDS.values() for name in slots}
# 這些框的標籤由樣式加上；內文開頭再寫一次就重複了
LABELS = {"trap": ("常見錯誤",), "summary": ("這段記住", "這頁重點", "這題記住"), "def": ("定義",),
          "sheet": ("答案紙上寫這樣",), "uses": ("這題用到",), "yes": ("是：", "是:"), "no": ("不是：", "不是:"),
          **{name: (label,) for slots in DEF_KINDS.values() for name, label in slots.items() if name not in ("yes", "no")}}
# 提醒（不擋產出）：沒有摺起來的圖的張數
FIGURE_WARN = 60

CJK = re.compile(r"[㐀-鿿豈-﫿]")
WORD = re.compile(r"[A-Za-z0-9]+")
PAGE_REF = re.compile(r"\bp{1,2}\.\s*\d+")
# data-pages 的一項：「檔名 p.3」或「檔名 p.1-8」
PAGES_ITEM = re.compile(r"^(.+?)\s+p\.\s*(\d+)(?:\s*-\s*(\d+))?$")
SECTION_REF = re.compile(r"§(\d+(?:\.\d+)?)")
REMOTE = re.compile(r"^\s*(https?:)?//", re.I)
# 把讀者推去看別的 topic 的句子：前置知識要在原地從零教，把那一頁課件截過來
PREREQ = re.compile(r"(Topic\s*\d+\s*(學過|教過|講過|的東西|的內容|已經)|見\s*Topic\s*\d|[上前]一?個\s*topic|"
                    r"之前(學|教|講)過|前面的\s*topic|上學期)", re.I)
# 「不考」的說法：只有老師明示過才能寫，而且要寫在帶 data-evidence（出處）的元素裡
NOT_EXAMINED = re.compile(r"(?<!考)不(?:會直接|會|用)?考(?![試慮量])|看懂就好")
# 題型代號：題型表每一列一個，練習頁和模擬卷的題目用它對回題型
SLUG = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
SENTENCE_END = re.compile(r"[。！？；!?]|\.(?=\s|$)")  # 英文句點後面要有空白，小數點不算
# 句子在這些元素的邊界結束
BLOCK = {"p", "li", "div", "h1", "h2", "h3", "h4", "summary", "dd", "dt", "caption", "td", "th", "section", "aside",
         "blockquote"}


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
        self.defs = []  # 開著的 .def：{"dfn": 個數, "kind": data-kind, "slots": {格子的 class: 文字}}
        self.calcs = []  # 開著的 .calc：{"formula": 文字, "subst": 文字}
        self.refs = []  # 內文提到的 §N、§N.M
        self.heading = None  # 正在讀的 h2 標題
        self.prelude = 0  # 第一個 h2 之前的字數
        self.figures = []  # 每個開著的 figure，欄位見 handle_starttag
        self.kind = "calc"  # <body data-problems>
        self.sentence = ""  # 正在讀的一句散文
        self.in_heading = 0  # 在 h2/h3 裡（標題的頁碼不算「先舉例」）
        self.example = False  # 這個 h2/h3 塊裡，定義框之前有沒有用數字舉過例
        self.types = None  # 題目欄開頭的題型表提到的 §；None 表示沒有這張表
        self.problems_h2 = False  # 題目欄已經有 h2 了（題型表要在它前面）
        self.type_row = None  # 正在讀的題型表列：{"slug", "cells", "text"}
        self.type_slugs = []  # 題型表每一列的 data-type
        self.boxes = []  # 開著的有標籤的框：{"depth", "labels", "first"}
        self.shown_figures = 0  # 沒有摺在 <details> 裡的圖
        self.checks = []  # 講義那部開著的自測：{"ask": summary 的字, "refs": 答案裡的 § 個數}
        self.whys = []  # 開著的 .why：{"state": start|q|done|bad, "q": 開頭那個 <b> 裡的字}

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
            self.kind = a.get("data-problems") or "calc"
            if self.kind not in KINDS:
                self.problems.append(f'<body data-problems="{self.kind}"> 看不懂：只能是 {" 或 ".join(KINDS)}')
        if self.stack and self.stack[-1][0] == "body" and not (
                tag in ("script", "style") or (tag == "section" and cls & set(PANES)) or (tag == "aside" and "panel" in cls)):
            self.problems.append(f'<body> 底下只能放 <section class="course">、<section class="problems"> 和查表面板 '
                                 f'<aside class="panel">（現在有 <{tag}>）：標題和範圍表放進課件欄的開頭')
        for name in cls & set(LABELS):
            self.boxes.append({"depth": len(self.stack), "labels": LABELS[name], "first": True})
        if "ans" in cls and self.calcs:
            self.calcs[-1]["ans"] = True
        if tag == "b" and self.whys and self.whys[-1]["state"] == "start":
            self.whys[-1]["state"] = "q"
        if "why" in cls:
            self.whys.append({"state": "start", "q": ""})
        if tag == "details" and "check" in cls and self.pane() == "course":
            self.checks.append({"ask": "", "refs": 0, "depth": len(self.stack)})
        for key in ("src", "href", "data-zh"):
            if tag in ("img", "script", "link", "source") and a.get(key) and REMOTE.match(a[key]):
                self.problems.append(f"外部資源 <{tag} {key}={a[key]!r}>：頁面要能離線打開，請改成本機檔案")
        if tag == "img":
            if not self.figures:
                self.problems.append(f"圖片 {a.get('src', '')!r} 不在 <figure> 裡：每張圖都要有寫出處的 figcaption")
            elif a.get("data-zh"):
                self.figures[-1]["zh"] = True
        if tag in ("input", "textarea", "select"):
            self.problems.append(f'導讀頁不能有輸入框（<{tag}>）：自測用 <details class="check">，整題的練習放練習頁')
        if tag in BLOCK:
            self.end_sentence()
        if tag in ("h2", "h3"):
            self.in_heading += 1
            self.example = False
        if tag == "table" and "types" in cls and self.pane() == "problems" and not self.problems_h2:
            self.types = []
            if not self.inside_class("cheat"):
                self.problems.append('題型表要放在速查卡 <div class="cheat"> 裡：題目欄開頭一張可以單獨列印的卡，'
                                     "題型表、要背的公式、判斷規則都在上面")
        if cls & ANSWER_ONLY and self.pane() == "problems" and not self.in_answer():
            what = ", ".join(sorted(cls & ANSWER_ONLY))
            self.problems.append(f'題目欄的 .{what} 要收在 <details class="answer"> 裡：先自己做，做完再打開')
        if tag == "mspace" and self.inside_class("cheat") and self.inside_class("formula"):
            gap = re.fullmatch(r"\s*(\d*\.?\d+)\s*em\s*", a.get("width") or "")
            if gap and float(gap.group(1)) >= JOIN_GAP_EM:
                self.problems.append(f'速查卡的公式一條一行：這一行用 <mspace width="{a["width"].strip()}"> 把好幾條接在一起，'
                                     '在對照欄和手機上右邊會被切掉。每條公式各寫一個 <div class="formula">')
        if tag == "figure":
            self.shown_figures += not self.inside("details")
            if self.inside_class("panel") and not (a.get("data-tab") or "").strip():
                self.problems.append("查表面板的 figure 沒有 data-tab：寫分頁名稱，例如「Z 表」")
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
            kind = (a.get("data-kind") or "class").strip()
            if kind not in DEF_KINDS:
                self.problems.append(f'定義框的 data-kind="{kind}" 看不懂：只能是 {"、".join(DEF_KINDS)}'
                                     "（要分辨的東西、一個量、一個方法）")
                kind = "class"
            self.defs.append({"dfn": 0, "kind": kind, "slots": {}, "term": "", "example": self.example})
        if "calc" in cls:
            self.calcs.append({"formula": "", "subst": "", "ans": False})
        if tag == "h2":
            self.heading = ""
            if self.pane() == "problems":
                self.problems_h2 = True
            self.sections.append({"title": "", "units": 0, "method": False, "why": False, "origin": False,
                                  "figs": set(), "calcs": set(), "rows": [], "h3": 0, "uses": False, "uses_refs": [], "calc_first": False,
                                  "pane": self.pane(), "depth": len(self.stack), "last": set(),
                                  "last_inner": set(), "recap": "recap" in cls, "refs": [], "done": False,
                                  "keys": False})
        if self.sections:
            sec = self.sections[-1]
            sec["method"] |= bool(cls & METHOD_CLASSES)
            sec["why"] |= "why" in cls
            sec["uses"] |= "uses" in cls
            if "summary" in cls and not sec["h3"]:
                sec["keys"] = True  # 課件欄：重點放在這一頁的開頭，第一個 h3 之前
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
        if tag == "tr" and self.types is not None and self.inside_class("types"):
            self.type_row = {"slug": (a.get("data-type") or "").strip(), "cells": 0, "text": ""}
        if tag == "td" and self.type_row is not None:
            self.type_row["cells"] += 1
        if (a.get("data-evidence") or "").strip():
            cls = cls | {"@evidence"}  # 記在 stack 上：裡面的「不考」有出處
        if tag in VOID:
            self.closed(len(self.stack), cls, set())
        else:
            self.stack.append((tag, tag in SKIP_TAGS or bool(cls & SKIP_CLASSES), cls))
            self.prev.append(set())

    def closed(self, depth, cls, inner):
        """第 depth 層有一個元素結束：記成那一層最後一個子元素；和 h2 同層的，就是這一段目前的最後一塊。
        inner 是這個元素自己最後一個子元素的 class（最後一塊是摺起來的答案時，要看它裡面的最後一塊）。"""
        self.prev[depth] = cls
        if self.sections and self.sections[-1]["depth"] == depth and not self.sections[-1]["done"]:
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
                self.boxes = [b for b in self.boxes if b["depth"] < i]
                self.closed(i, cls, inner)
                break
        if cls is None:
            return
        if tag == "section" and cls & set(PANES) and self.sections:
            self.sections[-1]["done"] = True  # 這一欄結束了，後面那欄開頭的東西不算這一段的最後一塊
        if tag in BLOCK:
            self.end_sentence()
        if tag in ("h2", "h3"):
            self.in_heading = max(0, self.in_heading - 1)
        if tag == "tr":
            self.row = None
            if self.type_row is not None and self.type_row["cells"]:
                slug, what = self.type_row["slug"], " ".join(self.type_row["text"].split())[:20]
                if not SLUG.match(slug):
                    self.problems.append(f'題型表的「{what}」沒有 data-type：每一列寫一個英文小寫代號（例如 acf-read），'
                                         "練習頁的題目用它對回這個題型")
                elif slug in self.type_slugs:
                    self.problems.append(f"題型表的 data-type={slug!r} 重複了：每個題型一個代號")
                self.type_slugs.append(slug)
            self.type_row = None
        if "def" in cls and self.defs:
            d = self.defs.pop()
            if d["dfn"] != 1:
                self.problems.append(f'定義框裡有 {d["dfn"]} 個 <dfn>：一個 class="def" 只定義一個術語')
            need, label = next(iter(DEF_KINDS[d["kind"]].items()))
            if not d["slots"].get(need, "").strip():
                self.problems.append(f'定義框「{d["term"].strip()[:20]}」（data-kind="{d["kind"]}"）沒有 class="{need}" 的「{label}」：'
                                     + {"class": "要寫讀者能拿來檢查的判斷標準",
                                        "quantity": "用小整數算一次給讀者看",
                                        "method": "寫出遇到什麼情況要用它"}[d["kind"]])
            if not d["example"]:
                self.problems.append(f'定義框「{d["term"].strip()[:20]}」前面沒有先舉例：新概念先用生活情境和小整數在原地算一次或畫一次，'
                                     "再說「這叫做○○」（這個 h2/h3 塊裡，定義框之前的正文要有數字）")
        if tag == "b" and self.whys and self.whys[-1]["state"] == "q":
            self.whys[-1]["state"] = "done"
        if "why" in cls and self.whys:
            w = self.whys.pop()
            if w["state"] != "done" or not w["q"].strip().endswith(("？", "?")):
                self.problems.append("「為什麼」框沒有先寫出它在回答的問題：開頭寫成 <b>讀者會問的那一句？</b>（問號結尾），"
                                     "接著才是答案；一個框只答一個問題")
        if tag == "details" and self.checks and self.checks[-1]["depth"] == len(self.stack):
            c = self.checks.pop()
            if not c["refs"]:
                self.problems.append(f"自測「{' '.join(c['ask'].split())[:20]}」的答案沒有指回講義的 §：答案要教會答不出來的人，"
                                     "寫出線索、對到這頁的哪一條規則，最後一行「還不會：回 §N.M」")
        if "calc" in cls and self.calcs:
            c = self.calcs.pop()
            what = " ".join((c["formula"] + c["subst"]).split())[:30]
            if not re.search(r"[=＝]", c["formula"]):
                self.problems.append(f'計算「{what}」沒有寫出公式：.calc 裡要有含「=」的 class="formula"，不寫「用 §N 的公式」')
            if not re.search(r"\d", c["subst"]):
                self.problems.append(f'計算「{what}」沒有代入數字：.calc 裡要有 class="subst"，把數字代進公式')
            if not c["ans"]:
                self.problems.append(f'計算「{what}」沒有標出結果：算出來的那個數包成 <span class="ans">…</span>，讀者一眼找到答案')
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

    def end_sentence(self):
        """一個區塊結束，手上這句也結束：太長就報。"""
        self.check_sentence(self.sentence)
        self.sentence = ""

    def check_sentence(self, s):
        n = text_units(s)
        if n > MAX_SENTENCE:
            self.problems.append(f"這句有 {n} 字，一句上限 {MAX_SENTENCE}：「{' '.join(s.split())[:30]}…」一句只講一件事，拆開")

    def handle_data(self, data):
        if self.row is not None:
            self.row["text"] += data
        text = data.strip()
        if text and self.whys:
            if self.whys[-1]["state"] == "start":
                self.whys[-1]["state"] = "bad"  # 問題之前先寫了別的字
            elif self.whys[-1]["state"] == "q":
                self.whys[-1]["q"] += data
        for box in self.boxes:
            if box["first"] and text:
                box["first"] = False
                if text.startswith(box["labels"]):
                    self.problems.append(f"「{text[:12]}」開頭重複了標籤：這個框的標籤由樣式加上，內文直接寫內容")
        if self.type_row is not None:
            self.type_row["text"] += data
        m = NOT_EXAMINED.search(data)
        if m and not self.inside_class("@evidence"):
            self.problems.append(f"「{m.group(0)}」沒有出處：沒有老師明示就當會考、照會考的規格教；"
                                 '老師明示過的，寫在帶 data-evidence="檔名 p.頁碼或哪一次公告" 的元素裡')
        m = PREREQ.search(data)
        if m:
            self.problems.append(f"「{m.group(0)}」把讀者推去看別的 topic：前置知識要在原地從零教，"
                                 "用定義框加上那一頁課件的截圖，只補這裡需要的那一點")
        if self.types is not None and self.inside_class("types"):
            self.types += SECTION_REF.findall(data)
        for fig in self.figures:
            if fig["in_caption"]:
                fig["caption"] += data
        if self.heading is not None:
            self.heading += data
        if self.defs:
            for name in DEF_SLOTS:
                if self.inside_class(name):
                    self.defs[-1]["slots"][name] = self.defs[-1]["slots"].get(name, "") + data
        if self.defs and self.inside("dfn"):
            self.defs[-1]["term"] += data
        if self.calcs:
            if self.inside_class("formula"):
                self.calcs[-1]["formula"] += data
            elif self.inside_class("subst"):
                self.calcs[-1]["subst"] += data
        found = SECTION_REF.findall(data)
        self.refs += found
        if self.checks:
            if self.inside("summary"):
                self.checks[-1]["ask"] += data
            else:
                self.checks[-1]["refs"] += len(found)
        if self.sections:
            self.sections[-1]["refs"] += found
            if self.inside_class("uses"):
                self.sections[-1]["uses_refs"] += found
        if self.skipping():
            return
        if not self.in_heading and not self.defs and re.search(r"\d", data):
            self.example = True
        if not self.calcs:
            parts = SENTENCE_END.split(data)
            for done in parts[:-1]:
                self.check_sentence(self.sentence + done)
                self.sentence = ""
            self.sentence += parts[-1]
        n = text_units(data)
        if self.sections:
            self.sections[-1]["units"] += n
        else:
            self.prelude += n


def lint(src: str) -> list:
    p = Lint()
    p.feed(src)
    p.close()
    p.end_sentence()
    problems = list(p.problems)
    problems += coverage(p.pages, p.page_captions)
    problems += panes(p.sections)
    course = {f"{i}" for i, sec in enumerate(p.sections, 1) if sec["pane"] == "course"}
    problem_secs = {f"{i}" for i, sec in enumerate(p.sections, 1) if sec["pane"] == "problems"}
    if p.types is None:
        problems.append('題目欄開頭（第一個 h2 之前）要有 <table class="types"> 題型表：看到什麼題目 → 用哪條公式、哪張表 → '
                        "示範題 §N，趕時間的人從這裡起步")
    elif not any(r.split(".")[0] in problem_secs for r in p.types):
        problems.append("題型表沒有連到任何一題：每種題型寫出示範題的 §N")
    for sec in p.sections:
        title, n = sec["title"][:30], sec["units"]
        if n > PER_SECTION:
            problems.append(f"§「{title}」有 {n} 字，每段上限 {PER_SECTION}：拆成幾段，或刪掉不是在教這頁的東西")
        if sec["pane"] == "problems" and sec["method"]:
            if not sec["uses"]:
                problems.append(f'§「{title}」有計算或答案紙，卻沒有 <ul class="uses"> 的「這題用到」：一行列一樣用到的公式或規則，'
                                "後面寫講義的 §N；教學只寫在講義那一段，不在題目旁邊重寫一次")
            elif not any(r.split(".")[0] in course for r in sec["uses_refs"]):
                problems.append(f"§「{title}」的「這題用到」沒有連到講義：每一樣寫出講義的 §N，讀者按了那一段就在旁邊打開")
            if p.kind == "text":
                pass
            elif not sec["origin"]:
                problems.append(f'§「{title}」有計算或答案紙，卻沒有 class="origin" 的「數字從哪來」表')
            elif sec["calc_first"]:
                problems.append(f"§「{title}」的「數字從哪來」表排在算式後面：先列出要用的數字從哪來，再代公式，"
                                "讀者算到那一步時才知道每個數字的來源")
        ends = "summary" in sec["last"] or ("answer" in sec["last"] and "summary" in sec["last_inner"])
        if sec["pane"] == "course":
            if not sec["keys"]:
                problems.append(f'§「{title}」開頭沒有 class="summary" 的「這頁重點」：放在 h2 底下、第一個 h3 之前，'
                                "讀者先看到要帶走什麼，再讀細節")
            if "check" not in sec["last"]:
                problems.append(f'§「{title}」最後一塊不是 <details class="check"> 的自測：每一頁講完讓讀者自己算一次或答一次，'
                                "問題寫在 <summary>，答案摺在裡面")
        elif not sec["recap"] and not ends:
            problems.append(f'§「{title}」最後一塊不是 class="summary" 的「這題記住」：每題結尾都要有總結'
                            "（可以放在 details.answer 的最後）")
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


def warnings(src: str) -> list:
    """不擋產出的提醒：攤開的圖太多時，讀者找不到正文。"""
    p = Lint()
    p.feed(src)
    p.close()
    out = []
    if p.shown_figures > FIGURE_WARN:
        out.append(f"沒摺起來的圖有 {p.shown_figures} 張（提醒門檻 {FIGURE_WARN}）：整張統計表放查表面板，"
                   "題目裡只留圈出那一格的小截圖")
    return out


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
    """把內文的 §N、§N.M 換成連到那一段的連結（class="ref"：按了在對照欄打開）；標籤裡、<a> 裡、標題編號不動。"""
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
                lambda m: f'<a class="ref" href="#{anchors[m.group(1)]}">{m.group(0)}</a>' if m.group(1) in anchors else m.group(0),
                part))
    return "".join(out)


NUMBERED_H2 = re.compile(r'<h2([^>]*)><span class="num">§(\d+)</span> (.*?)</h2\s*>', re.I | re.S)
ID_ATTR = re.compile(r"""\bid\s*=\s*["']?([^"'\s>]+)""")
DOT = '<span class="dot">·</span>'
ICONS = {"check": '<path d="M3 8.5l3.2 3.2L13 4.5"/>', "x": '<path d="M4 4l8 8M12 4l-8 8"/>',
         "list": '<path d="M2.5 4h11M2.5 8h11M2.5 12h7"/>'}


def icon(name: str) -> str:
    return f'<svg class="i" viewBox="0 0 16 16" aria-hidden="true">{ICONS[name]}</svg>'


def plain(html: str) -> str:
    return " ".join(TAG.sub("", html).split())


def has_class(name: str) -> str:
    """比對 class 屬性裡有 name 這個字的樣式片段。"""
    return rf"""[^>]*\bclass\s*=\s*["'](?:[^"']*\s)?{name}(?:\s[^"']*)?["'][^>]*"""


def pane_start(src: str, name: str, end: bool = True) -> int:
    """<section class="name"> 開始標籤結束的位置（end=False 是標籤開始的位置）；沒有就回傳 -1。"""
    m = re.search(rf"<section\b{has_class(name)}>", src, re.I)
    return (m.end() if end else m.start()) if m else -1


# 目錄上不重複標題尾巴的頁碼：「……（講義 p.3）」
PAGE_TAIL = re.compile(r"\s*[（(][^（）()]*\bp{1,2}\.\s*\d[^（）()]*[）)]\s*$")


def add_meta(src: str, anchors: dict) -> str:
    """每個編號的 h2 寫上 data-n、data-min，後面接一行：約幾分鐘；講義那部的段再列出用到它的題目。"""
    heads = list(NUMBERED_H2.finditer(src))
    cut = pane_start(src, "problems", end=False)
    # 每一段的正文到下一個 h2 為止；講義最後一段只到講義那部結束，題目那部開頭的速查卡不算它的
    ends = [heads[i + 1].start() if i + 1 < len(heads) else len(src) for i in range(len(heads))]
    bodies = [src[m.end():(cut if m.start() < cut < end else end)] for m, end in zip(heads, ends)]
    label_of = {anchor: label.split(".")[0] for label, anchor in anchors.items()}
    used = {}  # 講義段的編號 → 用到它的題目段
    for m, body in zip(heads, bodies):
        if cut >= 0 and m.start() > cut:
            for anchor in re.findall(r'<a class="ref" href="#([^"]+)"', body):
                users = used.setdefault(label_of.get(anchor), [])
                if m.group(2) not in users:
                    users.append(m.group(2))
    out, pos = [], 0
    for m, body in zip(heads, bodies):
        n = m.group(2)
        minutes = max(1, round(text_units(TAG.sub("", body)) / UNITS_PER_MIN))
        bits = [f"約 {minutes} 分鐘"]
        if (cut < 0 or m.start() < cut) and used.get(n):
            bits.append("用到這頁的題目 " + "、".join(f'<a class="ref" href="#{anchors[u]}">§{u}</a>' for u in used[n]))
        attrs, title = m.group(1), PAGE_TAIL.sub("", plain(m.group(3)))
        if "data-short" not in attrs:  # 目錄和頁眉用的短標題：去掉尾巴的頁碼
            attrs += f' data-short="{title}"'
        out += [src[pos:m.start()],
                f'<h2{attrs} data-n="{n}" data-min="{minutes}"><span class="num">§{n}</span> {m.group(3)}</h2>',
                f'<p class="meta">{DOT.join(bits)}</p>']
        pos = m.end()
    return "".join(out) + src[pos:]


def add_cheat(src: str) -> str:
    """速查卡前面加一個不編號的標題（目錄和頁眉的「速查卡」連到它），和列印、展開全部做法的按鈕。"""
    m = re.search(rf"<div\b{has_class('cheat')}>", src, re.I)
    if not m:
        return src
    head = ('<h2 class="plain" id="cheat">速查卡</h2><p class="cheat-tools">'
            '<button type="button" class="btn" data-act="print">列印速查卡</button>'
            '<button type="button" class="btn" data-act="answers">展開全部做法</button></p>')
    return src[:m.start()] + head + src[m.start():]


DFN = re.compile(r"<dfn\b[^>]*>(.*?)</dfn\s*>\s*(?:[（(]([^（）()]*)[）)])?", re.I | re.S)
HEAD_TAG = re.compile(r"<h[23]\b[^>]*>", re.I)


def add_terms(src: str, anchors: dict) -> str:
    """最後加一張名詞表：每個 <dfn> 一列，緊跟在它後面括號裡的是另一種語言的寫法；連到它所在的那一段。"""
    label_of = {anchor: label for label, anchor in anchors.items()}
    heads = [(m.start(), ID_ATTR.search(m.group(0))) for m in HEAD_TAG.finditer(src)]
    heads = [(pos, m.group(1)) for pos, m in heads if m and m.group(1) in label_of]
    rows = []
    for m in DFN.finditer(src):
        before = [anchor for pos, anchor in heads if pos < m.start()]
        if before:
            rows.append((plain(m.group(1)), m.group(1), plain(m.group(2) or ""), before[-1]))
    end = src.lower().rfind("</section>")
    if not rows or end < 0:
        return src
    rows.sort(key=lambda r: r[0].lower())
    items = "".join(f'<li><a class="ref" href="#{anchor}">{term}</a><span>{alt}</span>'
                    f'<span class="where">§{label_of[anchor]}</span></li>' for _, term, alt, anchor in rows)
    table = ('<h2 class="plain" id="terms">名詞表</h2><p class="meta">這一頁定義過的名詞，照原文排。按名詞在旁邊打開定義。</p>'
             f'<ul class="terms">{items}</ul>')
    return src[:end] + table + src[end:]


PART = re.compile(rf"<p\b{has_class('part')}>(.*?)</p\s*>", re.I | re.S)


def add_parts(src: str) -> str:
    """每一部的開頭要有 <p class="part">：作者沒寫的，講義那部補「講義」，題目那部補「題目」。"""
    for name, label in (("problems", "題目"), ("course", "講義")):  # 先補後面那部，前面那部的位置才不會變
        start = pane_start(src, name)
        end = pane_start(src, "problems") if name == "course" else -1
        end = len(src) if end < 0 else end
        if start < 0 or PART.search(src, start, end):
            continue
        m = re.compile(r"<h2[\s>]", re.I).search(src, start, end)
        if m:
            src = src[:m.start()] + f'<p class="part">{label}</p>' + src[m.start():]
    return src


OUTLINE = re.compile(rf"<p\b{has_class('part')}>(?P<part>.*?)</p\s*>|<h(?P<level>[123])\b(?P<attrs>[^>]*)>(?P<inner>.*?)</h(?P=level)\s*>",
                     re.I | re.S)
NUM_SPAN = re.compile(r'<span class="num">.*?</span>', re.S)


def outline(src: str) -> list:
    """讀出目錄：一組一組的 {"label", "note", "items"}；項目是 {"id", "n", "title", "subs"}，subs 是 [(id, 文字)]。"""
    groups = [{"label": "開始", "note": "", "items": []}]
    for m in OUTLINE.finditer(src):
        if m.group("part") is not None:
            note = re.search(r"<span[^>]*>(.*?)</span\s*>", m.group("part"), re.I | re.S)
            groups.append({"label": plain(re.sub(r"<span.*", "", m.group("part"), flags=re.I | re.S)),
                           "note": plain(note.group(1)) if note else "", "items": []})
            continue
        attrs, inner = m.group("attrs"), m.group("inner")
        own = ID_ATTR.search(attrs)
        if not own:
            continue
        if m.group("level") == "3":
            if groups[-1]["items"]:
                groups[-1]["items"][-1]["subs"].append((own.group(1), plain(inner)))
            continue
        n = re.search(r'\bdata-n="(\d+)"', attrs)
        short = re.search(r"""\bdata-short\s*=\s*["']([^"']+)["']""", attrs)
        title = short.group(1) if short else PAGE_TAIL.sub("", plain(NUM_SPAN.sub("", inner)))
        if m.group("level") == "1":
            title = "開始之前"
        if re.search(r"\brecap\b", attrs) and groups[-1]["label"] != "總結":
            groups.append({"label": "總結", "note": "", "items": []})
        groups[-1]["items"].append({"id": own.group(1), "n": n.group(1) if n else "", "title": title, "subs": []})
    return [g for g in groups if g["items"]]


def rail(src: str, groups: list) -> str:
    """左邊固定的目錄：書名、讀了幾段、每段一格的進度條、切換鈕，再來是一組一組的段落。"""
    h1 = re.search(r"<h1\b[^>]*>(.*?)</h1\s*>", src, re.I | re.S)
    title = re.search(r"<title[^>]*>(.*?)</title\s*>", src, re.I | re.S)
    book = plain(h1.group(1)) if h1 else plain(title.group(1)) if title else ""
    cells = '<i class="gap"></i>'.join(
        "".join(f'<i data-for="{it["id"]}"></i>' for it in g["items"] if it["n"]) for g in groups if any(it["n"] for it in g["items"]))
    seg = ('<div class="seg" role="group" aria-label="{}"><button type="button" data-act="{}" aria-pressed="true">{}</button>'
           '<button type="button" data-act="{}" aria-pressed="false">{}</button></div>')
    quick = "".join(f'<button type="button" class="btn" data-act="{act}">{label}</button>'
                    for act, label in (("cheat", "速查卡"), ("terms", "名詞表"), ("panel", "查表")) if f'id="{act}"' in src)
    out = ['<nav class="rail" aria-label="目錄"><div class="rail-top">', f'<p class="book">{book}</p>',
           f'<button type="button" class="shut" data-act="scrim" aria-label="關閉目錄">{icon("x")}</button>',
           '<p class="status" aria-live="polite"></p>', f'<div class="strip" aria-hidden="true">{cells}</div>',
           seg.format("顯示多少", "digest-off", "全文", "digest-on", "只看重點"),
           f'<div class="quick">{quick}</div>' if quick else "", "</div>"]
    if re.search(r"<img\b[^>]*\bdata-zh\s*=", src, re.I):
        out.append(seg.format("截圖的語言", "lang-en", "截圖：原文", "lang-zh", "截圖：翻譯"))
    out.append(seg.format("頁面的明暗", "theme-light", "淺色", "theme-dark", "深色"))
    for g in groups:
        out.append(f'<h2>{g["label"]}<span>{g["note"]}</span></h2><ol>')
        for it in g["items"]:
            subs = "".join(f'<li><a href="#{sid}">{text}</a></li>' for sid, text in it["subs"])
            out.append(f'<li><a href="#{it["id"]}"><span class="n">{it["n"]}</span><span class="t">{it["title"]}</span>'
                       f'<span class="st">{icon("check")}<span class="vh">讀過了</span></span></a>'
                       + (f'<ol class="sub">{subs}</ol>' if subs else "") + "</li>")
        out.append("</ol>")
    out.append('<button type="button" class="reset" data-act="reset">清掉「讀過」的記號</button></nav>')
    return "".join(out)


def add_shell(src: str) -> str:
    """把兩部包進一條捲軸的版面：目錄、頁眉（現在讀到哪、速查卡、名詞表、查表、只看重點）、正文、對照欄。"""
    if not re.search(r"<h1\b[^>]*\bid\s*=", src, re.I):
        src = re.sub(r"<h1\b", '<h1 id="top"', src, count=1, flags=re.I)
    src = re.sub(r"</h1\s*>", lambda m: m.group(0)
                 + '<p class="digest-note">現在每段只顯示重點和定義。<button type="button" class="btn" data-act="digest-off">看全文</button></p>'
                 + '<p class="resume" hidden>上次讀到這裡：<a href="#"></a></p>', src, count=1, flags=re.I)
    tools = "".join(f'<button type="button" class="tool wide" data-act="{act}">{label}</button>'
                    for act, label in (("cheat", "速查卡"), ("terms", "名詞表"), ("panel", "查表")) if f'id="{act}"' in src)
    head = (f'<div class="head"><button type="button" class="tool" data-act="nav">{icon("list")}目錄</button>'
            f'<p class="crumb"></p><p class="count"></p>{tools}'
            '<button type="button" class="tool" data-act="digest-toggle" aria-pressed="false">只看重點</button>'
            '<span class="bar" aria-hidden="true"></span></div>')
    peek = ('<button type="button" class="scrim" data-act="scrim" aria-label="關閉"></button>'
            '<aside class="peek" aria-label="旁邊打開的那一段"><div class="peek-head"><h2></h2><p></p>'
            f'<button type="button" class="close" data-act="peek-close" aria-label="關閉">{icon("x")}</button>'
            '<div class="peek-acts"><button type="button" class="btn back" data-act="peek-back" hidden>返回</button>'
            '<button type="button" class="btn split" data-act="split" aria-pressed="false">並排</button>'
            '<a class="go" href="#">跳到這一段</a></div></div><div class="peek-body"></div></aside>')
    opening = re.search(r"<body\b[^>]*>", src, re.I)
    start = opening.end() if opening else 0
    end = src.lower().rfind("</body>")
    end = len(src) if end < 0 else end
    return (src[:start] + rail(src, outline(src)) + "<main>" + head + '<div class="page">' + src[start:end]
            + "</div></main>" + peek + src[end:])


PANEL = re.compile(rf"<aside\b{has_class('panel')}>(.*?)</aside\s*>", re.I | re.S)
PANEL_FIG = re.compile(r"""<figure\b[^>]*\bdata-tab\s*=\s*["'][^"']*["'][^>]*>.*?</figure\s*>""", re.I | re.S)


def add_panel(src: str) -> str:
    """<aside class="panel"> 裡的 figure 收成 #panel：頁眉的「查表」把它們在對照欄打開，一張一個分頁。"""
    m = PANEL.search(src)
    if not m:
        return src
    return src[:m.start()] + f'<div id="panel">{"".join(PANEL_FIG.findall(m.group(1)))}</div>' + src[m.end():]


IMG_TAG = re.compile(r"<img\b[^>]*>", re.I)
ZH_ATTR = re.compile(r"""\sdata-zh\s*=\s*["']([^"']+)["']""", re.I)
SRC_ATTR = re.compile(r"""(\ssrc\s*=\s*["'])([^"']+)(["'])""", re.I)
CLASS_ATTR = re.compile(r"""(\sclass\s*=\s*["'])""", re.I)


def split_bilingual(src: str) -> str:
    """<img src="原圖" data-zh="翻譯圖"> 拆成兩張：原圖（class en，預設顯示）和翻譯圖（class zh，點圖才顯示）。"""
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
        return with_class(base, "en") + with_class(zh_tag, "zh")

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


VIEWPORT = '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
# 深淺色由讀者切換、記在瀏覽器（練習頁用同一個鍵）；在樣式之前套上，打開時才不會先閃一下白底
THEME = ('<script>try { if (localStorage.getItem("tutor-theme") === "dark") '
         'document.documentElement.dataset.theme = "dark"; } catch (e) {}</script>\n')


def inject_assets(src: str) -> str:
    style = f"{THEME}<style>\n{CSS.read_text(encoding='utf-8')}</style>\n"
    if not re.search(r"<meta\b[^>]*\bname\s*=\s*[\"']viewport[\"']", src, re.I):
        style = VIEWPORT + style  # 沒有它，手機用桌面寬度排版再縮小
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
    src = add_meta(link_refs(add_panel(src), anchors), anchors)
    src = add_terms(add_cheat(src), anchors)
    src = add_shell(add_parts(src))
    return inject_assets(inline_images(split_bilingual(src), base))


# 量寬螢幕之前在頁面裡跑：正文裡自己橫向捲動的容器（.formula、.calc、表格、.sheet）內容比它寬的，記進 <meta name="clipped">
CLIPPED = re.compile(r'<meta name="clipped" content="([^"]*)"')
FIND_CLIPPED = r"""
  (() => {
    const cut = [...document.querySelectorAll(".page *")]
      .filter((e) => e.offsetParent && /auto|scroll/.test(getComputedStyle(e).overflowX) && e.scrollWidth > e.clientWidth + 1)
      .map((e) => ({
        el: e.tagName.toLowerCase() + (typeof e.className === "string" && e.className.trim() ? "." + e.className.trim().split(/\s+/).join(".") : ""),
        over: e.scrollWidth - e.clientWidth, text: (e.textContent || "").trim().replace(/\s+/g, " ").slice(0, 40),
      }));
    const meta = document.createElement("meta");
    meta.name = "clipped";
    meta.content = JSON.stringify(cut);
    document.head.append(meta);
  })();
"""


def clipped(dom: str, width: int) -> list:
    """overflow.render() 回傳的 DOM 裡，FIND_CLIPPED 記下的每個被切掉的容器，一條一句。"""
    m = CLIPPED.search(dom)
    return [f"視窗寬 {width}px：<{c['el']}> 的內容比正文欄寬 {c['over']}px，右邊被切掉、要橫向捲才看得到「{c['text']}」。"
            "一行只放一條公式；一條還是太寬就拆成兩行，表格拆欄"
            for c in (json.loads(html.unescape(m.group(1))) if m else [])]


def measure(page: Path):
    """寬螢幕和手機寬各量一次水平溢出，寬螢幕再查正文裡被切掉的公式和表格；回傳全部的問題，找不到瀏覽器回傳 None。"""
    out = []
    for width in overflow.WIDTHS:
        wide = width == max(overflow.WIDTHS)
        dom = overflow.render(page, width, FIND_CLIPPED if wide else "")
        if dom is None:
            return None
        out += overflow.problems(dom, width) + (clipped(dom, width) if wide else [])
    return out


def main(argv=None, measure=measure) -> int:
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
    for w in warnings(src):
        print(f"提醒：{w}", file=sys.stderr)
    out = args.out or args.src.with_name(args.src.stem.removesuffix("-src") + ".html")
    out.write_text(build(src, args.src.parent), encoding="utf-8")
    if not overflow.deliverable(out, args.src, measure(out)):
        return 1
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
