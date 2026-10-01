import os
import glob
import re
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster

st.set_page_config(page_title="Mapa de Votação - Araruama", page_icon="🗺️", layout="wide")

st.title("📍 Mapa de Locais de Votação e Seções")
st.markdown("Visão interativa da 92ª Zona Eleitoral de Araruama.")

@st.cache_data
def carregar_dados():
    # Procura automaticamente por ficheiros TSV, CSV ou XLSX na pasta
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
        st.error("Nenhum ficheiro de dados encontrado na pasta do repositório.")
        st.stop()

    # Normaliza nomes das colunas
    df.columns = [str(col).strip().upper() for col in df.columns]

    lats = []
    lons = []

    # Procura coluna combinada "LATITUDE, LONGITUDE" ou colunas separadas
    col_comb = next((c for c in df.columns if 'LAT' in c and 'LON' in c), None)
    col_lat = next((c for c in df.columns if 'LAT' in c and 'LON' not in c), None)
    col_lon = next((c for c in df.columns if 'LON' in c and 'LAT' not in c), None)

    for _, row in df.iterrows():
        lat, lon = None, None
        
        # 1. Tenta extrair da coluna combinada
        if col_comb and pd.notnull(row[col_comb]):
            texto = str(row[col_comb]).replace(';', ',')
            partes = texto.split(',')
            if len(partes) >= 2:
                try:
                    lat = float(partes[0].strip())
                    lon = float(partes[1].strip())
                except ValueError:
                    pass
                    
        # 2. Tenta extrair das colunas separadas se ainda não encontrou
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

        lats.append(lat)
        lons.append(lon)

    df['LATITUDE'] = lats
    df['LONGITUDE'] = lons

    return df

df = carregar_dados()

# Sidebar e Pesquisa
st.sidebar.header("🔍 Pesquisa")
busca = st.sidebar.text_input("Filtrar por Local ou Seção:")

col_local = next((c for c in df.columns if 'LOCAL' in c), 'LOCAIS DE VOTAÇÃO')
col_secao = next((c for c in df.columns if 'SEÇ' in c or 'SEC' in c), 'SEÇÕES')

if busca:
    df_filtrado = df[
        df[col_local].astype(str).str.contains(busca, case=False, na=False) |
        df[col_secao].astype(str).str.contains(busca, case=False, na=False)
    ]
else:
    df_filtrado = df.copy()

# Filtra registos com coordenadas válidas
df_mapa = df_filtrado.dropna(subset=['LATITUDE', 'LONGITUDE'])

st.metric("Total de Locais Mapeados", f"{len(df_mapa)} de {len(df)}")

if not df_mapa.empty:
    centro_lat = df_mapa['LATITUDE'].mean()
    centro_lon = df_mapa['LONGITUDE'].mean()
else:
    centro_lat, centro_lon = -22.8712, -42.3415

m = folium.Map(location=[centro_lat, centro_lon], zoom_start=12, tiles="OpenStreetMap")
marker_cluster = MarkerCluster().add_to(m)

col_link = next((c for c in df.columns if 'LINK' in c or 'MAPA' in c or 'URL' in c), None)

for _, row in df_mapa.iterrows():
    lat = float(row['LATITUDE'])
    lon = float(row['LONGITUDE'])
    local = row.get(col_local, 'Local de Votação')
    secoes = row.get(col_secao, 'N/A')
    link = row.get(col_link, f"https://www.google.com/maps/search/?api=1&query={lat},{lon}")

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
