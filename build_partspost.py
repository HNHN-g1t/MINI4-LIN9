#!/usr/bin/env python3
"""
パーツポスト - ページ生成スクリプト（4系統ハイブリッド）

使い方:
  # 1) デモ（キー不要・sample_listings.json を使う）
  python3 build_partspost.py --demo

  # 2) 実データ（config.json か環境変数に資格情報を設定）
  cp config.json.example config.json   # 編集して各キーを入れる
  python3 build_partspost.py --query "ミニ四駆 大径ローハイトタイヤ" --item-code 15435

取り込み系統（設定があるものだけ動く。無いものは自動スキップ）:
  Yahoo!ショッピング = 公式API / ヤフオク = ValueCommerce商品API
  メルカリ = 検索ディープリンク / 個人ショップ = shops/*.csv 入稿

出力: partspost.html（データ埋め込み済みの単一HTML）
"""

import argparse
import json
import os
import statistics
import sys
from datetime import datetime, timedelta, timezone

import sources

JST = timezone(timedelta(hours=9))


def load_demo() -> dict:
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "sample_listings.json"), encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------- 相場計算層
def enrich(listings: list[dict], market_median: int | None = None) -> tuple[list[dict], int]:
    """送料込み総額を出し、相場中央値からの乖離率で「安心バッジ」を機械的に付与する。

    ここは真贋判定ではない。あくまで観測データ（価格・出品者評価）の提示。
    """
    for x in listings:
        ship = x.get("shipping")
        x["total"] = x["price"] + (ship if isinstance(ship, int) else 0)
        x["shipping_included"] = isinstance(ship, int) and ship == 0

    totals = [x["total"] for x in listings if x["total"] > 0]
    median = market_median or (int(statistics.median(totals)) if totals else 0)

    for x in listings:
        badges = []
        dev = ((x["total"] - median) / median * 100) if median else 0.0
        x["deviation"] = round(dev, 1)

        if median:
            if dev <= -60:
                badges.append(("warn", f"⚠ 相場より{abs(int(dev))}%安い"))
            elif -45 <= dev <= 45:
                sign = "+" if dev >= 0 else "-"
                badges.append(("good", f"✓ 相場どおり（{sign}{abs(int(dev))}%）"))
            else:
                badges.append(("neutral", "相場からやや乖離"))

        rating = x.get("seller_rating")
        if rating is None or rating == "新規":
            if dev <= -60:
                badges.append(("warn", "出品者評価 新規"))
        if x.get("condition") in ("new", "新品"):
            badges.append(("neutral", "新品"))
        if x.get("is_ad"):
            badges.insert(0, ("neutral", "PR掲載"))

        x["badges"] = badges
    return listings, median


# ---------------------------------------------------------------- 描画層
MALL_LABEL = {
    "mercari": "メルカリ",
    "yahoo": "ヤフオク",           # 旧デモデータ互換
    "yahoo_auction": "ヤフオク",
    "yahoo_shopping": "Yahoo!ショッピング",
    "shop": "SHOP",
}
MALL_CLASS = {
    "mercari": "m",
    "yahoo": "y",
    "yahoo_auction": "y",
    "yahoo_shopping": "h",
    "shop": "s",
}


def render_cards(listings: list[dict]) -> str:
    out = []
    for x in listings:
        cls = "card ad" if x.get("is_ad") else "card"
        mall = x.get("mall", "shop")
        adchip = '<span class="adchip">AD</span>' if x.get("is_ad") else ""
        img = (
            f'<img src="{x["image"]}" alt="" style="width:100%;height:100%;object-fit:cover">'
            if x.get("image")
            else "出品写真"
        )
        ship_txt = "送料込" if x.get("shipping_included") else f'＋送料 ¥{x.get("shipping") or "?"}'
        badges = "".join(f'<span class="b {k}">{v}</span>' for k, v in x["badges"])
        beacon = (
            f'<span style="display:none">{x["pv_beacon"]}</span>' if x.get("pv_beacon") else ""
        )
        seller = x.get("seller") or ""
        if x.get("seller_rating"):
            seller += f' ・ 評価 {x["seller_rating"]}'
        out.append(
            f"""    <a class="{cls}" href="{x.get('url','#')}" target="_blank" rel="nofollow noopener">
      <div class="img"><span class="mall {MALL_CLASS[mall]}">{MALL_LABEL[mall]}</span>{adchip}{img}</div>
      <div class="body">
        <div class="ttl">{x['title']}</div>
        <div class="price">¥{x['total']:,} <small>{ship_txt}</small></div>
        <div class="badges">{badges}</div>
        <div class="seller">{seller}</div>
      </div>{beacon}
    </a>"""
        )
    return "\n".join(out)


def render_deeplinks(deeplinks: list[dict]) -> str:
    """カード化できないモール（メルカリ）への導線を、グリッド末尾の案内カードで出す。"""
    out = []
    for d in deeplinks:
        out.append(
            f"""    <a class="card link" href="{d['url']}" target="_blank" rel="nofollow noopener">
      <div class="img"><span class="mall {MALL_CLASS.get(d['mall'],'s')}">{MALL_LABEL.get(d['mall'],'')}</span>
        <div class="linkbox">外部モールで探す</div></div>
      <div class="body">
        <div class="ttl">{d['title']}</div>
        <div class="price" style="font-size:14px">最新の出品を直接チェック →</div>
        <div class="seller">公開APIがないため一覧化の対象外です</div>
      </div>
    </a>"""
        )
    return "\n".join(out)


