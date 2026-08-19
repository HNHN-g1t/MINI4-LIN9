# -*- coding: utf-8 -*-
"""スプレーの商品名から色を推定し、カラーマップ上の位置を決める。

商品名（例: 「PS-3 ライトブルー」「TS-96 蛍光オレンジ」）にはHEX値が無いため、
色名のキーワードから代表色を割り当て、HSLに変換して
    横軸 = 色相（赤→オレンジ→黄→緑→水色→青→紫→ピンク）
    縦軸 = 明るさ（明るい→暗い）
のグリッド位置を決める。

無彩色（白・グレー・黒・シルバー等）は NEUTRAL 帯、
色を持たないもの（クリヤー・ラメ等）は SPECIAL 帯に振り分ける。
"""
import colorsys
import re

# 効果（フィルタの分類にも使う）。上から順に判定する。
EFFECTS = [
    ("FLUORESCENT", ["蛍光"]),
    ("PEARL", ["パール", "マイカ"]),
    ("METALLIC", ["メタリック", "メタッリク", "アルミ", "クローム", "シルバー", "ゴールド",
                  "ガンメタル", "チタン", "アイアン", "ブロンズ", "カッパー"]),
    # フロスト（PS系のすりガラス調）は透過系なので CLEAR に含める
    ("CLEAR", ["クリヤー", "クリア", "スモーク", "フロスト"]),
]

# 明るさの補正（キーワード → HSLのLに対する係数）
LIGHT_ADJ = [
    ("ペール", 1.30), ("ライト", 1.22), ("ブライト", 1.12), ("ミディアム", 1.0),
    ("ディープ", 0.72), ("ダーク", 0.68), ("ダーグ", 0.68),
]

# 色名キーワード → 代表色。長いキーワードから順に判定する。
BASE_COLORS = {
    # 赤系
    "レッドブラウン": "#7b3f2e", "マイカレッド": "#a01824", "レーシングホワイト": "#f2f2f0",
    "レッド": "#d0202a", "赤": "#d0202a", "スカーレット": "#e03020",
    "マルーン": "#6d2432", "ワインレッド": "#7a1f2b",
    # ピンク・紫
    "マゼンタ": "#c72a7a", "ピンク": "#e86a9a", "パープル": "#7b3fa0",
    "バイオレット": "#6f42a8", "ライラック": "#b490cf", "紫": "#7b3fa0",
    # オレンジ・茶
    "オレンジ": "#ef7a1a", "橙": "#ef7a1a", "ブラウン": "#6d4a2f", "茶": "#6d4a2f",
    "カッパー": "#a8642f", "ブロンズ": "#8a6a3a", "タン": "#c9a06a", "バフ": "#cbb287",
    "サンド": "#cdb891", "デザートイエロー": "#c9ac6a", "ウッド": "#a9793f",
    # 黄
    "イエロー": "#f2c31d", "黄": "#f2c31d", "ゴールド": "#c9a227", "クリーム": "#efe2b0",
    "レモン": "#f0e04a",
    # 緑
    "ライムグリーン": "#8fd130", "オリーブ": "#6b6b34", "カーキ": "#7a7448",
    "灰緑色": "#7d8b7a", "グリーン": "#1e9c50", "緑": "#1e9c50", "ミント": "#7fd6b0",
    # 水色〜青
    "スカイブルー": "#63b8e8", "ターコイズ": "#26b3b6", "シアン": "#22b8d6",
    "コバルトブルー": "#1740b0", "ネイビー": "#1d2a56", "インディブルー": "#1f3f8f",
    "ブルー": "#1a5fc8", "青": "#1a5fc8", "ラベンダー": "#9a8cc8",
    # 軍用・情景色など、色名が独特なもの
    "ダークアース": "#7a6242", "アース": "#8a7350", "OD色": "#5f6144",
    "木甲板色": "#b98f5c", "リノリウム": "#8a5a3c", "フレッシュ": "#e8b898",
    "コッパー": "#a8642f",
    # 無彩色
    "ホワイト": "#f3f3f1", "白": "#f3f3f1", "ブラック": "#1d1d1f", "黒": "#1d1d1f",
    "ガンメタル": "#4a4f55", "ガンシップグレイ": "#5b6167", "シーグレイ": "#7d858c",
    "グレイ": "#8c9298", "グレー": "#8c9298", "灰": "#8c9298",
    "シルバー": "#c2c6ca", "アルミ": "#c6cacd", "チタン": "#9aa0a3",
    "クローム": "#cfd4d8", "アイアン": "#4b4e51", "スモーク": "#5a5a5a",
}
_BASE_ORDER = sorted(BASE_COLORS, key=len, reverse=True)

