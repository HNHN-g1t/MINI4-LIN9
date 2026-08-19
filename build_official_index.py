# -*- coding: utf-8 -*-
"""公式マスタ（tamiya_catalog.json）からカタログインデックス docs/index.html を生成する。

- タミヤ公式の品番・正式名称・定価・商品写真を掲載
- 上段タブでジャンル（GUパーツ／限定パーツ／AOパーツ／キット／塗装／ツール）を切り替え
- 下段チップでジャンル内の細分類を絞り込み（細分類が1種類のジャンルでは出さない）
- ページ内テキスト検索と各ECサイトへの検索ジャンプが動く
- お気に入りは閲覧者のブラウザ内（localStorage）に保存する

使い方:
    py build_official_index.py
"""
import html
import json
import os
import shutil
import sys
import urllib.parse
from datetime import datetime, timedelta, timezone

import colormap_ui
import paint_colors

JST = timezone(timedelta(hours=9))

# アフィリエイトの計測ID
MERCARI_AFID = "1714548549"      # メルカリアンバサダー
AMAZON_TAG = "hnhn03-22"         # Amazonアソシエイト
RAKUTEN_AFID = "56ae2925.07c6f012.56ae2926.4d88b0cd"   # 楽天アフィリエイト
VALUECOMMERCE_ID = ""            # ValueCommerce（申請中。IDが出たらここに入れる）

# 上段タブの並び（tamiya_catalog.json の genre_key に対応）。「すべて」は末尾に付く。
GENRE_ORDER = [
    ("parts", "GUパーツ"),
    ("limited", "限定パーツ"),
    ("ao", "AOパーツ"),
    ("kit", "キット"),
    ("paint", "塗装"),
    ("tool", "ツール"),
]

# 品番順に並べ替えるジャンル（中カテゴリごとに品番の昇順で並べる）
SORT_BY_CODE = {"paint"}

# 公式の細分類が無いジャンル（グレードアップパーツ・AOパーツ）向けの名前キーワード分類
CATEGORY_RULES = [
    ("ローラー", ["ローラー"]),
    ("タイヤ＆ホイール", ["タイヤ", "ホイール"]),
    ("モーター", ["モーター"]),
    ("ギヤ", ["ギヤ", "ギア", "ピニオン", "カウンター", "クラウン"]),
    ("プレート・ステー", ["プレート", "ステー", "FRP", "カーボン"]),
    ("ブレーキ", ["ブレーキ"]),
    ("マスダンパー・制振", ["マスダンパー", "ダンパー", "スラダン"]),
    ("ベアリング・ハトメ", ["ベアリング", "ハトメ", "はとめ"]),
    ("シャフト・駆動", ["シャフト", "プロペラ", "ターミナル", "モーターピン"]),
    ("ビス・金具", ["ビス", "ナット", "スペーサー", "ワッシャー", "金具", "スタビ"]),
    ("シャーシ・ボディ", ["シャーシ", "ボディ", "バンパー", "ユニット", "カバー", "ホルダー", "ケース", "ボックス"]),
]
FALLBACK_CATEGORY = "その他"


def categorize(name: str) -> str:
    for cat, kws in CATEGORY_RULES:
        if any(k in name for k in kws):
            return cat
    return FALLBACK_CATEGORY


def ec_links(item: dict) -> list[tuple[str, str, str]]:
    """ECサイトの検索URLを (ラベル, URL, rel属性) で返す。
    ミニ四駆系は品番、工具・塗料は商品名で引くのが当たりやすい。
    並び順は amazon → メルカリ → Yahoo! → ヤフオク → 楽天。
    メルカリ・Amazon・楽天はそれぞれの計測IDを付ける。"""
    code = item["item_code"]
    if item.get("genre_key") in ("tool", "paint"):
        # 工具と塗料は品番で検索してもモール側でほぼヒットしないため商品名で引く
        term = mercari_term = f"タミヤ {item['name']}"
    else:
        term = f"ミニ四駆 {code}"
        mercari_term = f"{code} タミヤ"
    q = urllib.parse.quote(term)
    mq = urllib.parse.quote(mercari_term)
    # 楽天は検索語をパスに埋める。アフィリエイトは中継URLに遷移先を
    # まるごとURLエンコードして渡す形式（pc=パソコン向け / m=スマホ向け）。
    rakuten_target = urllib.parse.quote(f"https://search.rakuten.co.jp/search/mall/{q}/", safe="")
    rakuten_url = (f"https://hb.afl.rakuten.co.jp/hgc/{RAKUTEN_AFID}/"
                   f"?pc={rakuten_target}&m={rakuten_target}")
    return [
        ("amazon", f"https://www.amazon.co.jp/s?k={q}&tag={AMAZON_TAG}", "sponsored noopener"),
        ("メルカリ", f"https://jp.mercari.com/search?keyword={mq}&afid={MERCARI_AFID}",
         "sponsored noopener"),
        ("Yahoo!", f"https://shopping.yahoo.co.jp/search?p={q}", "noopener"),
        ("ヤフオク", f"https://auctions.yahoo.co.jp/search/search?p={q}", "noopener"),
        ("楽天", rakuten_url, "sponsored noopener"),
    ]


