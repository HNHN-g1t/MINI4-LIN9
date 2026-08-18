#!/usr/bin/env python3
"""
Yahoo! Client ID 接続テスト

発行したClient IDが実際に使えるかだけを確認する。
本体を回す前にこれで疎通を取ると、問題の切り分けが楽になる。

使い方:
    python3 check_yahoo.py dj00aiZpPXh4eHh4...

    # または config.json / 環境変数 YAHOO_APPID から自動で読む
    python3 check_yahoo.py
"""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

ENDPOINT = "https://shopping.yahooapis.jp/ShoppingWebService/V3/itemSearch"


def load_appid(argv: list[str]) -> str | None:
    if len(argv) > 1 and argv[1].strip():
        return argv[1].strip()
    if os.environ.get("YAHOO_APPID"):
        return os.environ["YAHOO_APPID"].strip()
    if os.path.exists("config.json"):
        try:
            with open("config.json", encoding="utf-8") as f:
                v = (json.load(f).get("yahoo_appid") or "").strip()
            # 雛形のままの説明文が残っていたら未設定とみなす
            if v and not v.startswith("Yahoo!デベロッパー"):
                return v
        except Exception:
            pass
    return None


def main() -> int:
    appid = load_appid(sys.argv)
    if not appid:
        print("✗ Client IDが見つかりません。\n")
        print("  次のいずれかで渡してください:")
        print("    python3 check_yahoo.py あなたのClientID")
        print("    export YAHOO_APPID='あなたのClientID'")
        print("    config.json の yahoo_appid に記入")
        return 1

    print(f"Client ID: {appid[:12]}…（{len(appid)}文字）")
    print("テスト検索: 「ミニ四駆 大径ローハイトタイヤ」\n")

    params = urllib.parse.urlencode(
        {"appid": appid, "query": "ミニ四駆 大径ローハイトタイヤ", "results": 5, "sort": "+price"}
    )
    req = urllib.request.Request(f"{ENDPOINT}?{params}", headers={"User-Agent": "partspost/0.2"})

    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            data = json.load(res)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:300]
        print(f"✗ APIがエラーを返しました (HTTP {e.code})\n")
        if e.code in (400, 401, 403):
            print("  よくある原因:")
            print("   ・Client IDのコピーミス（前後の空白・改行が混入していないか）")
            print("   ・登録直後で反映待ち（数分おいて再実行）")
            print("   ・ショッピング系APIが利用対象に入っていない")
        elif e.code == 429:
            print("  リクエスト制限（1クエリ/秒）に抵触しています。少し待って再実行してください。")
        print(f"\n  レスポンス: {body}")
        return 1
    except Exception as e:
        print(f"✗ 接続できませんでした: {e}")
        print("  ネットワーク接続、またはプロキシ設定を確認してください。")
        return 1

    hits = data.get("hits", [])
    total = data.get("totalResultsAvailable", 0)

    if not hits:
        print("△ 通信は成功しましたが、該当商品が0件でした。")
        print("  Client IDは有効です。検索語を変えて試してください。")
        return 0

    print(f"✓ 成功！ 全{total:,}件ヒット（うち先頭5件を表示）\n")
    for i, h in enumerate(hits, 1):
        price = int(h.get("price") or 0)
        free = "送料無料" if (h.get("shipping") or {}).get("code") == 1 else "送料別"
        store = (h.get("seller") or {}).get("name", "")
        name = h.get("name", "")[:44]
        print(f"  {i}. ¥{price:>6,}  {free}  {name}")
        print(f"      {store}")

    print("\n" + "─" * 58)
    print("Client IDは正常に動作しています。次のコマンドで本体を生成できます:\n")
    print('  python3 build_partspost.py --query "ミニ四駆 大径ローハイトタイヤ" --item-code 15435')
    return 0


if __name__ == "__main__":
    sys.exit(main())
