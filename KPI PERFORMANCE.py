import streamlit as st
import pandas as pd
import plotly.express as px
import unicodedata
import re
from difflib import get_close_matches

# =========================
# Helpers de normalização
# =========================
_SUFFIXES_TO_STRIP = ["info", "min", "max", "avg", "mean", "median", "std", "ref", "target"]

def _normalize(s: str) -> str:
    s = str(s)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = s.strip().lower()
    s = re.sub(r"[_\-/]+", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s

def _strip_metric_suffixes(normalized_name: str) -> str:
    tokens = normalized_name.split()
    while tokens and tokens[-1] in _SUFFIXES_TO_STRIP:
        tokens.pop()
    return " ".join(tokens)

def build_normalized_columns_map(df: pd.DataFrame):
    norm_map = {}
    for c in df.columns:
        nfull = _normalize(c)
        nbase = _strip_metric_suffixes(nfull)
        if nfull not in norm_map:
            norm_map[nfull] = c
        if nbase and nbase not in norm_map:
            norm_map[nbase] = c
    return norm_map

def resolve_columns(df: pd.DataFrame, required_keys: list[str]) -> dict:
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
        for cand in candidates:
            if cand in norm_map:
                found = norm_map[cand]; break
        if not found:
            for cand in candidates:
                hits = [k for k in norm_keys_available if k.startswith(cand + " ")]
                if hits: found = norm_map[hits[0]]; break
            if not found:
                for cand in candidates:
                    hits = [k for k in norm_keys_available if f" {cand} " in f" {k} "]
                    if hits: found = norm_map[hits[0]]; break
        if not found:
            for cand in candidates:
                hits = get_close_matches(cand, norm_keys_available, n=1, cutoff=0.7)
                if hits: found = norm_map[hits[0]]; break
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
        drivername_col = col_map['drivername']

        # SessionLapDate
        if pd.api.types.is_datetime64_any_dtype(df[sessiondate_col]):
            sessiondate_str = df[sessiondate_col].dt.strftime("%Y-%m-%d %H:%M:%S").astype(str)
        else:
            s_try = pd.to_datetime(df[sessiondate_col], errors='coerce')
            sessiondate_str = s_try.dt.strftime("%Y-%m-%d %H:%M:%S").fillna(df[sessiondate_col].astype(str))
        df['SessionLapDate'] = (
            sessiondate_str +
            ' | Run ' + df[run_col].astype(str) +
            ' | Lap ' + df[lap_col].astype(str) +
            ' | ' + df[sessionname_col].astype(str) +
            ' | Track ' + df[trackname_col].astype(str)
        )

        # Sidebar: filtros gerais
        st.sidebar.header("Filtros Line Plot")
        car_alias = st.sidebar.selectbox("CarAlias:", sorted(df[col_map['caralias']].dropna().astype(str).unique()))
        tracks = ["TODAS"] + sorted(pd.Series(df[trackname_col].dropna().astype(str).unique()).tolist())
        selected_track = st.sidebar.selectbox("Etapa (TrackName):", tracks)

        cols_excluir_reais = [col_map[k] for k in required] + ['SessionLapDate']
        numeric_cols = df.select_dtypes(include='number').columns.tolist()
        metricas = [c for c in numeric_cols if c not in cols_excluir_reais] or numeric_cols

        base = df[df[col_map['caralias']].astype(str) == str(car_alias)]
        if selected_track != "TODAS":
            base = base[base[trackname_col].astype(str) == str(selected_track)]

        def _safe_num(s): return pd.to_numeric(s, errors='coerce')
        def order_df(dfin):
            sdate_ord = pd.to_datetime(dfin[sessiondate_col], errors='coerce')
            return dfin.assign(
                __sdate_ord=sdate_ord,
                __run_ord=_safe_num(dfin[run_col]),
                __lap_ord=_safe_num(dfin[lap_col]),
            ).sort_values(by=["__sdate_ord", "__run_ord", "__lap_ord"], kind="mergesort")

        def apply_individual_filters(df_in, driver_sel, mode_sel, session_sel):
            out = df_in
            if driver_sel:
                out = out[out[drivername_col].astype(str) == str(driver_sel)]
                if mode_sel == "Apenas uma" and session_sel:
                    out = out[out[sessionname_col].astype(str) == str(session_sel)]
            return out

        # ---------- 8 blocos explícitos de seleção na SIDEBAR ----------
        # G1
        y1 = st.sidebar.selectbox("Métrica para Gráfico 1:", metricas, index=0 if metricas else 0, key="metric_g1")
        en1 = st.sidebar.checkbox("Filtrar por Driver (G1)", key="enable_g1")
        d1 = s1m = s1 = None
        if en1:
            d1 = st.sidebar.selectbox("Driver (G1):", sorted(base[drivername_col].dropna().astype(str).unique()), key="driver_g1")
            s1m = st.sidebar.radio("Sessões (G1):", ["Todas", "Apenas uma"], index=0, horizontal=True, key="sessmode_g1")
            if s1m == "Apenas uma":
                s1 = st.sidebar.selectbox("SessionName (G1):",
                    sorted(base[base[drivername_col].astype(str) == str(d1)][sessionname_col].dropna().astype(str).unique()),
                    key="session_g1")

        # G2
        y2 = st.sidebar.selectbox("Métrica para Gráfico 2:", metricas, index=1 if len(metricas)>1 else 0, key="metric_g2")
        en2 = st.sidebar.checkbox("Filtrar por Driver (G2)", key="enable_g2")
        d2 = s2m = s2 = None
        if en2:
            d2 = st.sidebar.selectbox("Driver (G2):", sorted(base[drivername_col].dropna().astype(str).unique()), key="driver_g2")
            s2m = st.sidebar.radio("Sessões (G2):", ["Todas", "Apenas uma"], index=0, horizontal=True, key="sessmode_g2")
            if s2m == "Apenas uma":
                s2 = st.sidebar.selectbox("SessionName (G2):",
                    sorted(base[base[drivername_col].astype(str) == str(d2)][sessionname_col].dropna().astype(str).unique()),
                    key="session_g2")

        # G3
        y3 = st.sidebar.selectbox("Métrica para Gráfico 3:", metricas, index=2 if len(metricas)>2 else 0, key="metric_g3")
        en3 = st.sidebar.checkbox("Filtrar por Driver (G3)", key="enable_g3")
        d3 = s3m = s3 = None
        if en3:
            d3 = st.sidebar.selectbox("Driver (G3):", sorted(base[drivername_col].dropna().astype(str).unique()), key="driver_g3")
            s3m = st.sidebar.radio("Sessões (G3):", ["Todas", "Apenas uma"], index=0, horizontal=True, key="sessmode_g3")
            if s3m == "Apenas uma":
                s3 = st.sidebar.selectbox("SessionName (G3):",
                    sorted(base[base[drivername_col].astype(str) == str(d3)][sessionname_col].dropna().astype(str).unique()),
                    key="session_g3")

        # G4
        y4 = st.sidebar.selectbox("Métrica para Gráfico 4:", metricas, index=3 if len(metricas)>3 else 0, key="metric_g4")
        en4 = st.sidebar.checkbox("Filtrar por Driver (G4)", key="enable_g4")
        d4 = s4m = s4 = None
        if en4:
            d4 = st.sidebar.selectbox("Driver (G4):", sorted(base[drivername_col].dropna().astype(str).unique()), key="driver_g4")
            s4m = st.sidebar.radio("Sessões (G4):", ["Todas", "Apenas uma"], index=0, horizontal=True, key="sessmode_g4")
            if s4m == "Apenas uma":
                s4 = st.sidebar.selectbox("SessionName (G4):",
                    sorted(base[base[drivername_col].astype(str) == str(d4)][sessionname_col].dropna().astype(str).unique()),
                    key="session_g4")

        # G5
        y5 = st.sidebar.selectbox("Métrica para Gráfico 5:", metricas, index=4 if len(metricas)>4 else 0, key="metric_g5")
        en5 = st.sidebar.checkbox("Filtrar por Driver (G5)", key="enable_g5")
        d5 = s5m = s5 = None
        if en5:
            d5 = st.sidebar.selectbox("Driver (G5):", sorted(base[drivername_col].dropna().astype(str).unique()), key="driver_g5")
            s5m = st.sidebar.radio("Sessões (G5):", ["Todas", "Apenas uma"], index=0, horizontal=True, key="sessmode_g5")
            if s5m == "Apenas uma":
                s5 = st.sidebar.selectbox("SessionName (G5):",
                    sorted(base[base[drivername_col].astype(str) == str(d5)][sessionname_col].dropna().astype(str).unique()),
                    key="session_g5")

        # G6
        y6 = st.sidebar.selectbox("Métrica para Gráfico 6:", metricas, index=5 if len(metricas)>5 else 0, key="metric_g6")
        en6 = st.sidebar.checkbox("Filtrar por Driver (G6)", key="enable_g6")
        d6 = s6m = s6 = None
        if en6:
            d6 = st.sidebar.selectbox("Driver (G6):", sorted(base[drivername_col].dropna().astype(str).unique()), key="driver_g6")
            s6m = st.sidebar.radio("Sessões (G6):", ["Todas", "Apenas uma"], index=0, horizontal=True, key="sessmode_g6")
            if s6m == "Apenas uma":
                s6 = st.sidebar.selectbox("SessionName (G6):",
                    sorted(base[base[drivername_col].astype(str) == str(d6)][sessionname_col].dropna().astype(str).unique()),
                    key="session_g6")

        # G7
        y7 = st.sidebar.selectbox("Métrica para Gráfico 7:", metricas, index=6 if len(metricas)>6 else 0, key="metric_g7")
        en7 = st.sidebar.checkbox("Filtrar por Driver (G7)", key="enable_g7")
        d7 = s7m = s7 = None
        if en7:
            d7 = st.sidebar.selectbox("Driver (G7):", sorted(base[drivername_col].dropna().astype(str).unique()), key="driver_g7")
            s7m = st.sidebar.radio("Sessões (G7):", ["Todas", "Apenas uma"], index=0, horizontal=True, key="sessmode_g7")
            if s7m == "Apenas uma":
                s7 = st.sidebar.selectbox("SessionName (G7):",
                    sorted(base[base[drivername_col].astype(str) == str(d7)][sessionname_col].dropna().astype(str).unique()),
                    key="session_g7")

        # G8
        y8 = st.sidebar.selectbox("Métrica para Gráfico 8:", metricas, index=7 if len(metricas)>7 else 0, key="metric_g8")
        en8 = st.sidebar.checkbox("Filtrar por Driver (G8)", key="enable_g8")
        d8 = s8m = s8 = None
        if en8:
            d8 = st.sidebar.selectbox("Driver (G8):", sorted(base[drivername_col].dropna().astype(str).unique()), key="driver_g8")
            s8m = st.sidebar.radio("Sessões (G8):", ["Todas", "Apenas uma"], index=0, horizontal=True, key="sessmode_g8")
            if s8m == "Apenas uma":
                s8 = st.sidebar.selectbox("SessionName (G8):",
                    sorted(base[base[drivername_col].astype(str) == str(d8)][sessionname_col].dropna().astype(str).unique()),
                    key="session_g8")

        # ---------- Render dos 8 gráficos ----------
        cfgs = [
            (1, y1, d1, s1m or "Todas", s1),
            (2, y2, d2, s2m or "Todas", s2),
            (3, y3, d3, s3m or "Todas", s3),
            (4, y4, d4, s4m or "Todas", s4),
            (5, y5, d5, s5m or "Todas", s5),
            (6, y6, d6, s6m or "Todas", s6),
            (7, y7, d7, s7m or "Todas", s7),
            (8, y8, d8, s8m or "Todas", s8),
        ]

        for (i, y_i, d_i, sm_i, s_i) in cfgs:
            with st.container():
                df_g = apply_individual_filters(base, d_i, sm_i, s_i)
                df_g = order_df(df_g)
                if y_i in df_g.columns and not df_g.empty:
                    fig = px.line(df_g, x='SessionLapDate', y=y_i, color=trackname_col, markers=True, title=f"Gráfico {i}")
                    fig.update_layout(title_font=dict(size=40, color="white"), height=600, legend_title_text=trackname_col)
                    fig.update_xaxes(type='category', categoryorder='array', categoryarray=df_g['SessionLapDate'].tolist())
                    st.plotly_chart(fig, use_container_width=True)
                    c1, c2, c3 = st.columns(3)
                    with c1: st.metric("Mínimo", f"{pd.to_numeric(df_g[y_i], errors='coerce').min():.2f}")
                    with c2: st.metric("Máximo", f"{pd.to_numeric(df_g[y_i], errors='coerce').max():.2f}")
                    with c3: st.metric("Média",  f"{pd.to_numeric(df_g[y_i], errors='coerce').mean():.2f}")
                else:
                    st.warning(f"⚠️ Gráfico {i} sem dados para os filtros selecionados ou métrica ausente.")

        # ---------- Dispersão (inalterado) ----------
        st.sidebar.header("Dispersão")
        numeric_cols_all = df.select_dtypes(include='number').columns.tolist()
        metricas_all = [c for c in numeric_cols_all if c not in cols_excluir_reais] or numeric_cols_all

        x = st.sidebar.selectbox("Métrica X:", metricas_all, index=0 if metricas_all else 0)
        y = st.sidebar.selectbox("Métrica Y:", metricas_all, index=1 if len(metricas_all) > 1 else 0)
        show_trend = st.sidebar.checkbox("Mostrar linha de tendência")

        if x and y and x in df.columns and y in df.columns:
            fig3 = px.scatter(
                df, x=x, y=y,
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
