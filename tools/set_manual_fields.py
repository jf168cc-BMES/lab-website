#!/usr/bin/env python3
"""在 content/publications.yaml 標精選與不列出（初版的暫定值，Jeff 可以改）。

用法：python tools/set_manual_fields.py
之後要改精選，直接編輯 publications.yaml 的 selected 欄位即可，不必再跑這支。
"""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "content" / "publications.yaml"

SELECTED = {  # 初版精選：最後作者是 Chang CW 的論文，涵蓋四個研究主題
    "10.1007/s13346-025-01927-4",
    "10.1016/j.bios.2023.115985",
    "10.1039/D0TB02713H",
    "10.1021/acsami.0c03446",
    "10.7150/thno.29326",
    "10.2147/IJN.S177851",
    "10.7150/ntno.19379",
}
EXCLUDE = {  # 撤稿聲明與被撤回的論文，預設不列出
    "10.18632/oncotarget.10823": "retraction notice",
    "10.18632/oncotarget.7942": "retracted article",
}
TITLE_OVERRIDE = {  # 來源資料把縮寫轉成小寫，這裡只改回縮寫
    "10.7150/ntno.19379": "Multifunctional PEGylated albumin/IR780/iron oxide nanocomplexes for cancer photothermal therapy and MR imaging",
}

text = TARGET.read_text(encoding="utf-8")
header = "".join(line + "\n" for line in text.splitlines() if line.startswith("#"))
data = yaml.safe_load(text)
sel = {d.lower() for d in SELECTED}
exc = {d.lower(): n for d, n in EXCLUDE.items()}
for item in data["items"]:
    doi = item["doi"].lower()
    if doi in sel:
        item["selected"] = True
    if doi in exc:
        item["exclude"] = True
        item["note"] = exc[doi]
    for key, value in TITLE_OVERRIDE.items():
        if doi == key.lower():
            item["title_override"] = value
TARGET.write_text(header + yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=1000), encoding="utf-8", newline="\n")
print("精選", sum(1 for i in data["items"] if i.get("selected")), "篇；不列出", sum(1 for i in data["items"] if i.get("exclude")), "篇")