# 横軸（色相）の区分。角度の下限・上限（度）
HUE_BANDS = [
    ("レッド", 345, 15), ("オレンジ", 15, 45), ("イエロー", 45, 70),
    ("グリーン", 70, 160), ("スカイ", 160, 200), ("ブルー", 200, 250),
    ("パープル", 250, 300), ("ピンク", 300, 345),
]
# 縦軸（明るさ）の区分。上（明るい）から
LIGHT_BANDS = [("明るい", 0.62, 1.01), ("やや明るい", 0.48, 0.62),
               ("標準", 0.33, 0.48), ("暗い", -0.01, 0.33)]


def _hex_to_hsl(hx: str) -> tuple[float, float, float]:
    r, g, b = (int(hx[i:i + 2], 16) / 255 for i in (1, 3, 5))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return h * 360, s, l


def _hsl_to_hex(h: float, s: float, l: float) -> str:
    r, g, b = colorsys.hls_to_rgb((h % 360) / 360, max(0.0, min(1.0, l)), s)
    return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))


def _clean(name: str) -> str:
    """品番と補足を落として色名だけにする。"""
    s = re.sub(r"^(PS|TS|AS)[-\s]?\d*\s*", "", name)
    s = re.sub(r"[（(].*?[)）]", "", s)
    return s.strip()


def series_of(name: str) -> str:
    """品番の接頭辞（PS / TS / AS）を返す。"""
    m = re.match(r"^(PS|TS|AS)", name)
    return m.group(1) if m else ""


def classify(item: dict) -> dict:
    """商品1件のカラーマップ情報を返す。"""
    name = item["name"]
    color_name = _clean(name)
    series = series_of(name)

    effect = "STANDARD"
    for key, words in EFFECTS:
        if any(w in name for w in words):
            effect = key
            break

    base_hex, matched = None, ""
    for kw in _BASE_ORDER:
        if kw in color_name:
            base_hex, matched = BASE_COLORS[kw], kw
            break

    # 色名が拾えないもの（クリヤー単体・ラメ・プライマー等）は SPECIAL 帯へ
    if base_hex is None:
        return {**item, "swatch": "#d8dbe0", "effect": effect, "zone": "SPECIAL", "series": series,
                "color_name": color_name, "hue_band": "", "light_band": ""}

    h, s, l = _hex_to_hsl(base_hex)
    for kw, factor in LIGHT_ADJ:
        if kw in color_name:
            l = max(0.06, min(0.94, l * factor))
            break
    swatch = _hsl_to_hex(h, s, l)

    # 彩度が低いものは無彩色として NEUTRAL 帯へ
    if s < 0.14:
        return {**item, "swatch": swatch, "effect": effect, "zone": "NEUTRAL", "series": series,
                "color_name": color_name, "hue_band": "", "light_band": ""}

    hue_band = next(b for b, lo, hi in HUE_BANDS
                    if ((lo <= h < hi) if lo < hi else (h >= lo or h < hi)))
    light_band = next(b for b, lo, hi in LIGHT_BANDS if lo <= l < hi)
    return {**item, "swatch": swatch, "effect": effect, "zone": "MAP", "series": series,
            "color_name": color_name, "hue_band": hue_band, "light_band": light_band}


def build(items: list[dict]) -> list[dict]:
    """塗装ジャンルの商品にカラー情報を付ける。"""
    return [classify(i) for i in items]
