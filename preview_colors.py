# -*- coding: utf-8 -*-
"""マシンカラーの判定結果と、絞り込みUIの見た目を確かめるためのテストページ。

本番の docs/ には手を入れない。_preview_colors.html を単体で出力する。
判定が合っているか（写真と色ゾーンが一致しているか）を目で見て確かめ、
ゾーンの数や見せ方を決めてから本番へ入れる。

    py x_machine_colors.py     # 先にこちらで判定を作る
    py preview_colors.py
"""
import html
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SRC = os.path.join("docs", "data", "x-machine-colors.json")
OUT = "_preview_colors.html"
IMG_DIR = "cache/x-images"      # ブラウザから見たときの相対パス

CSS = """
:root{
  --bg:#0f1216; --card:#171b21; --line:#252b33;
  --ink:#eef1f5; --ink2:#aab3bf; --ink3:#79838f;
  --accent:#7d5fff;
  color-scheme:dark;
  font-family:system-ui,-apple-system,"Segoe UI","Hiragino Kaku Gothic ProN","Noto Sans JP",sans-serif;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--ink);line-height:1.6;padding:20px 16px 60px}
.wrap{max-width:1180px;margin:0 auto}
h1{font-size:19px;letter-spacing:.02em;margin-bottom:4px}
.lead{font-size:12.5px;color:var(--ink3);margin-bottom:20px}

/* ---- カラーゾーンの絞り込みUI（ここが今回の検討対象） ---- */
.zonebar{position:sticky;top:0;z-index:5;background:rgba(15,18,22,.86);
backdrop-filter:blur(12px);margin:0 -16px 22px;padding:14px 16px;
border-bottom:1px solid var(--line)}
.zones{display:flex;gap:10px;overflow-x:auto;scrollbar-width:none;
padding-bottom:2px;scroll-snap-type:x proximity}
.zones::-webkit-scrollbar{display:none}
.zone{flex:none;width:64px;background:none;border:none;padding:0;cursor:pointer;
font:inherit;color:var(--ink2);text-align:center;scroll-snap-align:start;
transition:color .18s}
.zone:hover{color:var(--ink)}
.dot{position:relative;width:44px;height:44px;margin:0 auto 6px;border-radius:50%;
background:var(--c);box-shadow:inset 0 -6px 12px rgba(0,0,0,.28),
inset 0 4px 10px rgba(255,255,255,.22),0 2px 8px rgba(0,0,0,.4);
transition:transform .18s cubic-bezier(.34,1.4,.5,1),box-shadow .18s}
.zone:hover .dot{transform:translateY(-2px) scale(1.06)}
.zone[aria-pressed="true"] .dot{transform:translateY(-2px) scale(1.06);
box-shadow:inset 0 -6px 12px rgba(0,0,0,.28),inset 0 4px 10px rgba(255,255,255,.22),
0 0 0 3px var(--bg),0 0 0 5.5px var(--c)}
.zone[aria-pressed="true"]{color:var(--ink)}
.dot.all{background:conic-gradient(#e5342c,#f5c518,#2fae5a,#2277dd,#8b5cf6,#ef5da8,#e5342c)}
.dot .n{position:absolute;right:-4px;bottom:-4px;min-width:20px;height:20px;
border-radius:10px;background:var(--card);border:1px solid var(--line);
font-size:10.5px;font-weight:800;color:var(--ink2);display:flex;
align-items:center;justify-content:center;padding:0 5px}
.zname{font-size:10.5px;font-weight:700;letter-spacing:.02em;white-space:nowrap}

/* ---- 判定結果の一覧 ---- */
.count{font-size:12px;color:var(--ink3);margin-bottom:12px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(184px,1fr));gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;
overflow:hidden;display:flex;flex-direction:column;align-self:start}
.card.hide{display:none}
/* 判定は投稿の写真すべてを合わせて出しているので、全部並べる */
.shots{display:grid;gap:1px;background:#0b0e12}
.shots.n1{grid-template-columns:1fr}
.shots.n2{grid-template-columns:1fr 1fr}
.shots.n3,.shots.n4{grid-template-columns:1fr 1fr}
.shot{aspect-ratio:4/3;background:#0b0e12;display:block;width:100%;object-fit:cover}
.shots.n1 .shot{aspect-ratio:16/10}
.meta{padding:9px 11px 11px;display:flex;flex-direction:column;gap:7px}
.tagrow{display:flex;align-items:center;gap:7px;flex-wrap:wrap}
.chip{display:inline-flex;align-items:center;gap:6px;background:#0f1319;
border:1px solid var(--line);border-radius:999px;padding:3px 9px 3px 4px;
font-size:11px;font-weight:800;white-space:nowrap}
.chip i{width:15px;height:15px;border-radius:50%;background:var(--c);
box-shadow:inset 0 -3px 6px rgba(0,0,0,.3),inset 0 2px 5px rgba(255,255,255,.2)}
.pct{font-size:10.5px;color:var(--ink3);font-weight:700}
.memo{font-size:11px;color:var(--ink2);line-height:1.45;
display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.bars{display:flex;height:6px;border-radius:3px;overflow:hidden;background:#0b0e12}
.bars span{display:block}
.pid{font-size:10px;color:var(--ink3);letter-spacing:.04em}
.pid a{color:var(--ink3)}
"""