CSS = """
:root{--bg:#f5f6f8;--surface:#fff;--ink:#1a2233;--ink2:#5a6478;--ink3:#8b93a5;
--brand:#1256c4;--brand-soft:#e8f0fd;--line:#e3e6ec;--good:#0e7a4b;--accent:#d81f2a;
font-family:"Hiragino Sans","Noto Sans JP",Meiryo,sans-serif}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--ink);font-size:14px;line-height:1.6}
a{color:inherit;text-decoration:none}
header{background:var(--surface);border-bottom:1px solid var(--line);position:sticky;top:0;z-index:10}
.hwrap{max-width:1120px;margin:0 auto;display:flex;align-items:center;gap:16px;padding:12px 16px;flex-wrap:wrap}
.logo{font-weight:800;font-size:20px;color:var(--accent);white-space:nowrap}
.logo span{color:var(--brand)}
.searchbox{flex:1;min-width:240px;display:flex;gap:8px}
.searchbox input{flex:1;border:1.5px solid var(--line);border-radius:8px;padding:8px 12px;font-size:13px;outline:none}
.searchbox input:focus{border-color:var(--brand)}
.tabs{max-width:1120px;margin:0 auto;display:flex;gap:4px;padding:0 16px;flex-wrap:wrap}
.tab{padding:9px 20px;font-size:13.5px;font-weight:700;color:var(--ink2);cursor:pointer;
background:var(--surface);border-radius:4px 4px 0 0;user-select:none;white-space:nowrap}
.tab:hover{color:var(--brand);background:var(--brand-soft)}
.tab.on{background:var(--brand);color:#fff}
.tab.on:hover{background:var(--brand);color:#fff}
.tab .n{font-size:11px;font-weight:600;color:var(--ink3);margin-left:6px}
.tab.on .n{color:#cfe0fa}
main{max-width:1120px;margin:0 auto;padding:12px 16px 40px}
.chips{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 10px}
.chip{background:var(--surface);border:1.5px solid var(--line);border-radius:999px;
padding:5px 14px;font-size:12px;font-weight:600;cursor:pointer;user-select:none}
.chip.on{background:var(--brand);border-color:var(--brand);color:#fff}
.chip.hide{display:none}
.count-line{font-size:12px;color:var(--ink3);margin:6px 2px 10px}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
.it{background:var(--surface);border:1px solid var(--line);border-radius:9px;overflow:hidden;
display:flex;flex-direction:column;transition:box-shadow .15s,transform .15s}
.it:hover{box-shadow:0 4px 14px rgba(20,40,80,.10);transform:translateY(-1px)}
.ph{aspect-ratio:4/3;background:#fff;display:flex;align-items:center;justify-content:center;border-bottom:1px solid var(--line)}
.ph img{max-width:100%;max-height:100%;object-fit:contain}
.bd{padding:10px 12px 12px;display:flex;flex-direction:column;gap:4px;flex:1}
.row1{display:flex;align-items:center;gap:6px}
.btn-fav{font-size:15px;line-height:1;border:none;background:none;cursor:pointer;padding:2px 1px;
color:var(--ink3);font-family:inherit}
.btn-fav:hover{color:#e8a400}
.btn-fav.on{color:#f0a500}
.tab.fav.on{background:#f0a500}
.tab.fav.on:hover{background:#f0a500}
.nm{font-size:12.5px;line-height:1.45;flex:1;overflow:hidden;white-space:nowrap}
.btn-detail{font-size:10.5px;font-weight:700;border:1px solid var(--line);background:var(--surface);
color:var(--ink2);border-radius:6px;padding:3px 10px;cursor:pointer;white-space:nowrap;
font-family:inherit;line-height:1.5}
.btn-detail:hover{border-color:var(--brand);color:var(--brand);background:var(--brand-soft)}
.detail{display:none;margin-top:6px;padding-top:6px;border-top:1px dashed var(--line)}
.it.open .detail{display:block}
.nmfull{font-size:12.5px;line-height:1.45;margin:2px 0 4px}
.code{font-size:10.5px;font-weight:800;color:var(--ink3);letter-spacing:.03em}
.pr{font-size:15px;font-weight:800}
.pr small{font-size:10px;font-weight:600;color:var(--ink3)}
.ecrow{display:flex;gap:6px;margin-top:auto;padding-top:8px;flex-wrap:wrap}
.ec{font-size:10.5px;font-weight:700;border-radius:6px;padding:3px 8px;border:1px solid var(--line);color:var(--ink2)}
.ec:hover{background:var(--brand-soft);border-color:var(--brand);color:var(--brand)}
.ec.souba{background:var(--brand);border-color:var(--brand);color:#fff}
.cat-tag{font-size:10px;color:var(--brand);font-weight:700}
.empty{padding:60px 0;text-align:center;color:var(--ink3);display:none}
/* ページ送り（公式サイトと同じ、数字を四角で並べる形） */
.pager{display:none;gap:5px;flex-wrap:wrap;align-items:center;justify-content:center;margin:12px 0}
.pager.on{display:flex}
.pager button{min-width:34px;height:34px;padding:0 8px;border:1.5px solid var(--line);
background:var(--surface);color:var(--ink2);border-radius:5px;font:inherit;font-size:12.5px;
font-weight:700;cursor:pointer}
.pager button:hover:not(:disabled){border-color:var(--brand);color:var(--brand)}
.pager button[aria-current="page"]{background:var(--brand);border-color:var(--brand);color:#fff}
.pager button:disabled{opacity:.35;cursor:default}
.pager .gap{color:var(--ink3);font-size:12px;padding:0 2px}
footer{max-width:1120px;margin:0 auto;padding:16px;font-size:11px;color:var(--ink3);border-top:1px solid var(--line)}
@media(max-width:900px){.grid{grid-template-columns:repeat(2,1fr)}}
""" + colormap_ui.CSS

