"""把同一份產出的兩個版本做成一頁 HTML 對照：整份逐段、逐字標出改動。

用法：
  uv run --no-project --with python-docx --with pymupdf python diff_html.py <前版> <後版> -o <輸出.html>
      [--notes notes.json] [--title 標題] [--before-label 起點] [--after-label 最終版]
  ... diff_html.py <前版> <後版> --words     只印兩版的字數（英文以詞計、中文以字計）和段數

支援 .docx（段落與表格照文件順序；表格逐格比對）、.pdf（文字區塊）、.html/.htm（看得到的文字，依區塊元素分段）、
其他副檔名當純文字（空行分段）。只用到的格式才需要對應套件：docx 要 python-docx，pdf 要 pymupdf。

notes.json（全部欄位都可省略）：
  {"intro": "頁首說明",
   "notes": [{"match": "前版或後版段落裡的一段原文", "note": "為什麼改", "tag": "必須修"}],
   "other": ["不在文字裡的改動，例如封面換了校徽"],
   "removed_midway": ["中途加過、最後又刪掉的內容"],
   "images": [{"caption": "第 1 頁", "before": "a.png", "after": "b.png"}]}
每條 note 掛到「前版或後版文字含 match」的改動段落上；一條都沒掛上的印到 stderr（UNMATCHED NOTE），
多半是 match 抄錯或那段其實沒改。
"""
import argparse
import base64
import difflib
import html
import json
import os
import re
import sys
from html.parser import HTMLParser


# ---------- 抽文字：每個格式都回傳 [("p", 文字) | ("table", [[格, ...], ...])]

