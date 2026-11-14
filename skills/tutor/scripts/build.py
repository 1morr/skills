"""把講解頁的原始 HTML 組成單一檔案，並檢查寫作規則；規則不過就不產出。

    python build.py <src.html> [-o <out.html>]

組好之後用本機的 Chrome 或 Edge 在寬螢幕和手機寬各量一次水平溢出（pages/scripts/overflow.py）：
有溢出就不產出，逐條印出哪個元素超出幾 px；找不到瀏覽器只提醒。

只用標準函式庫，CI 才能直接跑測試。
"""

import argparse
import base64
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

# 頁面分左右兩欄：左邊課件導讀，右邊例題和作業，各自捲動，連結可以跨欄跳
PANES = ("course", "problems")
# 每個 h2 段落的字數上限，單位見 text_units。整頁不設上限：課件導讀要教完宣告的每一頁，由頁數覆蓋把關
PER_SECTION = 2000
# 一句話的字數上限：讀者是零基礎，一句一件事
MAX_SENTENCE = 50
# 題目欄每一題最多連到課件欄幾段：用到的定義和公式要在題目旁邊原地再寫一次，不叫讀者跳來跳去
MAX_CROSS = 3
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

# 這些框的標籤由樣式加上；內文開頭再寫一次就重複了
LABELS = {"why": ("為什麼",), "trap": ("常見錯誤",), "summary": ("這段記住", "這頁重點", "這題記住"), "def": ("定義",),
          "sheet": ("答案紙上寫這樣",)}
# 整頁太長的提醒（不擋產出）：正文字數，和沒有摺起來的圖的張數
PROSE_WARN = 15000
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
        self.defs = []  # 開著的 .def：{"dfn": 個數, "test": 文字}
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
        if tag == "figure":
            if self.sections and self.inside_class("why"):
                self.sections[-1]["why_fig"] = True
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
            self.defs.append({"dfn": 0, "test": "", "term": "", "example": self.example})
        if "calc" in cls:
            self.calcs.append({"formula": "", "subst": "", "ans": False})
        if tag == "h2":
            self.heading = ""
            if self.pane() == "problems":
                self.problems_h2 = True
            self.sections.append({"title": "", "units": 0, "method": False, "why": False, "origin": False,
                                  "figs": set(), "calcs": set(), "rows": [], "h3": 0, "why_refs": [], "calc_first": False,
                                  "pane": self.pane(), "depth": len(self.stack), "last": set(),
                                  "last_inner": set(), "recap": "recap" in cls, "refs": [], "why_fig": False, "done": False,
                                  "keys": False})
        if self.sections:
            sec = self.sections[-1]
            sec["method"] |= bool(cls & METHOD_CLASSES)
            sec["why"] |= "why" in cls
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
            if not d["test"].strip():
                self.problems.append('定義框沒有 class="test" 的「怎樣才算」：要寫讀者能拿來檢查的判斷標準')
            if not d["example"]:
                self.problems.append(f'定義框「{d["term"].strip()[:20]}」前面沒有先舉例：新概念先用生活情境和小整數在原地算一次或畫一次，'
                                     "再說「這叫做○○」（這個 h2/h3 塊裡，定義框之前的正文要有數字）")
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
        if self.defs and self.inside_class("test"):
            self.defs[-1]["test"] += data
        if self.defs and self.inside("dfn"):
            self.defs[-1]["term"] += data
        if self.calcs:
            if self.inside_class("formula"):
                self.calcs[-1]["formula"] += data
            elif self.inside_class("subst"):
                self.calcs[-1]["subst"] += data
        found = SECTION_REF.findall(data)
        self.refs += found
        if self.sections:
            self.sections[-1]["refs"] += found
            if self.inside_class("why"):
                self.sections[-1]["why_refs"] += found
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
        if sec["pane"] == "problems" and not sec["recap"]:  # 總結是整個 topic 的導覽，連回課件不限
            cross = {r.split(".")[0] for r in sec["refs"]} & course
            if len(cross) > MAX_CROSS:
                problems.append(f"§「{title}」連到課件欄 {len(cross)} 段（§{'、§'.join(sorted(cross, key=int))}），"
                                f"上限 {MAX_CROSS}：用到的定義和公式在這題旁邊原地再寫一次，§ 連結只留「想看完整推導再點」的")
        if sec["pane"] == "problems" and sec["method"]:
            if not sec["why"]:
                problems.append(f'§「{title}」有計算或答案紙，卻沒有 class="why" 的區塊：要講這題在問什麼、用到課件哪裡')
            else:
                if not any(r.split(".")[0] in course for r in sec["why_refs"]):
                    problems.append(f"§「{title}」的「為什麼」沒有連到課件欄：寫出用到課件的 §N，讀者點了左欄就跳過去")
                if not sec["why_fig"]:
                    problems.append(f"§「{title}」的「為什麼」沒有課件截圖：把這題用到的那一塊課件（公式、規則）截過來放在這裡，"
                                    "讀者不用跳去左欄找")
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
    """不擋產出的提醒：整頁太長時讀者抓不到重點。"""
    p = Lint()
    p.feed(src)
    p.close()
    out = []
    units = sum(sec["units"] for sec in p.sections)
    if units > PROSE_WARN:
        out.append(f"正文有 {units} 字（提醒門檻 {PROSE_WARN}）：刪掉重複講的段落，把只有少數人要看的推導收進 <details>")
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
    here = '<button type="button" class="here" data-act="toc" title="回到這一欄的目錄"></button>'
    bars = {"problems": '<button type="button" data-act="print">列印速查卡</button>'
                        '<button type="button" data-act="answers">展開全部做法</button>', "course": ""}
    if re.search(r'<aside\b[^>]*\bid="panel"', src, re.I):
        bars["problems"] = '<button type="button" data-act="panel">查表</button>' + bars["problems"]
    if re.search(r"<img\b[^>]*\bdata-zh\s*=", src, re.I):
        bars["course"] = '<button type="button" data-act="lang">圖片：中文（點這裡全部換成原文）</button>'
    for name in ("problems", "course"):  # 先插後面那欄，前面那欄的位置才不會變
        at = pane_start(src, name)
        if at >= 0:
            src = src[:at] + f'<div class="bar">{here}{bars[name]}</div>' + src[at:]
    return src


