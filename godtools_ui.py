# -*- coding: utf-8 -*-
"""「神ツール」— 上段タブの1つ。読み物寄りの商品紹介コーナー。

品番カタログの一覧とは性質が違うため、このタブを選んだときだけ
商品一覧を隠してこのコーナーを出す。

商品を足すときは ITEMS に1つ増やすだけでよい。
直リンクは次のどちらか（両方でもよい）。無ければ検索リンクになる。
  asin        … Amazonの商品ページURL（/dp/XXXXXXXXXX）から取れる10文字
  rakuten_url … 楽天の商品ページURL（余計な追跡パラメータは外して入れる）
image は商品ページの画像URL。text は1行が1要素で、書いたとおりに改行される。
only を書くと、そのショップのリンクだけを出す（正規品がそこにしか無い商品用）。
"""
import html
import urllib.parse

# 上段タブのジャンルキー。build_official_index.py と合わせること。
GENRE = "god"

ITEMS = [
    {
        "name": "アネックス(ANEX) ハンドル 差替式",
        # 販売ページ上の正式名称。品番まで含めて取り違えを防ぐ。
        "official": "アネックス(ANEX) ハンドル 差替式 精密タイプ (ビットなし) No.3610-H",
        "asin": "B00I0HJEDO",
        "image": "https://m.media-amazon.com/images/I/31ApVgLTOOL._SL500_.jpg",
        # 直リンクが無いショップは検索で当てる。ここを変えれば検索語を調整できる。
        "search": "アネックス 差替ハンドル 3610",
        "text": [
            "ご本家同等アイテム。ミニ四ドライバー＆ボックスドライバーにスーパーフィット。",
            "通常ナット用とロックナット用で2本用意すればメンテ効率が大幅アップします。",
        ],
    },
    {
        "name": "高儀(Takagi) ホビークイックバークランプ ブラック 100mm 2個組",
        "official": "高儀(Takagi) ホビークイックバークランプ ブラック 100mm 2個組 HQB-100-2P",
        "asin": "B00G8PR80G",
        "image": "https://m.media-amazon.com/images/I/617uV1xgqVL._SL500_.jpg",
        "search": "高儀 ホビークイックバークランプ 100mm",
        "text": [
            "貫通済ホイールのシャフト差しに最適！",
            "トリガーでギュッと段階的に差し込む手ごたえ◎子供でも使えてケガ防止◎",
            "サイズバッチリ携行性◎本体シャフトが金属製で耐久性◎",
        ],
    },
    {
        "name": "ミニ四駆ワーキングボックス",
        "official": "汐見板金Web-Shop ミニ四駆ワーキングボックス",
        # 楽天ショップの商品。Amazonの品番が無いので、直リンクは楽天側に持たせる。
        "rakuten_url": "https://item.rakuten.co.jp/shop-siomi/m4d-tls-wkb/",
        # 正規品は楽天のこのショップでしか売っていないので、他店の検索は出さない
        "only": ["楽天"],
        "image": "https://shop.r10s.jp/shop-siomi/cabinet/product-img/m4d-tls-wkb-01b.jpg",
        "search": "ミニ四駆 ワーキングボックス",
        "text": [
            "ミニ四駆パーツの切る・削る・穴をあけるといった基本作業を土台から支えてくれる必須アイテムです。",
            "頑強な作りと四方の集塵スリットは、ご家庭を汚せない（笑）お父さんやキッズの頼もしい味方です！",
        ],
    },
]

CSS = """
/* ---- 神ツール（上段タブの1つ） ---- */
/* 選んでいる間は商品一覧まわりを出さない */
body.god .chips,body.god .chipbox,body.god .count-line,body.god .pager,
body.god .grid,body.god .empty,body.god .cmap,body.god .cmap-fab{display:none !important}
.god-sec{display:none;margin:6px 0 8px}
body.god .god-sec{display:block}
.god-head{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin:0 0 4px}
.god-head h2{font-size:16px;letter-spacing:.04em}
.god-head .pr{font-size:10.5px;font-weight:800;color:#8a6d00;background:#fff5cc;
border:1px solid #ecd88a;border-radius:4px;padding:1px 6px}
.god-lead{font-size:12px;color:var(--ink3);margin:0 0 14px}
.gitem{background:var(--surface);border:1px solid var(--line);border-radius:12px;
overflow:hidden;display:flex;gap:0;margin-bottom:14px}
@media(max-width:640px){.gitem{flex-direction:column}}
/* 画像が届かなくても枠が潰れないよう、高さの下限を決めておく */
.gshot{flex:none;width:220px;min-height:150px;background:#fff;display:flex;
align-items:center;justify-content:center;padding:14px;border-right:1px solid var(--line)}
@media(max-width:640px){.gshot{width:100%;border-right:none;border-bottom:1px solid var(--line)}}
.gshot img{width:100%;height:auto;max-height:200px;object-fit:contain;display:block}
.gbody{padding:14px 16px 16px;display:flex;flex-direction:column;gap:8px;min-width:0}
.gbody h3{font-size:15px;letter-spacing:.02em}
.gbody .official{font-size:11px;color:var(--ink3)}
.gbody p{font-size:13px;line-height:1.75;color:var(--ink2)}
/* 紹介文。書いた位置で改行しつつ、行頭がぶら下がらないようにする */
.gbody .desc{line-height:1.85;overflow-wrap:anywhere}
/* ショップへのリンク。並びは商品一覧のカードと同じ */
.gecrow{display:flex;gap:7px;flex-wrap:wrap;margin-top:4px}
.gec{font-size:11.5px;font-weight:700;border-radius:7px;padding:6px 14px;
border:1px solid var(--line);color:var(--ink2);background:var(--surface)}
.gec:hover{background:var(--brand-soft);border-color:var(--brand);color:var(--brand)}
/* その商品ページへ直接飛べるショップだけ色を付ける。
   検索に飛ぶだけのものと区別が付くように。 */
.gec.direct.az{background:#ff9900;border-color:#e88a00;color:#1a2233;
box-shadow:0 2px 6px rgba(255,153,0,.32)}
.gec.direct.az:hover{background:#ffad33;border-color:#ff9900;color:#1a2233}
.gec.direct.rk{background:#bf0000;border-color:#a30000;color:#fff;
box-shadow:0 2px 6px rgba(191,0,0,.3)}
.gec.direct.rk:hover{background:#d51616;border-color:#bf0000;color:#fff}
.god-note{font-size:11px;color:var(--ink3);margin-top:2px}
"""


