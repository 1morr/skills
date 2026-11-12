"""把資料和本機檔案填進手寫的頁面，產出單一 HTML 檔。

用法：
  python fill.py <page-src.html> -o <page.html> [--json 名稱=檔案.json ...] [--text 名稱=檔案 ...]

- 頁面裡的 __DATA__ 換成一個 JSON 物件：每個 --json 放解析後的內容，每個 --text 放檔案原文（例如 git diff、
  指令輸出）。換完的字串可以直接放進 <script type="application/json">。沒有 --json / --text 時不需要 __DATA__。
- <img>、<video>、<source> 的相對路徑 src（相對於 page-src.html）內嵌成 data URI；http(s) 和 data: 不動。
只用標準函式庫。
"""
import argparse
import base64
import json
import mimetypes
import os
import re
import sys

MEDIA_SRC = re.compile(r"""(<(?:img|video|source)\b[^>]*?\bsrc=)(["'])(?!data:|https?:|//)([^"']+)\2""", re.I)


def pairs(items, flag):
    out = []
    for it in items or []:
        name, sep, path = it.partition("=")
        if not sep or not name or not path:
            raise SystemExit(f"{flag} expects NAME=FILE, got {it!r}")
        out.append((name, path))
    return out


def fill(template, data, base):
    page = template
    if data:
        if "__DATA__" not in template:
            raise SystemExit("page has no __DATA__ placeholder")
        page = page.replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))

    def embed(m):
        path = os.path.join(base, m.group(3))
        mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
        with open(path, "rb") as f:
            uri = f"data:{mime};base64," + base64.b64encode(f.read()).decode()
        return f"{m.group(1)}{m.group(2)}{uri}{m.group(2)}"

    return MEDIA_SRC.sub(embed, page)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--json", action="append")
    ap.add_argument("--text", action="append")
    a = ap.parse_args(argv)
    data = {}
    for name, path in pairs(a.json, "--json"):
        with open(path, encoding="utf-8") as f:
            data[name] = json.load(f)
    for name, path in pairs(a.text, "--text"):
        with open(path, encoding="utf-8", errors="replace") as f:
            data[name] = f.read()
    with open(a.src, encoding="utf-8") as f:
        page = fill(f.read(), data, os.path.dirname(os.path.abspath(a.src)))
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(page)
    print(a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
