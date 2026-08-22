# -*- coding: utf-8 -*-
"""スプレーカラーMAP UI（CSS / JS / HTML）。

本番の build_official_index.py と、デザイン確認用の preview_colormap.py の
両方がこのモジュールを使う。両者で見た目が食い違わないようにするため。
"""
import html

import paint_colors as PC

MARKS = {"METALLIC": "M", "PEARL": "P", "FLUORESCENT": "F", "CLEAR": "C"}
HUE_SWATCH = {"レッド": "#d0202a", "オレンジ": "#ef7a1a", "イエロー": "#f2c31d",
              "グリーン": "#1e9c50", "スカイ": "#3fb8e0", "ブルー": "#1a5fc8",
              "パープル": "#7b3fa0", "ピンク": "#e86a9a"}
# シリーズボタン（中カテゴリと1対1で対応させる）。key は data-series の値。
SERIES = [("ALL", "ALL"), ("ポリカ", "ポリカ"), ("TS", "TS"), ("AS", "AS"),
          ("ラッカー", "ラッカー"), ("アクリル", "アクリル"), ("エナメル", "エナメル")]
EFFECTS = ["ALL", "STANDARD", "METALLIC", "PEARL", "FLUORESCENT", "CLEAR"]

CSS = """
/* ---- スプレーカラーMAP ---- */
/* 常にフローティング（下からせり上がるシート）。ページ中段には置かない。 */
.cmap{position:fixed;left:0;right:0;bottom:0;z-index:80;margin:0 auto;max-width:1120px;
background:var(--surface);border:1px solid var(--line);border-top:none;
border-radius:14px 14px 0 0;max-height:84vh;display:none;flex-direction:column;
box-shadow:0 -10px 30px rgba(20,40,80,.3);transform:translateY(100%);
transition:transform .24s ease-out}
.cmap.mounted{display:flex}
.cmap.shown{transform:translateY(0)}
.cmap-head{width:100%;display:flex;align-items:center;gap:10px;padding:10px 14px;
background:none;border:none;cursor:pointer;font:inherit;color:inherit;text-align:left}
.cmap-head:hover{background:var(--brand-soft)}
.cmap-head:focus-visible{outline:2px solid var(--brand);outline-offset:-2px}
/* 開閉ボタンはテキストの前。押せることが分かるよう太く目立たせる */
.cmap-toggle{width:34px;height:34px;flex:none;border-radius:8px;background:var(--brand);
color:#fff;display:flex;align-items:center;justify-content:center;
box-shadow:0 2px 6px rgba(18,86,196,.35)}
.cmap-head:hover .cmap-toggle{background:#0e46a0}
.cmap-chev{width:20px;height:20px;transition:transform .2s;stroke-width:3.4}
.cmap-head[aria-expanded="true"] .cmap-chev{transform:rotate(180deg)}
/* カテゴリ内の代表色を3つ見せて、中身があることを示す */
.cmap-swatches{display:flex;gap:3px;flex:none}
.cmap-swatches i{width:16px;height:16px;border-radius:3px;border:1px solid rgba(0,0,0,.22);
display:block;transition:background .2s}
.cmap-title{font-weight:800;font-size:13px;letter-spacing:.06em}
.cmap-sub{font-size:11px;color:var(--ink3);flex:1}
.cmap-head{position:sticky;top:0;background:var(--surface);z-index:1;
border-bottom:1px solid var(--line)}
.cmap-body{display:block;padding:12px 14px 18px;overflow-y:auto;
-webkit-overflow-scrolling:touch;flex:1}
.cmap-chev{transform:rotate(180deg)}          /* 閉じる向き（下向き）で固定 */
.cmap-head[aria-expanded="true"] .cmap-chev{transform:rotate(180deg)}
.frow{display:flex;gap:6px;flex-wrap:wrap;align-items:center;margin-bottom:8px}
.frow-label{font-size:10px;font-weight:800;color:var(--ink3);letter-spacing:.08em;width:52px;flex:none}
.fbtn{border:1.5px solid var(--line);background:var(--surface);border-radius:999px;
padding:5px 14px;font-size:11.5px;font-weight:700;cursor:pointer;font-family:inherit;color:var(--ink2)}
.fbtn[aria-pressed="true"]{background:var(--brand);border-color:var(--brand);color:#fff}
.fbtn.series[aria-pressed="true"]{background:var(--ink);border-color:var(--ink)}
.cmap-note{display:none;font-size:10.5px;color:var(--ink3);margin:2px 0 10px}
.cmap-note.show{display:block}

/* 横スクロール。標準のバーはスマホで表示されないため、自前の太いバーを置く */
.cmap-scroll{overflow-x:auto;overflow-y:hidden;-webkit-overflow-scrolling:touch;
scrollbar-width:none}
.cmap-scroll::-webkit-scrollbar{display:none}
.cmap-inner{min-width:660px}
.cmap-bar{height:26px;background:#eceff3;border-radius:13px;margin:2px 0 8px;
position:relative;touch-action:none;cursor:grab;display:none}
.cmap-bar.on{display:block}
.cmap-bar:active{cursor:grabbing}
.cmap-bar-thumb{position:absolute;top:3px;bottom:3px;left:0;min-width:56px;
background:#b6bcc6;border-radius:10px;transition:background .15s}
.cmap-bar:hover .cmap-bar-thumb{background:#98a0ac}
.cmap-bar-thumb::after{content:"";position:absolute;top:50%;left:50%;width:18px;height:2px;
transform:translate(-50%,-50%);background:rgba(255,255,255,.9);border-radius:2px;
box-shadow:0 -5px 0 rgba(255,255,255,.9),0 5px 0 rgba(255,255,255,.9)}

/* 2Dマップ（縦＝色相 / 横＝明るさ）。色相は細い縦帯で示す */
.grid2d{display:grid;grid-template-columns:14px repeat(4,max-content);gap:4px;align-items:stretch}
.hhead{font-size:10.5px;font-weight:700;color:var(--ink2);text-align:center;padding:1px 0}
.lhead{border-radius:4px;min-height:100%}
/* ピンは縦2段まで。増えたぶんは横に伸ばす */
.cell{background:#fafbfc;border:1px solid var(--line);border-radius:6px;min-height:52px;
padding:5px;display:grid;grid-auto-flow:column;grid-template-rows:repeat(2,auto);
gap:4px;justify-content:start;align-content:start}
.cell.empty{min-height:22px;padding:2px;display:block}
.band{background:#fafbfc;border:1px solid var(--line);border-radius:6px;padding:6px;
display:flex;flex-wrap:wrap;gap:5px}
.zone-label{font-size:10.5px;font-weight:800;color:var(--ink3);letter-spacing:.08em;margin:12px 0 5px}

/* ピン */
.pin{position:relative;width:46px;height:40px;border-radius:7px;border:1px solid rgba(0,0,0,.18);
cursor:pointer;padding:0;font:inherit;display:flex;align-items:flex-end;justify-content:center;
overflow:hidden;flex:none}
.pin:focus-visible{outline:2px solid var(--brand);outline-offset:2px}
.pin .lbl{width:100%;font-size:8.5px;font-weight:800;line-height:1.55;text-align:center;
background:rgba(255,255,255,.88);color:#1a2233;letter-spacing:-.03em}
.pin.on{box-shadow:0 0 0 3px var(--brand);border-color:var(--brand)}
.pin.hide{display:none}
.pin[data-effect="METALLIC"]::before,.pin[data-effect="PEARL"]::before,
.pin[data-effect="FLUORESCENT"]::before,.pin[data-effect="CLEAR"]::before{
content:attr(data-mark);position:absolute;top:0;right:2px;font-size:8px;font-weight:800;
color:#fff;text-shadow:0 0 2px rgba(0,0,0,.85)}
.cmap-legend{font-size:10.5px;color:var(--ink3);margin-top:10px}
.cmap-tip{position:fixed;z-index:60;background:#1a2233;color:#fff;font-size:11px;font-weight:600;
padding:4px 8px;border-radius:5px;pointer-events:none;opacity:0;transition:opacity .12s;white-space:nowrap}
.cmap-tip.show{opacity:1}
.it.flash{animation:cmapflash 2.4s ease-out}
@keyframes cmapflash{0%,55%{box-shadow:0 0 0 3px var(--accent);border-color:var(--accent)}
100%{box-shadow:0 0 0 0 rgba(0,0,0,0);border-color:var(--line)}}
@media(max-width:900px){.frow-label{width:100%}}

/* ---- スマホ用：円グラフボタン＋ボトムシート ---- */
.cmap-fab{position:fixed;right:14px;bottom:16px;z-index:70;width:58px;height:58px;border-radius:50%;
border:3px solid #fff;padding:0;cursor:pointer;display:none;
box-shadow:0 4px 14px rgba(20,40,80,.32)}
.cmap-fab.on{display:block}
.cmap-fab:focus-visible{outline:3px solid var(--brand);outline-offset:3px}
.cmap-fab .sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}

.cmap-backdrop{position:fixed;inset:0;background:rgba(16,22,34,.42);z-index:79;
opacity:0;pointer-events:none;transition:opacity .2s}
.cmap-backdrop.shown{opacity:1;pointer-events:auto}
"""