JS = """
const q = document.getElementById('q');
const tabs = [...document.querySelectorAll('.tab')];
const chips = [...document.querySelectorAll('.chip')];
const chipRow = document.querySelector('.chips');
const cards = [...document.querySelectorAll('.it')];
const countLine = document.getElementById('countLine');
const empty = document.getElementById('empty');
const favN = document.getElementById('favN');
let genre = '';   // '' = すべて
let cat = '';     // '' = 全カテゴリ

// ---- ページ送り ----
const PER_PAGE = 24;          // 1ページの表示件数
const PAGE_WINDOW = 7;        // 数字ボタンを並べる最大数
let page = 1;
let matched = [];             // 絞り込み後のカード（ページ分割前）
const pagerTop = document.getElementById('pagerTop');
const pagerBottom = document.getElementById('pagerBottom');

// ---- お気に入り（ブラウザのlocalStorageにのみ保存。ログイン不要） ----
const FAV_KEY = 'mini4rinku:favs';
let favs = new Set();
try{ favs = new Set(JSON.parse(localStorage.getItem(FAV_KEY) || '[]')); }catch(e){}

function saveFavs(){
  try{ localStorage.setItem(FAV_KEY, JSON.stringify([...favs])); }catch(e){}
}
function paintFavs(){
  for(const c of cards){
    const on = favs.has(c.dataset.code);
    const b = c.querySelector('.btn-fav');
    b.textContent = on ? '★' : '☆';
    b.classList.toggle('on', on);
    b.title = on ? 'お気に入りから外す' : 'お気に入りに追加';
  }
  favN.textContent = favs.size;
}

function syncChips(){
  // ジャンル未選択（すべて）・お気に入りのときは細分類を出さない。
  // ジャンル選択時は、そのジャンルに存在する細分類だけ出す。
  const real = genre && genre !== 'fav';
  for(const ch of chips){
    const gs = ch.dataset.genres;
    ch.classList.toggle('hide', !(real && (!gs || gs.split(' ').includes(genre))));
  }
  // 隠れたチップが選択中なら解除する
  const active = chips.find(c => cat && c.dataset.cat === cat);
  if(active && active.classList.contains('hide')) cat = '';
  chips.forEach(c => c.classList.toggle('on', c.dataset.cat === cat));
  // 細分類が1種類しかないジャンルでは、絞り込みにならないのでチップ行ごと隠す
  const usable = chips.filter(c => c.dataset.cat && !c.classList.contains('hide')).length;
  chipRow.style.display = (real && usable > 1) ? '' : 'none';
}

function apply(resetPage){
  const terms = q.value.trim().toLowerCase().split(/\\s+/).filter(Boolean);
  matched = cards.filter(c => {
    const okGenre = !genre ? true
                  : genre === 'fav' ? favs.has(c.dataset.code)
                  : c.dataset.genre === genre;
    return okGenre
        && (!cat || c.dataset.cat === cat)
        && terms.every(t => c.dataset.hay.includes(t));
  });
  if(resetPage !== false) page = 1;
  renderPage();
  if(window.paintPins) paintPins();
}

function pageCount(){ return Math.max(1, Math.ceil(matched.length / PER_PAGE)); }

// 指定カードが何ページ目にいるか。絞り込みに含まれなければ 0。
function pageOf(card){
  const i = matched.indexOf(card);
  return i < 0 ? 0 : Math.floor(i / PER_PAGE) + 1;
}

function renderPage(){
  const total = pageCount();
  page = Math.min(Math.max(1, page), total);
  const from = (page - 1) * PER_PAGE, to = from + PER_PAGE;
  const visible = new Set(matched.slice(from, to));
  for(const c of cards) c.style.display = visible.has(c) ? '' : 'none';

  const n = matched.length;
  countLine.textContent = n === 0
    ? (genre === 'fav' ? 'お気に入り 0件' : '0件')
    : genre === 'fav'
      ? `お気に入り ${n}件（${from + 1}〜${Math.min(to, n)}件を表示）`
      : `${from + 1}〜${Math.min(to, n)}件 / 全${n}件`;
  empty.textContent = genre === 'fav' && !favs.size
    ? 'お気に入りはまだありません。各カードの☆を押すと登録できます。'
    : '該当する商品が見つかりません';
  empty.style.display = n ? 'none' : 'block';

  buildPager(pagerTop, total);
  buildPager(pagerBottom, total);
  try{ history.replaceState(null, '', page > 1 ? '#p=' + page : location.pathname); }catch(e){}
}

// 数字は PAGE_WINDOW 個までにして、間は … で省略する
function buildPager(el, total){
  el.classList.toggle('on', total > 1);
  if(total <= 1){ el.innerHTML = ''; return; }
  const half = Math.floor(PAGE_WINDOW / 2);
  const start = Math.max(1, Math.min(page - half, total - PAGE_WINDOW + 1));
  const end = Math.min(total, start + PAGE_WINDOW - 1);
  const btn = (label, p, opt) => `<button type="button" data-p="${p}"${opt || ''}>${label}</button>`;
  const parts = [btn('‹', page - 1, page === 1 ? ' disabled aria-label="前のページ"' : ' aria-label="前のページ"')];
  if(start > 1){ parts.push(btn('1', 1)); if(start > 2) parts.push('<span class="gap">…</span>'); }
  for(let p = start; p <= end; p++) parts.push(btn(p, p, p === page ? ' aria-current="page"' : ''));
  if(end < total){ if(end < total - 1) parts.push('<span class="gap">…</span>'); parts.push(btn(total, total)); }
  parts.push(btn('›', page + 1, page === total ? ' disabled aria-label="次のページ"' : ' aria-label="次のページ"'));
  el.innerHTML = parts.join('');
}

// ページ番号を押したら切り替え、一覧の先頭へ戻す
function onPagerClick(e){
  const b = e.target.closest('button[data-p]');
  if(!b || b.disabled) return;
  page = parseInt(b.dataset.p, 10);
  renderPage();
  const top = document.querySelector('.grid').getBoundingClientRect().top + window.scrollY;
  window.scrollTo({top: top - 80, behavior: 'smooth'});
}
pagerTop.addEventListener('click', onPagerClick);
pagerBottom.addEventListener('click', onPagerClick);

// 指定カードを必ず表示できる状態にしてから、そのページへ移動する。
// 検索語や絞り込みで一覧から外れていると今までジャンプできなかったため、
// 邪魔になっている条件を解除してから探し直す。
window.revealCard = function(card){
  if(!matched.includes(card)){
    if(q.value){ q.value = ''; }        // 検索語を外す
    cat = '';                            // 中カテゴリの絞り込みを外す
    genre = card.dataset.genre || '';    // カードのあるジャンルへ移動
    tabs.forEach(t => t.classList.toggle('on', t.dataset.genre === genre));
    syncChips();
    apply();
  }
  const p = pageOf(card);
  if(p && p !== page){ page = p; renderPage(); }
  return p > 0;
};

// 戻る／進むでページを復元する
window.addEventListener('popstate', () => {
  const m = location.hash.match(/p=(\\d+)/);
  page = m ? parseInt(m[1], 10) : 1;
  renderPage();
});

q.addEventListener('input', apply);

tabs.forEach(t => t.addEventListener('click', () => {
  genre = t.dataset.genre;
  tabs.forEach(x => x.classList.toggle('on', x === t));
  cat = '';
  syncChips();
  apply();
}));

chips.forEach(ch => ch.addEventListener('click', () => {
  cat = (cat === ch.dataset.cat) ? '' : ch.dataset.cat;
  chips.forEach(c => c.classList.toggle('on', c.dataset.cat === cat));
  apply();
}));

// 「詳細」で品番・正式名称・価格を開閉する
document.querySelectorAll('.btn-detail').forEach(b => b.addEventListener('click', () => {
  const card = b.closest('.it');
  const open = card.classList.toggle('open');
  b.textContent = open ? '閉じる' : '詳細';
}));

// ☆でお気に入りを登録・解除する
document.querySelectorAll('.btn-fav').forEach(b => b.addEventListener('click', () => {
  const code = b.closest('.it').dataset.code;
  if(favs.has(code)) favs.delete(code); else favs.add(code);
  saveFavs();
  paintFavs();
  if(genre === 'fav') apply();   // お気に入り表示中は即座に反映する
}));

paintFavs();
syncChips();
apply();
const _hp = location.hash.match(/p=(\\d)+/);
if(_hp){ page = parseInt(location.hash.replace(/[^0-9]/g, ''), 10) || 1; renderPage(); }
""" + colormap_ui.JS


