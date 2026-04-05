import logging

from rdv_bilan_ia.app.core.storage.redis_client import job_queue
from rdv_bilan_ia.app.orchestrator.state import WorkflowState
from rdv_bilan_ia.app.services.gamma_client import gamma_client
from shared.slide_builder import build_slide_content

logger = logging.getLogger(__name__)


async def node_gamma(state: WorkflowState) -> dict:
    """Generate 10-slide presentation via Gamma API."""
    job_id = state.get("job_id", "unknown")

    try:
        await job_queue.set_state(
            job_id,
            {**state, "current_node": "gamma", "progress_pct": 70},
        )
    except Exception:
        pass

    contenu = build_slide_content(state)

    try:
        result = await gamma_client.generate(
            contenu=contenu,
            theme="cabinet",
        )
        slides_url = result.url
    except Exception:
        logger.exception("Gamma generation failed for job %s", job_id)
        slides_url = None

    livrables = state.get("livrables", {})
    livrables["slides_gamma_url"] = slides_url
    livrables["contenu_slides"] = contenu

    return {
        "contenu_slides": contenu,
        "livrables": livrables,
        "current_node": "gamma",
        "progress_pct": 80,
    }
