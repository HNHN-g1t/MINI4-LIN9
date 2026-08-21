# -*- coding: utf-8 -*-
"""タミヤ公式のイベント一覧から、ミニ四駆のレース開催情報を取り込む。

出来上がるのは events_draft.json という「下書き」だけで、
公開中の race.html には一切触れない。反映は review_events.py で
人が中身を確かめてから行う。

  py fetch_events.py              … キャッシュがあれば使う
  py fetch_events.py --refresh    … 取り直す
  py fetch_events.py --limit 2    … 先頭2ページだけ（動作確認用）

【このページの性質について】
JavaScript で描画されているように見えるが、実際は素のHTMLに全件入っている。
ただし文字コードが Shift_JIS なので、UTF-8 として読むと日本語が全部壊れ、
「中身が空だ」と誤診する。読み込みは必ず event_common.decode を通すこと。
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
from datetime import date

import event_common as ec

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ミニ四駆ジャンルの一覧。開催日が近い順。
LIST_PATH = "/japan/event/index.html"
LIST_QUERY = ("?cmdarticlesearch=1&field_sort=a"
              "&genre_item=event_mini4wd%2cevent_type%2cevent_pref%2cundefined"
              "&sortkey=sort_sa&absolutepage={page}")

# 一覧の中で、行が並んでいる場所の目印
_YEAR_RE = re.compile(r'class="caption_"[^>]*>\s*(\d{4})年')
# 日付見出しのクラス名は曜日で変わる（day / sun_ / sat_ …）ので、
# クラス名には頼らず「N月N日」の形そのものを目印にする。
_DAY_RE = re.compile(r'<th[^>]*>\s*(\d{1,2})月(\d{1,2})日')
# <a> は class などが href より前に付くことがあるため、属性の順を決め打ちしない。
_ITEM_RE = re.compile(
    r'<a[^>]*?href="(?P<url>https://www\.tamiya\.com/japan/event/[^"]+)"[^>]*>(?P<body>.*?)</a>',
    re.S)
_PREF_RE = re.compile(r'class="pref_".*?<span>(.*?)</span>', re.S)
# 行に付いているカテゴリの札。ミニ四駆で絞っても、スケールモデルや工作を
# 兼ねたイベント（プラモコンテスト等）が混ざるため、これを見て外す。
_GENRE_RE = re.compile(r'<span class="event_\w+_bg">([^<]*)</span>')
ONLY_GENRE = "ミニ四駆"
_TTL_RE = re.compile(r'class="ttl_"[^>]*>(.*?)</p>', re.S)
_TOTAL_RE = re.compile(r"全(\d+)件")
_LASTPAGE_RE = re.compile(r"absolutepage=(\d+)")

# 詳細ページの項目
_FIELD_RE = r'<span>{name}</span>\s*<p>(.*?)</p>'


def list_url(page: int) -> str:
    return ec.BASE + LIST_PATH + LIST_QUERY.format(page=page)


def parse_list(page_html: str) -> list[dict]:
    """一覧1ページ分から、日付・都道府県・イベント名・詳細URLを取り出す。"""
    # 本文だけに絞る。絞らないとヘッダのナビゲーションを拾ってしまう。
    start = page_html.find('class="notice_"')
    body = page_html[start:] if start >= 0 else page_html

    # 年見出し・日付見出し・各行の位置を、出てくる順に並べて読む
    marks: list[tuple[int, str, tuple]] = []
    for m in _YEAR_RE.finditer(body):
        marks.append((m.start(), "year", (int(m.group(1)),)))
    for m in _DAY_RE.finditer(body):
        marks.append((m.start(), "day", (int(m.group(1)), int(m.group(2)))))
    for m in _ITEM_RE.finditer(body):
        marks.append((m.start(), "item", (m.group("url"), m.group("body"))))
    marks.sort(key=lambda x: x[0])

    rows, year, md = [], None, None
    for _, kind, val in marks:
        if kind == "year":
            year = val[0]
        elif kind == "day":
            md = val
        elif kind == "item":
            if year is None or md is None:
                continue          # 日付の分からない行は拾わない
            url, frag = val
            pm = _PREF_RE.search(frag)
            tm = _TTL_RE.search(frag)
            rows.append({
                "date": "%04d-%02d-%02d" % (year, md[0], md[1]),
                "pref_raw": ec.text_of(pm.group(1)) if pm else "",
                "title": ec.text_of(tm.group(1)) if tm else "",
                "categories": [c.strip() for c in _GENRE_RE.findall(frag) if c.strip()],
                "url": url,
            })
    return rows


def parse_detail(detail_html: str) -> dict:
    """詳細ページから 場所・主催者名・開催日 を取り出す。"""
    out = {}
    for key, name in (("place", "場所"), ("host", "主催者名"), ("held", "開催日")):
        m = re.search(_FIELD_RE.format(name=name), detail_html, re.S)
        out[key] = ec.text_of(m.group(1)) if m else ""
    return out


# イベント名の末尾に「at 会場名」の形で会場が書かれていることが多い。
# 全角の＠や「 at 」など揺れがあるので、まとめて受ける。
# 全角の＠は前後に空白を置かない書き方が多いので、単独でも受ける。
# 半角の at / @ は語の一部を誤って拾わないよう、前後の空白を必須にする。
_AT_RE = re.compile(
    r"(?:(?:\s|　)(?:at|AT|At|@)(?:\s|　)+|　?＠(?:\s|　)*)(?P<venue>[^\s　][^\n]*)$")


def venue_from_title(title: str) -> str:
    """イベント名から「at 〜」の会場名を取り出す。無ければ空文字。"""
    m = _AT_RE.search((title or "").strip())
    if not m:
        return ""
    venue = m.group("venue").strip(" 　・,、")
    # 短すぎる／記号だけ、といった拾い損ねは会場名とみなさない
    return venue if len(venue) >= 2 else ""


def venue_of(detail: dict, fallback: str) -> str:
    """会場名にあたる文字列を選ぶ。

    「場所」は〒／住所／施設名 が改行で並んでいることが多いので、最後の行を採る。
    住所しか無い場合は主催者名、それも無ければ一覧のイベント名に落とす。
    仕様どおり、長くても切り詰めない（表示側で省略する）。
    """
    lines = [x for x in (detail.get("place") or "").split("\n") if x]
    lines = [x for x in lines if not x.startswith("〒")]
    if lines:
        last = lines[-1]
        # 最後の行がまだ住所（都道府県名＋市区町村や番地）なら施設名ではない
        looks_address = bool(re.search(r"[都道府県].*[市区町村郡]", last)) or \
            bool(re.search(r"\d+[-−ー丁目番地号]", last))
        if not looks_address:
            return last
    host = (detail.get("host") or "").strip()
    if host:
        return host
    # 詳細から取れないときは、イベント名の「at 〜」を会場名として使う。
    # それも無ければイベント名の全文をそのまま残す（勝手に切り詰めない）。
    return venue_from_title(fallback) or fallback


def main() -> int:
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--refresh", action="store_true",
                    help="キャッシュを使わずに取り直す")
    ap.add_argument("--limit", type=int, default=0,
                    help="読む一覧ページ数の上限（動作確認用）")
    ap.add_argument("--no-detail", action="store_true",
                    help="詳細ページを見ずに一覧だけで作る（動作確認用）")
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    os.chdir(here)
    today = date.today().isoformat()

    print("タミヤ公式イベント一覧から、ミニ四駆のレース情報を取り込みます。")
    print(f"  名乗り  : {ec.USER_AGENT}")
    print(f"  間隔    : {ec.REQUEST_INTERVAL:.0f}秒以上あけます")
    print(f"  保存先  : {ec.CACHE_DIR}/{today}/")
    print()

    # ---- robots.txt の確認 --------------------------------------------
    try:
        blocked = ec.robots_blocks(LIST_PATH, today, refresh=args.refresh)
    except ec.FetchError as e:
        print(f"エラー: {e}", file=sys.stderr)
        return 1
    if blocked:
        print(f"中止: {blocked}", file=sys.stderr)
        return 1
    print("robots.txt: 取得を禁止する指定はありませんでした。")

    # ---- 一覧を読む ----------------------------------------------------
    try:
        first = ec.fetch_text(list_url(1), today, refresh=args.refresh)
    except ec.FetchError as e:
        print(f"エラー: {e}", file=sys.stderr)
        return 1
    if first is None:
        print("エラー: 一覧ページが見つかりませんでした。", file=sys.stderr)
        return 1

    m = _TOTAL_RE.search(first)
    total = int(m.group(1)) if m else 0
    last_page = max([int(x) for x in _LASTPAGE_RE.findall(first)] or [1])
    if args.limit:
        last_page = min(last_page, args.limit)
    print(f"公式の掲載件数: {total}件 ／ 読むページ数: {last_page}")

    rows = parse_list(first)
    for page in range(2, last_page + 1):
        try:
            h = ec.fetch_text(list_url(page), today, refresh=args.refresh)
        except ec.FetchError as e:
            print(f"エラー: {e}", file=sys.stderr)
            return 1
        got = parse_list(h or "")
        print(f"  {page}/{last_page}ページ … {len(got)}件")
        rows += got

    # 同じイベントが複数ページに出た場合に備えて、URLで重複を落とす
    seen, uniq = set(), []
    for r in rows:
        if r["url"] in seen:
            continue
        seen.add(r["url"])
        uniq.append(r)
    rows = uniq

    # ---- カテゴリが「ミニ四駆」だけのものに絞る --------------------------
    # ジャンル指定で絞っても、他ジャンルを兼ねたイベント（プラモコンテスト等）が
    # 混ざってくる。外したものは黙って捨てず、必ず件数と中身を出す。
    dropped = [r for r in rows
               if r.get("categories") and set(r["categories"]) != {ONLY_GENRE}]
    if dropped:
        rows = [r for r in rows if r not in dropped]
        print(f"カテゴリが「{ONLY_GENRE}」だけではない {len(dropped)}件を除きました。")
        for d in dropped:
            print(f"    {d['date']} [{'／'.join(d['categories'])}] {d['title'][:36]}")

    # ---- 0件は「成功」にしない ------------------------------------------
    # ここが構造変更を見つけるいちばん大事な関所。
    if not rows:
        print(file=sys.stderr)
        print("エラー: 1件も取り出せませんでした。", file=sys.stderr)
        print("  公式ページの作りが変わった可能性が高いです。", file=sys.stderr)
        print(f"  取得したHTMLは {ec.cache_path(today, '')} に残してあります。", file=sys.stderr)
        print("  『全N件』の表記: " + (f"{total}件" if total else "見つかりませんでした"),
              file=sys.stderr)
        print("  下書きファイルは書き換えていません。", file=sys.stderr)
        return 1
    print(f"一覧から {len(rows)}件を取り出しました。")

    # ---- 詳細ページで会場名を押さえる -----------------------------------
    events, unknown = [], []
    if not args.no_detail:
        print(f"詳細ページを1件ずつ確認します（{len(rows)}件・"
              f"初回は約{int(len(rows) * ec.REQUEST_INTERVAL / 60) + 1}分）…")
    for i, r in enumerate(rows, 1):
        detail = {}
        if not args.no_detail:
            try:
                dh = ec.fetch_text(r["url"], today, refresh=args.refresh, allow_404=True)
            except ec.FetchError as e:
                # 1件の失敗で全部を捨てない。ただし黙らせない。
                print(f"  警告: {r['url']} を読めませんでした（{e}）")
                dh = None
            if dh:
                detail = parse_detail(dh)
            if i % 20 == 0:
                print(f"  {i}/{len(rows)}件")

        key, label = ec.pref_of(r["pref_raw"] or detail.get("place", ""))
        shop = venue_of(detail, r["title"]) if detail else r["title"]
        ev = {"date": r["date"], "pref": key, "label": label,
              "shop": shop, "url": r["url"]}
        if key == "unknown":
            unknown.append({**ev, "title": r["title"],
                            "pref_raw": r["pref_raw"], "place": detail.get("place", "")})
        events.append(ev)

    events.sort(key=lambda e: (e["date"], e["label"], e["shop"]))

    # ---- 下書きとして保存 ------------------------------------------------
    payload = {
        "generatedAt": today,
        "source": ec.BASE + LIST_PATH,
        "total": total,
        "count": len(events),
        "unknownPref": unknown,
        "events": events,
    }
    with open(ec.DRAFT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print()
    print(f"下書きを書きました: {ec.DRAFT_JSON}（{len(events)}件）")
    if unknown:
        print(f"⚠ 都道府県を判定できませんでした {len(unknown)}件")
        for u in unknown[:10]:
            print(f"   {u['date']} {u['shop']}（{u['pref_raw'] or '都道府県の表記なし'}）")
    print()
    print("--- 先頭5件 ---")
    for e in events[:5]:
        print(f"  {e['date']} [{e['label'] or '?'}] {e['shop']}")
        print(f"            {e['url']}")
    print()
    print("次は py review_events.py で差分を確認してください。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
