# -*- coding: utf-8 -*-
"""「神ツール」— ツールタブの中に置く、読み物寄りの商品紹介コーナー。

品番カタログの一覧とは性質が違うため、チップを選んだときだけ
一覧を隠してこのコーナーを出す。

商品を足すときは ITEMS に1つ増やすだけでよい。
asin は Amazon の商品ページURL（/dp/XXXXXXXXXX）から取れる10文字。
image は SiteStripe が出す m.media-amazon.com の画像URLを使う。
"""
import html
import urllib.parse

# チップの合言葉。細分類の名前と混ざらないよう、記号で始めておく。
CAT = "__god"

# text は1行が1要素。書いたとおりの位置で改行される。
ITEMS = [
    {
        "name": "アネックス(ANEX) ハンドル 差替式",
        # Amazon上の正式名称。品番まで含めて取り違えを防ぐ。
        "official": "アネックス(ANEX) ハンドル 差替式 精密タイプ (ビットなし) No.3610-H",
        "asin": "B00I0HJEDO",
        "image": "https://m.media-amazon.com/images/I/31ApVgLTOOL._SL500_.jpg",
        # amazon以外のショップは検索で当てる。ここを変えれば検索語を調整できる。
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
]

CSS = """
/* ---- 神ツール（ツールタブ内の読み物コーナー） ---- */
/* 選んでいる間は商品一覧まわりを出さない。チップ行だけは残す。 */
body.god .count-line,body.god .pager,body.god .grid,
body.god .empty,body.god .cmap,body.god .cmap-fab{display:none !important}
.chip.god{background:#f5c518;border-color:#e2b400;color:#4a3800;font-weight:800}
.chip.god:hover{background:#ffd42a}
.chip.god.on{background:#d99b00;border-color:#c08a00;color:#fff}
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
/* amazon だけは品番が分かっていて商品ページへ直接飛ぶので目立たせる */
.gec.az{background:#ff9900;border-color:#e88a00;color:#1a2233;
box-shadow:0 2px 6px rgba(255,153,0,.32)}
.gec.az:hover{background:#ffad33;border-color:#ff9900;color:#1a2233}
.god-note{font-size:11px;color:var(--ink3);margin-top:2px}
"""


def _link(asin: str, tag: str) -> str:
    return f"https://www.amazon.co.jp/dp/{asin}?tag={tag}&linkCode=ll1&language=ja_JP"


def shops(it: dict, ids: dict) -> list:
    """ショップへのリンクを (ラベル, URL) で返す。並びは商品一覧と同じ。

    amazon だけは品番が分かっているので商品ページへ直接飛ばす。
    他は検索結果へ飛ばす（メルカリは中古なので個別の出品はすぐ消えるため、
    直リンクにすると切れたリンクになってしまう）。
    Yahoo!とヤフオクにIDを付けないのは、ページに入れてある
    ValueCommerce の LinkSwitch が自動で差し替えてくれるため。
    """
    term = it.get("search") or it["official"]
    q = urllib.parse.quote(term)
    rt = urllib.parse.quote(f"https://search.rakuten.co.jp/search/mall/{q}/", safe="")
    return [
        ("amazon", _link(it["asin"], ids["amazon"])),
        ("メルカリ", f"https://jp.mercari.com/search?keyword={q}&afid={ids['mercari']}"),
        ("Yahoo!", f"https://shopping.yahoo.co.jp/search?p={q}"),
        ("ヤフオク", f"https://auctions.yahoo.co.jp/search/search?p={q}"),
        ("楽天", f"https://hb.afl.rakuten.co.jp/hgc/{ids['rakuten']}/?pc={rt}&m={rt}"),
    ]


def section(ids: dict) -> str:
    """神ツールのHTML。ids は各アフィリエイトの計測ID。"""
    cards = []
    for it in ITEMS:
        url = html.escape(_link(it["asin"], ids["amazon"]))
        row = "".join(
            f'<a class="gec{" az" if lb == "amazon" else ""}" href="{html.escape(u)}" '
            f'target="_blank" rel="sponsored noopener">{html.escape(lb)}</a>'
            for lb, u in shops(it, ids))
        # 書かれたとおりの位置で改行する。狭い画面では各行がさらに折り返す。
        lines = it["text"] if isinstance(it["text"], list) else [it["text"]]
        body = "<br>".join(html.escape(ln) for ln in lines)
        cards.append(f"""  <article class="gitem">
    <a class="gshot" href="{url}" target="_blank" rel="sponsored noopener">
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
  <p class="god-note">amazonは商品ページへ、ほかのショップは検索結果へ移動します。
  価格・在庫は各ショップの表示をご確認ください。</p>
</section>"""


def chip() -> str:
    """ツールジャンルの最後に置く黄色いチップ。"""
    return (f'<span class="chip god" data-cat="{CAT}" data-genres="tool">神ツール</span>')
