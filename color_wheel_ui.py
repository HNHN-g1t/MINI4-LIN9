# -*- coding: utf-8 -*-
"""マシンカラーで探すページ（colors.html）と、カッコ四駆 タブに置く丸ボタン。

判定データ（docs/data/x-machine-colors.json）を読み、
色相環の形をした絞り込みUIのページを作る。
build_official_index.py から呼ばれる。

写真は各投稿者のもの。カードは必ず元の投稿へ飛ぶようにし、
投稿者名（@〜）を添えて出典が分かるようにしている。
"""
import html
import json
import os

DATA = os.path.join("docs", "data", "x-machine-colors.json")
PAGE = "colors.html"

# 外側の輪に並べる順（色相の並び）と、内側の輪
RING_OUTER = ["red", "orange", "yellow", "gold", "green", "blue", "purple", "pink"]
RING_INNER = ["white", "silver", "black"]
CENTER = "multi"


def load() -> tuple:
    """(ゾーン定義, 一覧) を返す。データが無ければ (None, None)。"""
    if not os.path.exists(DATA):
        return (None, None)
    d = json.load(open(DATA, encoding="utf-8"))
    items = [{
        "url": it["url"],
        "photo": it.get("photo", ""),
        "color": it["color"],
        "memo": it.get("memo", ""),
        "handle": it.get("handle", ""),
    } for it in d.get("items", []) if it.get("photo")]
    return (d.get("zones", []), items)


# ---- カッコ四駆 タブに出す丸ボタン ------------------------------------

FAB_CSS = """
/* ---- カッコ四駆 タブの「マシンカラー」ボタン ---- */
/* 塗装タブの丸ボタンと同じ位置・同じ作り。両方が同時に出ることはない。 */
.wheel-fab{position:fixed;right:14px;bottom:16px;z-index:70;width:74px;height:74px;
border-radius:50%;border:3px solid #fff;padding:0;cursor:pointer;display:none;
background:conic-gradient(#e5342c 0deg 45deg,#f07a1a 45deg 90deg,#f5c518 90deg 135deg,
#c9a227 135deg 180deg,#2fae5a 180deg 225deg,#2277dd 225deg 270deg,
#8b5cf6 270deg 315deg,#ef5da8 315deg 360deg);
box-shadow:0 4px 14px rgba(20,40,80,.32)}
/* カッコ四駆 を見ているときだけ出す */
body.wall .wheel-fab{display:block !important}
.wheel-fab:focus-visible{outline:3px solid var(--brand);outline-offset:3px}
.wheel-fab .cap{position:absolute;inset:12px;border-radius:50%;background:var(--surface);
display:flex;flex-direction:column;align-items:center;justify-content:center;
font-size:10px;font-weight:800;line-height:1.18;letter-spacing:-.04em;color:var(--ink);
box-shadow:inset 0 0 0 1px rgba(0,0,0,.07)}
"""

FAB_HTML = ("""  <a class="wheel-fab" href="colors.html"
     aria-label="マシンカラーで探す">
    <span class="cap" aria-hidden="true"><b>マシン</b><b>カラー</b></span>
  </a>""")


# ---- ページ本体 -------------------------------------------------------

