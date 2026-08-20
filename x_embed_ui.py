# -*- coding: utf-8 -*-
"""TOPにX（旧Twitter）の投稿を2件横並びでランダム表示する（CSS / JS / HTML）。

投稿は docs/data/x-featured-posts.json で管理する。JSONに1件足すだけで
候補が増え、このファイルを触る必要はない。

左右どちらへスワイプしても、新しい2件がランダムで読み込まれる。
直近に出した投稿は displaySettings.avoidRecentCount 件だけ抽選から外す。

表示はX公式の Embedded Post（widgets.js の createTweet）に任せる。
投稿本文・投稿者情報・メディア・Xロゴの描画には手を加えず、
高さも固定しない（クロップ禁止）。スマホでは2件を画面内に収めるため
CSSの transform で等倍縮小するだけで、中身は一切いじらない。

読み込みに失敗した場合は表示領域ごと隠し、サイト本体には影響させない。
入れ替えに失敗した場合は、いま出ている2件をそのまま残す。
"""

DATA_URL = "data/x-featured-posts.json"

CSS = """
/* ---- X投稿（TOPに2件、スワイプで入れ替え） ---- */
/* --xw = Xに描画させる素の幅 / --xs = 画面に収めるための縮小率 */
#xFeatured{--xw:250px;--xs:1;--xgap:8px;
max-width:980px;margin:0 auto 10px;padding:0;position:relative}
#xFeatured[hidden]{display:none}
/* 読み込み中の控えめなプレースホルダー。描画されたら自然に置き換わる */
#xFeatured.loading{min-height:120px;border:1px solid var(--line);border-radius:10px;
background:var(--surface)}
#xFeatured .xph{display:flex;align-items:center;justify-content:center;min-height:120px;
font-size:11px;color:var(--ink3)}
#xFeatured.done{min-height:0;border:none;background:none}

/* スワイプを受ける器。縦スクロールは殺さない */
.xstage{position:relative;overflow:hidden;touch-action:pan-y}
.xpair{display:flex;gap:var(--xgap);justify-content:center;align-items:flex-start;
will-change:transform,opacity}
.xpair.anim{transition:transform .22s ease,opacity .22s ease}
.xpair.toLeft{transform:translateX(-14%);opacity:0}
.xpair.toRight{transform:translateX(14%);opacity:0}
/* 次の2件は、いまの2件の上に重ねたまま描き切る（iframeを動かさない） */
.xpair.staging{position:absolute;left:0;right:0;top:0;opacity:0;pointer-events:none}
/* 素の幅で描いたツイートを、枠の側で縮めて置く */
.xslot{flex:0 0 auto;width:calc(var(--xw) * var(--xs));overflow:hidden}
.xslot > .xinner{width:var(--xw);transform:scale(var(--xs));transform-origin:top left}
.xslot .twitter-tweet{margin:0 !important}

/* 送り操作 */
.xnav{display:flex;align-items:center;justify-content:center;gap:10px;margin-top:6px}
.xnav button{min-width:34px;height:28px;padding:0 10px;border:1.5px solid var(--line);
background:var(--surface);color:var(--ink2);border-radius:5px;font:inherit;font-size:13px;
font-weight:700;cursor:pointer;line-height:1}
.xnav button:hover:not(:disabled){border-color:var(--brand);color:var(--brand)}
.xnav button:disabled{opacity:.35;cursor:default}
.xhint{font-size:10.5px;color:var(--ink3)}
.xhint::after{content:"ボタンで次の2件"}

@media(max-width:900px){
  /* 2件を画面内に収めたいので、この区画だけ左右の余白を8px詰める */
  #xFeatured{max-width:none;margin-left:-8px;margin-right:-8px}
  .xhint::after{content:"スワイプで次の2件"}
}
@media(prefers-reduced-motion:reduce){
  .xpair.anim{transition:opacity .15s ease}
  .xpair.toLeft,.xpair.toRight{transform:none}
}
"""

