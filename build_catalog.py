#!/usr/bin/env python3
"""
パーツポスト - カタログ一括生成

catalog.json の全品番についてページを生成し、入口となる一覧ページも作る。
出力先: site/  （index.html + items/15xxx.html）

使い方:
    python3 build_catalog.py --demo          # キー不要・疑似データで全ページ生成
    python3 build_catalog.py                 # 実データ（config.json 必要）
    python3 build_catalog.py --limit 5       # 先頭5件だけ（お試し・API節約）

※ Yahoo!ショッピングAPIは「1クエリ/秒」制限があるため、
  実データ取得時は1件ごとに1.2秒の待機を入れている。
"""

import argparse
import html
import json
import os
import shutil
import sys
import time
from datetime import datetime, timedelta, timezone

import build_partspost as bp
import sources

JST = timezone(timedelta(hours=9))
CATEGORIES = ["キット", "ボディ", "シャーシ", "プレート", "タイヤ＆ホイール", "ローラー", "ブレーキ", "パーツ全般"]
API_INTERVAL = 1.2  # 秒（1クエリ/秒制限を守る）


# ---------------------------------------------------------------- 疑似データ
def synth_listings(item: dict) -> list[dict]:
    """デモ用の疑似出品。定価を基準に決定論的なばらつきを作る（乱数は使わない）。"""
    base = item["price"]
    seed = int(item["code"]) % 7
    specs = [
        ("mercari", "新品未開封", 0.92, 0, "★4.9（412）", False),
        ("yahoo_auction", "中古 動作確認済み", 0.68, 0, "98.7%（1,204）", False),
        ("shop", "店頭在庫あり・当日発送", 1.04, 0, None, True),
        ("mercari", "開封済み未使用", 0.81, 0, "★5.0（88）", False),
        ("yahoo_shopping", "正規品 送料無料", 1.12, 0, None, False),
        ("shop", "中古良品", 0.58, 185, None, False),
        ("mercari", "まとめ売り 4個セット", 0.31, 0, None, False),
    ]
    out = []
    for i, (mall, note, ratio, ship, rating, is_ad) in enumerate(specs):
        if (i + seed) % 7 == 6 and i != 6:
            continue  # 品番ごとに件数を変える
        price = max(50, int(base * ratio / 10) * 10)
        out.append(
            {
                "mall": mall,
                "title": f"{item['code']} {item['name'][:26]} {note}",
                "price": price,
                "shipping": ship,
                "url": "#",
                "image": "",
                "seller": {"shop": "個人ショップ", "mercari": "個人", "yahoo_auction": "個人", "yahoo_shopping": "ストア"}[mall],
                "seller_rating": rating,
                "condition": "新品" if "新品" in note else "中古",
                "is_ad": is_ad,
                "source": "demo",
            }
        )
    return out


