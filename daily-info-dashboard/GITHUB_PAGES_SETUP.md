# GitHub Actions で Pages を更新する手順

このプロジェクトは GitHub Actions で毎日記事を取得し、GitHub Pages に公開できます。ここでは最初の設定と、更新の流れを簡単にまとめます。

## 前提

- リポジトリが GitHub に push されている
- workflow ファイルがリポジトリ直下の `.github/workflows/daily-dashboard.yml` にある
- GitHub のリポジトリ設定を変更できる権限がある

## 1. GitHub Pages を GitHub Actions にする

1. GitHub で対象リポジトリを開く
2. `Settings` を開く
3. 左メニューの `Pages` を開く
4. `Build and deployment` の `Source` を `GitHub Actions` にする

## 2. GitHub Actions を有効にする

1. `Settings` を開く
2. 左メニューの `Actions` > `General` を開く
3. `Allow all actions and reusable workflows` を選ぶ
4. 必要なら `Read and write permissions` ではなく、workflow に書いてある `permissions` 設定をそのまま使う

## 3. 初回実行をする

1. GitHub の `Actions` タブを開く
2. `Daily Dashboard` を選ぶ
3. `Run workflow` を押す
4. ブランチは `main` を選んで実行する

成功すると workflow の最後で GitHub Pages にデプロイされます。

補足:

- workflow は Node 24 対応の公式 Actions バージョンを使います
- annotation で Node 20 廃止予告が出る場合は、Actions の major version を更新します

## 4. 公開URLを確認する

1. `Actions` の実行結果を開く
2. `Deploy to GitHub Pages` が成功していることを確認する
3. `Settings` > `Pages` を開く
4. 公開URLを確認する

公開後のページ構成は次のとおりです。

- `/` : 最新ページへ自動転送
- `/archive/` : 日付別アーカイブ
- `/{YYYY-MM-DD}/` : その日の記事ページ

## 5. 毎日自動更新される時刻

workflow は毎日 `07:00 JST` に動く想定です。

補足:

- GitHub Actions の `cron` は UTC で設定します
- このプロジェクトでは `22:00 UTC` を使っていて、これは `07:00 JST` に相当します
- GitHub Actions のスケジュール実行は数分遅れることがあります

## 6. ローカルで事前確認したいとき

```bash
cd daily-info-dashboard
pip install -r requirements.txt
python scripts/fetch.py
python scripts/build_md.py
```

生成される主なファイル:

- `data/raw/YYYY-MM-DD.json`
- `output/daily.md`
- `output/site/index.html`
- `output/site/archive/index.html`
- `output/site/YYYY-MM-DD/index.html`

## 7. 内容を変更して反映する流れ

1. ローカルでコードや `config/sources.yaml` を修正する
2. 必要ならローカルで動作確認する
3. GitHub に commit / push する
4. `Actions` タブで `Run workflow` を押す
5. デプロイ完了後にスマホで Pages を開く

## 8. よくある確認ポイント

- workflow ファイルは `daily-info-dashboard/.github/` ではなく、リポジトリ直下の `.github/workflows/` にあるか
- `Actions` が無効化されていないか
- `Pages` の `Source` が `GitHub Actions` になっているか
- `main` ブランチに最新の workflow とスクリプトが push されているか
- RSS取得先が一時的に落ちていないか
- Actions の major version が古くなっていないか

## 9. うまくいかないとき

見る場所:

- `Actions` タブの `Daily Dashboard`
- 実行ログの `Fetch yesterday's articles`
- 実行ログの `Build markdown and site`
- 実行ログの `Deploy to GitHub Pages`

記事が少ないときは `config/sources.yaml` の情報源やキーワードを広げるのが効果的です。
