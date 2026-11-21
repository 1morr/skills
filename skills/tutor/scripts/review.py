"""把幾份導讀頁的速查卡接成一頁考前速查，每個題型下面接讀者自己的筆記；規則不過就不產出。

    python scripts/review.py <topic4-guide.html> <topic5-guide.html> … [--notes <筆記.md>] [--title <標題>] -o <review.html>

導讀頁是 build.py 組好的頁（不是原始檔），照寫的順序排。速查卡原樣搬過來：題型表、公式、判斷規則；
卡上的 §N 連回那份導讀頁（連結相對於產出的頁）。產出是離線打得開的單一檔案，樣式和導讀頁同一套。

筆記（--notes，可以不給）是 Markdown，照導讀頁和題型分節：

    ## topic5-guide.html
    ### seasonal-index
    - 錯過（11/16 練習 1）：四個比率全部平均 → 先劃掉最高最低再平均
    - 懂了：medial mean 像評審給分，去掉最高分和最低分

    ##   導讀頁的檔名（.html 結尾）。其他的 ## 標題和它底下的東西是讀者自己寫的，不讀
    ###  題型代號：那份導讀頁題型表的 data-type
    -    一條筆記，接在速查頁那個題型的下面；冒號前面的字排成粗體，「錯過」開頭的用粉紅螢光筆
         下一行沒有「- 」開頭的，接在上一條後面；筆記裡的 §N 連到那份導讀頁

沒有速查卡的導讀頁只放它的筆記；沒有題型表的導讀頁，筆記照 ### 的標題排在它的最後（### 寫「§N 標題」）。

不產出的情況：沒有任何一份導讀頁有速查卡或筆記；筆記還沒寫任何 ## 就出現題型的 ###；導讀頁的 ## 底下，「- 」前面沒有題型的 ###。
只提醒的情況（印在 stderr）：筆記寫了這次沒給的導讀頁；導讀頁有題型表、筆記的題型代號卻不在上面（筆記照樣印在那個 topic 的最後）；
導讀頁沒有速查卡也沒有筆記（這次不放）。
組好之後和導讀頁一樣量水平溢出，有就不產出。

只用標準函式庫，CI 才能直接跑測試。
"""

import argparse
import html
import os
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build  # noqa: E402  共用樣式、深淺色、量溢出

overflow = build.overflow

H1 = re.compile(r"<h1\b[^>]*>(.*?)</h1\s*>", re.I | re.S)
REF = re.compile(r'(<a\b[^>]*\bhref=")#([^"]+)(")', re.I)
ROW = re.compile(r"""<tr\b[^>]*\bdata-type\s*=\s*["']([^"']+)["'][^>]*>.*?</tr\s*>""", re.I | re.S)
ANCHOR = re.compile(r'\bid="(s\d+(?:-\d+)?)"')
BULLET = re.compile(r"^\s*[-*]\s+(.*)$")
LABEL = re.compile(r"^([^：:→]{1,24})[：:]\s*(.*)$", re.S)
MISS = "錯過"
INTRO = "每個 topic 的速查卡排在一起，題型下面是你自己的筆記。按 § 會打開導讀頁的那一段。"
OTHERS = "其他筆記"
TOGGLE = """<script>
document.addEventListener("click", (e) => {
  if (e.target.closest("[data-act='print']")) { print(); return; }
  const fig = e.target.closest("figure");
  if (fig && fig.querySelector("img.zh") && e.target.closest("img")) fig.classList.toggle("show-zh");
});
</script>
"""


class _CheatFinder(HTMLParser):
    """用 HTMLParser 擷取第一個 <div class="cheat">…</div>，自動忽略註解、<script>/<style> 與屬性內的 <div。"""

    def __init__(self, page: str):
        super().__init__(convert_charrefs=False)
        self.page = page
        self.offs = build.line_offsets(page)
        self.start = None
        self.end = None
        self.depth = 0

    def _pos(self) -> int:
        ln, col = self.getpos()
        return self.offs[ln - 1] + col

    def handle_starttag(self, tag, attrs):
        if self.end is not None:
            return
        t = tag.lower()
        if self.start is None:
            if t == "div" and "cheat" in build.classes(attrs):
                self.start = self._pos()
                self.depth = 1
        elif t == "div":
            self.depth += 1

    def handle_startendtag(self, tag, attrs):
        if self.end is not None:
            return
        if self.start is None and tag.lower() == "div" and "cheat" in build.classes(attrs):
            p = self._pos()
            self.start = p
            self.end = p + len(self.get_starttag_text())

    def handle_endtag(self, tag):
        if self.start is not None and self.end is None and tag.lower() == "div":
            self.depth -= 1
            if self.depth == 0:
                p = self._pos()
                m = re.match(r"</div\s*>", self.page[p:], re.I)
                self.end = m.end() + p if m else p


