# -*- coding: utf-8 -*-
"""公式マスタ（tamiya_catalog.json）からカタログインデックス docs/index.html を生成する。

- タミヤ公式の品番・正式名称・定価・商品写真を掲載
- 上段タブでジャンル（GUパーツ／限定パーツ／AOパーツ／キット／塗料／ツール）を切り替え
- 下段チップでジャンル内の細分類を絞り込み（細分類が1種類のジャンルでは出さない）
- ページ内テキスト検索と各ECサイトへの検索ジャンプが動く
- お気に入りは閲覧者のブラウザ内（localStorage）に保存する

使い方:
    py build_official_index.py
"""
import html
import json
import os
import re
import shutil
import sys
import urllib.parse
from datetime import datetime, timedelta, timezone

import color_wheel_ui
import colormap_ui
import godtools_ui
import paint_colors
import x_embed_ui

JST = timezone(timedelta(hours=9))

# アフィリエイトの計測ID
MERCARI_AFID = "1714548549"      # メルカリアンバサダー
AMAZON_TAG = "hnhn03-22"         # Amazonアソシエイト
RAKUTEN_AFID = "56ae2925.07c6f012.56ae2926.4d88b0cd"   # 楽天アフィリエイト
VALUECOMMERCE_SID = "3778941"    # ValueCommerce サイトID
VALUECOMMERCE_PID = "892682983"  # ValueCommerce LinkSwitch の vc_pid

# ---- サイトの住所と紹介文（検索結果・SNS・サイトマップで使い回す） ----
SITE_URL = "https://mini4lin9.fun"
SITE_NAME = "ミニ四リン駆"
# Google Search Console の所有権確認ファイル。
# Search Console が「このファイルが置いてあること」を見にくる。
# 消すと所有権が外れて、検索での見え方が確認できなくなる。
GSC_VERIFY_FILE = "google924c214c12e811d4.html"
# 検索結果に出る説明文。長すぎると途中で切られるので120文字前後までに収める。
SITE_DESC = ("タミヤ ミニ四駆のパーツ・キット・塗料・工具 {n}品番を、品番や名前から検索できるカタログ。"
             "スプレーのカラーMAPやレース開催情報も掲載しています。")

# 上段タブの並び（tamiya_catalog.json の genre_key に対応）。「すべて」は末尾に付く。
GENRE_ORDER = [
    ("parts", "GUパーツ"),
    ("limited", "限定パーツ"),
    ("ao", "AOパーツ"),
    ("kit", "キット"),
    ("paint", "塗料"),
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

# カッコ四駆タブの中に置く特設チップ。
# cat はチップの合言葉、tag はレジストリの tags に入っている値。
# days を入れると「その日数以内の投稿だけ」になり、古いものは手を入れずに外れる。
WALL_CHIPS = [
    {"cat": "__emperor", "tag": "エンペラー", "label": "エンペラー",
     "badge": "empN", "cls": "emp"},
    {"cat": "__condele", "tag": "コンデレ", "label": "コンデレ", "badge": "conN"},
    {"cat": "__kojidele", "tag": "コジデレ", "label": "コジデレ", "badge": "kojN"},
    {"cat": "__official", "tag": "ミニ四駆公式", "label": "ミニ四駆公式",
     "badge": "offN", "days": 7},
]


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
        ("Yahoo!", f"https://shopping.yahoo.co.jp/search?p={q}", "sponsored noopener"),
        ("ヤフオク", f"https://auctions.yahoo.co.jp/search/search?p={q}", "sponsored noopener"),
        ("楽天", rakuten_url, "sponsored noopener"),
    ]


# 商品画像はすべてこのCDNから来る。JSONに何度も書くと無駄なので、
# 共通部分だけ切り出してブラウザ側で足し直す。
IMG_BASE = "https://d7z22c0gz59ng.cloudfront.net/"
# 公式ページのURLはほぼこの形。例外（3件）のときだけそのまま持たせる。
TAMIYA_URL = "https://www.tamiya.com/japan/products/{code}/index.html"