def extract(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".docx":
        return extract_docx(path)
    if ext == ".pdf":
        return extract_pdf(path)
    if ext in (".html", ".htm"):
        with open(path, encoding="utf-8", errors="replace") as f:
            return extract_html(f.read())
    with open(path, encoding="utf-8", errors="replace") as f:
        return extract_text(f.read())


def norm(s):
    return re.sub(r"\s+", " ", s).strip()


def extract_text(text):
    return [("p", norm(b)) for b in re.split(r"\n\s*\n", text) if norm(b)]


def extract_docx(path):
    import docx  # python-docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    d = docx.Document(path)
    out = []
    for el in d.element.body.iterchildren():
        tag = el.tag.rsplit("}", 1)[-1]
        if tag == "p":
            t = norm(Paragraph(el, d).text)
            if t:
                out.append(("p", t))
        elif tag == "tbl":
            rows = [[norm(c.text) for c in r.cells] for r in Table(el, d).rows]
            out.append(("table", rows))
    return out


def extract_pdf(path):
    import pymupdf

    out = []
    with pymupdf.open(path) as doc:
        for page in doc:
            for b in page.get_text("blocks"):
                t = norm(b[4])
                if t:
                    out.append(("p", t))
    return out


BLOCK = {"p", "div", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "td", "th", "br", "section",
         "article", "header", "footer", "figcaption", "figure", "blockquote", "pre", "table", "dt", "dd", "text"}
SKIP = {"script", "style", "head", "template", "noscript"}


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks, self.cur, self.skip = [], [], 0

    def flush(self):
        t = norm("".join(self.cur))
        if t:
            self.blocks.append(("p", t))
        self.cur = []

    def handle_starttag(self, tag, attrs):
        if tag in SKIP:
            self.skip += 1
        elif tag in BLOCK:
            self.flush()

    def handle_endtag(self, tag):
        if tag in SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag in BLOCK:
            self.flush()

    def handle_data(self, data):
        if not self.skip:
            self.cur.append(data)


def extract_html(src):
    p = _Text()
    p.feed(src)
    p.close()
    p.flush()
    return p.blocks


# ---------- 比對

TOKEN = re.compile(r"\s+|\w+|[^\w\s]", re.U)


def word_diff(a, b):
    """回傳 (前版 html, 後版 html, 合併 html)：刪掉的字包 <del>、加上的字包 <ins>。"""
    ta, tb = TOKEN.findall(a), TOKEN.findall(b)
    sm = difflib.SequenceMatcher(None, ta, tb, autojunk=False)
    left, right, merged = [], [], []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        x, y = html.escape("".join(ta[i1:i2])), html.escape("".join(tb[j1:j2]))
        if op == "equal":
            left.append(x); right.append(y); merged.append(y)
            continue
        if x:
            left.append(f"<del>{x}</del>"); merged.append(f"<del>{x}</del>")
        if y:
            right.append(f"<ins>{y}</ins>"); merged.append(f"<ins>{y}</ins>")
    return "".join(left), "".join(right), "".join(merged)


def key(block):
    kind, v = block
    return v if kind == "p" else "\x00table\x00" + "\x01".join("\x02".join(r) for r in v)


def align(a, b):
    """逐段對齊。回傳 [(狀態, 前版 block 或 None, 後版 block 或 None)]，狀態是 same / changed / removed / added。"""
    sm = difflib.SequenceMatcher(None, [key(x) for x in a], [key(x) for x in b], autojunk=False)
    rows = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            rows += [("same", a[i], b[j]) for i, j in zip(range(i1, i2), range(j1, j2))]
        elif op == "delete":
            rows += [("removed", a[i], None) for i in range(i1, i2)]
        elif op == "insert":
            rows += [("added", None, b[j]) for j in range(j1, j2)]
        else:
            rows += pair(a[i1:i2], b[j1:j2])
    return rows


def similar(x, y):
    if x[0] != y[0]:
        return False
    if x[0] == "table":
        return True
    return difflib.SequenceMatcher(None, x[1], y[1], autojunk=False).ratio() >= 0.4


def pair(xs, ys):
    """一段換成另一段時，照順序把相像的配成「改了」，配不上的算刪掉或新加。"""
    rows, j = [], 0
    for x in xs:
        k = next((k for k in range(j, len(ys)) if similar(x, ys[k])), None)
        if k is None:
            rows.append(("removed", x, None))
            continue
        rows += [("added", None, y) for y in ys[j:k]]
        rows.append(("changed", x, ys[k]))
        j = k + 1
    rows += [("added", None, y) for y in ys[j:]]
    return rows


def columns(before, after):
    """欄位對應：欄數一樣就照位置；不一樣就用第一列（表頭）對齊，插入或刪掉的欄另外標出。
    回傳 [(前版欄號或 None, 後版欄號或 None)]。"""
    nb = max((len(r) for r in before), default=0)
    na = max((len(r) for r in after), default=0)
    if nb == na or not before or not after:
        return [(c if c < nb else None, c if c < na else None) for c in range(max(nb, na))]
    hb, ha = before[0] + [""] * (nb - len(before[0])), after[0] + [""] * (na - len(after[0]))
    cols = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, hb, ha, autojunk=False).get_opcodes():
        if op == "equal":
            cols += list(zip(range(i1, i2), range(j1, j2)))
        else:
            k = min(i2 - i1, j2 - j1)
            cols += list(zip(range(i1, i1 + k), range(j1, j1 + k)))
            cols += [(i, None) for i in range(i1 + k, i2)] + [(None, j) for j in range(j1 + k, j2)]
    return cols


def cell(row, c):
    return row[c] if row is not None and c is not None and c < len(row) else None


def table_html(before, after):
    """表格逐格比：改過的格子標出前後值；多出或少掉的列、欄整列整欄標示。"""
    cols = columns(before, after)
    out = ["<table class='grid'>"]
    for r in range(max(len(before), len(after))):
        rb = before[r] if r < len(before) else None
        ra = after[r] if r < len(after) else None
        cls = " class='added'" if rb is None else " class='removed'" if ra is None else ""
        out.append(f"<tr{cls}>")
        for cb, ca in cols:
            vb, va = cell(rb, cb), cell(ra, ca)
            col_cls = " col-added" if cb is None else " col-removed" if ca is None else ""
            if vb == va:
                out.append(f"<td class='{col_cls.strip()}'>{html.escape(va or '')}</td>")
            else:
                _, _, m = word_diff(vb or "", va or "")
                out.append(f"<td class='cell-changed{col_cls}'>{m}</td>")
        out.append("</tr>")
    out.append("</table>")
    return "".join(out)


