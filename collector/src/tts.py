"""MP3音声生成（edge-tts / VOICEVOX の2エンジン）

2エンジンは主従ではなく日替わりで先行を入れ替える。先行が成功したら後攻は実行しない。
どちらか一方の障害（2026-10 の edge-tts 停止など）で音声が丸ごと欠けるのを防ぐ。

長文だと edge-tts のストリーミングセッションが途中で切れて生成が不完全になる
問題があったため、テキストを段落単位で分割して逐次合成し、MP3バイナリを連結する方式に変更。
"""

from __future__ import annotations

import asyncio
import io
import os
import subprocess
import time
import wave
from datetime import date as Date

import edge_tts
import httpx

VOICE = "ja-JP-NanamiNeural"  # Microsoft 日本語女性音声（高品質）
MAX_CHUNK_CHARS = 1500
MAX_RETRIES = 3

VOICEVOX_URL = os.environ.get("VOICEVOX_URL", "http://localhost:50021")
VOICEVOX_SPEAKER = 2  # 四国めたん ノーマル
EDGE_CREDIT = "Microsoft Edge TTS (Nanami)"
VOICEVOX_CREDIT = "VOICEVOX:四国めたん"  # VOICEVOX 利用規約でクレジット表記が必須


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


async def _edge_tts(chunks: list[str]) -> bytes:
    return b"".join([await _synthesize_chunk(c) for c in chunks])


def _voicevox(chunks: list[str]) -> bytes:
    """VOICEVOX エンジン(HTTP)で合成し、WAV を連結して ffmpeg で MP3 にする"""
    with httpx.Client(base_url=VOICEVOX_URL, timeout=300) as client:
        # Actions では収集と並行してコンテナを起動しているので、起動完了を待つ
        deadline = time.monotonic() + 180
        while True:
            try:
                client.get("/version").raise_for_status()
                break
            except httpx.HTTPError:
                if time.monotonic() > deadline:
                    raise
                time.sleep(3)
        frames, params = [], None
        for chunk in chunks:
            sp = {"speaker": VOICEVOX_SPEAKER}
            q = client.post("/audio_query", params={**sp, "text": chunk})
            q.raise_for_status()
            query = q.json() | {"speedScale": 1.1}  # edge-tts の rate=+10% に合わせる
            r = client.post("/synthesis", params=sp, json=query)
            r.raise_for_status()
            with wave.open(io.BytesIO(r.content)) as w:
                params = params or w.getparams()
                frames.append(w.readframes(w.getnframes()))
    pcm = b"".join(frames)
    return subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-f", "s16le", "-ar", str(params.framerate),
         "-ac", str(params.nchannels), "-i", "-", "-b:a", "48k", "-f", "mp3", "-"],
        input=pcm, capture_output=True, check=True,
    ).stdout


async def generate_mp3(text: str, output_path: str, date: str) -> str:
    """テキストからMP3音声ファイルを生成し、使ったエンジンのクレジットを返す。

    日付の偶奇で先行エンジンを入れ替え、先行が失敗したときだけ後攻を試す。
    """
    chunks = _split_text(text)
    print(f"  TTSチャンク数: {len(chunks)}件 (総文字数: {len(text)})")
    engines = [
        ("edge-tts", EDGE_CREDIT, lambda: _edge_tts(chunks)),
        # VOICEVOX はチャンク長に比例してメモリを食う(400字で2.7GB、1400字でOOM)ので文単位で細かく分ける
        ("VOICEVOX", VOICEVOX_CREDIT,
         lambda: asyncio.to_thread(_voicevox, _split_text(text.replace("。", "。\n\n"), 200))),
    ]
    if Date.fromisoformat(date).toordinal() % 2:
        engines.reverse()
    errors = []
    for name, credit, synth in engines:
        print(f"  TTSエンジン: {name}")
        try:
            audio = await synth()
            if not audio:
                raise RuntimeError("audioデータが空")
        except Exception as e:
            print(f"  {name} 失敗: {e}")
            errors.append(f"{name}: {e}")
            continue
        with open(output_path, "wb") as out:
            out.write(audio)
        return credit
    raise RuntimeError(" / ".join(errors))