# 既存の apply() / syncChips() と連動させる前提のスクリプト
JS = """
// ---- スプレーカラーMAP ----
const CMAP_KEY='mini4rinku:cmapOpen';
const SERIES_CAT={'ポリカ':'ポリカーボネートスプレー',TS:'タミヤスプレー',AS:'エアーモデルスプレー','ラッカー':'ラッカー塗料','アクリル':'アクリル塗料ミニ','エナメル':'エナメル塗料'};
const cmap=document.querySelector('.cmap');
if(cmap){
  const cmapHead=cmap.querySelector('.cmap-head');
  const pins=[...cmap.querySelectorAll('.pin')];
  const note=cmap.querySelector('.cmap-note');
  const tip=document.getElementById('cmapTip');
  let effect='ALL', activePin=null;


  // 中カテゴリ（チップ）と連動する。どちらを押しても状態は1つ。
  cmap.querySelectorAll('.fbtn.series').forEach(b => b.addEventListener('click', () => {
    cat = SERIES_CAT[b.dataset.series] || '';
    chips.forEach(c => c.classList.toggle('on', c.dataset.cat === cat));
    apply();
  }));
  cmap.querySelectorAll('.fbtn.effect').forEach(b => b.addEventListener('click', () => {
    effect=b.dataset.effect;
    cmap.querySelectorAll('.fbtn.effect').forEach(x =>
      x.setAttribute('aria-pressed', x===b ? 'true':'false'));
    paintPins();
  }));

  window.paintPins = function(){
    for(const p of pins){
      const okCat = !cat || p.dataset.cname===cat;
      const okEff = effect==='ALL' || p.dataset.effect===effect;
      p.classList.toggle('hide', !(okCat && okEff));
    }
    const cur=Object.keys(SERIES_CAT).find(k => SERIES_CAT[k]===cat) || 'ALL';
    cmap.querySelectorAll('.fbtn.series').forEach(x =>
      x.setAttribute('aria-pressed', x.dataset.series===cur ? 'true':'false'));
    note.classList.toggle('show', cur==='ポリカ');
    // 代表色は「赤系・青緑系・黄橙系」から1つずつ拾う。カテゴリを変えると色も変わる。
    const shownPins=pins.filter(p => !p.classList.contains('hide'));
    const FAMILY=[['レッド','ピンク'],['ブルー','スカイ','グリーン'],['イエロー','オレンジ']];
    const reps=FAMILY.map(fam => {
      const cand=shownPins.filter(p => fam.includes(p.dataset.hue));
      return cand.length ? cand[Math.floor(cand.length/2)].style.backgroundColor : null;
    });
    const fallback=shownPins.length ? shownPins[Math.floor(shownPins.length/2)].style.backgroundColor : '#e3e6ec';
    const cols=reps.map(c => c || fallback);
    const sw=cmap.querySelectorAll('.cmap-swatches i');
    for(let i=0;i<sw.length;i++) sw[i].style.background=cols[i];
    if(window.paintFab) paintFab(cols);
    // 塗装タブのときだけ円グラフボタンを出す
    const fabEl=document.querySelector('.cmap-fab');
    if(fabEl) fabEl.classList.toggle('on', genre==='paint');
    // 塗装タブに切り替わった直後は幅が確定していないので、描画後に測り直す
    if(window.syncCmapBar) setTimeout(window.syncCmapBar, 0);
  };

  pins.forEach(p => p.addEventListener('click', () => {
    if(activePin) activePin.classList.remove('on');
    p.classList.add('on'); activePin=p;
    // 対象が別ページにいることがあるので、まずそのページへ切り替える。
    // カードは表示中のページぶんしか作られていないため、切り替えたあとに取り直す。
    if(window.revealCard && !revealCard(p.dataset.item)) return;
    const card=document.getElementById(p.dataset.target);
    if(!card) return;
    closeSheet();
    setTimeout(() => {
      card.scrollIntoView({behavior:'smooth', block:'center'});
      card.classList.remove('flash');
      void card.offsetWidth;
      card.classList.add('flash');
    }, 16);
  }));

  function showTip(e){
    const p=e.currentTarget;
    tip.textContent=p.dataset.code+' '+p.dataset.color;
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

  // ---- スマホ：円グラフボタンとボトムシート ----
  const fab=document.querySelector('.cmap-fab');
  const backdrop=document.querySelector('.cmap-backdrop');

  function openSheet(){
    cmap.classList.add('mounted');
    backdrop.hidden=false;
    void cmap.offsetHeight;          // 位置を確定させてから出す
    setTimeout(() => {
      cmap.classList.add('shown');
      backdrop.classList.add('shown');
      cmapHead.setAttribute('aria-expanded','true');
      fab.setAttribute('aria-expanded','true');
      if(window.syncCmapBar) syncCmapBar();
    }, 16);
  }
  function closeSheet(){
    if(!cmap.classList.contains('mounted')) return;
    cmap.classList.remove('shown');
    backdrop.classList.remove('shown');
    cmapHead.setAttribute('aria-expanded','false');
    fab.setAttribute('aria-expanded','false');
    setTimeout(() => {
      cmap.classList.remove('mounted');
      backdrop.hidden=true;
    }, 240);
  }
  window.closeCmapSheet=closeSheet;

  fab.addEventListener('click', openSheet);
  backdrop.addEventListener('click', closeSheet);
  document.addEventListener('keydown', e => { if(e.key==='Escape') closeSheet(); });
  cmapHead.addEventListener('click', closeSheet);   // 見出しは閉じるボタン

  // 円グラフを120度ずつ3色で描く。カテゴリ切替に追従する。
  window.paintFab = function(cols){
    const [a,b,c]=cols;
    fab.style.background='conic-gradient('+a+' 0deg 120deg,'+b+' 120deg 240deg,'+c+' 240deg 360deg)';
  };

  // 自前の横スクロールバー（標準バーはスマホで出ないため）
  const sc=cmap.querySelector('.cmap-scroll');
  const bar=cmap.querySelector('.cmap-bar');
  const thumb=cmap.querySelector('.cmap-bar-thumb');
  function syncBar(){
    const max=sc.scrollWidth-sc.clientWidth;
    if(max<=1){ bar.classList.remove('on'); return; }
    bar.classList.add('on');
    const ratio=sc.clientWidth/sc.scrollWidth;
    const w=Math.max(56, bar.clientWidth*ratio);
    thumb.style.width=w+'px';
    thumb.style.left=(sc.scrollLeft/max)*(bar.clientWidth-w)+'px';
    bar.setAttribute('aria-valuenow', Math.round(sc.scrollLeft/max*100));
  }
  window.syncCmapBar = syncBar;
  sc.addEventListener('scroll', syncBar, {passive:true});
  // 端末によっては scroll が間引かれるため、指・ホイール操作でも直接更新する
  sc.addEventListener('touchmove', syncBar, {passive:true});
  sc.addEventListener('wheel', syncBar, {passive:true});
  window.addEventListener('resize', syncBar);

  let dragging=false;
  function moveTo(clientX){
    const r=bar.getBoundingClientRect();
    const w=thumb.offsetWidth;
    const x=Math.max(0, Math.min(r.width-w, clientX-r.left-w/2));
    sc.scrollLeft=(x/(r.width-w))*(sc.scrollWidth-sc.clientWidth);
  }
  bar.addEventListener('pointerdown', e => {
    dragging=true; bar.setPointerCapture(e.pointerId); moveTo(e.clientX); e.preventDefault();
  });
  bar.addEventListener('pointermove', e => { if(dragging) moveTo(e.clientX); });
  bar.addEventListener('pointerup', () => { dragging=false; });
  bar.addEventListener('pointercancel', () => { dragging=false; });
  bar.addEventListener('keydown', e => {
    const step=sc.clientWidth*0.4;
    if(e.key==='ArrowLeft'){ sc.scrollLeft-=step; e.preventDefault(); }
    if(e.key==='ArrowRight'){ sc.scrollLeft+=step; e.preventDefault(); }
  });
  cmapHead.addEventListener('click', () => setTimeout(syncBar, 0));
  syncBar();

  paintPins();
}
"""


