import os
import glob
import re
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
from folium.plugins import Fullscreen

st.set_page_config(page_title="Mapa de Votação - Araruama", page_icon="🗺️", layout="wide")

st.title("📍 Mapa de Locais de Votação e Seções")
st.markdown("Visão interativa da 92ª Zona Eleitoral de Araruama.")

@st.cache_data
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
        st.error("Nenhum ficheiro de dados encontrado na pasta do repositório.")
        st.stop()

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

    return df

df = carregar_dados()

# Colunas identificadas no DataFrame
col_local = next((c for c in df.columns if 'LOCAL' in c), 'LOCAIS DE VOTAÇÃO')
col_secao = next((c for c in df.columns if 'SEÇ' in c or 'SEC' in c), 'SEÇÕES')
col_link = next((c for c in df.columns if 'LINK' in c or 'MAPA' in c or 'URL' in c), None)

# Extração da lista de seções para o menu suspenso
todas_secoes = set()
for secoes_str in df[col_secao].dropna().astype(str):
    numeros = re.findall(r'\d+', secoes_str)
    todas_secoes.update(numeros)

secoes_ordenadas = sorted(list(todas_secoes), key=lambda x: int(x) if x.isdigit() else x)

# --- BARRA DE PESQUISA ACIMA DO MAPA ---
st.subheader("🔍 Pesquisar Local de Votação")
col_busca1, col_busca2 = st.columns([2, 1])

with col_busca1:
    busca_escola = st.text_input("Buscar por Nome da Escola / Local:", placeholder="Ex: André Gomes, Unilagos, etc.")

with col_busca2:
    secao_selecionada = st.selectbox("Filtrar por Número da Seção:", ["Todas"] + secoes_ordenadas)

# --- FILTRAGEM DOS DADOS ---
df_filtrado = df.copy()

if busca_escola:
    df_filtrado = df_filtrado[
        df_filtrado[col_local].astype(str).str.contains(busca_escola, case=False, na=False)
    ]

if secao_selecionada != "Todas":
    df_filtrado = df_filtrado[
        df_filtrado[col_secao].astype(str).apply(lambda x: re.search(r'\b' + re.escape(secao_selecionada) + r'\b', x) is not None)
    ]

df_mapa = df_filtrado.dropna(subset=['LATITUDE', 'LONGITUDE'])

# Indicador de resultados exibidos
st.metric("Total de Locais Exibidos", f"{len(df_mapa)} de {len(df)}")

# Ajuste automático do centro e zoom do mapa conforme a pesquisa
if not df_mapa.empty:
    centro_lat = df_mapa['LATITUDE'].mean()
    centro_lon = df_mapa['LONGITUDE'].mean()
    zoom_inicial = 15 if (busca_escola or secao_selecionada != "Todas") else 12
else:
    centro_lat, centro_lon = -22.8712, -42.3415
    zoom_inicial = 12

m = folium.Map(location=[centro_lat, centro_lon], zoom_start=zoom_inicial, tiles="OpenStreetMap")

# Plugin de Tela Cheia
Fullscreen(
    position="topright",
    title="Expandir Mapa",
    title_cancel="Sair da Tela Cheia",
    force_separate_button=True
).add_to(m)

# Inserção dos marcadores fixos
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
    ).add_to(m)

# Key dinâmica para atualização instantânea no renderizador do Streamlit
map_key = f"map_{busca_escola}_{secao_selecionada}_{len(df_mapa)}"
st_folium(m, width="100%", height=550, key=map_key, returned_objects=[])
