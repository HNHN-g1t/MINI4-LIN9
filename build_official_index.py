# -*- coding: utf-8 -*-
"""公式マスタ（tamiya_catalog.json）からカタログインデックス site/index.html を生成する。

- タミヤ公式の品番・正式名称・定価・商品写真を掲載
- 上段タブでジャンル（グレードアップパーツ／キット／AOパーツ／クラフトツール）を切り替え
- 下段チップでジャンル内の細分類（公式シリーズ名・工具種別・パーツ種別）を絞り込み
- ページ内テキスト検索と各ECサイトへの検索ジャンプが動く
- 相場ページ（site/items/15xxx.html）が生成済みの品番は内部リンクも表示

使い方:
    py build_official_index.py
"""
import html
import json
import os
import sys
import urllib.parse
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))

# 上段タブの並び（tamiya_catalog.json の genre_key に対応）。「すべて」は末尾に付く。
GENRE_ORDER = [
    ("parts", "グレードアップパーツ"),
    ("ao", "AOパーツ"),
    ("kit", "キット"),
    ("tool", "クラフトツール"),
]

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


def ec_links(item: dict) -> list[tuple[str, str]]:
    """ECサイトの検索URL。ミニ四駆系は品番、工具は商品名で引くのが当たりやすい。
    並び順は amazon → メルカリ → Yahoo! → ヤフオク。"""
    if item.get("genre_key") == "tool":
        term = f"タミヤ {item['name']}"
    else:
        term = f"ミニ四駆 {item['item_code']}"
    q = urllib.parse.quote(term)
    return [
        ("amazon", f"https://www.amazon.co.jp/s?k={q}"),
        ("メルカリ", f"https://jp.mercari.com/search?keyword={q}"),
        ("Yahoo!", f"https://shopping.yahoo.co.jp/search?p={q}"),
        ("ヤフオク", f"https://auctions.yahoo.co.jp/search/search?p={q}"),
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
footer{max-width:1120px;margin:0 auto;padding:16px;font-size:11px;color:var(--ink3);border-top:1px solid var(--line)}
@media(max-width:900px){.grid{grid-template-columns:repeat(2,1fr)}}
"""

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
  chipRow.style.display = real ? '' : 'none';
}

function apply(){
  const terms = q.value.trim().toLowerCase().split(/\\s+/).filter(Boolean);
  let shown = 0;
  for(const c of cards){
    const okGenre = !genre ? true
                  : genre === 'fav' ? favs.has(c.dataset.code)
                  : c.dataset.genre === genre;
    const on = okGenre
            && (!cat || c.dataset.cat === cat)
            && terms.every(t => c.dataset.hay.includes(t));
    c.style.display = on ? '' : 'none';
    if(on) shown++;
  }
  countLine.textContent = genre === 'fav'
    ? `お気に入り ${shown}件`
    : `${shown}件 / 全${cards.length}件を表示`;
  empty.textContent = genre === 'fav' && !favs.size
    ? 'お気に入りはまだありません。各カードの☆を押すと登録できます。'
    : '該当する商品が見つかりません';
  empty.style.display = shown ? 'none' : 'block';
}

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
"""


def build(items: list[dict], outdir: str) -> str:
    # 各商品に細分類を割り当てる
    for it in items:
        it["_cat"] = it.get("official_category") or categorize(it["name"])
        it.setdefault("genre_key", "parts")
        it.setdefault("genre", "グレードアップパーツ")

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
    chip_html = '<span class="chip on" data-cat="" data-genres="">すべて</span>' + "".join(
        f'<span class="chip" data-cat="{html.escape(c)}" data-genres="{" ".join(gs)}">{html.escape(c)}</span>'
        for c, gs in cat_genres.items()
    )

    cards = []
    for it in items:
        code, name, cat = it["item_code"], it["name"], it["_cat"]
        hay = html.escape(f"{code} {it.get('gp_no','')} {name} {cat} {it['genre']}".lower())
        gp = f"　／ {html.escape(it['gp_no'])}" if it.get("gp_no") else ""
        short = name[:13] + ("…" if len(name) > 13 else "")
        ecrow = "".join(
            f'<a class="ec" href="{u}" target="_blank" rel="noopener">{html.escape(lb)}</a>'
            for lb, u in ec_links(it)
        )
        cards.append(f'''      <div class="it" data-code="{code}" data-genre="{it["genre_key"]}" data-cat="{html.escape(cat)}" data-hay="{hay}">
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

    doc = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
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
  <div class="count-line" id="countLine"></div>
  <div class="grid">
{chr(10).join(cards)}
  </div>
  <div class="empty" id="empty">該当する商品が見つかりません</div>
</main>
<footer>
  ミニ四リン駆（プロトタイプ） ・ 品番・名称・価格・写真はタミヤ公式サイトの情報（出典: tamiya.com） ・
  最終更新 {datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")}<br>
  商品写真は公式サイトから直接参照しています。ECリンクは各モールの検索結果を開きます。
  お気に入りはご利用中のブラウザ内にのみ保存され、サーバーには送信されません。
</footer>
<script>{JS}</script>
</body>
</html>
"""
    os.makedirs(outdir, exist_ok=True)
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
    path = build(items, "site")
    print(f"生成完了: {path} ／ {len(items)}品番")
    for k, lb in GENRE_ORDER:
        n = sum(1 for i in items if i.get("genre_key") == k)
        if n:
            print(f"  {lb}: {n}件")
    return 0


if __name__ == "__main__":
    sys.exit(main())
