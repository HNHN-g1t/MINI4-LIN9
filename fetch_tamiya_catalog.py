# -*- coding: utf-8 -*-
"""タミヤ公式サイトからミニ四駆グレードアップパーツ一覧を取得し、
tamiya_catalog.json（品番マスタ）を生成する。

使い方:
    py fetch_tamiya_catalog.py                # 全ページ取得
    py fetch_tamiya_catalog.py --pages 2      # 先頭2ページだけ（動作確認用）

生成物: tamiya_catalog.json
    [{"item_code": "15551", "gp_no": "GP.551", "name": "...",
      "price": 814, "image": "https://...", "url": "https://...",
      "category": "..."}, ...]
"""
import argparse
import json
import re
import sys
import time
import urllib.request

LIST_URL = ("https://www.tamiya.com/japan/products/list.html"
            "?field_sort=d&cmdarticlesearch=1&genre_item=303010&absolutepage={page}")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) partspost-catalog-builder"

# 商品カード: <li><a href="..../products/15551/index.html" data-article="15551">
#   <img src="//cdn.../15551_s.jpg"> ... <h3><span>ITEM 15551</span>商品名</h3> <p>814円...
CARD_RE = re.compile(
    r'<a\s+href="(?P<url>https://www\.tamiya\.com/japan/products/\d+/index\.html)"'
    r'\s+data-article="(?P<code>\d+)">.*?'
    r'<img[^>]+src="(?P<img>[^"]+)".*?'
    r'<h3[^>]*><span>ITEM\s*(?P<item>\d+)\s*</span>(?P<name>.*?)</h3>.*?'
    r'<p>(?P<price>[\d,]+)円',
    re.S)

TOTAL_RE = re.compile(r'全(\d+)件')


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
        name = re.sub(r"<[^>]+>", "", m.group("name")).strip()
        code = m.group("code")
        # 15xxx → GP.xxx（1万5千番台のグレードアップパーツ命名規則）
        gp = f"GP.{int(code) - 15000}" if code.startswith("15") and len(code) == 5 else ""
        items.append({
            "item_code": code,
            "gp_no": gp,
            "name": name,
            "price": int(m.group("price").replace(",", "")),
            "image": img,
            "url": m.group("url"),
        })
    return items


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=0, help="取得ページ数上限（0=全ページ）")
    ap.add_argument("--out", default="tamiya_catalog.json")
    args = ap.parse_args()

    first = fetch(LIST_URL.format(page=1))
    total_m = TOTAL_RE.search(first)
    total = int(total_m.group(1)) if total_m else 0
    per_page = 20
    last_page = max(1, -(-total // per_page)) if total else 1
    if args.pages:
        last_page = min(last_page, args.pages)

    print(f"全{total}件 / {last_page}ページを取得します")
    all_items = parse_page(first)
    print(f"  page 1: {len(all_items)}件")

    for page in range(2, last_page + 1):
        time.sleep(1.0)  # 公式サイトへの負荷配慮
        html = fetch(LIST_URL.format(page=page))
        got = parse_page(html)
        all_items.extend(got)
        print(f"  page {page}: {len(got)}件")

    # 重複除去（品番キー）
    seen, uniq = set(), []
    for it in all_items:
        if it["item_code"] not in seen:
            seen.add(it["item_code"])
            uniq.append(it)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(uniq, f, ensure_ascii=False, indent=1)
    print(f"保存: {args.out} ／ {len(uniq)}件")


if __name__ == "__main__":
    sys.exit(main())
