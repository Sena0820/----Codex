# Daily Info Dashboard

Python と RSS を使って、指定キーワードに関連する記事を毎日集め、業務活用や生活改善の観点で重要度が高い記事をローカル向け Markdown にまとめる最小構成です。Web 公開や自動実行は含まず、まずは手元で JSON を保存し、スマホで読みやすい `output/daily.md` を生成するところまでに絞っています。

## 構成

```text
daily-info-dashboard/
├─ README.md
├─ requirements.txt
├─ config/
│  └─ sources.yaml
├─ scripts/
│  ├─ fetch.py
│  └─ build_md.py
├─ data/
│  └─ raw/
└─ output/
   └─ daily.md
```

## セットアップ

```bash
pip install -r requirements.txt
```

## 実行方法

RSS を取得して日付付き JSON を保存します。

```bash
python scripts/fetch.py
```

最新の JSON から、関連度と重要度を加味した Markdown と HTML を生成します。

```bash
python scripts/build_md.py
```

生成結果:

- `data/raw/YYYY-MM-DD.json`
- `output/daily.md`
- `output/site/index.html`
- `output/site/YYYY-MM-DD/index.html`

## 情報源と調査テーマの管理

RSS 情報源と追跡キーワードは `config/sources.yaml` で管理します。

```yaml
topics:
  - name: Codex
    keywords:
      - codex

sources:
  - name: OpenAI Blog
    category: AI
    url: https://openai.com/news/rss.xml
```

### `topics`

- `name`: Markdown 上で表示するテーマ名
- `keywords`: マッチ判定に使う単語や表記ゆれ
- 例: `Business Skills` を追加しておくと、タスク管理、協働、会議運営、資料作成、文章作成などの基本スキル系記事も拾えます。

### `sources`

- `name`: 情報源名
- `category`: 情報源のカテゴリ
- `url`: RSS URL
- 興味に合う記事が少ないときは、同じトピックに複数の情報源を足すのがいちばん効きます。たとえば AI、分析、GTM/GA4、業務改善ごとに 3 から 6 件ほど入れておくと拾える幅がかなり広がります。

## いまの選定ロジック

- 指定キーワードがタイトルや本文抜粋に含まれる記事だけを対象にします。
- URL 重複は除外します。
- 業務で使いやすい更新、使い方、分析、ワークフロー、自動化などの語を含む記事を高く評価します。
- 新しさも少しだけ加点します。
- Markdown では、まず全体の重要記事 5 件を表示し、その後に各トピックごとの上位 3 件を表示します。

## 出力内容

各記事には次の情報を出します。

- 日本語タイトル
- URL
- 情報源
- 公開日
- 重要度スコア
- 読むべき度
- 内容要約

## 仕様メモ

- RSS の取得失敗は処理全体を止めず、警告を表示してスキップします。
- 要約 AI API は使いません。RSS の本文抜粋から短い要約を作ります。
- タイトルと要約の日本語化は翻訳サービスを使います。翻訳に失敗した場合は元の本文をそのまま表示します。
- HTML はスマホで縦に流し読みしやすいよう、1記事あたりの高さを抑えたレイアウトです。
- GTM は初期設定では `Google Tag Manager` として扱っています。別の意味で使いたい場合は `topics` のキーワードを調整してください。
