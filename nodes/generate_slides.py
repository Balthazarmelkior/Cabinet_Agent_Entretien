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


async def _generate_gamma(contenu: str) -> dict:
    api_key = os.getenv("GAMMA_API_KEY", "")
    if not api_key:
        return {"url": None, "slides_count": 0}

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            "https://api.gamma.app/presentations/generate",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "content": contenu,
                "theme": "cabinet",
                "slides_count": 10,
                "format": "markdown",
            },
        )
        response.raise_for_status()
        data = response.json()

    return {"url": data.get("url", ""), "slides_count": data.get("count", 10)}


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
