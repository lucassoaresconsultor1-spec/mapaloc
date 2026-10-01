import os
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster

# Configuração da página do Streamlit
st.set_page_config(
    page_title="Mapa de Votação - Araruama",
    page_icon="🗺️",
    layout="wide"
)

st.title("📍 Mapa de Locais de Votação e Seções")
st.markdown("Visão interativa dos locais de votação da 92ª Zona Eleitoral.")

# -----------------------------------------------------------------------------
# 1. FUNÇÃO PARA CARREGAR E TRATAR OS DADOS
# -----------------------------------------------------------------------------
@st.cache_data
def carregar_dados():
    nome_arquivo = "Eleições 2026 - 92ª Zona Eleitoral de Araruama.xlsx"
    
    # Verifica se o arquivo existe na pasta/repositório
    if not os.path.exists(nome_arquivo):
        st.error(f"⚠️ O arquivo `{nome_arquivo}` não foi encontrado no repositório GitHub!")
        st.stop()
        
    # Leitura do arquivo Excel
    df = pd.read_excel(nome_arquivo)
    
    # Padronização dos nomes das colunas (maiúsculas e sem espaços extras)
    df.columns = [str(col).strip().upper() for col in df.columns]
    
    # Garantir que LATITUDE e LONGITUDE sejam tratadas corretamente
    # (substitui vírgula por ponto e converte para float)
    if 'LATITUDE' in df.columns and 'LONGITUDE' in df.columns:
        df['LATITUDE'] = (
            df['LATITUDE']
            .astype(str)
            .str.replace(',', '.')
            .str.strip()
        )
        df['LONGITUDE'] = (
            df['LONGITUDE']
            .astype(str)
            .str.replace(',', '.')
            .str.strip()
        )
        
        df['LATITUDE'] = pd.to_numeric(df['LATITUDE'], errors='coerce')
        df['LONGITUDE'] = pd.to_numeric(df['LONGITUDE'], errors='coerce')
        
        # Filtro de segurança: remove linhas sem coordenadas válidas
        df = df.dropna(subset=['LATITUDE', 'LONGITUDE'])
        
        # Filtro de coordenadas plausíveis para o estado do Rio / Araruama
        # (evita pontos zerados ou invertidos que caem no meio do oceano)
        df = df[
            (df['LATITUDE'] < -20.0) & (df['LATITUDE'] > -24.0) &
            (df['LONGITUDE'] < -40.0) & (df['LONGITUDE'] > -45.0)
        ]
    else:
        st.error("⚠️ As colunas 'LATITUDE' e 'LONGITUDE' não foram encontradas na planilha!")
        st.stop()
        
    return df

# Carregar os dados
df = carregar_dados()

# -----------------------------------------------------------------------------
# 2. PAINEL LATERAL (FILTROS)
# -----------------------------------------------------------------------------
st.sidebar.header("🔍 Filtros")

# Filtro por Local de Votação (se a coluna existir)
coluna_local = next((col for col in ['LOCAL', 'LOCAL_VOTACAO', 'NOME_LOCAL', 'ESCOLA'] if col in df.columns), None)

if coluna_local:
    locais_disponiveis = ["Todos"] + sorted(df[coluna_local].dropna().unique().tolist())
    local_selecionado = st.sidebar.selectbox("Selecione o Local de Votação:", locais_disponiveis)
    
    if local_selecionado != "Todos":
        df_filtrado = df[df[coluna_local] == local_selecionado]
    else:
        df_filtrado = df.copy()
else:
    df_filtrado = df.copy()

# Métricas rápidas
col1, col2 = st.columns(2)
with col1:
    st.metric("Total de Locais Exibidos", len(df_filtrado))
with col2:
    if 'SEÇÕES' in df_filtrado.columns:
        st.metric("Total de Seções Registradas", df_filtrado['SEÇÕES'].astype(str).nunique())

# -----------------------------------------------------------------------------
# 3. CRIAÇÃO DO MAPA INTERATIVO (FOLIUM)
# -----------------------------------------------------------------------------
# Coordenadas centrais aproximadas de Araruama
centro_lat = -22.8712
centro_lon = -42.3415

# Se houver dados filtrados, centraliza o mapa na média dos pontos exibidos
if not df_filtrado.empty:
    centro_lat = df_filtrado['LATITUDE'].mean()
    centro_lon = df_filtrado['LONGITUDE'].mean()

# Criar o objeto de mapa
m = folium.Map(
    location=[centro_lat, centro_lon],
    zoom_start=13,
    tiles="OpenStreetMap"
)

# Adicionar o MarkerCluster para agrupar marcadores próximos e evitar sobreposição
marker_cluster = MarkerCluster().add_to(m)

# Adicionar os marcadores no mapa
for _, row in df_filtrado.iterrows():
    lat = row['LATITUDE']
    lon = row['LONGITUDE']
    
    nome_local = row[coluna_local] if coluna_local else "Local de Votação"
    bairro = row.get('BAIRRO', 'Araruama')
    secoes = row.get('SEÇÕES', 'N/A')
    
    # Link direto e funcional para abrir no aplicativo do Google Maps no celular
    gmaps_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
    
    # HTML formatado para o popup do marcador
    popup_html = f"""
    <div style="font-family: Arial, sans-serif; font-size: 13px; width: 220px;">
        <h4 style="margin: 0 0 5px 0; color: #1E88E5;">{nome_local}</h4>
        <b>Bairro:</b> {bairro}<br>
        <b>Seções:</b> {secoes}<br><br>
        <a href="{gmaps_url}" target="_blank" 
           style="background-color: #4CAF50; color: white; padding: 6px 12px; 
                  text-decoration: none; border-radius: 4px; display: inline-block; 
                  font-weight: bold; text-align: center;">
            🗺️ Abrir no Google Maps
        </a>
    </div>
    """
    
    folium.Marker(
        location=[lat, lon],  # Ordem estrita [LATITUDE, LONGITUDE]
        popup=folium.Popup(popup_html, max_width=280),
        tooltip=str(nome_local),
        icon=folium.Icon(color="blue", icon="info-sign")
    ).add_to(marker_cluster)

# Renderizar o mapa dentro do Streamlit
st_folium(m, width="100%", height=550)
