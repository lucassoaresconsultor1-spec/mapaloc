"""Mapa da Zona 2026 — locais de votação da 92ª Zona Eleitoral (Araruama/RJ).

Visual "Azul Vidro": o mesmo azul-marinho, vidro, fontes e componentes do
painel Campanha 2026 e do Carona Amiga.

Dados: o primeiro arquivo .tsv / .csv / .xlsx da pasta, com as colunas
SEÇÕES, LOCAIS DE VOTAÇÃO, LINK e "LATITUDE, LONGITUDE" (ou LATITUDE e
LONGITUDE separadas). Para atualizar, é só trocar a planilha no GitHub.

Links diretos (para usar no Carona Amiga, WhatsApp etc.):
    ?secao=45        abre o mapa já na seção 045
    ?busca=darcy     abre já com a busca preenchida
    ?zona=3          abre já filtrado na Zona 3
"""
from __future__ import annotations

import glob
import html as _html
import re
import unicodedata
from collections import Counter
from urllib.parse import quote

import folium
import numpy as np
import pandas as pd
import streamlit as st
from folium.plugins import Fullscreen
from scipy.spatial import ConvexHull
from sklearn.cluster import KMeans
from streamlit_folium import st_folium

st.set_page_config(
    page_title="Mapa da Zona 2026 · Araruama",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Ajustes rápidos
# ---------------------------------------------------------------------------
N_ZONAS = 20                      # quantas zonas de cobertura
RAIO_MANCHA_M = 450               # folga da mancha em volta de cada escola (metros)
ALTURA_MAPA = 500                 # altura do mapa em pixels
CENTRO_PADRAO = (-22.8712, -42.3415)

LINKS = [  # (título, subtítulo, endereço, ícone) — mesmos atalhos do painel
    ("Carona Amiga", "Corridas do dia", "https://projcaronaamiga.netlify.app/painel.html", "carro"),
    ("Onde eu voto", "Busca por seção", "https://projlocaldevotacao.netlify.app/", "urna"),
    ("Painel 2026", "Centro de comando", "https://campanha2026.streamlit.app/", "grafico"),
]

# 20 cores pensadas para o fundo escuro; vizinhas na lista contrastam entre si
CORES_ZONAS = [
    "#38BDF8", "#F472B6", "#4ADE80", "#FBBF24", "#A78BFA",
    "#2DD4BF", "#FB923C", "#60A5FA", "#F87171", "#A3E635",
    "#E879F9", "#22D3EE", "#FACC15", "#818CF8", "#34D399",
    "#FB7185", "#C084FC", "#FDBA74", "#5EEAD4", "#CBD5E1",
]


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def esc(v) -> str:
    """Escapa texto vindo da planilha antes de ir para a tela."""
    if v is None:
        return ""
    try:
        if pd.isna(v):
            return ""
    except (TypeError, ValueError):
        pass
    return _html.escape(str(v), quote=True)


def url_segura(u) -> str:
    u = str(u or "").strip()
    return esc(u) if u.startswith("https://") else ""


def texto(v) -> str:
    if v is None:
        return ""
    try:
        if pd.isna(v):
            return ""
    except (TypeError, ValueError):
        pass
    return " ".join(str(v).split())


def sem_acento(t) -> str:
    return unicodedata.normalize("NFKD", str(t)).encode("ascii", "ignore").decode().lower()


def rgba(hex_cor: str, alfa: float) -> str:
    h = hex_cor.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alfa})"


def fmt_int(n) -> str:
    return f"{int(n):,}".replace(",", ".")