def _amazon(asin: str, tag: str) -> str:
    return f"https://www.amazon.co.jp/dp/{asin}?tag={tag}&linkCode=ll1&language=ja_JP"


def _rakuten(target: str, afid: str) -> str:
    """楽天は遷移先をまるごとURLエンコードして中継URLに渡す形式。"""
    t = urllib.parse.quote(target, safe="")
    return f"https://hb.afl.rakuten.co.jp/hgc/{afid}/?pc={t}&m={t}"


def shops(it: dict, ids: dict) -> list:
    """ショップへのリンクを (ラベル, URL, 直リンクか, 印) で返す。

    並びは商品一覧のカードと同じ。品番やURLが分かっているショップは
    その商品ページへ直接飛ばし、それ以外は検索結果へ飛ばす。
    メルカリを検索にしているのは、中古の個別出品はすぐ消えてしまい、
    直リンクにすると切れたリンクになるため。
    Yahoo!とヤフオクにIDを付けないのは、ページに入れてある
    ValueCommerce の LinkSwitch が自動で差し替えてくれるため。
    only があるショップは、そこでしか正規品が買えない商品。
    関係ない検索結果へ送らないよう、指定されたショップだけを残す。
    """
    term = it.get("search") or it["official"]
    q = urllib.parse.quote(term)
    rk_search = f"https://search.rakuten.co.jp/search/mall/{q}/"

    amazon = ((_amazon(it["asin"], ids["amazon"]), True) if it.get("asin")
              else (f"https://www.amazon.co.jp/s?k={q}&tag={ids['amazon']}", False))
    rakuten = ((_rakuten(it["rakuten_url"], ids["rakuten"]), True) if it.get("rakuten_url")
               else (_rakuten(rk_search, ids["rakuten"]), False))
    rows = [
        ("amazon", amazon[0], amazon[1], "az"),
        ("メルカリ", f"https://jp.mercari.com/search?keyword={q}&afid={ids['mercari']}",
         False, "mr"),
        ("Yahoo!", f"https://shopping.yahoo.co.jp/search?p={q}", False, "yh"),
        ("ヤフオク", f"https://auctions.yahoo.co.jp/search/search?p={q}", False, "ya"),
        ("楽天", rakuten[0], rakuten[1], "rk"),
    ]
    only = it.get("only")
    return [r for r in rows if r[0] in only] if only else rows


def section(ids: dict) -> str:
    """神ツールのHTML。ids は各アフィリエイトの計測ID。"""
    cards = []
    for it in ITEMS:
        links = shops(it, ids)
        # 写真を押したときの行き先は、その商品ページへ直接飛べるショップを優先する
        main = next((u for _, u, direct, _k in links if direct), links[0][1])
        row = "".join(
            f'<a class="gec{" direct " + k if direct else ""}" href="{html.escape(u)}" '
            f'target="_blank" rel="sponsored noopener">{html.escape(lb)}</a>'
            for lb, u, direct, k in links)
        # 書かれたとおりの位置で改行する。狭い画面では各行がさらに折り返す。
        lines = it["text"] if isinstance(it["text"], list) else [it["text"]]
        body = "<br>".join(html.escape(ln) for ln in lines)
        cards.append(f"""  <article class="gitem">
    <a class="gshot" href="{html.escape(main)}" target="_blank" rel="sponsored noopener">
      <img src="{html.escape(it["image"])}" alt="{html.escape(it["name"])}"
           loading="lazy" decoding="async"></a>
    <div class="gbody">
      <h3>{html.escape(it["name"])}</h3>
      <p class="official">{html.escape(it["official"])}</p>
      <p class="desc">{body}</p>
      <div class="gecrow">{row}</div>
    </div>
  </article>""")
    return f"""<section class="god-sec" id="godSec" aria-label="神ツール">
  <div class="god-head"><h2>神ツール</h2><span class="pr">PR</span></div>
  <p class="god-lead">タミヤ純正ではないけれど、ミニ四駆に効く道具を紹介します。
  実際に使ってよかったものだけを載せています。</p>
{chr(10).join(cards)}
  <p class="god-note">色の付いたショップは商品ページへ、ほかは検索結果へ移動します。
  価格・在庫は各ショップの表示をご確認ください。</p>
</section>"""


def tab() -> str:
    """上段タブ。「ツール」の次に置く。見た目は他のタブと揃える。"""
    return (f'<div class="tab" data-genre="{GENRE}">神ツール'
            f'<span class="n">{len(ITEMS)}</span></div>')
