"""把練習頁的原始 HTML 組成單一檔案：每題下面加一張能手寫、能打字的畫布，填答格在頁面上對答案，並檢查規則；規則不過就不產出。

    python practice.py <practice-src.html> -o <topicN-practice.html>

組好之後用本機的 Chrome 或 Edge 在寬螢幕和手機寬各量一次水平溢出（pages/scripts/overflow.py）：
有溢出就不產出，逐條印出哪個元素超出幾 px；找不到瀏覽器只提醒。

原始檔的 <body> 寫：
    data-title    頁面標題
    data-key      畫布存檔的名字空間（同一台電腦上每份練習頁要不一樣，例如 isom3031-topic4）
    data-guide    導讀頁檔名，相對於產出的練習頁；題目裡的 §N 會連到導讀頁那一段
    data-answers  答案檔，相對於原始檔；批改用，不放進頁面

模擬卷（同一套組頁，照考試的樣子做）：<body data-mode="mock" data-minutes="60">
    data-minutes  作答時間（分鐘）；頁面頂端倒數，按「交卷」才對填答格、才看得到範本答案
    data-guide    可以列好幾份導讀頁，用 ; 分開（跨 topic 的累積卷）
    只有完整題目：不放基本功、不寫對照的 §、不用 data-differs。只列一份導讀頁時，它的每個題型至少一題。

填答格（頁面上馬上對答案，寫法照 Moodle 的 short answer／numerical 題型：多個可接受的答案、不分大小寫、數字可給容許誤差）：
    <p class="fill" data-answer="2.262|2.26" data-why="df = 9、雙尾 α = 0.05，查 t 表">臨界值 =</p>
    data-answer   可接受的答案，用 | 分開；第一個是公布的答案。兩邊都是數字時比數值
    data-tol      數字的容許誤差（預設 0）
    data-why      一句原因：答對或公布答案時顯示。基本功必填
基本功錯兩次就公布答案和原因；整題的填答格只說對不對，不公布，步驟由 Claude 批改。

範本答案（每題完整題目一個，讀者寫完才打開，照給分點自己勾，勾的結果會進「複製填答結果」）：
    <details class="model">
      <div class="sheet">老師格式的完整答案</div>
      <ul class="rubric"><li data-marks="2">寫出 H0、Ha</li><li data-marks="1">結論句寫明顯著水準</li></ul>
    </details>
    data-marks    這個給分點幾分（正整數），配分照老師的評分方式

讀圖題：導讀頁題型表那一列寫了 data-reads="figure" 的題型，題目裡要有 <figure> 或 <pre class="mtb">（軟體輸出）。

只用標準函式庫，CI 才能直接跑測試。
"""

import argparse
import base64
import html
import mimetypes
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

# 共用的水平溢出量測在 plugin 根目錄的 pages/scripts/
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "pages" / "scripts"))
import overflow  # noqa: E402

ASSETS = Path(__file__).resolve().parents[1] / "assets"
CSS = ASSETS / "practice.css"
JS = ASSETS / "practice.js"

BODY_ATTRS = ("data-title", "data-key", "data-guide", "data-answers")
# 基本功小題至少幾題：每題只考一個判斷（用哪張表、哪一尾、df 多少），整題做錯時看不出錯在哪一步
MIN_DRILLS = 3
# 題型表的每個題型至少幾題變式（老師原題不算）：只做過一題，分不出是會了還是記得那一題
MIN_PER_TYPE = 2
MODES = ("practice", "mock")
ORIGINAL = "老師原題"
# 完整題目的畫布預設高度（畫布座標）；寫不下時讀者按「加長」。基本功只填一格，寫了 data-h 才有畫布
PAD_H = 900
# 題目代號是畫布存檔的鍵：照順序編的號（q1、練習 2）插題或改順序後，舊的筆跡會跑到別題
SLUG = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
ORDINAL = re.compile(r"^(?:q|p|ex|drill|practice|problem|question|item|task)?-?\d+[a-z]?$")
# 題目本身只放題目和填答格；做法和答案只能放在讀者寫完才打開的 details.model 裡
ANSWER_CLASSES = {"answer", "calc", "sheet", "origin", "trap", "summary"}
MODEL_SUMMARY = "寫完了再打開：範本答案和給分點"
SECTION_REF = re.compile(r"§(\d+(?:\.\d+)?)")
REMOTE = re.compile(r"^\s*(https?:)?//", re.I)
PLACEHOLDER = re.compile(r"\{\{|\}\}")


def classes(attrs) -> set:
    return set((dict(attrs).get("class") or "").split())