def html(conteudo: str):
    """Mostra HTML numa linha só (evita que o Markdown do Streamlit quebre o layout)."""
    st.markdown("".join(l.strip() for l in conteudo.splitlines() if l.strip()), unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Leitura e limpeza dos dados
# ---------------------------------------------------------------------------
_RE_COORD = re.compile(r"-?\d{1,3}[.,]\d+")


def ler_coordenadas(valor):
    """Aceita '-22.86, -42.32', '-22,92, -42,30' ou '-22.87,-42.35'."""
    nums = _RE_COORD.findall(texto(valor))
    if len(nums) < 2:
        return None, None
    a, b = (float(n.replace(",", ".")) for n in nums[:2])
    if abs(a) > abs(b):          # em Araruama a longitude (~42) é maior que a latitude (~22)
        a, b = b, a
    return -abs(a), -abs(b)      # RJ fica ao sul e a oeste: as duas são negativas


def ler_secoes(valor) -> list[str]:
    nums = re.findall(r"\d+", texto(valor))
    return sorted({n.zfill(3) for n in nums}, key=int)


_SIGLAS = {"CIEP", "PM", "XV", "XX", "II", "III", "IV"}
_MINUSC = {"de", "da", "do", "das", "dos", "e"}


def _palavra(p: str, primeira: bool) -> str:
    ini = re.match(r"^[(\[]*", p).group()
    fim = re.search(r"[)\],;:]*$", p).group()
    nucleo = p[len(ini):len(p) - len(fim)] if fim else p[len(ini):]
    if not nucleo:
        return p
    if nucleo in _SIGLAS or re.fullmatch(r"([A-Z]\.)+", nucleo) or re.fullmatch(r"[\d.\-–º°ª]+", nucleo):
        novo = nucleo
    elif nucleo.lower() in _MINUSC and not primeira:
        novo = nucleo.lower()
    else:
        novo = "-".join(s[:1].upper() + s[1:].lower() for s in nucleo.split("-"))
    return ini + novo + fim


def bonito(txt: str) -> str:
    """'E. M. PROF. NAIR VALLADARES' -> 'E.M. Prof. Nair Valladares'."""
    s = re.sub(r"\b([A-Z])\.\s(?=[A-Z]\.)", r"\1.", texto(txt))
    return " ".join(_palavra(p, i == 0) for i, p in enumerate(s.split()))


def separar_nome(bruto: str) -> tuple[str, str]:
    """Separa o nome da escola do bairro: 'CIEP 253 (EDUCANDÁRIO)' -> ('CIEP 253', 'EDUCANDÁRIO')."""
    s = texto(bruto)
    if s.endswith(")") and "(" in s:
        i = s.rfind("(")
        return s[:i].rstrip(" -–"), s[i + 1:-1].strip()
    m = re.search(r"\s[-–]\s+([^()\d]+)$", s)
    if m:
        return s[:m.start()].rstrip(" -–"), m.group(1).strip()
    return s, ""


def regiao_de(bairro: str) -> str:
    """'LOT. SANTANA - SÃO VICENTE' -> 'SÃO VICENTE' (usado para dar nome às zonas)."""
    partes = [p.strip() for p in re.split(r"\s[-–]\s", bairro) if p.strip()]
    return partes[-1] if partes else ""


def _coluna(colunas, *chaves, excluir=()):
    for c in colunas:
        if any(k in c for k in chaves) and not any(e in c for e in excluir):
            return c
    return None


def ler_planilha() -> pd.DataFrame:
    arquivos = sorted(glob.glob("*.tsv")) + sorted(glob.glob("*.csv")) + sorted(glob.glob("*.xlsx"))
    if not arquivos:
        return pd.DataFrame()
    arq = arquivos[0]
    if arq.endswith(".tsv"):
        return pd.read_csv(arq, sep="\t", dtype=str)
    if arq.endswith(".csv"):
        return pd.read_csv(arq, sep=None, engine="python", dtype=str)
    return pd.read_excel(arq, dtype=str)


def mancha(pontos: np.ndarray, raio_m: float = RAIO_MANCHA_M, passos: int = 20) -> list:
    """Contorno arredondado em volta dos pontos (funciona com 1, 2 ou mais escolas)."""
    lat0 = np.radians(pontos[:, 0].mean())
    dlat = raio_m / 111_320
    dlon = raio_m / (111_320 * np.cos(lat0))
    ang = np.linspace(0, 2 * np.pi, passos, endpoint=False)
    anel = np.c_[np.sin(ang) * dlat, np.cos(ang) * dlon]
    nuvem = (pontos[:, None, :] + anel[None, :, :]).reshape(-1, 2)
    casca = ConvexHull(nuvem)
    return [[round(float(a), 6), round(float(b), 6)] for a, b in nuvem[casca.vertices]]


@st.cache_data(show_spinner=False)
def preparar():
    bruto = ler_planilha()
    if bruto.empty:
        return pd.DataFrame(), pd.DataFrame(), []

    bruto.columns = [str(c).strip().upper() for c in bruto.columns]
    cols = list(bruto.columns)
    c_local = _coluna(cols, "LOCA")
    c_secao = _coluna(cols, "SEÇ", "SEC")
    c_link = _coluna(cols, "LINK", "URL", "MAPA")
    c_comb = next((c for c in cols if "LAT" in c and "LON" in c), None)
    c_lat = _coluna(cols, "LAT", excluir=("LON",))
    c_lon = _coluna(cols, "LON", excluir=("LAT",))

    linhas, sem_coord = [], []
    for _, r in bruto.iterrows():
        bruto_nome = texto(r.get(c_local)) if c_local else ""
        if not bruto_nome:
            continue
        lat, lon = ler_coordenadas(r.get(c_comb)) if c_comb else (None, None)
        if lat is None and c_lat and c_lon:
            lat, lon = ler_coordenadas(f"{texto(r.get(c_lat))} {texto(r.get(c_lon))}")
        if lat is None:
            sem_coord.append(bonito(bruto_nome))
            continue
        nome, bairro = separar_nome(bruto_nome)
        secoes = ler_secoes(r.get(c_secao)) if c_secao else []
        linhas.append({
            "NOME": bonito(nome),
            "BAIRRO": bonito(bairro),
            "REGIAO": bonito(regiao_de(bairro)),
            "SECOES": secoes,
            "N_SECOES": len(secoes),
            "LAT": lat,
            "LON": lon,
            "LINK": texto(r.get(c_link)) if c_link else "",
            "BUSCA": sem_acento(f"{bruto_nome} {bonito(nome)} {bairro}"),
        })

    df = pd.DataFrame(linhas)
    if df.empty:
        return df, pd.DataFrame(), sem_coord

    # ---- Zonas de cobertura: K-Means por proximidade, numeradas de norte a sul
    coords = df[["LAT", "LON"]].to_numpy()
    k = min(N_ZONAS, len(df))
    rotulos = KMeans(n_clusters=k, random_state=42, n_init=10).fit(coords).labels_
    centros = pd.DataFrame(coords, columns=["lat", "lon"]).groupby(rotulos).mean()
    ordem = centros.sort_values(["lat", "lon"], ascending=[False, True]).index.tolist()
    numero = {rot: i + 1 for i, rot in enumerate(ordem)}
    df["ZONA"] = [numero[r] for r in rotulos]

    zonas = []
    for z, grupo in df.groupby("ZONA"):
        nomes = Counter(x for x in grupo["REGIAO"] if x)
        if nomes:
            nome_z = nomes.most_common(1)[0][0]
        else:
            nome_z = grupo.sort_values("N_SECOES", ascending=False)["NOME"].iloc[0]
        cor = CORES_ZONAS[(z - 1) % len(CORES_ZONAS)]
        zonas.append({
            "NUM": z,
            "NOME": nome_z,
            "COR": cor,
            "N_LOCAIS": len(grupo),
            "N_SECOES": len({s for lista in grupo["SECOES"] for s in lista}),
            "MANCHA": mancha(grupo[["LAT", "LON"]].to_numpy()),
        })
    zonas = pd.DataFrame(zonas).set_index("NUM", drop=False)
    df = df.sort_values(["ZONA", "NOME"]).reset_index(drop=True)
    return df, zonas, sem_coord


def interpretar_busca(q: str):
    q = texto(q)
    if not q:
        return None, ""
    so_num = re.sub(r"(?i)^(se[cç][aã]o|sec|s)\s*[:nº°#.\-]*\s*", "", q).strip()
    if re.fullmatch(r"\d{1,3}", so_num):
        return "secao", so_num.zfill(3)
    return "texto", sem_acento(q)


def rota_url(lat: float, lon: float) -> str:
    return f"https://www.google.com/maps/dir/?api=1&destination={lat:.6f},{lon:.6f}"


def maps_url(r) -> str:
    return url_segura(r.LINK) or esc(f"https://www.google.com/maps/search/?api=1&query={quote(f'{r.LAT},{r.LON}')}")


# ---------------------------------------------------------------------------
# Visual (Azul Vidro — igual ao painel Campanha 2026)
# ---------------------------------------------------------------------------
_ICONES = {
    "pin": '<path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/>',
    "carro": '<path d="M3 13l2-6h14l2 6v5H3z"/><circle cx="7.5" cy="16.5" r="1.5"/><circle cx="16.5" cy="16.5" r="1.5"/>',
    "urna": '<path d="M4 11h16v9H4zM8 11V4h8v7M10 7h4"/>',
    "grafico": '<path d="M3 3v18h18M7 16l4-4 4 4 5-6"/>',
    "mapa": '<path d="M1 6v16l7-4 8 4 7-4V2l-7 4-8-4-7 4zM8 2v16M16 6v16"/>',
    "escola": '<path d="M22 10L12 5 2 10l10 5 10-5z"/><path d="M6 12v5c3 2 9 2 12 0v-5"/>',
    "camadas": '<path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5M2 12l10 5 10-5"/>',
    "trofeu": '<path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6M18 9h1.5a2.5 2.5 0 0 0 0-5H18M4 22h16M10 14.7V17c0 .6-.5 1-1 1.2C7.9 18.8 7 20.2 7 22M14 14.7V17c0 .6.5 1 1 1.2 1.1.6 2 2 2 3.8M18 2H6v7a6 6 0 0 0 12 0z"/>',
    "rota": '<path d="M3 11l19-9-9 19-2-8-8-2z"/>',
    "link": '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6M15 3h6v6M10 14L21 3"/>',
    "info": '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>',
    "alerta": '<path d="M10.3 3.9L1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/>',
    "chev": '<path d="M6 9l6 6 6-6"/>',
    "busca": '<circle cx="11" cy="11" r="8"/><path d="M21 21l-4.3-4.3"/>',
    "tela": '<path d="M8 3H5a2 2 0 0 0-2 2v3M21 8V5a2 2 0 0 0-2-2h-3M3 16v3a2 2 0 0 0 2 2h3M16 21h3a2 2 0 0 0 2-2v-3"/>',
    "sair_tela": '<path d="M8 3v3a2 2 0 0 1-2 2H3M21 8h-3a2 2 0 0 1-2-2V3M3 16h3a2 2 0 0 1 2 2v3M16 21v-3a2 2 0 0 1 2-2h3"/>',
}


def _svg_uri(path: str) -> str:
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="black" '
           f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{path}</svg>')
    return "data:image/svg+xml;utf8," + quote(svg, safe="")


def ic(nome: str, extra: str = "") -> str:
    return f'<i class="cv-i i-{nome} {extra}" aria-hidden="true"></i>'


_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@500;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
:root{--bg:#040B1F;--painel:rgba(13,32,74,.62);--painel2:rgba(4,12,32,.55);--borda:rgba(125,170,255,.16);--borda2:rgba(125,170,255,.30);--txt:#EAF2FF;--mut:#93A8CC;--sua:#C7D6F0;--fd:'Outfit',system-ui,sans-serif;--fb:'Plus Jakarta Sans',system-ui,sans-serif}
.stApp{background:radial-gradient(700px 520px at 8% 0px,rgba(37,99,235,.38),transparent 70%),radial-gradient(620px 620px at 100% 900px,rgba(14,165,233,.14),transparent 70%),radial-gradient(640px 640px at 0% 2200px,rgba(37,99,235,.12),transparent 70%),#040B1F !important;color:var(--txt)}
html,body,.stApp,.stApp p,.stApp label,.stApp input,.stApp button,.stApp textarea,.stApp li{font-family:var(--fb)}
header[data-testid="stHeader"],#MainMenu,footer,[data-testid="stToolbar"],[data-testid="stDecoration"],[data-testid="stStatusWidget"],.stDeployButton,[data-testid="stAppDeployButton"],[data-testid="manage-app-button"],[data-testid="stSidebarCollapsedControl"]{display:none !important}
.block-container,[data-testid="stMainBlockContainer"]{max-width:1280px !important;padding:16px 14px 48px !important}
@media(min-width:768px){.block-container,[data-testid="stMainBlockContainer"]{padding:28px 32px 60px !important}}
.stTextInput [data-baseweb="input"],.stTextInput [data-baseweb="base-input"],div[data-baseweb="select"]>div{background:rgba(13,32,74,.78) !important;border-color:var(--borda2) !important;border-radius:14px !important;min-height:48px}
.stTextInput input{color:var(--txt) !important;font-size:15px !important}
.stTextInput input::placeholder{color:#6F84A8 !important}
.stTextInput label p,.stSelectbox label p{color:var(--sua) !important;font-weight:700 !important;font-size:12.5px !important}
.stToggle label p,[data-testid="stToggle"] label p,.stCheckbox label p,[data-testid="stCheckbox"] label p{color:var(--sua) !important;font-weight:700 !important;font-size:13px !important}
.stToggle,[data-testid="stToggle"],.stCheckbox{padding-bottom:12px}
iframe[title="streamlit_folium.st_folium"],iframe[data-testid="stCustomComponentV1"]{border-radius:22px;border:1px solid rgba(125,170,255,.30) !important;box-shadow:0 18px 44px rgba(0,0,0,.38);background:#040B1F}
.cv{color:var(--txt);font-family:var(--fb);font-size:14px;line-height:1.35}
.cv *{box-sizing:border-box}
.cv a{color:inherit;text-decoration:none}
.cv-i{display:inline-block;width:16px;height:16px;flex-shrink:0;background:currentColor;-webkit-mask:var(--m) center/contain no-repeat;mask:var(--m) center/contain no-repeat}
.cv-i.p{width:12px;height:12px}.cv-i.g{width:20px;height:20px}.cv-i.gg{width:26px;height:26px}
.cv-card{background:var(--painel);border:1px solid var(--borda);border-radius:20px;box-shadow:inset 0 1px 0 rgba(255,255,255,.06);backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px)}
.cv-pad{padding:16px}
@media(min-width:768px){.cv-pad{padding:20px 22px}}
.cv-over{font-size:10.5px;font-weight:800;letter-spacing:1.3px;text-transform:uppercase;color:var(--mut)}
.cv-num{font-family:var(--fd);font-weight:700;line-height:1;letter-spacing:-.5px}
.cv-cab{display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap}
.cv-mut{color:var(--mut)}.cv-sua{color:var(--sua)}
.cv-topo{display:flex;align-items:center;justify-content:space-between;gap:12px}
.cv-marca{display:flex;align-items:center;gap:10px}
.cv-logo{width:40px;height:40px;border-radius:12px;background:#2563EB;display:flex;align-items:center;justify-content:center;color:#FFFFFF;box-shadow:0 6px 18px rgba(37,99,235,.45)}
.cv-marca b{display:block;font-family:var(--fd);font-size:17px;font-weight:700}
.cv-marca small{display:block;font-size:10px;font-weight:800;letter-spacing:1.4px;text-transform:uppercase;color:var(--mut)}
.cv-status{display:flex;align-items:center;gap:6px;font-size:11px;font-weight:700;color:var(--mut);padding:6px 10px;border-radius:999px;background:var(--painel);border:1px solid var(--borda);white-space:nowrap}
.cv-dot{width:8px;height:8px;border-radius:50%;background:#4ADE80;box-shadow:0 0 10px #4ADE80}
.cv-links{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:14px}
.cv-link{display:flex;flex-direction:column;align-items:flex-start;gap:6px;padding:12px;border-radius:16px;background:var(--painel);border:1px solid var(--borda2);color:var(--txt) !important;min-width:0}
.cv-link:hover{border-color:#3B82F6;background:rgba(37,99,235,.22)}
.cv-link b{font-size:12.5px;font-weight:800;line-height:1.2}
.cv-link small{font-size:10.5px;color:var(--mut);font-weight:600}
.cv-link-ico{width:34px;height:34px;border-radius:10px;display:flex;align-items:center;justify-content:center;background:rgba(56,189,248,.16);color:#7DD3FC}
@media(min-width:768px){.cv-link{flex-direction:row;align-items:center;gap:12px;padding:14px 16px}.cv-link b{font-size:14px}}
.cv-hero{display:flex;flex-direction:column;gap:14px;margin-top:18px}
@media(min-width:900px){.cv-hero{flex-direction:row;align-items:flex-end;justify-content:space-between}}
.cv-h1{font-family:var(--fd);font-size:30px;font-weight:700;letter-spacing:-.6px;line-height:1.08}
@media(min-width:768px){.cv-h1{font-size:40px}}
.cv-lead{font-size:13.5px;color:var(--mut);font-weight:500;margin-top:5px}
.cv-cont{display:flex;align-items:center;gap:14px;padding:14px 16px}
@media(min-width:900px){.cv-cont{min-width:360px}}
.cv-cont-ico{width:48px;height:48px;border-radius:14px;flex-shrink:0;display:flex;align-items:center;justify-content:center;background:rgba(56,189,248,.14);color:#7DD3FC}
.cv-cont b{display:block;font-size:15px;font-weight:700;margin-top:2px}
.cv-cont-num{margin-left:auto;font-family:var(--fd);font-size:36px;font-weight:700;color:#7DD3FC;line-height:1}
.cv-kpis{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin-top:14px}
@media(min-width:900px){.cv-kpis{grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}}
.cv-kpi{padding:14px;display:flex;flex-direction:column;gap:7px;border-radius:18px;min-width:0}
.cv-kpi-h{display:flex;align-items:center;justify-content:space-between;gap:6px}
.cv-kpi .cv-num{font-size:30px}
@media(min-width:768px){.cv-kpi .cv-num{font-size:34px}}
.cv-kpi-p{font-size:12px;color:var(--sua);font-weight:600;min-height:16px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.cv-c-ciano{color:#7DD3FC}.cv-c-azul{color:#93C5FD}.cv-c-ambar{color:#FCD34D}.cv-c-verde{color:#4ADE80}.cv-c-rosa{color:#F9A8D4}
.cv-sec{display:flex;flex-direction:column;gap:6px;margin:18px 0 2px}
.cv-sec-t{font-family:var(--fd);font-size:23px;font-weight:700;letter-spacing:-.2px}
@media(min-width:768px){.cv-sec-t{font-size:27px}}
.cv-sec-s{font-size:13px;color:var(--mut);line-height:1.45}
.cv-chips{display:flex;flex-wrap:wrap;gap:6px}
.cv-chip{display:inline-flex;align-items:center;gap:5px;font-size:11.5px;font-weight:700;padding:4px 10px;border-radius:999px;background:rgba(147,168,204,.12);color:var(--sua);border:1px solid var(--borda);white-space:nowrap}
.cv-chip.az{background:rgba(59,130,246,.16);color:#BFDBFE;border-color:rgba(59,130,246,.32)}
.cv-row{display:flex;align-items:center;gap:12px;width:100%}
.cv-info{flex:1;min-width:0;display:flex;flex-direction:column;gap:3px}
.cv-sub{font-size:12px;color:var(--sua)}
.cv-meta{display:flex;align-items:flex-start;gap:5px;font-size:12.5px;line-height:1.35;color:var(--mut);min-width:0}
.cv-meta>.cv-i{margin-top:2px}
.cv-chev{color:var(--mut);transition:transform .2s}
details[open]>summary .cv-chev{transform:rotate(180deg)}
.cv-vazio{padding:26px 16px;text-align:center;color:var(--mut);font-size:13.5px}
.cv-nota{display:flex;gap:10px;align-items:flex-start;padding:12px 14px;border-radius:14px;background:rgba(59,130,246,.12);border:1px solid rgba(59,130,246,.3);color:#DBEAFE;font-size:13px;line-height:1.5;margin-top:10px}
.cv-nota.al{background:rgba(251,191,36,.10);border-color:rgba(251,191,36,.35);color:#FDE68A}
.cv-nota .cv-i{margin-top:2px}
.cv-rodape{margin-top:26px;text-align:center;font-size:11.5px;color:var(--mut);line-height:1.6}
.mz-todos>summary{list-style:none;cursor:pointer;margin-top:12px;outline:none;-webkit-tap-highlight-color:transparent}
.mz-todos>summary::-webkit-details-marker{display:none}
.mz-todos[open]>summary{display:none}
.mz-mais{display:flex;align-items:center;justify-content:center;gap:8px;min-height:48px;border-radius:14px;border:1px dashed rgba(125,170,255,.40);background:rgba(13,32,74,.40);color:var(--sua);font-size:13.5px;font-weight:800}
.mz-mais:hover{border-color:#3B82F6;color:#FFFFFF}
.mz-res{display:flex;flex-direction:column;gap:14px;padding:16px;margin-top:12px;border-color:#3B82F6;box-shadow:0 0 0 1px #3B82F6 inset,0 18px 40px rgba(37,99,235,.20)}
@media(min-width:820px){.mz-res{flex-direction:row;align-items:center;padding:18px 22px}}
.mz-res-top{display:flex;align-items:center;gap:14px;min-width:0;flex:1}
.mz-res-sec{flex-shrink:0;width:76px;height:76px;border-radius:18px;background:linear-gradient(160deg,#3B82F6,#1D4ED8);color:#FFFFFF;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px;box-shadow:0 10px 26px rgba(37,99,235,.45)}
.mz-res-sec small{font-size:9.5px;font-weight:800;letter-spacing:1.3px;text-transform:uppercase;opacity:.85}
.mz-res-sec b{font-family:var(--fd);font-size:27px;font-weight:700;line-height:1}
.mz-res-n{font-family:var(--fd);font-size:19px;font-weight:700;line-height:1.2}
.mz-acoes{display:grid;grid-template-columns:1fr 1fr;gap:8px}
@media(min-width:820px){.mz-res .mz-acoes{min-width:310px}}
.mz-btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;min-height:44px;padding:0 12px;border-radius:12px;background:#2563EB;color:#FFFFFF !important;font-weight:800;font-size:13px;box-shadow:0 8px 22px rgba(37,99,235,.35);white-space:nowrap}
.mz-btn:hover{background:#1D4ED8}
.mz-btn.s{background:rgba(13,32,74,.62);border:1px solid var(--borda2);box-shadow:none;color:var(--txt) !important}
.mz-btn.s:hover{border-color:#3B82F6;background:rgba(37,99,235,.22)}
.mz-badge{width:30px;height:30px;flex-shrink:0;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;font-family:var(--fd);font-weight:700;font-size:13px;color:#04122E;border:2px solid rgba(255,255,255,.92)}
.mz-zchip{display:inline-flex;align-items:center;gap:6px;font-size:11.5px;font-weight:700;padding:3px 10px 3px 4px;border-radius:999px;background:rgba(147,168,204,.12);color:var(--sua);border:1px solid var(--borda);white-space:nowrap}
.mz-zchip i{width:16px;height:16px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;font-style:normal;font-size:9.5px;font-weight:800;color:#04122E}
.mz-mapa-cab{display:flex;align-items:flex-end;justify-content:space-between;gap:10px;flex-wrap:wrap;margin:20px 0 10px}
.mz-zonas{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:12px}
@media(min-width:760px){.mz-zonas{grid-template-columns:repeat(4,minmax(0,1fr))}}
@media(min-width:1150px){.mz-zonas{grid-template-columns:repeat(5,minmax(0,1fr))}}
.mz-z{display:flex;align-items:center;gap:10px;padding:10px 12px;border-radius:14px;background:var(--painel);border:1px solid var(--borda);min-width:0}
.mz-z.ativo{border-color:#3B82F6;box-shadow:0 0 0 1px #3B82F6 inset;background:rgba(37,99,235,.18)}
.mz-z.apagada{opacity:.45}
.mz-z b{font-size:13px;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:block}
.mz-z small{font-size:11px;color:var(--mut);font-weight:600;white-space:nowrap}
.mz-locs{display:grid;grid-template-columns:minmax(0,1fr);gap:10px;margin-top:12px;align-items:start}
@media(min-width:760px){.mz-locs{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(min-width:1150px){.mz-locs{grid-template-columns:repeat(3,minmax(0,1fr))}}
details.mz-loc{background:var(--painel);border:1px solid var(--borda);border-radius:18px;overflow:hidden;box-shadow:inset 0 1px 0 rgba(255,255,255,.06)}
details.mz-loc[open]{border-color:#3B82F6}
.mz-loc>summary{list-style:none;cursor:pointer;padding:14px;display:block;outline:none;-webkit-tap-highlight-color:transparent}
.mz-loc>summary::-webkit-details-marker{display:none}
.mz-loc>summary:focus-visible{box-shadow:inset 0 0 0 2px #7DD3FC}
.mz-loc-n{font-family:var(--fd);font-size:16px;font-weight:700;line-height:1.25;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.mz-q{display:flex;flex-direction:column;align-items:flex-end;flex-shrink:0}
.mz-q b{font-family:var(--fd);font-size:22px;font-weight:700;line-height:1}
.mz-q small{font-size:10.5px;color:var(--mut);font-weight:600}
.mz-loc-c{padding:0 14px 14px;display:flex;flex-direction:column;gap:12px}
.mz-secs{display:flex;flex-wrap:wrap;gap:5px;padding-top:12px;border-top:1px solid rgba(125,170,255,.14)}
.mz-s{font-family:var(--fd);font-size:12.5px;font-weight:600;padding:3px 8px;border-radius:8px;background:rgba(59,130,246,.14);color:#BFDBFE;border:1px solid rgba(59,130,246,.25);font-variant-numeric:tabular-nums}
.mz-s.hit{background:#2563EB;color:#FFFFFF;border-color:#2563EB;box-shadow:0 4px 12px rgba(37,99,235,.45)}
"""

# CSS de dentro do mapa (o mapa roda num quadro separado, então leva o próprio estilo)
_CSS_MAPA = """
.leaflet-container{background:#040B1F !important;font-family:'Plus Jakarta Sans',system-ui,sans-serif}
.mz-noite{filter:invert(100%) hue-rotate(185deg) brightness(.95) contrast(.86) saturate(.55)}
.leaflet-bar{border:1px solid rgba(125,170,255,.30) !important;border-radius:12px !important;overflow:hidden;box-shadow:0 8px 22px rgba(0,0,0,.35) !important}
.leaflet-bar a,.leaflet-bar a:hover{background:rgba(9,22,52,.94) !important;color:#EAF2FF !important;border-bottom-color:rgba(125,170,255,.18) !important;width:36px !important;height:36px !important;line-height:36px !important}
.leaflet-bar a:hover{background:rgba(37,99,235,.55) !important}
.leaflet-control-zoom-fullscreen,.leaflet-control-layers-toggle{background-image:none !important;display:flex !important;align-items:center;justify-content:center}
.leaflet-control-zoom-fullscreen::before,.leaflet-control-layers-toggle::before{content:"";width:17px;height:17px;background:#EAF2FF;-webkit-mask:var(--m) center/contain no-repeat;mask:var(--m) center/contain no-repeat}
.leaflet-control-zoom-fullscreen{--m:url("__ICO_TELA__")}
.leaflet-control-zoom-fullscreen.leaflet-fullscreen-on{--m:url("__ICO_SAIR__")}
.leaflet-control-layers-toggle{--m:url("__ICO_CAMADAS__");width:36px !important;height:36px !important}
.leaflet-control-layers{background:rgba(9,22,52,.94) !important;color:#EAF2FF !important;border:1px solid rgba(125,170,255,.30) !important;border-radius:12px !important;box-shadow:0 8px 22px rgba(0,0,0,.35) !important}
.leaflet-control-layers-expanded{padding:10px 12px !important;font-weight:700;font-size:13px}
.leaflet-control-layers label{margin:4px 0}
.leaflet-control-attribution{background:rgba(4,11,31,.72) !important;color:#93A8CC !important;font-size:10px;border-radius:8px 0 0 0}
.leaflet-control-attribution a{color:#7DD3FC !important}
.leaflet-popup-content-wrapper{background:rgba(9,22,52,.97);color:#EAF2FF;border:1px solid rgba(125,170,255,.30);border-radius:18px;box-shadow:0 18px 44px rgba(0,0,0,.5)}
.leaflet-popup-tip{background:rgba(9,22,52,.97);border:1px solid rgba(125,170,255,.30)}
.leaflet-popup-content{margin:14px 16px !important;min-width:220px}
.leaflet-container a.leaflet-popup-close-button{color:#93A8CC;font-size:20px;top:6px;right:8px}
.leaflet-tooltip{background:rgba(9,22,52,.95);color:#EAF2FF;border:1px solid rgba(125,170,255,.30);border-radius:10px;font-weight:700;font-size:12px;box-shadow:0 6px 18px rgba(0,0,0,.35);padding:5px 9px}
.leaflet-tooltip-top:before{border-top-color:rgba(125,170,255,.30)}
.leaflet-tooltip-bottom:before{border-bottom-color:rgba(125,170,255,.30)}
.leaflet-tooltip-left:before{border-left-color:rgba(125,170,255,.30)}
.leaflet-tooltip-right:before{border-right-color:rgba(125,170,255,.30)}
.mz-pin-w{background:none !important;border:0 !important}
.mz-pin{width:100%;height:100%;border-radius:50%;border:2.5px solid #FFFFFF;display:flex;align-items:center;justify-content:center;color:#04122E;font:700 12px/1 'Outfit',system-ui,sans-serif;box-sizing:border-box;transition:transform .15s}
.mz-pin:hover{transform:scale(1.12)}
.mz-pin.foco{font-size:15px;border-width:3px;animation:mzpulso 1.8s ease-out infinite}
@keyframes mzpulso{0%{box-shadow:0 0 0 0 rgba(255,255,255,.55),0 6px 16px rgba(0,0,0,.5)}70%{box-shadow:0 0 0 18px rgba(255,255,255,0),0 6px 16px rgba(0,0,0,.5)}100%{box-shadow:0 0 0 0 rgba(255,255,255,0),0 6px 16px rgba(0,0,0,.5)}}
.mz-pop{display:flex;flex-direction:column;gap:8px;font-size:13px;line-height:1.35}
.mz-pop-z{align-self:flex-start;display:inline-flex;align-items:center;gap:6px;font-size:10.5px;font-weight:800;letter-spacing:.6px;text-transform:uppercase;padding:3px 9px 3px 3px;border-radius:999px;background:rgba(147,168,204,.14);color:#C7D6F0}
.mz-pop-z i{width:16px;height:16px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;font-style:normal;font-size:9.5px;color:#04122E}
.mz-pop-n{font-family:'Outfit',system-ui,sans-serif;font-size:17px;font-weight:700;line-height:1.2;color:#FFFFFF}
.mz-pop-b{font-size:12px;color:#93A8CC;font-weight:600;margin-top:-4px}
.mz-pop-k{font-size:10.5px;font-weight:800;letter-spacing:1.2px;text-transform:uppercase;color:#93A8CC;margin-top:2px}
.mz-pop-s{display:flex;flex-wrap:wrap;gap:4px;max-height:96px;overflow:auto}
.mz-pop-s span{font-family:'Outfit',system-ui,sans-serif;font-size:12px;font-weight:600;padding:2px 7px;border-radius:7px;background:rgba(59,130,246,.16);color:#BFDBFE;border:1px solid rgba(59,130,246,.25)}
.mz-pop-s span.hit{background:#2563EB;color:#FFFFFF;border-color:#2563EB}
.mz-pop-a{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:4px}
.mz-pop-a a{display:flex;align-items:center;justify-content:center;min-height:38px;border-radius:10px;font-weight:800;font-size:12.5px;text-decoration:none;background:#2563EB;color:#FFFFFF !important}
.mz-pop-a a.s{background:rgba(13,32,74,.8);border:1px solid rgba(125,170,255,.30);color:#EAF2FF !important}
"""


def _css_prioritario(css: str) -> str:
    """Prefixa os seletores com 'html ' para vencer o CSS do Leaflet/Bootstrap, que carrega depois."""
    saida = []
    for linha in css.strip().splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("@") or "{" not in linha:
            saida.append(linha)
            continue
        sel, resto = linha.split("{", 1)
        sel = ",".join("html " + s.strip() for s in sel.split(","))
        saida.append(sel + "{" + resto)
    return " ".join(saida)


def estilo() -> str:
    icones = "".join(f'.i-{n}{{--m:url("{_svg_uri(p)}")}}' for n, p in _ICONES.items())
    css = " ".join(l.strip() for l in _CSS.strip().splitlines())
    return f"<style>{css}{icones}</style>"


# ---------------------------------------------------------------------------
# Componentes da página
# ---------------------------------------------------------------------------
def zchip(z) -> str:
    return (f'<span class="mz-zchip"><i style="background:{z.COR}">{z.NUM}</i>'
            f'Zona {z.NUM} · {esc(z.NOME)}</span>')


def cabecalho() -> str:
    links = "".join(
        f'<a class="cv-link" href="{esc(u)}" target="_blank" rel="noopener"><span class="cv-link-ico">{ic(i)}</span>'
        f'<span><b>{esc(t)}</b><br><small>{esc(s)}</small></span></a>' for t, s, u, i in LINKS)
    return f"""<div class="cv">
<div class="cv-topo">
<div class="cv-marca"><span class="cv-logo">{ic("mapa", "g")}</span><span><b>Mapa da Zona</b><small>92ª ZE · Araruama</small></span></div>
<div class="cv-status"><span class="cv-dot"></span>Eleições 2026</div>
</div>
<div class="cv-links">{links}</div>
</div>"""


def hero(n_vis: int, rotulo: str) -> str:
    return f"""<div class="cv"><div class="cv-hero">
<div><div class="cv-h1" role="heading" aria-level="1">Locais de votação</div>
<div class="cv-lead">Escolas e seções da 92ª Zona Eleitoral em {N_ZONAS} zonas de cobertura</div></div>
<div class="cv-card cv-cont"><span class="cv-cont-ico">{ic("pin", "g")}</span>
<span><span class="cv-over">No mapa agora</span><b>{esc(rotulo)}</b></span>
<span class="cv-cont-num">{n_vis}</span></div>
</div></div>"""


def kpi(rotulo, valor, icone, rodape, cor) -> str:
    return (f'<div class="cv-card cv-kpi"><div class="cv-kpi-h"><span class="cv-over">{esc(rotulo)}</span>'
            f'<span class="{cor}">{ic(icone)}</span></div><span class="cv-num">{esc(valor)}</span>'
            f'<span class="cv-kpi-p">{esc(rodape)}</span></div>')


def kpis(df: pd.DataFrame, zonas: pd.DataFrame) -> str:
    todas = {s for lista in df["SECOES"] for s in lista}
    maior = df.sort_values("N_SECOES", ascending=False).iloc[0]
    media = len(todas) / len(df) if len(df) else 0
    itens = [
        kpi("Locais", fmt_int(len(df)), "escola", "escolas e praças", "cv-c-ciano"),
        kpi("Seções", fmt_int(len(todas)), "urna", f"média de {media:.1f} por local".replace(".", ","), "cv-c-azul"),
        kpi("Zonas", fmt_int(len(zonas)), "camadas", "por proximidade", "cv-c-verde"),
        kpi("Maior local", fmt_int(maior["N_SECOES"]), "trofeu", maior["NOME"], "cv-c-ambar"),
    ]
    return f'<div class="cv"><div class="cv-kpis">{"".join(itens)}</div></div>'


def secao_titulo(titulo: str, sub: str = "") -> str:
    s = f'<div class="cv-sec-s">{esc(sub)}</div>' if sub else ""
    return f'<div class="cv"><div class="cv-sec"><div class="cv-sec-t" role="heading" aria-level="2">{esc(titulo)}</div>{s}</div></div>'


def nota(txt_html: str, tipo: str = "", icone: str = "info") -> str:
    return f'<div class="cv"><div class="cv-nota {tipo}">{ic(icone)}<div>{txt_html}</div></div></div>'


def card_resultado(r, z, secao: str) -> str:
    bairro = f'<span class="cv-meta">{ic("pin", "p")}{esc(r.BAIRRO)}</span>' if r.BAIRRO else ""
    return f"""<div class="cv"><div class="cv-card mz-res">
<div class="mz-res-top">
<div class="mz-res-sec"><small>Seção</small><b>{esc(secao)}</b></div>
<div class="cv-info" style="gap:6px"><span class="cv-over" style="color:#7DD3FC">Vota em</span>
<span class="mz-res-n">{esc(r.NOME)}</span>{bairro}
<span class="cv-chips">{zchip(z)}<span class="cv-chip az">{r.N_SECOES} seções no local</span></span></div>
</div>
<div class="mz-acoes">
<a class="mz-btn" href="{esc(rota_url(r.LAT, r.LON))}" target="_blank" rel="noopener">{ic("rota", "p")}Como chegar</a>
<a class="mz-btn s" href="{maps_url(r)}" target="_blank" rel="noopener">{ic("link", "p")}Abrir no Maps</a>
</div>
</div></div>"""


def legenda_zonas(zonas: pd.DataFrame, zona_sel, zonas_vis: set) -> str:
    itens = []
    for z in zonas.itertuples():
        classe = " ativo" if zona_sel == z.NUM else (" apagada" if zonas_vis and z.NUM not in zonas_vis else "")
        itens.append(
            f'<div class="mz-z{classe}"><span class="mz-badge" style="background:{z.COR};'
            f'box-shadow:0 0 0 3px {rgba(z.COR, .22)}">{z.NUM}</span>'
            f'<span class="cv-info"><b>{esc(z.NOME)}</b><small>{z.N_LOCAIS} '
            f'{"local" if z.N_LOCAIS == 1 else "locais"} · {z.N_SECOES} seções</small></span></div>')
    return f'<div class="cv"><div class="mz-zonas">{"".join(itens)}</div></div>'


def lista_locais(vis: pd.DataFrame, zonas: pd.DataFrame, secao: str, abrir: bool, recolher: bool = False) -> str:
    cards = []
    for r in vis.itertuples():
        z = zonas.loc[r.ZONA]
        secs = "".join(f'<span class="mz-s{" hit" if s == secao else ""}">{s}</span>' for s in r.SECOES)
        sub = " · ".join(x for x in [esc(r.BAIRRO), f"Zona {z.NUM}"] if x)
        cards.append(
            f'<details class="mz-loc"{" open" if abrir else ""}><summary><span class="cv-row">'
            f'<span class="mz-badge" style="background:{z.COR};box-shadow:0 0 0 3px {rgba(z.COR, .22)}">{z.NUM}</span>'
            f'<span class="cv-info"><span class="mz-loc-n">{esc(r.NOME)}</span><span class="cv-sub">{sub}</span></span>'
            f'<span class="mz-q"><b>{r.N_SECOES}</b><small>{"seção" if r.N_SECOES == 1 else "seções"}</small></span>'
            f'{ic("chev", "cv-chev")}</span></summary>'
            f'<div class="mz-loc-c"><div class="mz-secs">{secs or "<span class=cv-meta>Sem seções na planilha</span>"}</div>'
            f'<div class="mz-acoes"><a class="mz-btn" href="{esc(rota_url(r.LAT, r.LON))}" target="_blank" rel="noopener">'
            f'{ic("rota", "p")}Como chegar</a><a class="mz-btn s" href="{maps_url(r)}" target="_blank" rel="noopener">'
            f'{ic("link", "p")}Abrir no Maps</a></div></div></details>')
    grade = f'<div class="mz-locs">{"".join(cards)}</div>'
    if recolher:  # lista completa fica guardada atrás de um botão para não alongar a página no celular
        grade = (f'<details class="mz-todos"><summary><span class="mz-mais">Ver os {len(vis)} locais'
                 f'{ic("chev", "p cv-chev")}</span></summary>{grade}</details>')
    return f'<div class="cv">{grade}</div>'


# ---------------------------------------------------------------------------
# Mapa
# ---------------------------------------------------------------------------
def popup_html(r, z, secao: str) -> str:
    secs = "".join(f'<span{" class=hit" if s == secao else ""}>{s}</span>' for s in r.SECOES)
    bairro = f'<span class="mz-pop-b">{esc(r.BAIRRO)}</span>' if r.BAIRRO else ""
    return (f'<div class="mz-pop"><span class="mz-pop-z"><i style="background:{z.COR}">{z.NUM}</i>Zona {z.NUM} · {esc(z.NOME)}</span>'
            f'<span class="mz-pop-n">{esc(r.NOME)}</span>{bairro}'
            f'<span class="mz-pop-k">{r.N_SECOES} {"seção" if r.N_SECOES == 1 else "seções"}</span>'
            f'<div class="mz-pop-s">{secs}</div>'
            f'<div class="mz-pop-a"><a href="{esc(rota_url(r.LAT, r.LON))}" target="_blank" rel="noopener">Como chegar</a>'
            f'<a class="s" href="{maps_url(r)}" target="_blank" rel="noopener">Abrir no Maps</a></div></div>')


def montar_mapa(df, zonas, vis, foco: set, manchas: bool, zona_sel, secao: str) -> folium.Map:
    m = folium.Map(location=list(CENTRO_PADRAO), zoom_start=12, tiles=None, scrollWheelZoom=False, zoomSnap=0.25)
    folium.TileLayer("OpenStreetMap", name="Noturno", class_name="mz-noite").add_to(m)
    folium.TileLayer("OpenStreetMap", name="Ruas", show=False).add_to(m)
    css_mapa = (_css_prioritario(_CSS_MAPA)
                .replace("__ICO_TELA__", _svg_uri(_ICONES["tela"]))
                .replace("__ICO_SAIR__", _svg_uri(_ICONES["sair_tela"]))
                .replace("__ICO_CAMADAS__", _svg_uri(_ICONES["camadas"])))
    m.get_root().header.add_child(folium.Element(
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Outfit:wght@600;700'
        '&family=Plus+Jakarta+Sans:wght@500;600;700;800&display=swap">'
        f'<style>{css_mapa}</style>'))

    if manchas:
        for z in zonas.itertuples():
            forte = zona_sel is None or z.NUM == zona_sel
            folium.Polygon(
                locations=z.MANCHA, color=z.COR, weight=1.6 if forte else 1, opacity=.9 if forte else .3,
                dash_array="6 5", fill=True, fill_color=z.COR, fill_opacity=.17 if forte else .05,
                tooltip=f"Zona {z.NUM} · {esc(z.NOME)}",
            ).add_to(m)

    ids_vis = set(vis.index)
    for r in df.itertuples():  # locais fora do filtro ficam como pontinhos discretos
        if r.Index in ids_vis:
            continue
        folium.CircleMarker(
            [r.LAT, r.LON], radius=4, weight=1, color="#93A8CC", opacity=.7,
            fill=True, fill_color="#93A8CC", fill_opacity=.45, tooltip=esc(r.NOME),
        ).add_to(m)

    for r in vis.itertuples():
        z = zonas.loc[r.ZONA]
        destaque = r.Index in foco
        tam = 40 if destaque else 30
        pino = (f'<div class="mz-pin{" foco" if destaque else ""}" style="background:{z.COR};'
                f'box-shadow:0 0 0 4px {rgba(z.COR, .30)},0 6px 14px rgba(0,0,0,.45)">{z.NUM}</div>')
        folium.Marker(
            [r.LAT, r.LON],
            icon=folium.DivIcon(html=pino, icon_size=(tam, tam), icon_anchor=(tam // 2, tam // 2), class_name="mz-pin-w"),
            tooltip=esc(r.NOME),
            popup=folium.Popup(popup_html(r, z, secao), max_width=300, show=destaque and len(foco) == 1),
            z_index_offset=1000 if destaque else 0,
        ).add_to(m)

    pts = vis[["LAT", "LON"]].to_numpy() if len(vis) else df[["LAT", "LON"]].to_numpy()
    folga = .004 if len(pts) == 1 else 0
    m.fit_bounds([[pts[:, 0].min() - folga, pts[:, 1].min() - folga],
                  [pts[:, 0].max() + folga, pts[:, 1].max() + folga]], padding=(28, 28), max_zoom=16)

    Fullscreen(position="topright", title="Tela cheia", title_cancel="Sair da tela cheia",
               force_separate_button=True).add_to(m)
    folium.LayerControl(position="topright", collapsed=True).add_to(m)
    return m


# ---------------------------------------------------------------------------
# Página
# ---------------------------------------------------------------------------
def main():
    html(estilo())
    df, zonas, sem_coord = preparar()
    html(cabecalho())

    if df.empty:
        html(nota("<b>Não encontrei a planilha dos locais.</b> Envie o arquivo .tsv, .csv ou .xlsx para a "
                  "mesma pasta do app no GitHub.", "al", "alerta"))
        st.stop()

    # ---- Valores iniciais vindos do link (?secao=45, ?busca=darcy, ?zona=3)
    opcoes = ["Todas as zonas"] + [f"Zona {z.NUM} · {z.NOME}" for z in zonas.itertuples()]
    por_rotulo = {rot: int(rot.split()[1]) for rot in opcoes[1:]}
    qp = st.query_params
    if "busca" not in st.session_state:
        st.session_state["busca"] = qp.get("secao") or qp.get("busca") or ""
    if "zona" not in st.session_state:
        z_qp = str(qp.get("zona", "")).strip()
        st.session_state["zona"] = next((o for o, n in por_rotulo.items() if str(n) == z_qp), opcoes[0])

    topo_hero = st.empty()
    c1, c2, c3 = st.columns([1.5, 1.2, 0.9], vertical_alignment="bottom")
    with c1:
        busca = st.text_input("Buscar seção ou escola", key="busca", placeholder="Ex.: 045 ou Darcy Ribeiro")
    with c2:
        zona_txt = st.selectbox("Zona de cobertura", opcoes, key="zona")
    with c3:
        manchas = st.toggle("Manchas das zonas", value=True, key="manchas")

    zona_sel = por_rotulo.get(zona_txt)
    tipo, termo = interpretar_busca(busca)
    secao = termo if tipo == "secao" else ""

    vis = df
    foco: set = set()
    if tipo == "secao":  # seção procura na zona toda, ignorando o filtro de zona
        vis = df[df["SECOES"].apply(lambda lista: secao in lista)]
        foco = set(vis.index)
        zona_sel = None
    else:
        if zona_sel is not None:
            vis = vis[vis["ZONA"] == zona_sel]
        if tipo == "texto":
            palavras = termo.split()
            vis = vis[vis["BUSCA"].apply(lambda b: all(p in b for p in palavras))]
            if len(vis) <= 3:
                foco = set(vis.index)

    # ---- Cabeçalho com a contagem do que está no mapa
    if tipo == "secao":
        rotulo = f"Seção {secao}" if len(vis) else f"Seção {secao} não encontrada"
    elif zona_sel is not None:
        rotulo = f"Zona {zona_sel} · {zonas.loc[zona_sel].NOME}"
    elif tipo == "texto":
        rotulo = f"locais com “{texto(busca)}”"
    else:
        rotulo = f"de {len(df)} locais"
    with topo_hero.container():
        html(hero(len(vis), rotulo))

    # ---- Resultado da busca
    if tipo == "secao":
        if vis.empty:
            html(nota(f"A seção <b>{esc(secao)}</b> não está na planilha da 92ª Zona. Confira o número no título "
                      "de eleitor ou no e-Título.", "al", "alerta"))
        for r in vis.itertuples():
            html(card_resultado(r, zonas.loc[r.ZONA], secao))
        if len(vis) > 1:
            html(nota(f"A seção <b>{esc(secao)}</b> aparece em {len(vis)} locais na planilha. "
                      "Vale conferir qual está certo.", "al", "alerta"))
    elif tipo == "texto" and vis.empty:
        html(nota(f"Nenhum local encontrado para <b>{esc(texto(busca))}</b>"
                  f"{' nesta zona' if zona_sel else ''}. Tente outra parte do nome ou o bairro.", "al", "busca"))

    # ---- Mapa
    html(f"""<div class="cv"><div class="mz-mapa-cab"><div class="cv-sec" style="margin:0">
<div class="cv-sec-t" role="heading" aria-level="2">Mapa interativo</div>
<div class="cv-sec-s">Toque num pino para ver as seções e abrir a rota. O número no pino é a zona.</div></div>
<span class="cv-chip">{ic("camadas", "p")}Noturno ou ruas no canto do mapa</span></div></div>""")
    mapa = montar_mapa(df, zonas, vis, foco, manchas, zona_sel, secao)
    chave = f"mapa_{tipo}_{termo}_{zona_sel}_{manchas}"
    try:
        st_folium(mapa, height=ALTURA_MAPA, use_container_width=True, returned_objects=[], key=chave)
    except TypeError:  # versões antigas do streamlit-folium
        st_folium(mapa, height=ALTURA_MAPA, width="100%", returned_objects=[], key=chave)

    # ---- Números, zonas e lista de locais
    html(kpis(df, zonas))
    html(secao_titulo("Zonas de cobertura", f"{len(zonas)} zonas agrupadas por proximidade, numeradas de norte a sul."))
    html(legenda_zonas(zonas, zona_sel, set(vis["ZONA"]) if tipo else set()))

    if len(vis):
        todos = len(vis) == len(df)
        sub = (f"Todos os {len(df)} locais, por zona · toque para ver as seções" if todos
               else f"{len(vis)} {'local' if len(vis) == 1 else 'locais'} · toque para ver as seções")
        html(secao_titulo("Locais de votação", sub))
        html(lista_locais(vis, zonas, secao, abrir=len(vis) <= 3, recolher=todos))

    if sem_coord:
        html(nota(f"{len(sem_coord)} local(is) sem coordenada na planilha não aparecem no mapa: "
                  f"{esc(', '.join(sem_coord))}.", "al", "alerta"))

    html(f'<div class="cv"><div class="cv-rodape">Mapa da Zona 2026 · 92ª Zona Eleitoral de Araruama<br>'
         f'Análise e Desenvolvimento de Sistemas</div></div>')


main()
