# -*- coding: utf-8 -*-
"""タミヤ公式の「最新カタログ製品一覧」から、ミニ四駆の新製品だけを取り出す。

公式ページは月ごとの一覧になっている。ジャンルのタグ（category_NN）が
「ミニ四駆」のものだけを拾い、new_items.json に書き出す。

    py fetch_new_items.py          # 今月ぶんを取り直す
    py fetch_new_items.py --months 3   # 前の月もさかのぼる

取得の作法は fetch_events.py と同じ（robots確認・間隔をあける・
取得したHTMLはcacheに残す）。公式ページは Shift_JIS なので cp932 で読む。
"""
import io
import json
import os
import re
import sys
import time

import event_common as EC

DAY = time.strftime("%Y%m%d")   # キャッシュを日ごとに分けるための目印

OUT = "new_items.json"
BASE = "https://www.tamiya.com/japan/newitems/list.html"
MONTH = "https://www.tamiya.com/japan/newitems_month/list.html"
QS = "?current=%s&genre_item=category,undefined&sortkey=sort_rd"
WANT = "ミニ四駆"          # このジャンルタグが付いたものだけ採る

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# 1商品ぶんの塊。<li> の中に、リンク・画像・ジャンル・品番・名前・発売日・価格が並ぶ。
_ITEM_RE = re.compile(
    r'<li>\s*<a href="(?P<url>https://www\.tamiya\.com/japan/products/(?P<code>\d+)[^"]*)"'
    r'.*?<img[^>]*src="(?P<img>[^"]+)".*?'
    r'<span class="category_\d+">(?P<genre>[^<]*)</span>.*?'
    r'<h3>\s*<span>ITEM\s*(?P<code2>[^<\s]+)\s*</span>(?P<name>.*?)<span>(?P<rel>[^<]*)</span>'
    r'.*?</h3>\s*<p>(?P<price>[^<]*)<',
    re.S)
# 「前月を見る」のリンクから、さかのぼる先の年月を取る
_PREV_RE = re.compile(r'class="prev_"\s+href="[^"]*current=(\d{6})')


def clean(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s or "")
    return re.sub(r"\s+", " ", s).strip()


def parse(html_text: str) -> tuple:
    """(商品のリスト, 前月の年月) を返す。"""
    rows = []
    for m in _ITEM_RE.finditer(html_text):
        genre = clean(m.group("genre"))
        if genre != WANT:
            continue
        img = clean(m.group("img"))
        if img.startswith("//"):
            img = "https:" + img
        rows.append({
            "item_code": clean(m.group("code")),
            "name": clean(m.group("name")),
            "release": clean(m.group("rel")).replace("発売日：", ""),
            "price": clean(m.group("price")),
            "image": img,
            "url": clean(m.group("url")),
            "genre": genre,
        })
    prev = _PREV_RE.search(html_text)
    return (rows, prev.group(1) if prev else "")


def fetch_month(current: str) -> tuple:
    base = MONTH if current else BASE
    url = base + (QS % (current or "undefined"))
    if current:
        url += "&catalog_open_month=" + current
    return (url, EC.fetch_text(url, DAY))


def main(argv: list) -> int:
    months = 1
    if "--months" in argv:
        months = max(1, int(argv[argv.index("--months") + 1]))

    why = EC.robots_blocks(BASE, DAY)
    if why:
        print("エラー: %s" % why, file=sys.stderr)
        return 1

    seen, rows, current = set(), [], ""
    for i in range(months):
        try:
            url, text = fetch_month(current)
        except EC.FetchError as e:
            print("取得に失敗しました: %s" % e, file=sys.stderr)
            return 1
        got, prev = parse(text)
        add = [r for r in got if r["item_code"] not in seen]
        for r in add:
            seen.add(r["item_code"])
        rows += add
        print("  %s … ミニ四駆 %d件" % (current or "今月", len(add)))
        if not prev:
            break
        current = prev
        if i + 1 < months:
            time.sleep(EC.REQUEST_INTERVAL)

    if not rows:
        print("エラー: 1件も取れませんでした。ページの作りが変わった可能性があります。",
              file=sys.stderr)
        return 1

    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"fetchedAt": time.strftime("%Y-%m-%d"), "items": rows},
                  f, ensure_ascii=False, indent=1)
    print("\nミニ四駆の新製品 %d件 → %s" % (len(rows), OUT))
    for r in rows[:8]:
        print("  ITEM %-7s %-42s %s" % (r["item_code"], r["name"][:42], r["release"]))
    if len(rows) > 8:
        print("  ...ほか %d件" % (len(rows) - 8))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
