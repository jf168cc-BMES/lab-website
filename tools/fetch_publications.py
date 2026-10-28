#!/usr/bin/env python3
"""從 ORCID 抓論文清單、從 Crossref 補作者與卷期頁，寫成 content/publications.yaml。

用法：python tools/fetch_publications.py（會連 ORCID 與 Crossref、改寫 publications.yaml；--help 只印說明）
重抓時會保留既有檔案裡的手動欄位：selected（精選）、exclude（不列出）、theme、note、title_override、
corresponding（通訊作者標記；預設是 Chang CW 為最後一位作者時標）、co_corresponding（其他共同通訊作者）、
bib_fix（手動更正的書目，例 {volume: '10', pages: 463-473}；Crossref 不完整或寫錯時用，重抓一律以它為準）。
Crossref 缺卷期頁時，也會沿用既有檔案裡手補的值；但 Crossref 有值（就算不完整，例如只有起始頁）就會蓋掉，要保留請寫進 bib_fix。
只送出公開的 ORCID 編號與 DOI，不帶任何個人資料。
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

ORCID = "0000-0002-0701-876X"
ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "content" / "publications.yaml"
UA = "lab-website-publications/1.0 (static site build)"
MANUAL_FIELDS = ("selected", "exclude", "theme", "note", "title_override", "corresponding", "co_corresponding",
                 "bib_fix")


def get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def orcid_works() -> list[dict]:
    data = get_json(f"https://pub.orcid.org/v3.0/{ORCID}/works")
    works = []
    for group in data.get("group", []):
        s = group["work-summary"][0]
        doi = next((e.get("external-id-value", "") for e in (s.get("external-ids") or {}).get("external-id", [])
                    if e.get("external-id-type") == "doi"), "")
        if not doi:
            continue
        works.append({
            "doi": doi.strip(),
            "year": int(((s.get("publication-date") or {}).get("year") or {}).get("value") or 0),
            "title": ((s.get("title") or {}).get("title") or {}).get("value", ""),
            "journal": ((s.get("journal-title") or {}) or {}).get("value", "") if s.get("journal-title") else "",
            "type": s.get("type", ""),
        })
    return works


def short_author(a: dict) -> str:
    family = (a.get("family") or "").strip()
    given = (a.get("given") or "").replace("‐", "-").replace("‑", "-").strip()
    if not family:
        return (a.get("name") or "").strip()
    if family.isupper():  # 有些期刊整個姓名大寫，例如 CHANG
        family = "-".join(part.capitalize() for part in family.split("-"))
    initials = "".join(part[0].upper() for chunk in given.split() for part in chunk.split("-") if part)
    return f"{family} {initials}".strip()


def crossref(doi: str) -> dict:
    try:
        msg = get_json("https://api.crossref.org/works/" + urllib.parse.quote(doi))["message"]
    except Exception as exc:  # 抓不到就只用 ORCID 的資料
        print(f"  Crossref 失敗 {doi}: {exc}")
        return {}
    out = {
        "authors": [short_author(a) for a in msg.get("author", [])],
        "volume": msg.get("volume", ""),
        "issue": msg.get("issue", ""),
        "pages": msg.get("page", "") or msg.get("article-number", ""),
    }
    if msg.get("container-title"):
        out["journal_cr"] = msg["container-title"][0]
    return out


def merge_manual(item: dict, old: dict) -> dict:
    """把舊檔裡的手動欄位與手補的書目接回重抓的 item。"""
    for field in MANUAL_FIELDS:
        if field in old:
            item[field] = old[field]
    for field in ("volume", "issue", "pages"):   # Crossref 缺卷期頁時，沿用 publications.yaml 裡手補的值
        if not item.get(field) and old.get(field):
            item[field] = old[field]
    for field, value in (old.get("bib_fix") or {}).items():   # 手動更正：Crossref 不完整或寫錯時，一律以這裡為準
        item[field] = value
    return item


def main() -> None:
    argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
    existing = {}
    if TARGET.exists():
        old = yaml.safe_load(TARGET.read_text(encoding="utf-8")) or {}
        existing = {p["doi"].lower(): p for p in old.get("items", [])}
    items = []
    works = orcid_works()
    print(f"ORCID 作品 {len(works)} 筆（有 DOI）")
    for i, w in enumerate(works, 1):
        cr = crossref(w["doi"])
        volume = re.sub(r"^volume\s+", "", str(cr.get("volume", "")).strip(), flags=re.I)
        if volume == str(w["year"]):  # 例：Chem. Commun. 用年份當卷號，重複就不顯示
            volume = ""
        cr["volume"] = volume
        item = {
            "doi": w["doi"],
            "year": w["year"],
            "title": w["title"],
            "journal": w["journal"] or cr.get("journal_cr", ""),
            "volume": cr.get("volume", ""),
            "issue": cr.get("issue", ""),
            "pages": cr.get("pages", ""),
            "authors": cr.get("authors", []),
            "type": w["type"],
        }
        items.append(merge_manual(item, existing.get(w["doi"].lower(), {})))
        if i % 10 == 0:
            print(f"  已處理 {i}/{len(works)}")
        time.sleep(0.4)
    seen = {p["doi"].lower() for p in items}
    for p in existing.values():   # 手動補的論文（manual: true）：ORCID 還沒有就照留，ORCID 有了就以 ORCID 為準
        if p.get("manual") and p["doi"].lower() not in seen:
            items.append(p)
    items.sort(key=lambda p: (-p["year"], p["title"].lower()))
    header = (f"# 由 tools/fetch_publications.py 產生（ORCID {ORCID} ＋ Crossref），{dt.date.today().isoformat()}。\n"
              "# 手動欄位 selected／exclude／theme／note／title_override／corresponding／co_corresponding／bib_fix 重抓時會保留；"
              "其他欄位會被覆寫（Crossref 缺卷期頁時沿用手補的值；Crossref 不完整或寫錯的書目寫進 bib_fix，重抓一律以它為準）。\n"
              "# corresponding：Chang CW 是最後一位作者時預設標通訊作者（底線＋*）；false 排除、true 加上。"
              "co_corresponding：其他共同通訊作者，名字後面也打 *。精選預設＝通訊作者論文。\n"
              "# manual: true＝ORCID 還沒有、手動補的論文（資料取自 Crossref），重抓時照留。\n")
    body = yaml.safe_dump({"orcid": ORCID, "fetched": dt.date.today().isoformat(), "items": items},
                          allow_unicode=True, sort_keys=False, width=1000)
    TARGET.write_text(header + body, encoding="utf-8", newline="\n")
    print(f"寫入 {TARGET}（{len(items)} 筆）")


if __name__ == "__main__":
    main()