# ---------------------------------------------------------------- 個別ページ
def build_item_page(item: dict, listings: list[dict], deeplinks: list[dict], note: str, outdir: str) -> dict:
    listings, median = bp.enrich(listings)

    ads = [x for x in listings if x.get("is_ad")]
    organic = sorted((x for x in listings if not x.get("is_ad")), key=lambda x: x["total"])
    for slot, ad in zip((1, 5), ads):
        organic.insert(min(slot, len(organic)), ad)
    listings = organic

    data = {
        "query": item["code"],
        "product": {
            "item_code": f"ITEM {item['code']}",
            "gp_code": item["gp"],
            "name": item["name"],
            "category": item["category"],
            "tags": item.get("tags", []),
        },
        "price_history": [],  # 実運用では日次実行で蓄積する
    }

    tpl_html = bp.build_html(data, listings, deeplinks, median, note)
    # 個別ページは site/items/ に置くのでトップへ戻る導線を入れる
    tpl_html = tpl_html.replace(
        '<a class="logo">パーツ<span>ポスト</span></a>',
        '<a class="logo" href="../index.html">パーツ<span>ポスト</span></a>',
    )
    # 相場履歴が無い間はチャート欄に案内を出す
    tpl_html = tpl_html.replace(
        '<div class="sub">過去6ヶ月 ・ 全モール成約データ</div>\n      ',
        '<div class="sub">過去6ヶ月 ・ 全モール成約データ</div>\n      '
        '<div style="height:110px;display:flex;align-items:center;justify-content:center;'
        'color:#8b93a5;font-size:12px;text-align:center;line-height:1.8">'
        '相場データを蓄積中です<br>毎日の実行で推移グラフが表示されます</div>',
    )

    path = os.path.join(outdir, "items", f"{item['code']}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(tpl_html)

    cheapest = min((x["total"] for x in listings), default=0)
    return {**item, "count": len(listings), "cheapest": cheapest, "median": median}


# ---------------------------------------------------------------- 一覧ページ
INDEX_CSS = """
:root{--bg:#f5f6f8;--surface:#fff;--ink:#1a2233;--ink2:#5a6478;--ink3:#8b93a5;
--brand:#1256c4;--brand-soft:#e8f0fd;--line:#e3e6ec;--good:#0e7a4b;
font-family:"Hiragino Sans","Noto Sans JP",Meiryo,sans-serif}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--ink);font-size:14px;line-height:1.6}
a{color:inherit;text-decoration:none}
header{background:var(--surface);border-bottom:1px solid var(--line)}
.hwrap{max-width:1080px;margin:0 auto;display:flex;align-items:center;gap:16px;padding:14px 16px}
.logo{font-weight:800;font-size:20px;color:var(--brand)}
.logo span{color:var(--ink)}
.tagline{font-size:12px;color:var(--ink3)}
main{max-width:1080px;margin:0 auto;padding:20px 16px 40px}
.hero{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:22px;margin-bottom:20px}
.hero h1{font-size:20px;margin-bottom:6px}
.hero p{font-size:13px;color:var(--ink2)}
.kpis{display:flex;gap:26px;margin-top:14px}
.kpi .v{font-size:22px;font-weight:800}
.kpi .l{font-size:11px;color:var(--ink3)}
h2{font-size:15px;margin:26px 0 10px;padding-left:10px;border-left:3px solid var(--brand)}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
.it{background:var(--surface);border:1px solid var(--line);border-radius:9px;padding:12px;display:flex;
flex-direction:column;gap:5px;transition:box-shadow .15s,transform .15s}
.it:hover{box-shadow:0 4px 14px rgba(20,40,80,.10);transform:translateY(-1px)}
.code{font-size:10.5px;font-weight:800;color:var(--ink3);letter-spacing:.03em}
.nm{font-size:12.5px;line-height:1.45;min-height:54px;display:-webkit-box;-webkit-line-clamp:3;
-webkit-box-orient:vertical;overflow:hidden}
.pr{font-size:17px;font-weight:800;margin-top:auto}
.pr small{font-size:10.5px;font-weight:600;color:var(--ink3)}
.cnt{font-size:11px;color:var(--good);font-weight:700}
.cnt.zero{color:var(--ink3);font-weight:400}
footer{max-width:1080px;margin:0 auto;padding:16px;font-size:11px;color:var(--ink3);border-top:1px solid var(--line)}
@media(max-width:900px){.grid{grid-template-columns:repeat(2,1fr)}}
"""


def build_index(results: list[dict], note: str, outdir: str) -> None:
    total_listings = sum(r["count"] for r in results)
    sections = []
    for cat in CATEGORIES:
        rows = [r for r in results if r["category"] == cat]
        if not rows:
            continue
        cards = []
        for r in rows:
            cnt = (
                f'<div class="cnt">{r["count"]}件の出品</div>'
                if r["count"]
                else '<div class="cnt zero">出品なし</div>'
            )
            price = f'¥{r["cheapest"]:,} <small>最安</small>' if r["cheapest"] else "—"
            cards.append(
                f'''      <a class="it" href="items/{r["code"]}.html">
        <div class="code">ITEM {r["code"]} ／ {html.escape(r["gp"])}</div>
        <div class="nm">{html.escape(r["name"])}</div>
        <div class="pr">{price}</div>
        {cnt}
      </a>'''
            )
        sections.append(f'    <h2>{cat}（{len(rows)}品番）</h2>\n    <div class="grid">\n' + "\n".join(cards) + "\n    </div>")

    doc = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>パーツポスト｜ミニ四駆パーツ 相場・出品横断カタログ</title>
<style>{INDEX_CSS}</style>
</head>
<body>
<header>
  <div class="hwrap">
    <a class="logo">パーツ<span>ポスト</span></a>
    <span class="tagline">ミニ四駆パーツの相場と出品を、モール横断でまとめて見る</span>
  </div>
</header>
<main>
  <div class="hero">
    <h1>品番から探すパーツカタログ</h1>
    <p>メルカリ・ヤフオク・個人ショップの出品を品番単位で集約しています。相場中央値からの乖離は自動で表示されます。</p>
    <div class="kpis">
      <div class="kpi"><div class="v">{len(results)}</div><div class="l">掲載品番</div></div>
      <div class="kpi"><div class="v">{total_listings:,}</div><div class="l">集約した出品</div></div>
      <div class="kpi"><div class="v">{len([c for c in CATEGORIES if any(r["category"]==c for r in results)])}</div><div class="l">カテゴリ</div></div>
    </div>
  </div>
{chr(10).join(sections)}
</main>
<footer>
  パーツポスト（プロトタイプ） ・ {html.escape(note)} ・ 最終更新 {datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")}<br>
  掲載価格・出品は各モールの情報を集約したものです。⚠表示は成約相場との乖離・出品者評価など客観データに基づく自動表示です。
</footer>
</body>
</html>
"""
    with open(os.path.join(outdir, "index.html"), "w", encoding="utf-8") as f:
        f.write(doc)


# ---------------------------------------------------------------- エントリ
def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    os.chdir(here)

    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="先頭N件だけ生成")
    ap.add_argument("--outdir", default="site")
    args = ap.parse_args()

    with open("catalog.json", encoding="utf-8") as f:
        items = json.load(f)["items"]
    if args.limit:
        items = items[: args.limit]

    config = {}
    if os.path.exists("config.json"):
        with open("config.json", encoding="utf-8") as f:
            config = json.load(f)

    if not args.demo and not (config.get("yahoo_appid") or os.environ.get("YAHOO_APPID")):
        print("エラー: config.json に yahoo_appid がありません。--demo なら不要です。", file=sys.stderr)
        return 1

    outdir = args.outdir
    shutil.rmtree(outdir, ignore_errors=True)
    os.makedirs(os.path.join(outdir, "items"), exist_ok=True)

    total = len(items)
    est = "" if args.demo else f"（想定所要 約{int(total * API_INTERVAL / 60) + 1}分）"
    print(f"カタログ生成を開始します: {total}品番{est}\n")

    results = []
    for i, item in enumerate(items, 1):
        label = f"[{i:>2}/{total}] {item['code']} {item['name'][:28]}"
        try:
            if args.demo:
                listings = synth_listings(item)
                deeplinks = [sources.mercari_deeplink(item["code"])]
                note = "デモデータ（疑似出品）で生成"
            else:
                listings, deeplinks, notes = sources.collect(config, item["name"], item["code"])
                note = " ／ ".join(notes)
                if i < total:
                    time.sleep(API_INTERVAL)  # 1クエリ/秒制限の遵守
            r = build_item_page(item, listings, deeplinks, note, outdir)
            results.append(r)
            print(f"{label} … {r['count']}件")
        except Exception as e:
            print(f"{label} … 失敗 ({e})")
            results.append({**item, "count": 0, "cheapest": 0, "median": 0})

    note = "デモデータ（疑似出品）" if args.demo else "実データ取得"
    build_index(results, note, outdir)

    index_path = os.path.abspath(os.path.join(outdir, "index.html"))
    print(f"\n完了: {len(results)}品番 ／ 出品 {sum(r['count'] for r in results):,}件")
    print(f"入口ページ: {index_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