def site_jsonld(desc: str) -> str:
    """検索エンジンに「何のサイトか」を機械可読で伝える（JSON-LD）。

    SearchAction は「このURLで検索できます」という申告なので、
    実際に ?s=... で検索できる状態にしてから出すこと（JS側で対応済み）。
    """
    data = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "WebSite",
                "@id": f"{SITE_URL}/#website",
                "url": f"{SITE_URL}/",
                "name": SITE_NAME,
                "description": desc,
                "inLanguage": "ja",
                "potentialAction": {
                    "@type": "SearchAction",
                    "target": {
                        "@type": "EntryPoint",
                        "urlTemplate": f"{SITE_URL}/?s={{search_term_string}}",
                    },
                    "query-input": "required name=search_term_string",
                },
            },
            {
                "@type": "CollectionPage",
                "@id": f"{SITE_URL}/#webpage",
                "url": f"{SITE_URL}/",
                "name": "タミヤ ミニ四駆・クラフトツール 品番カタログ",
                "description": desc,
                "inLanguage": "ja",
                "isPartOf": {"@id": f"{SITE_URL}/#website"},
            },
        ],
    }
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")


def catalog_payload(items: list[dict]) -> str:
    """商品データを、ブラウザ側でカードを組み立てるための小さなJSONにする。

    1469件ぶんのカードをHTMLに書き出すと4MB近くになり、スマホでは
    HTMLの解析とDOMの構築だけで待たされる。表示に使うのは1ページ24件
    だけなので、データだけ渡して必要なぶんをブラウザ側で作る。

    削れるものは削ってある:
      - 何度も出てくる細分類・ジャンルは一覧表にして番号で参照する
      - 画像URLの共通部分と、規則どおりの公式ページURLは持たせない
      - ECサイトの検索URL（1件あたり5本）は計測IDから組み立てられるので持たせない
    """
    cats: list[str] = []
    genres: list[list[str]] = []
    ci: dict[str, int] = {}
    gi: dict[str, int] = {}
    rows = []
    for it in items:
        cat = it["_cat"]
        if cat not in ci:
            ci[cat] = len(cats)
            cats.append(cat)
        gkey = it["genre_key"]
        if gkey not in gi:
            gi[gkey] = len(genres)
            genres.append([gkey, it["genre"]])
        img = it.get("image", "")
        # 4件だけ "/cms/img/..." という先頭スラッシュだけの相対パスで入っている。
        # そのまま出すとサイト直下を指してしまい画像が出ない（従来はこれで壊れていた）。
        # 他の商品と同じ形なので、CDNのものとして補う。
        if img.startswith("/"):
            img = IMG_BASE + img.lstrip("/")
        if img.startswith(IMG_BASE):
            img = img[len(IMG_BASE):]
        url = it.get("url", "")
        if url == TAMIYA_URL.format(code=it["item_code"]):
            url = ""
        rows.append([it["item_code"], it.get("gp_no", ""), it["name"],
                     ci[cat], gi[gkey], it["price"], img, url])

    data = {"b": IMG_BASE, "c": cats, "g": genres, "i": rows,
            "ec": {"a": AMAZON_TAG, "m": MERCARI_AFID, "r": RAKUTEN_AFID}}
    body = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    # <script> の中に置くので、閉じタグに化ける可能性のある < だけ潰しておく
    return body.replace("<", "\\u003c")


def noscript_list(items: list[dict]) -> str:
    """JavaScriptが動かない環境向けの、素朴な品番一覧。

    scriptが有効なブラウザでは中身が要素として組み立てられないため、
    DOMの重さには影響しない。検索エンジンや読み上げ環境で、
    ページが空にならないようにするための保険。
    """
    rows = "".join(
        '<li><a href="{url}">ITEM {code} {name}</a></li>'.format(
            url=html.escape(it.get("url") or TAMIYA_URL.format(code=it["item_code"])),
            code=it["item_code"], name=html.escape(it["name"]))
        for it in items
    )
    return ('<noscript><div class="nojs"><p>この一覧の絞り込み・検索には '
            'JavaScript が必要です。以下は全品番の一覧です。</p><ul>'
            + rows + "</ul></div></noscript>")