JS = """
const zones=[...document.querySelectorAll('.zone')];
const cards=[...document.querySelectorAll('.card')];
const countEl=document.getElementById('count');
let cur='all';
function apply(){
  let n=0;
  for(const c of cards){
    const on = cur==='all' || c.dataset.color===cur;
    c.classList.toggle('hide', !on);
    if(on) n++;
  }
  countEl.textContent = n + ' 件を表示中';
}
zones.forEach(z => z.addEventListener('click', () => {
  cur = z.dataset.zone;
  zones.forEach(x => x.setAttribute('aria-pressed', x===z ? 'true':'false'));
  apply();
}));
apply();
"""


def main() -> int:
    if not os.path.exists(SRC):
        print("先に py x_machine_colors.py を実行してください。")
        return 1
    data = json.load(open(SRC, encoding="utf-8"))
    zones = data["zones"]
    items = data["items"]
    zmap = {z["key"]: z for z in zones}

    count = {}
    for it in items:
        count[it["color"]] = count.get(it["color"], 0) + 1

    zbtn = ['<button class="zone" type="button" data-zone="all" aria-pressed="true">'
            '<span class="dot all"><span class="n">%d</span></span>'
            '<span class="zname">すべて</span></button>' % len(items)]
    for z in zones:
        n = count.get(z["key"], 0)
        if not n:
            continue                      # 0件のゾーンはボタンを出さない
        zbtn.append(
            '<button class="zone" type="button" data-zone="%s" aria-pressed="false" '
            'style="--c:%s"><span class="dot"><span class="n">%d</span></span>'
            '<span class="zname">%s</span></button>'
            % (z["key"], z["swatch"], n, html.escape(z["label"])))

    cards = []
    for it in items:
        z = zmap.get(it["color"], {"label": it["color"], "swatch": "#888"})
        bars = "".join(
            '<span style="background:%s;width:%.1f%%"></span>'
            % (zmap.get(k, {}).get("swatch", "#888"), v * 100)
            for k, v in it["share"].items())
        # 判定は投稿の写真すべてを合わせて出しているので、全部並べて見せる
        shots = "".join(
            '<img class="shot" src="%s/%s" alt="">' % (IMG_DIR, f)
            for f in it.get("files", []))
        cards.append(
            '<article class="card" data-color="%s">'
            '<div class="shots n%d">%s</div>'
            '<div class="meta">'
            '<div class="tagrow"><span class="chip" style="--c:%s"><i></i>%s</span>'
            '<span class="pct">%d%%</span>'
            '<span class="pct">背景を除いて %d%% を判定</span></div>'
            '<div class="bars">%s</div>'
            '<div class="memo">%s</div>'
            '<div class="pid">%s ・ <a href="%s" target="_blank" rel="noopener">X で見る</a></div>'
            '</div></article>'
            % (it["color"], min(4, len(it.get("files", [])) or 1), shots,
               z["swatch"], html.escape(z["label"]),
               round(it["ratio"] * 100), round(it.get("kept", 0) * 100), bars,
               html.escape(it.get("memo", "")), it["id"], html.escape(it["url"])))

    doc = """<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>マシンカラー判定テスト｜ミニ四リン駆</title>
<style>%s</style></head><body>
<div class="wrap">
  <h1>マシンカラー 判定テスト</h1>
  <p class="lead">写真の専有面積がいちばん多い色をマシンカラーにしています。
  帯は上位5ゾーンの内訳です。判定が合っているか、ゾーンの数が多すぎないかを見てください。</p>
  <div class="zonebar"><div class="zones">%s</div></div>
  <p class="count" id="count"></p>
  <div class="grid">%s</div>
</div>
<script>%s</script>
</body></html>
""" % (CSS, "\n".join(zbtn), "\n".join(cards), JS)

    open(OUT, "w", encoding="utf-8", newline="\n").write(doc)
    print("書き出し: %s（%d件）" % (os.path.abspath(OUT), len(items)))
    for z in zones:
        if count.get(z["key"]):
            print("  %-6s %3d件" % (z["label"], count[z["key"]]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
