# -*- coding: utf-8 -*-
"""カラーホイール（色相環）で絞り込むUIの、見た目と操作を確かめるテストページ。

本番の docs/ には手を入れない。_preview_wheel.html を単体で出力する。

    py x_machine_colors.py     # 先に判定データを作る
    py preview_wheel.py

作り:
  外側の輪  … 有彩色（レッド〜ピンク）を色相の順に並べた扇
  内側の輪  … 無彩色（ホワイト・シルバー・ブラック）
  中心      … カラフル
扇の中にはマシン写真をランダムに散らす。並びは読み込むたびに変わる。
扇をタップするとその色で絞り込み、下の一覧が入れ替わる。
"""
import html
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SRC = os.path.join("docs", "data", "x-machine-colors.json")
OUT = "_preview_wheel.html"
IMG_DIR = "cache/x-images"      # テストでは手元の写真を使う（本番は pbs のURL）

# 外側の輪に並べる順（色相の並び）と、内側の輪
RING_OUTER = ["red", "orange", "yellow", "gold", "green", "blue", "purple", "pink"]
RING_INNER = ["white", "silver", "black"]
CENTER = "multi"

CSS = """
:root{
  --bg:#0d1014; --card:#161a20; --line:#252b33;
  --ink:#eef1f5; --ink2:#a9b2be; --ink3:#767f8b;
  color-scheme:dark;
  font-family:system-ui,-apple-system,"Segoe UI","Hiragino Kaku Gothic ProN","Noto Sans JP",sans-serif;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--ink);line-height:1.6;padding:22px 16px 70px}
.wrap{max-width:1120px;margin:0 auto}
h1{font-size:19px;letter-spacing:.02em;margin-bottom:4px}
.lead{font-size:12.5px;color:var(--ink3);margin-bottom:18px}

/* ---- カラーホイール ---- */
.wheelbox{display:flex;flex-direction:column;align-items:center;gap:12px;margin-bottom:26px}
.wheel{width:min(92vw,520px);aspect-ratio:1;position:relative;touch-action:manipulation}
.wheel svg{width:100%;height:100%;display:block;overflow:visible}
/* 扇。押せることが分かるよう、触れると少し浮かせる */
.sect{cursor:pointer;transition:opacity .18s,transform .22s cubic-bezier(.34,1.35,.5,1);
transform-origin:50% 50%;transform-box:fill-box}
.sect .base{transition:opacity .18s}
.g:hover .sect,.g.on .sect{opacity:1}
.g{transition:transform .22s cubic-bezier(.34,1.35,.5,1);transform-origin:280px 280px}
.g:hover{transform:scale(1.035)}
.g.on{transform:scale(1.06)}
.g.empty{opacity:.28;pointer-events:none}
.g.dim{opacity:.3}
/* SVGの中の文字はビューボックスと一緒に縮むので、
   画面が狭いときは指定を大きくして、実寸の読みやすさを保つ。 */
.zlabel{font-size:15px;font-weight:800;fill:#fff;letter-spacing:.04em;
paint-order:stroke;stroke:rgba(0,0,0,.55);stroke-width:3.5px;stroke-linejoin:round;
pointer-events:none;user-select:none}
.zcount{font-size:12px;font-weight:800;fill:rgba(255,255,255,.85);
paint-order:stroke;stroke:rgba(0,0,0,.55);stroke-width:3px;
pointer-events:none;user-select:none}
@media(max-width:600px){
  .zlabel{font-size:20px;stroke-width:4.5px}
  .zcount{font-size:16px;stroke-width:4px}
}
/* 散らすマシン写真。扇のタップを邪魔しないよう当たり判定は切る */
.chipimg{pointer-events:none}
.chipimg circle{fill:none;stroke:rgba(255,255,255,.85);stroke-width:1.5}

.hint{font-size:12px;color:var(--ink3)}
.reshuffle{background:var(--card);border:1px solid var(--line);color:var(--ink2);
border-radius:999px;padding:7px 16px;font:inherit;font-size:12px;font-weight:700;cursor:pointer}
.reshuffle:hover{color:var(--ink);border-color:#39424d}

/* ---- 絞り込みの結果 ---- */
.head{display:flex;align-items:baseline;gap:10px;margin:0 0 12px}
.head h2{font-size:15px;letter-spacing:.02em}
.head .n{font-size:12px;color:var(--ink3)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:13px;
overflow:hidden;display:flex;flex-direction:column;align-self:start;
text-decoration:none;color:inherit}
.card:hover{border-color:#39424d}
.card img{width:100%;aspect-ratio:4/3;object-fit:cover;display:block;background:#0b0e12}
.card .m{padding:8px 10px 10px;display:flex;flex-direction:column;gap:4px}
.card .t{font-size:11px;color:var(--ink2);line-height:1.4;
display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.card .u{font-size:10px;color:var(--ink3)}
.badge{display:inline-flex;align-items:center;gap:5px;font-size:10px;font-weight:800}
.badge i{width:11px;height:11px;border-radius:50%;background:var(--c)}
"""

