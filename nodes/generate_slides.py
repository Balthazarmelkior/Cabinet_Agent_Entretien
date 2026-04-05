# nodes/generate_slides.py
import asyncio
import logging
import os

import httpx

logger = logging.getLogger(__name__)


def _build_slide_content(state: dict) -> str:
    note = state.get("note_sectorielle", "")
    benchmark = state.get("benchmark")
    signaux = state.get("signaux_detectes", [])
    fiche = state.get("fiche_entretien")

    lines = [
        "# Préparation Rendez-vous Bilan",
        "",
        "## Contexte Sectoriel",
        note[:2000] if note else "_Analyse sectorielle non disponible_",
        "",
    ]

    if benchmark:
        lines += [
            "## Benchmark Sectoriel",
            f"**Secteur :** {benchmark.libelle_secteur}",
            f"**Année :** {benchmark.annee_reference}",
            "",
        ]
        for r in benchmark.ratios[:6]:
            med = f"{r.mediane_secteur:.1f}" if r.mediane_secteur else "—"
            lines.append(f"- {r.libelle} : client {r.valeur_client:.1f} vs secteur {med} ({r.interpretation})")
        lines.append("")

    if signaux:
        lines += ["## Signaux Détectés", ""]
        for s in signaux[:8]:
            icon = {"risque": "Risque", "opportunite": "Opportunité",
                    "optimisation": "Optimisation", "conformite": "Conformité"}.get(s.type, s.type)
            lines.append(f"- **[{icon}]** {s.titre} — {s.description}")
        lines.append("")

    if fiche:
        lines += ["## Plan d'Entretien", ""]
        for pt in fiche.plan_entretien:
            lines.append(f"### {pt.ordre}. {pt.theme}")
            lines.append(f"{pt.contexte_chiffre}")
            lines.append(f"*Question : {pt.question_ouverte}*")
            lines.append("")

        if fiche.missions_a_proposer:
            lines += ["## Missions Recommandées", ""]
            for m in fiche.missions_a_proposer:
                lines.append(f"- **{m.get('titre', '')}** — {m.get('benefice_attendu', '')}")
            lines.append("")

    return "\n".join(lines)


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

    import asyncio as _asyncio

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
        gamma_url = None
        for _ in range(MAX_POLLS):
            await _asyncio.sleep(POLL_INTERVAL)
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
    contenu = _build_slide_content(state)

    try:
        result = asyncio.run(_generate_gamma(contenu))
        slides_url = result["url"]
    except Exception:
        logger.exception("Gamma generation failed")
        slides_url = None

    return {
        "contenu_slides": contenu,
        "slides_url": slides_url,
    }
