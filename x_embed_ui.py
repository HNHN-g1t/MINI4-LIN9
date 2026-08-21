# -*- coding: utf-8 -*-
"""X（旧Twitter）の投稿を出す2つの区画（CSS / JS / HTML）。

1. TOPの帯（#xFeatured）… 縮小したサムネイルを横に並べ、シャッフルで入れ替える。
   商品一覧を押しのけないよう高さを固定して切り詰めてある。読ませる場所では
   ないので、どれを押しても「X Machines」タブへ送る。
2. X Machines（#xWall）… 上段タブの1つ。投稿を素の大きさで敷き詰める。
   こちらが読む場所。タブを開くまで描画しない。全件を一度に出すと重いので、
   商品一覧と同じようにページで区切る（PC 12件／スマホ 6件）。

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
#xFeatured{--xw:250px;--xs:1;--xgap:6px;--xh:136px;--xline:4px;--xtrim:#c9ced6;
max-width:1120px;margin:0 auto 8px;padding:0;position:relative}
#xFeatured[hidden]{display:none}
#xFeatured.loading{min-height:90px;border:1px solid var(--line);border-radius:10px;
background:var(--surface)}
#xFeatured .xph{display:flex;align-items:center;justify-content:center;min-height:90px;
font-size:11px;color:var(--ink3)}
#xFeatured.done{min-height:0;border:none;background:none}

.xstage{position:relative;overflow:hidden}
.xpair{display:flex;gap:var(--xgap);justify-content:center;align-items:flex-start;
will-change:transform,opacity}
.xpair.anim{transition:transform .22s ease,opacity .22s ease}
.xpair.toLeft{transform:translateX(-10%);opacity:0}
.xpair.toRight{transform:translateX(10%);opacity:0}
/* 次の組は、いまの組に重ねたまま描き切る（iframeを動かさない） */
.xpair.staging{position:absolute;left:0;right:0;top:0;opacity:0;pointer-events:none}

/* 上下はグレーの直線で切る。--xh は線の内側（＝見せたい高さ）。 */
.xslot{flex:0 0 auto;width:calc(var(--xw) * var(--xs));
height:calc(var(--xh) + var(--xline) * 2);
border-top:var(--xline) solid var(--xtrim);
border-bottom:var(--xline) solid var(--xtrim);
position:relative;overflow:hidden;background:var(--surface)}
/* scale を先に書くこと。translate を先にすると、ずらし量が画面上のpxとして
   効いてしまい、縮小しているスマホでは 1/縮小率 倍も動いてしまう。
   scale のあとに置けば、ずらし量は縮小前の座標のまま扱われる。 */
.xslot > .xinner{width:var(--xw);transform-origin:top left;
transform:scale(var(--xs)) translateY(calc(var(--yoff, 0px) * -1));
transition:transform .18s ease}
.xslot .twitter-tweet{margin:0 !important}

/* iframe内のリンクを踏ませず、タップは丸ごとタブ移動に使う */
.xhit{position:absolute;inset:0;z-index:2;padding:0;border:0;background:transparent;
cursor:pointer;border-radius:8px;-webkit-tap-highlight-color:transparent}
.xhit:hover{background:rgba(0,0,0,.05)}
.xhit:focus-visible{outline:2px solid var(--brand);outline-offset:2px}

@media(max-width:900px){
  /* 3件を画面内に収めたいので、この区画だけ左右の余白を8px詰める */
  #xFeatured{max-width:none;margin-left:-8px;margin-right:-8px;--xline:2px}
}
@media(prefers-reduced-motion:reduce){
  .xpair.anim{transition:opacity .15s ease}
  .xpair.toLeft,.xpair.toRight{transform:none}
}

/* ---- X Machines：全投稿を2列で敷き詰める ---- */
/* --xww = Xに描画させる素の幅 / --xws = 列幅に合わせた縮小率 */
#xWall{--xww:250px;--xws:1;--xwgap:12px;display:none;margin:0 0 10px}
#xWall.on{display:block}
/* ページ送りは商品一覧と同じ見た目。body.wall で .pager を隠しているので上書きする */
body.wall #xWall .pager.on{display:flex !important}
.xwgrid{display:grid;gap:var(--xwgap);align-items:start;
grid-template-columns:repeat(4,minmax(0,1fr))}
@media(max-width:900px){
  .xwgrid{grid-template-columns:repeat(2,minmax(0,1fr))}
}
/* 押した1件を先頭に置くため order を使う。DOMは動かさない（iframeが再読込されるため） */
.xwcell{min-width:0;overflow:hidden}
.xwcell > .xwinner{width:var(--xww);transform:scale(var(--xws));transform-origin:top left}
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
  const NATURAL = 250;          // Xの埋め込みが受け付ける最小幅
  const COUNT_PC = 4;           // PCで帯に並べる件数
  const COUNT_SP = 2;           // スマホで帯に並べる件数
  const WALL_GAP = 12;
  const WALL_PER_PC = 12;       // X Machines の1ページ表示数（PC）
  const WALL_PER_SP = 6;        // X Machines の1ページ表示数（スマホ）
  const WALL_PAGE_WINDOW = 7;   // 数字ボタンを並べる最大数
  const DEFAULTS = {random:true, avoidRecentCount:8,
                    autoRotate:false, hideThread:true, dnt:true, lang:'ja'};

  let cfg = DEFAULTS, allPosts = [], scale = 1;
  // Xに描かせる素の幅。並べたとき左右が余らないよう、最初の計測で決めて固定する
  // （途中で変えると描き直しになり、iframeが全部読み込み直しになるため）。
  let bandNatural = 250, bandFixed = false;
  let stage = null, current = null, wallFixed = false;
  let wallCells = [], wallNatural = NATURAL, wallScale = 1, pendingLead = null;
  let wallOrder = [];           // 開いたときに決めた並び（全件）
  let wallPage = 1, wallPerPageNow = WALL_PER_PC;
  let wallToken = 0;            // 描画中にページが変わったら捨てるための番号
  let bandIds = [];             // いまTOPの帯に出ている並び（X Machines の先頭に使う）
  const wallCols = () => isMobile() ? 2 : 4;
  const wallPerPage = () => isMobile() ? WALL_PER_SP : WALL_PER_PC;

  const isMobile = () => window.matchMedia('(max-width:900px)').matches;
  const count = () => isMobile() ? COUNT_SP : COUNT_PC;
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
      width: bandNatural
    };
  }

  // 3件を横に並べるのに、どれだけ縮めるかを決める
  function measure(){
    const gap = isMobile() ? 6 : 8;
    const n = count();
    const avail = (stage ? stage.clientWidth : HOST.clientWidth) - gap * (n - 1);
    const col = Math.max(1, avail) / n;                  // 1枠に使える幅
    // 素の幅を枠幅に合わせておけば、縮小率1のまま左右が余らない。
    // 枠が細いスマホでは最小幅(250)を割れないので、そこは縮小で合わせる。
    if(!bandFixed) bandNatural = Math.round(Math.min(550, Math.max(NATURAL, col)));
    scale = Math.min(1, col / bandNatural);
    HOST.style.setProperty('--xw', bandNatural + 'px');
    // 窓の高さは写真グリッドの高さそのもの。PC・スマホとも同じ考え方にする。
    HOST.style.setProperty('--xh', Math.round(photoH() * scale) + extraTop() + 'px');
    HOST.style.setProperty('--xs', scale.toFixed(4));
    HOST.style.setProperty('--xgap', gap + 'px');
  }

  // 切り詰めた窓の中で、投稿の縦位置を中央に寄せる。
  // 写真は本文の下に来るため、上端に揃えたままだと画像が切れやすい。
  // 実際に描かれた高さを測り、はみ出しぶんの半分だけ上へずらす。
  // 投稿の下端に揃えつつ、写真ブロックの中心が窓の中央へ来るように寄せる。
  // iframeの中は読めないので、写真4枚（2×2で全体16:9）と、その下に日付・
  // アクション行がある前提で位置を出す。行き過ぎないよう下端で止める。
  // 投稿の下端（日付・アクション行）をどれだけ窓の外に出すか。
  // 大きくするほど窓が上へ動き、写真が下寄り＝中央に寄る。
  // PCは窓が広いぶん下端が目立つので多めに切る。スマホは下端に揃えたままが
  // 見やすいので、従来どおりの控えめな値にしている。
  // 埋め込みの左右の余白。写真グリッドの幅はこれを引いたぶん。
  const CONTENT_PAD = 12;
  const MEDIA_RATIO = 9 / 16;     // 写真2枚・4枚のグリッドは全体で16:9
  // 写真の下端から投稿の下端までの高さ（日付＋アクション＋返信リンク）。
  // ここを増やすと窓が上へ、減らすと下へ動く。合わなければこの数値だけ直せばよい。
  const BELOW_PHOTO = 116;
  // 窓を写真より上へ広げる量（画面px）。下端は固定なので、増やすと上に伸びる。
  const extraTop = () => isMobile() ? 0 : 4;
  // 投稿を下へずらす量（画面px）。増やすと中身が下がる。
  const nudge = () => isMobile() ? 2 : 0;

  const photoH = () => (bandNatural - CONTENT_PAD * 2) * MEDIA_RATIO;

  function centerOne(slot){
    const inner = slot.querySelector('.xinner');
    const frame = inner && inner.querySelector('iframe');
    if(!inner || !frame) return;
    const h = frame.offsetHeight;                 // 縮小前の投稿全体の高さ
    const win = slot.clientHeight / scale;        // 窓の高さも縮小前に換算する
    const over = h - win;
    if(!h || over <= 4){                          // 収まっているなら動かさない
      inner.style.setProperty('--yoff', '0px');
      return;
    }
    // 窓の下端を写真の下端に合わせる（日付から下は窓の外に出る）。
    // nudge は画面px指定なので、縮小前の座標に戻してから引く。
    const target = h - BELOW_PHOTO - win - nudge() / scale;
    const off = Math.round(Math.max(0, Math.min(target, over)));
    inner.style.setProperty('--yoff', off + 'px');
  }

  // 写真が読み込まれると iframe の高さが伸びる。決め打ちのタイミングで
  // 測ると伸びる前の値を掴んでしまうので、高さの変化そのものを見張る。
  const bro = ('ResizeObserver' in window)
    ? new ResizeObserver(es => {
        for(const e of es){
          const slot = e.target.closest ? e.target.closest('.xslot') : null;
          if(slot) centerOne(slot);
        }
      })
    : null;

  function centerAll(root){
    const slots = [...(root || HOST).querySelectorAll('.xslot')];
    const run = () => slots.forEach(centerOne);
    run();
    if(bro){
      slots.forEach(sl => {
        const f = sl.querySelector('iframe');
        if(f && !f.dataset.watched){ f.dataset.watched = '1'; bro.observe(f); }
      });
    }
    // 写真の読み込みで高さが伸びるまで、しばらく測り続ける。
    // ResizeObserver が効かない環境でも取りこぼさないための保険で、
    // 高さが落ち着いたら止める。
    let last = -1, still = 0, n = 0;
    const tick = () => {
      run();
      const h = (HOST.querySelector('iframe') || {}).offsetHeight || 0;
      still = (h === last && h > 0) ? still + 1 : 0;
      last = h;
      if(still >= 3 || ++n > 30) return;      // 落ち着いたか、15秒で打ち切り
      setTimeout(tick, 500);
    };
    setTimeout(tick, 300);
  }
  window.recenterXBand = () => centerAll(null);

  // 空の枠を作って仕込む。iframeは生成した場所から最後まで動かさない。
  function stagePair(list){
    const pair = document.createElement('div');
    pair.className = 'xpair staging';
    const inners = list.map(p => {
      const slot = document.createElement('div');
      slot.className = 'xslot';
      const inner = document.createElement('div');
      inner.className = 'xinner';
      const hit = document.createElement('button');
      hit.type = 'button';
      hit.className = 'xhit';
      hit.dataset.pid = (p && p.id) || '';     // X Machines で先頭に置く1件
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
    // いま帯に出す並びを控えておく。X Machines を開いたとき、
    // この順のまま先頭の1段に置くため。
    bandIds = list.map(p => p && p.id).filter(Boolean);
    bandFixed = true;             // 以降は素の幅を変えない（描き直しになるため）
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
    centerAll(pair);
    return pair;
  }

  // 仕込み済みの組を表に出し、古いほうを捨てる
  function reveal(pair){
    const enter = 'toRight';
    pair.classList.add(enter);
    pair.classList.remove('staging');
    void pair.offsetWidth;                 // 位置を確定させてから戻す
    pair.classList.add('anim');
    pair.classList.remove(enter);
    if(current && current !== pair) current.remove();
    current = pair;
  }

  // X Machines タブへ送る。タブ側の処理はページ本体が持っている。
  // 押した1件は pendingLead に預け、開いた先で先頭に回す。
  function openWall(pid){
    pendingLead = pid || null;
    const tab = document.querySelector('.tab[data-genre="' + WALL_GENRE + '"]');
    if(tab) tab.click();
  }

  function buildShell(){
    HOST.innerHTML = '';
    stage = document.createElement('div');
    stage.className = 'xstage';
    HOST.appendChild(stage);

    // サムネはどこを押しても X Machines へ。押した1件を先頭に回す。
    stage.addEventListener('click', e => {
      const hit = e.target.closest('.xhit');
      if(hit) openWall(hit.dataset.pid);
    });

    let rt = null;
    window.addEventListener('resize', () => {
      clearTimeout(rt);
      rt = setTimeout(() => {
        measure(); centerAll(null); measureWall();
        // PC⇔スマホをまたいだときは1ページの件数が変わるので組み直す
        if(WALL && WALL.classList.contains('on') && wallPerPage() !== wallPerPageNow){
          wallPerPageNow = wallPerPage();
          wallPage = 1;
          renderWallPage();
        }else{
          fitWall();
        }
      }, 180);
    });
  }

  // ---- X Machines（全件を2列で敷き詰める） ----
  // 列幅に合わせて素の幅と縮小率を決める。素の幅は組んだ時点で固定する
  // （変えると描き直しになり、iframeが全部読み込み直しになるため）。
  function measureWall(){
    if(!WALL || !WALL.classList.contains('on')) return;
    const cols = wallCols();
    const col = Math.max(1, (WALL.clientWidth - WALL_GAP * (cols - 1)) / cols);
    if(!wallFixed){
      wallNatural = Math.round(Math.min(550, Math.max(NATURAL, col)));
      wallFixed = true;
    }
    wallScale = Math.min(1, col / wallNatural);
    WALL.style.setProperty('--xww', wallNatural + 'px');
    WALL.style.setProperty('--xws', wallScale.toFixed(4));
    WALL.style.setProperty('--xwgap', WALL_GAP + 'px');
  }

  // 縮小したぶんだけセルの高さも詰める（下に余白が残らないように）
  const wro = ('ResizeObserver' in window)
    ? new ResizeObserver(es => { for(const e of es) fitCell(e.target); }) : null;
  function fitCell(inner){
    const cell = inner.parentElement;
    if(!cell) return;
    const h = inner.offsetHeight;
    cell.style.height = h ? Math.ceil(h * wallScale) + 'px' : '';
  }
  function fitWall(){ wallCells.forEach(c => fitCell(c.inner)); }

  // 先頭は、TOPの帯に出ていた並びをそのまま持ってくる。
  // 押した1件があれば、その中でいちばん前に回す。あとはシャッフル。
  // 並び順は開いたときに1回だけ決め、ページを送っても崩れないようにする。
  function orderWall(leadId){
    const list = actives();
    const byId = id => list.find(p => p.id === id);

    let head = (bandIds || []).map(byId).filter(Boolean);
    if(leadId){
      const i = head.findIndex(p => p.id === leadId);
      if(i > 0) head = [head[i]].concat(head.filter((_, k) => k !== i));
      else if(i < 0 && byId(leadId)) head = [byId(leadId)].concat(head);
    }
    const headIds = new Set(head.map(p => p.id));

    const rest = list.filter(p => !headIds.has(p.id));
    for(let i = rest.length - 1; i > 0; i--){
      const j = Math.floor(Math.random() * (i + 1));
      const t = rest[i]; rest[i] = rest[j]; rest[j] = t;
    }
    wallOrder = head.concat(rest);
  }

  function wallPageCount(){
    return Math.max(1, Math.ceil(wallOrder.length / wallPerPage()));
  }

  // 商品一覧のページ送りと同じ形。数字は WALL_PAGE_WINDOW 個までで、間は … にする。
  function buildWallPager(el, total){
    el.classList.toggle('on', total > 1);
    if(total <= 1){ el.innerHTML = ''; return; }
    const half = Math.floor(WALL_PAGE_WINDOW / 2);
    const start = Math.max(1, Math.min(wallPage - half, total - WALL_PAGE_WINDOW + 1));
    const end = Math.min(total, start + WALL_PAGE_WINDOW - 1);
    const btn = (label, p, opt) =>
      '<button type="button" data-p="' + p + '"' + (opt || '') + '>' + label + '</button>';
    const parts = [btn('\u2039', wallPage - 1,
      wallPage === 1 ? ' disabled aria-label="前のページ"' : ' aria-label="前のページ"')];
    if(start > 1){
      parts.push(btn('1', 1));
      if(start > 2) parts.push('<span class="gap">…</span>');
    }
    for(let p = start; p <= end; p++){
      parts.push(btn(p, p, p === wallPage ? ' aria-current="page"' : ''));
    }
    if(end < total){
      if(end < total - 1) parts.push('<span class="gap">…</span>');
      parts.push(btn(total, total));
    }
    parts.push(btn('\u203a', wallPage + 1,
      wallPage === total ? ' disabled aria-label="次のページ"' : ' aria-label="次のページ"'));
    el.innerHTML = parts.join('');
  }

  // いまのページぶんだけ描く。前のページのiframeは捨てる（残すと重くなるため）。
  async function renderWallPage(){
    if(!WALL) return;
    if(!wallOrder.length){
      WALL.innerHTML = '<div class="xwnote">表示できる投稿がありません。</div>';
      return;
    }
    const total = wallPageCount();
    wallPage = Math.min(Math.max(1, wallPage), total);

    let twttr;
    try{ twttr = await loadWidgets(); }
    catch(e){
      WALL.innerHTML = '<div class="xwnote">投稿を読み込めませんでした。</div>';
      return;
    }

    const token = ++wallToken;
    if(wro) wallCells.forEach(c => wro.unobserve(c.inner));
    wallCells = [];

    WALL.innerHTML = '';
    const pagerTop = document.createElement('nav');
    pagerTop.className = 'pager xwpager';
    pagerTop.setAttribute('aria-label', 'X Machines ページ送り（上）');
    const grid = document.createElement('div');
    grid.className = 'xwgrid';
    const pagerBottom = document.createElement('nav');
    pagerBottom.className = 'pager xwpager';
    pagerBottom.setAttribute('aria-label', 'X Machines ページ送り（下）');
    WALL.appendChild(pagerTop);
    WALL.appendChild(grid);
    WALL.appendChild(pagerBottom);
    buildWallPager(pagerTop, total);
    buildWallPager(pagerBottom, total);

    measureWall();
    const per = wallPerPage();
    wallPerPageNow = per;
    const slice = wallOrder.slice((wallPage - 1) * per, (wallPage - 1) * per + per);
    const built = slice.map(p => {
      const cell = document.createElement('div');
      cell.className = 'xwcell';
      const inner = document.createElement('div');
      inner.className = 'xwinner';
      cell.appendChild(inner);
      grid.appendChild(cell);
      return {id: (p && p.id) || '', cell, inner};
    });

    const opts = Object.assign(tweetOpts(), {width: wallNatural});
    const jobs = slice.map((p, i) =>
      twttr.widgets.createTweet(tweetIdOf(p.url), built[i].inner, opts).catch(() => null));
    // 1件でも応答が返らないと先に進めなくなるので、帯と同じように時間で打ち切る。
    let wt = null;
    const guard = new Promise(res => { wt = setTimeout(res, RENDER_TIMEOUT); });
    await Promise.race([Promise.all(jobs), guard]);
    clearTimeout(wt);
    if(token !== wallToken) return;   // 描いている間にページが変わっていた

    // 描画できなかったものは畳む
    built.forEach(c => { if(!c.inner.querySelector('iframe')) c.cell.remove(); });
    wallCells = built.filter(c => c.inner.querySelector('iframe'));
    if(!wallCells.length && total === 1){
      WALL.innerHTML = '<div class="xwnote">投稿を読み込めませんでした。</div>';
      return;
    }
    wallCells.forEach(c => { fitCell(c.inner); if(wro) wro.observe(c.inner); });
  }

  // ページ番号を押したら、そのページを描いて一覧の先頭へ戻す
  if(WALL) WALL.addEventListener('click', e => {
    const b = e.target.closest('.xwpager button[data-p]');
    if(!b || b.disabled) return;
    wallPage = parseInt(b.dataset.p, 10);
    renderWallPage();
    const top = WALL.getBoundingClientRect().top + window.scrollY;
    window.scrollTo({top: Math.max(0, top - 80), behavior: 'smooth'});
  });

  // 開くたびに並べ替える。押した1件があればそれが先頭。
  async function openWallView(){
    const lead = pendingLead;
    pendingLead = null;
    orderWall(lead);
    wallPage = 1;
    measureWall();
    await renderWallPage();
    fitWall();
  }

  // ページ本体（タブ切り替え）から呼ばれる
  window.__xwall = {
    open(){ if(WALL){ WALL.classList.add('on'); openWallView(); } HOST.hidden = true; },
    close(){
      if(WALL){
        WALL.classList.remove('on');
        if(wro) wallCells.forEach(c => wro.unobserve(c.inner));
        wallCells = [];
        wallToken++;                 // 描画中なら結果を捨てる
        WALL.innerHTML = '';         // iframeを残さない
      }
      if(HOST.dataset.ready) HOST.hidden = false;
    },
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

    const first = pickMany(count());
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
    reveal(pair);
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