def table_changed_cells(before, after):
    """改過的格數，不含整欄新增或刪掉的欄（那些在畫面上整欄標示）。"""
    cols = [(cb, ca) for cb, ca in columns(before, after) if cb is not None and ca is not None]
    n = 0
    for r in range(max(len(before), len(after))):
        rb = before[r] if r < len(before) else None
        ra = after[r] if r < len(after) else None
        n += sum(1 for cb, ca in cols if cell(rb, cb) != cell(ra, ca))
    return n


def block_text(b):
    if b is None:
        return ""
    return b[1] if b[0] == "p" else " ".join(" ".join(r) for r in b[1])


# ---------- 輸出

CSS = """
body{font:15px/1.6 system-ui,'Segoe UI','Microsoft JhengHei',sans-serif;margin:0;color:#1d1d1f;background:#fafafa}
header{position:sticky;top:0;background:#fff;border-bottom:1px solid #ddd;padding:12px 24px;z-index:1}
h1{font-size:18px;margin:0 0 6px}
.stats{color:#555;font-size:13px}
.controls label{margin-right:16px;font-size:14px;cursor:pointer}
main{padding:16px 24px;max-width:1500px;margin:auto}
section.meta{background:#fff;border:1px solid #ddd;padding:12px 16px;margin-bottom:16px}
section.meta h2{font-size:15px;margin:0 0 6px}
.row{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:6px 8px;border-bottom:1px solid #eee;background:#fff}
.row .inline{display:none;grid-column:1/3}
body.inline .row .left,body.inline .row .right{display:none}
body.inline .row .inline{display:block}
.row.changed,.row.added,.row.removed{background:#fffbea}
body.only-changes .row.same{display:none}
.note{grid-column:1/3;font-size:13px;color:#333;background:#eef3ff;padding:4px 8px;border-radius:4px}
body.hide-notes .note{display:none}
.tag{font-weight:600;margin-right:6px}
del{background:#ffd7d5;text-decoration:line-through}
ins{background:#ccf2d1;text-decoration:none}
.empty{color:#aaa;font-style:italic}
table.grid{border-collapse:collapse;font-size:13px;margin:4px 0}
table.grid td{border:1px solid #ccc;padding:2px 6px}
td.cell-changed{background:#fff2b3}
tr.added td,td.col-added{background:#ccf2d1}
tr.removed td,td.col-removed{background:#ffd7d5}
.images figure{margin:12px 0}
.images .pair{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.images img{width:100%;border:1px solid #ccc}
.warn{color:#b00020}
"""

JS = """
for (const [id, cls] of [['mode','inline'],['only','only-changes'],['notes','hide-notes']]) {
  const el = document.getElementById(id);
  el.addEventListener('change', () => document.body.classList.toggle(cls, el.checked));
}
"""


def render_block(b, side):
    if b is None:
        return "<span class='empty'>（無）</span>"
    if b[0] == "table":
        return table_html(b[1], b[1])
    return html.escape(b[1])


def embed(path):
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    mime = "jpeg" if ext in ("jpg", "jpeg") else ext or "png"
    with open(path, "rb") as f:
        return f"data:image/{mime};base64," + base64.b64encode(f.read()).decode()