CSS = """
:root{--bg:#f5f6f8;--surface:#fff;--ink:#1a2233;--ink2:#5a6478;--ink3:#8b93a5;
--brand:#1256c4;--line:#e3e6ec;
font-family:"Hiragino Sans","Noto Sans JP",Meiryo,sans-serif}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--ink);font-size:14px;line-height:1.6}
a{color:inherit;text-decoration:none}
.topbar{background:#fff;border-bottom:1px solid #e2e6eb}
header{max-width:1120px;margin:0 auto;padding:10px 12px;
display:flex;align-items:center;gap:10px;flex-wrap:wrap}
@media(max-width:600px){header{padding:12px}}
.logo{display:block;line-height:0}
.logo img{width:190px;height:auto;max-width:52vw;display:block}
@media(max-width:600px){.logo img{width:160px}}
.back{margin-left:auto;font-size:13px;color:#1a5fd0}
.back:hover{text-decoration:underline}
.wrap{max-width:1120px;margin:0 auto;padding:16px 12px 48px}
.sr{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;
clip:rect(0 0 0 0);white-space:nowrap;border:0}

/* ---- カラーホイール ---- */
.wheelbox{display:flex;flex-direction:column;align-items:center;gap:10px;margin-bottom:24px}
.wheel{width:min(92vw,500px);aspect-ratio:1;touch-action:manipulation}
.wheel svg{width:100%;height:100%;display:block;overflow:visible}
.sect{cursor:pointer}
.g{transition:transform .22s cubic-bezier(.34,1.35,.5,1),opacity .18s;
transform-origin:280px 280px}
.g:hover{transform:scale(1.035)}
.g.on{transform:scale(1.06)}
.g.empty{opacity:.26;pointer-events:none}
.g.dim{opacity:.32}
/* マウスで押したときに四角い枠が出ないようにする。キーボード操作のときだけ出す */
.g:focus{outline:none}
.g:focus-visible{outline:2px dashed var(--brand);outline-offset:2px}
/* SVGの文字はビューボックスと一緒に縮むので、狭い画面では指定を大きくする */
.zlabel{font-size:15px;font-weight:800;fill:var(--ink);letter-spacing:.04em;
paint-order:stroke;stroke:#fff;stroke-width:3.5px;stroke-linejoin:round;
pointer-events:none;user-select:none}
.zcount{font-size:12px;font-weight:800;fill:var(--ink2);
paint-order:stroke;stroke:#fff;stroke-width:3px;pointer-events:none;user-select:none}
@media(max-width:600px){
  .zlabel{font-size:20px;stroke-width:4.5px}
  .zcount{font-size:16px;stroke-width:4px}
}
.chipimg{pointer-events:none}
.chipimg circle{fill:none;stroke:rgba(255,255,255,.9);stroke-width:1.5}
.reshuffle{background:var(--surface);border:1.5px solid var(--line);color:var(--ink2);
border-radius:999px;padding:7px 16px;font:inherit;font-size:12px;font-weight:700;cursor:pointer}
.reshuffle:hover{color:var(--ink);border-color:#c8cfda}

/* ---- 絞り込みの結果 ---- */
.head{display:flex;align-items:baseline;gap:10px;margin:0 0 10px;flex-wrap:wrap}
.head h2{font-size:15px}
.head .n{font-size:12px;color:var(--ink3)}
/* 絞り込み中だけ出る解除ボタン。絞り込んだ色のすぐ横に置く */
.clear{background:none;border:none;padding:0 2px;font:inherit;font-size:12px;
font-weight:700;color:var(--ink3);cursor:pointer;text-decoration:underline;
text-underline-offset:3px}
.clear:hover{color:var(--ink)}
.clear[hidden]{display:none}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(158px,1fr));gap:12px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:12px;
overflow:hidden;display:flex;flex-direction:column;align-self:start}
.card:hover{box-shadow:0 4px 14px rgba(20,40,80,.10)}
.card img{width:100%;aspect-ratio:4/3;object-fit:cover;display:block;background:#eceff3}
.card .m{padding:8px 10px 10px;display:flex;flex-direction:column;gap:4px}
.card .t{font-size:11px;color:var(--ink2);line-height:1.4;
display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.card .u{font-size:10px;color:var(--ink3)}
.badge{display:inline-flex;align-items:center;gap:5px;font-size:10px;font-weight:800}
.badge i{width:11px;height:11px;border-radius:50%;background:var(--c);
border:1px solid rgba(0,0,0,.15)}
footer{max-width:1120px;margin:0 auto;padding:0 12px 40px;font-size:11.5px;color:var(--ink3)}
"""

