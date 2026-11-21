"""把練習頁的原始 HTML 組成單一檔案：每題下面加一張能手寫、能打字的畫布（與選配流式步驟框），填答格在頁面上對答案；會讓頁面壞掉的事不過就不產出。

題目有兩種，各放幾題、怎麼排由出題的人照考試的形式決定：
    <section class="q drill" data-id="…">   小題：只有填答格，沒有畫布；一題問一件事
    <section class="q" data-id="…" data-type="題型代號">   整題：有畫布，可以有填答格、流式步驟框 textarea.work、提示、逐步詳解、範本答案
每題要有 <h2> 標題和 data-id（說明內容的英文小寫代號；它是存檔的鍵，發出去之後不要改）。
導讀頁有題型表時，整題的 data-type 寫它練的是哪幾列（空白分開）；沒有題型表就不用寫。整題至少要有範本答案或填答格其中一樣，讀者才對得了答案。
組好之後印「提醒」：題型表上還沒有題目的題型（不擋產出，出題的人對照計畫）。

    python scripts/practice.py <practice-src.html> -o <topicN-practice.html>

組好之後用本機的 Chrome 或 Edge 在寬螢幕和手機寬各量一次水平溢出（pages/scripts/overflow.py，可用 SKILLS_ROOT 指定根目錄）：
有溢出就不產出，逐條印出哪個元素超出幾 px；找不到瀏覽器只提醒。

原始檔的 <body> 寫：
    data-title    頁面標題
    data-key      畫布存檔的名字空間（同一台電腦上每份練習頁要不一樣，例如 stat101-topic4）
    data-guide    導讀頁檔名，相對於產出的練習頁；題目裡的 §N 會連到導讀頁那一段
    data-answers  答案檔，相對於原始檔；批改用，不放進頁面

模擬卷（同一套組頁，印在 A4 紙上做）：<body data-mode="mock" data-minutes="60">
    data-minutes  建議作答時間（分鐘），印在封面；可以不寫
    data-guide    可以列好幾份導讀頁，用 ; 分開（跨 topic 的累積卷）
    只有整題：不放小題、提示、逐步詳解，不寫對照的 §。
    每題從新的一頁開始，後面接一張整頁的作答頁（題目那一頁剩下的空白也可以寫）；模擬卷不看 data-h。
    答案直接寫在題目上的題（配對、填空、選擇）在 section 寫 data-space="none"：不接作答頁，也不另起一頁。
    版面照 LaTeX exam class 的慣例：封面有「題目／滿分／得分」表（滿分是那題給分點的總和；沒有給分點的題一個填答格一分），答案另外印。
    組好之後用同一個瀏覽器印兩份 PDF，放在頁面旁邊，路徑印在 stdout：
        <頁面檔名>.pdf          考卷：封面、題目、作答頁，查表面板的表接在卷末；不印翻譯和答案
                                查表面板只放考場會發的東西；沒有就不寫面板
        <頁面檔名>-answers.pdf  答案：每題的範本答案和給分點
    找不到瀏覽器只提醒：打開頁面按「列印考卷」「列印答案」各存一份。
    讀者做完在頁面上按「我在紙上做完了」，才對填答格、才看得到範本答案。

填答格（頁面上馬上對答案，寫法照 Moodle 的 short answer／numerical 題型：多個可接受的答案、不分大小寫、數字可給容許誤差）：
    <p class="fill" data-answer="2.262|2.26" data-why="df = 9、雙尾 α = 0.05，查 t 表">臨界值 =</p>
    data-answer   可接受的答案，用 | 分開；第一個是公布的答案。兩邊都是數字時比數值
    data-tol      數字的容許誤差（預設 0）
    data-why      一句原因：答對或公布答案時顯示
小題錯兩次就公布答案和原因；整題的填答格只說對不對，不公布，步驟由助教批改。

範本答案（整題最多一個，讀者寫完才打開；有給分點就照著自己勾，勾的結果會進「複製填答結果」）：
    <details class="model">
      <div class="sheet">老師格式的完整答案</div>
      <ul class="rubric"><li data-marks="2">寫出 H0、Ha</li><li data-marks="1">結論句寫明顯著水準</li></ul>
    </details>
    data-marks    這個給分點幾分（正整數），配分照老師的評分方式；給分點可以不寫

提示和逐步詳解（練習頁的整題，要不要放由出題的人決定；模擬卷不放）：排在範本答案前面，讀者卡住時一次看一個，用到第幾個會進「複製填答結果」。
    <ol class="hints"><li>這是哪個題型、做法在導讀頁 §16</li><li>第一步怎麼列</li></ol>
    <details class="steps">讀者的語言寫的逐步詳解，每一步寫為什麼；提示全部看完才出現</details>
    <p class="ref">、提示和詳解裡的 §N 會連到導讀頁（<code>、<pre> 與註解內的不轉）。

讀圖／讀輸出題：導讀頁題型表那一列寫了 data-reads="figure" 的題型，題目裡要有 <figure> 或 <pre class="output">（向下相容 pre.mtb）。

只用標準函式庫，CI 才能直接跑測試。
"""

