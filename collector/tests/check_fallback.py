"""Offline checks for headline and Workers AI fallbacks."""
import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
from src.search import NewsItem
from src.summarize import MAX_HIGHLIGHTS, build_fallback_digest, _try_workers_ai

items = [NewsItem(f"Title {i}", f"https://example.com/{i}", "A" if i < 15 else "B", "<b>News</b> &amp; more") for i in range(30)]
digest = build_fallback_digest(items, [{"source_url": items[0].url}])
assert digest["fallback"] is True
assert len(digest["highlights"]) <= MAX_HIGHLIGHTS
assert items[0].url not in [h["source_url"] for h in digest["highlights"]]
assert [h["source_title"] for h in digest["highlights"][:20]] == ["A", "B"] * 10
assert all(h["title"] and h["source_url"] for h in digest["highlights"])
assert digest["highlights"][0]["summary"] == "News & more"

async def check_workers():
    original_client = httpx.AsyncClient
    def client_for(status):
        def handler(request):
            assert request.headers["authorization"] == "Bearer test-token"
            payload = {"success": True, "errors": [], "result": {"choices": [{"message": {"content": '{"highlights":[{"title":"line\nfeed"}]}'}}], "usage": {}}}
            return httpx.Response(status, json=payload)
        return lambda **kwargs: original_client(transport=httpx.MockTransport(handler), **kwargs)
    with patch.dict(os.environ, {"CLOUDFLARE_AI_TOKEN": "test-token", "CLOUDFLARE_ACCOUNT_ID": "test-account"}):
        with patch("src.summarize.httpx.AsyncClient", client_for(200)):
            result = await _try_workers_ai("prompt")
            assert result == {"highlights": [{"title": "line\nfeed"}]}
        with patch("src.summarize.httpx.AsyncClient", client_for(500)):
            assert await _try_workers_ai("prompt") is None
    with patch.dict(os.environ, {"CLOUDFLARE_AI_TOKEN": "", "CLOUDFLARE_ACCOUNT_ID": ""}):
        assert await _try_workers_ai("prompt") is None

asyncio.run(check_workers())
print("Fallback checks passed")
