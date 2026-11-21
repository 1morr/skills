"""把整份課件切成導讀頁課件欄的單頁原圖，同時抽出文字塊寫進 slides.json 與去重的 zh.json。

    DECK="uv run --no-project --with pymupdf --with pillow python scripts/deck.py"
    $DECK <輸出資料夾> <代號>=<pdf> [<代號>=<pdf> …] [--width 1000]

代號是讀者認得的短名（L20、T6-Summary），只能用英數字和 -；導讀頁用「L20 p.25」指到那一頁。

跑一次即可：
- 每頁出一張單套原圖 <代號>-<頁>.jpg（有圖片的頁）或 .png，不塗改原圖像素。
- 寫出 slides.json（含每頁尺寸與原文塊順序 blocks；已標記的 skip 會保留）。
- 把課件上每一塊不重複的原文寫進 zh.json：{"原文": ""}。

翻譯子代理把 zh.json 填好後，build.py 組頁時直接讀取 zh.json，在右欄課件圖下方渲染可切換／摺疊的 HTML 譯文對照層。
zh.json 的值是 HTML（可以用 <b>）；留空字串的那一塊不翻（純頁碼、純年份、無通行譯名的人名或縮寫）。
重跑會保留已填好的譯文與已標記的 skip；斜放的字（角落緞帶）和沒有字母的塊（頁碼、純數字）不列進 zh.json。

slides.json（build.py 讀它；圖檔路徑相對於這個檔）：

    {"decks": [{"id": "L20", "pages": [{"n": 1, "src": "L20-01.jpg", "w": 1000, "h": 563, "blocks": ["…"], "skip": true}, …]}]}

純封面、議程、行政公告等過場頁可在 slides.json 的該頁加上 "skip": true（或在導讀頁 <body> 寫 data-skip），build.py 不計入「沒講到」。
"""

import argparse
import io
import json
import re
import sys
from pathlib import Path

import pymupdf
from PIL import Image

ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]*$")
LETTER = re.compile(r"[^\W\d_]")


def blocks(page) -> list:
    """這頁每一塊要翻的字：{"rect", "en", "size"}。"""
    out = []
    for b in page.get_text("dict")["blocks"]:
        if b.get("type") != 0:
            continue
        if any(abs(ln["dir"][1]) > 0.01 for ln in b["lines"]):
            continue
        text = " ".join(" ".join(sp["text"] for sp in ln["spans"]) for ln in b["lines"])
        text = " ".join(text.split())
        if not LETTER.search(text):
            continue
        size = max(sp["size"] for ln in b["lines"] for sp in ln["spans"])
        out.append({"rect": list(b["bbox"]), "en": text, "size": size})
    return out


def save(page, path: Path, width: int, photo: bool) -> tuple:
    """存一張整頁原圖，回傳 (寬, 高)。"""
    pix = page.get_pixmap(dpi=round(width / page.rect.width * 72))
    im = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
    if photo:
        im.save(path, quality=82, optimize=True)
    else:
        im.quantize(colors=64).save(path, optimize=True)
    return im.size


def _existing_skips(manifest_path: Path) -> tuple:
    """保留重跑前已在 slides.json 標記的 skip。"""
    if not manifest_path.is_file():
        return set(), None
    try:
        old = json.loads(manifest_path.read_text(encoding="utf-8"))
        page_skips = {(d["id"], int(p["n"])) for d in old.get("decks", []) for p in d.get("pages", []) if p.get("skip")}
        return page_skips, old.get("skip")
    except (OSError, ValueError, KeyError, TypeError):
        return set(), None


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):  # 測試會換成 StringIO
            stream.reconfigure(encoding="utf-8")  # Windows 終端機預設不是 UTF-8
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("out", type=Path)
    ap.add_argument("decks", nargs="+", metavar="代號=pdf")
    ap.add_argument("--width", type=int, default=1000, help="圖寬幾 px")
    a = ap.parse_args(argv)
    decks = []
    for item in a.decks:
        name, _, pdf = item.partition("=")
        if not ID.match(name) or not pdf:
            sys.exit(f"「{item}」看不懂：寫成 <代號>=<pdf>，代號只能用英數字和 -，例如 L20=slides/20.pdf")
        if not Path(pdf).is_file():
            sys.exit(f"找不到 {pdf}")
        if name in (d[0] for d in decks):
            sys.exit(f"代號 {name} 重複了：每份課件一個代號")
        decks.append((name, pdf))
    a.out.mkdir(parents=True, exist_ok=True)
    todo = a.out / "zh.json"
    zh = json.loads(todo.read_text(encoding="utf-8")) if todo.is_file() else {}
    manifest_path = a.out / "slides.json"
    page_skips, top_skip = _existing_skips(manifest_path)
    manifest = {"decks": []}
    if top_skip is not None:
        manifest["skip"] = top_skip
    for name, pdf in decks:
        pages, done = [], 0
        doc = pymupdf.open(pdf)
        digits = max(2, len(str(len(doc))))
        for n, page in enumerate(doc, 1):
            found = blocks(page)
            texts = list(dict.fromkeys(b["en"] for b in found))
            for en in texts:
                zh.setdefault(en, "")
            if any(zh.get(en, "").strip() for en in texts):
                done += 1
            photo = bool(page.get_images())
            ext = "jpg" if photo else "png"
            stem = f"{name}-{n:0{digits}d}"
            w, h = save(page, a.out / f"{stem}.{ext}", a.width, photo)
            entry = {"n": n, "src": f"{stem}.{ext}", "w": w, "h": h, "blocks": texts}
            if (name, n) in page_skips:
                entry["skip"] = True
            pages.append(entry)
        manifest["decks"].append({"id": name, "pages": pages})
        print(f"{name}：{len(pages)} 頁，{done} 頁有譯文")
    todo.write_text(json.dumps(zh, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    empty = sum(1 for v in zh.values() if not v.strip())
    print(f"{todo}：{len(zh)} 塊原文，{empty} 塊沒有譯文" + ("（填好後跑 build.py；不翻的留空）" if empty else ""))
    print(manifest_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
