"""把整份課件變成導讀頁課件欄的圖：每頁一張原文圖，有譯文的頁再一張翻譯圖，外加一份清單。

    DECK="uv run --no-project --with pymupdf --with pillow python deck.py"
    $DECK <輸出資料夾> <代號>=<pdf> [<代號>=<pdf> …] [--width 1000]

代號是讀者認得的短名（L20、T6-Summary），只能用英數字和 -；導讀頁用「L20 p.25」指到那一頁。

跑兩次：

1. 第一次：每頁出一張 <代號>-<頁>.jpg（有照片的頁）或 .png，寫出 slides.json，
   並把課件上每一塊不重複的原文寫進 zh.json：{"原文": ""}。
2. 把 zh.json 的譯文填上再跑一次：有譯文的頁多一張 <代號>-<頁>.zh.*，slides.json 跟著更新。

zh.json 照課件的順序排，被拆成兩塊的一句話會排在一起。值是 HTML（可以用 <b>）。留空字串的那一塊不翻：人名、年份、地圖上的地名、公式。
重跑會保留填好的譯文；課件多了字就加在最後，課件上已經沒有的原文留著不刪。
斜放的字（角落的緞帶）和沒有字母的塊（頁碼、純數字）不列進 zh.json。

slides.json（build.py 讀它；路徑相對於這個檔）：

    {"decks": [{"id": "L20", "pages": [{"n": 1, "src": "L20-01.jpg", "zh": "L20-01.zh.jpg", "w": 1000, "h": 563}, …]}]}

沒有翻譯圖的頁 zh 是 null；w、h 是圖的大小（px）。

譯文比原文長時，會往右寫到那一列空著的地方（右邊有別的字或圖就到它前面為止）；還是放不下字才縮小。
最後印每份課件幾頁、幾頁有翻譯圖、zh.json 還有幾塊沒填，並列出字縮到七成以下的頁（「L20 p.28：字縮到 52%」）：
那幾頁打開看，太小的把那一頁的譯文改短再跑一次。
"""

import argparse
import io
import json
import re
import sys
from pathlib import Path

import pymupdf
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import crop  # noqa: E402  蓋掉原文、寫進譯文的 translate()

ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]*$")
LETTER = re.compile(r"[^\W\d_]")
# 字的外框只包到字身，大寫字母的頂端和 g、y 的尾巴會露出來：照字級往外多蓋一圈
PAD_Y, PAD_X = 0.12, 0.06
# 中文字比同字級的英文寬，標題再大也不超過頁寬的這個比例
SHRINK, MAX_SIZE = 0.92, 1 / 32
# 字縮到這個比例以下的頁列出來給人看
TINY = 0.7
# 佔頁面這麼大的圖是底圖，不擋字
BACKDROP = 0.5


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


def obstacles(page) -> list:
    """這頁會擋住字的東西：每一塊字，和不是底圖的每一張圖。"""
    area = page.rect.width * page.rect.height
    boxes = [pymupdf.Rect(b["bbox"]) for b in page.get_text("dict")["blocks"] if b.get("type") == 0]
    boxes += [r for r in (pymupdf.Rect(i["bbox"]) for i in page.get_image_info()) if r.get_area() < area * BACKDROP]
    return boxes


def right_edge(page, boxes: list, r) -> float:
    """這一塊可以往右寫到哪：同一橫帶上右邊最近的字或圖的前面；都沒有就到右邊界，留的邊和這一塊離左邊界一樣寬。"""
    limit = page.rect.width - max(page.rect.width * 0.03, min(r.x0, page.rect.width * 0.1))
    for o in boxes:
        if o.x0 >= r.x1 - 1 and o.y0 < r.y1 and o.y1 > r.y0:
            limit = min(limit, o.x0 - 6)
    return max(limit, r.x1)


def overlay(page, found: list, zh: dict) -> list:
    """這頁有譯文的塊，寫成 crop.translate() 的格式。"""
    cap = page.rect.width * MAX_SIZE
    boxes = obstacles(page)
    items = []
    for b in found:
        text = zh.get(b["en"], "").strip()
        if not text:
            continue
        x0, y0, x1, y1 = b["rect"]
        dx, dy = b["size"] * PAD_X, b["size"] * PAD_Y
        cover = [x0 - dx, y0 - dy, x1 + dx, y1 + dy]
        items.append({"rect": cover, "box": [cover[0], cover[1], max(cover[2], right_edge(page, boxes, pymupdf.Rect(b["rect"]))), cover[3]],
                      "zh": text, "size": min(b["size"], cap) * SHRINK, "css": "* {line-height: 1.2;}"})
    return items


def save(page, path: Path, width: int, photo: bool) -> tuple:
    """存一張整頁圖，回傳 (寬, 高)。"""
    pix = page.get_pixmap(dpi=round(width / page.rect.width * 72))
    im = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
    if photo:
        im.save(path, quality=82, optimize=True)
    else:
        im.quantize(colors=64).save(path, optimize=True)
    return im.size


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
    manifest = {"decks": []}
    tiny = []  # [(字縮到幾成, "L20 p.28")]
    for name, pdf in decks:
        pages, done = [], 0
        doc = pymupdf.open(pdf)
        digits = max(2, len(str(len(doc))))
        for n, page in enumerate(doc, 1):
            found = blocks(page)
            for b in found:
                zh.setdefault(b["en"], "")
            photo = bool(page.get_images())
            ext = "jpg" if photo else "png"
            stem = f"{name}-{n:0{digits}d}"
            w, h = save(page, a.out / f"{stem}.{ext}", a.width, photo)
            items = overlay(page, found, zh)
            zh_name = None
            if items:
                smallest = min(crop.translate(page, items, warn=False))
                if smallest < TINY:
                    tiny.append((smallest, f"{name} p.{n}"))
                zh_name = f"{stem}.zh.{ext}"
                save(page, a.out / zh_name, a.width, photo)
                done += 1
            pages.append({"n": n, "src": f"{stem}.{ext}", "zh": zh_name, "w": w, "h": h})
        manifest["decks"].append({"id": name, "pages": pages})
        print(f"{name}：{len(pages)} 頁，{done} 頁有翻譯圖")
    todo.write_text(json.dumps(zh, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (a.out / "slides.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    empty = sum(1 for v in zh.values() if not v.strip())
    print(f"{todo}：{len(zh)} 塊原文，{empty} 塊沒有譯文" + ("（填上再跑一次；不翻的留空）" if empty else ""))
    for scale, where in sorted(tiny):
        print(f"{where}：字縮到 {scale:.0%}")
    print(a.out / "slides.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
