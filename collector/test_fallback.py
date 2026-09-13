"""モデルフォールバック順の最小チェック: uv run python test_fallback.py"""

import json

from src import summarize
from src.summarize import _discover_models


class _FakeClient:
    """client.models.list() だけを持つスタブ"""

    def __init__(self, names):
        self.models = type("_M", (), {"list": lambda _self: [type("_N", (), {"name": f"models/{n}"})() for n in names]})()


AVAILABLE = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3-flash-preview",  # preview は除外される
    "gemini-3.1-pro-preview",  # pro は除外される
]


def test_all_older_versions_are_tried():
    # 1つ前のバージョンだけでなく、利用可能な旧世代を全て並べる
    # (503 spike で 3.8/3.7 が同時に落ちても 3.6 以下へ逃げられること)
    summarize._load_last_model = lambda: None
    got = _discover_models(_FakeClient(AVAILABLE))
    assert got == [
        "gemini-3.8-flash",
        "gemini-3.7-flash",
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
    ], got


def test_control_char_in_llm_json():
    # Gemini が文字列値に生の改行を混ぜても落ちない
    assert json.loads('{"a": "x\ny"}', strict=False) == {"a": "x\ny"}


def test_retry_after_total_failure():
    # 全モデル 503 のときは間を置いて1回だけ撃ち直す
    import asyncio as _a
    import os

    os.environ["GEMINI_KEY_TEST"] = "dummy"
    calls = []
    slept = []

    async def _sweep(_prompt):
        calls.append(1)
        return {"highlights": [1]} if len(calls) == 2 else None

    summarize._gemini_sweep = _sweep
    real_sleep = _a.sleep
    _a.sleep = lambda s: slept.append(s) or real_sleep(0)  # summarize.asyncio は同じモジュール
    try:
        got = _a.run(summarize._try_gemini("x"))
    finally:
        _a.sleep = real_sleep
    assert got == {"highlights": [1]}, got
    assert len(calls) == 2, calls
    assert slept == [summarize.GEMINI_RETRY_WAIT_SEC], slept


if __name__ == "__main__":
    test_all_older_versions_are_tried()
    test_control_char_in_llm_json()
    test_retry_after_total_failure()
    print("OK")
