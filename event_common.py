# -*- coding: utf-8 -*-
"""レース開催情報の取り込みで、取得側と確認側の両方が使う道具をまとめたもの。

ここには「決めごと」だけを置く。取りに行く処理は fetch_events.py、
人が確かめて反映する処理は review_events.py が持つ。
"""

from __future__ import annotations

import hashlib
import html
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

# ---- 相手先に名乗る文字列 ----------------------------------------------
# マナーとして、誰が取りに来ているか分かるようにしておく。
# 連絡先を差し替えたいときはここだけ直せばよい。
CONTACT = "https://mini4lin9.fun/"
USER_AGENT = f"mini4lin9-event-bot/1.0 (+{CONTACT})"

# 相手のサーバに負担をかけないための最低間隔（秒）
REQUEST_INTERVAL = 2.0

BASE = "https://www.tamiya.com"
ROBOTS_URL = BASE + "/robots.txt"

# 取得したものを置く場所。日付ごとに分けて、同じ日は取り直さない。
CACHE_DIR = "cache"

# race.html の置き場所。docs/ 配下に置くとそのまま公開される。
RACE_HTML = os.path.join("docs", "race.html")
DRAFT_JSON = "events_draft.json"

# ---- 都道府県 ----------------------------------------------------------
# キーはローマ字、値は画面に出す短い表記（「県」「府」「都」は付けない）。
PREFS: dict[str, str] = {
    "hokkaido": "北海道", "aomori": "青森", "iwate": "岩手", "miyagi": "宮城",
    "akita": "秋田", "yamagata": "山形", "fukushima": "福島", "ibaraki": "茨城",
    "tochigi": "栃木", "gunma": "群馬", "saitama": "埼玉", "chiba": "千葉",
    "tokyo": "東京", "kanagawa": "神奈川", "niigata": "新潟", "toyama": "富山",
    "ishikawa": "石川", "fukui": "福井", "yamanashi": "山梨", "nagano": "長野",
    "gifu": "岐阜", "shizuoka": "静岡", "aichi": "愛知", "mie": "三重",
    "shiga": "滋賀", "kyoto": "京都", "osaka": "大阪", "hyogo": "兵庫",
    "nara": "奈良", "wakayama": "和歌山", "tottori": "鳥取", "shimane": "島根",
    "okayama": "岡山", "hiroshima": "広島", "yamaguchi": "山口", "tokushima": "徳島",
    "kagawa": "香川", "ehime": "愛媛", "kochi": "高知", "fukuoka": "福岡",
    "saga": "佐賀", "nagasaki": "長崎", "kumamoto": "熊本", "oita": "大分",
    "miyazaki": "宮崎", "kagoshima": "鹿児島", "okinawa": "沖縄",
}

# 「静岡県」「東京都」といった正式表記から、上のキーを引くための逆引き表。
_FULL_TO_KEY: dict[str, str] = {}
for _key, _label in PREFS.items():
    _FULL_TO_KEY[_label] = _key
    for _suffix in ("県", "府", "都"):
        _FULL_TO_KEY[_label + _suffix] = _key


def pref_of(text: str) -> tuple[str, str]:
    """住所や都道府県表記から (キー, 短い表記) を返す。

    分からないときは ('unknown', 原文) を返す。呼び出し側で必ず警告すること。
    黙って捨てると、間違った場所のレースが混ざったまま公開されてしまう。
    """
    s = (text or "").strip()
    if not s:
        return "unknown", ""
    # まず丸ごと一致（一覧の pref_ は「静岡県」のように正式表記で入っている）
    key = _FULL_TO_KEY.get(s)
    if key:
        return key, PREFS[key]
    # 住所の途中に入っている場合。長い名前から先に見て「東京」より「東京都」を優先する。
    for full in sorted(_FULL_TO_KEY, key=len, reverse=True):
        if full in s:
            key = _FULL_TO_KEY[full]
            return key, PREFS[key]
    return "unknown", s


# ---- HTML の下ごしらえ --------------------------------------------------

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t　]+")


def text_of(fragment: str) -> str:
    """タグを外して、前後と連続する空白を整えた文字列にする。"""
    s = _TAG_RE.sub("", fragment or "")
    s = html.unescape(s)
    s = s.replace("\r", "\n")
    s = "\n".join(_WS_RE.sub(" ", line).strip() for line in s.split("\n"))
    return "\n".join(line for line in s.split("\n") if line).strip()


# ---- 取得 --------------------------------------------------------------

