# nodes/generate_slides.py
import logging
import os

import httpx
from utils.async_helper import run_async
from shared.slide_builder import build_slide_content

logger = logging.getLogger(__name__)

GAMMA_BASE_URL = "https://public-api.gamma.app/v1.0"
POLL_INTERVAL = 5  # seconds
MAX_POLLS = 40  # 40 * 5s = 200s max


async def _generate_gamma(contenu: str) -> dict:
    api_key = os.getenv("GAMMA_API_KEY", "")
    if not api_key:
        return {"url": None, "slides_count": 0}

    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
    }

    import asyncio

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{GAMMA_BASE_URL}/generations",
            headers=headers,
            json={
                "inputText": contenu,
                "textMode": "condense",
                "format": "presentation",
                "numCards": 10,
            },
        )
        response.raise_for_status()
        data = response.json()

        generation_id = data["generationId"]

        gamma_url = None
        for _ in range(MAX_POLLS):
            await asyncio.sleep(POLL_INTERVAL)
            poll = await client.get(
                f"{GAMMA_BASE_URL}/generations/{generation_id}",
                headers=headers,
            )
            poll.raise_for_status()
            poll_data = poll.json()
            status = poll_data.get("status", "")
            gamma_url = poll_data.get("gammaUrl") or gamma_url
            if status in ("complete", "completed"):
                break

    return {"url": gamma_url, "slides_count": 10}


def generate_slides(state: dict) -> dict:
    contenu = build_slide_content(state)

    try:
        result = run_async(_generate_gamma(contenu))
        slides_url = result["url"]
    except Exception:
        logger.exception("Gamma generation failed")
        slides_url = None

    return {
        "contenu_slides": contenu,
        "slides_url": slides_url,
    }
