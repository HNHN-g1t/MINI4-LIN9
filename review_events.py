# -*- coding: utf-8 -*-
"""下書き（events_draft.json）と公開中の race.html を見比べ、人が確かめて反映する。

自動で公開はしない。差分を見せて「はい」と答えたときだけ書き換える。
書き換える前に race.html.bak を必ず残す。

  py review_events.py            … 差分を見て、確認のうえ反映
  py review_events.py --dry-run  … 差分を見るだけ（書き換えない）
  py review_events.py --yes      … 確認を省いて反映（自動実行では使わないこと）
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import shutil
import sys
from datetime import date

import event_common as ec

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# race.html の中の書き換え対象。中身（[ ... ]）だけを入れ替える。
EVENTS_RE = re.compile(r"(const\s+EVENTS\s*=\s*)\[.*?\](\s*;)", re.S)
# フッターの最終確認日
LASTCHECKED_RE = re.compile(r'(<p\s+id="lastChecked"[^>]*>)(.*?)(</p>)', re.S)

# EVENTS の中の「キー: '値'」を1つずつ拾う。値の中に , や } や
# エスケープした ' が入っていても壊れないよう、文字列として読む。
_KV_RE = re.compile(r"([A-Za-z_]\w*)\s*:\s*'((?:[^'\\]|\\.)*)'")


def load_draft() -> dict:
    """下書きを読む。無い・空のときは異常終了させる。"""
    if not os.path.exists(ec.DRAFT_JSON):
        raise SystemExit(
            f"エラー: {ec.DRAFT_JSON} がありません。\n"
            "  先に py fetch_events.py を実行してください。")
    try:
        with open(ec.DRAFT_JSON, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        raise SystemExit(f"エラー: {ec.DRAFT_JSON} を読めません（{e}）。")
    events = data.get("events")
    if not isinstance(events, list) or not events:
        raise SystemExit(
            f"エラー: {ec.DRAFT_JSON} に開催情報が入っていません。\n"
            "  取得に失敗した下書きの可能性があります。race.html は書き換えません。")
    return data


def read_race_html() -> str:
    if not os.path.exists(ec.RACE_HTML):
        raise SystemExit(f"エラー: {ec.RACE_HTML} がありません。")
    with open(ec.RACE_HTML, encoding="utf-8") as f:
        return f.read()


def _unescape(text: str) -> str:
    """JavaScript の文字列エスケープを元に戻す（\\' を ' に戻すなど）。"""
    return re.sub(r"\\(.)", lambda m: m.group(1), text)


def current_events(html_text: str) -> list[dict]:
    """race.html の中の EVENTS を読み出す。

    JSON として読もうとすると、会場名に含まれる記号で崩れることがある。
    ここでは「キー: '値'」の並びとして素直に読み、date が出るたびに
    1件として区切る（date は必ず先頭に書く決まりにしてある）。
    """
    m = EVENTS_RE.search(html_text)
    if not m:
        raise SystemExit(
            f"エラー: {ec.RACE_HTML} の中に const EVENTS = [...] が見つかりません。\n"
            "  ファイルの作りが変わっていないか確認してください。")
    body = html_text[m.end(1):m.start(2)]

    events: list[dict] = []
    cur: dict = {}
    for kv in _KV_RE.finditer(body):
        key, val = kv.group(1), _unescape(kv.group(2))
        if key == "date" and cur:
            events.append(cur)
            cur = {}
        cur[key] = val
    if cur:
        events.append(cur)

    # 中身が入っているのに1件も読めないのは、形が変わったということ。
    # 空の配列（[ と ] の間が改行だけ）は「0件」であって異常ではない。
    if not events and re.sub(r"\s+", "", body) not in ("", "[]"):
        raise SystemExit(
            f"エラー: {ec.RACE_HTML} の EVENTS を読み取れませんでした。\n"
            "  手で編集した際に形が崩れていないか確認してください。")
    return events


def key_of(e: dict) -> str:
    """同じイベントかどうかを見分ける手がかり。URLがいちばん確か。"""
    return e.get("url") or (e.get("date", "") + "|" + e.get("shop", ""))


def diff(old: list[dict], new: list[dict]) -> tuple[list, list, list]:
    """追加・変更・削除に分ける。"""
    om = {key_of(e): e for e in old}
    nm = {key_of(e): e for e in new}
    added = [nm[k] for k in nm if k not in om]
    removed = [om[k] for k in om if k not in nm]
    changed = []
    for k in nm:
        if k not in om:
            continue
        a, b = om[k], nm[k]
        fields = [f for f in ("date", "pref", "label", "shop")
                  if (a.get(f) or "") != (b.get(f) or "")]
        if fields:
            changed.append((a, b, fields))
    added.sort(key=lambda e: e.get("date", ""))
    removed.sort(key=lambda e: e.get("date", ""))
    changed.sort(key=lambda t: t[1].get("date", ""))
    return added, changed, removed


FIELD_NAMES = {"date": "日付", "pref": "都道府県キー",
               "label": "県名", "shop": "会場名"}


def show(added, changed, removed, unknown) -> None:
    """差分を人が読める形で並べる。"""
    if added:
        print(f"＋追加 {len(added)}件")
        for e in added:
            print(f"    {e['date']} [{e.get('label') or '?'}] {e.get('shop', '')}")
    if changed:
        print(f"～変更 {len(changed)}件")
        for a, b, fields in changed:
            print(f"    {b['date']} {b.get('shop', '')}")
            for f in fields:
                print(f"      : {FIELD_NAMES.get(f, f)} "
                      f"{a.get(f) or '（空）'} → {b.get(f) or '（空）'}")
    if removed:
        print(f"－削除 {len(removed)}件")
        for e in removed:
            print(f"    {e['date']} [{e.get('label') or '?'}] {e.get('shop', '')}")
    if unknown:
        print(f"⚠ 都道府県を判定できませんでした {len(unknown)}件")
        for u in unknown:
            hint = u.get("pref_raw") or u.get("place") or "住所表記なし"
            print(f"    {u['date']} {u.get('shop', '')}（{hint}）")


def js_str(value: str) -> str:
    """JavaScript の文字列として安全な形にする。"""
    s = str(value)
    s = s.replace("\\", "\\\\").replace("'", "\\'")
    s = s.replace("\n", " ").replace("\r", " ")
    return "'" + s + "'"


def render_events(events: list[dict]) -> str:
    """EVENTS の中身を、1件1行の読みやすい形で組み立てる。

    date を必ず先頭に置くこと。読み戻すときの区切りに使っている。
    """
    lines = []
    for e in events:
        lines.append(
            "  { date:%s, pref:%s, label:%s, shop:%s, url:%s }," % (
                js_str(e.get("date", "")), js_str(e.get("pref", "")),
                js_str(e.get("label", "")), js_str(e.get("shop", "")),
                js_str(e.get("url", ""))))
    return "[\n" + "\n".join(lines) + "\n]"


def apply_to_html(html_text: str, events: list[dict], day: str) -> str:
    """EVENTS の中身と、フッターの最終確認日を差し替える。"""
    block = render_events(events)
    # 差し込む文字列に \\1 のような後方参照が混ざっても壊れないよう、置換は関数で行う
    new_html, n = EVENTS_RE.subn(
        lambda m: m.group(1) + block + m.group(2), html_text, count=1)
    if n != 1:
        raise SystemExit("エラー: EVENTS の差し替えに失敗しました。書き換えていません。")

    note = (f"開催情報 最終確認日: {day} ／ "
            "最新情報は必ず主催ショップおよびタミヤ公式サイトでご確認ください")
    new_html, n = LASTCHECKED_RE.subn(
        lambda m: m.group(1) + note + m.group(3), new_html, count=1)
    if n != 1:
        print('警告: フッターの id="lastChecked" が見つからず、'
              "最終確認日は更新できませんでした。")
    return new_html


def main() -> int:
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--dry-run", action="store_true", help="差分を見るだけ")
    ap.add_argument("--yes", action="store_true", help="確認を省いて反映する")
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    os.chdir(here)

    data = load_draft()
    new_events = data["events"]
    unknown = data.get("unknownPref") or []

    html_text = read_race_html()
    old_events = current_events(html_text)

    print(f"下書き   : {ec.DRAFT_JSON}"
          f"（{len(new_events)}件・取得日 {data.get('generatedAt', '?')}）")
    print(f"公開中   : {ec.RACE_HTML}（{len(old_events)}件）")
    print()

    added, changed, removed = diff(old_events, new_events)
    if not (added or changed or removed):
        print("変更はありません。")
        if unknown:
            print()
            show([], [], [], unknown)
        return 0

    show(added, changed, removed, unknown)
    print()

    if args.dry_run:
        print("--dry-run のため、race.html は書き換えていません。")
        return 0

    if not args.yes:
        try:
            ans = input(f"この内容で {ec.RACE_HTML} を更新しますか？ (y/N): ")
        except EOFError:
            ans = ""
        if ans.strip().lower() != "y":
            print("中止しました。race.html は書き換えていません。")
            return 0

    # 書き換える前に必ず控えを取る
    backup = ec.RACE_HTML + ".bak"
    shutil.copy2(ec.RACE_HTML, backup)

    today = date.today().isoformat()
    updated = apply_to_html(html_text, new_events, today)
    with open(ec.RACE_HTML, "w", encoding="utf-8") as f:
        f.write(updated)

    print(f"更新しました: {ec.RACE_HTML}（{len(new_events)}件）")
    print(f"  控え      : {backup}")
    print(f"  最終確認日: {today}")
    if unknown:
        print(f"  ※ 都道府県が不明な {len(unknown)}件は pref='unknown' のまま入っています。"
              "必要なら手で直してください。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