class Lint(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.problems = []
        self.body = None  # <body> 的屬性
        self.stack = []  # [(tag, classes)]
        self.qs = []  # 每題：{"id", "drill", "differs", "title", "refs", "fills"}
        self.figures = []  # 開著的 figure：{"zh", "none", "caption", "in_caption", "panel", "tab"}
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
                            "model": 0, "marks": 0, "shows": False})
            if a.get("data-h") is not None and not a["data-h"].strip().isdigit():
                self.problems.append(f"data-h={a['data-h']!r} 要是整數：畫布的高度（畫布座標）")
        elif self.qs and self.inside("q"):
            q = self.qs[-1]
            name = q["id"] or q["title"]
            if tag == "details" and "model" in cls and not q["drill"] and not self.inside("model"):
                q["model"] += 1
            elif self.inside("model"):
                if tag == "li" and self.inside("rubric"):
                    marks = (a.get("data-marks") or "").strip()
                    if marks.isdigit() and int(marks) > 0:
                        q["marks"] += int(marks)
                    else:
                        self.problems.append(f"題目 {name!r} 的給分點沒有 data-marks：每個 <li> 寫這一點幾分（正整數）")
            elif tag == "details" or cls & ANSWER_CLASSES:
                what = f'<{tag} class="{" ".join(sorted(cls))}">' if cls else f"<{tag}>"
                self.problems.append(f"題目 {name!r} 裡有 {what}：做法和答案放進 <details class=\"model\">，讀者寫完才打開；"
                                     "要馬上對的單一答案用 .fill 填答格")
            if (tag == "figure" or (tag == "pre" and "mtb" in cls)) and not self.inside("model"):
                q["shows"] = True
            if tag == "h2":
                self.heading = ""
            if "pad" in cls:
                self.problems.append("不用自己放 .pad：practice.py 會在每題最後加畫布")
        if "fill" in cls:
            self.fill(tag, a)
        if tag == "figure":
            self.figures.append({"zh": False, "none": a.get("data-tr") == "none", "caption": "", "in_caption": False,
                                 "panel": self.inside("panel"), "tab": (a.get("data-tab") or "").strip()})
        if tag == "img":
            if not self.figures:
                self.problems.append(f"圖片 {a.get('src', '')!r} 不在 <figure> 裡：每張圖都要有寫出處的 figcaption")
            elif a.get("data-zh"):
                self.figures[-1]["zh"] = True
        if tag == "figcaption" and self.figures:
            self.figures[-1]["in_caption"] = True
        if tag not in ("img", "br", "hr", "meta", "link", "input", "col", "wbr", "source"):
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
        if q["drill"] and not (a.get("data-why") or "").strip():
            self.problems.append(f"基本功 {name!r} 的填答格沒有 data-why：寫一句原因，答對或公布答案時顯示")
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
            if not cap:
                self.problems.append("figure 沒有 figcaption：寫出處（檔名與 p.頁碼）或這張圖是什麼")
            if not (fig["zh"] or fig["none"]):
                self.problems.append(f"圖片沒有翻譯（{cap[:30]!r}）：用 crop.py cut --zh 產生翻譯圖寫成 data-zh，"
                                     '圖上沒有要翻的字寫 data-tr="none"')
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
        if self.qs and self.inside("ref"):
            self.qs[-1]["refs"] += SECTION_REF.findall(data)


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


