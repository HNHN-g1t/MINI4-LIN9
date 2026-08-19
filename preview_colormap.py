# -*- coding: utf-8 -*-
"""スプレーカラーMAP UI のデザイン確認用プレビューを生成する。

本番の docs/index.html には手を入れず、_preview_colormap.html を単体で出力する。
見た目が固まったら build_official_index.py へ取り込む。

    py preview_colormap.py
"""
import html
import io
import json
import os

import paint_colors as PC

OUT = "_preview_colormap.html"

CSS = """
:root{--bg:#f5f6f8;--surface:#fff;--ink:#1a2233;--ink2:#5a6478;--ink3:#8b93a5;
--brand:#1256c4;--brand-soft:#e8f0fd;--line:#e3e6ec;--accent:#d81f2a;
font-family:"Hiragino Sans","Noto Sans JP",Meiryo,sans-serif}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--ink);font-size:14px;line-height:1.6}
main{max-width:1120px;margin:0 auto;padding:16px}

/* ---- カラーマップ（アコーディオン） ---- */
.cmap{background:var(--surface);border:1px solid var(--line);border-radius:10px;margin-bottom:16px;overflow:hidden}
.cmap-head{width:100%;display:flex;align-items:center;gap:10px;padding:13px 16px;
background:none;border:none;cursor:pointer;font:inherit;color:inherit;text-align:left}
.cmap-head:hover{background:var(--brand-soft)}
.cmap-head:focus-visible{outline:2px solid var(--brand);outline-offset:-2px}
.cmap-title{font-weight:800;font-size:13.5px;letter-spacing:.06em}
.cmap-sub{font-size:11px;color:var(--ink3);flex:1}
.cmap-chev{width:18px;height:18px;flex:none;transition:transform .18s;color:var(--ink2)}
.cmap-head[aria-expanded="true"] .cmap-chev{transform:rotate(180deg)}
.cmap-body{display:none;border-top:1px solid var(--line);padding:14px 16px 16px}
.cmap.open .cmap-body{display:block}

/* フィルタ（上段＝シリーズ / 下段＝効果） */
.frow{display:flex;gap:6px;flex-wrap:wrap;align-items:center;margin-bottom:8px}
.frow-label{font-size:10px;font-weight:800;color:var(--ink3);letter-spacing:.08em;width:46px;flex:none}
.fbtn{border:1.5px solid var(--line);background:var(--surface);border-radius:999px;
padding:5px 14px;font-size:11.5px;font-weight:700;cursor:pointer;font-family:inherit;color:var(--ink2)}
.fbtn[aria-pressed="true"]{background:var(--brand);border-color:var(--brand);color:#fff}
.fbtn.series[aria-pressed="true"]{background:var(--ink);border-color:var(--ink)}

/* 注意書き（PS選択時のみ） */
.note{display:none;gap:8px;align-items:flex-start;background:#fff7e6;border:1px solid #f0d9a8;
border-radius:8px;padding:9px 12px;margin:2px 0 12px;font-size:12px;color:#6b4e12;font-weight:600}
.note.show{display:flex}
.note b{font-weight:800}

/* スクロール領域 */
.cmap-scroll{overflow-x:auto;overflow-y:hidden;-webkit-overflow-scrolling:touch;padding-bottom:6px}
.cmap-inner{min-width:700px}
.zone-label{font-size:10.5px;font-weight:800;color:var(--ink3);letter-spacing:.08em;margin:14px 0 5px}

/* 2Dマップ本体（縦＝色相 / 横＝明るさ） */
.grid2d{display:grid;grid-template-columns:64px repeat(4,1fr);gap:5px;align-items:stretch}
.hhead{font-size:11px;font-weight:700;color:var(--ink2);text-align:center;padding:3px 0}
.lhead{font-size:11px;font-weight:800;color:var(--ink2);display:flex;align-items:center;
padding-right:6px;gap:6px}
.lhead i{width:10px;height:10px;border-radius:3px;flex:none;display:block}
.cell{background:#fafbfc;border:1px solid var(--line);border-radius:6px;min-height:138px;
padding:6px;display:flex;flex-wrap:wrap;gap:5px;align-content:flex-start}
.band{background:#fafbfc;border:1px solid var(--line);border-radius:6px;padding:7px;
display:flex;flex-wrap:wrap;gap:5px}

/* ピン */
.pin{position:relative;width:52px;height:46px;border-radius:8px;border:1px solid rgba(0,0,0,.18);
cursor:pointer;padding:0;font:inherit;display:flex;align-items:flex-end;justify-content:center;
overflow:hidden;flex:none}
.pin:focus-visible{outline:2px solid var(--brand);outline-offset:2px}
.pin .lbl{width:100%;font-size:9px;font-weight:800;line-height:1.6;text-align:center;
background:rgba(255,255,255,.88);color:#1a2233;letter-spacing:-.02em}
.pin.on{box-shadow:0 0 0 3px var(--brand);border-color:var(--brand)}
.pin.hide{display:none}
/* 効果マーク（色だけに頼らないための識別） */
.pin[data-effect="METALLIC"]::before,.pin[data-effect="PEARL"]::before,
.pin[data-effect="FLUORESCENT"]::before,.pin[data-effect="CLEAR"]::before{
content:attr(data-mark);position:absolute;top:1px;right:3px;font-size:8.5px;font-weight:800;
color:#fff;text-shadow:0 0 2px rgba(0,0,0,.85)}
.tip{position:fixed;z-index:50;background:#1a2233;color:#fff;font-size:11px;font-weight:600;
padding:4px 8px;border-radius:5px;pointer-events:none;opacity:0;transition:opacity .12s;white-space:nowrap}
.tip.show{opacity:1}
.legend{font-size:10.5px;color:var(--ink3);margin-top:10px}
.emptycell{font-size:10px;color:#c8ccd3;align-self:center;margin:auto}

/* ---- 商品カード（本番と同じ体裁） ---- */
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
.it{background:var(--surface);border:1px solid var(--line);border-radius:9px;overflow:hidden;
display:flex;flex-direction:column;scroll-margin-top:16px}
.it.hide{display:none}
.it.flash{animation:flash 2.4s ease-out}
@keyframes flash{0%,55%{box-shadow:0 0 0 3px var(--accent);border-color:var(--accent)}
100%{box-shadow:0 0 0 0 rgba(0,0,0,0);border-color:var(--line)}}
.ph{aspect-ratio:4/3;background:#fff;display:flex;align-items:center;justify-content:center;
border-bottom:1px solid var(--line)}
.ph img{max-width:100%;max-height:100%;object-fit:contain}
.bd{padding:10px 12px 12px;display:flex;flex-direction:column;gap:4px;flex:1}
.nm{font-size:12.5px;overflow:hidden;white-space:nowrap}
.code{font-size:10.5px;font-weight:800;color:var(--ink3)}
.pr{font-size:15px;font-weight:800}
.pr small{font-size:10px;font-weight:600;color:var(--ink3)}
@media(max-width:900px){
  .grid{grid-template-columns:repeat(2,1fr)}
  .frow-label{width:100%}
}
"""