JS = """
const DATA=%(items)s, ZONES=%(zones)s;
const OUTER=%(outer)s, INNER=%(inner)s, CENTER=%(center)s;

const CX=280, CY=280, R_OUT=222, R_MID=148, R_IN=84;
const PHOTO_R=15;       // 散らす写真の半径
const EMPTY_SHARE=1/3;  // 1台も無いゾーンの幅（通常の何倍か）
const LABEL_R=246;      // 外側の輪のラベルは輪の外に出す
const NS='http://www.w3.org/2000/svg';
const svg=document.getElementById('wheel');
let cur=null;

const byZone={};
for(const z of ZONES) byZone[z.key]=[];
for(const it of DATA)(byZone[it.color]=byZone[it.color]||[]).push(it);
const zmap=Object.fromEntries(ZONES.map(z=>[z.key,z]));

function pol(cx,cy,r,deg){const a=(deg-90)*Math.PI/180;return[cx+r*Math.cos(a),cy+r*Math.sin(a)];}
function ring(cx,cy,r1,r2,a1,a2){
  const [x1,y1]=pol(cx,cy,r2,a1),[x2,y2]=pol(cx,cy,r2,a2);
  const [x3,y3]=pol(cx,cy,r1,a2),[x4,y4]=pol(cx,cy,r1,a1);
  const big=(a2-a1)>180?1:0;
  return 'M'+x1+' '+y1+'A'+r2+' '+r2+' 0 '+big+' 1 '+x2+' '+y2+
         'L'+x3+' '+y3+'A'+r1+' '+r1+' 0 '+big+' 0 '+x4+' '+y4+'Z';
}
function shuffle(a){for(let i=a.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));
  [a[i],a[j]]=[a[j],a[i]];}return a;}

// 扇の中に、はみ出さず重ならないように写真を散らす。
// 内側ほど1度あたりの弧が短いので、角度の余白は半径から計算する。
function scatter(a1,a2,r1,r2,n,keepOut){
  const pts=[], pad=PHOTO_R+3, lo=r1+pad, hi=r2-pad;
  if(hi<=lo) return pts;
  for(let t=0;t<500&&pts.length<n;t++){
    const rr=lo+Math.random()*(hi-lo);
    const margin=Math.asin(Math.min(1,pad/rr))*180/Math.PI;
    const aLo=a1+margin, aHi=a2-margin;
    if(aHi<=aLo) continue;
    const ang=aLo+Math.random()*(aHi-aLo);
    const [x,y]=pol(CX,CY,rr,ang);
    if(keepOut&&(x-keepOut[0])**2+(y-keepOut[1])**2<keepOut[2]**2) continue;
    if(pts.every(p=>(p[0]-x)**2+(p[1]-y)**2>(PHOTO_R*2+3)**2)) pts.push([x,y]);
  }
  return pts;
}

function photoAt(el,defs,it,x,y,key,idx){
  const r=PHOTO_R, cid='c'+key+idx+Math.floor(Math.random()*1e6);
  const cp=document.createElementNS(NS,'clipPath'); cp.id=cid;
  const cc=document.createElementNS(NS,'circle');
  cc.setAttribute('cx',x); cc.setAttribute('cy',y); cc.setAttribute('r',r);
  cp.appendChild(cc); defs.appendChild(cp);
  const gi=document.createElementNS(NS,'g'); gi.setAttribute('class','chipimg');
  const im=document.createElementNS(NS,'image');
  im.setAttribute('href',it.photo);
  im.setAttribute('x',x-r); im.setAttribute('y',y-r);
  im.setAttribute('width',r*2); im.setAttribute('height',r*2);
  im.setAttribute('preserveAspectRatio','xMidYMid slice');
  im.setAttribute('clip-path','url(#'+cid+')');
  const rg=document.createElementNS(NS,'circle');
  rg.setAttribute('cx',x); rg.setAttribute('cy',y); rg.setAttribute('r',r);
  gi.appendChild(im); gi.appendChild(rg); el.appendChild(gi);
}

function rgbOf(hex){
  const m=/^#?([0-9a-f]{6})$/i.exec(hex||'');
  if(!m) return [90,100,120];
  const n=parseInt(m[1],16);
  return [(n>>16)&255,(n>>8)&255,n&255];
}
function lum(r,g,b){ return 0.299*r+0.587*g+0.114*b; }
function isLight(hex){ const [r,g,b]=rgbOf(hex); return lum(r,g,b)>150; }

// ラベルはそのゾーンの色で書く（ブルーなら「ブルー43」ごとブルー）。
// ただし外側の輪は明るいページ背景の上に載るので、
// 明るすぎる色はそのままだと読めない。読める濃さまで落とす。
function labelColor(hex){
  let [r,g,b]=rgbOf(hex);
  let n=0;
  while(lum(r,g,b)>150 && n++<12){ r*=0.86; g*=0.86; b*=0.86; }
  return 'rgb('+Math.round(r)+','+Math.round(g)+','+Math.round(b)+')';
}

function label(el,x,y,text,count,inner,swatch){
  // 内側の輪は扇の上に文字が載るので、色はそのまま使い、
  // 下地と同化しないよう縁取りの色だけ明暗を入れ替える。
  const fill = inner ? swatch : labelColor(swatch);
  const edge = inner ? (isLight(swatch) ? 'rgba(0,0,0,.55)' : 'rgba(255,255,255,.85)') : '#fff';
  for(const [cls,val,dy] of [['zlabel',text,0],['zcount',count,15]]){
    const t=document.createElementNS(NS,'text');
    t.setAttribute('class',cls);
    t.setAttribute('x',x); t.setAttribute('y',y+dy);
    t.setAttribute('text-anchor','middle');
    t.setAttribute('fill',fill);
    t.setAttribute('stroke',edge);
    t.textContent=val;
    el.appendChild(t);
  }
}

function build(){
  svg.textContent='';
  const defs=document.createElementNS(NS,'defs');
  svg.appendChild(defs);

  // 1台も無いゾーンは幅を 1/3 にする。消さないのは、
  // あとから手で色を付けたときに元の幅へ戻るようにするため。
  function layout(keys,r1,r2,offset){
    const wsum=keys.reduce((s,k)=>s+((byZone[k]||[]).length?1:EMPTY_SHARE),0);
    let a=offset;
    return keys.map(key=>{
      const wgt=((byZone[key]||[]).length?1:EMPTY_SHARE)/wsum*360;
      const g={key,a1:a,a2:a+wgt,r1,r2}; a+=wgt; return g;
    });
  }

  for(const g of [...layout(OUTER,R_MID,R_OUT,0),...layout(INNER,R_IN,R_MID-6,18)]){
    const z=zmap[g.key], list=byZone[g.key]||[];
    const el=document.createElementNS(NS,'g');
    el.setAttribute('class','g'+(list.length?'':' empty'));
    el.dataset.zone=g.key;
    el.setAttribute('role','button');
    el.setAttribute('tabindex', list.length?'0':'-1');
    el.setAttribute('aria-label',z.label+' '+list.length+'台');

    const p=document.createElementNS(NS,'path');
    p.setAttribute('class','sect');
    p.setAttribute('d',ring(CX,CY,g.r1,g.r2,g.a1,g.a2));
    p.setAttribute('fill',z.swatch);
    p.setAttribute('stroke','#fff'); p.setAttribute('stroke-width','2');
    el.appendChild(p);

    const outer=g.r2>R_MID, mid=(g.a1+g.a2)/2;
    const [lx,ly]=outer?pol(CX,CY,LABEL_R,mid):pol(CX,CY,R_IN+22,mid);
    const keepOut=outer?null:[lx,ly,46];
    const pool=shuffle(list.slice()).slice(0,outer?5:3);
    const pts=scatter(g.a1,g.a2,g.r1,g.r2,pool.length,keepOut);
    pool.forEach((it,i)=>{ if(pts[i]) photoAt(el,defs,it,pts[i][0],pts[i][1],g.key,i); });
    label(el,lx,ly,z.label,list.length,!outer,z.swatch);

    el.addEventListener('click',()=>select(g.key));
    el.addEventListener('keydown',e=>{
      if(e.key==='Enter'||e.key===' '){ select(g.key); e.preventDefault(); }
    });
    svg.appendChild(el);
  }

  // 中心＝カラフル。SVGに円錐グラデーションは無いので細い扇を並べる。
  const z=zmap[CENTER], list=byZone[CENTER]||[];
  const el=document.createElementNS(NS,'g');
  el.setAttribute('class','g'+(list.length?'':' empty'));
  el.dataset.zone=CENTER;
  el.setAttribute('role','button');
  el.setAttribute('tabindex', list.length?'0':'-1');
  el.setAttribute('aria-label',z.label+' '+list.length+'台');
  const RC=R_IN-6, hues=['#e5342c','#f07a1a','#f5c518','#2fae5a','#2277dd','#8b5cf6','#ef5da8'];
  for(let i=0;i<24;i++){
    const w=document.createElementNS(NS,'path');
    w.setAttribute('class','sect');
    w.setAttribute('d',ring(CX,CY,0,RC,i*15,(i+1)*15+0.6));
    w.setAttribute('fill',hues[i%%hues.length]);
    el.appendChild(w);
  }
  const rim=document.createElementNS(NS,'circle');
  rim.setAttribute('cx',CX); rim.setAttribute('cy',CY); rim.setAttribute('r',RC);
  rim.setAttribute('fill','none'); rim.setAttribute('stroke','#fff');
  rim.setAttribute('stroke-width','2'); el.appendChild(rim);
  const pts=scatter(0,360,26,RC,3,[CX,CY,26]);
  shuffle(list.slice()).slice(0,3).forEach((it,i)=>{
    if(pts[i]) photoAt(el,defs,it,pts[i][0],pts[i][1],'mc',i);
  });
  const pill=document.createElementNS(NS,'circle');
  pill.setAttribute('cx',CX); pill.setAttribute('cy',CY); pill.setAttribute('r',30);
  pill.setAttribute('fill','rgba(20,26,36,.74)'); pill.setAttribute('class','chipimg');
  el.appendChild(pill);
  label(el,CX,CY+2,z.label,list.length,true,'#ffffff');
  el.addEventListener('click',()=>select(CENTER));
  el.addEventListener('keydown',e=>{
    if(e.key==='Enter'||e.key===' '){ select(CENTER); e.preventDefault(); }
  });
  svg.appendChild(el);

  mark();
}

function mark(){
  for(const g of svg.querySelectorAll('.g')){
    const on=g.dataset.zone===cur;
    g.classList.toggle('on',on);
    g.classList.toggle('dim',!!cur&&!on&&!g.classList.contains('empty'));
    g.setAttribute('aria-pressed',on?'true':'false');
  }
}

function select(key){
  cur=(cur===key)?null:key;
  mark(); render();
}

function esc(s){ return String(s||'').replace(/[&<>"']/g,
  c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#x27;'}[c])); }

function render(){
  const list=cur?(byZone[cur]||[]):DATA;
  const z=cur?zmap[cur]:null;
  const title=document.getElementById('title');
  title.textContent=z?z.label+' のマシン':'すべてのマシン';
  title.style.color=z?labelColor(z.swatch):'';
  document.getElementById('num').textContent=list.length+' 台';
  document.getElementById('clear').hidden=!cur;
  document.getElementById('grid').innerHTML=list.map(it=>{
    const zz=zmap[it.color]||{label:it.color,swatch:'#888'};
    return '<a class="card" href="'+esc(it.url)+'" target="_blank" rel="noopener">'+
      '<img src="'+esc(it.photo)+'" alt="" loading="lazy" referrerpolicy="no-referrer">'+
      '<div class="m"><span class="badge" style="--c:'+zz.swatch+'"><i></i>'+esc(zz.label)+'</span>'+
      '<span class="t">'+esc(it.memo)+'</span>'+
      '<span class="u">@'+esc(it.handle)+'</span></div></a>';
  }).join('');
}

document.getElementById('reshuffle').addEventListener('click',build);
document.getElementById('clear').addEventListener('click',()=>{
  cur=null; mark(); render();
});
build(); render();
"""


