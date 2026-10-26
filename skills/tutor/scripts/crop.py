"""從 PDF 截課件圖，用紅框標出要看的地方。

    CROP="uv run --no-project --with pymupdf --with pillow python crop.py"
    $CROP find <pdf> <頁> <文字>                 找文字的位置（掃描檔沒有文字層，找不到）
    $CROP grid <pdf> <頁> <out.png> [--rotate N]  整頁畫上格線，用來看圖讀座標
    $CROP cut  <pdf> <頁> <out.png> [--clip x0,y0,x1,y1] [--box ...] [--mark ...] [--rotate N] [--dpi N]

不給 --clip 就截整頁（課件導讀的整頁圖）。

頁碼從 1 起算。座標單位是 PDF point（1/72 吋），原點在左上；有 --rotate 時，
座標是轉正之後那一頁的座標（先用 grid 加同樣的 --rotate 看）。
"""

import argparse
import io
import sys

import pymupdf
from PIL import Image, ImageDraw, ImageFont

RED = (210, 30, 30, 255)
YELLOW = (255, 214, 0, 80)


def rect(s: str):
    v = [float(x) for x in s.split(",")]
    if len(v) != 4:
        raise argparse.ArgumentTypeError("座標要寫成 x0,y0,x1,y1")
    return v


def render(pdf: str, page: int, dpi: int, rotate: int) -> Image.Image:
    doc = pymupdf.open(pdf)
    if not 1 <= page <= len(doc):
        sys.exit(f"{pdf} 只有 {len(doc)} 頁")
    pix = doc[page - 1].get_pixmap(dpi=dpi)
    im = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
    return im.rotate(-rotate, expand=True) if rotate else im


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
    s = a.dpi / 72
    im = render(a.pdf, a.page, a.dpi, a.rotate).convert("RGBA")
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
    im.quantize(colors=64).save(a.out, optimize=True)
    print(f"{a.out} {im.size[0]}x{im.size[1]}px")


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")  # Windows 終端機預設不是 UTF-8
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("find", "grid", "cut"):
        p = sub.add_parser(name)
        p.add_argument("pdf")
        p.add_argument("page", type=int)
        p.add_argument("text" if name == "find" else "out")
        if name != "find":
            p.add_argument("--rotate", type=int, default=0, help="順時針轉幾度（橫放的表用 90）")
        if name == "cut":
            p.add_argument("--clip", type=rect, help="要截的範圍；不給就截整頁")
            p.add_argument("--box", type=rect, action="append", default=[], help="紅框，可重複")
            p.add_argument("--mark", type=rect, action="append", default=[], help="淡黃標色，可重複")
            p.add_argument("--dpi", type=int, default=200)
    a = ap.parse_args(argv)
    {"find": find, "grid": grid, "cut": cut}[a.cmd](a)


if __name__ == "__main__":
    main()
