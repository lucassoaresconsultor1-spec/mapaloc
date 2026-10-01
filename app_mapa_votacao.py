"""
Aplicação Streamlit: Locais de Votação da 92ª Zona Eleitoral de Araruama/RJ
===========================================================================
Lê o arquivo Excel 'Eleições 2026 - 92ª Zona Eleitoral de Araruama.xlsx' 
e renderiza mapa com filtros por seção eleitoral ou nome de escola.
"""

import os
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
from folium.plugins import Fullscreen, LocateControl

# ---------------------------------------------------------------------------
# 1. CONFIGURAÇÃO DA PÁGINA
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Locais de Votação - Araruama",
    page_icon="🗳️",
    layout="wide"
)

# ---------------------------------------------------------------------------
# 2. DICIONÁRIO DE COORDENADAS REAIS DOS LOCAIS
# ---------------------------------------------------------------------------
COORDENADAS_LOCAIS = {
    "PÇA E. COMTE. SÉRGIO RIBEIRO (PRAIA SECA)": (-22.9298, -42.3168),
    "E. M. ANDRÉ GOMES (BANANEIRAS)": (-22.8532, -42.3120),
    "FACULDADE UNILAGOS": (-22.8718, -42.3398),
    "E. M. VER. MOYSES RAMALHO (VILA CAPRI)": (-22.8598, -42.3195),
    "COLÉGIO ARARUAMA (CENTRO)": (-22.8732, -42.3421),
    "C. E. EDMUNDO SILVA (CENTRO)": (-22.8751, -42.3408),
    "E. M. E. FRANCISCO JOSÉ DE MARINS (MESTRE KIKO) – XV DE NOVEMBRO": (-22.8801, -42.3345),
    "E.M.E. MARGARIDA TRINDADE DE DEUS (FAZENDINHA)": (-22.8885, -42.3551),
    "E.E. CLARICE MOREIRA CALDAS (PONTE DOS LEITES)": (-22.8468, -42.2985),
    "E. M. JOÃO BRITO DE SOUZA (JARDIM SÃO PAULO)": (-22.8621, -42.3489),
    "PÇA E. M. PREF. AFRÂNIO VALLADARES - ITATIQUARA": (-22.8251, -42.3685),
    "CIEP 253 - GUIMARÃES ROSA (EDUCANDÁRIO)": (-22.8692, -42.3312),
    "ESCOLA PARATY (PARATY)": (-22.8633, -42.3210),
    "E.M. FRANCISCO D. NETO (BOA VISTA)": (-22.8123, -42.3150),
    "E.M. CELINA MESQUITA PEDROSA (IGUABINHA)": (-22.8589, -42.2215),
    "E.M. TONINHO SENRA (REGAMÉ)": (-22.8395, -42.2781),
    "E.M. DARCY RIBEIRO (PRAIA DO HOSPÍCIO)": (-22.8831, -42.3265),
    "PÇA E. DR. FERNANDO CARVALHO (FAZENDINHA)": (-22.8872, -42.3512),
    "E.M. BRUNNO NAMETALA (ENGENHO GRANDE)": (-22.8152, -42.3891),
    "E.M. SARA URRUTIA BATISTA (ENGENHO NOVO)": (-22.7981, -42.3654),
    "C. PROF. FERNANDO M. CALDAS (CENTRO)": (-22.8725, -42.3441),
    "E. M. PROF. NAIR VALLADARES": (-22.8745, -42.3385),
    "E. M. PRODÍGIO (PRODÍGIO)": (-22.7581, -42.3251),
    "E.M. HONORINO COUTINHO (MORRO GRANDE)": (-22.7812, -42.3411),
    "E. M. AGOSTINHO FRANCESCHI (AURORA)": (-22.7754, -42.2981),
    "E. M. JERÔNIMO CARLOS (PARACATU)": (-22.7321, -42.3125),
    "E. M. VER. EDEMUNDO PEREIRA DE SÁ CARVALHO - (LOT. SANTANA - SÃO VICENTE)": (-22.6981, -42.3651),
    "E.M. PROF. PEDRO PAULO (SÃO VICENTE)": (-22.6912, -42.3621),
    "E.M. FAUSTINA S. DE CARVALHO (NORIVAL CARVALHO - SÃO VICENTE)": (-22.6851, -42.3581),
    "E.M. JOÃO AUGUSTO CHAVES (SOBRADINHO - SÃO VICENTE)": (-22.6712, -42.3421),
    "CIEP 384 - GONÇALVES DIAS (SÃO VICENTE)": (-22.6931, -42.3611),
    "E.M. JOSÉ CORRÊA DA FONSECA (SÃO VICENTE)": (-22.6891, -42.3598),
    "E.M. NEDIR PAULO B. DA ROSA (POSSE)": (-22.7211, -42.3812),
    "E.M. SINVAL PINTO DE FIGUEIREDO (MUTIRÃO)": (-22.8651, -42.3412),
    "E.M. DR. JOÃO VASCONCELLOS (EDUCANDÁRIO)": (-22.8681, -42.3325),
    "E.M. PASTOR ALCEBÍADES (SOUBARA)": (-22.7612, -42.3891),
    "E.M. PROF. ORLANDO DIAS RIBEIRO (CENTRO)": (-22.8762, -42.3415),
    "CIEP 460 - THIOPHILA BRAGANÇA (CLUBE DOS ENGENHEIROS)": (-22.8612, -42.3581),
    "E.M. ANDERSON D. DE OLIVEIRA (TRÊS VENDAS)": (-22.7912, -42.2851),
    "E.M. PREF. ALTEVIR VIEIRA BARRETO (IGUABINHA)": (-22.8564, -42.2281),
    "E.M. RAYMUNDO M. CAMARÃO (PARATY)": (-22.8621, -42.3225),
    "E.M. BILINGUE SUELI AMARAL (PARQUE HOTEL)": (-22.8791, -42.3281),
    "C.E. SGT PM ANTONIO CARLOS DE OLIVEIRA DE MOURA (HOSPÍCIO)": (-22.8821, -42.3251),
    "E.M. BILÍNGUE GASTRONOMIA E HOTELARIA (PARQUE HOTEL)": (-22.8781, -42.3295),
}

