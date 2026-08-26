# -*- coding: utf-8 -*-
"""X Machines の各投稿について、写真から「マシンカラー」を決める。

やること:
  1. 投稿IDから、埋め込み用の公開エンドポイントで写真URLを取る
  2. 写真を小さく落として取り込む
  3. 背景（画像の縁からつながっている一様な色）を取り除く
  4. 残った画素を色ゾーンに振り分け、いちばん面積の多いゾーンをマシンカラーとする

3 が肝。机・マット・壁が画面の大半を占める写真が多く、
素直に全画素を数えるとホワイトとブラックばかりになるため、
画像の縁から色がつながっている範囲を塗りつぶして除いてから数える。

結果は docs/data/x-machine-colors.json に書く。
写真とAPIの応答は cache/ に貯めるので、2回目からは通信しない。

    py x_machine_colors.py            # 未取得ぶんだけ通信して処理する
    py x_machine_colors.py --recolor  # 通信せず、色の判定だけやり直す
"""
import colorsys
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections import deque

from PIL import Image, ImageChops, ImageFilter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REG = os.path.join("docs", "data", "x-featured-posts.json")
OUT = os.path.join("docs", "data", "x-machine-colors.json")
CACHE_API = os.path.join("cache", "x-tweets")
CACHE_IMG = os.path.join("cache", "x-images")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
WAIT = 0.7          # 連続で叩かないための間隔（秒）
LONG_SIDE = 150     # 解析に使う大きさ
MAX_PHOTOS = 4      # 1投稿あたり見る枚数

# --- 調整用のつまみ ---------------------------------------------------
BG_STEP = 26        # 隣の画素とこれだけ近ければ背景がつながっているとみなす
BG_FAR = 118        # ただし縁の色からこれ以上離れたら、そこで止める
BG_BORDER = 0.05    # 背景の色を学ぶ縁の幅（短辺に対する割合）
BG_CLUSTERS = 3     # 背景色をいくつまで認めるか（グラデ背景対策）
CENTER_BOOST = 1.5  # 中央の画素をどれだけ重く見るか
CHROMA_BOOST = 1.15  # 有彩色をどれだけ優遇するか
BLACK_DISCOUNT = 0.6  # 黒はどのマシンにも出るので割り引く（タイヤ・シャーシ・影）
MULTI_BELOW = 0.22  # 一番多いゾーンがこの割合に届かなければ「カラフル」
MIN_KEEP = 0.10     # 背景を削りすぎたら（残りがこの割合未満）削らずに数え直す
METAL_WIN = 3       # てかりを見る窓の大きさ（画素）。奇数のみ。広いと輪郭を拾う
METAL_HI = 190      # すぐ近くにこれ以上明るい点があること（＝白飛びしたてかり）
METAL_RANGE = 55    # かつ、その窓の中で明るさがこれ以上動いていること
GOLD_WINS = 0.15    # 金メッキはこれだけ映れば、面積1位でなくてもゴールド扱いにする
#                     （金は面積では勝てないが、見た目の印象は強く残るため）
# ----------------------------------------------------------------------

# ゾーンの並び順（UIでもこの順に出す）。key, 表示名, 代表色
ZONES = [
    ("red", "レッド", "#e5342c"),
    ("orange", "オレンジ", "#f07a1a"),
    ("yellow", "イエロー", "#f5c518"),
    ("green", "グリーン", "#2fae5a"),
    ("blue", "ブルー", "#2277dd"),
    ("purple", "パープル", "#8b5cf6"),
    ("pink", "ピンク", "#ef5da8"),
    ("gold", "ゴールド", "#c9a227"),
    ("silver", "シルバー", "#aab2bd"),
    ("white", "ホワイト", "#f2f4f7"),
    ("black", "ブラック", "#2b2f36"),
    ("multi", "カラフル", "#7d5fff"),
]
NEUTRAL = {"white", "silver", "black"}


# ==== 取得まわり =======================================================

