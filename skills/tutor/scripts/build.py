"""把導讀頁的原始 HTML 組成單一檔案；會讓頁面壞掉的事不過就不產出。

    python build.py <src.html> [-o <out.html>]

原始檔是一份普通的 HTML：<h1>、<h2>、<h3> 和正文，怎麼分段、用哪些元件由作者決定。build 加上的東西：
§ 編號和連結、左邊的目錄、頁眉、名詞表（每個 <dfn>）、速查卡的標題和列印鈕、
查表面板（<aside class="panel">）、右邊的課件欄，並把圖片和樣式內嵌成離線打得開的單一檔案。

課件欄：<body data-slides="slides/slides.json">（deck.py 寫的清單，路徑相對於原始檔）。
正文裡在講某一頁課件的元素寫 data-slide="L20 p.25"（或 "L20 p.25-28"、"L20 p.29; L22 p.6"），
讀者捲到那裡，課件欄就跟到那一頁；再加 data-key 的頁是必記的：課件欄標出來，「只看重點」時那一塊留著。

不產出的情況（逐條印出原因）：
- 圖片、樣式、腳本連到網路上（頁面要能離線打開）；找不到圖片檔。
- 內文的 §N 指到不存在的段落。
- 寫了題型表 <table class="types">，某一列卻沒有不重複的 data-type：練習頁、模擬卷、考前速查、學習紀錄靠它對回題型。
  （速查卡 <div class="cheat"> 和題型表都可以不寫。）
- 查表面板的 figure 沒有 data-tab。
- data-slide 寫了清單上沒有的頁，或寫了 data-slide 卻沒有 data-slides。
- 組好之後用本機的 Chrome 或 Edge 在寬螢幕和手機寬各量一次（pages/scripts/overflow.py）：有水平溢出，
  或寬螢幕上正文裡的公式、算式、表格比正文欄寬、右邊被切掉。找不到瀏覽器只提醒。

成功時印產出的路徑、整頁大約要讀幾分鐘（給寫頁的人對照計畫的份量，頁面上不顯示），有課件欄時再印正文講到幾頁、哪幾頁沒講到。

只用標準函式庫，CI 才能直接跑測試。
"""

import argparse
import base64
import html
import json
import mimetypes
import os
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

# 共用的水平溢出量測在 plugin 根目錄的 pages/scripts/
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "pages" / "scripts"))
import overflow  # noqa: E402

CSS = Path(__file__).resolve().parents[1] / "assets" / "lesson.css"
JS = Path(__file__).resolve().parents[1] / "assets" / "lesson.js"

# 估閱讀時間：一分鐘讀幾個字（單位見 text_units）；每個算式、每個自測、每題選擇題再各加半分鐘
UNITS_PER_MIN = 200
WORK_MIN = 0.5

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "param", "source", "track", "wbr"}

CJK = re.compile(r"[㐀-鿿豈-﫿]")
WORD = re.compile(r"[A-Za-z0-9]+")
SECTION_REF = re.compile(r"§(\d+(?:\.\d+)?)")
REMOTE = re.compile(r"^\s*(https?:)?//", re.I)
# 題型代號：題型表每一列一個，練習頁和模擬卷的題目用它對回題型
SLUG = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
# data-slide 的一項：「L20 p.25」或「L20 p.25-28」
SLIDE_REF = re.compile(r"^([A-Za-z0-9][A-Za-z0-9-]*)\s+p\.\s*(\d+)(?:\s*[-–]\s*(\d+))?$")


def text_units(s: str) -> int:
    """一個中日韓字算 1，一個英文字或數字串算 1。"""
    return len(CJK.findall(s)) + len(WORD.findall(s))


def classes(attrs) -> set:
    return set((dict(attrs).get("class") or "").split())


