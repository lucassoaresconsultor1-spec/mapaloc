# Mapa da Zona 2026

Mapa interativo dos locais de votação da 92ª Zona Eleitoral de Araruama/RJ, no mesmo visual "Azul Vidro" do painel Campanha 2026 e do Carona Amiga.

- Busca por número da seção (ex.: `45` ou `seção 045`) ou por nome da escola/bairro, sem precisar de acento
- 20 zonas de cobertura agrupadas por proximidade, numeradas de norte a sul, com manchas no mapa
- Pinos com o número da zona, cartão com as seções e botões "Como chegar" e "Abrir no Maps"
- Mapa noturno ou de ruas (ícone de camadas no canto do mapa) e tela cheia

## Links diretos

| Link | Abre |
|---|---|
| `https://mapa2026.streamlit.app/?secao=45` | já na seção 045 |
| `https://mapa2026.streamlit.app/?busca=darcy` | com a busca preenchida |
| `https://mapa2026.streamlit.app/?zona=3` | filtrado na Zona 3 |

## Atualizar os dados

Troque a planilha `.tsv` (ou envie `.csv`/`.xlsx`) mantendo as colunas `SEÇÕES`, `LOCAIS DE VOTAÇÃO`, `LINK` e `LATITUDE, LONGITUDE`. As coordenadas podem usar ponto ou vírgula.

## Arquivos

- `app_mapa_votacao.py` — o app
- `.streamlit/config.toml` — tema escuro igual ao do painel
- `requirements.txt` — bibliotecas