import argparse
import base64
import html
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path

# 共用的水平溢出量測：優先讀環境變數 SKILLS_ROOT，未設時 fallback 到 plugin 根目錄的 pages/scripts/
_SKILLS_ROOT = os.environ.get("SKILLS_ROOT")
_PAGES_SCRIPTS = (Path(_SKILLS_ROOT).expanduser().resolve() / "pages" / "scripts"
                  if _SKILLS_ROOT else Path(__file__).resolve().parents[3] / "pages" / "scripts")
sys.path.insert(0, str(_PAGES_SCRIPTS))
import overflow  # noqa: E402

ASSETS = Path(__file__).resolve().parents[1] / "assets"
CSS = ASSETS / "practice.css"
JS = ASSETS / "practice.js"

BODY_ATTRS = ("data-title", "data-key", "data-guide", "data-answers")
MODES = ("practice", "mock")
SPACES = ("page", "none")
# 整題的畫布預設高度（畫布座標）；寫不下時讀者按「加長」。小題只填一格，寫了 data-h 才有畫布
PAD_H = 900
# 題目代號是畫布存檔的鍵：照順序編的號（q1、練習 2）插題或改順序後，舊的筆跡會跑到別題
SLUG = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
ORDINAL = re.compile(r"^(?:q|p|ex|drill|practice|problem|question|item|task)?-?\d+[a-z]?$")
# 題目本身只放題目和填答格；做法和答案只能放在讀者自己打開的地方：逐步詳解 details.steps、範本答案 details.model
ANSWER_CLASSES = {"answer", "calc", "sheet", "origin", "trap", "summary"}
OUTPUT_CLASSES = {"output", "mtb"}
MODEL_SUMMARY = "寫完了再打開：範本答案"
STEPS_SUMMARY = "提示看完還是不會：逐步詳解"
# 這些 class 裡的 §N 連到導讀頁
LINKED = {"ref", "hints", "steps"}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "param", "source", "track", "wbr"}
NON_PROSE_TAGS = ("script", "style", "code", "pre")
SECTION_REF = re.compile(r"§(\d+(?:\.\d+)?)")
REMOTE = re.compile(r"^\s*(https?:)?//", re.I)
PLACEHOLDER = re.compile(r"\{\{|\}\}")


def classes(attrs) -> set:
    return set((dict(attrs).get("class") or "").split())


def line_offsets(src: str) -> list:
    offs = [0]
    for i, ch in enumerate(src):
        if ch == "\n":
            offs.append(i + 1)
    return offs


