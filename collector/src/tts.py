"""edge-tts を使ったMP3音声生成"""

from __future__ import annotations

import edge_tts

VOICE = "ja-JP-NanamiNeural"  # Microsoft 日本語女性音声（高品質）


async def generate_mp3(text: str, output_path: str) -> None:
    """テキストからMP3音声ファイルを生成"""
    communicate = edge_tts.Communicate(text, VOICE, rate="+10%")
    await communicate.save(output_path)
