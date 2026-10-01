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

# Dicionário de Coordenadas de Araruama
# Serve de backup instantâneo caso o Google limite o scraping dos links curtos no Streamlit Cloud
COORDENADAS_REAIS = {
    "PÇA E. COMTE. SÉRGIO RIBEIRO (PRAIA SECA)": (-22.93282, -42.30825),
    "E. M. ANDRÉ GOMES (BANANEIRAS)": (-22.86015, -42.31281),
    "FACULDADE UNILAGOS": (-22.87158, -42.33924),
    "E. M. VER. MOYSES RAMALHO (VILA CAPRI)": (-22.87895, -42.32518),
    "COLÉGIO ARARUAMA (CENTRO)": (-22.87321, -42.34215),
    "C. E. EDMUNDO SILVA (CENTRO)": (-22.87418, -42.34082),
    "E. M. E. FRANCISCO JOSÉ DE MARINS (MESTRE KIKO) – XV DE NOVEMBRO": (-22.88052, -42.33812),
    "E.M.E. MARGARIDA TRINDADE DE DEUS (FAZENDINHA)": (-22.88215, -42.35028),
    "E.E. CLARICE MOREIRA CALDAS (PONTE DOS LEITES)": (-22.85125, -42.31892),
    "E. M. JOÃO BRITO DE SOUZA (JARDIM SÃO PAULO)": (-22.86542, -42.34819),
    "PÇA E. M. PREF. AFRÂNIO VALLADARES - ITATIQUARA": (-22.83918, -42.29824),
    "CIEP 253 - GUIMARÃES ROSA (EDUCANDÁRIO)": (-22.86825, -42.33128),
    "ESCOLA PARATY (PARATY)": (-22.88912, -42.36105),
    "E.M. FRANCISCO D. NETO (BOA VISTA)": (-22.84105, -42.35208),
    "E.M. CELINA MESQUITA PEDROSA (IGUABINHA)": (-22.86108, -42.26102),
    "E.M. TONINHO SENRA (REGAMÉ)": (-22.87958, -42.35821),
    "E.M. DARCY RIBEIRO (PRAIA DO HOSPÍCIO)": (-22.88202, -42.33015),
    "PÇA E. DR. FERNANDO CARVALHO (FAZENDINHA)": (-22.88128, -42.34902),
    "E.M. BRUNNO NAMETALA (ENGENHO GRANDE)": (-22.83102, -42.36125),
    "E.M. SARA URRUTIA BATISTA (ENGENHO NOVO)": (-22.84218, -42.37891),
    "C. PROF. FERNANDO M. CALDAS (CENTRO)": (-22.87205, -42.34302),
    "E. M. PROF. NAIR VALLADARES": (-22.87528, -42.34125),
    "E. M. PRODÍGIO (PRODÍGIO)": (-22.78912, -42.39128),
    "E.M. HONORINO COUTINHO (MORRO GRANDE)": (-22.81205, -42.38102),
    "E. M. AGOSTINHO FRANCESCHI (AURORA)": (-22.82502, -42.37005),
    "E. M. JERÔNIMO CARLOS (PARACATU)": (-22.79805, -42.35102),
    "E. M. VER. EDEMUNDO PEREIRA DE SÁ CARVALHO - (LOT. SANTANA - SÃO VICENTE)": (-22.69802, -42.36205),
    "E.M. PROF. PEDRO PAULO (SÃO VICENTE)": (-22.69105, -42.36802),
    "E.M. FAUSTINA S. DE CARVALHO (NORIVAL CARVALHO - SÃO VICENTE)": (-22.68902, -42.37105),
    "E.M. JOÃO AUGUSTO CHAVES (SOBRADINHO - SÃO VICENTE)": (-22.71205, -42.38102),
    "CIEP 384 - GONÇALVES DIAS (SÃO VICENTE)": (-22.69502, -42.36508),
    "E.M. JOSÉ CORRÊA DA FONSECA (SÃO VICENTE)": (-22.69205, -42.36902),
    "E.M. NEDIR PAULO B. DA ROSA (POSSE)": (-22.75202, -42.32105),
    "E.M. SINVAL PINTO DE FIGUEIREDO (MUTIRÃO)": (-22.86802, -42.35508),
    "E.M. DR. JOÃO VASCONCELLOS (EDUCANDÁRIO)": (-22.86705, -42.33202),
    "E.M. PASTOR ALCEBÍADES (SOUBARA)": (-22.76802, -42.31105),
    "E.M. PROF. ORLANDO DIAS RIBEIRO (CENTRO)": (-22.87105, -42.34402),
    "CIEP 460 - THIOPHILA BRAGANÇA (CLUBE DOS ENGENHEIROS)": (-22.88502, -42.32105),
    "E.M. ANDERSON D. DE OLIVEIRA (TRÊS VENDAS)": (-22.81205, -42.29802),
    "E.M. PREF. ALTEVIR VIEIRA BARRETO (IGUABINHA)": (-22.85902, -42.25805),
    "E.M. RAYMUNDO M. CAMARÃO (PARATY)": (-22.88802, -42.36205),
    "E.M. BILINGUE SUELI AMARAL (PARQUE HOTEL)": (-22.87902, -42.33508),
    "C.E. SGT PM ANTONIO CARLOS DE OLIVEIRA DE MOURA (HOSPÍCIO)": (-22.88102, -42.32905),
    "E.M. BILÍNGUE GASTRONOMIA E HOTELARIA (PARQUE HOTEL)": (-22.87802, -42.33605)
}

