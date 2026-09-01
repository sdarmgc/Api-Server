"""
Reference/mock implementation of the translation socket backend --
TRANSLATION_BACKEND_HOST/_PORT in app/config.py (localhost:9998 by
default).

Run standalone:
    python -m scripts.mock_translate_backend

**This is a placeholder only.** The real translation backend is being
provided separately -- once it's deployed, point
TRANSLATION_BACKEND_HOST/_PORT at it and this script (and its
docker-compose service, if still present) can be removed. Included here so
local dev and the test suite have something to talk to in the meantime.

Wire protocol: newline-delimited JSON, one request per connection -- see
app/services/socket_client.py. Request/response use exactly the same JSON
structure as POST /api/translate's own HTTP contract:
    in  -> {"source_text": [...], "source_lang": ..., "target_lang": ...,
            "option": ...}
    out -> {"source_text": [...], "target_text": [...], "source_lang": ...,
            "target_lang": ..., "option": ...}

Translation logic here is the same "[<target_lang>] <text>" placeholder as
the in-process "mock" backend (app/services/translation_service.py).
"""
import asyncio
import logging

from scripts._socket_server_utils import serve

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")

HOST = "0.0.0.0"
PORT = 9998


def handle(payload: dict) -> dict:
    source_text = payload["source_text"]
    source_lang = payload["source_lang"]
    target_lang = payload["target_lang"]
    option = payload.get("option", 0)
    return {
        "source_text": source_text,
        "target_text": [f"[{target_lang}] {t}" for t in source_text],
        "source_lang": source_lang,
        "target_lang": target_lang,
        "option": option,
    }


async def _main():
    server = await serve("translate", handle, HOST, PORT)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(_main())
