// 論文／研究插圖：桌機點小圖在頁面上開大圖，右上角有關閉鈕，點一下或按 Esc 也能關。
// 手機（寬 ≤760px，或橫放的觸控手機）不開小視窗：照連結直接開 1600 寬原圖，用手機瀏覽器原生的雙指縮放看細節。
// 瀏覽器不支援 <dialog> 時也照連結直接開圖檔。
var phoneView = window.matchMedia("(max-width: 760px), (pointer: coarse) and (max-height: 520px)");
document.addEventListener("click", function (event) {
  var link = event.target.closest("a[data-zoom]");
  if (!link || typeof HTMLDialogElement !== "function" || phoneView.matches) return;
  event.preventDefault();
  var box = document.querySelector("dialog.zoom");
  if (!box) {
    var zh = /^zh/i.test(document.documentElement.lang);
    box = document.createElement("dialog");
    box.className = "zoom";
    var bar = document.createElement("div");
    bar.className = "zoom-bar";
    var close = document.createElement("button");
    close.type = "button";
    close.className = "zoom-close";
    close.setAttribute("aria-label", zh ? "關閉大圖" : "Close enlarged image");
    close.textContent = "×";
    bar.appendChild(close);
    box.appendChild(bar);
    box.appendChild(document.createElement("img"));
    box.addEventListener("click", function () { box.close(); });
    document.body.appendChild(box);
  }
  var small = link.querySelector("img");
  var caption = link.getAttribute("data-caption") || (small ? small.alt : "");
  var img = box.querySelector("img");
  img.src = link.href;
  img.alt = caption;
  box.setAttribute("aria-label", caption);   // 視窗的名字＝論文標題，螢幕閱讀器才知道開的是哪一張
  box.showModal();
});

// 手機版選單開合；點選單內的連結後自動收起。
document.addEventListener("DOMContentLoaded", function () {
  var toggle = document.querySelector(".nav-toggle");
  var nav = document.getElementById("site-nav");
  if (!toggle || !nav) return;
  toggle.addEventListener("click", function () {
    var open = nav.classList.toggle("open");
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
  });
  nav.addEventListener("click", function (event) {
    if (event.target.closest("a") && nav.classList.contains("open")) {
      nav.classList.remove("open");
      toggle.setAttribute("aria-expanded", "false");
    }
  });
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && nav.classList.contains("open")) {
      nav.classList.remove("open");
      toggle.setAttribute("aria-expanded", "false");
      toggle.focus();
    }
  });
});