def build(before_blocks, after_blocks, notes=None, title="修改對照", before_label="前版", after_label="後版"):
    """回傳 (html, 沒掛上的 notes)。"""
    notes = notes or {}
    items = notes.get("notes", [])
    used = [False] * len(items)
    rows = align(before_blocks, after_blocks)
    body, n_changed, n_cells = [], 0, 0
    for status, a, b in rows:
        if status == "same":
            content = render_block(b, "right")
            body.append(f"<div class='row same'><div class='left'>{content}</div><div class='right'>{content}</div>"
                        f"<div class='inline'>{content}</div></div>")
            continue
        n_changed += 1
        if a is not None and b is not None and a[0] == "table":
            n_cells += table_changed_cells(a[1], b[1])
            grid = table_html(a[1], b[1])
            left, right, merged = table_html(a[1], a[1]), grid, grid
        elif a is not None and b is not None:
            left, right, merged = word_diff(a[1], b[1])
        elif a is not None:
            left = f"<del>{render_block(a, 'left')}</del>"
            right, merged = "<span class='empty'>（刪除）</span>", left
        else:
            left = "<span class='empty'>（新增）</span>"
            right = merged = f"<ins>{render_block(b, 'right')}</ins>"
        texts = block_text(a) + "\n" + block_text(b)
        nh = []
        for i, it in enumerate(items):
            if it.get("match") and it["match"] in texts:
                used[i] = True
                tag = f"<span class='tag'>{html.escape(it['tag'])}</span>" if it.get("tag") else ""
                nh.append(f"<div class='note'>{tag}{html.escape(it.get('note', ''))}</div>")
        body.append(f"<div class='row {status}'><div class='left'>{left}</div><div class='right'>{right}</div>"
                    f"<div class='inline'>{merged}</div>{''.join(nh)}</div>")

    unmatched = [it for i, it in enumerate(items) if not used[i]]
    meta = []
    if notes.get("intro"):
        meta.append(f"<section class='meta'><h2>說明</h2><p>{html.escape(notes['intro'])}</p></section>")
    for k, h in (("other", "不在文字裡的改動"), ("removed_midway", "中途加過、最後又刪掉的內容")):
        if notes.get(k):
            lis = "".join(f"<li>{html.escape(x)}</li>" for x in notes[k])
            meta.append(f"<section class='meta'><h2>{h}</h2><ul>{lis}</ul></section>")
    if unmatched:
        lis = "".join(f"<li>{html.escape(it.get('match', ''))}：{html.escape(it.get('note', ''))}</li>" for it in unmatched)
        meta.append(f"<section class='meta warn'><h2>沒對上段落的說明</h2><ul>{lis}</ul></section>")
    imgs = notes.get("images") or []
    if imgs:
        figs = "".join(
            f"<figure><figcaption>{html.escape(im.get('caption', ''))}</figcaption><div class='pair'>"
            f"<img src='{embed(im['before'])}' alt='{html.escape(before_label)}'>"
            f"<img src='{embed(im['after'])}' alt='{html.escape(after_label)}'></div></figure>" for im in imgs)
        meta.append(f"<section class='meta images'><h2>渲染對照（左：{html.escape(before_label)}，右：{html.escape(after_label)}）</h2>{figs}</section>")

    stats = f"改動 {n_changed} 處" + (f"，表格改了 {n_cells} 格" if n_cells else "") + f"；左：{html.escape(before_label)}，右：{html.escape(after_label)}"
    page = f"""<!DOCTYPE html>
<html lang="zh-Hant"><head><meta charset="utf-8"><title>{html.escape(title)}</title><style>{CSS}</style></head>
<body><header><h1>{html.escape(title)}</h1><div class="stats">{stats}</div>
<div class="controls"><label><input type="checkbox" id="mode">合併顯示</label>
<label><input type="checkbox" id="only">只看改動</label><label><input type="checkbox" id="notes">隱藏說明</label></div></header>
<main>{''.join(meta)}{''.join(body)}</main><script>{JS}</script></body></html>"""
    return page, unmatched


WORD = re.compile(r"[㐀-鿿豈-﫿]|[^\W㐀-鿿豈-﫿]+", re.U)


def words(blocks):
    """字數：英文以詞計，中日文以字計；表格的格子也算。"""
    return sum(len(WORD.findall(block_text(b))) for b in blocks)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("before")
    ap.add_argument("after")
    ap.add_argument("-o", "--out")
    ap.add_argument("--words", action="store_true", help="只印兩版的字數和段數，不產生 HTML")
    ap.add_argument("--notes")
    ap.add_argument("--title", default="修改對照")
    ap.add_argument("--before-label", default="前版")
    ap.add_argument("--after-label", default="後版")
    a = ap.parse_args(argv)
    if a.words:
        for label, path in (("before", a.before), ("after", a.after)):
            bl = extract(path)
            print(f"{label} words={words(bl)} blocks={len(bl)}")
        return
    if not a.out:
        ap.error("-o/--out is required unless --words")
    notes = {}
    if a.notes:
        with open(a.notes, encoding="utf-8") as f:
            notes = json.load(f)
    page, unmatched = build(extract(a.before), extract(a.after), notes, a.title, a.before_label, a.after_label)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(page)
    for it in unmatched:
        print(f"UNMATCHED NOTE: {it.get('match')}", file=sys.stderr)
    print(a.out)


if __name__ == "__main__":
    main()