def cheat_of(page: str):
    """組好的導讀頁裡那張速查卡（整個 <div class="cheat">…</div>）；沒有回傳 None。"""
    finder = _CheatFinder(page)
    finder.feed(page)
    finder.close()
    if finder.start is None or finder.end is None:
        return None
    return page[finder.start:finder.end]


def parse_notes(text: str):
    """筆記 → ({導讀頁檔名: {題型代號: [一條筆記, …]}}, 問題)。不是導讀頁檔名的 ## 和它底下的東西不讀。"""
    notes, problems = {}, []
    guide = slug = None
    reading = False  # 在某份導讀頁的 ## 底下
    any_h2 = False  # 已經出現過 ##（不管是不是導讀頁）
    fenced = False
    for n, line in enumerate(text.split("\n"), 1):
        if line.strip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue
        if line.startswith("## "):
            name = line[3:].strip().strip("`")
            any_h2 = True
            reading = name.lower().endswith(".html")
            guide, slug = (name if reading else None), None
            if reading:
                notes.setdefault(guide, {})
            continue
        if line.startswith("# "):
            reading, guide, slug = False, None, None
            continue
        if line.startswith("### "):
            if reading:
                slug = line[4:].strip().strip("`")
                notes[guide].setdefault(slug, [])
            elif not any_h2 and build.SLUG.match(line[4:].strip().strip("`")):
                problems.append(f"筆記第 {n} 行的「{line.strip()}」前面沒有導讀頁的 ## 標題：寫成「## topic5-guide.html」，速查頁才知道接到哪一份")
            continue
        if not reading:
            continue
        b = BULLET.match(line)
        if b and slug is None:
            problems.append(f"筆記第 {n} 行的「{line.strip()[:30]}」前面沒有題型的 ### 標題：寫成「### 題型代號」（題型表的 data-type）")
        elif b:
            notes[guide][slug].append(b.group(1).strip())
        elif line.strip() and slug is not None and notes[guide][slug]:
            notes[guide][slug][-1] += " " + line.strip()
    return notes, problems


def linked(text: str, link, anchors: set) -> str:
    """跳脫過的文字，裡面的 §N 連到導讀頁（導讀頁有那一段才連）。"""
    return build.SECTION_REF.sub(
        lambda m: f'<a class="ref" href="{link}#s{m.group(1).replace(".", "-")}" target="_blank">{m.group(0)}</a>'
        if "s" + m.group(1).replace(".", "-") in anchors else m.group(0), html.escape(text, quote=False))


def note_html(note: str, link, anchors: set) -> str:
    """一條筆記：冒號前面的字粗體（「錯過」開頭的用粉紅螢光筆），§N 連到導讀頁。"""
    m = LABEL.match(note)
    if not m:
        return f"<li>{linked(note, link, anchors)}</li>"
    cls = ' class="mk mk-pink"' if m.group(1).startswith(MISS) else ""
    return f"<li><b{cls}>{linked(m.group(1), link, anchors)}</b> {linked(m.group(2), link, anchors)}</li>"