CSS = """
:root{--bg:#f5f6f8;--surface:#fff;--ink:#1a2233;--ink2:#5a6478;--ink3:#8b93a5;
--brand:#1256c4;--brand-soft:#e8f0fd;--line:#e3e6ec;--good:#0e7a4b;--accent:#d81f2a;
font-family:"Hiragino Sans","Noto Sans JP",Meiryo,sans-serif}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--ink);font-size:14px;line-height:1.6}
a{color:inherit;text-decoration:none}
header{background:var(--surface);border-bottom:1px solid var(--line);position:sticky;top:0;z-index:10}
.hwrap{max-width:1120px;margin:0 auto;display:flex;align-items:center;gap:16px;padding:12px 16px;flex-wrap:wrap}
/* タイトルは画像。文字の情報は img の alt と .sr の一文が持っているので、
   検索エンジンにも読み上げにも「ミニ四リン駆」として伝わる。
   width/height を属性で持たせてあるため、読み込み前でも場所が確保され
   レイアウトがガタつかない。 */
.logo{line-height:0}
/* display:block にしておくと、画像下に隙間ができない。
   font-size は 0 にしないこと（.sr の説明文が読み上げられなくなるため）。 */
.logo img{width:248px;height:auto;max-width:56vw;display:block}
/* スマホはロゴの上下に余白を足して窮屈さをなくす（PCの見た目は変えない） */
@media(max-width:600px){.logo img{width:200px}.logo{padding:8px 0}}
.searchbox{flex:1;min-width:240px;display:flex;gap:8px}
.searchbox input{flex:1;border:1.5px solid var(--line);border-radius:8px;padding:8px 12px;font-size:13px;outline:none}
.searchbox input:focus{border-color:var(--brand)}
.tabs{max-width:1120px;margin:0 auto;display:flex;gap:4px;padding:0 16px;flex-wrap:wrap}
.tab{padding:7.6px 20px;font-size:13.5px;font-weight:700;color:var(--ink2);cursor:pointer;
background:var(--surface);border-radius:4px 4px 0 0;user-select:none;white-space:nowrap}
.tab:hover{color:var(--brand);background:var(--brand-soft)}
.tab.on{background:var(--brand);color:#fff}
.tab.on:hover{background:var(--brand);color:#fff}
/* 別ページへ飛ぶタブ。押しても選択状態にはならないので、リンクとして出す。 */
.tab.link{text-decoration:none;display:inline-block}
.tab .n{font-size:11px;font-weight:600;color:var(--ink3);margin-left:6px}
.tab.on .n{color:#cfe0fa}
/* スマホは1段ぶん詰めて4段に収める。字とすき間を一回り小さくし、
   最終段の「レース情報」だけを横いっぱいに置く。PCの見た目は変えない。 */
@media(max-width:600px){
  .tabs{gap:3px;padding:0 10px}
  .tab{padding:6px 20px;font-size:11.5px}
  .tab .n{font-size:10px;margin-left:4px}
  .tab.link{flex:1 0 100%;text-align:center}
}
main{max-width:1120px;margin:0 auto;padding:12px 16px 40px}
/* ---- エンペラー特設（カッコ四駆タブの中） ---- */
/* エンペラーのイメージに合わせてオレンジ。チップもページ送りも同じ色でそろえる */
.chip.emp{background:#f57c00;border-color:#e06f00;color:#fff;font-weight:800}
.chip.emp:hover{background:#ff8f1f}
.chip.emp.on{background:#d35f00;border-color:#bd5500;color:#fff}
.chip.emp .n{margin-left:5px;font-size:10px;opacity:.9}
body.emp #xWall .pager button:hover:not(:disabled){border-color:#f57c00;color:#d35f00}
body.emp #xWall .pager button[aria-current="page"]{background:#f57c00;border-color:#f57c00;color:#fff}
/* カッコ四駆 タブ表示中は商品一覧まわりを出さない */
/* チップ行はエンペラー特設の入口なので、カッコ四駆でも隠さない */
body.wall .cmap,body.wall .cmap-fab,body.wall .count-line,
body.wall .pager,body.wall .grid,body.wall .empty{display:none !important}
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
/* 画面には出さず、読み上げと検索エンジンにだけ伝える見出し */
.sr{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;
clip:rect(0,0,0,0);white-space:nowrap;border:0}
/* JavaScriptが無い環境向けの品番一覧 */
.nojs{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:16px;margin:8px 0}
.nojs p{color:var(--ink2);font-size:12.5px;margin-bottom:10px}
.nojs ul{list-style:none;display:grid;gap:2px}
.nojs a{color:var(--brand);font-size:12.5px}
""" + colormap_ui.CSS + color_wheel_ui.FAB_CSS + godtools_ui.CSS + x_embed_ui.CSS

