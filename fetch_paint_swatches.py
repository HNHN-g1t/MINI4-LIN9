# -*- coding: utf-8 -*-
"""タミヤ公式の商品画像から、スプレーの実際の色を抽出して paint_swatches.json に保存する。

スプレーの商品画像は缶のシルエットを塗り分けた「色見本」そのものなので、
シルエット内側を数点サンプリングして中央値を取れば実際の色が得られる。
色名からの推定と違って、公式サイトの色をそのまま使える。

    py fetch_paint_swatches.py            # 未取得ぶんだけ取得
    py fetch_paint_swatches.py --all      # 全件取り直し

生成物: paint_swatches.json  {"86003": "#1e99c3", ...}
"""
import argparse
import io
import json
import os
import sys
import time
import urllib.request

from PIL import Image

OUT = "paint_swatches.json"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) mini4lin9-swatch-builder"}
SLEEP = 0.6  # 公式サイトへの負荷配慮
# 缶シルエットの内側（ラベル文字を避けた位置）
POINTS = [(0.28, 0.32), (0.22, 0.55), (0.38, 0.28), (0.30, 0.62), (0.45, 0.45)]


def swatch_of(url: str) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as res:
        raw = res.read()
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    w, h = im.size
    px = [im.getpixel((int(w * x), int(h * y))) for x, y in POINTS]
    med = tuple(sorted(c[i] for c in px)[len(px) // 2] for i in range(3))
    return "#%02x%02x%02x" % med


def main() -> int:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="既存ぶんも取り直す")
    args = ap.parse_args()

    items = [i for i in json.load(io.open("tamiya_catalog.json", encoding="utf-8"))
             if i.get("genre_key") == "paint"]
    known = {}
    if os.path.exists(OUT) and not args.all:
        known = json.load(io.open(OUT, encoding="utf-8"))

    todo = [i for i in items if i["item_code"] not in known]
    print(f"塗装 {len(items)}件 ／ 取得対象 {len(todo)}件")

    ok = ng = 0
    for n, it in enumerate(todo, 1):
        try:
            known[it["item_code"]] = swatch_of(it["image"])
            ok += 1
            if n % 20 == 0 or n == len(todo):
                print(f"  {n}/{len(todo)} 件")
        except Exception as e:
            ng += 1
            print(f"  [{it['item_code']}] {it['name'][:20]} … 失敗 ({e})", file=sys.stderr)
        time.sleep(SLEEP)

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(dict(sorted(known.items())), f, ensure_ascii=False, indent=1)
    print(f"保存: {OUT} ／ 合計 {len(known)}色（今回 成功{ok} 失敗{ng}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
