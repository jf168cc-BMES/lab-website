#!/usr/bin/env python3
"""實驗室網站產生器。

content/*.yaml（中英內容）＋ templates/（版型）＋ static/（樣式、圖片）→ docs/
GitHub Pages 設定成從 main 分支的 /docs 發布。

用法：
    python build.py            產生 docs/
    python build.py --check    產生後檢查站內連結
    python build.py --serve    產生後開本機預覽 http://127.0.0.1:8790

內容裡寫 [待確認：...] 或 [TBC: ...] 的地方，網頁上會標黃，產生時也會列出清單。
"""
from __future__ import annotations

import argparse
import datetime as dt
import functools
import hashlib
import html
import http.server
import mimetypes
import re
import shutil
import sys
import urllib.parse
from html.parser import HTMLParser
from pathlib import Path

import jinja2
import markdown as md
import yaml
from markupsafe import Markup, escape
from PIL import Image

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tools"))   # 用路徑載入 font_subset：不靠 `tools` 這個套件名（site-packages 裡若有同名套件會蓋過去）
import font_subset  # noqa: E402

CONTENT = ROOT / "content"
TEMPLATES = ROOT / "templates"
STATIC = ROOT / "static"
OUT = ROOT / "docs"
LANGS = ("en", "zh")
TBC_RE = re.compile(r"\[(?:待確認|TBC)[:：]\s*([^\]]*)\]")
ALLOWED_TITLE_TAGS = re.compile(r"&lt;(/?)(sup|sub|i|em)&gt;")
MD_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")

# (語言, 頁面代號, 輸出路徑, 模板, 內容檔)
PAGES = [
    ("en", "home", "index.html", "home.html", "home"),
    ("en", "research", "research/index.html", "research.html", "research"),
    ("en", "people", "people/index.html", "people.html", "people"),
    ("en", "publications", "publications/index.html", "publications.html", "pubpage"),
    ("en", "news", "news/index.html", "news.html", "news"),
    ("en", "join", "join-us/index.html", "join_international.html", "join_international"),
    ("en", "contact", "contact/index.html", "contact.html", "contact"),
    ("zh", "home", "zh/index.html", "home.html", "home"),
    ("zh", "research", "zh/research/index.html", "research.html", "research"),
    ("zh", "people", "zh/people/index.html", "people.html", "people"),
    ("zh", "publications", "zh/publications/index.html", "publications.html", "pubpage"),
    ("zh", "news", "zh/news/index.html", "news.html", "news"),
    ("zh", "join", "zh/join/index.html", "join_domestic.html", "join_domestic"),
    ("zh", "contact", "zh/contact/index.html", "contact.html", "contact"),
]
PATHS = {(lang, key): out for lang, key, out, _, _ in PAGES}

TBC_FOUND: list[tuple[str, str]] = []
MISSING: list[tuple[str, str]] = []


