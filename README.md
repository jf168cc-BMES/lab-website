# 奈米醫藥與幹細胞工程實驗室網站

張建文老師實驗室（清大醫環系）的中英雙語網站。靜態網站：`content/` 的文字檔 ＋ `templates/` 的版型 → `docs/` 的網頁，GitHub Pages 從 `docs/` 發布。

原始碼靠 GitHub 在不同電腦之間同步，不要放進雲端同步資料夾（git 在同步夾裡容易壞掉）。

## 資料夾

| 位置 | 放什麼 |
| :--- | :--- |
| `content/site.yaml` | 網站名稱、聯絡方式（含 `phone_tel`，手機點電話直接撥號用）、選單、頁尾連結（`links.nthu`、`links.department`）、**`updated`（最後更新日期）**、網址設定（`custom_domain`、`base_url`、`noindex`） |
| `content/home.yaml` | 首頁（含「精選論文」「認識張老師」兩小段的標題與文字） |
| `content/research.yaml` | 研究主題（每個主題的圖見下面「研究主題圖」）、實驗室技術 |
| `content/pi.yaml` | 主持人頁：簡介、學經歷、獲獎（首頁「認識張老師」的照片也取自這裡） |
| `content/people.yaml` | 成員頁：現任成員（`members`）、各組畢業成員與交換生（`alumni_groups`）；兩者空的時候整段不顯示 |
| `content/news.yaml` | 消息 |
| `content/publications.yaml` | 論文清單，**由程式產生**，只手改 `selected`／`exclude`／`note`／`corresponding`／`co_corresponding`（其他共同通訊作者，名字後面也打 *）／`bib_fix`；Crossref 的卷期頁或作者不完整、寫錯時，把正確的值寫進那篇的 `bib_fix`（例：`bib_fix: {volume: '10', pages: 463-473}`），重抓一律以它為準（直接改 `volume`、`pages` 只有在 Crossref 那欄是空的時候會被沿用，Crossref 只給起始頁之類的不完整值會蓋掉）；ORCID 還沒有的論文可以手動補一筆，加上 `manual: true`（重抓時會保留） |
| `content/join_international.yaml` | 英文國際生招生頁 |
| `content/join_domestic.yaml` | 中文國內招生頁 |
| `content/contact.yaml`、`pubpage.yaml` | 聯絡頁、論文頁的文字 |
| `templates/` | 版型（Jinja2） |
| `static/` | 樣式、程式、圖片、字型（`static/fonts/` 是中文字型子集，見下面） |
| `tools/` | 抓論文、做圖、做字型子集、本機預覽的小程式 |
| `docs/` | 產生出來的網站，**不要手改**，每次 `build.py` 會整個重做 |

中英文寫在同一個欄位：`{en: "...", zh: "..."}`。只寫一種語言時，另一種會暫用這個語言顯示，產生時會列出來。

## 常見修改

