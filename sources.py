#!/usr/bin/env python3
"""
パーツポスト - データ取り込み層（4系統ハイブリッド）

  系統1: Yahoo!ショッピング …… 公式API v3（無料・要Client ID）
  系統2: ヤフオク!         …… ValueCommerce商品API（要アフィリエイト提携＋トークン）
  系統3: メルカリ          …… 検索ディープリンク生成のみ（公開APIなし・スクレイピング禁止）
  系統4: 個人ショップ      …… CSV入稿（BASE/STORESのエクスポート形式に対応）

すべてのアダプタは共通スキーマ（dict）を返す:
  mall, title, price, shipping, url, image, seller, seller_rating,
  condition, is_ad, source
"""

import csv
import json
import os
import urllib.parse
import urllib.request

UA = {"User-Agent": "partspost/0.2 (+catalog aggregator prototype)"}


def _get_json(url: str, timeout: int = 20) -> dict:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.load(res)


# ================================================================ 系統1: Yahoo!ショッピング
YAHOO_ENDPOINT = "https://shopping.yahooapis.jp/ShoppingWebService/V3/itemSearch"


def fetch_yahoo(
    appid: str,
    query: str,
    results: int = 20,
    affiliate_id: str | None = None,
) -> list[dict]:
    """Yahoo!ショッピング 商品検索API v3。新品・ショップ在庫が中心。

    appid       : Yahoo!デベロッパーネットワークで発行したClient ID（必須）
    affiliate_id: ValueCommerceのアフィリエイトID（任意）。指定すると
                  返却URLが成果計測付きになり、収益化できる。
    制限        : 1クエリ/秒。連続実行時はsleepを入れること。
    """
    q: dict = {"appid": appid, "query": query, "results": results, "sort": "+price"}
    if affiliate_id:
        q["affiliate_type"] = "vc"
        q["affiliate_id"] = affiliate_id
    params = urllib.parse.urlencode(q)
    payload = _get_json(f"{YAHOO_ENDPOINT}?{params}")
    out = []
    for hit in payload.get("hits", []):
        out.append(
            {
                "mall": "yahoo_shopping",
                "title": hit.get("name", ""),
                "price": int(hit.get("price") or 0),
                "shipping": 0 if (hit.get("shipping") or {}).get("code") == 1 else None,
                "url": hit.get("url", ""),
                "image": ((hit.get("image") or {}).get("medium")) or "",
                "seller": (hit.get("seller") or {}).get("name", ""),
                "seller_rating": None,
                "condition": hit.get("condition", ""),
                "source": "yahoo_api_v3",
            }
        )
    return out


# ================================================================ 系統2: ヤフオク!（ValueCommerce商品API）
VC_ENDPOINT = "http://webservice.valuecommerce.ne.jp/productdb/search"
# ヤフオク!の広告主サイトコード（ecCode）は提携承認後にVC管理画面で確認する。
# 「広告」→「対応機能別」→「Webサービス」にトークン、提携一覧にecCodeがある。


def fetch_valuecommerce(
    token: str,
    keyword: str,
    ec_code: str | None = None,
    results: int = 20,
    price_min: int | None = None,
    price_max: int | None = None,
) -> list[dict]:
    """ValueCommerce商品API。format=json で取得し共通スキーマへ正規化。

    ヤフオク!検索API終了（2020年1月）後の実質的な公式ルート。
    link はクリックスルーURL（成果計測込み）なのでそのまま販売欄に張れる。
    vc:pvImg（表示カウント用ビーコン）は規約上ページに埋め込むこと。
    """
    q: dict = {
        "token": token,
        "keyword": keyword,
        "results_per_page": min(results, 50),
        "sort_by": "price",
        "format": "json",
    }
    if ec_code:
        q["ecCode"] = ec_code
    if price_min is not None:
        q["price_min"] = price_min
    if price_max is not None:
        q["price_max"] = price_max

    payload = _get_json(f"{VC_ENDPOINT}?{urllib.parse.urlencode(q)}")

    # JSON形式はRSS構造を写した形: channel > item[]（環境により rss キーを挟む）
    channel = payload.get("rss", payload).get("channel", payload.get("channel", {}))
    items = channel.get("item", [])
    if isinstance(items, dict):
        items = [items]

    out = []
    for it in items:
        vc = {k.replace("vc:", ""): v for k, v in it.items() if k.startswith("vc:")}
        price = int(float(vc.get("price") or 0))
        out.append(
            {
                "mall": "yahoo_auction",
                "title": it.get("title", ""),
                "price": price,
                "shipping": None,  # フィードに送料情報なし → 総額表示は「＋送料」表記
                "url": it.get("link", ""),
                "image": vc.get("imageUrl") or vc.get("image") or "",
                "seller": vc.get("merchantName", "ヤフオク!"),
                "seller_rating": None,
                "condition": "",
                "pv_beacon": vc.get("pvImg", ""),  # 必須ビーコン
                "source": "valuecommerce",
            }
        )
    return out


