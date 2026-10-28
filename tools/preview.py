#!/usr/bin/env python3
"""在瀏覽器打開網站的本機預覽，直接用 docs/ 裡現有的網頁，不會重新產生。

用法：
    python tools/preview.py               開預覽並打開瀏覽器；Ctrl+C 結束
    python tools/preview.py --shortcut    在 Windows 桌面建「實驗室網站預覽」捷徑
捷徑用 pythonw 在背景跑、不開視窗，到登出或關機才停；預覽在跑時再雙擊，只會多開一個分頁。
內容改過要先跑 build.py，這裡看到的才會是新版。只有這台電腦連得到（綁 127.0.0.1）。
"""
from __future__ import annotations

import argparse
import datetime as dt
import functools
import http.server
import math
import mimetypes
import socket
import sys
import tempfile
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
ICON = Path(__file__).resolve().with_name("preview.ico")
SHORTCUT_NAME = "實驗室網站預覽.lnk"
LAB_MARK = "Nanomedicine &amp; Stem Cell Engineering Lab"   # 用來認出佔著 port 的是不是我們的網站
# 從捷徑用 pythonw 啟動時沒有視窗：訊息寫進暫存資料夾的 log，出錯改跳對話框
WINDOWLESS = Path(sys.executable).name.lower() == "pythonw.exe" or sys.stdout is None
LOG = Path(tempfile.gettempdir()) / "lab-website-preview.log"


# Windows 的 Python 常常不認得 .webp、.woff：回 application/octet-stream，手機版點圖直接開圖檔時瀏覽器會變成下載。這裡補上，預覽才跟 GitHub Pages 一樣
mimetypes.add_type("image/webp", ".webp")
mimetypes.add_type("font/woff", ".woff")
mimetypes.add_type("font/woff2", ".woff2")


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):   # 不逐筆記錄請求
        pass


class Server(http.server.ThreadingHTTPServer):
    allow_reuse_address = False   # Windows 上開了這個，兩個程式能綁同一個 port，請求會亂跑


def fail(msg: str) -> None:
    if WINDOWLESS and sys.platform == "win32":
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, msg, "實驗室網站預覽", 0x30)
    sys.exit(msg)


def port_busy(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0


def is_lab_site(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=3) as r:
            return LAB_MARK in r.read().decode("utf-8", "replace")
    except OSError:
        return False


def make_icon(path: Path) -> None:
    """照 static/img/favicon.svg 畫捷徑圖示（Pillow 不能直接讀 SVG）。"""
    from PIL import Image, ImageDraw

    size = 1024
    k = size / 32   # favicon 的座標是 32×32

    def box(cx: float, cy: float, r: float) -> list[float]:
        return [(cx - r) * k, (cy - r) * k, (cx + r) * k, (cy + r) * k]

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(img).ellipse(box(16, 16, 15), fill="#15305c")
    # 虛線圓環：半徑 10.5、線寬 1.2、虛線 1.6 間隔 3、白色半透明；Pillow 的線寬往內長，所以外框加半個線寬
    ring = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    r, w = 10.5, 1.2
    period, dash = 360 * 4.6 / (2 * math.pi * r), 360 * 1.6 / (2 * math.pi * r)
    a = 0.0
    while a < 360:
        ImageDraw.Draw(ring).arc(box(16, 16, r + w / 2), a, min(a + dash, 360),
                                 fill=(255, 255, 255, 128), width=round(w * k))
        a += period
    img = Image.alpha_composite(img, ring)
    draw = ImageDraw.Draw(img)
    draw.ellipse(box(16, 16, 5.6), fill="#f2b01e")
    draw.ellipse(box(24.6, 10.8, 2.2), fill="#ffffff")
    draw.ellipse(box(8.6, 22.4, 1.6), fill="#9ec5ff")
    img.resize((256, 256), Image.LANCZOS).save(path, sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])


def make_shortcut() -> Path:
    import win32com.client   # pywin32，只有建捷徑用得到

    make_icon(ICON)
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    shell = win32com.client.Dispatch("WScript.Shell")
    target = Path(shell.SpecialFolders("Desktop")) / SHORTCUT_NAME
    lnk = shell.CreateShortCut(str(target))
    lnk.TargetPath = str(pythonw if pythonw.exists() else Path(sys.executable))
    lnk.Arguments = f'"{Path(__file__).resolve()}"'
    lnk.WorkingDirectory = str(ROOT)
    lnk.IconLocation = str(ICON)
    lnk.Description = "在瀏覽器打開實驗室網站的本機預覽（背景執行，到登出或關機才停）"
    lnk.Save()
    return target


def main() -> None:
    if WINDOWLESS:
        sys.stdout = sys.stderr = open(LOG, "a", encoding="utf-8", buffering=1)
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", type=int, default=8790)
    ap.add_argument("--page", default="zh/", help="打開哪一頁，預設中文首頁")
    ap.add_argument("--no-open", action="store_true", help="不開瀏覽器（測試用）")
    ap.add_argument("--shortcut", action="store_true", help="在 Windows 桌面建捷徑")
    args = ap.parse_args()

    if args.shortcut:
        print(f"捷徑：{make_shortcut()}")
        return
    if not (DOCS / "index.html").exists():
        fail("docs/ 裡還沒有網頁，先跑 python build.py。")

    url = f"http://127.0.0.1:{args.port}/{args.page}"
    if port_busy(args.port):
        if not is_lab_site(args.port):
            fail(f"port {args.port} 被別的程式佔用，請加 --port 換一個號碼。")
        print(f"{dt.datetime.now():%Y-%m-%d %H:%M} 預覽已經在跑，直接打開：{url}", flush=True)
        if not args.no_open:
            webbrowser.open(url)
        return

    with Server(("127.0.0.1", args.port), functools.partial(QuietHandler, directory=str(DOCS))) as httpd:
        print(f"{dt.datetime.now():%Y-%m-%d %H:%M} 預覽中：{url}", flush=True)
        if not WINDOWLESS:
            print("按 Ctrl+C 結束。", flush=True)
        if not args.no_open:
            webbrowser.open(url)   # port 已經綁好，瀏覽器的請求會排隊等下一行開始處理
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