class FetchError(Exception):
    """取りに行けなかった。呼び出し側は必ず異常終了させること。"""


_last_request_at = 0.0


def _sleep_between() -> None:
    """前回の取得から REQUEST_INTERVAL 秒あくまで待つ。"""
    global _last_request_at
    wait = REQUEST_INTERVAL - (time.time() - _last_request_at)
    if wait > 0:
        time.sleep(wait)
    _last_request_at = time.time()


def cache_path(day: str, name: str) -> str:
    """cache/2026-08-21/<name> の形の置き場所を返す。"""
    return os.path.join(CACHE_DIR, day, name)


def cache_name(url: str) -> str:
    """URLから、そのまま file 名にできる短い名前を作る。

    長いURLは切り詰めるが、末尾だけが違うURL（ページ番号など）が
    同じ名前に潰れないよう、URL全体のハッシュを必ず付ける。
    """
    p = urllib.parse.urlparse(url)
    raw = (p.path + "?" + p.query).strip("/?")
    safe = re.sub(r"[^0-9A-Za-z._-]+", "_", raw)
    digest = hashlib.md5(url.encode("utf-8")).hexdigest()[:8]
    return (safe[:90] or "index") + "_" + digest + ".html"


def fetch_text(url: str, day: str, *, refresh: bool = False,
               allow_404: bool = False) -> str | None:
    """1ページ取得して本文を返す。取得済みならキャッシュを読む。

    allow_404 が真のときだけ、404 を「無い」として None で返す。
    それ以外の失敗は FetchError にする（黙って先へ進ませない）。
    """
    path = cache_path(day, cache_name(url))
    if not refresh and os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read()

    _sleep_between()
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ja,en-US;q=0.9",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            raw = res.read()
            ctype = res.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        if e.code == 404 and allow_404:
            return None
        raise FetchError(f"{url} の取得に失敗しました（HTTP {e.code}）") from e
    except Exception as e:  # 接続断・名前解決の失敗など
        raise FetchError(f"{url} に接続できませんでした（{e}）") from e

    text = decode(raw, ctype)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return text


def decode(raw: bytes, ctype: str = "") -> str:
    """文字コードを見分けて UTF-8 の文字列にする。

    タミヤのページは Shift_JIS。UTF-8 として読むと日本語が全滅し、
    「中身が空だ」と誤診する原因になるので、必ずここを通すこと。
    """
    m = re.search(r"charset=([\w-]+)", ctype or "", re.I)
    order = []
    if m:
        order.append(m.group(1))
    m = re.search(rb"charset=[\"']?([\w-]+)", raw[:4096], re.I)
    if m:
        order.append(m.group(1).decode("ascii", "ignore"))
    order += ["utf-8", "cp932", "euc-jp"]

    seen = set()
    for enc in order:
        enc = (enc or "").lower().strip()
        if enc in ("shift_jis", "shift-jis", "sjis", "x-sjis"):
            enc = "cp932"
        if not enc or enc in seen:
            continue
        seen.add(enc)
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    # どれでも読めなければ、化けを許してでも中身を見せる
    return raw.decode("cp932", "replace")


def robots_blocks(path: str, day: str, *, refresh: bool = False) -> str | None:
    """robots.txt を見て、その path が禁止なら理由の文章を返す。

    禁止されていなければ None。robots.txt が無い（404）場合は
    「指定なし＝許可」とみなす。取得そのものに失敗した場合は分からないので
    その旨を返し、呼び出し側で止める。
    """
    try:
        body = fetch_text(ROBOTS_URL, day, refresh=refresh, allow_404=True)
    except FetchError as e:
        return f"robots.txt を確認できませんでした（{e}）。安全のため中止します。"
    if body is None:
        return None  # robots.txt が無い＝制限なし

    # User-agent: * の段落だけを見る（自分専用の指定は無い前提）
    applies, rules = False, []
    for line in body.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        name, _, value = line.partition(":")
        name, value = name.strip().lower(), value.strip()
        if name == "user-agent":
            applies = value == "*"
        elif applies and name in ("disallow", "allow") and value:
            rules.append((name, value))

    # 長く一致する指定が優先。同じ長さなら allow を勝たせる。
    best = None
    for name, value in rules:
        if path.startswith(value):
            if best is None or len(value) > len(best[1]) or \
                    (len(value) == len(best[1]) and name == "allow"):
                best = (name, value)
    if best and best[0] == "disallow":
        return f"robots.txt で {best[1]} が禁止されています。取得を中止します。"
    return None
