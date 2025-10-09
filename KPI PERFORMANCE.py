import streamlit as st
import pandas as pd
import plotly.express as px
import unicodedata
import re
from difflib import get_close_matches

# =========================
# Helpers para normalização
# =========================
def _normalize(s: str) -> str:
    """lower, trim, remove accents, collapse spaces/underscores/hífens."""
    s = str(s)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = s.strip().lower()
    s = re.sub(r"[\s_\-\/]+", " ", s)
    return s

def build_normalized_columns_map(df: pd.DataFrame):
    """Mapeia versão normalizada -> nome real da coluna no DF (primeira ocorrência)."""
    norm_map = {}
    for c in df.columns:
        norm = _normalize(c)
        if norm not in norm_map:
            norm_map[norm] = c
    return norm_map

def resolve_columns(df: pd.DataFrame, required_keys: list[str]) -> dict:
    """
    Resolve colunas obrigatórias mesmo com nomes diferentes.
    Retorna dict: { required_key -> nome_coluna_real_no_df }
    """
    norm_map = build_normalized_columns_map(df)

    # Dicionário de sinônimos (inclui PT/EN variações comuns)
    aliases = {
        "caralias": [
            "caralias", "car alias", "car", "carro", "veiculo", "vehicle", "car id", "car number", "carno", "n carro"
        ],
        "sessiondate": [
            "sessiondate", "session date", "date", "data", "session day", "dia", "data sessao"
        ],
        "run": [
            "run", "stint", "stint id", "stint no", "stint number", "corrida", "bateria"
        ],
        "trackname": [
            "trackname", "track name", "track", "circuit", "circuito", "etapa"
        ],
        "drivername": [
            "drivername", "driver", "piloto", "nome piloto", "driver name"
        ],
        "sessionname": [
            "sessionname", "session", "nome sessao", "tipo sessao", "session type", "practice", "qualifying", "race"
        ],
        "lap": [
            "lap", "lapnumber", "lap number", "lap no", "n volta", "volta", "lapcount", "lap idx"
        ],
    }

    resolved = {}
    # Primeiro: tentativa direta por sinônimos
    for key in required_keys:
        found = None
        # 1) Sinônimos explícitos
        for candidate in aliases.get(key, []):
            norm_c = _normalize(candidate)
            if norm_c in norm_map:
                found = norm_map[norm_c]
                break
        # 2) Fuzzy match se não achou
        if not found:
            norm_keys = list(norm_map.keys())
            # tenta com a própria chave
            hits = get_close_matches(_normalize(key), norm_keys, n=1, cutoff=0.8)
            if hits:
                found = norm_map[hits[0]]
            else:
                # tenta com todos sinônimos daquela chave
                for cand in aliases.get(key, []):
                    hits = get_close_matches(_normalize(cand), norm_keys, n=1, cutoff=0.8)
                    if hits:
                        found = norm_map[hits[0]]
                        break
        if found:
            resolved[key] = found

    return resolved

# =========================
# APP (layout mantido)
# =========================
st.set_page_config(layout="wide")
st.title("KPI VITAIS - Análise Dinâmica")

uploaded_file = st.file_uploader("Escolha a planilha (.xlsx):", type=["xlsx"])

