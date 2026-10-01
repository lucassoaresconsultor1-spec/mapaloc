import os
import glob
import re
import numpy as np
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
from folium.plugins import Fullscreen
from sklearn.cluster import KMeans
from scipy.spatial import ConvexHull

st.set_page_config(page_title="Mapa de Votação - Araruama", page_icon="🗺️", layout="wide")

st.title("📍 Mapa de Locais de Votação por Zonas e Áreas")
st.markdown("Divisão inteligente dos pontos em 20 zonas geográficas com manchas de cobertura.")

def carregar_dados():
    arquivos_tsv = glob.glob("*.tsv")
    arquivos_csv = glob.glob("*.csv")
    arquivos_xlsx = glob.glob("*.xlsx")
    
    if arquivos_tsv:
        df = pd.read_csv(arquivos_tsv[0], sep='\t')
    elif arquivos_csv:
        df = pd.read_csv(arquivos_csv[0])
    elif arquivos_xlsx:
        df = pd.read_excel(arquivos_xlsx[0])
    else:
        df = pd.DataFrame()

    df.columns = [str(col).strip().upper() for col in df.columns]

    lats, lons = [], []

    col_comb = next((c for c in df.columns if 'LAT' in c and 'LON' in c), None)
    col_lat = next((c for c in df.columns if 'LAT' in c and 'LON' not in c), None)
    col_lon = next((c for c in df.columns if 'LON' in c and 'LAT' not in c), None)

    for _, row in df.iterrows():
        lat, lon = None, None
        
        if col_comb and pd.notnull(row[col_comb]):
            nums = re.findall(r'-?\d+\.\d+', str(row[col_comb]))
            if len(nums) >= 2:
                v1, v2 = float(nums[0]), float(nums[1])
                if v1 < -35 and v2 > -30:
                    lat, lon = v2, v1
                else:
                    lat, lon = v1, v2
                    
        if lat is None and col_lat and pd.notnull(row[col_lat]):
            try:
                lat = float(str(row[col_lat]).replace(',', '.').strip())
            except ValueError:
                pass
                
        if lon is None and col_lon and pd.notnull(row[col_lon]):
            try:
                lon = float(str(row[col_lon]).replace(',', '.').strip())
            except ValueError:
                pass

        if lat is not None and lon is not None:
            if lat < -35 and lon > -30:
                lat, lon = lon, lat

        lats.append(lat)
        lons.append(lon)

    df['LATITUDE'] = lats
    df['LONGITUDE'] = lons

    col_local = next((c for c in df.columns if 'LOCAL' in c), 'LOCAIS DE VOTAÇÃO')
    col_secao = next((c for c in df.columns if 'SEÇ' in c or 'SEC' in c), 'SEÇÕES')
    col_link = next((c for c in df.columns if 'LINK' in c or 'MAPA' in c or 'URL' in c), 'LINK')

    # Registro garantido da Praia Seca
    praia_seca = pd.DataFrame([{
        col_local: "PÇA E. COMTE. SÉRGIO RIBEIRO (PRAIA SECA)",
        col_secao: "Praia Seca",
        'LATITUDE': -22.9225214,
        'LONGITUDE': -42.3081065,
        col_link: "https://maps.app.goo.gl/ohsy6xAmdXSqJV4g8?g_st=ac"
    }])

    if not df.empty and col_local in df.columns:
        df = df[~df[col_local].astype(str).str.contains("SÉRGIO RIBEIRO", case=False, na=False)]
    
    df = pd.concat([df, praia_seca], ignore_index=True)

    return df

df = carregar_dados()

col_local = next((c for c in df.columns if 'LOCAL' in c), 'LOCAIS DE VOTAÇÃO')
col_secao = next((c for c in df.columns if 'SEÇ' in c or 'SEC' in c), 'SEÇÕES')
col_link = next((c for c in df.columns if 'LINK' in c or 'MAPA' in c or 'URL' in c), 'LINK')

df_valid = df.dropna(subset=['LATITUDE', 'LONGITUDE']).copy()

# --- DIVISÃO EM 20 ZONAS VIA K-MEANS ---
n_clusters = min(20, len(df_valid))

if n_clusters > 0:
    coords = df_valid[['LATITUDE', 'LONGITUDE']].values
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10).fit(coords)
    df_valid['ZONA'] = kmeans.labels_ + 1
else:
    df_valid['ZONA'] = 1

# Paleta com 20 cores distintas em código HEX
CORES_ZONAS = [
    '#e6194b', '#3cb44b', '#ffe119', '#4363d8', '#f58231', 
    '#911eb4', '#46f0f0', '#f032e6', '#bcfd4c', '#fabebe', 
    '#008080', '#e6beff', '#9a6324', '#fffac8', '#800000', 
    '#aaffc3', '#808000', '#ffd8b1', '#000075', '#808080'
]

