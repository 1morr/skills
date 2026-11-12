"""把計算腳本算好的值填進範本的 {{名稱}}；有一個沒填到就不產出。

    python fill.py <values.json> <範本> -o <產出> [--sheet <填好的答案紙>]

values.json 是計算腳本（calc.py、gen.py）寫出的一層物件，值都是字串：
    {"t_stat": "2.262", "decision": "reject H<sub>0</sub>"}
四捨五入到幾位、結論是哪一句，由計算腳本決定；這支只管放進去。值原樣放進範本，可以含 HTML。
用不到的值不算錯：答案紙、導讀頁、練習頁、答案檔共用同一份 values.json，各自只用一部分。

--sheet：範本裡的 {{sheet:a}} 換成答案紙上 <div class="part" data-part="a">…</div><!--/part--> 裡面那一段，
導讀頁的「答案紙上寫這樣」就和答案紙一字不差。答案紙要先填好。

寫法照 Mustache 的 {{name}} 和 jinja2-cli 的「範本 + JSON」。只用標準函式庫，CI 才能直接跑測試。
"""

import argparse
import json
import re
import sys
from pathlib import Path

PLACE = re.compile(r"\{\{\s*([^{}\s]+)\s*\}\}")
PART = re.compile(r"""<div\b[^>]*\bdata-part\s*=\s*["']([^"']+)["'][^>]*>(.*?)</div>\s*<!--/part-->""", re.S | re.I)
SHEET = "sheet:"


def sheet_parts(sheet: str) -> dict:
    return {m.group(1): m.group(2).strip() for m in PART.finditer(sheet)}


def fill(template: str, values, sheet=None):
    """回傳 (填好的內容, 問題清單)；有問題時內容不能用。"""
    if not isinstance(values, dict):
        return template, ["values.json 最外層要是一個物件：{\"名稱\": \"值\"}"]
    problems = [f"「{k}」的值是 {type(v).__name__}，要是字串：先在計算腳本決定四捨五入到幾位、寫成什麼字"
                for k, v in values.items() if not isinstance(v, str)]
    parts = None
    if sheet is not None:
        parts = sheet_parts(sheet)
        if PLACE.search(sheet):
            problems.append("答案紙還有沒填的 {{佔位}}：--sheet 要給填好的答案紙")
    missing, lost = [], []

    def repl(m):
        name = m.group(1)
        if name.startswith(SHEET):
            if parts is None:
                problems.append(f"範本用了 {{{{{name}}}}}，但沒給 --sheet")
            elif name[len(SHEET):] not in parts:
                lost.append(name[len(SHEET):])
            else:
                return parts[name[len(SHEET):]]
        elif isinstance(values.get(name), str):
            return values[name]
        elif name not in values:
            missing.append(name)
        return m.group(0)

    out = PLACE.sub(repl, template)
    if missing:
        problems.append(f"values.json 沒有這幾個值：{'、'.join(dict.fromkeys(missing))}")
    if lost:
        problems.append(f"答案紙沒有 data-part=\"{'」「'.join(dict.fromkeys(lost))}\" 的段落："
                        '每題包成 <div class="part" data-part="a">…</div><!--/part-->')
    return out, list(dict.fromkeys(problems))


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")  # Windows 終端機預設不是 UTF-8
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("values", type=Path)
    ap.add_argument("template", type=Path)
    ap.add_argument("-o", "--out", type=Path, required=True)
    ap.add_argument("--sheet", type=Path)
    args = ap.parse_args(argv)
    sheet = args.sheet.read_text(encoding="utf-8") if args.sheet else None
    out, problems = fill(args.template.read_text(encoding="utf-8"),
                         json.loads(args.values.read_text(encoding="utf-8")), sheet)
    if problems:
        print(f"{args.template}：{len(problems)} 個問題，沒有產出", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    args.out.write_text(out, encoding="utf-8")
    print(args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
