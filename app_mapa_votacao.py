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
    # Lê o ficheiro CSV diretamente do GitHub
    df = pd.read_csv("Eleições 2026 - 92ª Zona Eleitoral de Araruama.csv")
    df.columns = [str(col).strip().upper() for col in df.columns]
    
    # Se a coluna de coordenadas estiver juntas como "LATITUDE, LONGITUDE", faz a separação automática
    col_lat_lon = next((c for c in df.columns if 'LATITUDE' in c or 'LONGITUDE' in c), None)
    
    if col_lat_lon and 'LATITUDE' not in df.columns:
        coords = df[col_lat_lon].astype(str).str.split(',', expand=True)
        df['LATITUDE'] = coords[0].astype(float)
        df['LONGITUDE'] = coords[1].astype(float)
        
    return df

df = carregar_dados()

# Sidebar e Busca
st.sidebar.header("🔍 Pesquisa")
busca = st.sidebar.text_input("Filtrar por Local ou Seção:")

if busca:
    df_filtrado = df[
        df['LOCAIS DE VOTAÇÃO'].astype(str).str.contains(busca, case=False, na=False) |
        df['SEÇÕES'].astype(str).str.contains(busca, case=False, na=False)
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

for _, row in df_mapa.iterrows():
    lat = float(row['LATITUDE'])
    lon = float(row['LONGITUDE'])
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