def section(page: str, name: str, link: str, n: int, notes: dict):
    """一份導讀頁的那一節：標題、速查卡、接在題型下面的筆記。回傳 (HTML, 提醒)；速查卡和筆記都沒有回傳 (None, [])。"""
    cheat = cheat_of(page) or ""
    if not cheat and not any(notes.values()):
        return None, []
    typed = bool(ROW.search(cheat))
    h1 = H1.search(page)
    title = build.plain(h1.group(1)) if h1 else name
    anchors = set(ANCHOR.findall(page))
    link = html.escape(link)
    cheat = REF.sub(lambda m: f'{m.group(1)}{link}#{m.group(2)}" target="_blank"', cheat)
    left = dict(notes)

    def with_notes(m):
        mine = left.pop(m.group(1), None)
        if not mine:
            return m.group(0)
        cols = len(re.findall(r"<t[dh]\b", m.group(0), re.I))
        items = "".join(note_html(x, link, anchors) for x in mine)
        return f'{m.group(0)}<tr class="mine"><td colspan="{cols}"><ul>{items}</ul></td></tr>'

    cheat = ROW.sub(with_notes, cheat)
    rest, loose, warns = "", "", []
    for slug, mine in left.items():
        if not mine:
            continue
        if typed:
            warns.append(f"筆記的題型 {slug!r} 不在 {name} 的題型表裡：這幾條印在那個 topic 的最後，代號寫錯就改筆記")
            rest += "".join(note_html(f"{slug}：{x}", link, anchors) for x in mine)
        else:  # 沒有題型表：筆記照它自己的 ### 標題分組
            loose += f'<h4>{linked(slug, link, anchors)}</h4><ul class="mine">{"".join(note_html(x, link, anchors) for x in mine)}</ul>'
    if rest:
        rest = f'<h4>{OTHERS}</h4><ul class="mine">{rest}</ul>'
    return (f'<section id="t{n}"><h2 class="plain">{html.escape(title)}</h2>'
            f'<p class="meta"><a href="{link}" target="_blank">打開導讀頁</a></p>{cheat}{rest}{loose}</section>\n'), warns


def assemble(guides: list, notes: dict, title: str, lang: str = "zh-Hant"):
    """guides：[(檔名, 連結, 組好的導讀頁 HTML)]。回傳 (整頁 HTML, 問題, 提醒)。"""
    problems, warns, parts, names = [], [], [], [g[0] for g in guides]
    for n, (name, link, page) in enumerate(guides, 1):
        part, w = section(page, name, link, n, notes.get(name, {}))
        if part is None:
            warns.append(f"{name} 沒有速查卡也沒有筆記：這次不放進考前速查")
        else:
            parts.append(part)
            warns += w
    if not parts:
        problems.append("沒有任何一份導讀頁有速查卡或筆記：考前速查沒有東西可放")
    for name in notes:
        if name not in names:
            warns.append(f"筆記有 {name} 的筆記，這次沒有給這份導讀頁：它的筆記沒有印出來")
    t = html.escape(title)
    page = (f'<!DOCTYPE html>\n<html lang="{html.escape(lang)}">\n<head>\n<meta charset="utf-8">\n{build.VIEWPORT}<title>{t}</title>\n'
            f"{build.THEME}<style>\n{build.CSS.read_text(encoding='utf-8')}</style>\n</head>\n"
            f'<body class="review">\n<main><div class="page">\n<h1>{t}</h1>\n<p class="lead">{INTRO}</p>\n'
            '<p class="cheat-tools"><button type="button" class="btn" data-act="print">列印</button></p>\n'
            f'{"".join(parts)}</div></main>\n{TOGGLE}</body>\n</html>\n')
    return page, problems, warns


def main(argv=None, measure=build.measure) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")  # Windows 終端機預設不是 UTF-8
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("guides", type=Path, nargs="+")
    ap.add_argument("--notes", type=Path)
    ap.add_argument("--title", default="考前速查")
    ap.add_argument("-o", "--out", type=Path, required=True)
    args = ap.parse_args(argv)
    notes, problems = {}, []
    if args.notes:
        if args.notes.is_file():
            notes, problems = parse_notes(args.notes.read_text(encoding="utf-8"))
        else:
            problems.append(f"找不到筆記 {args.notes}")
    guides = []
    for g in args.guides:
        if not g.is_file():
            problems.append(f"找不到導讀頁 {g}")
            continue
        link = Path(os.path.relpath(g.resolve(), args.out.resolve().parent)).as_posix()
        guides.append((g.name, link, g.read_text(encoding="utf-8")))
    lang = re.search(r'<html\b[^>]*\blang="([^"]+)"', guides[0][2], re.I) if guides else None
    page, more, warns = assemble(guides, notes, args.title, lang.group(1) if lang else "zh-Hant")
    problems += more
    if problems:
        print(f"{len(problems)} 個問題，沒有產出", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    for w in warns:
        print(f"提醒：{w}", file=sys.stderr)
    args.out.write_text(page, encoding="utf-8")
    if not overflow.deliverable(args.out, args.out.name, measure(args.out)):
        return 1
    print(args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