def slide_keys(value: str) -> list:
    """data-slide 的值拆成 [(代號, 頁)]；看不懂就丟 ValueError。"""
    keys = []
    for item in filter(None, (x.strip() for x in value.split(";"))):
        m = SLIDE_REF.match(item)
        if not m:
            raise ValueError(item)
        first, last = int(m.group(2)), int(m.group(3) or m.group(2))
        if last < first:
            raise ValueError(item)
        keys += [(m.group(1), n) for n in range(first, last + 1)]
    if not keys:
        raise ValueError(value)
    return keys


def load_slides(path: Path) -> dict:
    """讀 deck.py 寫的清單：{(代號, 頁): {"src", "zh", "w", "h"}}，圖檔路徑換成絕對路徑；照課件和頁碼的順序。"""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {(d["id"], p["n"]): {"src": path.parent / p["src"], "zh": path.parent / p["zh"] if p.get("zh") else None,
                                    "w": int(p["w"]), "h": int(p["h"])}
                for d in data["decks"] for p in d["pages"]}
    except (OSError, ValueError, KeyError, TypeError) as e:
        raise SystemExit(f"讀不了課件清單 {path}（{e}）：用 deck.py 產生 slides.json")


class Lint(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.problems = []
        self.stack = []  # [(tag, classes)]
        self.h2 = 0  # 目前有幾個 h2
        self.h3 = {}  # {第幾個 h2: 底下有幾個 h3}
        self.refs = []  # 內文提到的 §N、§N.M
        self.types = None  # 題型表每一列的 data-type；None 表示沒有這張表
        self.row = None  # 正在讀的題型表列：{"slug", "cells", "text"}
        self.slides = []  # 每個 data-slide 的值
        self.deck = None  # <body data-slides>

    def inside_class(self, name) -> bool:
        return any(name in c for _, c in self.stack)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = classes(attrs)
        if tag == "body":
            self.deck = (a.get("data-slides") or "").strip() or None
        for key in ("src", "href", "data-zh"):
            if tag in ("img", "script", "link", "source") and a.get(key) and REMOTE.match(a[key]):
                self.problems.append(f"外部資源 <{tag} {key}={a[key]!r}>：頁面要能離線打開，請改成本機檔案")
        if tag == "h2":
            self.h2 += 1
        if tag == "h3":
            self.h3[self.h2] = self.h3.get(self.h2, 0) + 1
        if tag == "table" and "types" in cls and self.types is None:
            self.types = []
        if tag == "tr" and self.types is not None and self.inside_class("types"):
            self.row = {"slug": (a.get("data-type") or "").strip(), "cells": 0, "text": ""}
        if tag == "td" and self.row is not None:
            self.row["cells"] += 1
        if tag == "figure" and self.inside_class("panel") and not (a.get("data-tab") or "").strip():
            self.problems.append("查表面板的 figure 沒有 data-tab：寫分頁名稱，例如「Z 表」")
        if "data-slide" in a:
            self.slides.append(a["data-slide"] or "")
        if tag not in VOID:
            self.stack.append((tag, cls))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        # 容許省略結束標籤：往回找到同名的那層再收
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break
        else:
            return
        if tag == "tr" and self.row is not None:
            if self.row["cells"]:  # 沒有 <td> 的是表頭
                slug, what = self.row["slug"], " ".join(self.row["text"].split())[:20]
                if not SLUG.match(slug):
                    self.problems.append(f'題型表的「{what}」沒有 data-type：每一列寫一個英文小寫代號（例如 acf-read），'
                                         "練習頁的題目用它對回這個題型")
                elif slug in self.types:
                    self.problems.append(f"題型表的 data-type={slug!r} 重複了：每個題型一個代號")
                self.types.append(slug)
            self.row = None

    def handle_data(self, data):
        if self.row is not None:
            self.row["text"] += data
        if not any(t in ("script", "style") for t, _ in self.stack):
            self.refs += SECTION_REF.findall(data)


def lint(src: str, slides=None) -> list:
    """會讓頁面或下游的頁壞掉的事。slides 是 load_slides() 的結果；頁面沒有課件欄時是 None。"""
    p = Lint()
    p.feed(src)
    p.close()
    problems = list(p.problems)
    if p.types is not None and not p.types:
        problems.append('題型表沒有任何一列：每個題型寫一列 <tr data-type="英文小寫代號">')
    labels = {f"{i}" for i in range(1, p.h2 + 1)} | {f"{i}.{j}" for i, n in p.h3.items() for j in range(1, n + 1)}
    for ref in sorted(set(p.refs) - labels):
        problems.append(f"內文提到 §{ref}，但頁面沒有這一段：§ 編號由 build 依 h2、h3 的順序產生")
    if p.slides and slides is None:
        problems.append('正文寫了 data-slide，<body> 卻沒有 data-slides：寫上 deck.py 產生的 slides.json 的路徑')
    for value in p.slides if slides is not None else ():
        try:
            missing = [k for k in slide_keys(value) if k not in slides]
        except ValueError as e:
            problems.append(f'data-slide="{value}" 的「{e}」看不懂：寫成「代號 p.3」或「代號 p.3-5」，多份用 ; 分開')
            continue
        if missing:
            problems.append(f'data-slide="{value}"：課件清單沒有 {missing[0][0]} p.{missing[0][1]}'
                            "（代號是 deck.py 的 <代號>=<pdf>，頁碼從 1 起算）")
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
ICONS = {"check": '<path d="M3 8.5l3.2 3.2L13 4.5"/>', "x": '<path d="M4 4l8 8M12 4l-8 8"/>',
         "list": '<path d="M2.5 4h11M2.5 8h11M2.5 12h7"/>'}


def icon(name: str) -> str:
    return f'<svg class="i" viewBox="0 0 16 16" aria-hidden="true">{ICONS[name]}</svg>'


def plain(html: str) -> str:
    return " ".join(TAG.sub("", html).split())


def has_class(name: str) -> str:
    """比對 class 屬性裡有 name 這個字的樣式片段。"""
    return rf"""[^>]*\bclass\s*=\s*["'](?:[^"']*\s)?{name}(?:\s[^"']*)?["'][^>]*"""


# 目錄上不重複標題尾巴的頁碼：「……（講義 p.3）」
PAGE_TAIL = re.compile(r"\s*[（(][^（）()]*\bp{1,2}\.\s*\d[^（）()]*[）)]\s*$")
WORK = re.compile(rf"<(?:div|details)\b(?:{has_class('calc')}|{has_class('check')}|{has_class('quiz')})>", re.I)


def minutes(body: str) -> int:
    """這一段大約要讀幾分鐘：字數，加上每個算式、自測、選擇題要自己動手的時間。"""
    return max(1, round(text_units(TAG.sub("", body)) / UNITS_PER_MIN + len(WORK.findall(body)) * WORK_MIN))


def add_meta(src: str) -> str:
    """每個編號的 h2 寫上 data-n 和目錄用的短標題。"""
    def repl(m):
        attrs, title = m.group(1), PAGE_TAIL.sub("", plain(m.group(3)))
        if "data-short" not in attrs:  # 目錄和頁眉用的短標題：去掉尾巴的頁碼
            attrs += f' data-short="{title}"'
        return f'<h2{attrs} data-n="{m.group(2)}"><span class="num">§{m.group(2)}</span> {m.group(3)}</h2>'

    return NUMBERED_H2.sub(repl, src)


def total_minutes(src: str) -> int:
    """原始檔整頁大約要讀幾分鐘：每個 h2 段落各自估，再加起來。"""
    numbered, _ = number_headings(src)
    heads = list(NUMBERED_H2.finditer(numbered))
    return sum(minutes(numbered[m.end():heads[i + 1].start() if i + 1 < len(heads) else len(numbered)])
               for i, m in enumerate(heads))


def body_end(src: str) -> int:
    end = src.lower().rfind("</body>")
    return len(src) if end < 0 else end


def add_cheat(src: str) -> str:
    """速查卡前面加一個不編號的標題（目錄和頁眉的「速查卡」連到它），和列印、展開全部做法的按鈕。"""
    m = re.search(rf"<div\b{has_class('cheat')}>", src, re.I)
    if not m:
        return src
    answers = ('<button type="button" class="btn" data-act="answers">展開全部做法</button>'
               if re.search(rf"<details\b{has_class('answer')}>", src, re.I) else "")
    head = ('<h2 class="plain" id="cheat">速查卡</h2><p class="cheat-tools">'
            f'<button type="button" class="btn" data-act="print">列印速查卡</button>{answers}</p>')
    return src[:m.start()] + head + src[m.start():]


DFN = re.compile(r"<dfn\b[^>]*>(.*?)</dfn\s*>", re.I | re.S)
# <dfn> 裡寫成「譯名（原文）」：名詞表照原文排，譯名放旁邊
DFN_PAIR = re.compile(r"^(.*?)\s*[（(]([^（）()]+)[）)]\s*$", re.S)
HEAD_TAG = re.compile(r"<h[23]\b[^>]*>", re.I)


def add_terms(src: str, anchors: dict) -> str:
    """正文最後加一張名詞表：每個 <dfn> 一列，照原文排；<dfn>譯名（原文）</dfn> 的譯名放在旁邊。連到它所在的那一段。"""
    label_of = {anchor: label for label, anchor in anchors.items()}
    heads = [(m.start(), ID_ATTR.search(m.group(0))) for m in HEAD_TAG.finditer(src)]
    heads = [(pos, m.group(1)) for pos, m in heads if m and m.group(1) in label_of]
    rows = []
    for m in DFN.finditer(src):
        before = [anchor for pos, anchor in heads if pos < m.start()]
        if before:
            pair = DFN_PAIR.match(m.group(1))
            term, alt = (pair.group(2), pair.group(1)) if pair else (m.group(1), "")
            rows.append((plain(term), term.strip(), plain(alt), before[-1]))
    if not rows:
        return src
    rows.sort(key=lambda r: r[0].lower())
    items = "".join(f'<li><a class="ref" href="#{anchor}">{term}</a><span>{alt}</span>'
                    f'<span class="where">§{label_of[anchor]}</span></li>' for _, term, alt, anchor in rows)
    table = ('<h2 class="plain" id="terms">名詞表</h2><p class="meta">這一頁定義過的名詞，照原文排。按名詞在旁邊打開定義。</p>'
             f'<ul class="terms">{items}</ul>')
    end = body_end(src)
    return src[:end] + table + src[end:]


OPEN_TAG = re.compile(r"<([a-zA-Z][\w-]*)\b([^<>]*)>")
SLIDE_ATTR = re.compile(r"""\sdata-slide\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.I)
KEY_ATTR = re.compile(r"\sdata-key\b", re.I)
# 圖說上最多列幾個講到這一頁的段落
MAX_USES = 4


def slide_id(key) -> str:
    return f"slide-{key[0]}-{key[1]}"


def add_deck(src: str, slides: dict, anchors: dict, base: Path) -> tuple:
    """課件欄：清單上的每一頁一張圖，照課件順序；圖說連到講到它的段落。正文裡的 data-slide 換成 data-at（那幾張圖的 id）。
    回傳 (新的 HTML, {"pages": 總頁數, "used": 講到幾頁, "key": 必記幾頁, "idle": 沒講到的 [(代號, 頁)]})。"""
    label_of = {anchor: label for label, anchor in anchors.items()}
    uses, keyed, current = {}, set(), [None]

    def repl(m):
        tag, attrs = m.group(1).lower(), m.group(2)
        if tag in ("h2", "h3"):
            own = ID_ATTR.search(attrs)
            if own and own.group(1) in label_of:
                current[0] = own.group(1)
        hit = SLIDE_ATTR.search(attrs)
        if not hit:
            return m.group(0)
        try:
            keys = slide_keys(hit.group(1) if hit.group(1) is not None else hit.group(2))
        except ValueError:  # 註解裡的範例：lint 沒看到它，原樣留著
            return m.group(0)
        for k in keys:
            if current[0] and current[0] not in uses.setdefault(k, []):
                uses[k].append(current[0])
            uses.setdefault(k, [])
        if KEY_ATTR.search(attrs):
            keyed.update(keys)
        at = " ".join(slide_id(k) for k in keys)
        rest = SLIDE_ATTR.sub("", attrs, count=1).rstrip()
        close = " /" if rest.endswith("/") else ""
        return f'<{m.group(1)}{rest.rstrip("/").rstrip()} data-at="{at}"{close}>'

    src = OPEN_TAG.sub(repl, src)
    figs, deck = [], None
    for key, page in slides.items():
        if key[0] != deck:
            deck = key[0]
            figs.append(f'<h3 class="deck-name">{html.escape(deck)}</h3>')
        rel = [Path(os.path.relpath(f, base)).as_posix() if f else None for f in (page["src"], page["zh"])]
        zh = f' data-zh="{html.escape(rel[1])}"' if rel[1] else ""
        to = "".join(f'<a class="to" href="#{a}">§{label_of[a]}</a>' for a in uses.get(key, [])[:MAX_USES])
        cls = ' class="key"' if key in keyed else ""
        figs.append(f'<figure id="{slide_id(key)}"{cls}>'
                    # 寫上大小：圖還沒載入時先佔好位置，課件欄才捲得到對的地方
                    f'<img src="{html.escape(rel[0])}"{zh} width="{page["w"]}" height="{page["h"]}" alt="" loading="lazy">'
                    f'<figcaption><b>{html.escape(key[0])} p.{key[1]}</b>{to}</figcaption></figure>')
    aside = ('<aside class="deck" aria-label="課件"><div class="deck-head"><b>課件</b>'
             '<button type="button" class="btn" data-act="follow" aria-pressed="true">跟著正文</button>'
             f'<button type="button" class="close" data-act="deck-close" aria-label="收起課件">{icon("x")}</button></div>'
             f'<div class="deck-body">{"".join(figs)}</div></aside>')
    end = body_end(src)
    report = {"pages": len(slides), "used": len(uses), "key": len(keyed), "idle": [k for k in slides if k not in uses]}
    return src[:end] + aside + src[end:], report


def idle_text(idle: list) -> str:
    """沒講到的頁寫成「L20 p.1、4–6；L21 p.2」。"""
    by_deck = {}
    for deck, n in idle:
        by_deck.setdefault(deck, []).append(n)
    parts = []
    for deck, pages in by_deck.items():
        runs, start = [], pages[0]
        for a, b in zip(pages, pages[1:] + [None]):
            if b != a + 1:
                runs.append(f"{start}" if start == a else f"{start}–{a}")
                start = b
        parts.append(f"{deck} p.{'、'.join(runs)}")
    return "；".join(parts)


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


DECK = re.compile(rf"<aside\b{has_class('deck')}>.*?</aside\s*>", re.I | re.S)
BODY_TAG = re.compile(r"<body\b([^>]*)>", re.I)


def add_shell(src: str) -> str:
    """把正文包進版面：目錄、頁眉（現在讀到哪、速查卡、名詞表、查表、課件、只看重點）、正文、課件欄、對照欄。"""
    if not re.search(r"<h1\b[^>]*\bid\s*=", src, re.I):
        src = re.sub(r"<h1\b", '<h1 id="top"', src, count=1, flags=re.I)
    src = re.sub(r"</h1\s*>", lambda m: m.group(0)
                 + '<p class="digest-note">現在只顯示標題、重點框、定義、表格、常見錯誤和必記的課件頁那幾段。<button type="button" class="btn" data-act="digest-off">看全文</button></p>'
                 + '<p class="resume" hidden>上次讀到這裡：<a href="#"></a></p>', src, count=1, flags=re.I)
    deck = DECK.search(src)
    if deck:
        src = src[:deck.start()] + src[deck.end():]
        src = BODY_TAG.sub(lambda m: (CLASS_ATTR.sub(lambda c: c.group(1) + "has-deck ", m.group(0), count=1)
                                     if CLASS_ATTR.search(m.group(1)) else f'<body class="has-deck"{m.group(1)}>'), src, count=1)
    tools = "".join(f'<button type="button" class="tool wide" data-act="{act}">{label}</button>'
                    for act, label in (("cheat", "速查卡"), ("terms", "名詞表"), ("panel", "查表")) if f'id="{act}"' in src)
    if deck:
        tools += '<button type="button" class="tool narrow" data-act="deck" aria-pressed="false">課件</button>'
    head = (f'<div class="head"><button type="button" class="tool" data-act="nav">{icon("list")}目錄</button>'
            f'<p class="crumb"></p><p class="count"></p>{tools}'
            '<button type="button" class="tool" data-act="digest-toggle" aria-pressed="false">只看重點</button>'
            '<span class="bar" aria-hidden="true"></span></div>')
    peek = ('<button type="button" class="scrim" data-act="scrim" aria-label="關閉"></button>'
            '<aside class="peek" aria-label="旁邊打開的那一段"><div class="peek-head"><h2></h2><p></p>'
            f'<button type="button" class="close" data-act="peek-close" aria-label="關閉">{icon("x")}</button>'
            '<div class="peek-acts"><button type="button" class="btn back" data-act="peek-back" hidden>返回</button>'
            '<a class="go" href="#">跳到這一段</a></div></div><div class="peek-body"></div></aside>')
    opening = BODY_TAG.search(src)
    start = opening.end() if opening else 0
    end = body_end(src)
    return (src[:start] + rail(src + (deck.group(0) if deck else ""), outline(src)) + "<main>" + head + '<div class="page">'
            + src[start:end] + "</div></main>" + (deck.group(0) if deck else "") + peek + src[end:])


def build(src: str, base: Path, slides=None) -> tuple:
    """回傳 (組好的頁, 課件欄的統計或 None)。"""
    src, anchors = number_headings(src)
    src = add_meta(link_refs(add_panel(src), anchors))
    src = add_terms(add_cheat(src), anchors)
    report = None
    if slides is not None:
        src, report = add_deck(src, slides, anchors, base)
    return inject_assets(inline_images(split_bilingual(add_shell(src)), base)), report


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


BODY_SLIDES = re.compile(r"""<body\b[^>]*\sdata-slides\s*=\s*["']([^"']+)["']""", re.I)


def main(argv=None, measure=measure) -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")  # Windows 終端機預設不是 UTF-8
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("src", type=Path)
    ap.add_argument("-o", "--out", type=Path)
    args = ap.parse_args(argv)
    src = args.src.read_text(encoding="utf-8")
    declared = BODY_SLIDES.search(src)
    slides = load_slides(args.src.parent / declared.group(1).strip()) if declared else None
    problems = lint(src, slides)
    if problems:
        print(f"{args.src}：{len(problems)} 個問題，沒有產出", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    out = args.out or args.src.with_name(args.src.stem.removesuffix("-src") + ".html")
    page, report = build(src, args.src.parent, slides)
    out.write_text(page, encoding="utf-8")
    if not overflow.deliverable(out, args.src, measure(out)):
        return 1
    print(out)
    print(f"讀完大約 {total_minutes(src)} 分鐘")
    if report:
        idle = f"；沒講到：{idle_text(report['idle'])}" if report["idle"] else ""
        print(f"課件欄 {report['pages']} 頁：正文講到 {report['used']} 頁，必記 {report['key']} 頁{idle}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
