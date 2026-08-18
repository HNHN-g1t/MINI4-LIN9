# Yahoo! Client ID（アプリケーションID）取得ガイド

所要時間 **約10分**、費用 **無料**、審査 **なし**（発行は即時）。

---

## 事前に必要なもの

1. **Yahoo! JAPAN ID** — 持っていなければ [https://account.yahoo.co.jp/](https://account.yahoo.co.jp/) で無料作成
2. **確認済みのメールアドレス** — 未確認だと途中で確認手続きが挟まります
3. **サイトのURL** — まだサイトが無くても大丈夫（下の「まだサイトが無い場合」参照）

---

## 手順

### STEP 1. 登録ページを開く

[https://e.developer.yahoo.co.jp/register](https://e.developer.yahoo.co.jp/register)

Yahoo! JAPAN IDでログインした状態でアクセスしてください。

### STEP 2. アプリケーションの種類を選ぶ

**「サーバーサイド（Server-side）」を選択します。**

今回のスクリプトはPythonがサーバー側でAPIを叩く構成なので、こちらが正解です。
ブラウザのJavaScriptから直接叩く場合のみ「クライアントサイド」を選びます。

### STEP 3. フォームを入力

| 項目 | 入力する内容の例 |
|---|---|
| アプリケーション名 | `パーツポスト` |
| サイトURL | `https://partspost.example.com`（後から変更可） |
| アプリケーションの説明 | `ミニ四駆・プラモデルの中古パーツ横断検索カタログ` |
| 連絡先メールアドレス | 確認済みのアドレスを選択 |
| コールバックURL | **入力不要**（Yahoo! ID連携を使う場合のみ必要） |
| 利用するAPI | ショッピング系にチェック |

> コールバックURLは「ユーザーにYahoo!でログインさせる」機能を使う時だけ必要です。
> 商品検索APIは不要なので空欄で構いません。

### STEP 4. ガイドラインに同意 → 確認 → 登録

「ガイドラインに同意しますか？」で **同意する** を選び、
「確認」→「登録」と進むと、その場で **Client ID** が表示されます。

### STEP 5. Client IDを控える

`dj00aiZpPXh4eHh4eHh4...` のような長い文字列です。
後から [アプリケーションの管理](https://e.developer.yahoo.co.jp/register) でいつでも確認できます。

---

## 設定ファイルに入れる

```bash
cp config.json.example config.json
```

`config.json` を開き、`yahoo_appid` に貼り付けます:

```json
{
  "yahoo_appid": "dj00aiZpPXh4eHh4eHh4...",
  "vc_affiliate_id": "",
  "vc_token": "",
  "shop_csv_dir": "shops"
}
```

## 実行して確認

```bash
python3 build_partspost.py --query "ミニ四駆 大径ローハイトタイヤ" --item-code 15435
```

成功するとこう出ます:

```
生成完了: partspost.html ／ 20件 ／ 相場中央値 ¥1,180
  - Yahoo!ショッピングAPI: 20件
  - ValueCommerce(ヤフオク): スキップ（vc_token 未設定）
  - メルカリ: ディープリンク生成（公開APIなし）
  - ショップCSV: 2件（shops/）
```

---

## 知っておくべき2つの制約

### ① リクエスト制限は「1クエリ／秒」

品番を大量にループ処理する時は、1件ごとに1秒以上の待ち時間を入れてください。
短時間に大量アクセスすると一時的に利用できなくなります。

```python
import time
for code in item_codes:
    fetch_yahoo(appid, code)
    time.sleep(1.2)   # 必須
```

### ② 商用利用は事前の問い合わせが必要

Yahoo!のWeb APIは原則として非商用利用が前提です。商用サイトが一律禁止という
わけではありませんが、**広告収益を得るサイトで使うなら事前にYahoo!へ問い合わせて
確認を取る**のが正規の手順です。

問い合わせ先: [https://developer.yahoo.co.jp/developer/contact/](https://developer.yahoo.co.jp/developer/contact/)

伝えるべき内容:
- サイトの概要（ミニ四駆・プラモデルパーツの横断検索カタログ）
- 使用するAPI（Yahoo!ショッピング 商品検索API v3）
- 収益モデル（アフィリエイト報酬および掲載広告）
- 想定リクエスト数（1日あたり◯件程度）

**開発・検証の段階では問題ありません。** 公開して収益化する前に確認を取ってください。

---

## 収益化するなら：アフィリエイトIDも設定する

ValueCommerceのアフィリエイトIDを `vc_affiliate_id` に入れると、
商品検索APIが返すURLが成果計測付きリンクになり、経由売上が報酬になります。

```json
"vc_affiliate_id": "あなたのValueCommerceアフィリエイトID"
```

スクリプト側は `affiliate_type=vc` を自動付与するので、IDを入れるだけで有効になります。
ValueCommerceの登録はヤフオク!側（系統2）でもどのみち必要なので、
**先にValueCommerceに登録しておくと二度手間になりません。**

---

## 次のステップ

| 系統 | 状態 | 次にやること |
|---|---|---|
| Yahoo!ショッピング | ← 今ここ | Client ID発行 |
| 個人ショップCSV | すぐ使える | `shops/` にCSVを置く |
| ヤフオク! | 提携審査あり | ValueCommerce登録 → ヤフオク!と提携申請 |
| メルカリ | リンクのみ | メルカリアンバサダー登録（任意） |
