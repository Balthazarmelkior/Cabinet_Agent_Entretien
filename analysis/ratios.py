# analysis/ratios.py
from dataclasses import dataclass
from typing import Optional
from models import DonneesFinancieres


class ZeroRevenueError(ValueError):
    """Raised when chiffre d'affaires is zero, making ratio analysis impossible."""


@dataclass
class Ratios:
    # Rentabilité
    taux_marge_brute: float
    taux_ebe: float
    taux_resultat_net: float
    rentabilite_capitaux: Optional[float]  # None when capitaux_propres == 0

    # Liquidité & solvabilité
    ratio_liquidite_generale: float
    couverture_dettes: float
    autonomie_financiere: float

    # Activité
    delai_clients_jours: float
    delai_fournisseurs_jours: float
    rotation_stocks_jours: float

    # Variations N vs N-1
    variation_ca_pct: Optional[float]
    variation_resultat_pct: Optional[float]


def compute_ratios(d: DonneesFinancieres) -> Ratios:
    ca = d.chiffre_affaires.montant_n
    if not ca:
        raise ZeroRevenueError(
            "Chiffre d'affaires nul ou manquant : l'analyse des ratios est impossible."
        )

    achats       = d.achats_consommes.montant_n
    charges_ext  = d.charges_externes.montant_n
    charges_pers = d.charges_personnel.montant_n
    ebe          = d.ebe.montant_n
    rn           = d.resultat_net.montant_n
    cp           = d.capitaux_propres.montant_n
    dettes_fin   = d.dettes_financieres.montant_n
    dettes_fourn = d.dettes_fournisseurs.montant_n
    clients      = d.creances_clients.montant_n
    stocks       = d.stocks.montant_n
    tresorerie   = d.tresorerie_actif.montant_n

    total_passif    = (cp + dettes_fin + dettes_fourn) or 1
    dettes_ct       = dettes_fourn or 1
    actif_circulant = stocks + clients + tresorerie

    return Ratios(
        taux_marge_brute         = round((ca - achats) / ca * 100, 1),
        taux_ebe                 = round(ebe / ca * 100, 1),
        taux_resultat_net        = round(rn / ca * 100, 1),
        rentabilite_capitaux     = round(rn / cp * 100, 1) if cp else None,
        ratio_liquidite_generale = round(actif_circulant / dettes_ct, 2),
        couverture_dettes        = round(dettes_fin / ebe, 1) if ebe > 0 else 99.0,
        autonomie_financiere     = round(cp / total_passif * 100, 1),
        delai_clients_jours      = round(clients / ca * 365, 0),
        delai_fournisseurs_jours = round(dettes_fourn / achats * 365, 0) if achats > 0 else 0.0,
        rotation_stocks_jours    = round(stocks / achats * 365, 0) if achats > 0 else 0.0,
        variation_ca_pct         = d.chiffre_affaires.variation_pct,
        variation_resultat_pct   = d.resultat_net.variation_pct,
    )