JS = """
(() => {
const KEY='mini4rinku:cmapOpen';
const wrap=document.querySelector('.cmap');
const head=document.querySelector('.cmap-head');
const pins=[...document.querySelectorAll('.pin')];
const cards=[...document.querySelectorAll('.it')];
const tip=document.getElementById('tip');
const note=document.getElementById('psNote');
let series='ALL', effect='ALL';

// 開閉（前回の状態を localStorage で復元）
function setOpen(open){
  wrap.classList.toggle('open', open);
  head.setAttribute('aria-expanded', open ? 'true' : 'false');
  try{ localStorage.setItem(KEY, open ? '1' : '0'); }catch(e){}
}
head.addEventListener('click', () => setOpen(!wrap.classList.contains('open')));
let init=false; try{ init = localStorage.getItem(KEY)==='1'; }catch(e){}
setOpen(init);

// フィルタ
function apply(){
  for(const p of pins){
    const ok = (series==='ALL' || p.dataset.series===series)
            && (effect==='ALL' || p.dataset.effect===effect);
    p.classList.toggle('hide', !ok);
  }
  for(const c of cards){
    c.classList.toggle('hide', !(series==='ALL' || c.dataset.series===series));
  }
  note.classList.toggle('show', series==='PS');
}
document.querySelectorAll('.fbtn.series').forEach(b => b.addEventListener('click', () => {
  series=b.dataset.series;
  document.querySelectorAll('.fbtn.series').forEach(x =>
    x.setAttribute('aria-pressed', x===b ? 'true':'false'));
  apply();
}));
document.querySelectorAll('.fbtn.effect').forEach(b => b.addEventListener('click', () => {
  effect=b.dataset.effect;
  document.querySelectorAll('.fbtn.effect').forEach(x =>
    x.setAttribute('aria-pressed', x===b ? 'true':'false'));
  apply();
}));

// ピン → カード
let active=null;
pins.forEach(p => p.addEventListener('click', () => {
  const card=document.getElementById(p.dataset.target);
  if(!card) return;
  if(active) active.classList.remove('on');
  p.classList.add('on'); active=p;
  card.scrollIntoView({behavior:'smooth', block:'center'});
  card.classList.remove('flash');
  void card.offsetWidth;
  card.classList.add('flash');
}));

// ツールチップ（ホバーできる環境のみ）
function showTip(e){
  const p=e.currentTarget;
  tip.textContent=p.dataset.code+' '+p.dataset.cname;
  const r=p.getBoundingClientRect();
  tip.style.left=Math.max(6, r.left+r.width/2-tip.offsetWidth/2)+'px';
  tip.style.top=(r.top-tip.offsetHeight-6)+'px';
  tip.classList.add('show');
}
if(window.matchMedia('(hover:hover)').matches){
  pins.forEach(p => {
    p.addEventListener('mouseenter', showTip);
    p.addEventListener('focus', showTip);
    p.addEventListener('mouseleave', () => tip.classList.remove('show'));
    p.addEventListener('blur', () => tip.classList.remove('show'));
  });
}
apply();
})();
"""

