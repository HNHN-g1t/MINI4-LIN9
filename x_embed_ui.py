# -*- coding: utf-8 -*-
"""TOPにX（旧Twitter）の投稿を1件だけランダム表示する（CSS / JS / HTML）。

投稿は docs/data/x-featured-posts.json で管理する。JSONに1件足すだけで
候補が増え、このファイルを触る必要はない。

表示はX公式の Embedded Post（widgets.js の createTweet）に任せる。
投稿本文・投稿者情報・メディア・Xロゴの描画には手を加えず、
高さも固定しない（クロップ禁止）。

読み込みに失敗した場合は表示領域ごと隠し、サイト本体には影響させない。
"""

DATA_URL = "data/x-featured-posts.json"

CSS = """
/* ---- X投稿（TOPに1件だけ） ---- */
#xFeatured{max-width:460px;margin:0 auto 10px;padding:0}
#xFeatured[hidden]{display:none}
/* 読み込み中の控えめなプレースホルダー。描画されたら自然に置き換わる */
#xFeatured.loading{min-height:120px;border:1px solid var(--line);border-radius:10px;
background:var(--surface)}
#xFeatured .xph{display:flex;align-items:center;justify-content:center;min-height:120px;
font-size:11px;color:var(--ink3)}
#xFeatured.done{min-height:0;border:none;background:none}
#xFeatured .twitter-tweet{margin:0 auto !important}
@media(max-width:900px){#xFeatured{max-width:100%;margin:0 auto 10px}}
"""

JS = """
// ---- X投稿を1件だけランダム表示 ----
// 失敗しても本体に影響させない。何かあれば領域ごと隠す。
(() => {
  const HOST = document.getElementById('xFeatured');
  if(!HOST) return;

  const DATA_URL = '%DATA_URL%';
  const RECENT_KEY = 'm4rinku:x-recent-post-ids';
  const RENDER_TIMEOUT = 8000;
  const DEFAULTS = {maxPosts:1, random:true, avoidRecentCount:5,
                    autoRotate:false, hideThread:true, dnt:true, lang:'ja'};

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

  function pick(posts, cfg){
    const actives = posts.filter(p => p && p.active === true && tweetIdOf(p.url));
    if(!actives.length) return null;
    const recent = readRecent();
    let pool = actives.filter(p => !recent.includes(p.id));
    if(!pool.length){                      // 全部出し切ったら履歴を捨ててやり直す
      try{ sessionStorage.removeItem(RECENT_KEY); }catch(e){}
      pool = actives;
    }
    const chosen = cfg.random === false ? pool[0]
                 : pool[Math.floor(Math.random() * pool.length)];
    if(chosen && chosen.id) pushRecent(chosen.id, cfg.avoidRecentCount);
    return chosen;
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

  async function main(){
    let data;
    try{
      const res = await fetch(DATA_URL, {cache: 'no-cache'});
      if(!res.ok) throw new Error('HTTP ' + res.status);
      data = await res.json();
    }catch(e){ return giveUp('投稿リストを取得できません: ' + e.message); }

    const cfg = Object.assign({}, DEFAULTS, data.displaySettings || {});
    const post = pick(Array.isArray(data.posts) ? data.posts : [], cfg);
    if(!post) return giveUp(null);          // 候補なしは異常ではないので静かに隠す

    const id = tweetIdOf(post.url);
    HOST.hidden = false;
    HOST.classList.add('loading');
    HOST.innerHTML = '<div class="xph">読み込み中…</div>';

    let done = false;
    const timer = setTimeout(() => { if(!done) giveUp('埋め込みの描画がタイムアウトしました'); },
                             RENDER_TIMEOUT);

    try{
      const twttr = await loadWidgets();
      HOST.innerHTML = '';
      const el = await twttr.widgets.createTweet(id, HOST, {
        conversation: cfg.hideThread === false ? 'all' : 'none',  // 親スレッドを出さない
        align: 'center',
        dnt: cfg.dnt !== false,
        lang: cfg.lang || 'ja'
      });
      done = true;
      clearTimeout(timer);
      // 削除・非公開などで描画されなかった場合は undefined が返る
      if(!el) return giveUp('投稿を表示できませんでした（削除・非公開の可能性）');
      HOST.classList.remove('loading');
      HOST.classList.add('done');
    }catch(e){
      done = true;
      clearTimeout(timer);
      giveUp(e && e.message ? e.message : '埋め込みに失敗しました');
    }
  }

  // 本体の描画を待たせないよう、読み込み完了後に動かす
  if(document.readyState === 'complete') main();
  else window.addEventListener('load', main, {once: true});
})();
""".replace("%DATA_URL%", DATA_URL)

# <main> の先頭に置く空の器。中身はJSが入れる。
SECTION = '  <section id="xFeatured" aria-label="X の投稿" hidden></section>'