def lint(src: str, base: Path, out_dir: Path) -> list:
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
    if mock and not re.fullmatch(r"[1-9]\d*", (body.get("data-minutes") or "").strip()):
        problems.append('模擬卷的 <body> 要有 data-minutes：作答時間幾分鐘（正整數），照老師的考試時間按題數比例抓')

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
            problems.append(f'基本功「{name}」沒有填答格：加一個 class="fill" data-answer="…" data-why="…" 的元素，'
                            "讀者填了馬上知道對錯，不用貼回對話")
        if mock:
            if q["drill"]:
                problems.append(f"模擬卷不放基本功（「{name}」）：只放完整題目，照考試的樣子")
            if q["refs"]:
                problems.append(f"模擬卷的題目「{name}」不寫對照的 §：考試沒有提示，對照留到交卷後的範本答案")
        if not q["drill"] and not mock:
            if not q["refs"]:
                problems.append(f"題目「{name}」的 .ref 沒寫對照導讀頁的 §N：寫「對照 Eg 1（導讀頁 §16）」，讀者卡住時點過去看")
            if not q["differs"]:
                problems.append(f"題目「{name}」沒有 data-differs：寫這題和對照的例題哪裡不一樣（結論相反、陷阱不同），"
                                "照抄例題步驟的人會在這裡錯")
        if not q["drill"]:
            if q["model"] != 1:
                problems.append(f'題目「{name}」要有一個 <details class="model"> 範本答案（現在 {q["model"]} 個）：'
                                "老師格式的完整答案加給分點，讀者寫完自己對，不用等批改")
            elif not q["marks"]:
                problems.append(f'題目「{name}」的範本答案沒有給分點：加 <ul class="rubric">，每個 <li data-marks="分數"> 寫一個老師會給分的點')

    drills = [q for q in p.qs if q["drill"]]
    full = [q for q in p.qs if not q["drill"]]
    if mock:
        if not full:
            problems.append('模擬卷沒有題目（section class="q"）')
    elif len(drills) < MIN_DRILLS:
        problems.append(f'基本功小題（section class="q drill"）有 {len(drills)} 題，至少 {MIN_DRILLS} 題：'
                        "每題只考一個判斷，例如用 t 還是 Z、左尾右尾、查哪一格")
    if not full:
        problems.append('沒有完整題目（section class="q"）：基本功之後要有對照例題和作業的整題')
    elif drills and p.qs.index(full[0]) < p.qs.index(drills[-1]):
        problems.append("基本功小題要全部排在完整題目前面：先確定每個判斷會做，再做整題")

    guides = [g.strip() for g in (body.get("data-guide") or "").split(";") if g.strip()]
    if len(guides) > 1 and not mock:
        problems.append("練習頁的 data-guide 只能寫一份導讀頁；跨 topic 的題目放模擬卷（data-mode=\"mock\"）")
    refs = {r for q in p.qs for r in q["refs"]}
    missing = [g for g in guides if not (out_dir / g).is_file()]
    for g in missing:
        problems.append(f"找不到導讀頁 {out_dir / g}：data-guide 相對於產出的練習頁；先用 build.py 組好導讀頁")
    if guides and not missing:
        types = {}
        for g in guides:
            types.update(guide_types(out_dir / g))
        need = 0 if len(guides) > 1 else 1 if mock else MIN_PER_TYPE
        problems += type_coverage(full, types, "、".join(guides), need)
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


def type_coverage(full: list, types: dict, guide: str, need: int = MIN_PER_TYPE) -> list:
    """每題寫明練的是題型表的哪幾列；每個題型至少 need 題（老師原題不算）；讀圖題型的題目有圖或軟體輸出。"""
    if not types:
        return [f"導讀頁 {guide} 的題型表沒有 data-type：用現在的 build.py 重組導讀頁"]
    problems = []
    for q in full:
        name = q["title"] or q["id"]
        if not q["types"]:
            problems.append(f"題目「{name}」沒有 data-type：寫它練的是題型表的哪一列（{'、'.join(types)}），可以寫好幾個，用空白分開")
        for t in q["types"]:
            if t not in types:
                problems.append(f"題目「{name}」的 data-type={t!r} 不在導讀頁的題型表裡（{'、'.join(types)}）")
            elif types[t] and not q["shows"]:
                problems.append(f'題目「{name}」練的是讀圖題型 {t!r}，卻沒有圖：放腳本畫的 <figure>（時間序列圖、ACF 圖）'
                                '或排成老師樣式的 <pre class="mtb"> 軟體輸出，考試就是這樣給')
    for t in types:
        n = sum(t in q["types"] for q in full if not q["differs"].startswith(ORIGINAL))
        if n < need:
            problems.append(f"題型 {t!r} 只有 {n} 題變式，至少 {need} 題（{ORIGINAL}不算）：題型表上的每一種都要練到")
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


def add_pads(inner: str) -> str:
    """每題完整題目加一張畫布，排在範本答案前面（沒有範本答案就排在最後）：先寫，往下才是答案。data-h 可以在 section 上覆寫預設高度。
    基本功只填一格，不加畫布（要打草稿的那一題在 section 寫 data-h）。"""
    out, pos = [], 0
    low = inner.lower()
    for m, a in q_tags(inner):
        if "drill" in a["class"].split() and not a.get("data-h"):
            continue
        height = int(a.get("data-h") or PAD_H)
        end = low.index("</section>", m.end())
        model = next((d.start() for d in re.finditer(r"<details\b[^>]*>", inner[m.end():end], re.I)
                      if "model" in (tag_attrs(d.group(0)).get("class") or "").split()), None)
        if model is not None:
            end = m.end() + model
        out += [inner[pos:end], f'<div class="pad" data-id="{html.escape(a["data-id"])}" data-h="{height}"></div>\n']
        pos = end
    out.append(inner[pos:])
    return "".join(out)


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


