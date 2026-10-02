"""
LE COURSIER
-----------
Ce programme va chercher les chiffres sur Internet et les range dans
le fichier data/uemoa.csv. Il est relancé automatiquement chaque mois.

Sources (gratuites, sans inscription) :
- Banque mondiale (WDI) : croissance, inflation, recettes fiscales
- FMI (World Economic Outlook) : dette publique
"""

import datetime
from pathlib import Path

import pandas as pd
import requests

# Les 8 pays de l'UEMOA (codes ISO à 3 lettres)
PAYS = {
    "BEN": "Bénin",
    "BFA": "Burkina Faso",
    "CIV": "Côte d'Ivoire",
    "GNB": "Guinée-Bissau",
    "MLI": "Mali",
    "NER": "Niger",
    "SEN": "Sénégal",
    "TGO": "Togo",
}

# Indicateurs Banque mondiale : code WDI -> nom lisible
INDICATEURS_BM = {
    "GC.TAX.TOTL.GD.ZS": "Recettes fiscales (% du PIB)",
    "NY.GDP.MKTP.KD.ZG": "Croissance du PIB réel (%)",
    "FP.CPI.TOTL.ZG": "Inflation (%)",
}

# Indicateur FMI : code WEO -> nom lisible
INDICATEURS_FMI = {
    "GGXWDG_NGDP": "Dette publique (% du PIB)",
}

ANNEE_DEBUT = 2000
ANNEE_FIN = datetime.date.today().year - 1  # on exclut les projections
FICHIER = Path(__file__).parent / "data" / "uemoa.csv"


def telecharger_banque_mondiale(code, nom):
    """Récupère un indicateur pour les 8 pays auprès de la Banque mondiale."""
    pays = ";".join(PAYS)
    url = f"https://api.worldbank.org/v2/country/{pays}/indicator/{code}"
    params = {"format": "json", "per_page": 5000, "date": f"{ANNEE_DEBUT}:{ANNEE_FIN}"}
    reponse = requests.get(url, params=params, timeout=60)
    reponse.raise_for_status()
    lignes = reponse.json()[1] or []
    return [
        {
            "code_pays": l["countryiso3code"],
            "annee": int(l["date"]),
            "indicateur": nom,
            "valeur": l["value"],
            "source": "Banque mondiale (WDI)",
        }
        for l in lignes
        if l["value"] is not None
    ]


def telecharger_fmi(code, nom):
    """Récupère un indicateur pour les 8 pays auprès du FMI."""
    url = f"https://www.imf.org/external/datamapper/api/v1/{code}/" + "/".join(PAYS)
    reponse = requests.get(url, timeout=60)
    reponse.raise_for_status()
    donnees = reponse.json().get("values", {}).get(code, {})
    resultat = []
    for code_pays, series in donnees.items():
        for annee, valeur in series.items():
            annee = int(annee)
            if ANNEE_DEBUT <= annee <= ANNEE_FIN and valeur is not None:
                resultat.append(
                    {
                        "code_pays": code_pays,
                        "annee": annee,
                        "indicateur": nom,
                        "valeur": valeur,
                        "source": "FMI (WEO)",
                    }
                )
    return resultat


def main():
    lignes = []
    for code, nom in INDICATEURS_BM.items():
        print(f"Téléchargement : {nom}")
        lignes += telecharger_banque_mondiale(code, nom)
    for code, nom in INDICATEURS_FMI.items():
        print(f"Téléchargement : {nom}")
        lignes += telecharger_fmi(code, nom)

    df = pd.DataFrame(lignes)

    # Contrôle de sécurité : si un téléchargement a échoué en silence,
    # on s'arrête plutôt que d'écraser les bonnes données par des données vides.
    attendus = len(INDICATEURS_BM) + len(INDICATEURS_FMI)
    if df.empty or df["indicateur"].nunique() < attendus:
        raise SystemExit("Données incomplètes : mise à jour annulée.")

    df["pays"] = df["code_pays"].map(PAYS)
    df["valeur"] = df["valeur"].round(2)
    df = df.sort_values(["indicateur", "pays", "annee"])
    df = df[["pays", "code_pays", "annee", "indicateur", "valeur", "source"]]

    FICHIER.parent.mkdir(exist_ok=True)
    df.to_csv(FICHIER, index=False)
    print(f"{len(df)} lignes enregistrées dans {FICHIER}")


if __name__ == "__main__":
    main()
