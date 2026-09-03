# -*- coding: utf-8 -*-
"""「新製品」タブの3文字に付ける5組の配色を、並べて確かめるためのプレビュー。

本番には手を入れない。_preview_newtab.html を単体で出す。

    py preview_newtab.py

本番では、タブを押すたびにこの5組が順に切り替わる。
動き続けるアニメーションにしなかったのは、常時動くものは目に障るのと、
「動きを減らす」設定の人には見えないため。操作に応じた変化なら両立する。
配色そのものは build_official_index.py の NEW_TAB_HUES が正。
"""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

OUT = "_preview_newtab.html"

# build_official_index.NEW_TAB_HUES と同じ並び
HUES = [
    ["#e5342c", "#f07a1a", "#f5c518"],
    ["#f07a1a", "#f5c518", "#8dc925"],
    ["#f5c518", "#8dc925", "#2fae5a"],
    ["#2fae5a", "#2277dd", "#8b5cf6"],
    ["#2277dd", "#8b5cf6", "#ef5da8"],
]
NAMES = ["赤 / オレンジ / 黄", "オレンジ / 黄 / 黄緑", "黄 / 黄緑 / 緑",
         "緑 / 青 / 紫", "青 / 紫 / ピンク"]

CSS = """
:root{--bg:#f5f6f8;--surface:#fff;--ink:#1a2233;--ink2:#5a6478;--ink3:#8b93a5;
--brand:#1256c4;--line:#e3e6ec;
font-family:"Hiragino Sans","Noto Sans JP",Meiryo,sans-serif}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--ink);font-size:14px;line-height:1.6;padding:24px 18px 60px}
.wrap{max-width:820px;margin:0 auto}
h1{font-size:18px;margin-bottom:4px}
.lead{font-size:12.5px;color:var(--ink3);margin-bottom:22px}
.row{display:flex;align-items:center;gap:14px;margin-bottom:10px}
.no{font-size:11px;color:var(--ink3);width:2.5em;text-align:right}
.tabs{display:flex;gap:4px;background:var(--surface);padding:6px 8px;
border:1px solid var(--line);border-radius:8px}
.tab{padding:7.6px 20px;font-size:13.5px;font-weight:700;color:var(--ink2);
background:var(--surface);border-radius:4px 4px 0 0;white-space:nowrap}
.tab .n{font-size:11px;margin-left:6px;color:var(--ink3)}
.tab.on{background:var(--brand);color:#fff}
.tab.on .n{color:rgba(255,255,255,.8)}
.ch{display:inline-block}
.ch:nth-child(1){color:var(--c1)}
.ch:nth-child(2){color:var(--c2)}
.ch:nth-child(3){color:var(--c3)}
/* 選択中は青背景に乗るので白で固定。上の3行より詳細度が低いため !important。 */
.tab.on .ch{color:#fff !important}
.name{font-size:12px;color:var(--ink2)}
"""

HTML = """<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>新製品タブの配色｜プレビュー</title>
<style>%(css)s</style></head><body>
<div class="wrap">
  <h1>「新製品」タブの配色 5組</h1>
  <p class="lead">タブを押すたびに、上から順に切り替わって一巡します。
  選択中（青背景）は白で固定です。</p>
%(rows)s
</div>
</body></html>
"""


def main() -> int:
    chars = "".join('<span class="ch">%s</span>' % c for c in "新製品")
    rows = []
    for i, (h, nm) in enumerate(zip(HUES, NAMES), 1):
        var = "--c1:%s;--c2:%s;--c3:%s" % tuple(h)
        rows.append(
            '  <div class="row"><span class="no">%d</span>'
            '<div class="tabs">'
            '<div class="tab" style="%s">%s<span class="n">32</span></div>'
            '<div class="tab on" style="%s">%s<span class="n">32</span></div>'
            '<div class="tab">キット<span class="n">467</span></div>'
            '</div><span class="name">%s</span></div>' % (i, var, chars, var, chars, nm))
    open(OUT, "w", encoding="utf-8", newline="\n").write(
        HTML % {"css": CSS, "rows": "\n".join(rows)})
    print("書き出し: %s" % os.path.abspath(OUT))
    for i, (h, nm) in enumerate(zip(HUES, NAMES), 1):
        print("  %d. %-22s %s" % (i, nm, " ".join(h)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