PANEL = re.compile(r"""<aside\b[^>]*\bclass\s*=\s*["'][^"']*\bpanel\b[^"']*["'][^>]*>(.*?)</aside\s*>""", re.I | re.S)
PANEL_FIG = re.compile(r"""<figure\b[^>]*\bdata-tab\s*=\s*["']([^"']*)["'][^>]*>(.*?</figure\s*>)""", re.I | re.S)


def add_panel(src: str) -> str:
    """<aside class="panel"> 裡的 figure 變成「查表」按鈕打開的分頁面板：整張統計表放這裡，不用每題重貼。"""
    m = PANEL.search(src)
    if not m:
        return src
    tabs, bodies = [], []
    for i, fm in enumerate(PANEL_FIG.finditer(m.group(1))):
        tabs.append(f'<button type="button" data-tab="t{i}" aria-pressed="{"true" if i == 0 else "false"}">{fm.group(1)}</button>')
        bodies.append(f'<figure data-tab="t{i}"{"" if i == 0 else " hidden"}>{fm.group(2)}')
    panel = (f'<aside id="panel" aria-label="查表"><header>{"".join(tabs)}'
             f'<button type="button" class="close">關閉</button></header><div class="body">{"".join(bodies)}</div></aside>')
    return src[:m.start()] + panel + src[m.end():]


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


VIEWPORT = '<meta name="viewport" content="width=device-width, initial-scale=1">\n'


def inject_assets(src: str) -> str:
    style = f"<style>\n{CSS.read_text(encoding='utf-8')}</style>\n"
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
    src = add_toolbars(add_toc(link_refs(add_panel(src), anchors)))
    return inject_assets(inline_images(split_bilingual(src), base))


def main(argv=None, measure=overflow.measure) -> int:
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
