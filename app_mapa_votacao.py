import os
import re
import requests
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster

st.set_page_config(page_title="Mapa de Votação - Araruama", page_icon="🗺️", layout="wide")

st.title("📍 Mapa de Locais de Votação e Seções")
st.markdown("Visão interativa da 92ª Zona Eleitoral de Araruama com localizações oficiais.")

# Função para extrair lat/lon reais do link curto do Google Maps
def extrair_coords_do_link(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        r = requests.get(url, allow_redirects=True, headers=headers, timeout=6)
        final_url = r.url
        text = r.text

        # Padrões comuns do Google Maps
        patterns = [
            r'@(-?\d+\.\d+),(-?\d+\.\d+)',
            r'!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)',
            r'ftid:[^!]*!2d(-?\d+\.\d+)!3d(-?\d+\.\d+)',
            r'[?&]q=(-?\d+\.\d+),(-?\d+\.\d+)',
            r'/place/[^/]+/(-?\d+\.\d+),(-?\d+\.\d+)'
        ]

        for pat in patterns:
            m = re.search(pat, final_url)
            if m:
                v1, v2 = float(m.group(1)), float(m.group(2))
                # Validar se bate na região de Araruama/Região dos Lagos
                if -23.5 < v1 < -22.0 and -43.0 < v2 < -41.5:
                    return v1, v2
                elif -23.5 < v2 < -22.0 and -43.0 < v1 < -41.5:
                    return v2, v1

        # Busca secundaria no HTML da página redirecionada
        m_html = re.search(r'(-22\.\d{4,8}),\s*(-42\.\d{4,8})', text)
        if m_html:
            return float(m_html.group(1)), float(m_html.group(2))

    except Exception:
        pass
    return None, None

@st.cache_data
def carregar_dados():
    nome_arquivo = "Eleições 2026 - 92ª Zona Eleitoral de Araruama.xlsx"
    if not os.path.exists(nome_arquivo):
        if os.path.exists("Eleições 2026 - 92ª Zona Eleitoral de Araruama_2.xlsx"):
            nome_arquivo = "Eleições 2026 - 92ª Zona Eleitoral de Araruama_2.xlsx"
            
    df = pd.read_excel(nome_arquivo)
    df.columns = [str(col).strip().upper() for col in df.columns]

    col_local = next((c for c in df.columns if 'LOCAL' in c), 'LOCAIS DE VOTAÇÃO')
    col_link = next((c for c in df.columns if 'LINK' in c or 'MAPA' in c or 'URL' in c), None)

    cache_file = ".cache_coords.csv"
    if os.path.exists(cache_file):
        df_cache = pd.read_csv(cache_file)
        if len(df_cache) == len(df):
            return df_cache

    lats, lons = [], []
    bar = st.progress(0, text="Mapeando locais exatos via Google Maps... Aguarde alguns segundos.")
    
    for idx, row in df.iterrows():
        lat, lon = None, None
        if col_link and pd.notnull(row[col_link]):
            lat, lon = extrair_coords_do_link(str(row[col_link]).strip())
        
        lats.append(lat)
        lons.append(lon)
        bar.progress((idx + 1) / len(df))
        
    bar.empty()
    df['LATITUDE'] = lats
    df['LONGITUDE'] = lons

    # Remove entradas onde não conseguiu pegar coordenada para não jogar pino no lugar errado
    df_valido = df.dropna(subset=['LATITUDE', 'LONGITUDE']).copy()
    df_valido.to_csv(cache_file, index=False)
    return df_valido

df = carregar_dados()

# Sidebar e Métricas
st.sidebar.header("🔍 Pesquisa")
busca = st.sidebar.text_input("Filtrar por Local ou Seção:")

if busca:
    df_filtrado = df[
        df['LOCAIS DE VOTAÇÃO'].astype(str).str.contains(busca, case=False, na=False) |
        df['SEÇÕES'].astype(str).str.contains(busca, case=False, na=False)
    ]
else:
    df_filtrado = df.copy()

st.metric("Locais Mapeados Exatamente", f"{len(df_filtrado)} de {len(df)}")

# Configuração do Mapa
if not df_filtrado.empty:
    centro_lat = df_filtrado['LATITUDE'].mean()
    centro_lon = df_filtrado['LONGITUDE'].mean()
else:
    centro_lat, centro_lon = -22.8712, -42.3415

m = folium.Map(location=[centro_lat, centro_lon], zoom_start=12, tiles="OpenStreetMap")
marker_cluster = MarkerCluster().add_to(m)

for _, row in df_filtrado.iterrows():
    lat = row['LATITUDE']
    lon = row['LONGITUDE']
    local = row.get('LOCAIS DE VOTAÇÃO', 'Local de Votação')
    secoes = row.get('SEÇÕES', 'N/A')
    link = row.get('LINK', f"https://www.google.com/maps/search/?api=1&query={lat},{lon}")

    popup_html = f"""
    <div style="font-family: Arial, sans-serif; font-size: 13px; width: 220px;">
        <h4 style="margin: 0 0 5px 0; color: #1E88E5;">{local}</h4>
        <p style="margin: 0 0 10px 0;"><b>Seções:</b> {secoes}</p>
        <a href="{link}" target="_blank" 
           style="background-color: #28a745; color: white; padding: 6px 12px; 
                  text-decoration: none; border-radius: 4px; display: inline-block; 
                  font-weight: bold; text-align: center; width: 100%; box-sizing: border-box;">
            🗺️ Abrir no Google Maps
        </a>
    </div>
    """

    folium.Marker(
        location=[lat, lon],
        popup=folium.Popup(popup_html, max_width=280),
        tooltip=str(local),
        icon=folium.Icon(color="blue", icon="info-sign")
    ).add_to(marker_cluster)

st_folium(m, width="100%", height=550)