def page(zones: list, items: list, site_url: str, site_name: str) -> str:
    """colors.html の中身を作る。"""
    js = JS % {
        "items": json.dumps(items, ensure_ascii=False, separators=(",", ":")),
        "zones": json.dumps(zones, ensure_ascii=False, separators=(",", ":")),
        "outer": json.dumps(RING_OUTER),
        "inner": json.dumps(RING_INNER),
        "center": json.dumps(CENTER),
    }
    desc = ("X に投稿されたミニ四駆のマシンを、色から探せるページです。"
            "写真の専有面積がいちばん多い色でマシンを分類しています。")
    title = "マシンカラーで探す｜ミニ四駆の作品を色から｜" + site_name
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(desc)}">
<link rel="canonical" href="{site_url}/{PAGE}">
<link rel="icon" href="assets/favicon.ico?v=2" sizes="any">
<link rel="icon" type="image/png" sizes="32x32" href="assets/favicon-32.png?v=2">
<link rel="apple-touch-icon" href="assets/apple-touch-icon.png?v=2">
<meta name="theme-color" content="#d81f2a">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{html.escape(site_name)}">
<meta property="og:title" content="マシンカラーで探す｜ミニ四駆の作品を色から">
<meta property="og:description" content="{html.escape(desc)}">
<meta property="og:url" content="{site_url}/{PAGE}">
<meta property="og:image" content="{site_url}/assets/icon-512.png">
<meta property="og:locale" content="ja_JP">
<meta name="twitter:card" content="summary">
<script type="application/ld+json">{{"@context":"https://schema.org","@type":"WebPage",\
"url":"{site_url}/{PAGE}","name":"マシンカラーで探す","description":"{desc}","inLanguage":"ja",\
"isPartOf":{{"@id":"{site_url}/#website"}},"breadcrumb":{{"@type":"BreadcrumbList",\
"itemListElement":[{{"@type":"ListItem","position":1,"name":"{site_name}","item":"{site_url}/"}},\
{{"@type":"ListItem","position":2,"name":"マシンカラーで探す"}}]}}}}</script>
<style>{CSS}</style>
</head>
<body>
<div class="topbar">
  <header>
    <a class="logo" href="index.html"><img src="assets/logo-title.png?v=3"
       width="462" height="86" alt="{html.escape(site_name)}" fetchpriority="high"
       decoding="async"></a>
    <a class="back" href="index.html">← パーツカタログへ戻る</a>
  </header>
