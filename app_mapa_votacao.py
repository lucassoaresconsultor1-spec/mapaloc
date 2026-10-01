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
st.markdown("Visão interativa da 92ª Zona Eleitoral de Araruama.")

# -----------------------------------------------------------------------------
# FUNÇÃO PARA EXTRAIR LATITUDE E LONGITUDE DIRETO DO LINK DO GOOGLE MAPS
# -----------------------------------------------------------------------------
def extrair_coordenadas_do_link(url):
    try:
        # Segue o redirecionamento do link encurtado (maps.app.goo.gl)
        response = requests.get(url, allow_redirects=True, timeout=5)
        url_final = response.url
        
        # Padrão 1: @lat,lon (ex: @-22.8712,-42.3415)
        match = re.search(r'@(-?\d+\.\d+),(-?\d+\.\d+)', url_final)
        if match:
            return float(match.group(1)), float(match.group(2))
            
        # Padrão 2: !3dlat!4dlon
        match = re.search(r'!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)', url_final)
        if match:
            return float(match.group(1)), float(match.group(2))
            
        # Padrão 3: ?q=lat,lon
        match = re.search(r'[?&]q=(-?\d+\.\d+),(-?\d+\.\d+)', url_final)
        if match:
            return float(match.group(1)), float(match.group(2))
            
        return None, None
    except Exception:
        return None, None

# -----------------------------------------------------------------------------
# CARREGAMENTO E PROCESSAMENTO AUTOMÁTICO
# -----------------------------------------------------------------------------
@st.cache_data(ttl=86400) # Guarda em cache por 24h para ser ultra-rápido nas requisições
def carregar_dados_com_coordenadas_automaticas():
    nome_arquivo = "Eleições 2026 - 92ª Zona Eleitoral de Araruama.xlsx"
    if not os.path.exists(nome_arquivo):
        if os.path.exists("Eleições 2026 - 92ª Zona Eleitoral de Araruama_2.xlsx"):
            nome_arquivo = "Eleições 2026 - 92ª Zona Eleitoral de Araruama_2.xlsx"
        else:
            st.error("⚠️ Planilha não encontrada no repositório GitHub!")
            st.stop()
            
    df = pd.read_excel(nome_arquivo)
    df.columns = [str(col).strip().upper() for col in df.columns]
    
    col_link = next((c for c in df.columns if 'LINK' in c or 'URL' in c), None)
    col_local = next((c for c in df.columns if 'LOCAL' in c), 'LOCAIS DE VOTAÇÃO')
    
    if not col_link:
        st.error("⚠️️ Coluna 'LINK' não encontrada na planilha!")
        st.stop()
        
    lats = []
    lons = []
    
    # Processa os links automaticamente
    progress_bar = st.progress(0, text="Obtendo coordenadas automaticamente dos links...")
    total = len(df)
    
    for i, row in df.iterrows():
        link = str(row[col_link]).strip()
        lat, lon = extrair_coordenadas_do_link(link)
        lats.append(lat)
        lons.append(lon)
        progress_bar.progress((i + 1) / total)
        
    progress_bar.empty()
    
    df['LATITUDE'] = lats
    df['LONGITUDE'] = lons
    
    # Remove eventuais links que não puderam ser resolvidos
    df_valido = df.dropna(subset=['LATITUDE', 'LONGITUDE']).copy()
    
    return df_valido

df = carregar_dados_com_coordenadas_automaticas()

# -----------------------------------------------------------------------------
# FILTROS E PESQUISA
# -----------------------------------------------------------------------------
st.sidebar.header("🔍 Pesquisa")
busca = st.sidebar.text_input("Filtrar por Local ou Seção:")

if busca:
    df_filtrado = df[
        df['LOCAIS DE VOTAÇÃO'].astype(str).str.contains(busca, case=False, na=False) |
        df['SEÇÕES'].astype(str).str.contains(busca, case=False, na=False)
    ]
else:
    df_filtrado = df.copy()

st.metric("Locais Exibidos no Mapa", f"{len(df_filtrado)} de {len(df)}")

# -----------------------------------------------------------------------------
# CONSTRUÇÃO DO MAPA INTERATIVO (FOLIUM)
# -----------------------------------------------------------------------------
centro_lat = df_filtrado['LATITUDE'].mean() if not df_filtrado.empty else -22.8712
centro_lon = df_filtrado['LONGITUDE'].mean() if not df_filtrado.empty else -42.3415

m = folium.Map(location=[centro_lat, centro_lon], zoom_start=12, tiles="OpenStreetMap")
marker_cluster = MarkerCluster().add_to(m)

for _, row in df_filtrado.iterrows():
    lat = row['LATITUDE']
    lon = row['LONGITUDE']
    local = row.get('LOCAIS DE VOTAÇÃO', 'Local de Votação')
    secoes = row.get('SEÇÕES', 'N/A')
    link = row.get('LINK', '#')
    
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