def finish_models(inner: str) -> str:
    """details.model 補上摘要，預設收起來。"""
    def repl(m):
        a = tag_attrs(m.group(0))
        if "model" not in (a.get("class") or "").split():
            return m.group(0)
        tag = re.sub(r"\sopen(\s*=\s*(\"[^\"]*\"|'[^']*'))?", "", m.group(0), flags=re.I)
        return f"{tag}<summary>{MODEL_SUMMARY}</summary>"
    return re.sub(r"<details\b[^>]*>", repl, inner, flags=re.I)


def link_refs(inner: str, guide: str) -> str:
    """.ref 裡的 §N 連到導讀頁那一段，開新分頁，練習頁上寫到一半的東西不會跑掉。"""
    def repl(m):
        if "ref" not in (tag_attrs(m.group(1)).get("class") or "").split():
            return m.group(0)
        body = SECTION_REF.sub(
            lambda r: f'<a href="{html.escape(guide)}#{anchor(r.group(1))}" target="_blank">{r.group(0)}</a>', m.group(3))
        return m.group(1) + body + m.group(4)
    return re.sub(r"(<(p|div|span)\b[^>]*>)(.*?)(</\2>)", repl, inner, flags=re.S | re.I)


def nav(inner: str) -> str:
    links = []
    for m, a in q_tags(inner):
        h2 = re.search(r"<h2\b[^>]*>(.*?)</h2>", inner[m.end():], re.S | re.I)
        title = re.sub(r"<[^>]+>", "", h2.group(1)).strip() if h2 else a["data-id"]
        cls = ' class="drill"' if "drill" in a["class"].split() else ""
        head, _, rest = title.partition("\u3000")  # 「練習 1　防曬乳銷量」：題號一格、題名接在後面
        name = f'<span>{rest.strip()}</span>' if rest.strip() else ""
        links.append(f'<a href="#{html.escape(a.get("id") or "q-" + a["data-id"])}"{cls} title="{html.escape(html.unescape(title), quote=True)}">'
                     f'<b>{head.strip()}</b>{name}</a>')
    return f'<nav class="jump" aria-label="跳到題目">{"".join(links)}</nav>\n'


def panel(inner: str):
    """<aside class="panel" data-label="查表"> 裡的 figure 變成分頁面板；回傳（去掉 aside 的內文、放進書眉的按鈕、面板）。"""
    for m in re.finditer(r"(<aside\b[^>]*>)(.*?)</aside>", inner, re.S | re.I):
        a = tag_attrs(m.group(1))
        if "panel" not in (a.get("class") or "").split():
            continue
        label = html.escape(a.get("data-label") or "查表")
        tabs, bodies = [], []
        for i, fm in enumerate(re.finditer(r"(<figure\b[^>]*>)(.*?</figure>)", m.group(2), re.S | re.I)):
            tab = html.escape(tag_attrs(fm.group(1)).get("data-tab", ""))
            tabs.append(f'<button type="button" data-tab="t{i}" aria-pressed="{"true" if i == 0 else "false"}">{tab}</button>')
            bodies.append(f'<figure data-tab="t{i}"{"" if i == 0 else " hidden"}>{fm.group(2)}')
        html_ = (f'<aside id="panel" aria-label="{label}"><header>{"".join(tabs)}'
                 f'<button type="button" class="close">關閉</button></header>\n'
                 f'<div class="body">{"".join(bodies)}</div></aside>\n')
        return inner[:m.start()] + inner[m.end():], f'<button id="panel-btn" type="button">{label}</button>', html_
    return inner, "", ""


def inline_images(page: str, base: Path) -> str:
    """圖片內嵌成單一檔案；有翻譯圖的預設顯示中文，原圖記在 data-en，點圖切換。"""
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
        zh = data_uri(a["data-zh"])
        return f'<img src="{zh}" data-zh="{zh}" data-en="{data_uri(a["src"])}"{keep}>'

    return re.sub(r"<img\b[^>]*>", img, page, flags=re.I)