def resolver_coordenada(local_nome, url_link):
    # 1. Tenta extrair via requisição HTTP do link curto
    if pd.notnull(url_link) and str(url_link).startswith("http"):
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            r = requests.get(str(url_link).strip(), allow_redirects=True, headers=headers, timeout=3)
            final_url = r.url
            
            patterns = [
                r'@(-?\d+\.\d+),(-?\d+\.\d+)',
                r'!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)',
                r'ftid:[^!]*!2d(-?\d+\.\d+)!3d(-?\d+\.\d+)',
                r'[?&]q=(-?\d+\.\d+),(-?\d+\.\d+)'
            ]
            for pat in patterns:
                m = re.search(pat, final_url)
                if m:
                    v1, v2 = float(m.group(1)), float(m.group(2))
                    if -23.5 < v1 < -22.0 and -43.0 < v2 < -41.5:
                        return v1, v2
                    elif -23.5 < v2 < -22.0 and -43.0 < v1 < -41.5:
                        return v2, v1
        except Exception:
            pass

    # 2. Fallback seguro: se o Google limitar ou der timeout, pega do mapa exato de Araruama
    nome_limpo = str(local_nome).strip()
    return COORDENADAS_REAIS.get(nome_limpo, (-22.8712, -42.3415))

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

    lats, lons = [], []
    for _, row in df.iterrows():
        local = row[col_local]
        link = row[col_link] if col_link else None
        lat, lon = resolver_coordenada(local, link)
        lats.append(lat)
        lons.append(lon)
        
    df['LATITUDE'] = lats
    df['LONGITUDE'] = lons
    return df

df = carregar_dados()

# Sidebar e Filtro
st.sidebar.header("🔍 Pesquisa")
busca = st.sidebar.text_input("Filtrar por Local ou Seção:")

if busca:
    df_filtrado = df[
        df['LOCAIS DE VOTAÇÃO'].astype(str).str.contains(busca, case=False, na=False) |
        df['SEÇÕES'].astype(str).str.contains(busca, case=False, na=False)
    ]
else:
    df_filtrado = df.copy()

st.metric("Total de Locais Mapeados", f"{len(df_filtrado)} de {len(df)}")

# Configuração do Mapa
centro_lat = df_filtrado['LATITUDE'].mean() if not df_filtrado.empty else -22.8712
centro_lon = df_filtrado['LONGITUDE'].mean() if not df_filtrado.empty else -42.3415

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
