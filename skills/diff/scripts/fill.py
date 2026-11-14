"""把資料、本機檔案和共用樣式填進手寫的頁面，產出單一 HTML 檔。

用法：
  python fill.py <page-src.html> -o <page.html> [--json 名稱=檔案.json ...] [--text 名稱=檔案 ...]

- 頁面裡的 __DATA__ 換成一個 JSON 物件：每個 --json 放解析後的內容，每個 --text 放檔案原文（例如 git diff、
  指令輸出）。換完的字串可以直接放進 <script type="application/json">。沒有 --json / --text 時不需要 __DATA__。
- <img>、<video>、<source> 的相對路徑 src（相對於 page-src.html）內嵌成 data URI；http(s) 和 data: 不動。
- 在 <head> 最前面內嵌 pages/scripts/tokens.css（配色、字體）和同資料夾的 diff.css（改動標記、版面、程式頁的元件；
  class 各用在哪見 LOOK.md）。原始頁自己的 <style> 排在後面，只補這兩份沒有的東西。
- 寫出之後用本機的 Chrome 或 Edge 在寬螢幕和手機寬各量一次水平溢出（pages/scripts/overflow.py）。

成功時印出輸出檔路徑，退出碼 0。有問題時印到 stderr、退出碼 1、沒有產出：
- 原始頁的 <style> 重新定義了 tokens.css 的變數。
- 有水平溢出：逐條印出哪個元素在哪個寬度超出幾 px。
找不到瀏覽器時印一句提醒，照樣產出。只用標準函式庫。
"""
import argparse
import base64
import json
import mimetypes
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAGES = HERE.parents[2] / "pages" / "scripts"
# 共用的配色和水平溢出量測在 plugin 根目錄的 pages/scripts/
sys.path.insert(0, str(PAGES))
import overflow  # noqa: E402

STYLES = (PAGES / "tokens.css", HERE / "diff.css")
STYLE_BLOCK = re.compile(r"<style\b[^>]*>(.*?)</style\s*>", re.I | re.S)

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


def own_tokens(page: str) -> list:
    """原始頁的 <style> 裡重新定義的 tokens.css 變數：兩份對不上時，這一頁會和其他頁長得不一樣。"""
    names = sorted(set(re.findall(r"--([a-z0-9-]+)\s*:", STYLES[0].read_text(encoding="utf-8"))), key=len, reverse=True)
    own = re.compile(r"(?<![\w-])--(" + "|".join(map(re.escape, names)) + r")\s*:")
    return sorted({"--" + m.group(1) for css in STYLE_BLOCK.findall(page) for m in own.finditer(css)})


def with_styles(page: str) -> str:
    """把 tokens.css 和 diff.css 放在 <head> 的最前面：原始頁自己的 <style> 排在後面，補得上、也蓋得過。"""
    style = "<style>\n" + "".join(p.read_text(encoding="utf-8") for p in STYLES) + "</style>\n"
    for opener in (r"<head\b[^>]*>", r"<html\b[^>]*>", r"<!doctype[^>]*>"):
        m = re.search(opener, page, re.I)
        if m:
            return page[:m.end()] + "\n" + style + page[m.end():]
    return style + page


def main(argv=None, measure=overflow.measure):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")  # Windows 終端機預設不是 UTF-8
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
        src = f.read()
    own = own_tokens(src)
    if own:
        print(f"{a.src}：<style> 裡重新定義了 {'、'.join(own)}，沒有產出。拿掉：fill.py 會放 tokens.css", file=sys.stderr)
        return 1
    page = with_styles(fill(src, data, os.path.dirname(os.path.abspath(a.src))))
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(page)
    if not overflow.deliverable(Path(a.out), a.src, measure(Path(a.out))):
        return 1
    print(a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
