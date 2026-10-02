"""
LA VITRINE
----------
Ce programme fabrique la page web du tableau de bord à partir du
fichier data/uemoa.csv rempli par le coursier (fetch_data.py).
"""

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

FICHIER = Path(__file__).parent / "data" / "uemoa.csv"

# Critères de convergence de l'UEMOA (Pacte de 2015), affichés en repère
NORMES = {
    "Dette publique (% du PIB)": (70, "Norme UEMOA ≤ 70 %"),
    "Inflation (%)": (3, "Norme UEMOA ≤ 3 %"),
    "Recettes fiscales (% du PIB)": (20, "Norme UEMOA ≥ 20 %"),
}

st.set_page_config(page_title="Pays en développement", page_icon="🌍", layout="wide")


@st.cache_data(ttl=3600)
def charger():
    df = pd.read_csv(FICHIER)
    return df.dropna(subset=["pays"])


if not FICHIER.exists():
    st.error("Les données n'ont pas encore été téléchargées. Lance d'abord le coursier (onglet Actions de GitHub).")
    st.stop()

df = charger()

if "region" not in df.columns:
    st.info("Les données sont en cours de mise à jour vers la nouvelle version. "
            "Relance le coursier dans l'onglet Actions de GitHub, puis recharge cette page.")
    st.stop()

# ---------- Barre latérale : les menus ----------
st.sidebar.header("Paramètres")
indicateur = st.sidebar.selectbox("Indicateur", sorted(df["indicateur"].unique()))

zones = ["UEMOA", "Tous les pays en développement"] + sorted(df["region"].unique())
zone = st.sidebar.selectbox("Zone", zones)

revenus = sorted(df["revenu"].unique())
revenu = st.sidebar.multiselect("Niveau de revenu", revenus, default=revenus)

annee_min, annee_max = int(df["annee"].min()), int(df["annee"].max())
periode = st.sidebar.slider("Période", annee_min, annee_max, (2010, annee_max))

# Pays de la zone choisie
groupe = df[(df["indicateur"] == indicateur) & (df["revenu"].isin(revenu))]
if zone == "UEMOA":
    groupe = groupe[groupe["uemoa"]]
elif zone != "Tous les pays en développement":
    groupe = groupe[groupe["region"] == zone]
groupe = groupe[groupe["annee"].between(*periode)]

pays_zone = sorted(groupe["pays"].unique())
defaut = pays_zone if len(pays_zone) <= 8 else []
pays_courbe = st.sidebar.multiselect(
    "Pays à suivre sur la courbe", pays_zone, default=defaut,
    help="Choisis quelques pays à comparer dans le temps. La médiane de la zone s'affiche toujours.",
)

# ---------- En-tête ----------
st.title("🌍 Tableau de bord des pays en développement")
st.caption(
    f"{zone} · {indicateur} · Sources : Banque mondiale (WDI) et FMI (WEO) · "
    "Mise à jour automatique chaque mois"
)

if groupe.empty:
    st.warning("Aucune donnée pour cette sélection.")
    st.stop()

# Dernière valeur connue de chaque pays
derniere = groupe.sort_values("annee").groupby("pays").tail(1)
norme = NORMES.get(indicateur)

# ---------- Chiffres clés ----------
c1, c2, c3, c4 = st.columns(4)
c1.metric("Pays avec données", f"{derniere['pays'].nunique()}")
c2.metric("Médiane de la zone", f"{derniere['valeur'].median():.1f}")
mini = derniere.loc[derniere["valeur"].idxmin()]
maxi = derniere.loc[derniere["valeur"].idxmax()]
c3.metric("Plus bas", f"{mini['valeur']:.1f}", mini["pays"], delta_color="off")
c4.metric("Plus haut", f"{maxi['valeur']:.1f}", maxi["pays"], delta_color="off")

# ---------- Carte ----------
st.subheader("Carte (dernière année disponible pour chaque pays)")
carte = px.choropleth(
    derniere, locations="code_pays", color="valeur", hover_name="pays",
    hover_data={"annee": True, "code_pays": False, "valeur": ":.1f"},
    color_continuous_scale="Viridis", labels={"valeur": "", "annee": "Année"},
)
carte.update_geos(fitbounds="locations", visible=False, showcountries=True)
carte.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=420)
st.plotly_chart(carte, width="stretch")

# ---------- Évolution dans le temps ----------
st.subheader("Évolution dans le temps")
mediane = groupe.groupby("annee", as_index=False)["valeur"].median()
mediane["pays"] = f"Médiane {zone}"
courbe = pd.concat([groupe[groupe["pays"].isin(pays_courbe)], mediane])
fig = px.line(
    courbe, x="annee", y="valeur", color="pays", markers=True,
    labels={"annee": "Année", "valeur": indicateur, "pays": ""},
)
fig.for_each_trace(
    lambda t: t.update(line=dict(dash="dot", width=4, color="grey"))
    if t.name.startswith("Médiane") else None
)
if norme:
    fig.add_hline(y=norme[0], line_dash="dash", line_color="red",
                  annotation_text=norme[1], annotation_position="top left")
fig.update_layout(hovermode="x unified")
st.plotly_chart(fig, width="stretch")
if not pays_courbe:
    st.caption("Ajoute des pays dans le menu « Pays à suivre » pour les voir sur la courbe.")

# ---------- Classement ----------
st.subheader("Classement des pays (dernière année disponible)")
classement = derniere.sort_values("valeur")
classement["suivi"] = classement["pays"].isin(pays_courbe).map({True: "Pays suivis", False: "Autres"})
fig2 = px.bar(
    classement, x="valeur", y="pays", orientation="h", color="suivi",
    color_discrete_map={"Pays suivis": "#E4572E", "Autres": "#4C78A8"},
    hover_data={"annee": True, "suivi": False},
    labels={"valeur": indicateur, "pays": "", "annee": "Année"},
)
if norme:
    fig2.add_vline(x=norme[0], line_dash="dash", line_color="red", annotation_text=norme[1])
fig2.update_layout(height=max(350, 18 * len(classement)), showlegend=False,
                   yaxis=dict(categoryorder="array", categoryarray=classement["pays"].tolist()))
st.plotly_chart(fig2, width="stretch")

# ---------- Tableau des données + téléchargement ----------
with st.expander("Voir les données"):
    tableau = groupe.pivot_table(index="pays", columns="annee", values="valeur").round(1)
    st.dataframe(tableau, width="stretch")
    st.download_button(
        "Télécharger en CSV", groupe.to_csv(index=False).encode("utf-8"),
        file_name="donnees_selection.csv", mime="text/csv",
    )