JS = """
const q = document.getElementById('q');
// .link は別ページへのリンクなので、切り替えの対象からは外す
const tabs = [...document.querySelectorAll('.tab:not(.link)')];
const chips = [...document.querySelectorAll('.chip')];
const chipRow = document.querySelector('.chips');
const grid = document.querySelector('.grid');
const countLine = document.getElementById('countLine');
const empty = document.getElementById('empty');
const favN = document.getElementById('favN');
let genre = '';   // '' = すべて
let cat = '';     // '' = 全カテゴリ

// ---- 商品データ ----
// カードのHTMLはページに焼かれていない。ここでデータを開き、
// 表示するページぶん（24件）だけをそのつど組み立てる。
const XD = JSON.parse(document.getElementById('xdata').textContent);
const ITEMS = XD.i.map(r => {
  const cat_ = XD.c[r[3]], g = XD.g[r[4]], img = r[6];
  return {
    code: r[0], gp: r[1], name: r[2], cat: cat_, gkey: g[0], genre: g[1], price: r[5],
    img: !img ? '' : (img.slice(0, 4) === 'http' ? img : XD.b + img),
    url: r[7] || ('https://www.tamiya.com/japan/products/' + r[0] + '/index.html'),
    // 検索用。品番・GP番号・商品名・細分類・ジャンルをまとめて小文字にしたもの
    hay: (r[0] + ' ' + r[1] + ' ' + r[2] + ' ' + cat_ + ' ' + g[1]).toLowerCase()
  };
});

// ---- カードの組み立て ----
const ESCMAP = {'&':'&amp;','\\u003c':'&lt;','>':'&gt;','"':'&quot;',"'":'&#x27;'};
function esc(s){ return String(s).replace(/[&\\u003c>"']/g, c => ESCMAP[c]); }
function yen(n){ return String(n).replace(/\\B(?=(\\d{3})+(?!\\d))/g, ','); }

// Python の urllib.parse.quote と同じ結果にする。
// encodeURIComponent は !'()* を素通しし / を潰すので、そこだけ合わせる。
function pq(s, keepSlash){
  const o = encodeURIComponent(s).replace(/[!'()*]/g,
    c => '%' + c.charCodeAt(0).toString(16).toUpperCase());
  return keepSlash ? o.replace(/%2F/g, '/') : o;
}

// ECサイトの検索URL。工具と塗料は品番で引いてもほぼヒットしないため商品名で引く。
function ecRow(it){
  const byName = (it.gkey === 'tool' || it.gkey === 'paint');
  const q1 = pq(byName ? 'タミヤ ' + it.name : 'ミニ四駆 ' + it.code, true);
  const mq = pq(byName ? 'タミヤ ' + it.name : it.code + ' タミヤ', true);
  // 楽天は検索語をパスに埋め、その全体をもう一度エンコードして中継URLに渡す
  const rt = pq('https://search.rakuten.co.jp/search/mall/' + q1 + '/', false);
  const links = [
    ['amazon',   'https://www.amazon.co.jp/s?k=' + q1 + '&tag=' + XD.ec.a],
    ['メルカリ', 'https://jp.mercari.com/search?keyword=' + mq + '&afid=' + XD.ec.m],
    ['Yahoo!',   'https://shopping.yahoo.co.jp/search?p=' + q1],
    ['ヤフオク',  'https://auctions.yahoo.co.jp/search/search?p=' + q1],
    ['楽天',     'https://hb.afl.rakuten.co.jp/hgc/' + XD.ec.r + '/?pc=' + rt + '&m=' + rt]
  ];
  return links.map(l => '<a class="ec" href="' + esc(l[1]) +
    '" target="_blank" rel="sponsored noopener">' + esc(l[0]) + '</a>').join('');
}

function cardHTML(it){
  const on = favs.has(it.code);
  const short = it.name.length > 13 ? it.name.slice(0, 13) + '…' : it.name;
  const gp = it.gp ? '　／ ' + esc(it.gp) : '';
  return '<div class="it" id="item-' + esc(it.code) + '" data-code="' + esc(it.code) + '">' +
    '<a class="ph" href="' + esc(it.url) + '" target="_blank" rel="noopener">' +
    '<img src="' + esc(it.img) + '" alt="' + esc(it.name) + '" loading="lazy"></a>' +
    '<div class="bd">' +
      '<div class="row1">' +
        '<button class="btn-fav' + (on ? ' on' : '') + '" type="button" title="' +
          (on ? 'お気に入りから外す' : 'お気に入りに追加') + '">' + (on ? '★' : '☆') + '</button>' +
        '<div class="nm">' + esc(short) + '</div>' +
        '<button class="btn-detail" type="button">詳細</button>' +
      '</div>' +
      '<div class="detail">' +
        '<div class="code">ITEM ' + esc(it.code) + gp + '</div>' +
        '<div class="cat-tag">' + esc(it.cat) + '</div>' +
        '<div class="nmfull">' + esc(it.name) + '</div>' +
        '<div class="pr">¥' + yen(it.price) + ' <small>メーカー希望（税込）</small></div>' +
      '</div>' +
      '<div class="ecrow">' + ecRow(it) + '</div>' +
    '</div></div>';
}

// ---- ページ送り ----
const PER_PAGE = 24;          // 1ページの表示件数
const PAGE_WINDOW = 7;        // 数字ボタンを並べる最大数
let page = 1;
let matched = [];             // 絞り込み後の商品（ページ分割前）
const pagerTop = document.getElementById('pagerTop');
const pagerBottom = document.getElementById('pagerBottom');

// ---- お気に入り（ブラウザのlocalStorageにのみ保存。ログイン不要） ----
const FAV_KEY = 'mini4rinku:favs';
let favs = new Set();
try{ favs = new Set(JSON.parse(localStorage.getItem(FAV_KEY) || '[]')); }catch(e){}

function saveFavs(){
  try{ localStorage.setItem(FAV_KEY, JSON.stringify([...favs])); }catch(e){}
}
// 表示中のカードは組み立て時に★の状態が入るので、ここは件数だけ見る
function paintFavs(){ favN.textContent = favs.size; }

function syncChips(){
  // ジャンル未選択（すべて）・お気に入りのときは細分類を出さない。
  // ジャンル選択時は、そのジャンルに存在する細分類だけ出す。
  // カッコ四駆でも特設チップ（エンペラー）を出したいので、xm を除外しない
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
  const shown = chips.filter(c => c.dataset.cat && !c.classList.contains('hide'));
  // 細分類が1種類だけなら絞り込みにならないので隠す。
  // ただし特設チップ（神ツール・エンペラー）が出ているときは必ず見せる。
  const special = shown.some(c => c.dataset.cat.slice(0, 2) === '__');
  chipRow.style.display = (real && (shown.length > 1 || special)) ? '' : 'none';
}

const WALL_GENRE = 'xm';
const GOD_CAT = '__god';
// カッコ四駆の中の特設チップ。cat をキーに、どのタグで絞るかを引く。
// days があると「その日数以内の投稿だけ」になり、古いものは自動で外れる。
const WALL_CHIPS = %WALL_CHIPS%;
window.__wallChips = WALL_CHIPS;

function apply(resetPage){
  // カッコ四駆 は商品一覧ではないので、絞り込みも件数もページ送りも使わない
  const wall = genre === WALL_GENRE;
  const spec = wall ? WALL_CHIPS.find(c => c.cat === cat) : null;
  document.body.classList.toggle('wall', wall);
  document.body.classList.toggle('emp', !!spec && spec.cat === '__emperor');
  if(window.__xwall){
    wall ? window.__xwall.open(spec ? {tag: spec.tag, days: spec.days} : null)
         : window.__xwall.close();
  }
  if(wall) return;

  // 神ツールも一覧ではない。チップ行だけ残して、商品一覧は出さない。
  const god = cat === GOD_CAT;
  document.body.classList.toggle('god', god);
  if(god) return;

  const terms = q.value.trim().toLowerCase().split(/\\s+/).filter(Boolean);
  matched = ITEMS.filter(it => {
    const okGenre = !genre ? true
                  : genre === 'fav' ? favs.has(it.code)
                  : it.gkey === genre;
    return okGenre
        && (!cat || it.cat === cat)
        && terms.every(t => it.hay.includes(t));
  });
  if(resetPage !== false) page = 1;
  renderPage();
  if(window.paintPins) paintPins();
}

function pageCount(){ return Math.max(1, Math.ceil(matched.length / PER_PAGE)); }

// 指定品番が何ページ目にいるか。絞り込みに含まれなければ 0。
function pageOfCode(code){
  const i = matched.findIndex(it => it.code === code);
  return i < 0 ? 0 : Math.floor(i / PER_PAGE) + 1;
}

function renderPage(){
  const total = pageCount();
  page = Math.min(Math.max(1, page), total);
  const from = (page - 1) * PER_PAGE, to = from + PER_PAGE;
  grid.innerHTML = matched.slice(from, to).map(cardHTML).join('');

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
  // ?s=... を消さずにページ番号だけ付け替える（共有されたURLを壊さないため）
  try{
    const base = location.pathname + location.search;
    history.replaceState(null, '', page > 1 ? base + '#p=' + page : base);
  }catch(e){}
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
  const top = grid.getBoundingClientRect().top + window.scrollY;
  window.scrollTo({top: top - 80, behavior: 'smooth'});
}
pagerTop.addEventListener('click', onPagerClick);
pagerBottom.addEventListener('click', onPagerClick);

// 指定品番を必ず表示できる状態にしてから、そのページへ移動する。
// 検索語や絞り込みで一覧から外れていると今までジャンプできなかったため、
// 邪魔になっている条件を解除してから探し直す。
// 表示中のページにしかカードが無いので、呼んだ側はこのあとに要素を取り直すこと。
window.revealCard = function(code){
  if(!matched.some(it => it.code === code)){
    const it = ITEMS.find(x => x.code === code);
    if(!it) return false;
    if(q.value){ q.value = ''; }        // 検索語を外す
    cat = '';                            // 中カテゴリの絞り込みを外す
    genre = it.gkey;                     // その品番のあるジャンルへ移動
    tabs.forEach(t => t.classList.toggle('on', t.dataset.genre === genre));
    syncChips();
    apply();
  }
  const p = pageOfCode(code);
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

// カードは組み立て直されるので、個別にではなく一覧側で受ける
grid.addEventListener('click', e => {
  // 「詳細」で品番・正式名称・価格を開閉する
  const d = e.target.closest('.btn-detail');
  if(d){
    const open = d.closest('.it').classList.toggle('open');
    d.textContent = open ? '閉じる' : '詳細';
    return;
  }
  // ☆でお気に入りを登録・解除する
  const f = e.target.closest('.btn-fav');
  if(f){
    const code = f.closest('.it').dataset.code;
    const on = !favs.has(code);
    if(on) favs.add(code); else favs.delete(code);
    saveFavs();
    // 押した1つだけ塗り替える（組み立て直すと写真を読み込み直すため）
    f.textContent = on ? '★' : '☆';
    f.classList.toggle('on', on);
    f.title = on ? 'お気に入りから外す' : 'お気に入りに追加';
    paintFavs();
    if(genre === 'fav') apply();   // お気に入り表示中は即座に反映する
  }
});

// ?s=... 付きで開かれたら、その語で検索した状態にする。
// 検索結果をそのまま人に渡せるほか、構造化データの SearchAction の裏付けにもなる。
// apply() より前に入れること（apply の中で URL を書き換えるため）。
try{
  const _s = new URLSearchParams(location.search).get('s');
  if(_s) q.value = _s;
}catch(e){}

paintFavs();
syncChips();
apply();
const _hp = location.hash.match(/p=(\\d)+/);
if(_hp){ page = parseInt(location.hash.replace(/[^0-9]/g, ''), 10) || 1; renderPage(); }
""" + colormap_ui.JS + x_embed_ui.JS


