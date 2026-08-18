# ミニ四リン駆

タミヤ ミニ四駆・クラフトツールの品番カタログです。

**公開サイト: https://mini4lin9.fun/**

タミヤ公式サイトの品番・正式名称・メーカー希望価格・商品写真をもとにした一覧に、
各ECサイト（amazon / メルカリ / Yahoo!ショッピング / ヤフオク）の検索へのリンクを添えています。

| ジャンル | 件数 | 公式ジャンルコード |
|---|---|---|
| GUパーツ（グレードアップパーツ） | 243 | 303010 |
| 限定パーツ | 83 | 303025 |
| AOパーツ | 42 | 303030 |
| キット | 467 | 3010 |
| クラフトツール | 152 | 5020 |

## 自動更新

サイトは GitHub Actions で自動生成・自動公開されます（`.github/workflows/deploy.yml`）。

| 更新のきっかけ | 何が起きるか |
|---|---|
| `main` への push | カタログを再生成して即時公開 |
| 毎週月曜 6:00 JST | タミヤ公式から品番一覧を取り直して公開 |
| Actionsタブの手動実行 | 任意のタイミングで再生成 |

## ローカルでの動かし方

Python 3.10以上が必要です。外部ライブラリは使いません（標準ライブラリのみ）。

```bash
py fetch_tamiya_catalog.py     # タミヤ公式から品番マスタを取得（数分）
py build_official_index.py     # site/index.html を生成
```

生成された `site/index.html` をブラウザで開けば確認できます。
`fetch_tamiya_catalog.py` は公式サイトへの負荷に配慮して1秒間隔でアクセスします。

品番マスタ（`tamiya_catalog.json`）は取得済みのものが同梱されているので、
見た目だけ調整したい場合は `build_official_index.py` だけ実行すれば十分です。

## ファイル構成

| ファイル | 役割 |
|---|---|
| `fetch_tamiya_catalog.py` | タミヤ公式を巡回して `tamiya_catalog.json` を作る |
| `build_official_index.py` | 品番マスタから `site/index.html` を生成する |
| `tamiya_catalog.json` | 品番マスタ（987件） |
| `assets/` | ファビコン等。生成時に `site/assets/` へコピーされる |
| `CNAME` | 独自ドメイン設定（`mini4lin9.fun`） |
| `index.html` | リポジトリ直下からカタログへのリダイレクト |
| `site/` | 生成物。GitHub Pages はここを配信する |

## 設定値

アフィリエイトの計測IDは `build_official_index.py` の先頭にまとめてあります。

| 定数 | 内容 |
|---|---|
| `MERCARI_AFID` | メルカリアンバサダー |
| `AMAZON_TAG` | Amazonアソシエイト |
| `VALUECOMMERCE_ID` | ValueCommerce（申請中。IDが出たらここに入れる） |

## 掲載情報について

- 品番・名称・価格・商品写真はタミヤ公式サイトの情報です（出典: tamiya.com）。
  商品写真は公式サイトから直接参照しています。
- お気に入り機能は閲覧者のブラウザ内（localStorage）にのみ保存され、
  サーバーには送信されません。