- **加一則消息**：在 `content/news.yaml` 的 `items` 加一筆 `date`（`YYYY` 或 `YYYY-MM`）、`title`、`text`，可加 `doi` 或 `link`。順序不用管，會自動排。
- **新增成員**：成員本人同意後，在 `content/people.yaml` 的 `members` 加 `name`、`role`、`topic`（選填）和 `photo`（照片放 `static/img/people/`，4:5、480×600 以內、不帶 EXIF）；沒有照片的人改寫 `initials`（姓名縮寫頭像）。成員離開就把那筆移到 `alumni_groups` 對應的組別（`now` 寫現況，沒有就省略）。同意書不要放進這個資料夾。
- **更新論文**：`python tools/fetch_publications.py`（從 ORCID 0000-0002-0701-876X 重抓，保留手動欄位）。精選自動是張老師為通訊作者的論文；要個別排除寫 `selected: false`，要加進別篇寫 `selected: true`。
- **改國際生頁的金額或日期**：`content/join_international.yaml`，每學期對官方頁核對一次。
- **「最後更新」日期**：頁尾與英文招生頁顯示的日期是 `content/site.yaml` 的 `updated`（`YYYY-MM-DD`），**不再自動用產生網站的日期**；改了網站內容後手動改這個日期。
- **寄信按鈕**：「寄信給張老師」按鈕（兩個招生頁的標題區、聯絡頁）的按鈕文字在 `site.yaml` 的 `email_button`；英文招生頁與中文招生頁的主旨分別是 `join_international.yaml` 的 `apply.mail_subject`、`join_domestic.yaml` 的 `contact.mail_subject`（聯絡頁的按鈕不帶主旨）。
- **頁尾連結**：「國立清華大學」「系所」連結在 `site.yaml` 的 `links.nthu`、`links.department`（系所的中英文各一個網址，都是醫環系網站首頁，用 `?Lang=en`、`?Lang=zh-tw` 切語言）。
- **待確認的內容**：在文字裡寫 `[待確認：…]` 或 `[TBC: …]`，網頁上會標黃，產生時會列出清單。上線前要清到 0。
- **精選論文與示意圖**：精選論文＝張老師是通訊作者的論文（作者列有 * 的；Jeff 2026-10-26），每篇一張卡片。**2020 年（含）以後的**才在書目上面放 SciDraw 生的示意圖（卡片全寬，點圖開大圖；Jeff 2026-10-27），2015–2019 年的卡片只列書目；全部論文清單只列書目、不放圖。年份門檻是 `build.py` 的 `SCHEMATIC_FROM_YEAR`，判斷在 `has_schematic()`。不放示意圖的論文（非通訊作者、2020 年以前）：`pub_images.py` 會跳過它們的原圖，`build.py` 也不顯示。原圖與提示詞放在 repo 外的資料夾，裡面的 `prompts.json` 記每張圖對應的 DOI 與種類（3D 封面圖 `cover` 也留在那裡，網站目前不放）。跑 `python tools/pub_images.py --src <原圖資料夾>` 會先裁掉白邊，再轉成 `static/img/pubs/` 的 WebP（卡片 960 寬、點開 1600 寬），然後跑 `build.py` 就會出現；檔名照 DOI，還沒有圖的精選論文只顯示書目。AI 生的圖可能把標籤、結構畫錯，上線前每張都要對著論文核對。
- **研究主題圖**：四張水彩畫（`prompts.json` 種類 `research`）。`pub_images.py` 產生三個尺寸：`{主題}-xs.webp`（480 寬、從中間裁成 3:2，首頁主題卡片的縮圖）、`-sm.webp`（900 寬，研究頁）、`.webp`（1600 寬，點開的大圖）。`build.py` 看到 `-xs` 才在首頁卡片放縮圖，沒有就退回小圖示。
- **首頁的精選論文**：自動放最新 3 篇精選論文（標題、期刊、示意圖取自 `publications.yaml`），每張卡片連到論文頁上同一篇；手機版只列文字、不載示意圖。
- **全站背景畫**：首頁主視覺（`hero`）與內頁標題區（`pagehead`）的背景是 SciDraw 生的「印象派筆觸＋分子網絡」畫，灰底區塊、頁尾與首頁下方的招生色帶也借用這兩張，各疊一層遮罩。要換圖：原圖放進原圖資料夾、`prompts.json` 種類填 `background`、`name` 填 `hero` 或 `pagehead`，再跑 `tools/pub_images.py` 與 `build.py`。換圖後要確認左側文字仍然好讀。
- **換 PI 照片**：`python tools/make_images.py --pi <原始照片>`，會裁成 4:5、720×900，並順便縮出首頁用的 `pi-sm.jpg`（360×450）。
- **改了網站名稱或主視覺的畫**：重跑 `python tools/make_images.py`，分享預覽圖（`og-image.jpg`，1200×630）會跟著更新：底圖是 `static/img/bg/hero.webp`，左邊疊深藍漸層，上面的字取自 `site.yaml`（用到 Windows 內建的 Segoe UI 與微軟正黑體）。

## 產生與預覽

```
pip install -r requirements.txt
python build.py --check      # 產生 docs/ 並檢查站內連結
python build.py --serve      # 產生後開 http://127.0.0.1:8790 預覽
python tools/preview.py      # 不重新產生，直接開預覽並打開瀏覽器（Ctrl+C 結束）
```

`--serve` 與 `tools/preview.py` 預設都用 8790，跟桌面捷徑的預覽是同一個 port；桌面捷徑的預覽在跑時，不要再開 `--serve`（Windows 可能讓兩個程式同時綁住 8790），改了內容只要跑 `build.py`、重新整理頁面。另外開一個預覽用 `python tools/preview.py --port 8791 --no-open`。

