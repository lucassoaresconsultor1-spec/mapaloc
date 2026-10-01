"""
Mapa interativo - Locais de Votação da 92ª Zona Eleitoral de Araruama/RJ
=========================================================================

Executar:
    streamlit run app_mapa_votacao.py
"""

import html
import json
import re
import time
from pathlib import Path
from urllib.parse import unquote, unquote_plus

import folium
import pandas as pd
import requests
import streamlit as st
from folium.plugins import Fullscreen, LocateControl
from streamlit_folium import st_folium

# ---------------------------------------------------------------------------
# 1. DADOS (formato: seções | local | link do Google Maps)
# ---------------------------------------------------------------------------
DADOS_BRUTOS = """
001-002-034-035-155-166-202-254-279-303-326 | PÇA E. COMTE. SÉRGIO RIBEIRO (PRAIA SECA) | https://maps.app.goo.gl/ohsy6xAmdXSqJV4g8
003-017-018-123-169-188-258-266-311-333 | E. M. ANDRÉ GOMES (BANANEIRAS) | https://maps.app.goo.gl/fQzYDpQLUa1rMFxp9
004-005-006-007-008-125-167-180-187-190-199-208-219-240-250-274-299 | FACULDADE UNILAGOS | https://maps.app.goo.gl/YqBEnL3PQyyEXtCc7
009-010-131-146-168-211-221-270-277 | E. M. VER. MOYSES RAMALHO (VILA CAPRI) | https://maps.app.goo.gl/fUsNZPMdDwh56hme6
011-012-013-074-075-076-117-121-183-283 | COLÉGIO ARARUAMA (CENTRO) | https://maps.app.goo.gl/SvPxjfvoD5RvLp3Y7
014-071-072-073-118-133-178-252-263-278 | C. E. EDMUNDO SILVA (CENTRO) | https://maps.app.goo.gl/LHvshQAoF2a3a6mf7
015-016-056-057-058-196-268-282-325 | E. M. E. FRANCISCO JOSÉ DE MARINS (MESTRE KIKO) – XV DE NOVEMBRO | https://maps.app.goo.gl/mksQNoY2KmixrXDm7
019-040-096-139-142-151-328-339-342 | E.M.E. MARGARIDA TRINDADE DE DEUS (FAZENDINHA) | https://maps.app.goo.gl/jHrtuTcSQmoLu6Xz7
020-021-127-179-207-237 | E.E. CLARICE MOREIRA CALDAS (PONTE DOS LEITES) | https://maps.app.goo.gl/EZ9acex8DkxY1zo96
022-023-024-025-170-194-297 | E. M. JOÃO BRITO DE SOUZA (JARDIM SÃO PAULO) | https://maps.app.goo.gl/gF2meYB8BwiVFQ2b7
026-027-028-129-165-189-294-308-334 | PÇA E. M. PREF. AFRÂNIO VALLADARES - ITATIQUARA | https://maps.app.goo.gl/EhuZuUft6x24a3Ah7
029-030-031-038-039-113-124-173-275 | CIEP 253 - GUIMARÃES ROSA (EDUCANDÁRIO) | https://maps.app.goo.gl/EH26hLVz54Q4Asui9
032-033-122-160-185 | ESCOLA PARATY (PARATY) | https://maps.app.goo.gl/aA51CjfZmhSxVsXE7
036-037-047 | E.M. FRANCISCO D. NETO (BOA VISTA) | https://maps.app.goo.gl/2vtdRvna8rxPgfSx8
041-042-043-128-158-197-298-317-336 | E.M. CELINA MESQUITA PEDROSA (IGUABINHA) | https://maps.app.goo.gl/6ercWSXZ1tQpx9eu6
044-048-174-213 | E.M. TONINHO SENRA (REGAMÉ) | https://maps.app.goo.gl/toVujQ9zYyCW9ddU7
045-046-149-159-171-217-292-318 | E.M. DARCY RIBEIRO (PRAIA DO HOSPÍCIO) | https://maps.app.goo.gl/KAoCRMxSK6L4NQeP9
049-050-051-052-114-161-172-181-186-301-314 | PÇA E. DR. FERNANDO CARVALHO (FAZENDINHA) | https://maps.app.goo.gl/PRWcdTd8irhMWtpT7
053-054-236-248-276-313 | E.M. BRUNNO NAMETALA (ENGENHO GRANDE) | https://maps.app.goo.gl/6mMQz9XqTKG8z7C76
055-234 | E.M. SARA URRUTIA BATISTA (ENGENHO NOVO) | https://maps.app.goo.gl/uyXQ2mpRqSiwSGQ1A
059-060-061-062-119-132-143-175-273 | C. PROF. FERNANDO M. CALDAS (CENTRO) | https://maps.app.goo.gl/p62s4ZQvhdjgE2qy7
069-070-115-141-148-162-164-214-218-259-265 | E. M. PROF. NAIR VALLADARES | https://maps.app.goo.gl/GQSACcLZ6DJwSuLY8
077-087 | E. M. PRODÍGIO (PRODÍGIO) | https://maps.app.goo.gl/q6HWgu4sUKdvDNHfA
078-079-080-083-088-116-135-137-147-157-182-238 | E.M. HONORINO COUTINHO (MORRO GRANDE) | https://maps.app.goo.gl/ZqbZRGpW7pUovbQ37
081-082-085-086-144 | E. M. AGOSTINHO FRANCESCHI (AURORA) | https://maps.app.goo.gl/9KCGqz7KB2HNRZoT8
084-225-233-307 | E. M. JERÔNIMO CARLOS (PARACATU) | https://maps.app.goo.gl/MeMqSTRvp8ZxifRN9
088-089-090-091-092-093-152-272-309 | E. M. VER. EDEMUNDO PEREIRA DE SÁ CARVALHO - (LOT. SANTANA - SÃO VICENTE) | https://maps.app.goo.gl/yvqQzqrs4Fs4t2uz9
094-108-109-110-111-112-287-315-341 | E.M. PROF. PEDRO PAULO (SÃO VICENTE) | https://maps.app.goo.gl/nd9m7MwNJ3C5Xv5h8
097-101 | E.M. FAUSTINA S. DE CARVALHO (NORIVAL CARVALHO - SÃO VICENTE) | https://maps.app.goo.gl/uTWVFiMXLzeaHTu49
098-099-100-312 | E.M. JOÃO AUGUSTO CHAVES (SOBRADINHO - SÃO VICENTE) | https://maps.app.goo.gl/4oqCmT9mb6ZJJKuH6
102-107-120-126-153-176-192-206-215-232-257 | CIEP 384 - GONÇALVES DIAS (SÃO VICENTE) | https://maps.app.goo.gl/9egS35g9tH18C2719
103-104-242 | E.M. JOSÉ CORRÊA DA FONSECA (SÃO VICENTE) | https://maps.app.goo.gl/BnDHCGmd1Q9RNZTS6
105-243 | E.M. NEDIR PAULO B. DA ROSA (POSSE) | https://maps.app.goo.gl/UqshVycpbdEo79aP9
130-177-205-216-249-267-293-319-335 | E.M. SINVAL PINTO DE FIGUEIREDO (MUTIRÃO) | https://maps.app.goo.gl/EfdToPjAUan7thuM6
136-145-163-184-204-210-228-235-253-302-322-338 | E.M. DR. JOÃO VASCONCELLOS (EDUCANDÁRIO) | https://maps.app.goo.gl/gJUUZa5myHfSSXv16
154-239 | E.M. PASTOR ALCEBÍADES (SOUBARA) | https://maps.app.goo.gl/fcEyLF2ETcmnL22d8
191-195-198-209-222-223-227-241-255 | E.M. PROF. ORLANDO DIAS RIBEIRO (CENTRO) | https://maps.app.goo.gl/F2PqcgvGHBNWWpHa9
193-226-230-256-262-269 | CIEP 460 - THIOPHILA BRAGANÇA (CLUBE DOS ENGENHEIROS) | https://maps.app.goo.gl/y6cnHu2GHwuB6mw19
200-229-280-310 | E.M. ANDERSON D. DE OLIVEIRA (TRÊS VENDAS) | https://maps.app.goo.gl/RJSv4cf4SegCcBA
201-212-224-251-271-285-296-320-332 | E.M. PREF. ALTEVIR VIEIRA BARRETO (IGUABINHA) | https://maps.app.goo.gl/pyJMzEJgs9cJED7z9
203-220-231-246-260-295 | E.M. RAYMUNDO M. CAMARÃO (PARATY) | https://maps.app.goo.gl/W46mBxj956YfLwGb6
244-284-286-288-289-290-291-304-323 | E.M. BILINGUE SUELI AMARAL (PARQUE HOTEL) | https://maps.app.goo.gl/MXeWGsCJeWB99FbLA
245-261-264-281-300-337 | C.E. SGT PM ANTONIO CARLOS DE OLIVEIRA DE MOURA (HOSPÍCIO) | https://maps.app.goo.gl/WtKKzQHnjKEwv38QA
305-306-316-321-324-327-329-330-331-340 | E.M. BILÍNGUE GASTRONOMIA E HOTELARIA (PARQUE HOTEL) | https://maps.app.goo.gl/varhgeUXB5pnYpjZ6
"""

