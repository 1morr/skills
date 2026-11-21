"""把資料、本機媒體檔案和共用樣式填進原始頁（document.html 的副本），產出單一離線 HTML 檔。

用法：
  python fill.py <page-src.html> -o <page.html> [--json 名稱=檔案.json ...] [--text 名稱=檔案 ...]

- 頁面裡的 __DATA__ 換成一個 JSON 物件：每個 --json 放解析後的內容，每個 --text 放檔案原文。
  換完的字串可以直接放進 <script type="application/json">。沒有 --json / --text 時不需要 __DATA__。
- <img>、<video>、<source>、<audio> 的相對路徑 src（相對於 page-src.html）內嵌成 data URI；data: 保留不動；
  任何外部網址（http://、https://、//）拒絕產出，確保 100% 離線可用。
- 在 <head> 最前面內嵌 pages/scripts/tokens.css（配色、字體）和同資料夾的 diff.css（改動標記、版面；
  class 各用在哪見 LOOK.md）。共用的 pages/scripts 優先從環境變數 SKILLS_ROOT 解析，未設時往上兩層找。
- 寫出之後用本機的 Chrome 或 Edge 在寬螢幕和手機寬各量一次水平溢出（pages/scripts/overflow.py）。

成功時印出輸出檔路徑，退出碼 0。有問題時印到 stderr、退出碼 1、沒有產出：
- 原始頁的 <style> 重新定義了 tokens.css 的變數。
- 引用了外部 http(s):// 或 // 資源。
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


def pages_scripts_dir(env=None) -> Path:
    """優先以環境變數 SKILLS_ROOT 解析 pages/scripts，未設時退回相對本檔的 repo 根目錄。"""
    env_map = os.environ if env is None else env
    root = env_map.get("SKILLS_ROOT")
    base = Path(root).expanduser().resolve() if root else HERE.parents[2]
    return base / "pages" / "scripts"


PAGES = pages_scripts_dir()
sys.path.insert(0, str(PAGES))
import overflow  # noqa: E402

STYLES = (PAGES / "tokens.css", HERE / "diff.css")
STYLE_BLOCK = re.compile(r"<style\b[^>]*>(.*?)</style\s*>", re.I | re.S)
SCRIPT_BODY = re.compile(r"(<script\b[^>]*>)(.*?)(</script\s*>)", re.I | re.S)
EXTERNAL_URL = re.compile(r"^\s*(?:https?:)?//", re.I)

MEDIA_SRC = re.compile(
    r"""(<(?:img|video|source|audio)\b[^>]*?\bsrc\s*=\s*)(?:(["'])(?!\s*data:)([^"']*)\2|(?![\"'])(?!data:)([^\s>]+))""",
    re.I,
)
EXTERNAL_RES = re.compile(
    r"""<(?:img|video|source|audio|script|link)\b[^>]*?\b(?:src|href|poster)\s*=\s*(?:["']\s*((?:https?:)?//[^"']*)["']|((?:https?:)?//[^\s>]+))""",
    re.I,
)


def _styles() -> tuple:
    return (pages_scripts_dir() / "tokens.css", HERE / "diff.css")


def external_urls(html: str) -> list:
    """找出頁面標籤上引用的外部 http(s):// 或 // 資源網址（忽略 <script> 內文，保留 <script src=...> 開頭標籤）。"""
    stripped = SCRIPT_BODY.sub(r"\1\3", html)
    found = [m.group(1) or m.group(2) for m in EXTERNAL_RES.finditer(stripped)]
    return list(dict.fromkeys(u.strip() for u in found if u))


def pairs(items, flag):
    out = []
    for it in items or []:
        name, sep, path = it.partition("=")
        if not sep or not name or not path:
            raise SystemExit(f"{flag} expects NAME=FILE, got {it!r}")
        out.append((name, path))
    return out


def fill(template, data, base):
    bad = external_urls(template)
    if bad:
        raise SystemExit(f"external media/resource URL is not allowed in offline page: {', '.join(bad)}")

    def embed(m):
        quote = m.group(2) or '"'
        raw = m.group(3) if m.group(2) is not None else m.group(4)
        if EXTERNAL_URL.match(raw):
            raise SystemExit(f"external media URL is not allowed in offline page: {raw.strip()}")
        path = os.path.join(base, raw)
        mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
        with open(path, "rb") as f:
            uri = f"data:{mime};base64," + base64.b64encode(f.read()).decode()
        return f"{m.group(1)}{quote}{uri}{quote}"

    page = MEDIA_SRC.sub(embed, template)
    if data:
        if "__DATA__" not in template:
            raise SystemExit("page has no __DATA__ placeholder")
        page = page.replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
    return page


def own_tokens(page: str) -> list:
    """原始頁的 <style> 裡重新定義的 tokens.css 變數：兩份對不上時，這一頁會和其他頁長得不一樣。"""
    tokens_css = _styles()[0]
    names = sorted(set(re.findall(r"--([a-z0-9-]+)\s*:", tokens_css.read_text(encoding="utf-8"))), key=len, reverse=True)
    own = re.compile(r"(?<![\w-])--(" + "|".join(map(re.escape, names)) + r")\s*:")
    return sorted({"--" + m.group(1) for css in STYLE_BLOCK.findall(page) for m in own.finditer(css)})


def with_styles(page: str) -> str:
    """把 tokens.css 和 diff.css 放在 <head> 的最前面：原始頁自己的 <style> 排在後面，補得上、也蓋得過。"""
    style = "<style>\n" + "".join(p.read_text(encoding="utf-8") for p in _styles()) + "</style>\n"
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
    bad = external_urls(src)
    if bad:
        print(f"{a.src}：引用了外部網址 {'、'.join(bad)}，沒有產出。改用本機相對路徑讓 fill.py 內嵌", file=sys.stderr)
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
