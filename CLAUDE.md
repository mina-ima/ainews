# Technology Daily Report

毎朝AI・先端技術・製造業界の幅広いニュースを自動収集・要約し、md + MP3を生成するシステム。
展示会を毎日巡回するように、AI以外の技術ブレイクスルーやPCB/電子実装業界の動向も網羅する。

## 構成

- `collector/` - Python (uv): ニュース収集・要約・TTS
- `frontend/` - Next.js (pnpm): Web UI (記事一覧・音声プレイヤー)
- `articles/` - 生成されたmd + index.json
- `.github/workflows/collect.yml` - 毎朝JST 7:00自動実行

## 技術スタック

- ニュース収集: Hacker News API + RSS
- AI要約: Google Gemini 2.5 Flash (無料枠) → Groq Llama (フォールバック)
- TTS: edge-tts (Microsoft Nanami)
- MP3保存: GitHub Releases
- フロント: Next.js + Vercel
- CI: GitHub Actions

## コマンド

```bash
# ローカル実行
cd collector && export $(cat .env | xargs) && uv run python -m src.main

# フロントエンド開発
cd frontend && pnpm dev
```

## 環境変数 (collector/.env)

- `GEMINI_KEY_*` - Google Gemini APIキー（複数可）
- `GROQ_API_KEY` - Groq APIキー（フォールバック）
