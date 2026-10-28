#!/usr/bin/env python3
"""把 SciDraw 生的圖轉成網站用的 WebP：論文示意圖放 static/img/pubs/，研究主題圖放 static/img/research/。

用法：
    python tools/pub_images.py --src <原圖資料夾>
原圖資料夾裡每篇論文、每個研究主題各一個子資料夾，最上層的 prompts.json 記每張圖的路徑（子資料夾/檔名）、
種類（kind）與對應的論文 DOI（paper）或研究主題（theme）；原圖不進 git。
- schematic（論文示意圖）：先裁掉大片白邊，產生 {slug}-schematic-sm.webp（960 寬，精選論文卡片）與
  {slug}-schematic.webp（1600 寬，點開的大圖）。slug 用 build.py 的 pub_slug()。
  只轉 2020 年（含）以後、張老師是通訊作者的論文（build.py 的 has_schematic()；Jeff 2026-10-26 定通訊作者、
  2026-10-27 定 2020 年起），其他論文的原圖留著但跳過。
- research（研究主題圖，水彩粉彩畫風、滿版）：不裁白邊，產生 {theme}-xs.webp（480 寬、裁成 3:2，首頁主題卡片的縮圖）、
  {theme}-sm.webp（900 寬）與 {theme}.webp（1600 寬）；theme 是 content/research.yaml 裡主題的 id。
- background（全站背景，科技＋印象派畫風）：不裁，產生 static/img/bg/{name}-sm.webp（1200 寬）與 {name}.webp（2400 寬），
  name 是 hero（首頁主視覺）或 pagehead（內頁標題區；灰底區塊與頁尾也借用這兩張）。
3D 封面圖（cover）留在原圖資料夾、不轉（2026-10-26 Jeff：論文只放示意圖）。build.py 照同樣的檔名找圖，有檔才顯示。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from build import has_schematic, load_yaml, pub_slug  # noqa: E402

WIDTHS = {"schematic": {"-sm": 960, "": 1600}, "research": {"-xs": 480, "-sm": 900, "": 1600},
          "background": {"-sm": 1200, "": 2400}}
QUALITY = {"background": 80}   # 背景圖放大鋪滿、上面還疊遮罩，壓縮多一點看不出來
CROP_RATIO = {("research", "-xs"): 3 / 2}   # 這幾個尺寸先把原圖（4:3）從中間裁成指定的寬高比，再縮到指定寬度


def trim_white(img: Image.Image, pad: float = 0.025, threshold: int = 245) -> Image.Image:
    """裁掉幾乎全白的邊，四周留 2.5% 空白。"""
    bbox = img.convert("L").point(lambda v: 255 if v < threshold else 0).getbbox()
    if not bbox:
        return img
    px, py = int(img.width * pad), int(img.height * pad)
    left, top, right, bottom = bbox
    return img.crop((max(0, left - px), max(0, top - py), min(img.width, right + px), min(img.height, bottom + py)))


def crop_to_ratio(img: Image.Image, ratio: float) -> Image.Image:
    """從中間裁成寬:高＝ratio；原圖比較高就裁上下，比較寬就裁左右。"""
    w, h = img.size
    if w / h < ratio:
        nh = round(w / ratio)
        top = (h - nh) // 2
        return img.crop((0, top, w, top + nh))
    nw = round(h * ratio)
    left = (w - nw) // 2
    return img.crop((left, 0, left + nw, h))


def out_base(e: dict) -> Path:
    if e["kind"] == "schematic":
        return ROOT / "static" / "img" / "pubs" / f"{pub_slug(e['paper'])}-schematic"
    if e["kind"] == "background":
        return ROOT / "static" / "img" / "bg" / e["name"]
    return ROOT / "static" / "img" / "research" / e["theme"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--src", required=True, help="SciDraw 原圖資料夾（含 prompts.json）")
    args = ap.parse_args()
    src = Path(args.src)
    entries = json.load(open(src / "prompts.json", encoding="utf-8"))
    wanted = {p["doi"].lower(): has_schematic(p) for p in load_yaml("publications").get("items", [])}
    done: set[str] = set()
    for e in reversed(entries):   # 同一張圖重生過的話，以最後一次為準
        if e.get("kind") not in WIDTHS or e["file"] in done:
            continue
        done.add(e["file"])
        if e["kind"] == "schematic" and not wanted.get(e["paper"].lower(), True):
            print(f"跳過（不是 2020 年起的通訊作者論文）：{e['file']}")
            continue
        f = src / e["file"]
        if not f.exists():
            print(f"找不到原圖：{e['file']}")
            continue
        img = Image.open(f).convert("RGB")
        if e["kind"] == "schematic":
            img = trim_white(img)
        base = out_base(e)
        base.parent.mkdir(parents=True, exist_ok=True)
        for suffix, width in WIDTHS[e["kind"]].items():
            target = base.with_name(f"{base.name}{suffix}.webp")
            small = img.copy()
            if (e["kind"], suffix) in CROP_RATIO:
                small = crop_to_ratio(small, CROP_RATIO[(e["kind"], suffix)])
            small.thumbnail((width, width * 4), Image.LANCZOS)
            small.save(target, "WEBP", quality=QUALITY.get(e["kind"], 88), method=6)
            print(f"{target.parent.name}/{target.name}  {small.size[0]}×{small.size[1]}  {target.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