</div>

<div class="wrap">
  <!-- 見出しは画面には出さない。検索と読み上げのために文字だけ残す。 -->
  <h1 class="sr">マシンカラーで探す｜X に投稿されたミニ四駆の作品を色から</h1>

  <div class="wheelbox">
    <div class="wheel"><svg id="wheel" viewBox="0 0 560 560" role="group"
      aria-label="色で絞り込むカラーホイール"></svg></div>
    <!-- 配置のシャッフルは機能を残したまま隠してある。
         出したくなったら hidden を外すだけでよい。 -->
    <button class="reshuffle" id="reshuffle" type="button" hidden>配置をシャッフル</button>
  </div>

  <div id="result">
    <div class="head"><h2 id="title"></h2><span class="n" id="num"></span>
      <button class="clear" id="clear" type="button" hidden>解除</button></div>
    <div class="grid" id="grid"></div>
  </div>
</div>

<footer>
  <p>写真は各投稿者のものです。カードを押すと元の投稿へ移動します。
  掲載の取り下げをご希望の方は X からご連絡ください。</p>
</footer>

<script>{js}</script>
</body>
</html>
"""


def write(outdir: str, site_url: str, site_name: str) -> str:
    """colors.html を書き出す。データが無ければ何もしない。"""
    zones, items = load()
    if not zones or not items:
        return ""
    path = os.path.join(outdir, PAGE)
    with open(path, "w", encoding="utf-8") as f:
        f.write(page(zones, items, site_url, site_name))
    return path
