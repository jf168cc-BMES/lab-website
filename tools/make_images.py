#!/usr/bin/env python3
"""產生網站用圖：分享預覽圖（og-image.jpg）、PI 照片（pi.jpg）與首頁用的小張 PI 照片（pi-sm.jpg）。

用法：
    python tools/make_images.py                      重做分享預覽圖與小張 PI 照片（pi-sm.jpg，從現有的 pi.jpg 縮出來）
    python tools/make_images.py --pi <原始照片路徑>    另外先把 PI 照片裁成 4:5、720×900
分享預覽圖：底圖是首頁主視覺的畫（static/img/bg/hero.webp）裁成 1200×630，左邊疊深藍漸層，
上面的字取自 content/site.yaml；改了網站名稱或主視覺圖就重跑一次。
"""
from __future__ import annotations

import argparse
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
IMG = ROOT / "static" / "img"
FONTS = Path("C:/Windows/Fonts")
NAVY_950, GOLD = (11, 24, 48), (242, 176, 30)


def font(name: str, size: int, index: int = 0) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), size, index=index)


def ramp(stops: list[tuple[float, float]], n: int) -> list[float]:
    """分段線性：stops 是 (位置 0–1, 值) 的列表，回傳 n 個點的值。"""
    out = []
    for i in range(n):
        t = i / (n - 1)
        for (t0, v0), (t1, v1) in zip(stops, stops[1:]):
            if t0 <= t <= t1:
                out.append(v0 + (v1 - v0) * (t - t0) / (t1 - t0))
                break
    return out


def draw_text(img: Image.Image, xy: tuple[int, int], text: str, fnt: ImageFont.FreeTypeFont, fill, spacing: int = 6) -> None:
    """文字加一層柔和的深藍陰影，壓在畫上也讀得清楚。"""
    shadow = Image.new("L", img.size, 0)
    ImageDraw.Draw(shadow).multiline_text(xy, text, font=fnt, fill=255, spacing=spacing)
    shadow = shadow.filter(ImageFilter.GaussianBlur(7)).point(lambda v: int(v * 0.75))
    img.paste(Image.new("RGB", img.size, NAVY_950), (0, 0), shadow)
    ImageDraw.Draw(img).multiline_text(xy, text, font=fnt, fill=fill, spacing=spacing)


def make_og() -> None:
    site = yaml.safe_load((ROOT / "content" / "site.yaml").read_text(encoding="utf-8"))
    w, h = 1200, 630
    # 底圖：主視覺的畫縮到蓋滿 1200×630（跟網站一樣靠右），上下多的部分裁掉
    hero = Image.open(IMG / "bg" / "hero.webp").convert("RGB")
    scale = max(w / hero.width, h / hero.height)
    hero = hero.resize((round(hero.width * scale), round(hero.height * scale)), Image.LANCZOS)
    left, top = hero.width - w, (hero.height - h) // 2
    img = hero.crop((left, top, left + w, top + h))
    # 深藍遮罩：左邊最濃（放字），往右變淡讓畫露出來；下半部再整排加深，放作者與系所那兩行
    horiz = ramp([(0, 0.94), (0.5, 0.9), (0.78, 0.6), (1, 0.12)], w)
    vert = ramp([(0, 0), (0.55, 0), (1, 0.78)], h)
    mask = Image.new("L", (w, h))
    mask.putdata([int(255 * max(horiz[x], vert[y])) for y in range(h) for x in range(w)])
    img = Image.composite(Image.new("RGB", (w, h), NAVY_950), img, mask)
    d = ImageDraw.Draw(img)
    d.rectangle((80, 120, 92, 300), fill=GOLD)
    draw_text(img, (116, 112), site["lab_name"]["en"].replace(" & ", " &\n"), font("segoeuib.ttf", 58), (255, 255, 255), spacing=8)
    draw_text(img, (116, 300), site["lab_name"]["zh"].replace("{wbr}", ""), font("msjhbd.ttc", 40), (246, 197, 82))
    draw_text(img, (116, 470), site["pi_line"]["en"], font("segoeui.ttf", 30), (232, 240, 250))
    draw_text(img, (116, 515), site["department"]["en"], font("segoeui.ttf", 24), (200, 214, 236))
    img.save(IMG / "og-image.jpg", quality=85, optimize=True, progressive=True)   # 畫作存 PNG 會到 700 KB，JPEG 約一成大小
    print("寫入", IMG / "og-image.jpg")


def make_pi(src: Path) -> None:
    im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    w, h = im.size
    target = 4 / 5
    if w / h > target:  # 太寬：左右裁
        nw = int(h * target)
        im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    else:  # 太高：從上方保留，裁掉下方
        nh = int(w / target)
        im = im.crop((0, 0, w, nh))
    im = im.resize((720, 900), Image.LANCZOS)
    im.save(IMG / "pi.jpg", quality=84, optimize=True, progressive=True)
    print("寫入", IMG / "pi.jpg")


def make_pi_small() -> None:
    """首頁「認識張老師」用的小張照片：同一張 pi.jpg 縮成 360×450（兩倍螢幕下約 180px 寬），檔案小很多。"""
    with Image.open(IMG / "pi.jpg") as im:
        im.convert("RGB").resize((360, 450), Image.LANCZOS).save(IMG / "pi-sm.jpg", quality=84, optimize=True, progressive=True)
    print("寫入", IMG / "pi-sm.jpg")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pi", type=Path, help="PI 原始照片路徑")
    args = ap.parse_args()
    IMG.mkdir(parents=True, exist_ok=True)
    make_og()
    if args.pi:
        make_pi(args.pi)
    make_pi_small()