NOT_FOUND_HTML = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ミニ四リン駆</title>
<link rel="icon" href="/assets/favicon.ico?v=2" sizes="any">
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


def race_lastmod(outdir: str) -> str:
    """レースカレンダーの更新日を、ページ内の「最終確認日」から読む。

    ファイルの更新時刻は、CIがチェックアウトした時刻になってしまい
    実態とずれるため使わない。読めなければ今日の日付にしておく。
    """
    path = os.path.join(outdir, "race.html")
    try:
        with open(path, encoding="utf-8") as f:
            m = re.search(r"最終確認日:\s*(\d{4}-\d{2}-\d{2})", f.read())
        if m:
            return m.group(1)
    except OSError:
        pass
    return datetime.now(JST).strftime("%Y-%m-%d")


def write_seo(outdir: str) -> None:
    """robots.txt と sitemap.xml を書き出す。

    検索エンジンに「見に来てよい」「ここにページがある」と伝えるための標識。
    載せるのは実在するページだけにする（404を並べると信用を落とす）。
    """
    # Search Console の所有権確認ファイル。中身は決められた1行だけ。
    with open(os.path.join(outdir, GSC_VERIFY_FILE), "w", encoding="utf-8") as f:
        f.write(f"google-site-verification: {GSC_VERIFY_FILE}")

    with open(os.path.join(outdir, "robots.txt"), "w", encoding="utf-8") as f:
        f.write("User-agent: *\n"
                "Allow: /\n"
                "\n"
                f"Sitemap: {SITE_URL}/sitemap.xml\n")

    today = datetime.now(JST).strftime("%Y-%m-%d")
    pages = [
        # (URL, 最終更新日, 更新のめやす, 優先度)
        (f"{SITE_URL}/", today, "weekly", "1.0"),
        (f"{SITE_URL}/race.html", race_lastmod(outdir), "weekly", "0.8"),
        (f"{SITE_URL}/{color_wheel_ui.PAGE}", today, "weekly", "0.7"),
    ]
    body = "".join(
        f"  <url>\n"
        f"    <loc>{loc}</loc>\n"
        f"    <lastmod>{mod}</lastmod>\n"
        f"    <changefreq>{freq}</changefreq>\n"
        f"    <priority>{pri}</priority>\n"
        f"  </url>\n"
        for loc, mod, freq, pri in pages
    )
    with open(os.path.join(outdir, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                + body +
                "</urlset>\n")


def write_extras(outdir: str) -> None:
    """404ページ・マニフェスト・検索エンジン向けの標識を書き出す。

    404ページは、古いURL（/partspost/ など）をホーム画面アイコンや
    ブックマークが保持していてもトップへ着地させるための保険。
    """
    with open(os.path.join(outdir, "404.html"), "w", encoding="utf-8") as f:
        f.write(NOT_FOUND_HTML)
    with open(os.path.join(outdir, "manifest.webmanifest"), "w", encoding="utf-8") as f:
        json.dump(MANIFEST, f, ensure_ascii=False, indent=1)
    write_seo(outdir)


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
    # X投稿リスト（docs/data/x-featured-posts.json）は手で編集する運用のため、
    # 生成時に触らない。ここでは存在の確認だけしておく。
    if not os.path.exists(os.path.join(outdir, "data", "x-featured-posts.json")):
        print("  注意: data/x-featured-posts.json が見つかりません（X投稿は非表示になります）")

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
        f'<div class="tab" data-genre="{x_embed_ui.WALL_GENRE}">カッコ四駆'
        '<span class="n" id="xmN"></span></div>'
        f'<div class="tab on" data-genre="">すべて<span class="n">{len(items)}</span></div>'
        '<div class="tab fav" data-genre="fav">★ お気に入り<span class="n" id="favN">0</span></div>'
        # レースカレンダーは別ページ。タブと同じ見た目のリンクで並べる。
        '<a class="tab link" href="race.html">🏁レース情報</a>'
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
    ) + '<span class="chip on" data-cat="" data-genres="">すべて</span>' + godtools_ui.chip() + "".join(
        f'<span class="chip{" " + c["cls"] if c.get("cls") else ""}" data-cat="{c["cat"]}" '
        f'data-genres="xm">{html.escape(c["label"])}'
        f'<span class="n" id="{c["badge"]}"></span></span>' for c in WALL_CHIPS)

    # カードのHTMLはここでは作らない。データだけ渡してブラウザ側で組み立てる。
    site_desc = SITE_DESC.format(n=len(items))
    jsonld = site_jsonld(site_desc)
    site_name, site_url = SITE_NAME, SITE_URL
    payload = catalog_payload(items)
    nojs = noscript_list(items)

    paint_rows = paint_colors.build([i for i in items if i.get("genre_key") == "paint"])
    cmap_html = colormap_ui.section(paint_rows) if paint_rows else ""
    god_html = godtools_ui.section({"amazon": AMAZON_TAG, "mercari": MERCARI_AFID,
                                    "rakuten": RAKUTEN_AFID})
    # JS は f-string ではないので、目印を実データに差し替えてから埋める
    js_all = JS.replace("%WALL_CHIPS%", json.dumps(
        WALL_CHIPS, ensure_ascii=False, separators=(",", ":")))
    # マシンカラーのページがあるときだけ、カッコ四駆 用の丸ボタンを出す
    wheel_fab = color_wheel_ui.FAB_HTML if color_wheel_ui.load()[1] else ""

    doc = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="icon" href="assets/favicon.ico?v=2" sizes="any">
