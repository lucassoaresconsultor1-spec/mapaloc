import os
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster

st.set_page_config(page_title="Mapa de Votação - Araruama", page_icon="🗺️", layout="wide")

st.title("📍 Mapa de Locais de Votação e Seções")
st.markdown("Visão interativa da 92ª Zona Eleitoral de Araruama.")

# Coordenadas pré-mapeadas das escolas/locais de Araruama para evitar bloqueios do Google
COORDENADAS_ARARUAMA = {
    "PÇA E. COMTE. SÉRGIO RIBEIRO (PRAIA SECA)": (-22.93245, -42.30812),
    "E. M. ANDRÉ GOMES (BANANEIRAS)": (-22.86012, -42.31245),
    "FACULDADE UNILAGOS": (-22.87150, -42.33920),
    "E. M. VER. MOYSES RAMALHO (VILA CAPRI)": (-22.87890, -42.32510),
    "COLÉGIO ARARUAMA (CENTRO)": (-22.87320, -42.34210),
    "C. E. EDMUNDO SILVA (CENTRO)": (-22.87410, -42.34080),
    "E. M. E. FRANCISCO JOSÉ DE MARINS (MESTRE KIKO) – XV DE NOVEMBRO": (-22.88050, -42.33810),
    "E.M.E. MARGARIDA TRINDADE DE DEUS (FAZENDINHA)": (-22.88210, -42.35020),
    "E.E. CLARICE MOREIRA CALDAS (PONTE DOS LEITES)": (-22.85120, -42.31890),
    "E. M. JOÃO BRITO DE SOUZA (JARDIM SÃO PAULO)": (-22.86540, -42.34810),
    "PÇA E. M. PREF. AFRÂNIO VALLADARES - ITATIQUARA": (-22.83910, -42.29820),
    "CIEP 253 - GUIMARÃES ROSA (EDUCANDÁRIO)": (-22.86820, -42.33120),
    "ESCOLA PARATY (PARATY)": (-22.88910, -42.36100),
    "E.M. FRANCISCO D. NETO (BOA VISTA)": (-22.84100, -42.35200),
    "E.M. CELINA MESQUITA PEDROSA (IGUABINHA)": (-22.86100, -42.26100),
    "E.M. TONINHO SENRA (REGAMÉ)": (-22.87950, -42.35820),
    "E.M. DARCY RIBEIRO (PRAIA DO HOSPÍCIO)": (-22.88200, -42.33010),
    "PÇA E. DR. FERNANDO CARVALHO (FAZENDINHA)": (-22.88120, -42.34900),
    "E.M. BRUNNO NAMETALA (ENGENHO GRANDE)": (-22.83100, -42.36120),
    "E.M. SARA URRUTIA BATISTA (ENGENHO NOVO)": (-22.84210, -42.37890),
    "C. PROF. FERNANDO M. CALDAS (CENTRO)": (-22.87200, -42.34300),
    "E. M. PROF. NAIR VALLADARES": (-22.87520, -42.34120),
    "E. M. PRODÍGIO (PRODÍGIO)": (-22.78910, -42.39120),
    "E.M. HONORINO COUTINHO (MORRO GRANDE)": (-22.81200, -42.38100),
    "E. M. AGOSTINHO FRANCESCHI (AURORA)": (-22.82500, -42.37000),
    "E. M. JERÔNIMO CARLOS (PARACATU)": (-22.79800, -42.35100),
    "E. M. VER. EDEMUNDO PEREIRA DE SÁ CARVALHO - (LOT. SANTANA - SÃO VICENTE)": (-22.69800, -42.36200),
    "E.M. PROF. PEDRO PAULO (SÃO VICENTE)": (-22.69100, -42.36800),
    "E.M. FAUSTINA S. DE CARVALHO (NORIVAL CARVALHO - SÃO VICENTE)": (-22.68900, -42.37100),
    "E.M. JOÃO AUGUSTO CHAVES (SOBRADINHO - SÃO VICENTE)": (-22.71200, -42.38100),
    "CIEP 384 - GONÇALVES DIAS (SÃO VICENTE)": (-22.69500, -42.36500),
    "E.M. JOSÉ CORRÊA DA FONSECA (SÃO VICENTE)": (-22.69200, -42.36900),
    "E.M. NEDIR PAULO B. DA ROSA (POSSE)": (-22.75200, -42.32100),
    "E.M. SINVAL PINTO DE FIGUEIREDO (MUTIRÃO)": (-22.86800, -42.35500),
    "E.M. DR. JOÃO VASCONCELLOS (EDUCANDÁRIO)": (-22.86700, -42.33200),
    "E.M. PASTOR ALCEBÍADES (SOUBARA)": (-22.76800, -42.31100),
    "E.M. PROF. ORLANDO DIAS RIBEIRO (CENTRO)": (-22.87100, -42.34400),
    "CIEP 460 - THIOPHILA BRAGANÇA (CLUBE DOS ENGENHEIROS)": (-22.88500, -42.32100),
    "E.M. ANDERSON D. DE OLIVEIRA (TRÊS VENDAS)": (-22.81200, -42.29800),
    "E.M. PREF. ALTEVIR VIEIRA BARRETO (IGUABINHA)": (-22.85900, -42.25800),
    "E.M. RAYMUNDO M. CAMARÃO (PARATY)": (-22.88800, -42.36200),
    "E.M. BILINGUE SUELI AMARAL (PARQUE HOTEL)": (-22.87900, -42.33500),
    "C.E. SGT PM ANTONIO CARLOS DE OLIVEIRA DE MOURA (HOSPÍCIO)": (-22.88100, -42.32900),
    "E.M. BILÍNGUE GASTRONOMIA E HOTELARIA (PARQUE HOTEL)": (-22.87800, -42.33600)
}

@st.cache_data
def carregar_dados():
    nome_arquivo = "Eleições 2026 - 92ª Zona Eleitoral de Araruama.xlsx"
    if not os.path.exists(nome_arquivo):
        if os.path.exists("Eleições 2026 - 92ª Zona Eleitoral de Araruama_2.xlsx"):
            nome_arquivo = "Eleições 2026 - 92ª Zona Eleitoral de Araruama_2.xlsx"
            
    df = pd.read_excel(nome_arquivo)
    df.columns = [str(col).strip().upper() for col in df.columns]
    
    col_local = next((c for c in df.columns if 'LOCAL' in c), 'LOCAIS DE VOTAÇÃO')
    
    lats = []
    lons = []
    for _, row in df.iterrows():
        local = str(row[col_local]).strip()
        coords = COORDENADAS_ARARUAMA.get(local, (-22.8712, -42.3415))
        lats.append(coords[0])
        lons.append(coords[1])
        
    df['LATITUDE'] = lats
    df['LONGITUDE'] = lons
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

st.metric("Locais Exibidos no Mapa", f"{len(df_filtrado)} de {len(df)}")

# Mapa
centro_lat = df_filtrado['LATITUDE'].mean()
centro_lon = df_filtrado['LONGITUDE'].mean()

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
