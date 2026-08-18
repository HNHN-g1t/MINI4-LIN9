#!/usr/bin/env python3
"""ページ生成ウィザード（検索語を聞いて生成 → ブラウザで開く）"""

import os
import subprocess
import sys
import webbrowser

LINE = "=" * 56
DEFAULT_QUERY = "ミニ四駆 大径ローハイトタイヤ"


def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    os.chdir(here)

    demo = "--demo" in sys.argv

    print()
    print(LINE)
    if demo:
        print("  パーツポスト  デモ表示（Client ID不要）")
    else:
        print("  パーツポスト  ステップ2  ページを作る")
    print(LINE)
    print()

    args = [sys.executable, "build_partspost.py", "--out", "partspost.html"]

    if demo:
        args.append("--demo")
    else:
        if not os.path.exists("config.json"):
            print("  [!] 設定がまだ済んでいません。")
            print("      先に 1_Setup.bat を実行してください。")
            return 1

        print("  検索したい言葉を入力してEnterキーを押してください。")
        print(f"  （そのままEnterを押すと「{DEFAULT_QUERY}」で検索します）")
        print()
        try:
            keyword = input("  検索語 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  中断しました。")
            return 1
        if not keyword:
            keyword = DEFAULT_QUERY
        args += ["--query", keyword, "--item-code", "15435"]
        print()
        print(f"  「{keyword}」で検索しています...")

    print()
    result = subprocess.run(args)
    if result.returncode != 0:
        print()
        print("  [!] 生成に失敗しました。上のメッセージを確認してください。")
        return result.returncode

    out = os.path.join(here, "partspost.html")
    print()
    print("  ブラウザで開きます...")
    webbrowser.open("file:///" + out.replace("\\", "/"))
    return 0


if __name__ == "__main__":
    code = main()
    print()
    print(LINE)
    try:
        input("  Enterキーで閉じます...")
    except (EOFError, KeyboardInterrupt):
        pass
    sys.exit(code)
