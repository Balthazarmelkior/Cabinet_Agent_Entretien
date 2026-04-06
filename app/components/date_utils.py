# app/components/date_utils.py

MOIS_COURT = {
    "01": "Jan", "02": "Fév", "03": "Mar", "04": "Avr",
    "05": "Mai", "06": "Juin", "07": "Juil", "08": "Août",
    "09": "Sep", "10": "Oct", "11": "Nov", "12": "Déc",
}


def mois_labels(soldes: list) -> list[str]:
    """Convertit une liste de SoldeMensuel en labels de mois courts."""
    labels = []
    for s in soldes:
        mm = s.mois.split("-")[1]
        labels.append(MOIS_COURT.get(mm, mm))
    return labels