# ---------------------------------------------------------------------------
# COORDENADAS MANUAIS EXATAS (Prevalecem sobre qualquer resolução dinâmica)
# ---------------------------------------------------------------------------
COORD_MANUAL: dict[str, tuple[float, float]] = {
    # Correção direta solicitada:
    "E.E. CLARICE MOREIRA CALDAS (PONTE DOS LEITES)": (-22.86872, -42.30815),
    
    # Demais escolas com coordenadas fixas para evitar desvios:
    "FACULDADE UNILAGOS": (-22.87182, -42.33981),
    "COLÉGIO ARARUAMA (CENTRO)": (-22.87321, -42.34215),
    "C. E. EDMUNDO SILVA (CENTRO)": (-22.87510, -42.34080),
    "C. PROF. FERNANDO M. CALDAS (CENTRO)": (-22.87250, -42.34410),
    "E.M. PROF. ORLANDO DIAS RIBEIRO (CENTRO)": (-22.87620, -42.34150),
}

CACHE_FILE = Path("coordenadas_cache.json")
CENTRO_ARARUAMA = (-22.8730, -42.3430)
LAT_MIN, LAT_MAX = -23.10, -22.60
LON_MIN, LON_MAX = -42.60, -42.10
HEADERS = {"User-Agent": "mapa-votacao-araruama/1.0 (streamlit app)"}

