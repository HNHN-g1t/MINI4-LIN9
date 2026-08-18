# -*- coding: utf-8 -*-
"""タミヤ公式サイトから商品一覧を取得し、tamiya_catalog.json（品番マスタ）を生成する。

取得対象（公式のジャンル区分）:
    グレードアップパーツ … genre 303010
    キット             … genre 3010  （シリーズ別の子カテゴリあり）
    AOパーツ           … genre 303030
    クラフトツール       … genre 5020  （工具種別の子カテゴリあり）

子カテゴリを持つジャンルは、親ページで全件を押さえたうえで子ページも巡回し、
各商品に公式のシリーズ名・工具種別を割り当てる。

使い方:
    py fetch_tamiya_catalog.py                  # 全ジャンル取得
    py fetch_tamiya_catalog.py --genre kit      # キットだけ
    py fetch_tamiya_catalog.py --pages 1        # 各ジャンル1ページだけ（動作確認用）

生成物: tamiya_catalog.json
"""
import argparse
import json
import re
import sys
import time
import urllib.request

BASE = "https://www.tamiya.com/japan/products/list.html"
LIST_URL = BASE + "?field_sort=d&cmdarticlesearch=1&genre_item={code}&absolutepage={page}"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) partspost-catalog-builder"
PER_PAGE = 20
SLEEP = 1.0  # 公式サイトへの負荷配慮

# key, 表示ラベル, ジャンルコード
GENRES = [
    ("parts", "グレードアップパーツ", "303010"),
    ("kit", "キット", "3010"),
    ("ao", "AOパーツ", "303030"),
    ("tool", "クラフトツール", "5020"),
]

CARD_RE = re.compile(
    r'<a\s+href="(?P<url>https://www\.tamiya\.com/japan/products/\d+/index\.html)"'
    r'\s+data-article="(?P<code>\d+)">.*?'
    r'<img[^>]+src="(?P<img>[^"]+)".*?'
    r'<h3[^>]*><span>ITEM\s*(?P<item>\d+)\s*</span>(?P<name>.*?)</h3>.*?'
    r'<p>(?P<price>[\d,]+)円',
    re.S)
TOTAL_RE = re.compile(r"全(\d+)件")
GENRE_LINK_RE = re.compile(r'genre_item=(\d+)"[^>]*>([^<]{2,40})<')


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as res:
        raw = res.read()
    for enc in ("cp932", "utf-8"):  # タミヤ公式はShift_JIS配信
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "ignore")


def parse_page(html: str) -> list[dict]:
    items = []
    for m in CARD_RE.finditer(html):
        img = m.group("img").strip()
        if img.startswith("//"):
            img = "https:" + img
        items.append({
            "item_code": m.group("code"),
            "name": re.sub(r"<[^>]+>", "", m.group("name")).strip(),
            "price": int(m.group("price").replace(",", "")),
            "image": img,
            "url": m.group("url"),
        })
    return items


def crawl(code: str, max_pages: int = 0, label: str = "") -> list[dict]:
    """1ジャンルを全ページ巡回する。"""
    first = fetch(LIST_URL.format(code=code, page=1))
    total_m = TOTAL_RE.search(first)
    total = int(total_m.group(1)) if total_m else 0
    last = max(1, -(-total // PER_PAGE)) if total else 1
    if max_pages:
        last = min(last, max_pages)

    items = parse_page(first)
    for page in range(2, last + 1):
        time.sleep(SLEEP)
        items.extend(parse_page(fetch(LIST_URL.format(code=code, page=page))))
    print(f"    [{code}] {label or ''} 全{total}件 → 取得{len(items)}件")
    return items


def discover_children(parent: str, html: str) -> list[tuple[str, str]]:
    """ナビゲーションから直下の子ジャンル（コード, ラベル）を拾う。"""
    found = {}
    for code, name in GENRE_LINK_RE.findall(html):
        if code.startswith(parent) and len(code) > len(parent):
            found.setdefault(code, name.strip())
    return sorted(found.items())


def collect_genre(key: str, label: str, code: str, max_pages: int) -> list[dict]:
    print(f"\n■ {label}（genre {code}）")
    first = fetch(LIST_URL.format(code=code, page=1))
    children = discover_children(code, first)

    # 親ジャンルの全件（これが掲載対象の母集合）
    items = crawl(code, max_pages, label)
    by_code = {it["item_code"]: {**it, "genre": label, "genre_key": key,
                                 "official_category": ""} for it in items}

    # 子カテゴリを巡回して公式の細分類を割り当てる
    if children and not max_pages:
        print(f"    子カテゴリ {len(children)}件 を巡回します")
        for child_code, child_label in children:
            time.sleep(SLEEP)
            try:
                for it in crawl(child_code, 0, child_label):
                    if it["item_code"] in by_code:
                        by_code[it["item_code"]]["official_category"] = child_label
                    else:  # 親に出ない商品も拾っておく
                        by_code[it["item_code"]] = {**it, "genre": label, "genre_key": key,
                                                    "official_category": child_label}
            except Exception as e:
                print(f"    [{child_code}] {child_label} … 失敗 ({e})")

    out = list(by_code.values())
    for it in out:
        c = it["item_code"]
        # GP番号はグレードアップパーツ（15xxx）だけに付く
        it["gp_no"] = f"GP.{int(c) - 15000}" if key == "parts" and c.startswith("15") and len(c) == 5 else ""
    print(f"  → {label}: {len(out)}件")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=0, help="各ジャンルの取得ページ上限（0=全件）")
    ap.add_argument("--genre", default="", help="キー指定で1ジャンルだけ取得（parts/kit/ao/tool）")
    ap.add_argument("--out", default="tamiya_catalog.json")
    args = ap.parse_args()

    targets = [g for g in GENRES if not args.genre or g[0] == args.genre]
    if not targets:
        print(f"エラー: 不明なジャンル {args.genre}（parts/kit/ao/tool）", file=sys.stderr)
        return 1

    all_items: list[dict] = []
    for key, label, code in targets:
        all_items.extend(collect_genre(key, label, code, args.pages))

    # 品番重複はジャンル優先順（GENRESの並び）で先勝ち
    seen, uniq = set(), []
    for it in all_items:
        if it["item_code"] not in seen:
            seen.add(it["item_code"])
            uniq.append(it)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(uniq, f, ensure_ascii=False, indent=1)

    print(f"\n保存: {args.out} ／ 合計 {len(uniq)}件")
    for _, label, _ in targets:
        print(f"  {label}: {sum(1 for i in uniq if i['genre'] == label)}件")
    return 0


if __name__ == "__main__":
    sys.exit(main())