def _pin(r: dict) -> str:
    code = PC.code_of(r["name"]) or r["item_code"]
    return (f'<button class="pin" style="background:{r["swatch"]}" '
            f'data-target="item-{r["item_code"]}" data-item="{r["item_code"]}" '
            f'data-effect="{r["effect"]}" '
            f'data-series="{r["series"]}" data-cname="{html.escape(r["official_category"])}" '
            f'data-hue="{html.escape(r["hue_band"])}" '
            f'data-code="{html.escape(code)}" data-color="{html.escape(r["color_name"])}" '
            f'data-mark="{MARKS.get(r["effect"], "")}" '
            f'aria-label="{html.escape(code)} {html.escape(r["color_name"])} へ移動">'
            f'<span class="lbl">{html.escape(code)}</span></button>')


def _map_grid(rows: list[dict]) -> str:
    hues = [b for b, _, _ in PC.HUE_BANDS]
    lights = [b for b, _, _ in PC.LIGHT_BANDS]
    out = ['<div class="grid2d">', '<div></div>']
    out += [f'<div class="hhead">{html.escape(l)}</div>' for l in lights]
    for hue in hues:
        out.append(f'<div class="lhead" style="background:{HUE_SWATCH.get(hue, "#ccc")}" '
                   f'title="{html.escape(hue)}" aria-label="{html.escape(hue)}"></div>')
        for lb in lights:
            cell = [r for r in rows if r["zone"] == "MAP"
                    and r["hue_band"] == hue and r["light_band"] == lb]
            cls = "cell" if cell else "cell empty"
            out.append(f'<div class="{cls}">' + "".join(_pin(r) for r in cell) + '</div>')
    out.append('</div>')
    for zone, title in [("NEUTRAL", "NEUTRAL ／ 白・グレー・黒"),
                        ("SPECIAL", "SPECIAL ／ クリヤー・特殊")]:
        band = [r for r in rows if r["zone"] == zone]
        out.append(f'<div class="zone-label">{html.escape(title)}（{len(band)}）</div>')
        out.append('<div class="band">' + "".join(_pin(r) for r in band) + '</div>')
    return "\n".join(out)


