# ミニ四リン駆

ミニ四駆パーツの販売情報をモール横断でまとめています。

**公開サイト: https://mini4lin9.fun/**

（独自ドメイン。GitHub Pages の従来URL https://hnhn-g1t.github.io/partspost/ からは自動転送されます）

タミヤ公式の品番・正式名称・商品写真をもとにしたカタログに、Yahoo!ショッピング・
ヤフオク・メルカリ・個人ショップの出品情報を組み合わせています。
サイトは GitHub Actions で自動生成・自動公開されます（`.github/workflows/deploy.yml`）。

| 更新のきっかけ | 何が起きるか |
|---|---|
| `main` への push | カタログを再生成して即時公開 |
| 毎週月曜 6:00 JST | タミヤ公式から品番一覧を取り直して公開 |
| Actionsタブの手動実行 | 任意のタイミングで再生成 |

---

## 動かし方（ローカル）

## いちばん大事なこと

**`template.html` は直接開かないでください。** これは穴あきの雛形なので、`{{QUERY}}` のような
記号がそのまま見えます。ブラウザで開くべきなのは、スクリプトが生成する **`partspost.html`** です。

同梱の `partspost.html` は生成済みなので、まずはそれを開けば完成形が見られます。

---

## 1. デモを動かす（3分・キー不要）

必要なもの: Python 3.10以上（`python3 --version` で確認。Macは標準で入っています）

```bash
# zipを解凍したフォルダに移動してから
python3 build_partspost.py --demo
```

`partspost.html` が生成されます。これをダブルクリックで開いてください。

うまくいくと、こう表示されます:

```
生成完了: partspost.html ／ 10件 ／ 相場中央値 ¥1,015
  - デモデータ（サンプル）で生成
```

---

## 2. 実データを入れる

### 準備: 設定ファイルを作る

```bash
cp config.json.example config.json
```

`config.json` をテキストエディタで開き、取得できたキーだけを埋めます。
**空のままの系統は自動でスキップされる**ので、1つずつ増やしていけば大丈夫です。

| 設定キー | 何を入れるか | 取得先 | 難易度 |
|---|---|---|---|
| `yahoo_appid` | Client ID | [Yahoo!デベロッパーネットワーク](https://developer.yahoo.co.jp/) | 即日・無料 |
| `vc_token` | Webサービストークン | ValueCommerce管理画面 → 広告 → 対応機能別 → Webサービス | 提携審査あり |
| `vc_yahoo_auction_ec_code` | ヤフオク!のecCode | ValueCommerce管理画面の提携一覧 | 任意 |
| `mercari_ambassador_suffix` | 計測パラメータ | メルカリアンバサダー管理画面 | 任意 |

### 実行

```bash
python3 build_partspost.py --query "ミニ四駆 大径ローハイトタイヤ" --item-code 15435
```

---

## 3. 個人ショップのCSVを入れる（キー不要・今すぐ試せる）

`shops/` フォルダにCSVを置くだけです。同梱の `shops/hoshino_model.csv` が見本です。

列名は BASE や STORES のエクスポートに合わせてあり、以下のどれでも認識します:

- 品番 / item_code / 型番
- 商品名 / title / name
- 販売価格 / price / 価格
- 送料 / shipping
- 商品URL / url / 公開URL
- ショップ名 / seller / 店舗名
- 状態 / condition
- 広告枠 / is_ad … `1` を入れるとAD枠として検索結果に差し込まれます

CSVだけで動作確認する場合:

```bash
cp config.json.example config.json
# config.json の yahoo_appid と vc_token を "" (空) にしておく
python3 build_partspost.py --query "15435" --item-code 15435
```

---

## ファイル構成

| ファイル | 役割 | 直接開く？ |
|---|---|---|
| `partspost.html` | **生成された完成ページ** | ✅ これを開く |
| `build_partspost.py` | 生成スクリプト（実行するのはこれ） | — |
| `sources.py` | 4系統の取り込み層 | — |
| `template.html` | 穴あき雛形 | ❌ 開かない |
| `sample_listings.json` | デモ用データ・品番情報 | — |
| `config.json.example` | 設定ファイルの見本 | — |
| `shops/*.csv` | 個人ショップの入稿データ | — |

---

## つまずいたら

**`python3: command not found`**
→ Windowsなら `py build_partspost.py --demo` を試してください。

**`FileNotFoundError: template.html`**
→ zipを解凍したフォルダの中でコマンドを実行してください（`cd` で移動）。

**ページに `{{QUERY}}` が見える**
→ `template.html` を開いています。`partspost.html` を開いてください。

**`警告: どの系統からも出品を取得できませんでした`**
→ 実モードでキーが全部空です。`--demo` を付けるか、`shops/` にCSVを置いてください。