class Lint(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.problems = []
        self.body = None  # <body> 的屬性
        self.stack = []  # [(tag, classes)]
        self.qs = []  # 每題：{"id", "drill", "differs", "title", "refs", "fills"}
        self.figures = []  # 開著的 figure：{"caption", "in_caption", "panel", "tab"}
        self.heading = None

    def inside(self, name) -> bool:
        return any(name in c for _, c in self.stack)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = classes(attrs)
        for k, v in attrs:
            if v and PLACEHOLDER.search(v):
                self.problems.append(f"<{tag} {k}={v[:40]!r}> 還有沒填的 {{{{佔位}}}}：先跑產生數字的腳本")
        if tag == "body":
            self.body = a
        for key in ("src", "href", "data-zh"):
            if tag in ("img", "script", "link", "source") and a.get(key) and REMOTE.match(a[key]):
                self.problems.append(f"外部資源 <{tag} {key}={a[key]!r}>：頁面要能離線打開，請改成本機檔案")
        if tag == "section" and "q" in cls:
            if self.inside("q"):
                self.problems.append("題目裡又有題目（section.q 不能巢狀）")
            self.qs.append({"id": a.get("data-id") or "", "drill": "drill" in cls, "differs": (a.get("data-differs") or "").strip(),
                            "title": "", "refs": [], "fills": 0, "types": (a.get("data-type") or "").split(),
                            "model": 0, "marks": 0, "shows": False, "hints": 0, "steps": 0, "links": []})
            if (a.get("data-space") or "page").strip() not in SPACES:
                self.problems.append(f"data-space={a['data-space']!r} 看不懂：不寫是接一張作答頁，答案直接寫在題目上的題寫 none")
            if a.get("data-h") is not None and not a["data-h"].strip().isdigit():
                self.problems.append(f"data-h={a['data-h']!r} 要是整數：畫布的高度（畫布座標）")
        elif self.qs and self.inside("q"):
            q = self.qs[-1]
            name = q["id"] or q["title"]
            if tag == "details" and "model" in cls and not q["drill"] and not self.inside("model"):
                q["model"] += 1
            elif tag == "details" and "steps" in cls and not q["drill"] and not self.inside("steps"):
                q["steps"] += 1
            elif tag == "ol" and "hints" in cls and not q["drill"]:
                pass
            elif self.inside("steps"):
                pass
            elif self.inside("model"):
                if tag == "li" and self.inside("rubric"):
                    marks = (a.get("data-marks") or "").strip()
                    if marks.isdigit() and int(marks) > 0:
                        q["marks"] += int(marks)
                    else:
                        self.problems.append(f"題目 {name!r} 的給分點沒有 data-marks：每個 <li> 寫這一點幾分（正整數）")
            elif tag == "details" or cls & ANSWER_CLASSES:
                what = f'<{tag} class="{" ".join(sorted(cls))}">' if cls else f"<{tag}>"
                self.problems.append(f"題目 {name!r} 裡有 {what}：做法和答案放進 <details class=\"model\">，讀者寫完才打開"
                                     "（逐步的講解放 <details class=\"steps\">）；要馬上對的單一答案用 .fill 填答格")
            if (tag == "figure" or (tag == "pre" and bool(cls & OUTPUT_CLASSES))) and not self.inside("model"):
                q["shows"] = True
            if tag == "li" and self.stack and "hints" in self.stack[-1][1]:
                q["hints"] += 1
            if tag == "h2":
                self.heading = ""
            if "pad" in cls:
                self.problems.append("不用自己放 .pad：practice.py 會在每題最後加畫布")
        if "fill" in cls:
            self.fill(tag, a)
        if tag == "figure":
            self.figures.append({"caption": "", "in_caption": False,
                                 "panel": self.inside("panel"), "tab": (a.get("data-tab") or "").strip()})
        if tag == "figcaption" and self.figures:
            self.figures[-1]["in_caption"] = True
        if tag not in VOID:
            self.stack.append((tag, cls))

    def fill(self, tag, a):
        """填答格：頁面上對答案的一格。"""
        if not (self.qs and self.inside("q")):
            self.problems.append(f'<{tag} class="fill"> 不在題目裡：填答格要放在 section.q 裡')
            return
        q = self.qs[-1]
        q["fills"] += 1
        name = q["id"] or q["title"]
        if not [x for x in (a.get("data-answer") or "").split("|") if x.strip()]:
            self.problems.append(f"題目 {name!r} 的填答格沒有 data-answer：寫可接受的答案，多個用 | 分開")
        tol = a.get("data-tol")
        if tol is not None and not re.fullmatch(r"\s*\d+(\.\d+)?\s*", tol):
            self.problems.append(f"data-tol={tol!r} 要是不小於 0 的數字：數字答案的容許誤差")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag == "figcaption" and self.figures:
            self.figures[-1]["in_caption"] = False
        if tag == "figure" and self.figures:
            fig = self.figures.pop()
            cap = fig["caption"].strip()
            if fig["panel"] and not fig["tab"]:
                self.problems.append(f"查表面板的 figure 沒有 data-tab（{cap[:30]!r}）：寫分頁名稱，例如「Z 表」")
        if tag == "h2" and self.heading is not None and self.qs:
            self.qs[-1]["title"] = " ".join(self.heading.split())
            self.heading = None
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        if PLACEHOLDER.search(data):
            self.problems.append(f"還有沒填的 {{{{佔位}}}}：「{' '.join(data.split())[:30]}」先跑產生數字的腳本")
        if self.heading is not None:
            self.heading += data
        for fig in self.figures:
            if fig["in_caption"]:
                fig["caption"] += data
        if any(t in NON_PROSE_TAGS for t, _ in self.stack):
            return
        if self.qs and self.inside("ref"):
            self.qs[-1]["refs"] += SECTION_REF.findall(data)
        elif self.qs and (self.inside("hints") or self.inside("steps")):
            self.qs[-1]["links"] += SECTION_REF.findall(data)  # 提示和詳解裡的 § 也會連到導讀頁，但不算「對照」


def guide_anchors(path: Path) -> set:
    text = path.read_text(encoding="utf-8")
    return set(re.findall(r'\bid="(s\d+(?:-\d+)?)"', text))


def guide_types(path: Path) -> dict:
    """導讀頁題型表每一列：{data-type: 是不是讀圖題（data-reads="figure"）}，照表上的順序。"""
    text = path.read_text(encoding="utf-8")
    rows = (tag_attrs(m.group(0)) for m in re.finditer(r"<tr\b[^>]*\bdata-type\s*=[^>]*>", text, re.I))
    return {a["data-type"]: a.get("data-reads") == "figure" for a in rows}


def anchor(ref: str) -> str:
    return "s" + ref.replace(".", "-")


def lint(src: str, base: Path, out_dir: Path, notes=None) -> list:
    """會讓頁面壞掉、或讓題目對不回導讀頁和答案檔的事。notes 給一個 list 時，把不擋產出的提醒加進去。"""
    p = Lint()
    p.feed(src)
    p.close()
    problems = list(p.problems)
    body = p.body or {}
    missing = [k for k in BODY_ATTRS if not (body.get(k) or "").strip()]
    if p.body is None or missing:
        problems.append(f"<body> 缺 {'、'.join(missing or BODY_ATTRS)}：見 practice.py 開頭的說明")

    mode = (body.get("data-mode") or "practice").strip()
    mock = mode == "mock"
    if mode not in MODES:
        problems.append(f'<body data-mode="{mode}"> 看不懂：不寫是練習頁，模擬卷寫 mock')
    if mock and body.get("data-minutes") is not None and not re.fullmatch(r"[1-9]\d*", body["data-minutes"].strip()):
        problems.append(f'data-minutes={body["data-minutes"]!r} 要是正整數：建議作答時間幾分鐘，照老師的考試時間按題數比例抓')

    ids = [q["id"] for q in p.qs]
    for q in p.qs:
        name = q["title"] or q["id"] or "(沒有標題)"
        if not q["title"]:
            problems.append(f"題目 {q['id']!r} 沒有 <h2> 標題：導覽列和複製出去的圖都用它")
        if not q["id"]:
            problems.append(f"題目「{name}」沒有 data-id：它是畫布存檔的鍵，也是答案檔裡找這題的名字")
        elif not SLUG.match(q["id"]) or ORDINAL.match(q["id"]):
            problems.append(f"題目代號 {q['id']!r} 要寫成說明內容的英文小寫代號（例如 ci-sigma-known），"
                            "不能只是編號：插題或改順序後，存在瀏覽器裡的筆跡會跑到別題")
        elif ids.count(q["id"]) > 1:
            problems.append(f"題目代號 {q['id']!r} 重複了：每題一個")
        if q["drill"] and not q["fills"]:
            problems.append(f'小題「{name}」沒有填答格：加一個 class="fill" data-answer="…" 的元素，'
                            "讀者填了馬上知道對錯，不用貼回對話")
        if mock:
            if q["drill"]:
                problems.append(f"模擬卷不放小題（「{name}」）：短的題目寫成整題，裡面放填答格，data-space=\"none\"")
            if q["hints"] or q["steps"]:
                problems.append(f"模擬卷的題目「{name}」不放提示和逐步詳解：考試沒有提示，卡住的題型回練習頁練")
            if q["refs"]:
                problems.append(f"模擬卷的題目「{name}」不寫對照的 §：考試沒有提示，對照留到做完後的範本答案")
        if not q["drill"]:
            if q["model"] > 1:
                problems.append(f'題目「{name}」有 {q["model"]} 個 <details class="model">：一題一個範本答案，自評的分數才算得出來')
            elif not q["model"] and not q["fills"]:
                problems.append(f'題目「{name}」沒有範本答案也沒有填答格，讀者對不了答案：加 <details class="model">，'
                                '或要馬上對的答案用 class="fill" 的填答格')

    full = [q for q in p.qs if not q["drill"]]
    if not (full if mock else p.qs):
        problems.append('頁面沒有題目：每題寫成 <section class="q" data-id="…">')

    guides = [g.strip() for g in (body.get("data-guide") or "").split(";") if g.strip()]
    if len(guides) > 1 and not mock:
        problems.append("練習頁的 data-guide 只能寫一份導讀頁；跨 topic 的題目放模擬卷（data-mode=\"mock\"）")
    refs = {r for q in p.qs for r in q["refs"] + q["links"]}
    missing = [g for g in guides if not (out_dir / g).is_file()]
    for g in missing:
        problems.append(f"找不到導讀頁 {out_dir / g}：data-guide 相對於產出的練習頁；先用 build.py 組好導讀頁")
    if guides and not missing:
        types = {}
        for g in guides:
            types.update(guide_types(out_dir / g))
        problems += type_coverage(full, types, "、".join(guides))
        used = {t for q in p.qs for t in q["types"]}
        idle = [t for t in types if t not in used]
        if idle and notes is not None:
            notes.append(f"題型表上這幾個題型沒有題目：{'、'.join(idle)}。對照計畫：是決定不出，還是漏了")
        if not mock:
            guide, gpath = guides[0], out_dir / guides[0]
            have = guide_anchors(gpath)
            bad = sorted((r for r in refs if anchor(r) not in have), key=lambda r: [int(x) for x in r.split(".")])
            if bad:
                problems.append(f"導讀頁 {guide} 沒有 §{'、§'.join(bad)}：段落編號改過了，對照的 § 要跟著改")

    answers = body.get("data-answers")
    if answers:
        apath = base / answers
        if not apath.is_file():
            problems.append(f"找不到答案檔 {apath}：每題的答案由腳本算好寫在這裡，批改時用")
        else:
            text = apath.read_text(encoding="utf-8")
            lost = [i for i in ids if i and i not in text]
            if lost:
                problems.append(f"答案檔沒有這幾題：{'、'.join(lost)}。每題的答案標題寫上題目代號，批改時才對得上")
    return problems


def type_coverage(full: list, types: dict, guide: str) -> list:
    """導讀頁有題型表時，每題整題寫明練的是哪幾列；讀圖題型的題目有圖或程式／軟體輸出。"""
    if not types:  # 導讀頁沒有題型表：題目只靠 § 對回導讀頁
        return []
    problems = []
    for q in full:
        name = q["title"] or q["id"]
        if not q["types"]:
            problems.append(f"題目「{name}」沒有 data-type：寫它練的是題型表的哪一列（{'、'.join(types)}），可以寫好幾個，用空白分開")
        for t in q["types"]:
            if t not in types:
                problems.append(f"題目「{name}」的 data-type={t!r} 不在導讀頁的題型表裡（{'、'.join(types)}）")
            elif types[t] and not q["shows"]:
                problems.append(f'題目「{name}」練的是讀圖題型 {t!r}，卻沒有圖：放腳本畫的 <figure>'
                                '或排成考試樣式的 <pre class="output"> 程式／軟體輸出，考試就是這樣給')
    return problems


ATTR = re.compile(r"""([\w-]+)\s*=\s*(?:"([^"]*)"|'([^']*)')""")


def tag_attrs(tag: str) -> dict:
    """開始標籤的屬性（雙引號、單引號都行），值已經解開 &amp; 這類字元參照。"""
    return {m.group(1).lower(): html.unescape(m.group(2) if m.group(2) is not None else m.group(3))
            for m in ATTR.finditer(tag)}


def body_parts(src: str):
    m = re.search(r"<body\b([^>]*)>(.*?)</body>", src, re.S | re.I)
    if not m:
        raise SystemExit("原始檔沒有 <body>")
    return tag_attrs(m.group(1)), m.group(2)


def q_tags(inner: str):
    """每個 <section class="q"> 的開始標籤和屬性（引號、屬性順序不拘）。"""
    for m in re.finditer(r"<section\b[^>]*>", inner, re.I):
        a = tag_attrs(m.group(0))
        if "q" in (a.get("class") or "").split():
            yield m, a


def add_pads(inner: str, paper: bool = False) -> str:
    """每題整題加一張畫布，排在提示、逐步詳解、範本答案前面（都沒有就排在最後）：先寫，往下才是提示和答案。data-h 可以在 section 上覆寫預設高度。
    小題只填一格，不加畫布（要打草稿的那一題在 section 寫 data-h）。
    paper（模擬卷）：同一個位置改放一張紙上的作答頁 .space，只在列印時出現；不夠寫的人自己加紙。
    寫了 data-space="none" 的題答案直接寫在題目上，不放作答頁。"""
    out, pos = [], 0
    low = inner.lower()
    for m, a in q_tags(inner):
        if "drill" in a["class"].split() and not a.get("data-h"):
            continue
        if paper and (a.get("data-space") or "").strip() == "none":
            continue
        height = int(a.get("data-h") or PAD_H)
        end = low.index("</section>", m.end())
        model = next((d.start() for d in re.finditer(r"<(?:details|ol)\b[^>]*>", inner[m.end():end], re.I)
                      if {"model", "steps", "hints"} & set((tag_attrs(d.group(0)).get("class") or "").split())), None)
        if model is not None:
            end = m.end() + model
        qid = html.escape(a["data-id"])
        if paper:  # 一張整頁的作答頁；題目那一頁剩下的空白也可以寫
            box = f'<div class="space" data-id="{qid}"></div>\n'
        else:
            box = f'<div class="pad" data-id="{qid}" data-h="{height}"></div>\n'
        out += [inner[pos:end], box]
        pos = end
    out.append(inner[pos:])
    return "".join(out)


def questions(inner: str) -> list:
    """每題的代號、標題、滿分（給分點的總分；沒有給分點就一個填答格一分）、有沒有作答頁，照頁面上的順序。"""
    out = []
    low = inner.lower()
    for m, a in q_tags(inner):
        body = inner[m.end():low.index("</section>", m.end())]
        h2 = re.search(r"<h2\b[^>]*>(.*?)</h2>", body, re.S | re.I)
        given = (tag_attrs(t.group(0)).get("data-marks", "").strip() for t in re.finditer(r"<li\b[^>]*>", body, re.I))
        marks = sum(int(g) for g in given if g.isdigit())
        if not marks:  # 沒有給分點：一個填答格一分
            marks = sum("fill" in (tag_attrs(t.group(0)).get("class") or "").split() for t in re.finditer(r"<\w+\b[^>]*>", body))
        out.append({"id": a["data-id"], "title": re.sub(r"<[^>]+>", "", h2.group(1)).strip() if h2 else a["data-id"],
                    "marks": marks, "space": (a.get("data-space") or "").strip() != "none"})
    return out


def finish_sections(inner: str) -> str:
    """section.q 加上 id 讓導覽列跳過去；data-differs 是給出題人的，不放進頁面。"""
    out, pos = [], 0
    for m, a in q_tags(inner):
        tag = re.sub(r"""\s+data-differs\s*=\s*("[^"]*"|'[^']*')""", "", m.group(0), flags=re.I)
        if "id" not in a:
            tag = tag[:-1] + f' id="q-{html.escape(a["data-id"])}">'
        out += [inner[pos:m.start()], tag]
        pos = m.end()
    out.append(inner[pos:])
    return "".join(out)


def cover(inner: str, minutes: str, tables: bool) -> str:
    """模擬卷的封面：建議時間、滿分、「題目／滿分／得分」表（得分留給讀者在紙上填）和作答規則。
    tables：卷末有沒有附表（查表面板）；沒附就不提。"""
    qs = questions(inner)
    total = sum(q["marks"] for q in qs)
    facts = ([f"建議時間 {html.escape(minutes)} 分鐘"] if minutes else []) + [f"滿分 {total} 分"]
    rows = "".join(f'<tr><td>{html.escape(q["title"])}</td><td>{q["marks"]}</td><td></td></tr>' for q in qs)
    return (f'<div class="cover">\n<p class="facts">{"　".join(facts)}</p>\n'
            f'<table><thead><tr><th>題目</th><th>滿分</th><th>得分</th></tr></thead>\n<tbody>{rows}'
            f'<tr class="total"><td>合計</td><td>{total}</td><td></td></tr></tbody></table>\n'
            f"<ul>\n<li>照考試做：不看導讀頁、不看筆記{'，只用卷末附的表' if tables else ''}。</li>\n"
            + ("<li>寫在題目下面的空白和後面的作答頁，每一步都寫出來，不夠寫就自己加紙；最後的答案再填到題目裡的底線上。</li>\n"
               if any(q["space"] for q in qs) else "<li>答案直接寫在題目裡的底線上。</li>\n") + "</ul>\n</div>\n")


def finish_models(inner: str) -> str:
    """details.model 和 details.steps 補上摘要，預設收起來。"""
    def repl(m):
        cls = (tag_attrs(m.group(0)).get("class") or "").split()
        summary = MODEL_SUMMARY if "model" in cls else STEPS_SUMMARY if "steps" in cls else None
        if summary is None:
            return m.group(0)
        tag = re.sub(r"\sopen(\s*=\s*(\"[^\"]*\"|'[^']*'))?", "", m.group(0), flags=re.I)
        return f"{tag}<summary>{summary}</summary>"
    return re.sub(r"<details\b[^>]*>", repl, inner, flags=re.I)


class _PracticeRefLinker(HTMLParser):
    """用 HTMLParser 在 .ref、.hints、.steps 容器內轉 §N 連結，支援任意巢狀標籤並跳過 <a>/<code>/<pre>/<script>/<style> 與註解。"""

    def __init__(self, src: str, guide: str):
        super().__init__(convert_charrefs=False)
        self.src = src
        self.guide = html.escape(guide)
        self.offs = line_offsets(src)
        self.stack = []  # [(tag, classes)]
        self.edits = []

    def _pos(self) -> int:
        ln, col = self.getpos()
        return self.offs[ln - 1] + col

    def handle_starttag(self, tag, attrs):
        t = tag.lower()
        if t not in VOID:
            self.stack.append((t, classes(attrs)))

    def handle_endtag(self, tag):
        t = tag.lower()
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == t:
                del self.stack[i:]
                break

    def handle_data(self, data):
        if "§" not in data:
            return
        if not any(c & LINKED for _, c in self.stack):
            return
        if any(t in ("a", "code", "pre", "script", "style") for t, _ in self.stack):
            return
        replaced = SECTION_REF.sub(
            lambda r: f'<a href="{self.guide}#{anchor(r.group(1))}" target="_blank">{r.group(0)}</a>',
            data,
        )
        if replaced != data:
            p = self._pos()
            self.edits.append((p, p + len(data), replaced))


def link_refs(inner: str, guide: str) -> str:
    """.ref、提示、逐步詳解裡的 §N 連到導讀頁那一段，開新分頁，練習頁上寫到一半的東西不會跑掉。"""
    if "§" not in inner:
        return inner
    parser = _PracticeRefLinker(inner, guide)
    parser.feed(inner)
    parser.close()
    if not parser.edits:
        return inner
    out, last = [], 0
    for start, end, rep in parser.edits:
        out.append(inner[last:start])
        out.append(rep)
        last = end
    out.append(inner[last:])
    return "".join(out)


def nav(inner: str) -> str:
    links = []
    for m, a in q_tags(inner):
        h2 = re.search(r"<h2\b[^>]*>(.*?)</h2>", inner[m.end():], re.S | re.I)
        title = re.sub(r"<[^>]+>", "", h2.group(1)).strip() if h2 else a["data-id"]
        cls = ' class="drill"' if "drill" in a["class"].split() else ""
        links.append(f'<a href="#{html.escape(a.get("id") or "q-" + a["data-id"])}"{cls}>{title}</a>')
    return f'<nav class="jump" aria-label="跳到題目">{"".join(links)}</nav>\n'


def panel(inner: str):
    """<aside class="panel" data-label="查表"> 裡的 figure 變成右下角按鈕打開的分頁面板。"""
    for m in re.finditer(r"(<aside\b[^>]*>)(.*?)</aside>", inner, re.S | re.I):
        a = tag_attrs(m.group(1))
        if "panel" not in (a.get("class") or "").split():
            continue
        label = html.escape(a.get("data-label") or "查表")
        tabs, bodies = [], []
        for i, fm in enumerate(re.finditer(r"(<figure\b[^>]*>)(.*?</figure>)", m.group(2), re.S | re.I)):
            tab = html.escape(tag_attrs(fm.group(1)).get("data-tab", ""))
            tabs.append(f'<button type="button" data-tab="t{i}" aria-pressed="{"true" if i == 0 else "false"}">{tab}</button>')
            # data-name：模擬卷把這些表印在卷末，每張表上面要有名字
            bodies.append(f'<figure data-tab="t{i}" data-name="{tab}"{"" if i == 0 else " hidden"}>{fm.group(2)}')
        html_ = (f'<button id="panel-btn" type="button">{label}</button>\n'
                 f'<aside id="panel" aria-label="{label}"><header>{"".join(tabs)}'
                 f'<button type="button" class="close">關閉</button></header>\n'
                 f'<div class="body">{"".join(bodies)}</div></aside>\n')
        return inner[:m.start()] + inner[m.end():], html_
    return inner, ""


def inline_images(page: str, base: Path) -> str:
    """圖片內嵌成單一檔案；有翻譯圖的預設顯示原圖（考試用原文），翻譯圖記在 data-zh，點圖切換。"""
    def data_uri(path):
        f = (base / path).resolve()
        if not f.is_file():
            raise SystemExit(f"找不到圖片：{f}")
        mime = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
        return f"data:{mime};base64,{base64.b64encode(f.read_bytes()).decode()}"

    def img(m):
        a = tag_attrs(m.group(0))
        if a.get("src", "").startswith("data:"):
            return m.group(0)
        keep = "".join(f' {k}="{html.escape(v)}"' for k, v in a.items() if k not in ("src", "data-zh", "data-en"))
        if "data-zh" not in a:
            return f'<img src="{data_uri(a["src"])}"{keep}>'
        en = data_uri(a["src"])
        return f'<img src="{en}" data-zh="{data_uri(a["data-zh"])}" data-en="{en}"{keep}>'

    return re.sub(r"<img\b[^>]*>", img, page, flags=re.I)


def howto(inner: str) -> str:
    """「怎麼用這頁」：只寫這一頁真的有的東西。"""
    def has(tag, cls):
        return any(cls in (tag_attrs(m.group(0)).get("class") or "").split() for m in re.finditer(rf"<{tag}\b[^>]*>", inner, re.I))

    qs = [a["class"].split() for _, a in q_tags(inner)]
    drills, full = any("drill" in c for c in qs), any("drill" not in c for c in qs)
    hints, steps, model = has("ol", "hints"), has("details", "steps"), has("details", "model")
    items = []
    if drills:
        items.append("小題一題問一件事，填好按「對答案」馬上知道對錯；錯兩次會公布答案。考前想再練，按「再做一次」。")
    if full and (has("p", "ref") or hints or steps):
        help_ = "卡住時" + ("按畫布下面的「看提示」，一次看一個" if hints else "")
        help_ += ("；提示看完還是不會，再打開「逐步詳解」照著做一遍" if hints and steps else "打開「逐步詳解」照著做一遍" if steps else "")
        items.append("題目裡的 § 會在新分頁打開導讀頁的那一段。" + (help_ + "。" if hints or steps else ""))
    if full:
        items.append("畫布：滑鼠按住拖曳就是寫字，觸控筆、手指也可以。按「文字」在畫布打字，或按「文字步驟」開流式文字框寫算式與推理；"
                     "工具列還有換顏色、橡皮擦、復原（Ctrl+Z）、加長、清空（要連按兩下）。寫的東西自動存在瀏覽器裡，也能按「匯出進度」存成 JSON。")
    if model:
        items.append("整題寫完才打開下面的範本答案，對照自己寫的；有給分點就一點一點勾，知道會拿幾分。"
                     "手寫步驟看不出哪裡錯，按「複製給助教」，到對話裡按 Ctrl+V 貼上。")
    items.append("全部做完按上面的「複製填答結果」貼到對話（打字的算式與步驟會自動附上），助教會記下哪些題型要再練，並依步驟診斷錯因。")
    items.append("上面每題的按鈕會變色：綠色是填答格全對，紅色是有答錯的" + ("，打勾是對過範本答案。" if model else "。"))
    return ('<details class="howto">\n<summary>怎麼用這頁</summary>\n<ul>\n'
            + "".join(f"<li>{x}</li>\n" for x in items) + "</ul>\n</details>\n")


HOWTO_MOCK = """<div class="howto">
<b>這份模擬卷在紙上做</b>
<ul>
<li>印考卷：用這頁旁邊同名的 PDF，或按「列印考卷」。有平板和筆的話，也可以用筆記 app 打開那份 PDF 直接寫。照封面的規則做完。</li>
<li>做完回到這頁，把答案填進題目裡的格子，按「我在紙上做完了」：填答格一次對完，每題的範本答案才會出現。有給分點就一點一點勾，算出你的分數。</li>
<li>想在紙上對答案：印檔名結尾是 -answers 的 PDF，或按「列印答案」。</li>
<li>對完按「複製填答結果」貼到對話，助教會記下哪些題型要再練。要助教看步驟，把寫好的那幾頁拍照貼到對話。</li>
</ul>
</div>
"""

MOCK_BAR = ('<div class="mockbar"><button type="button" data-act="print">列印考卷</button>'
            '<button type="button" data-act="print-key">列印答案</button>'
            '<button type="button" data-act="done">我在紙上做完了</button>'
            '<span class="status" aria-live="polite"></span></div>\n')

# 深淺色由讀者切換、記在瀏覽器（和導讀頁同一個鍵）；在樣式之前套上，打開時才不會先閃一下白底
THEME = ('<script>try { if (localStorage.getItem("tutor-theme") === "dark") '
         'document.documentElement.dataset.theme = "dark"; } catch (e) {}</script>\n')
PREFS = '<p class="prefs"><button id="theme" type="button" aria-pressed="false">深色</button></p>\n'

REPORT = ('<p class="report"><button id="report" type="button">複製填答結果</button> '
          '<button id="export-progress" type="button">匯出進度</button> '
          '<button id="import-progress" type="button">匯入進度</button>'
          '<input id="import-file" type="file" accept="application/json,.json" hidden>'
          '<span class="status" aria-live="polite"></span></p>\n')


def build(src: str, base: Path) -> str:
    a, inner = body_parts(src)
    inner, panel_html = panel(inner)
    mock = a.get("data-mode") == "mock"
    inner = finish_models(finish_sections(add_pads(inner, paper=mock)))
    if not mock:
        inner = link_refs(inner, a["data-guide"])
    title = html.escape(a["data-title"])
    mode = ' data-mode="mock"' if mock else ""
    top = HOWTO_MOCK + MOCK_BAR + cover(inner, (a.get("data-minutes") or "").strip(), bool(panel_html)) if mock else howto(inner)
    page = (f'<!DOCTYPE html>\n<html lang="zh-Hant">\n<head>\n<meta charset="utf-8">\n'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>{title}</title>\n'
            f"{THEME}<style>\n{CSS.read_text(encoding='utf-8')}</style>\n</head>\n"
            f'<body data-key="{html.escape(a["data-key"])}" data-title="{title}"{mode}>\n<main>\n<h1>{title}</h1>\n{PREFS}{top}'
            f"{nav(inner)}{REPORT}{inner}\n</main>\n{panel_html}"
            f"<script>\n{JS.read_text(encoding='utf-8')}</script>\n</body>\n</html>\n")
    return inline_images(page, base)


# 模擬卷的範本答案按「我在紙上做完了」才出現：量溢出之前先讓它出現
REVEAL = 'document.body.classList.add("submitted");'
# 模擬卷印成 PDF：(檔名結尾, 網址結尾)。頁面的 JS 看到 #answers 就換成答案版
PDFS = (("", ""), ("-answers", "#answers"))


def print_pdfs(page: Path):
    """用無頭瀏覽器把模擬卷印成 PDF（紙張大小和邊界由頁面的 @page 決定），放在 page 旁邊。
    回傳寫出的檔；找不到瀏覽器回傳 None。"""
    browser = overflow.find_browser()
    if not browser:
        return None
    out = []
    for suffix, fragment in PDFS:
        pdf = page.with_name(page.stem + suffix + ".pdf")
        pdf.unlink(missing_ok=True)
        work = Path(tempfile.mkdtemp(prefix="mock-print-"))  # 自己的 profile：不碰使用者開著的瀏覽器，也沒有存過的作答
        try:
            subprocess.run(
                [browser, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
                 f"--user-data-dir={work / 'profile'}", "--no-pdf-header-footer", "--virtual-time-budget=5000",
                 f"--print-to-pdf={pdf}", page.resolve().as_uri() + fragment],
                capture_output=True, timeout=180)
        finally:
            shutil.rmtree(work, ignore_errors=True)
        if not pdf.is_file():
            raise SystemExit(f"瀏覽器沒有印出 {pdf}")
        out.append(pdf)
    return out


def main(argv=None, measure=overflow.measure, printer=print_pdfs) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")  # Windows 終端機預設不是 UTF-8
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("src", type=Path)
    ap.add_argument("-o", "--out", type=Path)
    args = ap.parse_args(argv)
    src = args.src.read_text(encoding="utf-8")
    out = args.out or args.src.with_name(args.src.stem.removesuffix("-src") + ".html")
    notes = []
    problems = lint(src, args.src.parent, out.parent, notes)
    if problems:
        print(f"{args.src}：{len(problems)} 個問題，沒有產出", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    out.write_text(build(src, args.src.parent), encoding="utf-8")
    if not overflow.deliverable(out, args.src, measure(out, prepare=REVEAL)):
        return 1
    print(out)
    for note in notes:
        print(f"提醒：{note}", file=sys.stderr)
    if body_parts(src)[0].get("data-mode") == "mock":
        pdfs = printer(out)
        if pdfs is None:
            print("提醒：找不到 Chrome 或 Edge，沒有印 PDF；用瀏覽器打開頁面，按「列印考卷」「列印答案」各存一份",
                  file=sys.stderr)
        for pdf in pdfs or []:
            print(pdf)
    return 0


if __name__ == "__main__":
    sys.exit(main())
