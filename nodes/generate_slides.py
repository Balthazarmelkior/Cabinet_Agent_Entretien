# nodes/generate_slides.py
import asyncio
import logging
import os

import httpx

logger = logging.getLogger(__name__)


def _fmt(v: float) -> str:
    return f"{v:,.0f} €".replace(",", "\u202f")


def _build_slide_content(state: dict) -> str:
    donnees = state.get("donnees_financieres")
    ratios = state.get("ratios")
    note = state.get("note_sectorielle", "")
    benchmark = state.get("benchmark")
    signaux = state.get("signaux_detectes", [])
    fiche = state.get("fiche_entretien")

    lines = ["# Préparation Rendez-vous Bilan", ""]

    # Slide 1-2: Synthèse exécutive
    if fiche:
        lines += [
            "## Synthèse Exécutive",
            fiche.synthese_executive,
            "",
        ]

    # Slide 3: Chiffres clés
    if donnees:
        lines += [
            "## Chiffres Clés",
            f"- **Chiffre d'affaires** : {_fmt(donnees.chiffre_affaires.montant_n)}",
        ]
        if donnees.chiffre_affaires.variation_pct is not None:
            lines[-1] += f" ({donnees.chiffre_affaires.variation_pct:+.1f}% vs N-1)"
        lines += [
            f"- **EBE** : {_fmt(donnees.ebe.montant_n)} ({ratios.taux_ebe:.1f}% du CA)" if ratios else f"- **EBE** : {_fmt(donnees.ebe.montant_n)}",
            f"- **Résultat net** : {_fmt(donnees.resultat_net.montant_n)}",
            f"- **Trésorerie** : {_fmt(donnees.tresorerie_actif.montant_n)}",
            "",
        ]

    # Slide 4: Analyse de trésorerie
    if ratios:
        lines += [
            "## Analyse de Trésorerie",
            f"- **BFR** : {_fmt(ratios.bfr)}",
            f"- **FRNG** : {_fmt(ratios.frng)}",
            f"- **Trésorerie nette** : {_fmt(ratios.tresorerie_nette)} ({ratios.tresorerie_nette_jours_ca:.0f} jours de CA)",
            f"- **Cycle de conversion** : {ratios.cycle_conversion_jours:.0f} jours (clients {ratios.delai_clients_jours:.0f}j + stocks {ratios.rotation_stocks_jours:.0f}j - fournisseurs {ratios.delai_fournisseurs_jours:.0f}j)",
            "",
        ]

    # Slide 5: Contexte sectoriel
    if note:
        lines += [
            "## Contexte Sectoriel",
            note[:2000],
            "",
        ]

    # Slide 5b: SWOT sectoriel
    swot = state.get("swot", {})
    if swot and any(swot.get(k) for k in ("forces", "faiblesses", "opportunites", "menaces")):
        lines += ["## Analyse SWOT Sectorielle", ""]
        for label, key in [("Forces", "forces"), ("Faiblesses", "faiblesses"),
                           ("Opportunités", "opportunites"), ("Menaces", "menaces")]:
            items = swot.get(key, [])
            if items:
                lines.append(f"**{label} :**")
                for item in items:
                    lines.append(f"- {item}")
                lines.append("")

    # Slide 6: Benchmark
    if benchmark:
        lines += [
            "## Positionnement Sectoriel",
            f"**{benchmark.libelle_secteur}** — Référence {benchmark.annee_reference}",
            "",
        ]
        for r in benchmark.ratios[:7]:
            med = f"{r.mediane_secteur:.1f}" if r.mediane_secteur else "—"
            ecart = f" ({r.ecart_mediane_pct:+.1f}%)" if r.ecart_mediane_pct else ""
            lines.append(f"- {r.libelle} : **{r.valeur_client:.1f}** vs secteur {med}{ecart} — {r.interpretation}")
        lines += ["", f"*{benchmark.commentaire_global}*", ""]

    # Slide 7: Signaux
    if signaux:
        risques = [s for s in signaux if s.type in ("risque",)]
        opportunites = [s for s in signaux if s.type in ("opportunite", "optimisation")]
        if risques:
            lines += ["## Points de Vigilance", ""]
            for s in risques[:5]:
                lines.append(f"- **{s.titre}** — {s.description}")
            lines.append("")
        if opportunites:
            lines += ["## Opportunités", ""]
            for s in opportunites[:5]:
                lines.append(f"- **{s.titre}** — {s.description}")
            lines.append("")

    # Slide 8-9: Plan d'entretien
    if fiche and fiche.plan_entretien:
        lines += ["## Plan d'Entretien", ""]
        for pt in fiche.plan_entretien:
            lines.append(f"### {pt.ordre}. {pt.theme}")
            lines.append(f"{pt.contexte_chiffre}")
            lines.append(f"*{pt.question_ouverte}*")
            if pt.mission_associee:
                lines.append(f"→ Mission : {pt.mission_associee}")
            lines.append("")

    # Slide 10: Missions recommandées
    if fiche and fiche.missions_a_proposer:
        lines += ["## Missions Recommandées", ""]
        for m in fiche.missions_a_proposer:
            titre = m.get("titre", "")
            urgence = m.get("urgence", "")
            benefice = m.get("benefice_attendu", "")
            lines.append(f"- **{titre}** [{urgence}] — {benefice}")
        lines.append("")

    # Points de vigilance
    if fiche and fiche.points_vigilance:
        lines += ["## Points de Vigilance", ""]
        for p in fiche.points_vigilance:
            lines.append(f"- {p}")
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