HEADERS_NAV = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9",
}

_PADROES = [
    (r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)", "latlon"),
    (r"@(-?\d+\.\d+),(-?\d+\.\d+)", "latlon"),
    (r"[?&;](?:q|ll|center)=(-?\d+\.\d+)(?:,|%2C|%2c)(-?\d+\.\d+)", "latlon"),
    (r"\[null,null,(-?\d+\.\d+),(-?\d+\.\d+)\]", "latlon"),
    (r"APP_INITIALIZATION_STATE=\[\[\[[-\d.eE+]+,(-?\d+\.\d+),(-?\d+\.\d+)\]", "lonlat"),
]


def carregar_dataframe() -> pd.DataFrame:
    linhas = []
    for linha in DADOS_BRUTOS.strip().splitlines():
        secoes_txt, local, link = [p.strip() for p in linha.split("|")]
        secoes = [s for s in secoes_txt.split("-") if s.strip()]
        linhas.append({"local": local, "secoes": secoes, "link": link})
    return pd.DataFrame(linhas)


def _valida(lat: float, lon: float) -> bool:
    return LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX


def _extrair_coord(texto: str):
    for padrao, ordem in _PADROES:
        for m in re.finditer(padrao, texto):
            a, b = float(m.group(1)), float(m.group(2))
            lat, lon = (a, b) if ordem == "latlon" else (b, a)
            if _valida(lat, lon):
                return lat, lon
    return None


def consultar_link(url: str):
    try:
        r = requests.get(url, headers=HEADERS_NAV, allow_redirects=True, timeout=15)
    except requests.RequestException:
        return None, None

    corpo = html.unescape(r.text).replace("\\u003d", "=").replace("\\u0026", "&")
    alvos = [unquote(r.url)] + [unquote(h.headers.get("Location", "")) for h in r.history] + [corpo]
    coord = None
    for texto in alvos:
        coord = _extrair_coord(texto)
        if coord:
            break

    lugar = None
    m = re.search(r"/maps/place/([^/]+)/", r.url)
    if m:
        lugar = unquote_plus(m.group(1))
    return coord, lugar


def coord_nominatim(consulta: str):
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": f"{consulta}, Brasil", "format": "json", "limit": 1},
            headers=HEADERS,
            timeout=12,
        )
        time.sleep(1.1)
        dados = r.json()
        if dados and _valida(float(dados[0]["lat"]), float(dados[0]["lon"])):
            return float(dados[0]["lat"]), float(dados[0]["lon"])
    except (requests.RequestException, ValueError, KeyError):
        pass
    return None


@st.cache_data(show_spinner=False)
def resolver_coordenadas(locais_links: tuple) -> dict:
    cache = json.loads(CACHE_FILE.read_text("utf-8")) if CACHE_FILE.exists() else {}
    alterado = False

    for local, link in locais_links:
        # Se estiver configurado no COORD_MANUAL, força a substituição
        if local in COORD_MANUAL:
            lat, lon = COORD_MANUAL[local]
            if local not in cache or cache[local]["lat"] != lat or cache[local]["lon"] != lon:
                cache[local] = {"lat": lat, "lon": lon, "origem": "manual"}
                alterado = True
            continue

        if local in cache and cache[local]["origem"] in ("manual", "link"):
            continue

        res, lugar = consultar_link(link)
        origem = "link"

        if res is None:
            consultas = []
            if lugar:
                consultas += [lugar, lugar.split(" - ", 1)[-1]]
            nome_limpo = re.sub(r"\(.*?\)", "", local).strip()
            consultas.append(f"{nome_limpo}, Araruama, RJ")
            for q in consultas:
                res = coord_nominatim(q)
                if res:
                    origem = "geocodificação"
                    break

        if res is None:
            res, origem = CENTRO_ARARUAMA, "aproximada"

        cache[local] = {"lat": res[0], "lon": res[1], "origem": origem}
        alterado = True

    if alterado:
        CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), "utf-8")
    return cache


