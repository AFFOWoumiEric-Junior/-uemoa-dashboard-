"""
LE COURSIER
-----------
Ce programme va chercher les chiffres sur Internet et les range dans
le fichier data/uemoa.csv. Il est relancé automatiquement chaque mois.

Pays couverts : tous les pays en développement, c'est-à-dire les pays
à revenu faible, intermédiaire inférieur et intermédiaire supérieur
selon la classification de la Banque mondiale (environ 135 pays).

Sources (gratuites, sans inscription) :
- Banque mondiale (WDI) : croissance, inflation, recettes fiscales
- FMI (World Economic Outlook) : dette publique
"""

import datetime
from pathlib import Path

import pandas as pd
import requests

# Groupes de revenu retenus (codes Banque mondiale)
# LIC = faible, LMC = intermédiaire inférieur, UMC = intermédiaire supérieur
GROUPES_REVENU = {"LIC", "LMC", "UMC"}

# Les 8 pays de l'UEMOA, pour pouvoir les repérer dans le tableau de bord
UEMOA = {"BEN", "BFA", "CIV", "GNB", "MLI", "NER", "SEN", "TGO"}

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


def liste_pays_en_developpement():
    """Demande à la Banque mondiale la liste des pays et garde les pays en développement."""
    url = "https://api.worldbank.org/v2/fr/country"  # /fr/ = noms en français
    reponse = requests.get(url, params={"format": "json", "per_page": 500}, timeout=60)
    reponse.raise_for_status()
    pays = {}
    for p in reponse.json()[1]:
        if p["incomeLevel"]["id"] in GROUPES_REVENU:
            pays[p["id"]] = {
                "pays": p["name"],
                "region": p["region"]["value"].strip(),
                "revenu": p["incomeLevel"]["value"].strip(),
            }
    return pays


def telecharger_banque_mondiale(code, nom, pays):
    """Récupère un indicateur pour tous les pays, puis garde les pays en développement."""
    url = f"https://api.worldbank.org/v2/country/all/indicator/{code}"
    params = {"format": "json", "per_page": 20000, "date": f"{ANNEE_DEBUT}:{ANNEE_FIN}"}
    reponse = requests.get(url, params=params, timeout=120)
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
        if l["value"] is not None and l["countryiso3code"] in pays
    ]


def telecharger_fmi(code, nom, pays):
    """Récupère un indicateur pour tous les pays auprès du FMI, puis filtre."""
    url = f"https://www.imf.org/external/datamapper/api/v1/{code}"
    reponse = requests.get(url, timeout=120)
    reponse.raise_for_status()
    donnees = reponse.json().get("values", {}).get(code, {})
    resultat = []
    for code_pays, series in donnees.items():
        if code_pays not in pays:
            continue
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
    print("Liste des pays en développement…")
    pays = liste_pays_en_developpement()
    print(f"{len(pays)} pays retenus")

    lignes = []
    for code, nom in INDICATEURS_BM.items():
        print(f"Téléchargement : {nom}")
        lignes += telecharger_banque_mondiale(code, nom, pays)
    for code, nom in INDICATEURS_FMI.items():
        print(f"Téléchargement : {nom}")
        lignes += telecharger_fmi(code, nom, pays)

    df = pd.DataFrame(lignes)

    # Contrôle de sécurité : si un téléchargement a échoué en silence,
    # on s'arrête plutôt que d'écraser les bonnes données par des données vides.
    attendus = len(INDICATEURS_BM) + len(INDICATEURS_FMI)
    if len(pays) < 100 or df.empty or df["indicateur"].nunique() < attendus:
        raise SystemExit("Données incomplètes : mise à jour annulée.")

    infos = pd.DataFrame.from_dict(pays, orient="index").rename_axis("code_pays").reset_index()
    df = df.merge(infos, on="code_pays", how="inner")
    df["uemoa"] = df["code_pays"].isin(UEMOA)
    df["valeur"] = df["valeur"].round(2)
    df = df.sort_values(["indicateur", "pays", "annee"])
    df = df[["pays", "code_pays", "region", "revenu", "uemoa",
             "annee", "indicateur", "valeur", "source"]]

    FICHIER.parent.mkdir(exist_ok=True)
    df.to_csv(FICHIER, index=False)
    print(f"{len(df)} lignes enregistrées pour {df['code_pays'].nunique()} pays dans {FICHIER}")


if __name__ == "__main__":
    main()
