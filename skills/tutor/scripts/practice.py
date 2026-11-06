"""把練習頁的原始 HTML 組成單一檔案：每題下面加一張能手寫、能打字的畫布，並檢查規則；規則不過就不產出。

    python practice.py <practice-src.html> -o <topicN-practice.html>

原始檔的 <body> 寫：
    data-title    頁面標題
    data-key      畫布存檔的名字空間（同一台電腦上每份練習頁要不一樣，例如 isom3031-topic4）
    data-guide    導讀頁檔名，相對於產出的練習頁；題目裡的 §N 會連到導讀頁那一段
    data-answers  答案檔，相對於原始檔；批改用，不放進頁面

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

ASSETS = Path(__file__).resolve().parents[1] / "assets"
CSS = ASSETS / "practice.css"
JS = ASSETS / "practice.js"

BODY_ATTRS = ("data-title", "data-key", "data-guide", "data-answers")
# 基本功小題至少幾題：每題只考一個判斷（用哪張表、哪一尾、df 多少），整題做錯時看不出錯在哪一步
MIN_DRILLS = 3
# 畫布預設高度（畫布座標）；寫不下時讀者按「加長」
PAD_H = {"drill": 280, "full": 900}
# 題目代號是畫布存檔的鍵：照順序編的號（q1、練習 2）插題或改順序後，舊的筆跡會跑到別題
SLUG = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
ORDINAL = re.compile(r"^(?:q|p|ex|drill|practice|problem|question|item|task)?-?\d+[a-z]?$")
# 練習頁只放題目：做法和答案在答案檔，由 Claude 批改
ANSWER_CLASSES = {"answer", "calc", "sheet", "origin", "trap", "summary"}
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
        self.qs = []  # 每題：{"id", "drill", "differs", "title", "refs", "has_ref"}
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
                            "title": "", "refs": [], "has_ref": False})
            if a.get("data-h") is not None and not a["data-h"].strip().isdigit():
                self.problems.append(f"data-h={a['data-h']!r} 要是整數：畫布的高度（畫布座標）")
        elif self.qs and self.inside("q"):
            if tag == "details" or cls & ANSWER_CLASSES:
                what = f'<{tag} class="{" ".join(sorted(cls))}">' if cls else f"<{tag}>"
                self.problems.append(f"題目 {self.qs[-1]['id'] or self.qs[-1]['title']!r} 裡有 {what}："
                                     "練習頁不放做法和答案，答案寫在答案檔，做完由 Claude 批改")
            if tag == "h2":
                self.heading = ""
            if "ref" in cls:
                self.qs[-1]["has_ref"] = True
            if "pad" in cls:
                self.problems.append("不用自己放 .pad：practice.py 會在每題最後加畫布")
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
        if not q["drill"]:
            if not q["refs"]:
                problems.append(f"題目「{name}」的 .ref 沒寫對照導讀頁的 §N：寫「對照 Eg 1（導讀頁 §16）」，讀者卡住時點過去看")
            if not q["differs"]:
                problems.append(f"題目「{name}」沒有 data-differs：寫這題和對照的例題哪裡不一樣（結論相反、陷阱不同），"
                                "照抄例題步驟的人會在這裡錯")

    drills = [q for q in p.qs if q["drill"]]
    full = [q for q in p.qs if not q["drill"]]
    if len(drills) < MIN_DRILLS:
        problems.append(f'基本功小題（section class="q drill"）有 {len(drills)} 題，至少 {MIN_DRILLS} 題：'
                        "每題只考一個判斷，例如用 t 還是 Z、左尾右尾、查哪一格")
    if not full:
        problems.append('沒有完整題目（section class="q"）：基本功之後要有對照例題和作業的整題')
    elif drills and p.qs.index(full[0]) < p.qs.index(drills[-1]):
        problems.append("基本功小題要全部排在完整題目前面：先確定每個判斷會做，再做整題")

    guide = body.get("data-guide")
    refs = {r for q in p.qs for r in q["refs"]}
    if guide and refs:
        gpath = out_dir / guide
        if not gpath.is_file():
            problems.append(f"找不到導讀頁 {gpath}：data-guide 相對於產出的練習頁；先用 build.py 組好導讀頁")
        else:
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
    """每題的 </section> 前面加一張畫布；data-h 可以在 section 上覆寫預設高度。"""
    out, pos = [], 0
    low = inner.lower()
    for m, a in q_tags(inner):
        drill = "drill" in a["class"].split()
        height = int(a.get("data-h") or PAD_H["drill" if drill else "full"])
        end = low.index("</section>", m.end())
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
            bodies.append(f'<figure data-tab="t{i}"{"" if i == 0 else " hidden"}>{fm.group(2)}')
        html_ = (f'<button id="panel-btn" type="button">{label}</button>\n'
                 f'<aside id="panel" aria-label="{label}"><header>{"".join(tabs)}'
                 f'<button type="button" class="close">關閉</button></header>\n'
                 f'<div class="body">{"".join(bodies)}</div></aside>\n')
        return inner[:m.start()] + inner[m.end():], html_
    return inner, ""


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


HOWTO = """<div class="howto">
<b>怎麼用這頁</b>
<ul>
<li>先做最上面的「基本功」：每題只考一個判斷，錯了馬上知道錯在哪。再做下面的整題。</li>
<li>每題標了對照導讀頁的哪一段，點 § 會在新分頁打開；卡住時去看那題例題的做法。</li>
<li>畫布：滑鼠按住拖曳就是寫字，觸控筆、手指也可以。按「文字」再點畫布任何地方就能打字；點已經打的字可以改，按 Esc 或點別處收起來。</li>
<li>工具列還有換顏色、橡皮擦、復原（Ctrl+Z）、加長、清空（要連按兩下）。寫的東西自動存在這台電腦的瀏覽器裡，關掉再開還在。</li>
<li>做完一題按「複製給 Claude」，到對話裡按 Ctrl+V 貼上，Claude 照你寫的步驟批改。這頁沒有答案。</li>
</ul>
</div>
"""


def build(src: str, base: Path) -> str:
    a, inner = body_parts(src)
    inner, panel_html = panel(inner)
    inner = link_refs(finish_sections(add_pads(inner)), a["data-guide"])
    has_lead = re.search(r"""class\s*=\s*["'][^"']*\blead\b""", inner)
    lead = "" if has_lead else '<p class="lead">每題和導讀頁的一題例題或作業同類型，只換了情境和數字，結論不一定一樣。</p>\n'
    title = html.escape(a["data-title"])
    page = (f'<!DOCTYPE html>\n<html lang="zh-Hant">\n<head>\n<meta charset="utf-8">\n'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>{title}</title>\n'
            f"<style>\n{CSS.read_text(encoding='utf-8')}</style>\n</head>\n"
            f'<body data-key="{html.escape(a["data-key"])}" data-title="{title}">\n<main>\n<h1>{title}</h1>\n{lead}{HOWTO}'
            f"{nav(inner)}{inner}\n</main>\n{panel_html}"
            f"<script>\n{JS.read_text(encoding='utf-8')}</script>\n</body>\n</html>\n")
    return inline_images(page, base)


def main(argv=None) -> int:
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
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