def token_of(tweet_id: str) -> str:
    """埋め込みが使っているトークン。投稿IDから決まる。"""
    n = (int(tweet_id) / 1e15) * 3.141592653589793
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    i, frac = int(n), n - int(n)
    s = "0" if i == 0 else ""
    while i:
        s = digits[i % 36] + s
        i //= 36
    out = s + "."
    for _ in range(20):
        frac *= 36
        d = int(frac)
        out += digits[d]
        frac -= d
    return re.sub(r"(0+|\.)", "", out)


def get(url: str, timeout: int = 25) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def tweet_data(tweet_id: str) -> dict:
    os.makedirs(CACHE_API, exist_ok=True)
    path = os.path.join(CACHE_API, tweet_id + ".json")
    if os.path.exists(path):
        return json.load(open(path, encoding="utf-8"))
    url = ("https://cdn.syndication.twimg.com/tweet-result?id=%s&lang=ja&token=%s"
           % (tweet_id, token_of(tweet_id)))
    try:
        d = json.loads(get(url).decode("utf-8"))
    except urllib.error.HTTPError as e:
        d = {"_error": "HTTP %s" % e.code}
    except Exception as e:                                  # noqa: BLE001
        d = {"_error": str(e)}
    json.dump(d, open(path, "w", encoding="utf-8"), ensure_ascii=False)
    time.sleep(WAIT)
    return d


def photos_of(d: dict) -> list:
    out = [p["url"] for p in (d.get("photos") or []) if p.get("url")]
    if not out:
        for m in (d.get("mediaDetails") or []):
            if m.get("media_url_https"):
                out.append(m["media_url_https"])
    return out[:MAX_PHOTOS]


def image_path(url: str) -> str:
    os.makedirs(CACHE_IMG, exist_ok=True)
    name = url.rsplit("/", 1)[-1].split("?")[0]
    path = os.path.join(CACHE_IMG, name)
    if os.path.exists(path):
        return path
    try:
        data = get(url + ("&" if "?" in url else "?") + "name=small")
    except Exception:                                       # noqa: BLE001
        return ""
    open(path, "wb").write(data)
    time.sleep(WAIT)
    return path


# ==== 色の判定 =========================================================

def zone_of(r: int, g: int, b: int, metal: bool = False) -> str:
    """1画素をゾーンに振り分ける。

    metal は「そのすぐ周りで明るさが急に変わっているか」。
    金属は表面がてかるので、狭い範囲に白飛びと影が同居する。
    塗り分けただけの平らな黄色やオーカーにはこれが出ない。
    """
    h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
    hd = h * 360.0

    # 暗くても色みが残っていれば、その色として扱う（濃紺・ダークグリーンなど）
    if v < 0.11:
        return "black"
    if s < 0.17:
        if v > 0.76:
            return "white"
        if v > 0.38:
            return "silver"
        return "black"

    # 金は「黄〜オーカーの色みを持ち、かつ金属らしくてかっている」もの。
    # 色だけでは平らな黄色と見分けが付かないので、てかりを条件に入れる。
    # 彩度に上限を置くのが効く。金メッキは真鍮寄りでくすんでおり、
    # 黄色い塗装ほど鮮やかにならない。ここで塗装の黄色と分かれる。
    if metal and 25 <= hd < 62 and 0.18 <= s <= 0.60 and v >= 0.25:
        return "gold"
    if hd < 14 or hd >= 344:
        return "red"
    if hd < 30:
        return "orange"
    if hd < 70:
        return "yellow"
    if hd < 160:
        return "green"
    if hd < 258:
        return "blue"
    if hd < 300:
        return "purple"
    return "pink"


