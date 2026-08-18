#!/usr/bin/env python3
"""カタログ一括生成ウィザード（ダブルクリック起動用）"""

import os
import subprocess
import sys
import webbrowser

LINE = "=" * 56


def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    os.chdir(here)

    demo = "--demo" in sys.argv

    print()
    print(LINE)
    if demo:
        print("  パーツポスト  カタログ一括生成（デモ・ID不要）")
    else:
        print("  パーツポスト  ステップ3  カタログ一括生成")
    print(LINE)
    print()

    args = [sys.executable, "build_catalog.py"]

    if demo:
        args.append("--demo")
    else:
        if not os.path.exists("config.json"):
            print("  [!] 設定がまだ済んでいません。")
            print("      先に 1_Setup.bat を実行してください。")
            return 1

        print("  catalog.json に登録された全品番のページを作ります。")
        print()
        print("  Yahoo!のAPIは「1秒に1回まで」の制限があるため、")
        print("  1品番ごとに約1.2秒の待ち時間を入れて実行します。")
        print("  38品番すべてで約1分かかります。")
        print()
        print("  まず少数で試す場合は、件数を入力してください。")
        print("  （そのままEnterを押すと全品番を生成します）")
        print()
        try:
            n = input("  生成する件数 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  中断しました。")
            return 1
        if n.isdigit() and int(n) > 0:
            args += ["--limit", n]

    print()
    result = subprocess.run(args)
    if result.returncode != 0:
        print()
        print("  [!] 生成に失敗しました。上のメッセージを確認してください。")
        return result.returncode

    index = os.path.join(here, "site", "index.html")
    if os.path.exists(index):
        print()
        print("  ブラウザで開きます...")
        webbrowser.open("file:///" + index.replace("\\", "/"))
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