JS = """
// ---- X投稿を2件ランダム表示し、スワイプで入れ替える ----
// 失敗しても本体に影響させない。何かあれば領域ごと隠す。
(() => {
  const HOST = document.getElementById('xFeatured');
  if(!HOST) return;

  const DATA_URL = '%DATA_URL%';
  const RECENT_KEY = 'm4rinku:x-recent-post-ids';
  const RENDER_TIMEOUT = 8000;
  const ANIM_MS = 220;
  const NATURAL_MOBILE = 250;   // Xの埋め込みが受け付ける最小幅
  const NATURAL_DESKTOP = 400;  // PCは縮小せずこの幅で並べる
  const SWIPE_MIN = 40;         // これ未満は誤タッチ扱い
  const DEFAULTS = {maxPosts:2, random:true, avoidRecentCount:8,
                    autoRotate:false, hideThread:true, dnt:true, lang:'ja'};

  let cfg = DEFAULTS, allPosts = [], scale = 1, natural = NATURAL_MOBILE;
  let stage = null, nav = null, current = null, busy = false;

  const giveUp = (why) => {
    if(why) console.warn('[x-featured]', why);
    HOST.hidden = true;
    HOST.classList.remove('loading');
    HOST.innerHTML = '';
  };

  // 投稿URLから数値のIDを取り出す。x.com / twitter.com、末尾のクエリに対応。
  function tweetIdOf(url){
    if(typeof url !== 'string') return '';
    const m = url.match(/(?:twitter|x)\\.com\\/[^/]+\\/status(?:es)?\\/(\\d+)/);
    return m ? m[1] : '';
  }

  // 直近に出したidを覚えておき、続けて同じものが出にくいようにする。
  // プライベートモード等で使えなくても、履歴なしで普通に抽選する。
  function readRecent(){
    try{
      const v = JSON.parse(sessionStorage.getItem(RECENT_KEY) || '[]');
      return Array.isArray(v) ? v : [];
    }catch(e){ return []; }
  }
  function pushRecent(id, keep){
    try{
      const next = [id, ...readRecent().filter(x => x !== id)].slice(0, Math.max(0, keep));
      sessionStorage.setItem(RECENT_KEY, JSON.stringify(next));
    }catch(e){ /* 使えなければ黙って諦める */ }
  }

  // 直近を避けてn件引く。候補が足りなければ古い履歴から順に条件を緩める。
  function pickMany(n){
    const actives = allPosts.filter(p => p && p.active === true && tweetIdOf(p.url));
    const want = Math.min(n, actives.length);
    if(!want) return [];

    let recent = readRecent();
    let pool = actives.filter(p => !recent.includes(p.id));
    while(pool.length < want && recent.length){
      recent = recent.slice(0, -1);
      pool = actives.filter(p => !recent.includes(p.id));
    }
    if(pool.length < want) pool = actives.slice();

    const bag = pool.slice(), out = [];
    while(out.length < want && bag.length){
      const i = cfg.random === false ? 0 : Math.floor(Math.random() * bag.length);
      out.push(bag.splice(i, 1)[0]);
    }
    out.forEach(p => { if(p && p.id) pushRecent(p.id, cfg.avoidRecentCount); });
    return out;
  }

  // widgets.js はページ内で1回だけ読み込む
  let loading = null;
  function loadWidgets(){
    if(window.twttr && window.twttr.widgets) return Promise.resolve(window.twttr);
    if(loading) return loading;
    loading = new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = 'https://platform.twitter.com/widgets.js';
      s.async = true;
      s.charset = 'utf-8';
      s.onload = () => (window.twttr && window.twttr.widgets)
        ? resolve(window.twttr) : reject(new Error('widgets.js を読み込めませんでした'));
      s.onerror = () => reject(new Error('widgets.js の取得に失敗しました'));
      document.head.appendChild(s);
    });
    return loading;
  }

  // 素の幅と縮小率を決める。2件が横に収まる範囲でいちばん大きくする。
  function measure(){
    const per = Math.max(1, ((stage ? stage.clientWidth : HOST.clientWidth) - 8) / 2);
    natural = window.matchMedia('(max-width:900px)').matches
      ? NATURAL_MOBILE : NATURAL_DESKTOP;
    scale = Math.min(1, per / natural);
    HOST.style.setProperty('--xw', natural + 'px');
    HOST.style.setProperty('--xs', scale.toFixed(4));
  }

  // 縮小したぶんだけ枠の高さも詰める（下に余白が残らないように）
  const ro = ('ResizeObserver' in window) ? new ResizeObserver(entries => {
    for(const e of entries) fitSlot(e.target);
  }) : null;
  function fitSlot(inner){
    const slot = inner.parentElement;
    if(!slot) return;
    const h = inner.offsetHeight;
    slot.style.height = h ? Math.ceil(h * scale) + 'px' : '';
  }
  function fitAll(){
    if(!current) return;
    current.querySelectorAll('.xinner').forEach(fitSlot);
  }

  // 空の2枠を作ってステージに仕込む。iframeは最後まで動かさない。
  function stagePair(list){
    const pair = document.createElement('div');
    pair.className = 'xpair staging';
    const inners = list.map(() => {
      const slot = document.createElement('div');
      slot.className = 'xslot';
      const inner = document.createElement('div');
      inner.className = 'xinner';
      slot.appendChild(inner);
      pair.appendChild(slot);
      return inner;
    });
    stage.appendChild(pair);
    return {pair, inners};
  }

  // 仕込んだ枠の中でXに描かせる。1件も描けなければ null を返して片付ける。
  async function fillPair(list){
    const twttr = await loadWidgets();
    const {pair, inners} = stagePair(list);
    const opts = {
      conversation: cfg.hideThread === false ? 'all' : 'none',  // 親スレッドを出さない
      dnt: cfg.dnt !== false,
      lang: cfg.lang || 'ja',
      width: natural
    };
    const jobs = list.map((p, i) =>
      twttr.widgets.createTweet(tweetIdOf(p.url), inners[i], opts).catch(() => null));

    let timer = null;
    const guard = new Promise(res => { timer = setTimeout(res, RENDER_TIMEOUT); });
    await Promise.race([Promise.all(jobs), guard]);
    clearTimeout(timer);

    // 削除・非公開などで描画されなかった枠は畳む
    inners.forEach(inner => {
      if(!inner.querySelector('iframe')) inner.parentElement.remove();
    });
    if(!pair.querySelector('iframe')){ pair.remove(); return null; }
    return pair;
  }

  // 仕込み済みの2件を表に出し、古いほうを捨てる
  function reveal(pair, dir){
    const enter = dir === 'prev' ? 'toLeft' : 'toRight';
    pair.classList.add(enter);
    pair.classList.remove('staging');
    pair.querySelectorAll('.xinner').forEach(inner => {
      fitSlot(inner);
      if(ro) ro.observe(inner);
    });
    void pair.offsetWidth;                 // 位置を確定させてから戻す
    pair.classList.add('anim');
    pair.classList.remove(enter);
    if(current && current !== pair) current.remove();
    current = pair;
  }

  // 左右どちらでも「新しい2件」を引き直す。dirは出ていく向きだけを決める。
  async function swap(dir){
    if(busy) return;
    const list = pickMany(cfg.maxPosts);
    if(!list.length) return;
    busy = true;
    setNav(false);
    try{
      measure();
      const pair = await fillPair(list);
      if(!pair) return;                    // 引けなければ今の2件を残す
      if(current){
        current.classList.add('anim', dir === 'prev' ? 'toRight' : 'toLeft');
        await new Promise(r => setTimeout(r, ANIM_MS));
      }
      reveal(pair, dir);
    }catch(e){
      console.warn('[x-featured]', e && e.message ? e.message : e);
    }finally{
      busy = false;
      setNav(true);
    }
  }

  function setNav(on){
    if(nav) nav.querySelectorAll('button').forEach(b => { b.disabled = !on; });
  }

  function buildShell(){
    HOST.innerHTML = '';
    stage = document.createElement('div');
    stage.className = 'xstage';
    nav = document.createElement('div');
    nav.className = 'xnav';
    nav.innerHTML =
      '<button type="button" data-dir="prev" aria-label="前の2件を表示">&#8249;</button>' +
      '<span class="xhint"></span>' +
      '<button type="button" data-dir="next" aria-label="次の2件を表示">&#8250;</button>';
    HOST.append(stage, nav);

    nav.addEventListener('click', e => {
      const b = e.target.closest('button[data-dir]');
      if(b) swap(b.dataset.dir);
    });

    // 横スワイプ。縦方向が勝っていればページのスクロールに譲る。
    let x0 = 0, y0 = 0, tracking = false;
    stage.addEventListener('touchstart', e => {
      if(e.touches.length !== 1){ tracking = false; return; }
      x0 = e.touches[0].clientX; y0 = e.touches[0].clientY; tracking = true;
    }, {passive:true});
    stage.addEventListener('touchend', e => {
      if(!tracking) return;
      tracking = false;
      const t = e.changedTouches[0];
      const dx = t.clientX - x0, dy = t.clientY - y0;
      if(Math.abs(dx) < SWIPE_MIN || Math.abs(dx) < Math.abs(dy) * 1.5) return;
      swap(dx < 0 ? 'next' : 'prev');
    }, {passive:true});

    let rt = null;
    window.addEventListener('resize', () => {
      clearTimeout(rt);
      rt = setTimeout(() => { measure(); fitAll(); }, 150);
    });
  }

  async function main(){
    let data;
    try{
      const res = await fetch(DATA_URL, {cache: 'no-cache'});
      if(!res.ok) throw new Error('HTTP ' + res.status);
      data = await res.json();
    }catch(e){ return giveUp('投稿リストを取得できません: ' + e.message); }

    cfg = Object.assign({}, DEFAULTS, data.displaySettings || {});
    allPosts = Array.isArray(data.posts) ? data.posts : [];
    const first = pickMany(cfg.maxPosts);
    if(!first.length) return giveUp(null);   // 候補なしは異常ではないので静かに隠す

    HOST.hidden = false;
    HOST.classList.add('loading');
    buildShell();
    stage.innerHTML = '<div class="xph">読み込み中…</div>';
    measure();

    let pair;
    try{
      pair = await fillPair(first);
    }catch(e){
      return giveUp(e && e.message ? e.message : '埋め込みに失敗しました');
    }
    if(!pair) return giveUp('投稿を表示できませんでした（削除・非公開の可能性）');

    const ph = stage.querySelector('.xph');
    if(ph) ph.remove();
    reveal(pair, 'next');
    HOST.classList.remove('loading');
    HOST.classList.add('done');
  }

  // 本体の描画を待たせないよう、読み込み完了後に動かす
  if(document.readyState === 'complete') main();
  else window.addEventListener('load', main, {once: true});
})();
""".replace("%DATA_URL%", DATA_URL)

# <main> の先頭に置く空の器。中身はJSが入れる。
SECTION = '  <section id="xFeatured" aria-label="X の投稿" hidden></section>'