MARKS = {"METALLIC": "M", "PEARL": "P", "FLUORESCENT": "F", "CLEAR": "C"}
# 行見出しに添える色（色相の目印）
HUE_SWATCH = {"レッド": "#d0202a", "オレンジ": "#ef7a1a", "イエロー": "#f2c31d",
              "グリーン": "#1e9c50", "スカイ": "#3fb8e0", "ブルー": "#1a5fc8",
              "パープル": "#7b3fa0", "ピンク": "#e86a9a"}


def pin_html(r: dict) -> str:
    code = r["name"].split()[0] if r["name"].split() else r["item_code"]
    return (f'<button class="pin" style="background:{r["swatch"]}" '
            f'data-target="item-{r["item_code"]}" data-effect="{r["effect"]}" '
            f'data-series="{r["series"]}" '
            f'data-code="{html.escape(code)}" data-cname="{html.escape(r["color_name"])}" '
            f'data-mark="{MARKS.get(r["effect"], "")}" '
            f'aria-label="{html.escape(code)} {html.escape(r["color_name"])} へ移動">'
            f'<span class="lbl">{html.escape(code)}</span></button>')


def build_map(rows: list[dict]) -> str:
    hues = [b for b, _, _ in PC.HUE_BANDS]        # 縦（行）
    lights = [b for b, _, _ in PC.LIGHT_BANDS]    # 横（列）
    out = ['<div class="grid2d">', '<div></div>']
    out += [f'<div class="hhead">{html.escape(l)}</div>' for l in lights]
    for hue in hues:
        sw = HUE_SWATCH.get(hue, "#ccc")
        out.append(f'<div class="lhead"><i style="background:{sw}"></i>{html.escape(hue)}</div>')
        for lb in lights:
            cell = [r for r in rows if r["zone"] == "MAP"
                    and r["hue_band"] == hue and r["light_band"] == lb]
            inner = "".join(pin_html(r) for r in cell) if cell else '<span class="emptycell">—</span>'
            out.append(f'<div class="cell">{inner}</div>')
    out.append('</div>')

    for zone, title in [("NEUTRAL", "NEUTRAL ／ 白・グレー・黒"), ("SPECIAL", "SPECIAL ／ クリヤー・特殊")]:
        band = [r for r in rows if r["zone"] == zone]
        out.append(f'<div class="zone-label">{html.escape(title)}（{len(band)}）</div>')
        out.append('<div class="band">' + "".join(pin_html(r) for r in band) + '</div>')
    return "\n".join(out)