def section(rows: list[dict]) -> str:
    """カラーマップのHTML（塗装タブ選択時だけ表示される）。"""
    sbtn = "".join(
        f'<button class="fbtn series" data-series="{k}" type="button" '
        f'aria-pressed="{"true" if k == "ALL" else "false"}">{html.escape(lb)}</button>'
        for k, lb in SERIES)
    ebtn = "".join(
        f'<button class="fbtn effect" data-effect="{e}" type="button" '
        f'aria-pressed="{"true" if e == "ALL" else "false"}">{e}</button>'
        for e in EFFECTS)
    return f"""  <section class="cmap">
    <button class="cmap-head" type="button" aria-expanded="false" aria-controls="cmapBody">
      <span class="cmap-toggle" aria-hidden="true">
        <svg class="cmap-chev" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg>
      </span>
      <span class="cmap-swatches" aria-hidden="true"><i></i><i></i><i></i></span>
      <span class="cmap-title">SPRAY COLOR MAP</span>
      <span class="cmap-sub">色から探す（{len(rows)}色）</span>
    </button>
    <div class="cmap-body" id="cmapBody">
      <div class="frow"><span class="frow-label">シリーズ</span>{sbtn}</div>
      <div class="frow"><span class="frow-label">色特性</span>{ebtn}</div>
      <p class="cmap-note">PSはポリカボディ専用の塗装スプレーです。</p>
      <div class="cmap-bar" role="scrollbar" aria-label="カラーマップを横に動かす"
           aria-controls="cmapBody" aria-orientation="horizontal" tabindex="0">
        <div class="cmap-bar-thumb"></div>
      </div>
      <div class="cmap-scroll"><div class="cmap-inner">
{_map_grid(rows)}
      </div></div>
      <div class="cmap-legend">縦軸＝色相／横軸＝明るさ。ピンを押すと該当商品へ移動します。
      記号 M=メタリック P=パール F=蛍光 C=クリヤー</div>
    </div>
  </section>
  <div class="cmap-backdrop" hidden></div>
  <button class="cmap-fab" type="button" aria-expanded="false" aria-controls="cmapBody">
    <span class="sr">スプレーカラーMAPを開く</span>
  </button>"""
