"""比對同一份文件的兩個版本，輸出逐段、逐字的改動資料（JSON）。頁面由呼叫的人自己寫，見 DOCUMENT.md。

用法：
  python diff.py <前版> <後版> [-o diff.json] [--notes notes.json] [--before-label 起點] [--after-label 最終版]
  python diff.py <前版> <後版> --words      只印兩版的字數（英文以詞計、中文以字計）和段數

docx 要 python-docx、pdf 要 pymupdf（用 uv：uv run --no-project --with python-docx --with pymupdf python diff.py …）；
html、htm 和其他副檔名（當純文字，空行分段）不用套件。圖片裡的字讀不到。

輸出：
  {"before": {"label", "path", "words", "blocks"}, "after": {…},
   "counts": {"groups", "changed", "added", "removed", "table_cells"},
   "blocks": [
     {"status": "same", "kind": "p", "text": "…"} | {"status": "same", "kind": "table", "rows": [["格", …], …]},
     {"status": "changed", "kind": "p", "before": "…", "after": "…", "ops": [["=", "沒變的字"], ["-", "刪掉的"], ["+", "加上的"]]},
     {"status": "changed", "kind": "table", "changed_cells": 1, "columns": [[0, 0], [null, 1]],
      "rows": [{"status": "same|changed|added|removed", "cells": [{"text": "沒變"} | {"before", "after", "ops"}]}]},
     {"status": "removed", "kind": "p|table", "before": 文字或列} | {"status": "added", "kind": …, "after": …}
   ],
   "unmatched_notes": [...]}
  columns 每項是 [前版欄號, 後版欄號]，null 代表那一欄是新加或刪掉的。
  計數的單位是區塊：docx 一段或一張表、pdf 一個文字區塊（大約一行）、html 一個區塊元素。groups 是連續改動的
  區塊合成的「處」，給讀者看的改動數用它；changed / added / removed 是區塊數。
  表格只有 docx 會逐格比；pdf 與 html 的表格會拆成一格或一列一個區塊。
  有 --notes 時，對上的說明放在該段的 "notes": [{"note", "tag"}]。

notes.json：[{"match": "前版或後版該段裡的一段原文", "note": "為什麼改", "tag": "選填，例如 必須修"}]
  只掛在有改動的段落；一條都沒掛上的印到 stderr（UNMATCHED NOTE），多半是 match 抄錯或那段其實沒改。
"""
import argparse
import difflib
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


def word_ops(a, b):
    """逐字比對，回傳 [["=" | "-" | "+", 文字], ...]；相鄰同類的合併。"""
    ta, tb = TOKEN.findall(a), TOKEN.findall(b)
    ops = []

    def push(op, s):
        if not s:
            return
        if ops and ops[-1][0] == op:
            ops[-1][1] += s
        else:
            ops.append([op, s])

    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, ta, tb, autojunk=False).get_opcodes():
        if op == "equal":
            push("=", "".join(tb[j1:j2]))
        else:
            push("-", "".join(ta[i1:i2]))
            push("+", "".join(tb[j1:j2]))
    return ops


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


def table_diff(before, after):
    """表格逐格比。changed_cells 不含整欄新加或刪掉的欄（那些靠 columns 標示）。"""
    cols = columns(before, after)
    rows, n = [], 0
    for r in range(max(len(before), len(after))):
        rb = before[r] if r < len(before) else None
        ra = after[r] if r < len(after) else None
        cells, row_changed = [], False
        for cb, ca in cols:
            vb, va = cell(rb, cb), cell(ra, ca)
            if vb == va:
                cells.append({"text": va or ""})
                continue
            cells.append({"before": vb or "", "after": va or "", "ops": word_ops(vb or "", va or "")})
            row_changed = True
            if rb is not None and ra is not None and cb is not None and ca is not None:
                n += 1
        status = "added" if rb is None else "removed" if ra is None else "changed" if row_changed else "same"
        rows.append({"status": status, "cells": cells})
    return {"columns": [list(c) for c in cols], "rows": rows, "changed_cells": n}


def block_text(b):
    if b is None:
        return ""
    return b[1] if b[0] == "p" else " ".join(" ".join(r) for r in b[1])


WORD = re.compile(r"[㐀-鿿豈-﫿]|[^\W㐀-鿿豈-﫿]+", re.U)


def words(blocks):
    """字數：英文以詞計，中日文以字計；表格的格子也算。"""
    return sum(len(WORD.findall(block_text(b))) for b in blocks)


def diff(before_blocks, after_blocks, notes=None):
    """回傳 (blocks, counts, 沒掛上的 notes)。"""
    items = notes or []
    used = [False] * len(items)
    out = []
    counts = {"groups": 0, "changed": 0, "added": 0, "removed": 0, "table_cells": 0}
    prev_same = True
    for status, a, b in align(before_blocks, after_blocks):
        kind = (a or b)[0]
        if status != "same" and prev_same:
            counts["groups"] += 1
        prev_same = status == "same"
        if status == "same":
            out.append({"status": "same", "kind": kind, ("text" if kind == "p" else "rows"): b[1]})
            continue
        counts[status] += 1
        e = {"status": status, "kind": kind}
        if status == "changed" and kind == "table":
            e.update(table_diff(a[1], b[1]))
            counts["table_cells"] += e["changed_cells"]
        elif status == "changed":
            e.update(before=a[1], after=b[1], ops=word_ops(a[1], b[1]))
        elif status == "removed":
            e["before"] = a[1]
        else:
            e["after"] = b[1]
        texts = block_text(a) + "\n" + block_text(b)
        hits = []
        for i, it in enumerate(items):
            if it.get("match") and it["match"] in texts:
                used[i] = True
                hits.append({"note": it.get("note", ""), "tag": it.get("tag", "")})
        if hits:
            e["notes"] = hits
        out.append(e)
    return out, counts, [it for i, it in enumerate(items) if not used[i]]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("before")
    ap.add_argument("after")
    ap.add_argument("-o", "--out")
    ap.add_argument("--words", action="store_true", help="只印兩版的字數和段數")
    ap.add_argument("--notes")
    ap.add_argument("--before-label", default="前版")
    ap.add_argument("--after-label", default="後版")
    a = ap.parse_args(argv)

    eb, ea = extract(a.before), extract(a.after)
    if a.words:
        for label, bl in (("before", eb), ("after", ea)):
            print(f"{label} words={words(bl)} blocks={len(bl)}")
        return 0
    notes = []
    if a.notes:
        with open(a.notes, encoding="utf-8") as f:
            notes = json.load(f)
    blocks, counts, unmatched = diff(eb, ea, notes)
    data = {
        "before": {"label": a.before_label, "path": os.path.basename(a.before), "words": words(eb), "blocks": len(eb)},
        "after": {"label": a.after_label, "path": os.path.basename(a.after), "words": words(ea), "blocks": len(ea)},
        "counts": counts, "blocks": blocks, "unmatched_notes": unmatched,
    }
    text = json.dumps(data, ensure_ascii=False, indent=1)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text)
    else:
        sys.stdout.write(text + "\n")
    for it in unmatched:
        print(f"UNMATCHED NOTE: {it.get('match')}", file=sys.stderr)
    print("groups={groups} changed={changed} added={added} removed={removed} table_cells={table_cells}".format(**counts), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
