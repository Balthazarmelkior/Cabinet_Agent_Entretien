import logging

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

GAMMA_BASE_URL = "https://public-api.gamma.app/v1.0"
POLL_INTERVAL = 5  # seconds
MAX_POLLS = 40  # 40 * 5s = 200s max


class GammaResult(BaseModel):
    url: str
    slides_count: int = 10


class GammaClient:
    """
    Generates a 10-slide presentation via the Gamma API v1.0.
    Receives structured Markdown content and returns the presentation URL.
    """

    async def generate(self, contenu: str, theme: str = "cabinet") -> GammaResult:
        import asyncio

        from rdv_bilan_ia.app.config import settings

        if not settings.GAMMA_API_KEY:
            logger.warning("GAMMA_API_KEY not set — returning stub presentation URL")
            return GammaResult(
                url="https://gamma.app/stub-presentation",
                slides_count=0,
            )

        headers = {
            "X-API-KEY": settings.GAMMA_API_KEY,
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            # 1. Launch generation
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

            # 2. Poll until complete
            gamma_url = ""
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

        return GammaResult(
            url=gamma_url,
            slides_count=10,
        )


gamma_client = GammaClient()