def bg_seeds(px, w, h):
    """画像の縁の色から、背景とみなす代表色をいくつか作る。"""
    b = max(2, int(min(w, h) * BG_BORDER))
    bins = {}
    for y in range(h):
        inner = b <= y < h - b
        for x in range(w):
            if inner and b <= x < w - b:
                continue
            r, g, bl = px[(y * w + x) * 3:(y * w + x) * 3 + 3]
            key = (r >> 5, g >> 5, bl >> 5)
            acc = bins.setdefault(key, [0, 0, 0, 0])
            acc[0] += r
            acc[1] += g
            acc[2] += bl
            acc[3] += 1
    top = sorted(bins.values(), key=lambda a: -a[3])[:BG_CLUSTERS]
    return [(a[0] // a[3], a[1] // a[3], a[2] // a[3]) for a in top if a[3]]


def machine_mask(px, w, h):
    """縁からつながっている背景を塗りつぶし、残った画素だけ 1 のマスクを返す。

    「隣の画素と色が近ければ、そこも背景」という広げ方をする。
    こうするとグラデーションの背景も最後まで追える。
    ただし縁の色から離れすぎたら止める（マシンまで食べないため）。
    """
    seeds = bg_seeds(px, w, h)
    if not seeds:
        return None

    def far_from_seeds(r, g, b):
        best = min((r - sr) ** 2 + (g - sg) ** 2 + (b - sb) ** 2
                   for sr, sg, sb in seeds)
        return best > BG_FAR * BG_FAR

    keep = bytearray(b"\x01" * (w * h))
    q = deque()

    def seed(x, y):
        i = (y * w + x) * 3
        if far_from_seeds(px[i], px[i + 1], px[i + 2]):
            return
        keep[y * w + x] = 0
        q.append((x, y))

    for x in range(w):
        for y in (0, h - 1):
            if keep[y * w + x]:
                seed(x, y)
    for y in range(h):
        for x in (0, w - 1):
            if keep[y * w + x]:
                seed(x, y)

    step2 = BG_STEP * BG_STEP
    while q:
        x, y = q.popleft()
        i = (y * w + x) * 3
        r, g, b = px[i], px[i + 1], px[i + 2]
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if not (0 <= nx < w and 0 <= ny < h) or not keep[ny * w + nx]:
                continue
            j = (ny * w + nx) * 3
            nr, ng, nb = px[j], px[j + 1], px[j + 2]
            if (nr - r) ** 2 + (ng - g) ** 2 + (nb - b) ** 2 > step2:
                continue            # 隣と色が違う＝ここが物の輪郭
            if far_from_seeds(nr, ng, nb):
                continue            # 縁の色から離れすぎた＝もう背景ではない
            keep[ny * w + nx] = 0
            q.append((nx, ny))
    return keep


def tally_image(path, tally):
    """1枚を数えて tally に足す。戻り値は (使った画素数, 全画素数)。"""
    try:
        im = Image.open(path).convert("RGB")
    except Exception:                                       # noqa: BLE001
        return (0, 0)
    w, h = im.size
    sc = LONG_SIDE / float(max(w, h))
    if sc < 1:
        im = im.resize((max(1, int(w * sc)), max(1, int(h * sc))), Image.BILINEAR)
        w, h = im.size
    px = im.tobytes()

    # 「そのすぐ周りで明るさがどれだけ動くか」を1枚ぶんまとめて出す。
    # 最大値フィルタと最小値フィルタの差＝狭い範囲での明暗の幅。
    # 金属のてかりはここが大きく、平らな塗装は小さい。
    gray = im.convert("L")
    mx = gray.filter(ImageFilter.MaxFilter(METAL_WIN))
    mn = gray.filter(ImageFilter.MinFilter(METAL_WIN))
    hi = mx.tobytes()                                   # すぐ近くの一番明るい点
    rng = ImageChops.difference(mx, mn).tobytes()       # 狭い範囲での明暗の幅

    keep = machine_mask(px, w, h)
    used = sum(keep) if keep else w * h
    # 削りすぎたときは、背景を削らずに数える（判定不能を避けるため）
    if not keep or used < w * h * MIN_KEEP:
        keep = None
        used = w * h

    cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
    dmax = (cx * cx + cy * cy) ** 0.5 or 1.0
    for y in range(h):
        for x in range(w):
            if keep is not None and not keep[y * w + x]:
                continue
            k = y * w + x
            i = k * 3
            d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5 / dmax
            wgt = 1.0 + CENTER_BOOST * (1.0 - d)
            metal = hi[k] >= METAL_HI and rng[k] >= METAL_RANGE
            tally[zone_of(px[i], px[i + 1], px[i + 2], metal)] += wgt
    return (used, w * h)


def analyze(paths: list) -> tuple:
    tally = {k: 0.0 for k, _, _ in ZONES}
    used = total = 0
    for p in paths:
        u, t = tally_image(p, tally)
        used += u
        total += t
    s = sum(tally.values())
    if not s:
        return ({}, 0.0)
    share = {k: v / s for k, v in tally.items() if v}
    return (share, (used / total) if total else 0.0)


def pick(share: dict) -> tuple:
    """割合から代表色を決める。返り値は (ゾーン, その割合)。"""
    if not share:
        return ("multi", 0.0)
    # 金メッキは面積では勝てない（パーツ単位で使われることが多い）が、
    # 見た目の印象は強く残る。一定量映っていればゴールドとして扱う。
    if share.get("gold", 0) >= GOLD_WINS:
        return ("gold", share["gold"])
    # 黒はタイヤ・シャーシ・影としてどのマシンにも必ず出るので、
    # 「そのマシンらしさ」を表す度合いが低い。割り引いて比べる。
    scored = {}
    for k, v in share.items():
        if k == "multi":
            continue
        if k == "black":
            scored[k] = v * BLACK_DISCOUNT
        elif k in NEUTRAL:
            scored[k] = v
        else:
            scored[k] = v * CHROMA_BOOST
    top = max(scored, key=scored.get)
    if share[top] < MULTI_BELOW:
        return ("multi", share[top])
    return (top, share[top])


# ==== 本体 =============================================================

def main(argv: list) -> int:
    recolor = "--recolor" in argv
    reg = json.load(open(REG, encoding="utf-8"))
    old = {}
    if os.path.exists(OUT):
        old = {r["id"]: r for r in json.load(open(OUT, encoding="utf-8"))["items"]}

    items, missing = [], []
    for i, post in enumerate(reg["posts"], 1):
        pid, url = post["id"], post["url"]
        tid = url.rsplit("/", 1)[-1]

        d = tweet_data(tid)      # 1度取ったら cache から読むだけ
        if d.get("_error"):
            missing.append((pid, url, d["_error"]))
            continue
        urls = photos_of(d)
        prev = old.get(pid)
        if recolor and prev and prev.get("files"):
            paths = [os.path.join(CACHE_IMG, f) for f in prev["files"]]
        else:
            paths = [p for p in (image_path(u) for u in urls) if p]
        if not paths:
            missing.append((pid, url, "写真なし"))
            continue

        share, kept = analyze(paths)
        zone, ratio = pick(share)

        # レジストリ側に "color" が書いてあれば、そちらを優先する。
        # 写真だけでは決められないマシンがどうしても残るので、
        # 人が手で直せる逃げ道を残しておく（自動判定は下書きという扱い）。
        source = "auto"
        manual = post.get("color")
        if manual in {k for k, _, _ in ZONES}:
            zone, source = manual, "manual"

        items.append({
            "id": pid, "url": url, "color": zone, "source": source,
            "auto": pick(share)[0], "ratio": round(ratio, 3),
            "kept": round(kept, 3),
            "share": {k: round(v, 3) for k, v in sorted(
                share.items(), key=lambda kv: -kv[1])[:5]},
            "files": [os.path.basename(p) for p in paths],
            "photo": urls[0] if urls else "",
            "handle": (d.get("user") or {}).get("screen_name", ""),
            "memo": post.get("memo", ""),
        })
        if i % 20 == 0:
            print("  %d / %d 件" % (i, len(reg["posts"])))

    json.dump({"zones": [{"key": k, "label": lb, "swatch": sw} for k, lb, sw in ZONES],
               "items": items},
              open(OUT, "w", encoding="utf-8", newline="\n"),
              ensure_ascii=False, indent=1)

    count = {}
    for it in items:
        count[it["color"]] = count.get(it["color"], 0) + 1
    print("\n判定できた投稿: %d / %d 件" % (len(items), len(reg["posts"])))
    for k, lb, _ in ZONES:
        if count.get(k):
            print("  %-6s %3d件" % (lb, count[k]))
    if missing:
        print("\n判定できなかったもの %d件:" % len(missing))
        for pid, url, why in missing[:20]:
            print("  %s %s  %s" % (pid, url, why))
    print("\n書き込み: %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