JS = """
const DATA = %s;
const ZONES = %s;
const OUTER = %s, INNER = %s, CENTER = %s;

const CX=280, CY=280;
const R_OUT=222, R_MID=148, R_IN=84;
const PHOTO_R=15;      // 散らす写真の半径
const LABEL_R=246;     // 外側の輪のラベルは、輪の外に出して読みやすくする
const svg=document.getElementById('wheel');
const NS='http://www.w3.org/2000/svg';
let cur=null;

const byZone={};
for(const z of ZONES) byZone[z.key]=[];
for(const it of DATA) (byZone[it.color]=byZone[it.color]||[]).push(it);
const zmap=Object.fromEntries(ZONES.map(z=>[z.key,z]));

function pol(cx,cy,r,deg){const a=(deg-90)*Math.PI/180;return [cx+r*Math.cos(a),cy+r*Math.sin(a)];}
function ring(cx,cy,r1,r2,a1,a2){
  const [x1,y1]=pol(cx,cy,r2,a1),[x2,y2]=pol(cx,cy,r2,a2);
  const [x3,y3]=pol(cx,cy,r1,a2),[x4,y4]=pol(cx,cy,r1,a1);
  const big=(a2-a1)>180?1:0;
  return `M${x1} ${y1}A${r2} ${r2} 0 ${big} 1 ${x2} ${y2}L${x3} ${y3}A${r1} ${r1} 0 ${big} 0 ${x4} ${y4}Z`;
}
function shuffle(a){for(let i=a.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[a[i],a[j]]=[a[j],a[i]];}return a;}

// 扇の中に、はみ出さず重ならないように写真を散らす。
// 半径方向はそのまま、角度方向は「その半径での弧の長さ」で余白を測る
// （内側ほど1度あたりの距離が短いので、角度の余白は大きく取る必要がある）。
function scatter(a1,a2,r1,r2,n,keepOut){
  const pts=[], tries=500, pad=PHOTO_R+3;
  const lo=r1+pad, hi=r2-pad;
  if(hi<=lo) return pts;
  for(let t=0;t<tries&&pts.length<n;t++){
    const rr=lo+Math.random()*(hi-lo);
    const margin=Math.asin(Math.min(1,pad/rr))*180/Math.PI;   // 端から離す角度
    const aLo=a1+margin, aHi=a2-margin;
    if(aHi<=aLo) continue;
    const ang=aLo+Math.random()*(aHi-aLo);
    const [x,y]=pol(CX,CY,rr,ang);
    if(keepOut && (x-keepOut[0])**2+(y-keepOut[1])**2 < keepOut[2]**2) continue;
    if(pts.every(p=>(p[0]-x)**2+(p[1]-y)**2 > (PHOTO_R*2+3)**2)) pts.push([x,y]);
  }
  return pts;
}

function build(){
  svg.textContent='';
  const defs=document.createElementNS(NS,'defs');
  svg.appendChild(defs);

  const groups=[];
  const step=360/OUTER.length;
  OUTER.forEach((key,i)=>groups.push({key,a1:i*step,a2:(i+1)*step,r1:R_MID,r2:R_OUT}));
  const istep=360/INNER.length;
  INNER.forEach((key,i)=>groups.push({key,a1:i*istep+18,a2:(i+1)*istep+18,r1:R_IN,r2:R_MID-6}));

  for(const g of groups){
    const z=zmap[g.key], list=byZone[g.key]||[];
    const el=document.createElementNS(NS,'g');
    el.setAttribute('class','g'+(list.length?'':' empty'));
    el.dataset.zone=g.key;

    const p=document.createElementNS(NS,'path');
    p.setAttribute('class','sect');
    p.setAttribute('d',ring(CX,CY,g.r1,g.r2,g.a1,g.a2));
    p.setAttribute('fill',z.swatch);
    p.setAttribute('stroke','#0d1014');
    p.setAttribute('stroke-width','2');
    el.appendChild(p);

    const outer = g.r2>R_MID;
    const mid=(g.a1+g.a2)/2;
    // ラベルの位置。外側の輪は輪の外へ出す（写真と重ならず読みやすい）
    const [lx,ly]= outer ? pol(CX,CY,LABEL_R,mid) : pol(CX,CY,R_IN+22,mid);
    // 内側の輪はラベルが扇の中に載るので、その周りには写真を置かない
    const keepOut = outer ? null : [lx,ly,46];

    // 写真を散らす（少ないゾーンは繰り返さず、あるだけ置く）
    const pool=shuffle(list.slice()).slice(0, outer ? 5 : 3);
    const pts=scatter(g.a1,g.a2,g.r1,g.r2,pool.length,keepOut);
    pool.forEach((it,idx)=>{
      if(!pts[idx]) return;
      const [x,y]=pts[idx], r=PHOTO_R;
      const cid='c'+g.key+idx+Math.floor(Math.random()*1e6);
      const cp=document.createElementNS(NS,'clipPath');
      cp.id=cid;
      const cc=document.createElementNS(NS,'circle');
      cc.setAttribute('cx',x);cc.setAttribute('cy',y);cc.setAttribute('r',r);
      cp.appendChild(cc);defs.appendChild(cp);
      const gi=document.createElementNS(NS,'g');
      gi.setAttribute('class','chipimg');
      const im=document.createElementNS(NS,'image');
      im.setAttribute('href',it.thumb);
      im.setAttribute('x',x-r);im.setAttribute('y',y-r);
      im.setAttribute('width',r*2);im.setAttribute('height',r*2);
      im.setAttribute('preserveAspectRatio','xMidYMid slice');
      im.setAttribute('clip-path',`url(#${cid})`);
      const rg=document.createElementNS(NS,'circle');
      rg.setAttribute('cx',x);rg.setAttribute('cy',y);rg.setAttribute('r',r);
      gi.appendChild(im);gi.appendChild(rg);
      el.appendChild(gi);
    });

    // ゾーン名と件数
    const t=document.createElementNS(NS,'text');
    t.setAttribute('class','zlabel'+(outer?' out':''));
    t.setAttribute('x',lx);t.setAttribute('y',ly);
    t.setAttribute('text-anchor','middle');
    t.textContent=z.label;
    el.appendChild(t);
    const t2=document.createElementNS(NS,'text');
    t2.setAttribute('class','zcount');
    t2.setAttribute('x',lx);t2.setAttribute('y',ly+15);
    t2.setAttribute('text-anchor','middle');
    t2.textContent=list.length;
    el.appendChild(t2);

    el.addEventListener('click',()=>select(g.key));
    svg.appendChild(el);
  }

  // 中心＝カラフル
  const z=zmap[CENTER], list=byZone[CENTER]||[];
  const el=document.createElementNS(NS,'g');
  el.setAttribute('class','g'+(list.length?'':' empty'));
  el.dataset.zone=CENTER;
  // SVGに円錐グラデーションは無いので、細い扇を並べて虹にする
  const RC=R_IN-6, WEDGES=24;
  const hues=['#e5342c','#f07a1a','#f5c518','#2fae5a','#2277dd','#8b5cf6','#ef5da8'];
  for(let i=0;i<WEDGES;i++){
    const a1=i*360/WEDGES, a2=(i+1)*360/WEDGES+0.6;
    const w=document.createElementNS(NS,'path');
    w.setAttribute('class','sect');
    w.setAttribute('d',ring(CX,CY,0,RC,a1,a2));
    w.setAttribute('fill',hues[i%%hues.length]);
    el.appendChild(w);
  }
  const rim=document.createElementNS(NS,'circle');
  rim.setAttribute('cx',CX);rim.setAttribute('cy',CY);rim.setAttribute('r',RC);
  rim.setAttribute('fill','none');
  rim.setAttribute('stroke','#0d1014');rim.setAttribute('stroke-width','2');
  el.appendChild(rim);

  // 中心にも写真を散らす
  shuffle(list.slice()).slice(0,3).forEach((it,idx)=>{
    const pts=scatter(0,360,26,RC,3,[CX,CY,26]);
    const pt=pts[idx];
    if(!pt) return;
    const [x,y]=pt, r=PHOTO_R;
    const cid='mc'+idx+Math.floor(Math.random()*1e6);
    const cp=document.createElementNS(NS,'clipPath');cp.id=cid;
    const cc=document.createElementNS(NS,'circle');
    cc.setAttribute('cx',x);cc.setAttribute('cy',y);cc.setAttribute('r',r);
    cp.appendChild(cc);defs.appendChild(cp);
    const gi=document.createElementNS(NS,'g');gi.setAttribute('class','chipimg');
    const im=document.createElementNS(NS,'image');
    im.setAttribute('href',it.thumb);
    im.setAttribute('x',x-r);im.setAttribute('y',y-r);
    im.setAttribute('width',r*2);im.setAttribute('height',r*2);
    im.setAttribute('preserveAspectRatio','xMidYMid slice');
    im.setAttribute('clip-path',`url(#${cid})`);
    const rg=document.createElementNS(NS,'circle');
    rg.setAttribute('cx',x);rg.setAttribute('cy',y);rg.setAttribute('r',r);
    gi.appendChild(im);gi.appendChild(rg);
    el.appendChild(gi);
  });

  // 文字が虹の上でも読めるよう、暗い丸を敷く
  const pill=document.createElementNS(NS,'circle');
  pill.setAttribute('cx',CX);pill.setAttribute('cy',CY);pill.setAttribute('r',30);
  pill.setAttribute('fill','rgba(13,16,20,.72)');
  pill.setAttribute('class','chipimg');
  el.appendChild(pill);
  const t=document.createElementNS(NS,'text');
  t.setAttribute('class','zlabel');t.setAttribute('x',CX);t.setAttribute('y',CY+2);
  t.setAttribute('text-anchor','middle');t.textContent=z.label;
  el.appendChild(t);
  const t2=document.createElementNS(NS,'text');
  t2.setAttribute('class','zcount');t2.setAttribute('x',CX);t2.setAttribute('y',CY+16);
  t2.setAttribute('text-anchor','middle');t2.textContent=list.length;
  el.appendChild(t2);
  el.addEventListener('click',()=>select(CENTER));
  svg.appendChild(el);

  if(cur) mark();
}

function mark(){
  for(const g of svg.querySelectorAll('.g')){
    const on = g.dataset.zone===cur;
    g.classList.toggle('on', on);
    g.classList.toggle('dim', !!cur && !on && !g.classList.contains('empty'));
  }
}

function select(key){
  cur = (cur===key) ? null : key;
  mark();
  render();
}

function render(){
  const list = cur ? (byZone[cur]||[]) : DATA;
  const z = cur ? zmap[cur] : null;
  document.getElementById('title').textContent = z ? z.label+' のマシン' : 'すべてのマシン';
  document.getElementById('num').textContent = list.length+' 件';
  const grid=document.getElementById('grid');
  grid.innerHTML = list.map(it=>{
    const zz=zmap[it.color]||{label:it.color,swatch:'#888'};
    return `<a class="card" href="${it.url}" target="_blank" rel="noopener">
      <img src="${it.thumb}" alt="" loading="lazy">
      <div class="m">
        <span class="badge" style="--c:${zz.swatch}"><i></i>${zz.label}</span>
        <span class="t">${it.memo||''}</span>
        <span class="u">@${it.handle||''}</span>
      </div></a>`;
  }).join('');
}

document.getElementById('reshuffle').addEventListener('click', build);
build();
render();
"""