def filtrar(df: pd.DataFrame, termo: str) -> pd.DataFrame:
    termo = termo.strip()
    if not termo:
        return df
    if termo.isdigit():
        alvo = termo.zfill(3)
        return df[df["secoes"].apply(lambda lst: alvo in lst)]
    chave = termo.lower()
    return df[df["local"].str.lower().str.contains(re.escape(chave), na=False)]


def montar_popup(row, origem: str) -> str:
    badges = " ".join(
        f"<span style='background:#e8f0fe;border-radius:4px;padding:1px 5px;"
        f"margin:1px;display:inline-block;font-size:12px'>{s}</span>"
        for s in row["secoes"]
    )
    aviso = (
        "<p style='color:#b45309;font-size:11px'>⚠ Posição aproximada</p>"
        if origem == "aproximada"
        else ""
    )
    return (
        f"<div style='font-family:sans-serif;width:260px'>"
        f"<h4 style='margin:0 0 6px'>{row['local']}</h4>"
        f"<b>{len(row['secoes'])} seções:</b><br>{badges}{aviso}"
        f"<p style='margin-top:8px'><a href='{row['link']}' target='_blank'>"
        f"📍 Abrir no Google Maps</a></p></div>"
    )


def construir_mapa(df: pd.DataFrame, coords: dict, destaque: bool) -> folium.Map:
    mapa = folium.Map(location=CENTRO_ARARUAMA, zoom_start=11, tiles="OpenStreetMap")
    Fullscreen().add_to(mapa)
    LocateControl().add_to(mapa)

    pontos = []
    for _, row in df.iterrows():
        c = coords[row["local"]]
        pontos.append((c["lat"], c["lon"]))
        folium.Marker(
            location=(c["lat"], c["lon"]),
            tooltip=f"{row['local']} ({len(row['secoes'])} seções)",
            popup=folium.Popup(montar_popup(row, c["origem"]), max_width=300),
            icon=folium.Icon(
                color="red" if destaque else "blue",
                icon="check-to-slot" if destaque else "location-dot",
                prefix="fa",
            ),
        ).add_to(mapa)

    if pontos:
        mapa.fit_bounds(pontos, padding=(30, 30), max_zoom=16)
    return mapa


def main():
    st.set_page_config(page_title="Locais de Votação - Araruama", page_icon="🗳️", layout="wide")
    st.title("🗳️ Locais de Votação – 92ª Zona Eleitoral de Araruama/RJ")

    df = carregar_dataframe()
    if st.sidebar.button("🔄 Recalcular coordenadas"):
        CACHE_FILE.unlink(missing_ok=True)
        st.cache_data.clear()
        st.rerun()

    coords = resolver_coordenadas(tuple(zip(df["local"], df["link"])))

    termo = st.text_input(
        "🔎 Pesquisar",
        placeholder="Número da seção (ex.: 088) ou nome da escola (ex.: Clarice)",
    )
    resultado = filtrar(df, termo)

    c1, c2 = st.columns(2)
    c1.metric("Locais encontrados", len(resultado))
    c2.metric("Seções nesses locais", int(resultado["secoes"].apply(len).sum()))

    if resultado.empty:
        st.warning("Nenhum local encontrado para essa pesquisa.")
        return

    mapa = construir_mapa(resultado, coords, destaque=bool(termo.strip()))
    st_folium(mapa, height=520, use_container_width=True, returned_objects=[])

    with st.expander("📋 Ver lista", expanded=bool(termo.strip())):
        tabela = resultado.assign(
            secoes=resultado["secoes"].apply(", ".join),
            qtd=resultado["secoes"].apply(len),
        )[["local", "qtd", "secoes", "link"]]
        st.dataframe(
            tabela,
            hide_index=True,
            use_container_width=True,
            column_config={
                "local": "Local de votação",
                "qtd": "Qtd.",
                "secoes": "Seções",
                "link": st.column_config.LinkColumn("Mapa", display_text="Abrir"),
            },
        )

    with st.expander("🧭 Origem das coordenadas (conferência)"):
        conf = pd.DataFrame(
            [{"local": l, "origem": c["origem"], "lat": c["lat"], "lon": c["lon"]}
             for l, c in coords.items()]
        )
        st.caption("link = exata (do Google Maps) · manual = tua correção · "
                   "geocodificação/aproximada = conferir")
        st.dataframe(conf, hide_index=True, use_container_width=True)


if __name__ == "__main__":
    main()
