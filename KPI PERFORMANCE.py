import streamlit as st
import pandas as pd
import plotly.express as px
import unicodedata
import re
from difflib import get_close_matches

# =========================
# Helpers para normalização
# =========================
_SUFFIXES_TO_STRIP = [
    "info", "min", "max", "avg", "mean", "median", "std", "ref", "target"
]

def _normalize(s: str) -> str:
    """lower, trim, remove accents, collapse spaces/underscores/hífens."""
    s = str(s)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = s.strip().lower()
    s = re.sub(r"[_\-/]+", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s

def _strip_metric_suffixes(normalized_name: str) -> str:
    """
    Remove sufixos comuns à direita: ' - info / - max / - min / - avg ...'
    Ex.: 'caralias info' -> 'caralias'
         'lap   -  info' -> 'lap'
    """
    tokens = normalized_name.split()
    # Se último token for um dos sufixos, remova repetidamente
    while tokens and tokens[-1] in _SUFFIXES_TO_STRIP:
        tokens.pop()
    return " ".join(tokens)

def build_normalized_columns_map(df: pd.DataFrame):
    """
    Mapeia:
      - nome normalizado completo -> nome real
      - nome normalizado sem sufixo -> nome real (prioriza a 1ª ocorrência)
    """
    norm_map = {}
    for c in df.columns:
        nfull = _normalize(c)
        nbase = _strip_metric_suffixes(nfull)
        if nfull not in norm_map:
            norm_map[nfull] = c
        # guarde também a versão sem sufixo
        if nbase and nbase not in norm_map:
            norm_map[nbase] = c
    return norm_map

def resolve_columns(df: pd.DataFrame, required_keys: list[str]) -> dict:
    """
    Resolve colunas obrigatórias mesmo com nomes diferentes/sufixos.
    Retorna dict: { required_key -> nome_coluna_real_no_df }
    """
    norm_map = build_normalized_columns_map(df)
    norm_keys_available = list(norm_map.keys())

    aliases = {
        "caralias": ["caralias", "car alias", "car", "carro", "vehicle", "car id", "car number", "carno", "n carro"],
        "sessiondate": ["sessiondate", "session date", "date", "data", "session day", "dia", "data sessao"],
        "run": ["run", "stint", "stint id", "stint no", "stint number", "corrida", "bateria"],
        "trackname": ["trackname", "track name", "track", "circuit", "circuito", "etapa"],
        "drivername": ["drivername", "driver", "piloto", "nome piloto", "driver name"],
        "sessionname": ["sessionname", "session", "nome sessao", "tipo sessao", "session type", "practice", "qualifying", "race"],
        "lap": ["lap", "lapnumber", "lap number", "lap no", "n volta", "volta", "lapcount", "lap idx"],
    }

    resolved = {}
    for key in required_keys:
        candidates = [_normalize(key)] + [_normalize(a) for a in aliases.get(key, [])]

        found = None
        # 1) match direto no mapa (com e sem sufixo)
        for cand in candidates:
            if cand in norm_map:
                found = norm_map[cand]
                break

        # 2) começa com/contém (ex.: 'caralias info' contém 'caralias')
        if not found:
            for cand in candidates:
                # tenta "startswith"
                hits = [k for k in norm_keys_available if k.startswith(cand + " ")]
                if hits:
                    found = norm_map[hits[0]]
                    break
            if not found:
                for cand in candidates:
                    hits = [k for k in norm_keys_available if f" {cand} " in f" {k} "]
                    if hits:
                        found = norm_map[hits[0]]
                        break

        # 3) fuzzy (cutoff mais baixo por causa de espaços extras)
        if not found:
            for cand in candidates:
                hits = get_close_matches(cand, norm_keys_available, n=1, cutoff=0.7)
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
    df = pd.read_excel(uploaded_file, header=0)
    df = df.dropna(axis=1, how='all')
    df.columns = df.columns.map(str)

    required = ['caralias', 'sessiondate', 'run', 'trackname', 'drivername', 'sessionname', 'lap']
    col_map = resolve_columns(df, required)

    missing = [k for k in required if k not in col_map]
    if missing:
        st.error("❌ Planilha não contém as colunas obrigatórias:\n" + ", ".join(missing))
        with st.expander("Ver colunas detectadas no arquivo"):
            st.write(sorted(list(df.columns)))
    else:
        sessiondate_col = col_map['sessiondate']
        run_col = col_map['run']
        lap_col = col_map['lap']
        sessionname_col = col_map['sessionname']
        trackname_col = col_map['trackname']

        # Formata sessiondate
        if pd.api.types.is_datetime64_any_dtype(df[sessiondate_col]):
            sessiondate_str = df[sessiondate_col].dt.strftime("%Y-%m-%d %H:%M:%S").astype(str)
        else:
            # tenta converter
            s_try = pd.to_datetime(df[sessiondate_col], errors='coerce')
            sessiondate_str = s_try.dt.strftime("%Y-%m-%d %H:%M:%S").fillna(df[sessiondate_col].astype(str))

        df['SessionLapDate'] = (
            sessiondate_str +
            ' | Run ' + df[run_col].astype(str) +
            ' | Lap ' + df[lap_col].astype(str) +
            ' | ' + df[sessionname_col].astype(str) +
            ' | Track ' + df[trackname_col].astype(str)
        )

        # Sidebar - Filtros Line Plot
        st.sidebar.header("Filtros Line Plot")
        car_alias = st.sidebar.selectbox("CarAlias:", sorted(df[col_map['caralias']].dropna().astype(str).unique()))
        tracks = ["TODAS"] + sorted(pd.Series(df[trackname_col].dropna().astype(str).unique()).tolist())
        selected_track = st.sidebar.selectbox("Etapa (TrackName):", tracks)

        # métricas = todas numéricas exceto obrigatórias + identificador
        cols_excluir_reais = [col_map[k] for k in required] + ['SessionLapDate']
        numeric_cols = df.select_dtypes(include='number').columns.tolist()
        metricas = [c for c in numeric_cols if c not in cols_excluir_reais]
        if len(metricas) < 1:
            st.warning("⚠️ Não encontrei métricas numéricas além das colunas obrigatórias.")
            metricas = numeric_cols

        y1 = st.sidebar.selectbox("Métrica para Gráfico 1:", metricas, index=0 if metricas else None)
        y2 = st.sidebar.selectbox("Métrica para Gráfico 2:", metricas, index=1 if len(metricas) > 1 else 0)

        # Filtragem e ordenação
        df_filtrado = df[df[col_map['caralias']].astype(str) == str(car_alias)]
        if selected_track != "TODAS":
            df_filtrado = df_filtrado[df_filtrado[trackname_col].astype(str) == str(selected_track)]

        def _safe_num(s): return pd.to_numeric(s, errors='coerce')

        sdate_ord = pd.to_datetime(df_filtrado[sessiondate_col], errors='coerce')
        df_filtrado = df_filtrado.assign(
            __sdate_ord=sdate_ord,
            __run_ord=_safe_num(df_filtrado[run_col]),
            __lap_ord=_safe_num(df_filtrado[lap_col]),
        ).sort_values(by=["__sdate_ord", "__run_ord", "__lap_ord"], kind="mergesort")

        # Gráficos de Linha (2) — layout mantido
        for y, titulo in zip([y1, y2], ["Gráfico 1", "Gráfico 2"]):
            if y not in df_filtrado.columns:
                st.warning(f"⚠️ Métrica '{y}' não encontrada.")
                continue
            fig = px.line(
                df_filtrado,
                x='SessionLapDate',
                y=y,
                color=trackname_col,
                markers=True,
                title=titulo
            )
            fig.update_layout(title_font=dict(size=40, color="white"), height=600, legend_title_text=trackname_col)
            fig.update_xaxes(type='category', categoryorder='array', categoryarray=df_filtrado['SessionLapDate'].tolist())
            st.plotly_chart(fig, use_container_width=True)

            c1, c2, c3 = st.columns(3)
            with c1: st.metric("Mínimo", f"{pd.to_numeric(df_filtrado[y], errors='coerce').min():.2f}")
            with c2: st.metric("Máximo", f"{pd.to_numeric(df_filtrado[y], errors='coerce').max():.2f}")
            with c3: st.metric("Média",  f"{pd.to_numeric(df_filtrado[y], errors='coerce').mean():.2f}")

        # Dispersão — layout mantido
        st.sidebar.header("Dispersão")
        numeric_cols_all = df.select_dtypes(include='number').columns.tolist()
        metricas_all = [c for c in numeric_cols_all if c not in cols_excluir_reais] or numeric_cols_all

        x = st.sidebar.selectbox("Métrica X:", metricas_all, index=0 if metricas_all else None)
        y = st.sidebar.selectbox("Métrica Y:", metricas_all, index=1 if len(metricas_all) > 1 else 0)
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
