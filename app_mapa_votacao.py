import os
import glob
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
    # Procura automaticamente qualquer arquivo CSV ou XLSX na pasta do projeto
    arquivos_csv = glob.glob("*.csv")
    arquivos_xlsx = glob.glob("*.xlsx")
    
    if arquivos_csv:
        nome_arquivo = arquivos_csv[0]
        df = pd.read_csv(nome_arquivo)
    elif arquivos_xlsx:
        nome_arquivo = arquivos_xlsx[0]
        df = pd.read_excel(nome_arquivo)
    else:
        st.error("Nenhum arquivo de planilha (CSV ou XLSX) foi encontrado na pasta do GitHub.")
        st.stop()

    df.columns = [str(col).strip().upper() for col in df.columns]

    # Verifica se Latitude e Longitude estão juntas em uma única coluna ou separadas
    col_coords = next((c for c in df.columns if 'LATITUDE' in c and 'LONGITUDE' in c), None)
    
    if col_coords:
        # Separa a coluna combinada "LATITUDE, LONGITUDE"
        df[['LATITUDE', 'LONGITUDE']] = df[col_coords].astype(str).str.split(',', expand=True)
        df['LATITUDE'] = pd.to_numeric(df['LATITUDE'].str.strip(), errors='coerce')
        df['LONGITUDE'] = pd.to_numeric(df['LONGITUDE'].str.strip(), errors='coerce')
    else:
        # Garante a conversão para número caso estejam em colunas separadas
        if 'LATITUDE' in df.columns:
            df['LATITUDE'] = pd.to_numeric(df['LATITUDE'].astype(str).str.replace(',', '.'), errors='coerce')
        if 'LONGITUDE' in df.columns:
            df['LONGITUDE'] = pd.to_numeric(df['LONGITUDE'].astype(str).str.replace(',', '.'), errors='coerce')

    return df

df = carregar_dados()

# Sidebar e Busca
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