NOT_FOUND_HTML = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ミニ四リン駆</title>
<link rel="icon" href="/assets/favicon.ico" sizes="any">
<meta http-equiv="refresh" content="0; url=/">
<script>location.replace('/' + location.hash);</script>
<style>body{font-family:"Hiragino Sans","Noto Sans JP",Meiryo,sans-serif;
background:#f5f6f8;color:#1a2233;display:flex;min-height:100vh;margin:0;
align-items:center;justify-content:center;text-align:center;padding:24px}
a{color:#1256c4;font-weight:700}</style>
</head>
<body>
<div>
  <p>ページを移動しています…</p>
  <p><a href="/">開かない場合はこちら（ミニ四リン駆トップ）</a></p>
</div>
</body>
</html>
"""

MANIFEST = {
    "name": "ミニ四リン駆",
    "short_name": "ミニ四リン駆",
    "description": "タミヤ ミニ四駆・クラフトツールの品番カタログ",
    "start_url": "/",
    "scope": "/",
    "display": "standalone",
    "background_color": "#f5f6f8",
    "theme_color": "#d81f2a",
    "icons": [
        {"src": "/assets/icon-192.png", "sizes": "192x192", "type": "image/png"},
        {"src": "/assets/icon-512.png", "sizes": "512x512", "type": "image/png"},
        {"src": "/assets/apple-touch-icon.png", "sizes": "180x180", "type": "image/png"},
    ],
}


def write_extras(outdir: str) -> None:
    """404ページとマニフェストを書き出す。

    404ページは、古いURL（/partspost/ など）をホーム画面アイコンや
    ブックマークが保持していてもトップへ着地させるための保険。
    """
    with open(os.path.join(outdir, "404.html"), "w", encoding="utf-8") as f:
        f.write(NOT_FOUND_HTML)
    with open(os.path.join(outdir, "manifest.webmanifest"), "w", encoding="utf-8") as f:
        json.dump(MANIFEST, f, ensure_ascii=False, indent=1)


def copy_assets(outdir: str) -> None:
    """ファビコン等の固定ファイルを docs/assets/ に配置する。
    独自ドメイン用の CNAME も公開ルートに置く。"""
    src, dst = "assets", os.path.join(outdir, "assets")
    if os.path.isdir(src):
        os.makedirs(dst, exist_ok=True)
        for name in os.listdir(src):
            shutil.copy2(os.path.join(src, name), os.path.join(dst, name))
    # 独自ドメイン（mini4lin9.fun）用の CNAME。
    # DNSレコードの登録が済むまでは CNAME.pending のまま置いておく。
    # 有効化するときは CNAME.pending を CNAME にリネームするだけでよい。
    if os.path.exists("CNAME"):
        shutil.copy2("CNAME", os.path.join(outdir, "CNAME"))


def build(items: list[dict], outdir: str) -> str:
    # 各商品に細分類を割り当てる
    for it in items:
        it["_cat"] = it.get("official_category") or categorize(it["name"])
        it.setdefault("genre_key", "parts")
        it.setdefault("genre", "グレードアップパーツ")

    # 指定ジャンルはジャンル内を品番の昇順に並べ替える（他は取得順のまま）
    if any(i["genre_key"] in SORT_BY_CODE for i in items):
        head = [i for i in items if i["genre_key"] not in SORT_BY_CODE]
        # 中カテゴリの並びは取得順（=公式ジャンルの指定順）を維持し、
        # その中を品番の昇順にする
        rank = {}
        for i in items:
            rank.setdefault((i["genre_key"], i.get("official_category", "")), len(rank))
        tail = sorted((i for i in items if i["genre_key"] in SORT_BY_CODE),
                      key=lambda i: (rank[(i["genre_key"], i.get("official_category", ""))],
                                     int(i["item_code"])))
        items = head + tail

    genres = [(k, lb) for k, lb in GENRE_ORDER if any(i["genre_key"] == k for i in items)]
    genre_counts = {k: sum(1 for i in items if i["genre_key"] == k) for k, _ in genres}

    # 上段タブ（ジャンル → すべて → お気に入り）
    tab_html = "".join(
        f'<div class="tab" data-genre="{k}">{html.escape(lb)}<span class="n">{genre_counts[k]}</span></div>'
        for k, lb in genres
    ) + (
        f'<div class="tab on" data-genre="">すべて<span class="n">{len(items)}</span></div>'
        '<div class="tab fav" data-genre="fav">★ お気に入り<span class="n" id="favN">0</span></div>'
    )

    # 下段チップ（細分類）。同じ分類名が複数ジャンルに出るので1つにまとめ、
    # どのジャンルに属するかを data-genres に持たせる。ジャンル選択時だけ表示する。
    cat_genres: dict[str, list[str]] = {}
    for k, _ in genres:
        for c in dict.fromkeys(i["_cat"] for i in items if i["genre_key"] == k):
            cat_genres.setdefault(c, []).append(k)
    chip_html = "".join(
        f'<span class="chip" data-cat="{html.escape(c)}" data-genres="{" ".join(gs)}">{html.escape(c)}</span>'
        for c, gs in cat_genres.items()
    ) + '<span class="chip on" data-cat="" data-genres="">すべて</span>' 

    cards = []
    for it in items:
        code, name, cat = it["item_code"], it["name"], it["_cat"]
        hay = html.escape(f"{code} {it.get('gp_no','')} {name} {cat} {it['genre']}".lower())
        gp = f"　／ {html.escape(it['gp_no'])}" if it.get("gp_no") else ""
        short = name[:13] + ("…" if len(name) > 13 else "")
        ecrow = "".join(
            f'<a class="ec" href="{u}" target="_blank" rel="{rel}">{html.escape(lb)}</a>'
            for lb, u, rel in ec_links(it)
        )
        cards.append(f'''      <div class="it" id="item-{code}" data-code="{code}" data-genre="{it["genre_key"]}" data-cat="{html.escape(cat)}" data-hay="{hay}">
        <a class="ph" href="{html.escape(it["url"])}" target="_blank" rel="noopener">
          <img src="{html.escape(it["image"])}" alt="{html.escape(name)}" loading="lazy"></a>
        <div class="bd">
          <div class="row1">
            <button class="btn-fav" type="button" title="お気に入りに追加">☆</button>
            <div class="nm">{html.escape(short)}</div>
            <button class="btn-detail" type="button">詳細</button>
          </div>
          <div class="detail">
            <div class="code">ITEM {code}{gp}</div>
            <div class="cat-tag">{html.escape(cat)}</div>
            <div class="nmfull">{html.escape(name)}</div>
            <div class="pr">¥{it["price"]:,} <small>メーカー希望（税込）</small></div>
          </div>
          <div class="ecrow">{ecrow}</div>
        </div>
      </div>''')

    paint_rows = paint_colors.build([i for i in items if i.get("genre_key") == "paint"])
    cmap_html = colormap_ui.section(paint_rows) if paint_rows else ""

    doc = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="icon" href="assets/favicon.ico" sizes="any">
<link rel="icon" type="image/png" sizes="32x32" href="assets/favicon-32.png">
<link rel="apple-touch-icon" href="assets/apple-touch-icon.png">
<link rel="manifest" href="manifest.webmanifest">
<link rel="canonical" href="https://mini4lin9.fun/">
<meta name="theme-color" content="#d81f2a">
<meta name="apple-mobile-web-app-title" content="ミニ四リン駆">
<title>ミニ四リン駆｜タミヤ ミニ四駆・クラフトツール カタログ（公式品番マスタ）</title>
<style>{CSS}</style>
</head>
<body>
<header>
  <div class="hwrap">
    <a class="logo" href="index.html">ミニ四<span>リン駆</span></a>
    <div class="searchbox"><input id="q" type="search"
      placeholder="品番・商品名で検索（例：15435 / ローラー / ニッパー / エンペラー）"></div>
  </div>
  <div class="tabs">{tab_html}</div>
</header>
<main>
  <div class="chips">{chip_html}</div>
{cmap_html}
  <div class="count-line" id="countLine"></div>
  <nav class="pager" id="pagerTop" aria-label="ページ送り（上）"></nav>
  <div class="grid">
{chr(10).join(cards)}
  </div>
  <nav class="pager" id="pagerBottom" aria-label="ページ送り（下）"></nav>
  <div class="empty" id="empty">該当する商品が見つかりません</div>
  <div class="cmap-tip" id="cmapTip" role="status"></div>
</main>
<footer>
  ミニ四リン駆（プロトタイプ） ・ 品番・名称・価格・写真はタミヤ公式サイトの情報（出典: tamiya.com） ・
  最終更新 {datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")}<br>
  商品写真は公式サイトから直接参照しています。ECリンクは各モールの検索結果を開きます。
  お気に入りはご利用中のブラウザ内にのみ保存され、サーバーには送信されません。<br>
  <b>【PR】</b>当サイトはアフィリエイトプログラム（メルカリアンバサダー、Amazonアソシエイト、
  楽天アフィリエイト、ValueCommerce ※申請中）を利用しており、商品リンク経由の購入により
  報酬を受け取る場合があります。<br>
  Amazonのアソシエイトとして、ミニ四リン駆は適格販売により収入を得ています。
</footer>
<script>{JS}</script>
</body>
</html>
"""
    os.makedirs(outdir, exist_ok=True)
    copy_assets(outdir)
    write_extras(outdir)
    path = os.path.join(outdir, "index.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)
    return path


def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    os.chdir(here)
    if not os.path.exists("tamiya_catalog.json"):
        print("エラー: tamiya_catalog.json がありません。先に py fetch_tamiya_catalog.py を実行してください。", file=sys.stderr)
        return 1
    with open("tamiya_catalog.json", encoding="utf-8") as f:
        items = json.load(f)
    path = build(items, "docs")
    print(f"生成完了: {path} ／ {len(items)}品番")
    for k, lb in GENRE_ORDER:
        n = sum(1 for i in items if i.get("genre_key") == k)
        if n:
            print(f"  {lb}: {n}件")
    return 0


if __name__ == "__main__":
    sys.exit(main())