def card_html(r: dict) -> str:
    return f'''<div class="it" id="item-{r["item_code"]}" data-series="{r["series"]}">
  <div class="ph"><img src="{html.escape(r["image"])}" alt="{html.escape(r["name"])}" loading="lazy"></div>
  <div class="bd">
    <div class="nm">{html.escape(r["name"][:13])}</div>
    <div class="code">ITEM {r["item_code"]}</div>
    <div class="pr">¥{r["price"]:,} <small>メーカー希望（税込）</small></div>
  </div>
</div>'''


def main() -> None:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    items = [i for i in json.load(io.open("tamiya_catalog.json", encoding="utf-8"))
             if i["genre_key"] == "paint"]
    rows = PC.build(items)

    series_btns = "".join(
        f'<button class="fbtn series" data-series="{s}" '
        f'aria-pressed="{"true" if s == "ALL" else "false"}">{s}</button>'
        for s in ["ALL", "PS", "TS", "AS"])
    effect_btns = "".join(
        f'<button class="fbtn effect" data-effect="{f}" '
        f'aria-pressed="{"true" if f == "ALL" else "false"}">{f}</button>'
        for f in ["ALL", "STANDARD", "METALLIC", "PEARL", "FLUORESCENT", "CLEAR"])

    doc = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>スプレーカラーMAP プレビュー｜ミニ四リン駆</title>
<style>{CSS}</style>
</head>
<body>
<main>
  <section class="cmap">
    <button class="cmap-head" aria-expanded="false" aria-controls="cmapBody">
      <span class="cmap-title">SPRAY COLOR MAP</span>
      <span class="cmap-sub">色から探す（{len(rows)}色）</span>
      <svg class="cmap-chev" viewBox="0 0 24 24" fill="none" stroke="currentColor"
           stroke-width="2.5" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg>
    </button>
    <div class="cmap-body" id="cmapBody">
      <div class="frow"><span class="frow-label">シリーズ</span>{series_btns}</div>
      <div class="frow"><span class="frow-label">効果</span>{effect_btns}</div>
      <p class="note" id="psNote" role="note">
        <b>ご注意</b>PSはポリカボディ専用の塗装スプレーです。</p>
      <div class="cmap-scroll"><div class="cmap-inner">
{build_map(rows)}
      </div></div>
      <div class="legend">縦軸＝色相（レッド→ピンク）／横軸＝明るさ。ピンを押すと該当商品へ移動します。
      右上の記号 M=メタリック P=パール F=蛍光 C=クリヤー</div>
    </div>
  </section>

  <div class="grid">
{chr(10).join(card_html(r) for r in rows)}
  </div>
</main>
<div class="tip" id="tip" role="status"></div>
<script>{JS}</script>
</body>
</html>
"""
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(doc)
    print(f"生成: {OUT} ／ {len(rows)}色")
    print(f"  2Dマップ {sum(1 for r in rows if r['zone'] == 'MAP')} / "
          f"NEUTRAL {sum(1 for r in rows if r['zone'] == 'NEUTRAL')} / "
          f"SPECIAL {sum(1 for r in rows if r['zone'] == 'SPECIAL')}")


if __name__ == "__main__":
    main()
