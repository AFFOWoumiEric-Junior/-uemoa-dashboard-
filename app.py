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

# Critères de convergence de l'UEMOA (Pacte de 2015)
NORMES = {
    "Dette publique (% du PIB)": (70, "≤ 70 % (norme UEMOA)"),
    "Inflation (%)": (3, "≤ 3 % (norme UEMOA)"),
    "Recettes fiscales (% du PIB)": (20, "≥ 20 % (norme UEMOA)"),
}

st.set_page_config(page_title="Tableau de bord UEMOA", page_icon="📊", layout="wide")


@st.cache_data(ttl=3600)
def charger():
    return pd.read_csv(FICHIER)


if not FICHIER.exists():
    st.error("Les données n'ont pas encore été téléchargées. Lance d'abord fetch_data.py.")
    st.stop()

df = charger()
df = df.dropna(subset=["pays"])

# ---------- Barre latérale : les menus ----------
st.sidebar.header("Paramètres")
indicateur = st.sidebar.selectbox("Indicateur", sorted(df["indicateur"].unique()))
tous_pays = sorted(df["pays"].unique())
pays = st.sidebar.multiselect("Pays", tous_pays, default=tous_pays)
annee_min, annee_max = int(df["annee"].min()), int(df["annee"].max())
periode = st.sidebar.slider("Période", annee_min, annee_max, (annee_min, annee_max))

data = df[
    (df["indicateur"] == indicateur)
    & (df["pays"].isin(pays))
    & (df["annee"].between(*periode))
]

# ---------- En-tête ----------
st.title("📊 Tableau de bord macroéconomique de l'UEMOA")
st.caption(
    f"Source : {', '.join(data['source'].unique()) if not data.empty else '—'} · "
    f"Données de {annee_min} à {annee_max} · Mise à jour automatique chaque mois"
)

if data.empty:
    st.warning("Aucune donnée pour cette sélection.")
    st.stop()

# ---------- Chiffres clés : dernière valeur connue par pays ----------
st.subheader(f"{indicateur} : dernière valeur connue")
derniere = data.sort_values("annee").groupby("pays").tail(1).sort_values("pays")
colonnes = st.columns(4)
for i, (_, ligne) in enumerate(derniere.iterrows()):
    colonnes[i % 4].metric(f"{ligne['pays']} ({ligne['annee']})", f"{ligne['valeur']:.1f}")

norme = NORMES.get(indicateur)

# ---------- Graphique 1 : évolution dans le temps ----------
st.subheader("Évolution dans le temps")
fig = px.line(
    data, x="annee", y="valeur", color="pays", markers=True,
    labels={"annee": "Année", "valeur": indicateur, "pays": "Pays"},
)
if norme:
    fig.add_hline(y=norme[0], line_dash="dash", line_color="red",
                  annotation_text=norme[1], annotation_position="top left")
fig.update_layout(hovermode="x unified", legend_title_text="")
st.plotly_chart(fig, width="stretch")

# ---------- Graphique 2 : comparaison entre pays ----------
st.subheader("Comparaison entre pays (dernière année disponible)")
fig2 = px.bar(
    derniere.sort_values("valeur"), x="valeur", y="pays", orientation="h",
    text="valeur", labels={"valeur": indicateur, "pays": ""},
)
fig2.update_traces(texttemplate="%{text:.1f}", textposition="outside")
if norme:
    fig2.add_vline(x=norme[0], line_dash="dash", line_color="red",
                   annotation_text=norme[1])
st.plotly_chart(fig2, width="stretch")

# ---------- Tableau des données + téléchargement ----------
with st.expander("Voir les données"):
    tableau = data.pivot_table(index="annee", columns="pays", values="valeur").round(1)
    st.dataframe(tableau, width="stretch")
    st.download_button(
        "Télécharger en CSV", data.to_csv(index=False).encode("utf-8"),
        file_name=f"uemoa_{indicateur[:20]}.csv", mime="text/csv",
    )