# --- PAINEL LATERAL DE OPÇÕES ---
st.sidebar.header("⚙️ Opções de Zonas")
mostrar_manchas = st.sidebar.checkbox("Mostrar manchas/polígonos das Zonas", value=True)
zona_filtro = st.sidebar.selectbox("Filtrar por Zona:", ["Todas as Zonas"] + [f"Zona {i}" for i in range(1, n_clusters + 1)])

# --- CAMPO DE PESQUISA ---
busca = st.text_input(
    "🔍 Pesquisar por Nome do Local ou Número da Seção:", 
    placeholder="Digite o nome da escola ou o número da seção..."
)

df_filtrado = df_valid.copy()

if busca.strip():
    termo = busca.strip()
    df_filtrado = df_filtrado[
        df_filtrado[col_local].astype(str).str.contains(termo, case=False, na=False) |
        df_filtrado[col_secao].astype(str).str.contains(termo, case=False, na=False)
    ]

if zona_filtro != "Todas as Zonas":
    num_z = int(zona_filtro.replace("Zona ", ""))
    df_filtrado = df_filtrado[df_filtrado['ZONA'] == num_z]

st.metric("Total de Locais Exibidos", f"{len(df_filtrado)} de {len(df_valid)}")

if not df_filtrado.empty:
    centro_lat = df_filtrado['LATITUDE'].mean()
    centro_lon = df_filtrado['LONGITUDE'].mean()
    zoom_inicial = 14 if (busca.strip() or zona_filtro != "Todas as Zonas") else 11
else:
    centro_lat, centro_lon = -22.8712, -42.3415
    zoom_inicial = 11

m = folium.Map(location=[centro_lat, centro_lon], zoom_start=zoom_inicial, tiles="OpenStreetMap")

Fullscreen(
    position="topright",
    title="Expandir Mapa",
    title_cancel="Sair da Tela Cheia",
    force_separate_button=True
).add_to(m)

# DESENHAR MANCHAS DA COBERTURA GEOGRÁFICA DE CADA ZONA
if mostrar_manchas:
    zonas_desenhar = df_filtrado['ZONA'].unique() if zona_filtro != "Todas as Zonas" else range(1, n_clusters + 1)
    
    for z in zonas_desenhar:
        pts = df_valid[df_valid['ZONA'] == z][['LATITUDE', 'LONGITUDE']].values
        cor = CORES_ZONAS[(z - 1) % len(CORES_ZONAS)]
        
        if len(pts) >= 3:
            hull = ConvexHull(pts)
            hull_pts = pts[hull.vertices]
            polygon_coords = [[pt[0], pt[1]] for pt in hull_pts]
            
            folium.Polygon(
                locations=polygon_coords,
                color=cor,
                fill=True,
                fill_color=cor,
                fill_opacity=0.22,
                weight=2,
                popup=f"Mancha Geográfica - Zona {z}"
            ).add_to(m)
        elif len(pts) > 0:
            for pt in pts:
                folium.Circle(
                    location=[pt[0], pt[1]],
                    radius=500,
                    color=cor,
                    fill=True,
                    fill_color=cor,
                    fill_opacity=0.25,
                    popup=f"Zona {z}"
                ).add_to(m)

# EXIBIR OS MARCADORES COLORIDOS DE CADA LOCAL
for _, row in df_filtrado.iterrows():
    lat = float(row['LATITUDE'])
    lon = float(row['LONGITUDE'])
    local = row.get(col_local, 'Local de Votação')
    secoes = row.get(col_secao, 'N/A')
    zona_num = int(row['ZONA'])
    cor_zona = CORES_ZONAS[(zona_num - 1) % len(CORES_ZONAS)]
    link = row.get(col_link, f"https://www.google.com/maps/search/?api=1&query={lat},{lon}")

    popup_html = f"""
    <div style="font-family: Arial, sans-serif; font-size: 13px; width: 230px;">
        <span style="background-color: {cor_zona}; color: white; padding: 3px 8px; border-radius: 10px; font-weight: bold; font-size: 11px;">
            ZONA {zona_num}
        </span>
        <h4 style="margin: 8px 0 5px 0; color: #1E88E5;">{local}</h4>
        <p style="margin: 0 0 10px 0;"><b>Seções:</b> {secoes}</p>
        <a href="{link}" target="_blank" 
           style="background-color: #28a745; color: white; padding: 6px 12px; 
                  text-decoration: none; border-radius: 4px; display: inline-block; 
                  font-weight: bold; text-align: center; width: 100%; box-sizing: border-box;">
            🗺️ Abrir no Google Maps
        </a>
    </div>
    """

    folium.CircleMarker(
        location=[lat, lon],
        radius=9,
        color="#000000",
        weight=1,
        fill=True,
        fill_color=cor_zona,
        fill_opacity=0.9,
        popup=folium.Popup(popup_html, max_width=280),
        tooltip=f"[Zona {zona_num}] {local}"
    ).add_to(m)

map_key = f"map_{busca.strip()}_{zona_filtro}_{len(df_filtrado)}"
st_folium(m, width="100%", height=550, key=map_key, returned_objects=[])