<link rel="icon" type="image/png" sizes="32x32" href="assets/favicon-32.png?v=2">
<link rel="apple-touch-icon" href="assets/apple-touch-icon.png?v=2">
<link rel="manifest" href="manifest.webmanifest">
<link rel="canonical" href="https://mini4lin9.fun/">
<meta name="theme-color" content="#d81f2a">
<meta name="apple-mobile-web-app-title" content="ミニ四リン駆">
<title>ミニ四リン駆｜タミヤ ミニ四駆・クラフトツール カタログ（公式品番マスタ）</title>
<meta name="description" content="{site_desc}">
<!-- SNSに貼られたときの見え方（OGP / Twitterカード） -->
<meta property="og:type" content="website">
<meta property="og:site_name" content="{site_name}">
<meta property="og:title" content="ミニ四リン駆｜タミヤ ミニ四駆・クラフトツール カタログ">
<meta property="og:description" content="{site_desc}">
<meta property="og:url" content="{site_url}/">
<meta property="og:image" content="{site_url}/assets/icon-512.png">
<meta property="og:locale" content="ja_JP">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="ミニ四リン駆｜タミヤ ミニ四駆・クラフトツール カタログ">
<meta name="twitter:description" content="{site_desc}">
<meta name="twitter:image" content="{site_url}/assets/icon-512.png">
<script type="application/ld+json">{jsonld}</script>
<style>{CSS}</style>
</head>
<body>
<header>
  <div class="hwrap">
    <h1 class="logo"><a href="index.html"><img src="assets/logo-title.png?v=3"
      width="462" height="86" alt="ミニ四リン駆" fetchpriority="high"
      decoding="async"></a><span
      class="sr">｜タミヤ ミニ四駆・クラフトツール 品番カタログ</span></h1>
    <div class="searchbox"><input id="q" type="search"
      placeholder="品番・商品名で検索（例：15435 / ローラー / ニッパー / エンペラー）"></div>
  </div>
  <div class="tabs">{tab_html}</div>
