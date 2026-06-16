# ainews（Technology Daily Report）取扱説明書

> 毎朝、AI・先端技術・製造業界のニュースを自動で集めて要約し、記事一覧と音声（MP3）として届けるシステムです。

## このアプリでできること

- AI・先端技術・PCB/電子実装業界などのニュースを自動で収集します。
- 集めたニュースをAIが日本語で分かりやすく要約します。
- 要約をテキスト（Markdown）と音声（MP3）の両方で生成します。
- Webサイト上で記事一覧を読んだり、音声プレイヤーで聞いたりできます。
- 毎朝決まった時刻に自動更新されるため、手動操作なしで最新情報が届きます。

## 想定ユーザー・利用シーン

- 忙しくて技術ニュースを毎日チェックする時間がない方。
- 通勤中などに「ながら聞き」で最新動向をキャッチアップしたい方。
- PCB/電子実装・製造業界の技術ブレイクスルーを定点観測したい方。
- 朝のルーティンとして、まとめ記事をさっと読みたい方。

## 動作環境・前提

- 閲覧するだけの方: スマートフォンまたはPCのWebブラウザがあれば利用できます。本番サイト（下記「開発者向けメモ」参照）にアクセスするだけです。
- 自分で動かす・開発する方: Node.js（pnpm）と Python（uv）の環境が必要です。
- AI要約・音声生成には Google Gemini と Groq のAPIキーが必要です（無料枠を利用）。

## セットアップ

閲覧だけなら不要です。本番サイトにアクセスしてください。

自分で動かす場合:

1. リポジトリを取得します。
2. 収集処理（Python）の準備をします。
   ```bash
   cd collector
   # .env ファイルにAPIキーを記入（GEMINI_KEY_*, GROQ_API_KEY）
   ```
3. フロントエンド（Next.js）の準備をします。
   ```bash
   cd frontend && pnpm install
   ```

## 使い方（ステップbyステップ）

### 読者として使う場合

1. 本番サイトをブラウザで開きます。
2. トップページに最新の記事一覧が並びます。
3. 読みたい記事のタイトルをタップ／クリックします。
4. 要約本文が表示されます。音声プレイヤーがある記事は再生ボタンで「ながら聞き」できます。

### 自分で収集を実行する場合

1. APIキーを設定した状態で、収集処理を実行します。
   ```bash
   cd collector && export $(cat .env | xargs) && uv run python -m src.main
   ```
2. `articles/` フォルダに Markdown と `index.json` が生成されます。MP3 は GitHub Releases に保存されます。
3. フロントエンドを起動して確認します。
   ```bash
   cd frontend && pnpm dev
   ```

## 主な機能

- ニュース収集: Hacker News API と RSS から幅広く記事を集めます。
- AI要約: Google Gemini 2.5 Flash（無料枠）で要約。失敗時は Groq Llama にフォールバックします。
- 音声生成（TTS）: edge-tts（Microsoft Nanami）で日本語音声を作成します。
- 自動実行: GitHub Actions により毎朝 JST 7:00 ごろ（cron は遅延対策で前倒し設定）に自動更新されます。
- 通知: 取得完了時に Discord へ通知します（設定時）。

## よくある質問・トラブルシューティング

- Q: 記事が今日更新されていません。
  - A: 自動実行（GitHub Actions）の遅延や、ニュース元・APIの一時的な不調が考えられます。時間をおいて再度ご確認ください。
- Q: 音声が再生されません。
  - A: その記事にMP3が生成されていない場合があります。また、MP3はGitHub Releasesに置かれているため、ネットワーク状況により読み込みに時間がかかることがあります。
- Q: 自分で動かしたら要約が出ません。
  - A: APIキー（Gemini / Groq）の設定や無料枠の上限を確認してください。Geminiが上限に達するとGroqへ自動的に切り替わります。

## 開発者向けメモ（技術スタック/起動コマンド/ビルド/デプロイ先・本番URL）

- 構成:
  - `collector/` … Python（uv）。ニュース収集・要約・TTS。
  - `frontend/` … Next.js（pnpm）。記事一覧・音声プレイヤーのWeb UI。
  - `articles/` … 生成された Markdown と `index.json`。
  - `.github/workflows/collect.yml` … 毎朝の自動実行ワークフロー。
- 技術スタック:
  - 収集: Hacker News API + RSS
  - 要約: Google Gemini 2.5 Flash →（フォールバック）Groq Llama
  - TTS: edge-tts（Microsoft Nanami）
  - MP3保存: GitHub Releases
  - フロント: Next.js 16 / React 19 / Tailwind CSS / Vercel
  - CI: GitHub Actions
- 起動コマンド:
  - 収集: `cd collector && export $(cat .env | xargs) && uv run python -m src.main`
  - フロント開発: `cd frontend && pnpm dev`
  - フロントビルド: `cd frontend && pnpm build`
- 本番URL: https://ainews-eight-theta.vercel.app
- 状態: デプロイ済み・本番稼働中。
