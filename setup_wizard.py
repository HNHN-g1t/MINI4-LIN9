#!/usr/bin/env python3
"""かんたん設定ウィザード（Client IDの保存 → 接続テスト）

日本語の表示・入力はすべてPython側で行う。
Windowsのコンソール文字コードに依存しないため、文字化けしない。
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

TEMPLATE = {
    "yahoo_appid": "",
    "vc_affiliate_id": "",
    "vc_token": "",
    "vc_yahoo_auction_ec_code": "",
    "mercari_ambassador_suffix": "",
    "shop_csv_dir": "shops",
}

LINE = "=" * 56


def save_appid(appid: str) -> None:
    config = dict(TEMPLATE)
    if os.path.exists("config.json"):
        try:
            with open("config.json", encoding="utf-8") as f:
                saved = json.load(f)
            for k, v in saved.items():
                if k in config and isinstance(v, str):
                    config[k] = v
        except Exception:
            pass
    config["yahoo_appid"] = appid
    with open("config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def main() -> int:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    print()
    print(LINE)
    print("  パーツポスト  ステップ1  かんたん設定")
    print(LINE)
    print()
    print("  Yahoo!デベロッパーネットワークで発行した")
    print("  Client ID を貼り付けてEnterキーを押してください。")
    print()
    print("  ※ Ctrl+V が効かない場合は、マウスの右クリックで貼り付けできます")
    print()

    try:
        appid = input("  Client ID > ").strip().strip('"').strip("'")
    except (EOFError, KeyboardInterrupt):
        print("\n  中断しました。")
        return 1

    if not appid:
        print()
        print("  入力がありませんでした。もう一度実行してください。")
        return 1

    if len(appid) < 20:
        print()
        print(f"  [!] 入力されたIDが短すぎます（{len(appid)}文字）。")
        print("      貼り付けが途中で切れている可能性があります。")
        print("      このまま続けますが、失敗したら貼り直してください。")

    save_appid(appid)
    print()
    print(f"  設定を保存しました（config.json）")
    print(f"  yahoo_appid = {appid[:12]}…（{len(appid)}文字）")
    print()
    print(LINE)
    print("  接続テストを実行します")
    print(LINE)

    import check_yahoo

    sys.argv = ["check_yahoo.py", appid]
    return check_yahoo.main()


if __name__ == "__main__":
    code = main()
    print()
    print(LINE)
    try:
        input("  Enterキーで閉じます...")
    except (EOFError, KeyboardInterrupt):
        pass
    sys.exit(code)