if uploaded_file:
    # Leitura e limpeza básica
    df = pd.read_excel(uploaded_file, header=0)
    df = df.dropna(axis=1, how='all')
    df.columns = df.columns.map(str)

    # Tenta resolver colunas obrigatórias com nomes diferentes
    required = ['caralias', 'sessiondate', 'run', 'trackname', 'drivername', 'sessionname', 'lap']
    col_map = resolve_columns(df, required)

    # Se faltar algo, informa o que está faltando (sem mudar layout)
    missing = [k for k in required if k not in col_map]
    if missing:
        st.error("❌ Planilha não contém (ou não consegui identificar) as colunas obrigatórias:\n" + ", ".join(missing))
        # Ajuda extra: mostra sugestão dos nomes que existem
        with st.expander("Ver colunas detectadas no arquivo"):
            st.write(sorted(list(df.columns)))
    else:
        # Cria um identificador textual por volta, mantendo a ideia original
        # Tenta converter sessiondate para string segura
        sessiondate_col = col_map['sessiondate']
        run_col = col_map['run']
        lap_col = col_map['lap']
        sessionname_col = col_map['sessionname']
        trackname_col = col_map['trackname']

        # Se sessiondate for datetime, formata amigável
        if pd.api.types.is_datetime64_any_dtype(df[sessiondate_col]):
            sessiondate_str = df[sessiondate_col].dt.strftime("%Y-%m-%d %H:%M:%S").astype(str)
        else:
            sessiondate_str = df[sessiondate_col].astype(str)

        df['SessionLapDate'] = (
            sessiondate_str +
            ' | Run ' + df[run_col].astype(str) +
            ' | Lap ' + df[lap_col].astype(str) +
            ' | ' + df[sessionname_col].astype(str) +
            ' | Track ' + df[trackname_col].astype(str)
        )

        # =========================
        # Sidebar - Filtros Line
        # =========================
        st.sidebar.header("Filtros Line Plot")

        # CarAlias
        car_alias = st.sidebar.selectbox("CarAlias:", sorted(df[col_map['caralias']].dropna().astype(str).unique()))

        # TrackName (com opção TODAS)
        tracks = ["TODAS"] + sorted(pd.Series(df[trackname_col].dropna().astype(str).unique()).tolist())
        selected_track = st.sidebar.selectbox("Etapa (TrackName):", tracks)

        # Define métricas (todas numéricas, exceto colunas obrigatórias e a SessionLapDate)
        # Observação: se houverem novas colunas numéricas, elas entram automaticamente
        cols_excluir_reais = [col_map[k] for k in required] + ['SessionLapDate']
        numeric_cols = df.select_dtypes(include='number').columns.tolist()
        metricas = [c for c in numeric_cols if c not in cols_excluir_reais]

        if len(metricas) < 1:
            st.warning("⚠️ Não encontrei métricas numéricas além das colunas obrigatórias. Verifique se há colunas numéricas adicionais.")
            metricas = numeric_cols  # fallback: deixa escolher, mesmo que vazio

        y1 = st.sidebar.selectbox("Métrica para Gráfico 1:", metricas, index=0 if metricas else None)
        y2 = st.sidebar.selectbox("Métrica para Gráfico 2:", metricas, index=1 if len(metricas) > 1 else 0)

        # =========================
        # Filtragem e ordenação
        # =========================
        df_filtrado = df[df[col_map['caralias']].astype(str) == str(car_alias)]
        if selected_track != "TODAS":
            df_filtrado = df_filtrado[df_filtrado[trackname_col].astype(str) == str(selected_track)]

        # Ordena respeitando data/run/lap (mesmo que tipos estejam como string)
        # Tenta converter para tipos corretos antes
        def _safe_numeric(s):
            try:
                return pd.to_numeric(s, errors='coerce')
            except Exception:
                return s

        # sessiondate ordenável
        if pd.api.types.is_datetime64_any_dtype(df_filtrado[sessiondate_col]):
            sdate_ord = df_filtrado[sessiondate_col]
        else:
            # tenta converter
            sdate_try = pd.to_datetime(df_filtrado[sessiondate_col], errors='coerce', dayfirst=False)
            sdate_ord = sdate_try

        df_filtrado = df_filtrado.assign(
            __run_ord=_safe_numeric(df_filtrado[run_col]),
            __lap_ord=_safe_numeric(df_filtrado[lap_col]),
            __sdate_ord=sdate_ord
        ).sort_values(by=["__sdate_ord", "__run_ord", "__lap_ord"], kind="mergesort")  # estável

        # =========================
        # Gráficos de Linha (2)
        # =========================
        for y, titulo in zip([y1, y2], ["Gráfico 1", "Gráfico 2"]):
            if y not in df_filtrado.columns:
                st.warning(f"⚠️ Métrica '{y}' não encontrada após a normalização das colunas.")
                continue
            fig = px.line(
                df_filtrado,
                x='SessionLapDate',
                y=y,
                color=trackname_col,
                markers=True,
                title=titulo
            )
            fig.update_layout(
                title_font=dict(size=40, color="white"),
                height=600,
                legend_title_text=trackname_col
            )
            # Ajuda a manter ordem cronológica do eixo X como categórico ordenado
            fig.update_xaxes(type='category', categoryorder='array', categoryarray=df_filtrado['SessionLapDate'].tolist())

            st.plotly_chart(fig, use_container_width=True)

            # Estatísticas
            col_min, col_max, col_avg = st.columns(3)
            with col_min:
                st.metric("Mínimo", f"{pd.to_numeric(df_filtrado[y], errors='coerce').min():.2f}")
            with col_max:
                st.metric("Máximo", f"{pd.to_numeric(df_filtrado[y], errors='coerce').max():.2f}")
            with col_avg:
                st.metric("Média", f"{pd.to_numeric(df_filtrado[y], errors='coerce').mean():.2f}")

        # =========================
        # Dispersão (mantido)
        # =========================
        st.sidebar.header("Dispersão")
        # Recalcula metricas do DF inteiro (não filtrado) para a dispersão, incluindo novas colunas
        numeric_cols_all = df.select_dtypes(include='number').columns.tolist()
        metricas_all = [c for c in numeric_cols_all if c not in cols_excluir_reais]
        if len(metricas_all) < 2 and len(numeric_cols_all) >= 2:
            metricas_all = numeric_cols_all  # fallback

        if len(metricas_all) >= 1:
            x = st.sidebar.selectbox("Métrica X:", metricas_all, index=0)
            y = st.sidebar.selectbox("Métrica Y:", metricas_all, index=1 if len(metricas_all) > 1 else 0)
        else:
            x = None
            y = None

        show_trend = st.sidebar.checkbox("Mostrar linha de tendência")

        if x and y and x in df.columns and y in df.columns:
            fig3 = px.scatter(
                df,
                x=x,
                y=y,
                color=trackname_col if trackname_col in df.columns else None,
                trendline="ols" if show_trend else None,
                hover_data=[sessionname_col if sessionname_col in df.columns else None,
                            lap_col if lap_col in df.columns else None,
                            run_col if run_col in df.columns else None],
                title="Dispersão"
            )
            fig3.update_layout(title_font=dict(size=40, color="white"), height=600)
            st.plotly_chart(fig3, use_container_width=True)
        else:
            st.info("Selecione métricas numéricas válidas para X e Y na seção Dispersão.")

else:
    st.info("Envie uma planilha .xlsx para iniciar a análise.")