# ---------------------------------------------------------------------------
# 3. LEITURA E TRATAMENTO DOS DADOS DO EXCEL
# ---------------------------------------------------------------------------
@st.cache_data
def carregar_dados():
    file_name = "Eleições 2026 - 92ª Zona Eleitoral de Araruama.xlsx"
    
    if not os.path.exists(file_name):
        st.error(f"O arquivo `{file_name}` não foi encontrado na raiz do projeto.")
        st.stop()
        
    df = pd.read_excel(file_name)
    df.columns = [col.strip().upper() for col in df.columns]

    def processar_secoes(val):
        if pd.isna(val):
            return []
        partes = str(val).replace(" ", "").split("-")
        return [p for p in partes if p]

    df["SECOES_LISTA"] = df["SEÇÕES"].apply(processar_secoes)
    df["QTD_SECOES"] = df["SECOES_LISTA"].apply(len)
    return df

# ---------------------------------------------------------------------------
# 4. EXECUÇÃO PRINCIPAL
# ---------------------------------------------------------------------------
def main():
    st.title("🗳️ Mapeamento de Locais de Votação – Araruama/RJ")
    st.subheader("92ª Zona Eleitoral")

    df = carregar_dados()

    # Campo de busca no topo
    termo = st.text_input(
        "🔎 Pesquisar por número da Seção ou nome do Local/Bairro",
        placeholder="Ex: 001 ou Praia Seca"
    ).strip()

    # Filtro dinâmico
    if termo:
        if termo.isdigit():
            secao_formatada = termo.zfill(3)
            mask = df["SECOES_LISTA"].apply(lambda lista: secao_formatada in lista)
        else:
            mask = df["LOCAIS DE VOTAÇÃO"].str.contains(termo, case=False, na=False)
        df_filtrado = df[mask]
    else:
        df_filtrado = df

    # Indicadores em Destaque
    m1, m2 = st.columns(2)
    m1.metric("Locais Encontrados", len(df_filtrado))
    m2.metric("Total de Seções Exibidas", df_filtrado["QTD_SECOES"].sum())

    # Inicialização do Mapa Folium
    mapa = folium.Map(location=[-22.8730, -42.3430], zoom_start=11)
    Fullscreen().add_to(mapa)
    LocateControl().add_to(mapa)

    pontos = []
    for _, row in df_filtrado.iterrows():
        local_nome = row["LOCAIS DE VOTAÇÃO"]
        link_maps = row["LINK"]
        secoes_str = ", ".join(row["SECOES_LISTA"])
        
        # Pega a coordenada cadastrada no dicionário ou usa o centro como fallback
        coords = COORDENADAS_LOCAIS.get(local_nome, (-22.8730, -42.3430))
        pontos.append(coords)

        popup_content = f"""
        <div style="font-family: Arial, sans-serif; width: 260px;">
            <h4 style="margin: 0 0 8px 0; color: #1E3A8A;">{local_nome}</h4>
            <p style="margin: 0 0 8px 0; font-size: 13px;"><b>Seções ({row['QTD_SECOES']}):</b><br>{secoes_str}</p>
            <a href="{link_maps}" target="_blank" style="
                background-color: #2563EB; 
                color: white; 
                padding: 6px 12px; 
                text-decoration: none; 
                display: inline-block; 
                border-radius: 4px;
                font-size: 12px;
                font-weight: bold;
            ">📍 Abrir no Google Maps</a>
        </div>
        """

        folium.Marker(
            location=coords,
            tooltip=local_nome,
            popup=folium.Popup(popup_content, max_width=300),
            icon=folium.Icon(color="red" if termo else "blue", icon="info-sign")
        ).add_to(mapa)

    # Ajusta o zoom automaticamente para enquadrar os pontos pesquisados
    if pontos:
        mapa.fit_bounds(pontos, padding=(30, 30))

    # Renderiza o Mapa no Streamlit
    st_folium(mapa, height=520, use_container_width=True, returned_objects=[])

    # Tabela com o conteúdo lido diretamente do Excel
    with st.expander("📋 Tabela Completa dos Dados", expanded=bool(termo)):
        st.dataframe(
            df_filtrado[["LOCAIS DE VOTAÇÃO", "QTD_SECOES", "SEÇÕES", "LINK"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "LOCAIS DE VOTAÇÃO": "Local de Votação",
                "QTD_SECOES": "Seções",
                "SEÇÕES": "Relação de Seções",
                "LINK": st.column_config.LinkColumn("Google Maps", display_text="Ver no Mapa")
            }
        )

if __name__ == "__main__":
    main()
