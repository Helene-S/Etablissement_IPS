import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import branca.colormap as cm
import pandas as pd
import os

import sys
import streamlit as st
import platform
import os

st.sidebar.title("Infos système")
st.sidebar.write("🧠 Python version:", sys.version)
st.sidebar.write("📦 Interpreter path:", sys.executable)
st.sidebar.write("🗂️ Current working directory:", os.getcwd())
st.sidebar.write("🖥️ Platform:", platform.platform())


# Charger le fond de carte
shp_file = os.path.join(os.path.dirname(__file__), '../ne_110m_admin_0_countries/ne_110m_admin_0_countries.shp')


@st.cache_data
def charger_fond_france(shp_path):
    world = gpd.read_file(shp_file)
    return world[world.NAME == "France"]

france = charger_fond_france(shp_file)

# Initialiser l'état de la carte
if 'map_center' not in st.session_state:
    st.session_state['map_center'] = [46.2276, 2.2137]  # Coordonnées du centre de la France
if 'zoom' not in st.session_state:
    st.session_state['zoom'] = 6  # Niveau de zoom initial

# Charger les données IPS
college_path =os.path.join(os.path.dirname(__file__), '../fr-en-ips-colleges-ap2022.parquet')
lycee_path =os.path.join(os.path.dirname(__file__), '../fr-en-ips-lycees-ap2022.parquet')

@st.cache_resource
def charger_donnees_ips():
    df_ips_college = pd.read_parquet(college_path)
    df_ips_lycee = pd.read_parquet(lycee_path)
    
    df_ips_college['type'] = 'collège'
    df_ips_lycee['type'] = 'lycée'
    df_ips_lycee['ips'] = df_ips_lycee['ips_voie_gt']

    return pd.concat([df_ips_college, df_ips_lycee])

df_ips = charger_donnees_ips()
df_ips = df_ips.dropna(subset=['ips'])

@st.cache_resource
def charger_donnees_geo():
    path = os.path.join(os.path.dirname(__file__), '../fr-en-annuaire-education.csv')
    return pd.read_csv(path,
                      encoding='utf-8-sig',
                      sep=';',
                      quotechar='"',
                      engine='python')

df_geo = charger_donnees_geo()

@st.cache_resource
def creer_geodf(df_ips, df_geo):
    df_geo_limit = df_geo[['Nom_etablissement', 'Identifiant_de_l_etablissement', 'multi_uai', 'latitude', 'longitude', 'Nom_commune', 'Code_postal', 'Code_commune', 'libelle_nature']]
    df_ips = df_ips.merge(df_geo_limit, left_on='uai', right_on='Identifiant_de_l_etablissement')

    gdf = gpd.GeoDataFrame(df_ips, geometry=gpd.points_from_xy(df_ips.longitude, df_ips.latitude), crs="EPSG:4326")
    
    return gdf

gdf = creer_geodf(df_ips, df_geo)

# Définir la colormap pour l'IPS
colors = ['#d7191c', '#e76818', '#f29e2e', '#f9d057', '#ffff8c',
          '#90eb9d', '#00ccbc',  '#00a6ca', '#2c7bb6']

# Tri des couleurs et de l'échelle
min_ips = df_ips['ips'].min()
max_ips = df_ips['ips'].max()

colormap = cm.LinearColormap(
    colors=colors,
    vmin=min_ips,
    vmax=max_ips,
    caption='Indice de Position Sociale (IPS)'
)

# Fonction pour afficher la carte
def afficher_carte(gdf, afficher_public, afficher_prive, afficher_college, afficher_lycee):
    m = folium.Map(location=st.session_state['map_center'], zoom_start=st.session_state['zoom'])
    
    # Ajouter les contours de la France
    folium.GeoJson(france.geometry, name="France", style_function=lambda x: {
        'fillColor': 'none',
        'color': 'black',
        'weight': 1
    }).add_to(m)

    # Appliquer les filtres sur la GeoDataFrame
    if afficher_public and not afficher_prive:
        gdf_filtered = gdf[gdf['secteur'] == 'public']
    elif afficher_prive and not afficher_public:
        gdf_filtered = gdf[gdf['secteur'] != 'public']
    elif afficher_prive and afficher_public:
        gdf_filtered = gdf
    else:
        gdf_filtered = None

    if afficher_college and not afficher_lycee:
        gdf_filtered = gdf_filtered[gdf_filtered['type'] == 'collège']
    elif afficher_lycee and not afficher_college:
        gdf_filtered = gdf_filtered[gdf_filtered['type'] == 'lycée']
    elif afficher_college and afficher_lycee:
        gdf_filtered = gdf_filtered
    else : 
        gdf_filtered = None
      

    # Afficher les établissements filtrés
    fg = folium.FeatureGroup(name='Établissements')
    for _, row in gdf_filtered.iterrows():
        folium.CircleMarker(
            location=[row['latitude'], row['longitude']],
            radius=5,
            fill=True,
            fill_color=colormap(row['ips']),
            color=colormap(row['ips']),
            fill_opacity=0.9,
            popup=f"{row['Nom_commune']}<br>IPS: {row['ips']}<br>{row['type']}<br>{row['secteur']}"
        ).add_to(fg)
    fg.add_to(m)

    # Ajouter la légende de la colormap
    colormap.add_to(m)

    return m

# Afficher les checkboxes pour sélectionner les établissements publics/privés et collège/lycée
st.title("Carte des établissements avec IPS")

# Créer 2 colonnes pour les checkboxes
col1, col2 = st.columns(2)

# Première colonne : Choix entre Collège ou Lycée
with col1:
    afficher_college = st.checkbox("Afficher les Collèges", value=True)
    afficher_lycee = st.checkbox("Afficher les Lycées", value=False)

# Deuxième colonne : Choix entre Public ou Privé
with col2:
    afficher_public = st.checkbox("Afficher les établissements publics", value=True)
    afficher_prive = st.checkbox("Afficher les établissements privés", value=False)

# Sauvegarder l'état des checkboxes dans session_state
st.session_state['afficher_college'] = afficher_college
st.session_state['afficher_lycee'] = afficher_lycee
st.session_state['afficher_public'] = afficher_public
st.session_state['afficher_prive'] = afficher_prive

# Afficher la carte avec les couches sélectionnées
m = afficher_carte(gdf, st.session_state['afficher_public'], st.session_state['afficher_prive'], 
                   st.session_state['afficher_college'], st.session_state['afficher_lycee'])

# Afficher la carte avec Streamlit et récupérer l'état de la carte après interaction
st_data = st_folium(m, width=800, height=600, returned_objects=[])

# Mettre à jour session_state uniquement si l'utilisateur bouge la carte
if st_data and st_data.get("last_center") and st_data.get("zoom"):
    st.session_state['map_center'] = st_data["last_center"]
    st.session_state['zoom'] = st_data["zoom"]