HOWTO = """<details class="howto">
<summary>怎麼用這頁</summary>
<ul>
<li>先做最上面的「基本功」：每題只考一個判斷，填好按「對答案」馬上知道對錯；錯兩次會公布答案和原因。考前想再練，按「再做一次」。再做下面的整題。</li>
<li>每題標了對照導讀頁的哪一段，點 § 會在新分頁打開；卡住時去看那題例題的做法。</li>
<li>畫布：滑鼠按住拖曳就是寫字，觸控筆、手指也可以。按「文字」再點畫布任何地方就能打字；點已經打的字可以改，按 Esc 或點別處收起來。</li>
<li>工具列還有換顏色、橡皮擦、復原（Ctrl+Z）、加長、清空（要連按兩下）。寫的東西自動存在這台電腦的瀏覽器裡，關掉再開還在。基本功沒有畫布，直接填。</li>
<li>整題寫完才打開下面的「範本答案和給分點」，照老師的給分點一點一點勾，就知道會拿幾分。有填答格的先對最後的數字。看不出步驟哪裡錯，按「複製給 Claude」，到對話裡按 Ctrl+V 貼上。</li>
<li>全部做完按上面的「複製填答結果」貼到對話，Claude 會記下哪些題型要再練。</li>
<li>上面每題的按鈕會變色：綠色是填答格全對，紅色是有答錯的，打勾是對過範本答案。</li>
</ul>
</details>
"""

HOWTO_MOCK = """<div class="howto">
<b>這是模擬卷</b>
<ul>
<li>照考試做：不看導讀頁、不看筆記，只用考試發的表（計時列上的「查表」）。準備好再按「開始計時」。</li>
<li>每題寫在畫布上，最後的數字填進格子。作答時不會告訴你對錯。</li>
<li>寫完或時間到按「交卷」：填答格一次對完，每題的範本答案和給分點才會出現。照給分點一點一點勾，算出你的分數。</li>
<li>對完按「複製填答結果」貼到對話，Claude 會記下哪些題型要再練。</li>
</ul>
</div>
"""

MOCK_BAR = ('<div class="clock" data-minutes="{minutes}"><span class="left" aria-live="off"></span>'
            '<button type="button" data-act="start">開始計時</button>'
            '<button type="button" data-act="submit" hidden>交卷</button><span class="status" aria-live="polite"></span>'
            '{here}{panel}</div>\n')

# 書眉：固定在頂端，practice.js 把現在第幾題寫進 .here；模擬卷的書眉就是計時列
HERE = '<button type="button" class="here" title="回到題號格"></button>'
BAR = '<div class="bar">{here}{panel}</div>\n'

REPORT = ('<p class="report"><button id="report" type="button">複製填答結果</button>'
          '<span class="status" aria-live="polite"></span></p>\n')


def build(src: str, base: Path) -> str:
    a, inner = body_parts(src)
    inner, panel_btn, panel_html = panel(inner)
    mock = a.get("data-mode") == "mock"
    inner = finish_models(finish_sections(add_pads(inner)))
    if not mock:
        inner = link_refs(inner, a["data-guide"])
    has_lead = re.search(r"""class\s*=\s*["'][^"']*\blead\b""", inner)
    lead = "" if has_lead or mock else '<p class="lead">每題和導讀頁的一題例題或作業同類型，只換了情境和數字，結論不一定一樣。</p>\n'
    title = html.escape(a["data-title"])
    mode = ' data-mode="mock"' if mock else ""
    howto = (HOWTO_MOCK + MOCK_BAR.format(minutes=html.escape(a["data-minutes"].strip()), here=HERE, panel=panel_btn)) if mock else HOWTO
    bar = "" if mock else BAR.format(here=HERE, panel=panel_btn)
    page = (f'<!DOCTYPE html>\n<html lang="zh-Hant">\n<head>\n<meta charset="utf-8">\n'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>{title}</title>\n'
            f"<style>\n{CSS.read_text(encoding='utf-8')}</style>\n</head>\n"
            f'<body data-key="{html.escape(a["data-key"])}" data-title="{title}"{mode}>\n<main>\n{bar}<h1>{title}</h1>\n{lead}{howto}'
            f"{nav(inner)}{REPORT}{inner}\n</main>\n{panel_html}"
            f"<script>\n{JS.read_text(encoding='utf-8')}</script>\n</body>\n</html>\n")
    return inline_images(page, base)


# 模擬卷的題目按「開始計時」才出現、範本答案交卷才出現：量溢出之前先讓它們都出現
REVEAL = 'document.body.classList.add("started", "submitted");'


def main(argv=None, measure=overflow.measure) -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")  # Windows 終端機預設不是 UTF-8
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("src", type=Path)
    ap.add_argument("-o", "--out", type=Path)
    args = ap.parse_args(argv)
    src = args.src.read_text(encoding="utf-8")
    out = args.out or args.src.with_name(args.src.stem.removesuffix("-src") + ".html")
    problems = lint(src, args.src.parent, out.parent)
    if problems:
        print(f"{args.src}：{len(problems)} 個問題，沒有產出", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    out.write_text(build(src, args.src.parent), encoding="utf-8")
    if not overflow.deliverable(out, args.src, measure(out, prepare=REVEAL)):
        return 1
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
