import os
import glob
import re
import numpy as np
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
from folium.plugins import Fullscreen

st.set_page_config(page_title="Mapa de Votação por Bairros - Araruama", page_icon="🗺️", layout="wide")

st.title("📍 Divisão de Áreas e Bairros - Araruama")
st.markdown("Manchas de cobertura e divisão territorial por Bairros e Locais de Votação.")

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
col_bairro = next((c for c in df.columns if 'BAIRRO' in c or 'END' in c), None)
col_link = next((c for c in df.columns if 'LINK' in c or 'MAPA' in c or 'URL' in c), 'LINK')

df_valid = df.dropna(subset=['LATITUDE', 'LONGITUDE']).copy()

# Paleta de cores vibrantes
CORES_BAIRROS = [
    '#e6194b', '#3cb44b', '#ffe119', '#4363d8', '#f58231', 
    '#911eb4', '#46f0f0', '#f032e6', '#bcfd4c', '#fabebe', 
    '#008080', '#e6beff', '#9a6324', '#fffac8', '#800000', 
    '#aaffc3', '#808000', '#ffd8b1', '#000075', '#808080'
]

# --- PAINEL LATERAL ---
st.sidebar.header("⚙️ Opções de Visualização")
mostrar_manchas = st.sidebar.checkbox("Exibir manchas de abrangência/bairro", value=True)
raio_cobertura = st.sidebar.slider("Tamanho da Mancha (Raio em metros):", 500, 3000, 1200, 100)

busca = st.text_input("🔍 Pesquisar Local, Bairro ou Seção:", placeholder="Digite o nome do local ou bairro...")

df_filtrado = df_valid.copy()

if busca.strip():
    termo = busca.strip()
    cond = df_filtrado[col_local].astype(str).str.contains(termo, case=False, na=False) | \
           df_filtrado[col_secao].astype(str).str.contains(termo, case=False, na=False)
    if col_bairro:
        cond = cond | df_filtrado[col_bairro].astype(str).str.contains(termo, case=False, na=False)
    df_filtrado = df_filtrado[cond]

st.metric("Total de Locais Encontrados", f"{len(df_filtrado)} de {len(df_valid)}")

if not df_filtrado.empty:
    centro_lat = df_filtrado['LATITUDE'].mean()
    centro_lon = df_filtrado['LONGITUDE'].mean()
    zoom_inicial = 13 if busca.strip() else 11
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

# MANCHAS DE ABRANGÊNCIA / COBERTURA POR BAIRRO
if mostrar_manchas and not df_filtrado.empty:
    for idx, row in df_filtrado.reset_index().iterrows():
        lat = float(row['LATITUDE'])
        lon = float(row['LONGITUDE'])
        local = row.get(col_local, 'Local')
        cor = CORES_BAIRROS[idx % len(CORES_BAIRROS)]

        folium.Circle(
            location=[lat, lon],
            radius=raio_cobertura,
            color=cor,
            fill=True,
            fill_color=cor,
            fill_opacity=0.22,
            weight=1.5,
            popup=f"Área de Atendimento: {local}"
        ).add_to(m)

# MARCADORES NO MAPA
for idx, row in df_filtrado.reset_index().iterrows():
    lat = float(row['LATITUDE'])
    lon = float(row['LONGITUDE'])
    local = row.get(col_local, 'Local de Votação')
    secoes = row.get(col_secao, 'N/A')
    bairro_nome = row.get(col_bairro, 'Araruama') if col_bairro else 'Araruama'
    cor = CORES_BAIRROS[idx % len(CORES_BAIRROS)]
    link = row.get(col_link, f"https://www.google.com/maps/search/?api=1&query={lat},{lon}")

    popup_html = f"""
    <div style="font-family: Arial, sans-serif; font-size: 13px; width: 230px;">
        <span style="background-color: {cor}; color: white; padding: 3px 8px; border-radius: 10px; font-weight: bold; font-size: 11px;">
            {bairro_nome}
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
        radius=8,
        color="#000000",
        weight=1,
        fill=True,
        fill_color=cor,
        fill_opacity=0.9,
        popup=folium.Popup(popup_html, max_width=280),
        tooltip=f"{local} ({bairro_nome})"
    ).add_to(m)

map_key = f"map_{busca.strip()}_{raio_cobertura}_{len(df_filtrado)}"
st_folium(m, width="100%", height=550, key=map_key, returned_objects=[])