</header>
<main>
{x_embed_ui.SECTION}
  <div class="chips">{chip_html}</div>
{x_embed_ui.WALL_SECTION}
{god_html}
{cmap_html}
  <div class="count-line" id="countLine"></div>
  <nav class="pager" id="pagerTop" aria-label="ページ送り（上）"></nav>
  <h2 class="sr">商品一覧</h2>
  <div class="grid"></div>
{nojs}
  <nav class="pager" id="pagerBottom" aria-label="ページ送り（下）"></nav>
  <div class="empty" id="empty">該当する商品が見つかりません</div>
  <div class="cmap-tip" id="cmapTip" role="status"></div>
</main>
{wheel_fab}
<footer>
  ミニ四リン駆（プロトタイプ） ・ 品番・名称・価格・写真はタミヤ公式サイトの情報（出典: tamiya.com）<br>
  商品写真は公式サイトから直接参照しています。ECリンクは各モールの検索結果を開きます。
  お気に入りはご利用中のブラウザ内にのみ保存され、サーバーには送信されません。<br>
  <b>【PR】</b>当サイトはアフィリエイトプログラム（メルカリアンバサダー、Amazonアソシエイト、
  楽天アフィリエイト、ValueCommerce）を利用しており、商品リンク経由の購入により
  報酬を受け取る場合があります。
  Amazonアソシエイトとして適格販売により収入を得ています。<br>
  最終更新 {datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")}
</footer>
<script id="xdata" type="application/json">{payload}</script>
<script>{js_all}</script>
<!-- ValueCommerce LinkSwitch: ページ内のYahoo!ショッピング・ヤフオクへのリンクを
     自動でアフィリエイトリンクに差し替える。リンクのURLは書き換えない。 -->
<script>var vc_pid = "{VALUECOMMERCE_PID}";</script>
<script src="//aml.valuecommerce.com/vcdal.js" async></script>
</body>
</html>
"""
    os.makedirs(outdir, exist_ok=True)
    copy_assets(outdir)
    write_extras(outdir)
    color_wheel_ui.write(outdir, SITE_URL, SITE_NAME)
    path = os.path.join(outdir, "index.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)
    return path


X_POSTS_JSON = "docs/data/x-featured-posts.json"
# 投稿URLはこの形以外を認めない。/status/ が抜けると投稿IDを取り出せず、
# 画面上は「その投稿だけ無かったこと」になってしまうため。
X_URL_RE = re.compile(r"^https://(?:x|twitter)\.com/[^/]+/status/\d+$")


def check_x_posts() -> list:
    """X投稿JSONを点検し、問題点を文章のリストで返す。"""
    if not os.path.exists(X_POSTS_JSON):
        return []
    try:
        with open(X_POSTS_JSON, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return ["%s を読めません: %s" % (X_POSTS_JSON, e)]

    posts = data.get("posts") or []
    problems, seen_ids, seen_urls = [], set(), set()
    for i, p in enumerate(posts):
        where = (p or {}).get("id") or "%d番目" % (i + 1)
        url = (p or {}).get("url")
        if not isinstance(url, str) or not X_URL_RE.match(url):
            problems.append("%s: URLの形が違います → %r" % (where, url))
        elif url in seen_urls:
            problems.append("%s: URLが重複しています → %s" % (where, url))
        else:
            seen_urls.add(url)
        pid = (p or {}).get("id")
        if pid in seen_ids:
            problems.append("%s: idが重複しています" % where)
        seen_ids.add(pid)
        if (p or {}).get("active") not in (True, False):
            problems.append("%s: active が true/false ではありません" % where)
    return problems


def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    os.chdir(here)
    problems = check_x_posts()
    if problems:
        print("エラー: %s に問題があります。" % X_POSTS_JSON, file=sys.stderr)
        for m in problems:
            print("  - " + m, file=sys.stderr)
        return 1
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