Windows 的終端機若印中文出錯，改用 `python -X utf8 build.py`。預覽伺服器（`build.py --serve`、`tools/preview.py`）已補上 `.webp`、`.woff` 的檔案類型；Windows 的 Python 常不認得它們，不補的話手機版點精選論文的示意圖（直接開圖檔）會變成下載。

圖檔、樣式、程式、字型的網址會自動接上依檔案內容算的版本號（`?v=…`，CSS 裡的背景圖也有），換了圖或改了樣式，瀏覽器重新整理就會抓新的，不必清快取。

**中文字型子集**：中文頁的字型是 Noto Sans TC（SIL OFL 授權）的子集，檔案 `static/fonts/NotoSansTC-subset.woff`，只含中文頁實際用到的字（目前約 515 字、165 KB，保留 400–700 字重；英文字母與數字由 Inter 負責，所以不含 ASCII）。
- **不用手動處理**：`python build.py` 每次產生網頁後，會比對「中文頁用到的字」和「子集裡有的字」；電腦上有原字型（Windows 內建的 `C:\Windows\Fonts\NotoSansTC-VF.ttf`，或用環境變數 `NOTO_SANS_TC_VF` 指定檔案）而且有新字，就自動重做子集（需要 `pip install -r requirements.txt` 裝的 fontTools），並在畫面上印出「中文字型子集已更新」。更新後記得把 `static/fonts/` 的新字型檔一起提交。
- **找不到原字型**（例如換了電腦）：沿用 repo 裡的子集，並警告「下列 N 個字不在子集裡」。這些字會改用訪客電腦的系統字型顯示，版面不會壞；到有原字型的電腦重跑 `build.py` 就補上。
- 只做 WOFF（沒裝 brotli 做不了 WOFF2）。英文頁不載入這個字型（英文頁裡的少數中文字，例如「中文」按鈕，用系統字型）。
- 單獨檢查：`python tools/font_subset.py --check`（用 `docs/zh/` 現有的網頁比對，不改檔案）。

**Windows 桌面捷徑**：`python tools/preview.py --shortcut` 會在桌面建「實驗室網站預覽」。雙擊就打開瀏覽器；預覽用 pythonw 在背景跑、不開視窗，到登出或關機才停，預覽在跑時再雙擊只會多開一個分頁。啟動紀錄與錯誤寫在暫存資料夾的 `lab-website-preview.log`。捷徑用的圖示 `tools/preview.ico` 在本機產生，不進 git。

## 上線（還沒做）

1. 在 GitHub 建公開儲存庫，推上 `main`。Settings → Pages → Deploy from a branch → `main` 的 `/docs`。
2. 網址：先在 GitHub 帳號 Settings → Pages 驗證網域 `nmse.bmes.nthu.edu.tw`（2026-10-26 已加入，等 TXT 紀錄生效後按 Verify），系網管同時把子網域設成 CNAME 指到 `jf168cc-bmes.github.io`。沒驗證就加 CNAME，別人可能在 GitHub 上搶用這個子網域。
3. `content/site.yaml` 填 `custom_domain` 與 `base_url`，`noindex` 改成 `false`，重跑 `build.py`、推上去。GitHub 會自動簽 HTTPS 憑證，Settings → Pages 勾 Enforce HTTPS。填了 `base_url` 之後，`404.html` 的樣式、圖檔、連結會改用完整網址（GitHub Pages 在多層路徑的錯誤網址也回這一頁，相對網址會讓整頁沒有樣式）；沒填時維持相對網址。
4. 上線後：系教師頁、師資列表、PMED、TEEP 計畫頁、Google Scholar 的連結全部換成新網址。

## 注意

- 這個儲存庫會是**公開**的：只放網站上本來就要公開的東西。同意書、學生個資、未發表資料都不要放進來。
- 研究內容只寫已發表的成果與大方向；進行中的題目寫到多細，由張老師決定。
- 英文字型 Inter 從 Google Fonts 載入（訪客的 IP 會送到 Google）；中文字型是自己放在 `static/fonts/` 的子集，不經過 Google。挑工具與外掛時避開大陸廠牌（清大資安規範）。
