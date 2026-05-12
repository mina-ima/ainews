"""edge-tts を使ったMP3音声生成

長文だと edge-tts のストリーミングセッションが途中で切れて生成が不完全になる
問題があったため、テキストを段落単位で分割して逐次合成し、MP3バイナリを連結する方式に変更。
"""

from __future__ import annotations

import asyncio

import edge_tts

VOICE = "ja-JP-NanamiNeural"  # Microsoft 日本語女性音声（高品質）
MAX_CHUNK_CHARS = 1500
MAX_RETRIES = 3


def _split_text(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    """段落（空行区切り）単位に分割し、累積文字数が max_chars を超えない単位で結合"""
    paragraphs = [p for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""
    for p in paragraphs:
        if not current:
            current = p
        elif len(current) + 2 + len(p) <= max_chars:
            current = f"{current}\n\n{p}"
        else:
            chunks.append(current)
            current = p
    if current:
        chunks.append(current)
    return chunks


async def _synthesize_chunk(text: str) -> bytes:
    """1チャンクを合成しMP3バイナリを返す。失敗時は指数バックオフで最大MAX_RETRIES回リトライ"""
    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            communicate = edge_tts.Communicate(text, VOICE, rate="+10%")
            buf = bytearray()
            async for msg in communicate.stream():
                if msg["type"] == "audio":
                    buf.extend(msg["data"])
            if not buf:
                raise RuntimeError("audioデータが空")
            return bytes(buf)
        except Exception as e:
            last_err = e
            wait = 2 ** attempt
            print(f"  TTS合成失敗 (試行{attempt+1}/{MAX_RETRIES}): {e}; {wait}秒後に再試行")
            await asyncio.sleep(wait)
    raise RuntimeError(f"TTS合成が{MAX_RETRIES}回失敗: {last_err}")


async def generate_mp3(text: str, output_path: str) -> None:
    """テキストからMP3音声ファイルを生成。長文はチャンク分割して連結する"""
    chunks = _split_text(text)
    print(f"  TTSチャンク数: {len(chunks)}件 (総文字数: {len(text)})")
    with open(output_path, "wb") as out:
        for i, chunk in enumerate(chunks, 1):
            audio = await _synthesize_chunk(chunk)
            out.write(audio)
            print(f"  チャンク {i}/{len(chunks)}: {len(chunk)}文字 → {len(audio)/1024:.1f}KB")
