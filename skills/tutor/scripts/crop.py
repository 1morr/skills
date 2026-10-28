"""從 PDF 截課件圖，用紅框標出要看的地方。

    CROP="uv run --no-project --with pymupdf --with pillow python crop.py"
    $CROP find  <pdf> <頁> <文字>                 找文字的位置（掃描檔沒有文字層，找不到）
    $CROP lines <pdf> <頁>                        列出這頁每一行字的位置和字級（寫翻譯檔用）
    $CROP grid  <pdf> <頁> <out.png> [--rotate N]  整頁畫上格線，用來看圖讀座標
    $CROP cut   <pdf> <頁> <out.png> [--clip x0,y0,x1,y1] [--box ...] [--mark ...] [--rotate N] [--dpi N] [--zh 翻譯檔]

不給 --clip 就截整頁（課件導讀的整頁圖）。

--zh 另外產生一張翻譯圖 <out>.zh.png：同樣的範圍、紅框、標色，只是原文換成中文。
翻譯檔是 JSON，以頁碼為鍵，每項是一塊要換掉的字：

    {"3": [{"rect": [104, 217, 516, 338], "zh": "<b>平穩序列</b>是沒有趨勢……"}]}

rect 蓋掉原文（底色取 rect 邊緣最常見的顏色），zh 是 HTML，寫在原位。字級和字色預設取 rect 裡原文的，
可用 "size"（pt）、"css" 覆寫。譯文太長時字會自動縮小並提醒；公式和數字不要放進 rect，留原樣。

頁碼從 1 起算。座標單位是 PDF point（1/72 吋），原點在左上；有 --rotate 時，
座標是轉正之後那一頁的座標（先用 grid 加同樣的 --rotate 看）。
"""

import argparse
import io
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw, ImageFont

RED = (210, 30, 30, 255)
YELLOW = (255, 214, 0, 80)


def rect(s: str):
    v = [float(x) for x in s.split(",")]
    if len(v) != 4:
        raise argparse.ArgumentTypeError("座標要寫成 x0,y0,x1,y1")
    return v


# 譯文縮到這個比例以下就提醒：字太小，要精簡譯文或放大 rect
SHRINK_WARN = 0.85


def render(pdf: str, page: int, dpi: int, rotate: int, zh=None) -> Image.Image:
    doc = pymupdf.open(pdf)
    if not 1 <= page <= len(doc):
        sys.exit(f"{pdf} 只有 {len(doc)} 頁")
    if zh:
        translate(doc[page - 1], zh)
    pix = doc[page - 1].get_pixmap(dpi=dpi)
    im = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
    return im.rotate(-rotate, expand=True) if rotate else im


def text_lines(page):
    """這頁每一行字：(rect, 字級, 字色, 文字)。"""
    out = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            spans = [sp for sp in line["spans"] if sp["text"].strip()]
            if spans:
                out.append((pymupdf.Rect(line["bbox"]), spans[0]["size"], spans[0]["color"],
                            "".join(sp["text"] for sp in line["spans"])))
    return out


def background(pix, r) -> tuple:
    """rect 邊緣（往內 1pt）最常見的顏色，當作蓋掉原文時的底色。pix 是 72 dpi 的整頁圖。"""
    x0, y0 = max(0, int(r.x0) + 1), max(0, int(r.y0) + 1)
    x1, y1 = min(pix.width - 1, int(r.x1) - 1), min(pix.height - 1, int(r.y1) - 1)
    if x1 <= x0 or y1 <= y0:
        return (1, 1, 1)
    edge = [(x, y) for x in range(x0, x1 + 1) for y in (y0, y1)] + [(x, y) for y in range(y0, y1 + 1) for x in (x0, x1)]
    rgb = Counter(tuple(pix.pixel(x, y)[:3]) for x, y in edge).most_common(1)[0][0]
    return tuple(v / 255 for v in rgb)


def translate(page, items):
    """把每塊原文蓋掉，原位寫進中文。"""
    probe = page.get_pixmap(dpi=72)
    lines = text_lines(page)
    for it in items:
        r = pymupdf.Rect(it["rect"])
        inside = [ln for ln in lines if r.contains(pymupdf.Point((ln[0].x0 + ln[0].x1) / 2, (ln[0].y0 + ln[0].y1) / 2))]
        size = it.get("size") or (statistics.median(ln[1] for ln in inside) if inside else 11)
        color = Counter(ln[2] for ln in inside).most_common(1)[0][0] if inside else 0
        page.draw_rect(r, color=None, fill=background(probe, r), overlay=True)
        css = (f"* {{font-family: sans-serif; font-size: {size:.1f}px; line-height: 1.45; color: #{color:06x};}} "
               + it.get("css", ""))
        _, scale = page.insert_htmlbox(r, it["zh"], css=css)
        if scale < SHRINK_WARN:
            text = " ".join(it["zh"].split())[:20]
            print(f"提醒：「{text}…」放不下，字縮到 {scale:.0%}：精簡譯文或放大 rect", file=sys.stderr)