def main() -> int:
    if not os.path.exists(SRC):
        print("先に py x_machine_colors.py を実行してください。")
        return 1
    data = json.load(open(SRC, encoding="utf-8"))
    zones = data["zones"]

    items = []
    for it in data["items"]:
        items.append({
            "id": it["id"], "url": it["url"], "color": it["color"],
            "memo": it.get("memo", ""), "handle": it.get("handle", ""),
            "thumb": "%s/%s" % (IMG_DIR, it["files"][0]) if it.get("files") else "",
        })

    js = JS % (json.dumps(items, ensure_ascii=False),
               json.dumps(zones, ensure_ascii=False),
               json.dumps(RING_OUTER), json.dumps(RING_INNER),
               json.dumps(CENTER))

    doc = """<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>カラーホイール UIテスト｜ミニ四リン駆</title>
<style>%s</style></head><body>
<div class="wrap">
  <h1>カラーホイールで探す（UIテスト）</h1>
  <p class="lead">外側の輪が色みのある色、内側の輪が白・銀・黒、中心がカラフルです。
  扇をタップするとその色のマシンだけが下に並びます。写真の散らばりは開くたびに変わります。</p>
  <div class="wheelbox">
    <div class="wheel"><svg id="wheel" viewBox="0 0 560 560" role="group"
      aria-label="色で絞り込むカラーホイール"></svg></div>
    <button class="reshuffle" id="reshuffle" type="button">配置をシャッフル</button>
    <p class="hint">もう一度同じ扇をタップすると絞り込みを解除します。</p>
  </div>
  <div class="head"><h2 id="title"></h2><span class="n" id="num"></span></div>
  <div class="grid" id="grid"></div>
</div>
<script>%s</script>
</body></html>
""" % (CSS, js)

    open(OUT, "w", encoding="utf-8", newline="\n").write(doc)
    print("書き出し: %s（%d件）" % (os.path.abspath(OUT), len(items)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