def load_yaml(name: str) -> dict:
    with open(CONTENT / f"{name}.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def pub_slug(doi: str) -> str:
    """論文插圖檔名用：DOI 轉小寫、非英數字換成「-」。tools/pub_images.py 用同一個函式。"""
    return re.sub(r"[^a-z0-9]+", "-", doi.lower()).strip("-")


def is_corresponding(pub: dict) -> bool:
    """張老師是不是通訊作者：排最後一位就算，publications.yaml 的 corresponding: false／true 可以個別改
    （Sci Rep 2015 設 false）。作者列的 *、精選論文的預設都照這個判斷；示意圖另外看年份（has_schematic）。"""
    names = [str(n).lower() for n in (pub.get("authors") or [])]
    return pub.get("corresponding", bool(names) and names[-1] == "chang cw")


SCHEMATIC_FROM_YEAR = 2020   # Jeff 2026-10-27：「2020 以後的 selected papers 才放示意圖」


def has_schematic(pub: dict) -> bool:
    """這篇要不要放示意圖：通訊作者論文、而且是 2020 年（含）以後的。更早的精選論文卡片只列書目。
    tools/pub_images.py 用同一個判斷決定要不要轉圖。"""
    return is_corresponding(pub) and int(pub.get("year") or 0) >= SCHEMATIC_FROM_YEAR


@functools.lru_cache(maxsize=None)
def asset_version(rel: str) -> str:
    """docs/ 裡靜態檔的版本號（內容雜湊前 8 碼），接在網址後面（?v=）：檔案一改網址就變，
    瀏覽器不會繼續用快取裡的舊圖、舊樣式（本機預覽與 GitHub Pages 都沒送「不要快取」的標頭）。"""
    f = OUT / rel
    return hashlib.sha1(f.read_bytes()).hexdigest()[:8] if f.is_file() else ""


def version_css_urls() -> None:
    """docs/ 裡的 CSS：背景圖等 url(../...) 也接上版本號；CSS 自己的版本號之後照改過的內容算。"""
    for css in (OUT / "static" / "css").glob("*.css"):
        def add(m: re.Match) -> str:
            rel = (css.parent / m.group(2)).resolve().relative_to(OUT.resolve()).as_posix()
            v = asset_version(rel)
            return f"url({m.group(1)}{m.group(2)}?v={v}{m.group(1)})" if v else m.group(0)
        text = css.read_text(encoding="utf-8")
        css.write_text(re.sub(r"url\(([\"']?)(\.\./[^\"')?#]+)\1\)", add, text), encoding="utf-8", newline="\n")


def page_href(lang: str, key: str) -> str:
    out = PATHS[(lang, key)]
    return out[: -len("index.html")] if out.endswith("index.html") else out


def make_env(lang: str, out_path: str, abs_base: str = "") -> jinja2.Environment:
    """每一頁一個環境：翻譯、相對網址都跟著這一頁走。
    abs_base 有填（只有 404 頁用）就全部改成完整網址：GitHub Pages 在任何不存在的網址（含多層路徑）都回 404.html，
    相對網址那時會指到不存在的資料夾，整頁沒有樣式。"""
    depth = out_path.count("/")
    prefix = "../" * depth
    page_id = f"{lang}:{out_path}"

    def tr(value):
        if isinstance(value, dict) and set(value) & set(LANGS):
            v = value.get(lang)
            if v in (None, ""):
                other = value.get("zh" if lang == "en" else "en")
                if other not in (None, ""):
                    MISSING.append((page_id, str(other)[:60]))
                return other or ""
            return v
        return value if value is not None else ""

    def note_tbc(text: str) -> None:
        for m in TBC_RE.finditer(text):
            TBC_FOUND.append((page_id, m.group(1).strip()))

    def wrap_tbc(escaped: str) -> str:
        escaped = escaped.replace("{wbr}", "<wbr>")  # 指定斷行點，例如中文實驗室名稱
        return TBC_RE.sub(lambda m: f'<mark class="tbc" title="待確認">{m.group(1).strip()}</mark>', escaped)

    def f_tx(value) -> Markup:
        text = str(tr(value))
        note_tbc(text)
        return Markup(wrap_tbc(str(escape(text))))

    def f_md(value) -> Markup:
        text = str(tr(value))
        note_tbc(text)
        rendered = md.markdown(text, extensions=["extra", "sane_lists"])
        return Markup(wrap_tbc(rendered))

    def f_mdi(value) -> Markup:
        """行內 markdown：不包 <p>。"""
        rendered = str(f_md(value))
        if rendered.startswith("<p>") and rendered.endswith("</p>") and rendered.count("<p>") == 1:
            rendered = rendered[3:-4]
        return Markup(rendered)

    def f_plain(value) -> str:
        """給 meta 描述、alt 用的純文字：拿掉待確認標記、markdown 連結與粗體。"""
        text = str(tr(value)).replace("{wbr}", "")
        text = TBC_RE.sub("", text)
        text = MD_LINK_RE.sub(r"\1", text).replace("**", "")
        return re.sub(r"\s{2,}", " ", text).replace(" .", ".").replace(" ,", ",").strip()

    def f_title(value) -> Markup:
        safe = str(escape(str(value)))
        return Markup(ALLOWED_TITLE_TAGS.sub(lambda m: f"<{m.group(1)}{m.group(2)}>", safe))

    def f_authors(pub: dict) -> Markup:
        """PI 一律粗體加底線；PI 是最後一位作者時名字後面再加 *（通訊作者，Jeff 2026-10-26），
        publications.yaml 的 corresponding: false／true 可以個別排除或加上 *；
        co_corresponding 列的其他共同通訊作者也打 *（例如 Lo JM）。作者一律全部列出，不截斷（Jeff 2026-10-26）。"""
        names = [str(n) for n in (pub.get("authors") or [])]
        lower = [n.lower() for n in names]
        pi = lower.index("chang cw") if "chang cw" in lower else -1
        corr = is_corresponding(pub)
        co = {str(n).lower() for n in (pub.get("co_corresponding") or [])}

        def one(i: int) -> str:
            n = str(escape(names[i]))
            if i != pi:
                return f"{n}*" if lower[i] in co else n
            return f'<strong class="corr"><u>{n}</u>*</strong>' if corr else f"<strong><u>{n}</u></strong>"

        return Markup(", ".join(one(i) for i in range(len(names))))

    def url(target: str = "") -> str:
        if target.startswith(("http://", "https://", "mailto:", "tel:", "#")):
            return target
        v = asset_version(target) if target.startswith("static/") else ""
        if abs_base:
            return f"{abs_base}/{target}" + (f"?v={v}" if v else "")
        if v:
            return f"{prefix}{target}?v={v}"
        return (prefix + target) or "./"

    def mailto(address: str, subject: str = "") -> str:
        """寄信連結；主旨整段做百分比編碼（空格要 %20，不能用 +）。"""
        return f"mailto:{address}" + (f"?subject={urllib.parse.quote(str(subject), safe='')}" if subject else "")

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(TEMPLATES),
        autoescape=jinja2.select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters.update(t=tr, tx=f_tx, md=f_md, mdi=f_mdi, plain=f_plain, ptitle=f_title, authors=f_authors)
    env.globals.update(url=url, href=lambda key, l=lang: url(page_href(l, key)), mailto=mailto)
    return env


def fmt_date(value: str, lang: str) -> str:
    """'2026-02' → 'Feb 2026'／'2026 年 2 月'；'2025' → '2025'。"""
    parts = str(value).split("-")
    year = parts[0]
    if len(parts) == 1:
        return year
    month = int(parts[1])
    if lang == "zh":
        return f"{year} 年 {month} 月"
    return dt.date(int(year), month, 1).strftime("%b %Y")


def build_site() -> list[str]:
    """產生整個 docs/，回傳中文頁的 HTML（build() 用它檢查中文字型子集夠不夠）。"""
    MISSING.clear()
    TBC_FOUND.clear()
    site = load_yaml("site")
    research = load_yaml("research")
    people = load_yaml("people")
    news = load_yaml("news")
    pubs = load_yaml("publications")
    base_url = (site.get("base_url") or "").rstrip("/")
    updated = str(site.get("updated") or "")   # 頁尾與招生頁顯示的「最後更新」：content/site.yaml 的 updated，手動改
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", updated):
        print(f"⚠️ content/site.yaml 的 updated 沒填或格式不是 YYYY-MM-DD（目前：{updated!r}），暫用今天的日期。")
        updated = dt.date.today().isoformat()
    zh_font = (STATIC / "fonts" / font_subset.FONT_NAME).exists()   # 有字型檔，中文頁才預先載入

    items = [p for p in pubs.get("items", []) if not p.get("exclude")]
    for p in items:   # SciDraw 示意圖：static/img/pubs/{slug}-schematic[-sm].webp，有檔才放進精選論文卡片
        slug = pub_slug(p["doi"])   # 只放 2020 年起通訊作者論文的圖（has_schematic），其他的檔案在也不顯示
        p["slug"] = slug
        p["images"] = []
        for k in ("schematic",):
            sm = STATIC / "img" / "pubs" / f"{slug}-{k}-sm.webp"
            if sm.exists() and has_schematic(p):
                with Image.open(sm) as im:   # 寬高寫進 <img>，圖還沒載入時版面不會跳
                    w, h = im.size
                p["images"].append({"kind": k, "sm": f"static/img/pubs/{slug}-{k}-sm.webp",
                                    "lg": f"static/img/pubs/{slug}-{k}.webp", "w": w, "h": h})
    by_doi = {p["doi"].lower(): p for p in items}
    theme_images = {}   # 研究主題圖：static/img/research/{主題 id}[-xs／-sm].webp，有檔才取代主題的小圖示
    for th in research.get("themes", []):
        sm = STATIC / "img" / "research" / f"{th['id']}-sm.webp"
        if sm.exists():
            with Image.open(sm) as im:
                w, h = im.size
            entry = {"sm": f"static/img/research/{th['id']}-sm.webp",
                     "lg": f"static/img/research/{th['id']}.webp", "w": w, "h": h}
            xs = STATIC / "img" / "research" / f"{th['id']}-xs.webp"   # 首頁卡片用的 3:2 縮圖（480 寬）
            if xs.exists():
                with Image.open(xs) as im:
                    entry.update(xs=f"static/img/research/{th['id']}-xs.webp", xs_w=im.size[0], xs_h=im.size[1])
            theme_images[th["id"]] = entry
    pub_all = sorted(items, key=lambda p: int(p["year"]), reverse=True)   # 新到舊，不分年份段落；同年維持 publications.yaml 的順序
    selected = [p for p in items if p.get("selected", is_corresponding(p))]   # 精選＝通訊作者論文（Jeff 2026-10-26），selected 可個別改
    teaser_pubs = sorted(selected, key=lambda p: int(p["year"]), reverse=True)[:3]   # 首頁「精選論文」只放最新 3 篇
    news_items = sorted(news.get("items", []), key=lambda n: str(n["date"]), reverse=True)

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    shutil.copytree(STATIC, OUT / "static")
    asset_version.cache_clear()
    version_css_urls()

    zh_pages: list[str] = []
    for lang, key, out_path, template, content_name in PAGES:
        env = make_env(lang, out_path)
        other = "zh" if lang == "en" else "en"
        content = load_yaml(content_name)
        ctx = dict(
            site=site,
            lang=lang,
            other_lang=other,
            key=key,
            page=content,
            research=research,
            people=people,
            news_items=[dict(n, date_label=fmt_date(n["date"], lang)) for n in news_items],
            pub_all=pub_all,
            selected_pubs=selected,
            teaser_pubs=teaser_pubs,
            pub_by_doi=by_doi,
            theme_images=theme_images,
            updated=updated,
            zh_font=zh_font,
            alt_href=env.globals["url"](page_href(other, key)),
            out_path=out_path,
            base_url=base_url,
            page_href=page_href,
        )
        html_text = env.get_template(template).render(**ctx)
        if lang == "zh":
            zh_pages.append(html_text)
        target = OUT / out_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html_text, encoding="utf-8", newline="\n")

    env = make_env("en", "404.html", abs_base=base_url)   # 404 頁有填 base_url 就用完整網址（見 make_env）
    (OUT / "404.html").write_text(
        env.get_template("404.html").render(site=site, lang="en", other_lang="zh", key="404", page={},
                                            updated=updated, zh_font=zh_font,
                                            alt_href=env.globals["url"]("zh/"), out_path="404.html",
                                            base_url=base_url, page_href=page_href),
        encoding="utf-8")

    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    if site.get("custom_domain"):
        (OUT / "CNAME").write_text(site["custom_domain"].strip() + "\n", encoding="utf-8")
    if site.get("noindex") or not base_url:
        (OUT / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
    else:
        urls = "\n".join(f"  <url><loc>{base_url}/{page_href(l, k)}</loc></url>" for l, k, *_ in PAGES)
        (OUT / "sitemap.xml").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + urls + "\n</urlset>\n",
            encoding="utf-8")
        (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {base_url}/sitemap.xml\n", encoding="utf-8")
    return zh_pages


def build() -> None:
    zh_pages = build_site()
    if font_subset.update(zh_pages):   # 中文字型子集剛重做：網頁裡字型檔的版本號要跟著換，所以再產生一次
        build_site()
    print(f"產生 {len(PAGES) + 1} 頁 → {OUT}")
    if MISSING:
        print(f"⚠️ {len(MISSING)} 處缺另一種語言，暫用另一語言顯示：")
        for page_id, text in MISSING:
            print(f"   {page_id}｜{text}")
    unique = sorted(set(TBC_FOUND))
    if unique:
        print(f"🟡 待確認 {len(unique)} 處（網頁上標黃）：")
        for page_id, text in unique:
            print(f"   {page_id}｜{text}")


class LinkCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name in ("href", "src") and value:
                self.links.append(value)


def check_links() -> int:
    broken = []
    for page in OUT.rglob("*.html"):
        parser = LinkCollector()
        parser.feed(page.read_text(encoding="utf-8"))
        for link in parser.links:
            if link.startswith(("http://", "https://", "mailto:", "tel:", "#", "data:")):
                continue
            path = link.split("#")[0].split("?")[0]
            if not path:
                continue
            target = (page.parent / html.unescape(path)).resolve()
            if path.endswith("/") or target.is_dir():
                target = target / "index.html"
            if not target.exists():
                broken.append((page.relative_to(OUT).as_posix(), link))
    if broken:
        print(f"❌ 站內連結壞掉 {len(broken)} 個：")
        for page, link in broken:
            print(f"   {page} → {link}")
    else:
        print("✅ 站內連結全部有效")
    return len(broken)


def serve(port: int) -> None:
    mimetypes.add_type("image/webp", ".webp")   # Windows 的 Python 常不認得這兩種，會回 octet-stream，預覽時點圖變成下載
    mimetypes.add_type("font/woff", ".woff")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(OUT))
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), handler) as httpd:
        print(f"預覽：http://127.0.0.1:{port}/（Ctrl+C 結束）")
        httpd.serve_forever()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="產生後檢查站內連結")
    ap.add_argument("--serve", action="store_true", help="產生後開本機預覽")
    ap.add_argument("--port", type=int, default=8790)
    args = ap.parse_args()
    build()
    bad = check_links() if args.check or args.serve else 0
    if args.serve:
        serve(args.port)
    sys.exit(1 if bad else 0)
