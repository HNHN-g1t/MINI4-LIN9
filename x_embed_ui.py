# -*- coding: utf-8 -*-
"""X（旧Twitter）の投稿を出す2つの区画（CSS / JS / HTML）。

1. TOPの帯（#xFeatured）… 縮小したサムネイルを横に並べ、シャッフルで入れ替える。
   商品一覧を押しのけないよう高さを固定して切り詰めてある。読ませる場所では
   ないので、どれを押しても「X Machines」タブへ送る。
2. X Machines（#xWall）… 上段タブの1つ。全投稿を素の大きさで敷き詰める。
   こちらが読む場所。タブを開くまで描画しない。

投稿は docs/data/x-featured-posts.json で管理する。JSONに1件足すだけで
候補が増え、このファイルを触る必要はない。

読み込みに失敗した場合は表示領域ごと隠し、サイト本体には影響させない。
"""

DATA_URL = "data/x-featured-posts.json"

# 上段タブから参照するジャンルキー。build_official_index.py と合わせること。
WALL_GENRE = "xm"

CSS = """
/* ---- TOPの帯：縮小サムネを並べ、押すと X Machines へ送る ---- */
/* --xw = Xに描画させる素の幅 / --xs = 縮小率 / --xh = 切り詰めた表示高さ */
#xFeatured{--xw:250px;--xs:1;--xgap:6px;--xh:150px;
max-width:980px;margin:0 auto 8px;padding:0;position:relative}
#xFeatured[hidden]{display:none}
#xFeatured.loading{min-height:90px;border:1px solid var(--line);border-radius:10px;
background:var(--surface)}
#xFeatured .xph{display:flex;align-items:center;justify-content:center;min-height:90px;
font-size:11px;color:var(--ink3)}
#xFeatured.done{min-height:0;border:none;background:none}

/* シャッフル。ラベルは置かず、アイコンだけを帯の上に出す */
.xnav{display:flex;justify-content:flex-end;margin:0 0 4px}
.xnav button{width:30px;height:30px;display:flex;align-items:center;justify-content:center;
padding:0;border:1.5px solid var(--line);background:var(--surface);color:var(--ink2);
border-radius:50%;cursor:pointer}
.xnav button:hover:not(:disabled){border-color:var(--brand);color:var(--brand)}
.xnav button:disabled{opacity:.35;cursor:default}
.xnav button svg{display:block}
.xnav button.spin svg{animation:xspin .5s ease}
@keyframes xspin{from{transform:rotate(0)}to{transform:rotate(360deg)}}

.xstage{position:relative;overflow:hidden}
.xpair{display:flex;gap:var(--xgap);justify-content:center;align-items:flex-start;
will-change:transform,opacity}
.xpair.anim{transition:transform .22s ease,opacity .22s ease}
.xpair.toLeft{transform:translateX(-10%);opacity:0}
.xpair.toRight{transform:translateX(10%);opacity:0}
/* 次の組は、いまの組に重ねたまま描き切る（iframeを動かさない） */
.xpair.staging{position:absolute;left:0;right:0;top:0;opacity:0;pointer-events:none}

.xslot{flex:0 0 auto;width:calc(var(--xw) * var(--xs));height:var(--xh);
position:relative;overflow:hidden;border-radius:8px;background:var(--surface)}
.xslot > .xinner{width:var(--xw);transform:scale(var(--xs));transform-origin:top left}
.xslot .twitter-tweet{margin:0 !important}
/* 切り詰めた下端をぼかし、続きがあることを示す */
.xslot::after{content:"";position:absolute;left:0;right:0;bottom:0;height:26px;
background:linear-gradient(to bottom,transparent,var(--bg));pointer-events:none;z-index:1}
/* iframe内のリンクを踏ませず、タップは丸ごとタブ移動に使う */
.xhit{position:absolute;inset:0;z-index:2;padding:0;border:0;background:transparent;
cursor:pointer;border-radius:8px;-webkit-tap-highlight-color:transparent}
.xhit:hover{background:rgba(0,0,0,.05)}
.xhit:focus-visible{outline:2px solid var(--brand);outline-offset:2px}

@media(max-width:900px){
  /* 4件を画面内に収めたいので、この区画だけ左右の余白を8px詰める */
  #xFeatured{max-width:none;margin-left:-8px;margin-right:-8px;--xh:140px}
  .xslot::after{height:20px}
}
@media(prefers-reduced-motion:reduce){
  .xpair.anim{transition:opacity .15s ease}
  .xpair.toLeft,.xpair.toRight{transform:none}
  .xnav button.spin svg{animation:none}
}

/* ---- X Machines：全投稿を素の大きさで敷き詰める ---- */
#xWall{display:none;margin:0 0 10px}
#xWall.on{display:block}
.xwgrid{display:grid;gap:12px;justify-content:center;
grid-template-columns:repeat(auto-fill,minmax(250px,1fr))}
.xwcell{min-width:0}
.xwcell .twitter-tweet{margin:0 !important}
.xwnote{font-size:11px;color:var(--ink3);margin:0 0 10px}
"""