def load_zh(path: str, page: int) -> list:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    items = data.get(str(page))
    if not items:
        sys.exit(f"{path} 沒有第 {page} 頁的譯文：翻譯檔以頁碼為鍵，例如 {{\"{page}\": [{{\"rect\": [...], \"zh\": \"...\"}}]}}")
    for it in items:
        if len(it.get("rect", [])) != 4 or not str(it.get("zh", "")).strip():
            sys.exit(f"{path} 第 {page} 頁有一項缺 rect（x0,y0,x1,y1）或 zh：{it}")
    return items


def lines(a):
    page = pymupdf.open(a.pdf)[a.page - 1]
    print(f"頁面大小 {page.rect.width:.0f} x {page.rect.height:.0f} pt")
    found = text_lines(page)
    if not found:
        print("沒有文字層（掃描檔）：用 grid 看座標，翻譯檔的 rect 一樣能蓋掉原文")
    for r, size, _, text in found:
        print(f"{r.x0:.0f},{r.y0:.0f},{r.x1:.0f},{r.y1:.0f}  {size:.1f}pt  {text}")


def find(a):
    page = pymupdf.open(a.pdf)[a.page - 1]
    print(f"頁面大小 {page.rect.width:.0f} x {page.rect.height:.0f} pt")
    hits = page.search_for(a.text)
    if not hits:
        print("找不到（掃描檔沒有文字層，改用 grid）")
    for r in hits:
        print(f"{r.x0:.0f},{r.y0:.0f},{r.x1:.0f},{r.y1:.0f}")


def grid(a):
    dpi = 100
    s = dpi / 72
    im = render(a.pdf, a.page, dpi, a.rotate).convert("RGBA")
    over = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    font = ImageFont.load_default()
    w, h = im.size[0] / s, im.size[1] / s
    for x in range(0, int(w) + 1, 50):
        d.line([(x * s, 0), (x * s, im.size[1])], fill=(0, 120, 255, 90 if x % 100 else 160), width=1)
        if x % 100 == 0:
            d.text((x * s + 2, 2), str(x), fill=(0, 80, 220, 255), font=font)
    for y in range(0, int(h) + 1, 50):
        d.line([(0, y * s), (im.size[0], y * s)], fill=(0, 120, 255, 90 if y % 100 else 160), width=1)
        if y % 100 == 0:
            d.text((2, y * s + 2), str(y), fill=(0, 80, 220, 255), font=font)
    Image.alpha_composite(im, over).convert("RGB").save(a.out)
    print(f"{a.out}（{w:.0f} x {h:.0f} pt，細線每 50、粗線每 100）")


def cut(a):
    jobs = [(a.out, None)]
    if a.zh:
        if a.rotate:
            sys.exit("--zh 不支援轉向的頁（--rotate）：這種頁在圖前面放 class=\"tr\" 的譯文")
        out = Path(a.out)
        jobs.append((str(out.with_name(out.stem + ".zh" + out.suffix)), load_zh(a.zh, a.page)))
    s = a.dpi / 72
    for path, zh in jobs:
        im = render(a.pdf, a.page, a.dpi, a.rotate, zh).convert("RGBA")
        over = Image.new("RGBA", im.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(over)
        for r in a.mark:
            d.rectangle([v * s for v in r], fill=YELLOW)
        width = max(2, round(1.5 * s))
        for r in a.box:
            d.rectangle([v * s for v in r], outline=RED, width=width)
        im = Image.alpha_composite(im, over).convert("RGB")
        if a.clip:
            im = im.crop(tuple(round(v * s) for v in a.clip))
        # 課件多半是黑白字：縮成小調色盤，檔案小很多，字和標色都還清楚
        im.quantize(colors=64).save(path, optimize=True)
        print(f"{path} {im.size[0]}x{im.size[1]}px")


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):  # 測試會換成 StringIO
            stream.reconfigure(encoding="utf-8")  # Windows 終端機預設不是 UTF-8
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("find", "lines", "grid", "cut"):
        p = sub.add_parser(name)
        p.add_argument("pdf")
        p.add_argument("page", type=int)
        if name != "lines":
            p.add_argument("text" if name == "find" else "out")
        if name in ("grid", "cut"):
            p.add_argument("--rotate", type=int, default=0, help="順時針轉幾度（橫放的表用 90）")
        if name == "cut":
            p.add_argument("--clip", type=rect, help="要截的範圍；不給就截整頁")
            p.add_argument("--box", type=rect, action="append", default=[], help="紅框，可重複")
            p.add_argument("--mark", type=rect, action="append", default=[], help="淡黃標色，可重複")
            p.add_argument("--dpi", type=int, default=200)
            p.add_argument("--zh", help="翻譯檔（JSON）：另外產生 <out>.zh.png")
    a = ap.parse_args(argv)
    {"find": find, "lines": lines, "grid": grid, "cut": cut}[a.cmd](a)


if __name__ == "__main__":
    main()