def render_sparkline(history: list[dict]) -> str:
    """成約相場の推移（単一系列 / 直近値のみ直接ラベル）"""
    if not history:
        return ""
    vals = [h["value"] for h in history]
    lo, hi = min(vals) * 0.9, max(vals) * 1.1
    span = hi - lo or 1
    x0, x1, y0, y1 = 44, 264, 16, 90
    step = (x1 - x0) / max(len(vals) - 1, 1)
    pts = " ".join(
        f"{x0 + i * step:.0f},{y1 - (v - lo) / span * (y1 - y0):.0f}"
        for i, v in enumerate(vals)
    )
    lx, ly = pts.split(" ")[-1].split(",")
    ticks = "".join(
        f'<text x="{x0 + i * step:.0f}" y="102" font-size="9" fill="#8b93a5" text-anchor="middle">{h["label"]}</text>'
        for i, h in enumerate(history)
        if i % max(len(history) // 4, 1) == 0 or i == len(history) - 1
    )
    return f"""<svg viewBox="0 0 280 110" width="280" height="110" role="img" aria-label="成約相場の推移">
        <line x1="34" y1="16" x2="272" y2="16" stroke="#eef0f4"/>
        <line x1="34" y1="53" x2="272" y2="53" stroke="#eef0f4"/>
        <line x1="34" y1="90" x2="272" y2="90" stroke="#eef0f4"/>
        <text x="30" y="19" font-size="9" fill="#8b93a5" text-anchor="end">¥{hi:,.0f}</text>
        <text x="30" y="93" font-size="9" fill="#8b93a5" text-anchor="end">¥{lo:,.0f}</text>
        <polyline points="{pts}" fill="none" stroke="#1256c4" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
        <circle cx="{lx}" cy="{ly}" r="4" fill="#1256c4" stroke="#ffffff" stroke-width="2"/>
        <text x="{lx}" y="{float(ly)-12:.0f}" font-size="10" font-weight="700" fill="#1a2233" text-anchor="end">¥{vals[-1]:,}</text>
        {ticks}
      </svg>"""


def build_html(data: dict, listings: list[dict], deeplinks: list[dict], median: int, source_note: str) -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "template.html"), encoding="utf-8") as f:
        tpl = f.read()

    # 雛形を直接開いた人向けの警告バナーは、生成時に取り除く
    import re as _re
    tpl = _re.sub(r'<!-- ▼このファイル.*?</div>\n', '', tpl, count=1, flags=_re.S)

    p = data["product"]
    cheapest = min((x["total"] for x in listings), default=0)
    cats = "".join(
        f'<span class="cat{" on" if c == p["category"] else ""}">{c}</span>'
        for c in ["キット", "ボディ", "シャーシ", "プレート", "タイヤ＆ホイール", "ローラー", "ブレーキ", "パーツ全般"]
    )
    tags = "".join(f'<span class="tag">{t}</span>' for t in p.get("tags", []))

    repl = {
        "{{TITLE}}": p["name"],
        "{{ITEM_CODE}}": p["item_code"],
        "{{GP_CODE}}": p["gp_code"],
        "{{CATEGORY_TABS}}": cats,
        "{{CATEGORY}}": p["category"],
        "{{TAGS}}": tags,
        "{{COUNT}}": str(len(listings)),  # 導線カードは件数に含めない
        "{{CHEAPEST}}": f"¥{cheapest:,}",
        "{{MEDIAN}}": f"¥{median:,}",
        "{{QUERY}}": data.get("query", p["item_code"]),
        "{{SPARKLINE}}": render_sparkline(data.get("price_history", [])),
        "{{CARDS}}": render_cards(listings) + ("\n" + render_deeplinks(deeplinks) if deeplinks else ""),
        "{{SOURCE_NOTE}}": source_note,
        "{{UPDATED}}": datetime.now(JST).strftime("%Y-%m-%d %H:%M JST"),
    }
    for k, v in repl.items():
        tpl = tpl.replace(k, v)
    return tpl


# ---------------------------------------------------------------- エントリ
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="キー無しでサンプルデータから生成")
    ap.add_argument("--query", default="ミニ四駆 大径ローハイトタイヤ")
    ap.add_argument("--item-code", default="15435")
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--out", default="partspost.html")
    args = ap.parse_args()

    data = load_demo()

    config = {}
    if os.path.exists(args.config):
        with open(args.config, encoding="utf-8") as f:
            config = json.load(f)

    if args.demo:
        listings = data["listings"]
        deeplinks = [sources.mercari_deeplink(args.item_code)]
        notes = ["デモデータ（サンプル）で生成"]
    else:
        listings, deeplinks, notes = sources.collect(config, args.query, args.item_code)
        if not listings:
            print("警告: どの系統からも出品を取得できませんでした。設定を確認してください。", file=sys.stderr)
            for n in notes:
                print("  -", n, file=sys.stderr)
            sys.exit(1)

    listings, median = enrich(listings)

    # 通常出品は安い順。広告枠は検索結果に「しれっと」混ざるよう2番目・6番目に差し込む。
    ads = [x for x in listings if x.get("is_ad")]
    organic = sorted((x for x in listings if not x.get("is_ad")), key=lambda x: x["total"])
    for slot, ad in zip((1, 5), ads):
        organic.insert(min(slot, len(organic)), ad)
    listings = organic

    html = build_html(data, listings, deeplinks, median, " ／ ".join(notes))
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"生成完了: {args.out} ／ {len(listings)}件 ／ 相場中央値 ¥{median:,}")
    for n in notes:
        print("  -", n)


if __name__ == "__main__":
    main()
