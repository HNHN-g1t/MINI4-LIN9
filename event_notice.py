# -*- coding: utf-8 -*-
"""起動用バッチから呼ばれて、日本語の案内を出すだけの小さな道具。

バッチファイル（.bat）に日本語を書くと文字化けするため、
画面に出す日本語はすべてこちら側に置く。

  py event_notice.py start   … 開始の案内
  py event_notice.py abort   … 中止したときの案内
  py event_notice.py done    … 終わったときの案内
"""

import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

MESSAGES = {
    "start": [
        "ミニ四駆レース開催情報の更新を始めます。",
        "",
        "  1. タミヤ公式から開催情報を取り込み、下書きを作ります。",
        "  2. 公開中のカレンダーとの差分を表示します。",
        "  3. 内容を確認して y と答えたときだけ、カレンダーを更新します。",
        "",
        "※ 途中でやめたいときは、そのままウィンドウを閉じてください。",
        "",
    ],
    "abort": [
        "",
        "処理を中止しました。上に表示された理由を確認してください。",
        "レースカレンダー（race.html）は書き換えていません。",
        "",
    ],
    "done": [
        "",
        "処理が終わりました。",
        "",
    ],
}


def main() -> int:
    key = sys.argv[1] if len(sys.argv) > 1 else "start"
    for line in MESSAGES.get(key, MESSAGES["start"]):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
