import os
import re
import time
import requests
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster

st.set_page_config(page_title="Mapa de Votação - Araruama", page_icon="🗺️", layout="wide")

st.title("📍 Mapa de Locais de Votação e Seções")
st.markdown("Visão interativa da 92ª Zona Eleitoral de Araruama.")

# Função para extrair lat/lon reais do link do Google Maps com tempo de espera contra bloqueios
def extrair_coords_do_link(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7'
        }
        # Timeout aumentado para garantir carregamento e evitar perdas
        r = requests.get(url, allow_redirects=True, headers=headers, timeout=15)
        final_url = r.url
        text = r.text

        # Padrões de coordenadas nas URLs do Google Maps
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
                if -24.0 < v1 < -20.0 and -45.0 < v2 < -40.0:
                    return v1, v2
                elif -24.0 < v2 < -20.0 and -45.0 < v1 < -40.0:
                    return v2, v1

        # Procura no HTML retornado
        m_html = re.search(r'(-22\.\d{4,8}),\s*(-42\.\d{4,8})', text)
        if m_html:
            return float(m_html.group(1)), float(m_html.group(2))

    except Exception:
        pass
    return None, None

@st.cache_data
def carregar_dados():
    cache_file = ".cache_coords.csv"
    
    # Se o cache existe e tem 44 locais, carrega instantaneamente
    if os.path.exists(cache_file):
        df_cache = pd.read_csv(cache_file)
        if len(df_cache) == 44:
            return df_cache

    nome_arquivo = "Eleições 2026 - 92ª Zona Eleitoral de Araruama.xlsx"
    if not os.path.exists(nome_arquivo):
        if os.path.exists("Eleições 2026 - 92ª Zona Eleitoral de Araruama_2.xlsx"):
            nome_arquivo = "Eleições 2026 - 92ª Zona Eleitoral de Araruama_2.xlsx"
            
    df = pd.read_excel(nome_arquivo)
    df.columns = [str(col).strip().upper() for col in df.columns]

    col_local = next((c for c in df.columns if 'LOCAL' in c), 'LOCAIS DE VOTAÇÃO')
    col_link = next((c for c in df.columns if 'LINK' in c or 'MAPA' in c or 'URL' in c), None)

    lats = []
    lons = []
    
    progresso = st.progress(0, text="Mapeando os 44 locais exatos no Google Maps... (aguarde ~1 min na 1ª vez)")
    
    total = len(df)
    for idx, row in df.iterrows():
        url = str(row[col_link]).strip() if col_link and pd.notnull(row[col_link]) else ""
        lat, lon = extrair_coords_do_link(url)
        
        # Se falhou na 1ª tentativa por instabilidade da rede, tenta mais 1 vez
        if lat is None and url:
            time.sleep(2.0)
            lat, lon = extrair_coords_do_link(url)

        lats.append(lat)
        lons.append(lon)
        
        progresso.progress((idx + 1) / total, text=f"Mapeando local {idx+1} de {total}: {row[col_local]}")
        
        # Pausa de 1.2 segundos para não sofrer bloqueio do Google por acessos rápidos
        time.sleep(1.2)
        
    progresso.empty()

    df['LATITUDE'] = lats
    df['LONGITUDE'] = lons

    # Salva o arquivo de cache local para as próximas execuções
    df.to_csv(cache_file, index=False)
    return df

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

st.metric("Total de Locais Mapeados", f"{len(df_filtrado[df_filtrado['LATITUDE'].notnull()])} de {len(df)}")

# Filtra apenas locais que obtiveram coordenadas com sucesso
df_mapa = df_filtrado.dropna(subset=['LATITUDE', 'LONGITUDE'])

if not df_mapa.empty:
    centro_lat = df_mapa['LATITUDE'].mean()
    centro_lon = df_mapa['LONGITUDE'].mean()
else:
    centro_lat, centro_lon = -22.8712, -42.3415

m = folium.Map(location=[centro_lat, centro_lon], zoom_start=12, tiles="OpenStreetMap")
marker_cluster = MarkerCluster().add_to(m)

for _, row in df_mapa.iterrows():
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
