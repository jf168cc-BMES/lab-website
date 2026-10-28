#!/usr/bin/env python3
"""中文字型子集：把 Noto Sans TC 可變字型縮成「只含中文頁實際用到的字」，放在 static/fonts/。

build.py 每次產生網頁後會呼叫 update()：
- 找得到原字型（Windows 的 C:\\Windows\\Fonts\\NotoSansTC-VF.ttf，或用環境變數 NOTO_SANS_TC_VF 指定檔案）：
  比對中文頁用到的字和目前的子集，有差就重做子集；build.py 接著會再產生一次網頁（網頁裡的字型網址帶檔案版本號）。
- 找不到原字型：沿用 repo 裡已有的子集，並列出子集裡沒有的字（那些字會改用系統字型顯示，版面不會壞）。

只留 wght 400–700（網站用 400／500／700），輸出 WOFF（沒裝 brotli 做不了 WOFF2）。
Latin 字母與數字由 Inter 負責（style.css 中文頁的字型順序），所以子集不放 ASCII。
授權：Noto Sans TC 是 SIL OFL 1.1；版權與授權說明保留在字型檔的 name 表（ID 0、13、14）。

單獨檢查（用 docs/zh/ 現有的網頁，不重新產生網頁）：
    python tools/font_subset.py            有差異就重做子集
    python tools/font_subset.py --check    只報告，不改檔案
"""
from __future__ import annotations

import argparse
import html
import os
import re
import sys
import unicodedata
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent.parent
FONT_NAME = "NotoSansTC-subset.woff"
TARGET = ROOT / "static" / "fonts" / FONT_NAME
SOURCE_CANDIDATES = [
    os.environ.get("NOTO_SANS_TC_VF", ""),
    "C:/Windows/Fonts/NotoSansTC-VF.ttf",
    str(Path.home() / "AppData/Local/Microsoft/Windows/Fonts/NotoSansTC-VF.ttf"),
    str(Path.home() / "Library/Fonts/NotoSansTC-VF.ttf"),
    "/Library/Fonts/NotoSansTC-VF.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansTC-VF.ttf",
]
KEEP_FEATURES = ["ccmp", "locl", "kern", "mark", "liga"]   # 橫排用得到的；直排、全半形切換等功能不留
KEEP_NAME_IDS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 13, 14]   # 含版權（0）與 OFL 授權說明（13、14）


def find_source() -> Path | None:
    for c in SOURCE_CANDIDATES:
        if c and Path(c).is_file():
            return Path(c)
    return None


def chars_in(pages: Iterable[str]) -> set[str]:
    """網頁（HTML 字串）裡用到的非 ASCII 字：拿掉 script、style、註解，空白與控制字元不算。"""
    out: set[str] = set()
    for page in pages:
        text = html.unescape(re.sub(r"<(script|style)\b.*?</\1>|<!--.*?-->", "", page, flags=re.S))
        out.update(c for c in text if ord(c) > 0x7E and unicodedata.category(c)[0] not in "CZ")
    return out


def cmap_of(path: Path) -> set[str]:
    """字型檔收了哪些字（不含 ASCII）。需要 fontTools。"""
    from fontTools.ttLib import TTFont
    with TTFont(path, lazy=True) as f:
        return {chr(cp) for cp in f.getBestCmap() if cp > 0x7E}


def build_subset(source: Path, chars: set[str], target: Path) -> None:
    from fontTools import subset
    from fontTools.ttLib import TTFont, sfnt
    from fontTools.varLib import instancer

    font = TTFont(source)
    opt = subset.Options()
    opt.layout_features = KEEP_FEATURES
    opt.name_IDs = KEEP_NAME_IDS
    opt.hinting = False
    opt.glyph_names = False
    opt.notdef_outline = True
    opt.drop_tables += ["vhea", "vmtx", "VORG"]   # 直排用，網頁用不到
    sub = subset.Subsetter(opt)
    sub.populate(text="".join(sorted(chars)))
    sub.subset(font)
    # 原字型 wght 100–900（預設值 100）；縮成 400–700、預設 400，檔案小一點
    font = instancer.instantiateVariableFont(font, {"wght": (400, 400, 700)}, inplace=True)
    sfnt.ZLIB_COMPRESSION_LEVEL = 9
    font.flavor = "woff"
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    font.save(tmp)
    tmp.replace(target)


def update(zh_pages: list[str], check_only: bool = False, verbose: bool = False) -> bool:
    """比對中文頁用到的字與 static/fonts/ 的子集。回傳 True＝字型檔剛被改寫（呼叫端要重新產生網頁）。
    verbose：一切正常時也印一行狀態（單獨執行時用，build.py 呼叫時一切正常就不吵）。"""
    if not zh_pages:
        return False
    try:
        import fontTools  # noqa: F401
    except ImportError:
        print("⚠️ 沒裝 fontTools（pip install -r requirements.txt），無法檢查或更新中文字型子集。")
        return False
    need = chars_in(zh_pages)
    have = cmap_of(TARGET) if TARGET.is_file() else None
    source = find_source()
    if source is not None:
        from fontTools.ttLib import TTFont
        with TTFont(source, lazy=True) as f:
            in_font = {chr(cp) for cp in f.getBestCmap()}
        want = need & in_font
        absent = need - in_font
        if absent:
            print(f"ℹ️ 原字型也沒有這 {len(absent)} 個字，會用系統字型顯示：{''.join(sorted(absent))}")
        if have == want:
            if verbose:
                print(f"✓ 中文字型子集與中文頁用到的字一致：{len(want)} 字，{TARGET.stat().st_size / 1024:.0f} KB。")
            return False
        added = want - (have or set())
        if check_only:
            print(f"字型子集需要更新：新增 {len(added)} 字、移除 {len((have or set()) - want)} 字。")
            return False
        build_subset(source, want, TARGET)
        note = f"（新增 {len(added)} 字：{''.join(sorted(added))[:60]}）" if have is not None and added else ""
        print(f"🔤 中文字型子集已更新：{len(want)} 字，{TARGET.stat().st_size / 1024:.0f} KB {note}")
        return True
    # 沒有原字型：沿用 repo 裡的子集，列出缺的字
    if have is None:
        print(f"⚠️ 找不到原字型（NotoSansTC-VF.ttf）也沒有 {TARGET.relative_to(ROOT).as_posix()}，中文頁會改用系統字型。")
        return False
    missing = need - have
    if missing:
        print(f"⚠️ 找不到原字型（NotoSansTC-VF.ttf），沿用現有字型子集；下列 {len(missing)} 個字不在子集裡，"
              f"會改用系統字型顯示：{''.join(sorted(missing))}")
        print("   到有 Noto Sans TC 可變字型的電腦重跑 build.py，子集就會補上這些字。")
    elif verbose:
        print(f"✓ 中文字型子集涵蓋中文頁用到的全部字（{len(have)} 字）；這台電腦沒有原字型，不更新。")
    return False


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="只報告，不改檔案")
    args = ap.parse_args()
    pages = [p.read_text(encoding="utf-8") for p in sorted((ROOT / "docs" / "zh").rglob("*.html"))]
    if not pages:
        sys.exit("docs/zh/ 裡還沒有網頁，先跑 python build.py。")
    if update(pages, check_only=args.check, verbose=True):
        print("字型檔已改寫，請再跑一次 python build.py，網頁裡的字型網址才會帶上新的版本號。")


if __name__ == "__main__":
    main()