JS = """
// ---- Xの投稿（TOPの帯 と X Machines タブ） ----
// 失敗しても本体に影響させない。何かあれば領域ごと隠す。
(() => {
  const HOST = document.getElementById('xFeatured');
  const WALL = document.getElementById('xWall');
  if(!HOST) return;

  const DATA_URL = '%DATA_URL%';
  const WALL_GENRE = '%WALL_GENRE%';
  const RECENT_KEY = 'm4rinku:x-recent-post-ids';
  const RENDER_TIMEOUT = 8000;
  const ANIM_MS = 220;
  const NATURAL = 250;          // Xの埋め込みが受け付ける最小幅
  const COUNT_MOBILE = 4;
  const COUNT_DESKTOP = 6;
  const DEFAULTS = {random:true, avoidRecentCount:8,
                    autoRotate:false, hideThread:true, dnt:true, lang:'ja'};

  let cfg = DEFAULTS, allPosts = [], scale = 1, count = COUNT_MOBILE;
  let stage = null, nav = null, current = null, busy = false, wallDone = false;

  const isMobile = () => window.matchMedia('(max-width:900px)').matches;
  const actives = () => allPosts.filter(p => p && p.active === true && tweetIdOf(p.url));

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
    const pool0 = actives();
    const want = Math.min(n, pool0.length);
    if(!want) return [];

    let recent = readRecent();
    let pool = pool0.filter(p => !recent.includes(p.id));
    while(pool.length < want && recent.length){
      recent = recent.slice(0, -1);
      pool = pool0.filter(p => !recent.includes(p.id));
    }
    if(pool.length < want) pool = pool0.slice();

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

  function tweetOpts(){
    return {
      conversation: cfg.hideThread === false ? 'all' : 'none',  // 親スレッドを出さない
      dnt: cfg.dnt !== false,
      lang: cfg.lang || 'ja',
      width: NATURAL
    };
  }

  // 何件を横に並べ、どれだけ縮めるかを決める
  function measure(){
    count = isMobile() ? COUNT_MOBILE : COUNT_DESKTOP;
    const gap = isMobile() ? 6 : 8;
    const avail = (stage ? stage.clientWidth : HOST.clientWidth) - gap * (count - 1);
    scale = Math.min(1, Math.max(1, avail) / count / NATURAL);
    HOST.style.setProperty('--xw', NATURAL + 'px');
    HOST.style.setProperty('--xs', scale.toFixed(4));
    HOST.style.setProperty('--xgap', gap + 'px');
  }

  // 空の枠を作って仕込む。iframeは生成した場所から最後まで動かさない。
  function stagePair(list){
    const pair = document.createElement('div');
    pair.className = 'xpair staging';
    const inners = list.map(() => {
      const slot = document.createElement('div');
      slot.className = 'xslot';
      const inner = document.createElement('div');
      inner.className = 'xinner';
      const hit = document.createElement('button');
      hit.type = 'button';
      hit.className = 'xhit';
      hit.setAttribute('aria-label', 'X Machines を開く');
      slot.append(inner, hit);
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
    const opts = tweetOpts();
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

  // 仕込み済みの組を表に出し、古いほうを捨てる
  function reveal(pair, dir){
    const enter = dir === 'prev' ? 'toLeft' : 'toRight';
    pair.classList.add(enter);
    pair.classList.remove('staging');
    void pair.offsetWidth;                 // 位置を確定させてから戻す
    pair.classList.add('anim');
    pair.classList.remove(enter);
    if(current && current !== pair) current.remove();
    current = pair;
  }

  // 新しい組をランダムで引き直す。dirは出ていく向きだけを決める。
  async function shuffle(dir){
    if(busy) return;
    const list = pickMany(count);
    if(!list.length) return;
    busy = true;
    setNav(false);
    try{
      measure();
      const pair = await fillPair(list);
      if(!pair) return;                    // 引けなければ今の組を残す
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

  // X Machines タブへ送る。タブ側の処理はページ本体が持っている。
  function openWall(){
    const tab = document.querySelector('.tab[data-genre="' + WALL_GENRE + '"]');
    if(tab) tab.click();
  }

  function buildShell(){
    HOST.innerHTML = '';
    nav = document.createElement('div');
    nav.className = 'xnav';
    nav.innerHTML =
      '<button type="button" aria-label="別の投稿に入れ替える">' +
      '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" ' +
      'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      '<path d="M20.4 11.9a8.5 8.5 0 1 1-2.5-6"/><path d="M20.8 3.6v5.2h-5.2"/>' +
      '</svg></button>';
    stage = document.createElement('div');
    stage.className = 'xstage';
    HOST.append(nav, stage);          // アイコンは帯の上

    nav.addEventListener('click', e => {
      const b = e.target.closest('button');
      if(!b) return;
      b.classList.remove('spin');
      void b.offsetWidth;
      b.classList.add('spin');
      shuffle('next');
    });

    // サムネはどこを押しても X Machines へ
    stage.addEventListener('click', e => {
      if(e.target.closest('.xhit')) openWall();
    });

    let rt = null;
    window.addEventListener('resize', () => {
      const before = count;
      clearTimeout(rt);
      rt = setTimeout(() => {
        measure();
        // 並べる数が変わったら組ごと引き直す（枠の数が合わなくなるため）
        if(count !== before) shuffle('next');
      }, 180);
    });
  }

  // ---- X Machines（全件を素の大きさで） ----
  async function buildWall(){
    if(!WALL || wallDone) return;
    wallDone = true;
    const list = actives();
    if(!list.length){
      WALL.innerHTML = '<div class="xwnote">表示できる投稿がありません。</div>';
      return;
    }
    WALL.innerHTML = '<div class="xwnote">読み込み中…</div>';
    let twttr;
    try{ twttr = await loadWidgets(); }
    catch(e){
      WALL.innerHTML = '<div class="xwnote">投稿を読み込めませんでした。</div>';
      return;
    }
    const grid = document.createElement('div');
    grid.className = 'xwgrid';
    const cells = list.map(() => {
      const c = document.createElement('div');
      c.className = 'xwcell';
      grid.appendChild(c);
      return c;
    });
    WALL.innerHTML = '';
    WALL.appendChild(grid);

    const opts = tweetOpts();
    await Promise.all(list.map((p, i) =>
      twttr.widgets.createTweet(tweetIdOf(p.url), cells[i], opts).catch(() => null)));
    cells.forEach(c => { if(!c.querySelector('iframe')) c.remove(); });
    if(!grid.querySelector('iframe')){
      WALL.innerHTML = '<div class="xwnote">投稿を読み込めませんでした。</div>';
    }
  }

  // ページ本体（タブ切り替え）から呼ばれる
  window.__xwall = {
    open(){ if(WALL){ WALL.classList.add('on'); buildWall(); } HOST.hidden = true; },
    close(){ if(WALL) WALL.classList.remove('on'); if(HOST.dataset.ready) HOST.hidden = false; },
    count(){ return actives().length; }
  };

  async function main(){
    let data;
    try{
      const res = await fetch(DATA_URL, {cache: 'no-cache'});
      if(!res.ok) throw new Error('HTTP ' + res.status);
      data = await res.json();
    }catch(e){ return giveUp('投稿リストを取得できません: ' + e.message); }

    cfg = Object.assign({}, DEFAULTS, data.displaySettings || {});
    allPosts = Array.isArray(data.posts) ? data.posts : [];

    // 上段タブの件数を実データで埋める
    const badge = document.getElementById('xmN');
    if(badge) badge.textContent = actives().length;

    HOST.hidden = false;
    HOST.classList.add('loading');
    buildShell();
    stage.innerHTML = '<div class="xph">読み込み中…</div>';
    measure();

    const first = pickMany(count);
    if(!first.length) return giveUp(null);   // 候補なしは異常ではないので静かに隠す

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
    HOST.dataset.ready = '1';
    // X Machines を開いた状態で読み終わった場合は帯を出さない
    if(WALL && WALL.classList.contains('on')) HOST.hidden = true;
  }

  // 本体の描画を待たせないよう、読み込み完了後に動かす
  if(document.readyState === 'complete') main();
  else window.addEventListener('load', main, {once: true});
})();
""".replace("%DATA_URL%", DATA_URL).replace("%WALL_GENRE%", WALL_GENRE)

# <main> に置く空の器。中身はJSが入れる。
SECTION = '  <section id="xFeatured" aria-label="X の投稿" hidden></section>'
WALL_SECTION = '  <section id="xWall" aria-label="X Machines"></section>'