# ================================================================ 系統3: メルカリ（ディープリンクのみ）
def mercari_deeplink(query: str, ambassador_suffix: str = "") -> dict:
    """メルカリは公開検索APIが存在しないため、検索結果への導線カードを返す。

    ambassador_suffix にメルカリアンバサダーの計測パラメータを渡せば
    アフィリエイト成果の対象にできる（リンク形式は自身の管理画面で要確認）。
    """
    url = "https://jp.mercari.com/search?" + urllib.parse.urlencode(
        {"keyword": query, "status": "on_sale", "sort": "price", "order": "asc"}
    )
    if ambassador_suffix:
        url += "&" + ambassador_suffix.lstrip("&?")
    return {
        "mall": "mercari",
        "type": "deeplink",
        "title": f"メルカリで「{query}」の出品を見る",
        "url": url,
        "source": "deeplink",
    }


# ================================================================ 系統4: 個人ショップ（CSV入稿）
# 対応ヘッダ（左が正規名 / 右が受理する別名。BASE・STORESのエクスポート列名を吸収）
CSV_ALIASES = {
    "title": ["title", "商品名", "name"],
    "price": ["price", "価格", "販売価格"],
    "shipping": ["shipping", "送料"],
    "url": ["url", "商品URL", "公開URL"],
    "image": ["image", "画像URL", "画像1"],
    "seller": ["seller", "ショップ名", "店舗名"],
    "condition": ["condition", "状態", "コンディション"],
    "item_code": ["item_code", "品番", "型番"],
    "is_ad": ["is_ad", "広告枠"],
}


def _pick(row: dict, key: str) -> str:
    for alias in CSV_ALIASES[key]:
        if alias in row and str(row[alias]).strip():
            return str(row[alias]).strip()
    return ""


def load_shop_csv(path: str, item_code_filter: str | None = None) -> list[dict]:
    """個人ショップから入稿されたCSVを読む。1ショップ1ファイル想定。

    is_ad 列が truthy（1/true/yes/○）の行は広告枠として扱う。
    item_code_filter を渡すと該当品番の行だけに絞る。
    """
    out = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            code = _pick(row, "item_code")
            if item_code_filter and item_code_filter not in code:
                continue
            price = _pick(row, "price")
            ship = _pick(row, "shipping")
            ad = _pick(row, "is_ad").lower() in ("1", "true", "yes", "○", "y")
            out.append(
                {
                    "mall": "shop",
                    "title": _pick(row, "title"),
                    "price": int(float(price)) if price else 0,
                    "shipping": int(float(ship)) if ship else None,
                    "url": _pick(row, "url") or "#",
                    "image": _pick(row, "image"),
                    "seller": _pick(row, "seller"),
                    "seller_rating": None,
                    "condition": _pick(row, "condition"),
                    "is_ad": ad,
                    "source": f"csv:{os.path.basename(path)}",
                }
            )
    return out


# ================================================================ 統合
def collect(config: dict, query: str, item_code: str | None = None) -> tuple[list[dict], list[dict], list[str]]:
    """設定に応じて全系統から集約する。

    Returns:
        listings : カード表示する出品（Yahoo/VC/ショップCSV）
        deeplinks: カード化できないモールへの導線（メルカリ等）
        notes    : どの系統が動いた/スキップされたかのログ
    """
    listings: list[dict] = []
    deeplinks: list[dict] = []
    notes: list[str] = []

    appid = config.get("yahoo_appid") or os.environ.get("YAHOO_APPID")
    if appid:
        try:
            got = fetch_yahoo(appid, query, affiliate_id=config.get("vc_affiliate_id"))
            listings += got
            notes.append(f"Yahoo!ショッピングAPI: {len(got)}件")
        except Exception as e:
            notes.append(f"Yahoo!ショッピングAPI: 失敗 ({e})")
    else:
        notes.append("Yahoo!ショッピングAPI: スキップ（yahoo_appid 未設定）")

    vc_token = config.get("vc_token") or os.environ.get("VC_TOKEN")
    if vc_token:
        try:
            got = fetch_valuecommerce(vc_token, query, ec_code=config.get("vc_yahoo_auction_ec_code"))
            listings += got
            notes.append(f"ValueCommerce(ヤフオク): {len(got)}件")
        except Exception as e:
            notes.append(f"ValueCommerce(ヤフオク): 失敗 ({e})")
    else:
        notes.append("ValueCommerce(ヤフオク): スキップ（vc_token 未設定）")

    deeplinks.append(mercari_deeplink(query, config.get("mercari_ambassador_suffix", "")))
    notes.append("メルカリ: ディープリンク生成（公開APIなし）")

    shop_dir = config.get("shop_csv_dir", "shops")
    if os.path.isdir(shop_dir):
        n = 0
        for name in sorted(os.listdir(shop_dir)):
            if name.endswith(".csv"):
                rows = load_shop_csv(os.path.join(shop_dir, name), item_code)
                listings += rows
                n += len(rows)
        notes.append(f"ショップCSV: {n}件（{shop_dir}/）")
    else:
        notes.append(f"ショップCSV: スキップ（{shop_dir}/ なし）")

    return listings, deeplinks, notes
