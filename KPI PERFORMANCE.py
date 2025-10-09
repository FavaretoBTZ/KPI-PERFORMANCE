import streamlit as st
import pandas as pd
import plotly.express as px
import unicodedata, re
from difflib import get_close_matches
import numpy as np

# ---------------------------
# Normalização de nomes
# ---------------------------
_SUFFIXES_TO_STRIP = ["info","min","max","avg","mean","median","std","ref","target"]

def _normalize(s: str) -> str:
    s = str(s)
    s = unicodedata.normalize("NFKD", s).encode("ascii","ignore").decode("ascii")
    s = s.strip().lower()
    s = re.sub(r"[_\-/]+"," ", s)
    s = re.sub(r"\s+"," ", s)
    return s

def _strip_metric_suffixes(n: str) -> str:
    toks = n.split()
    while toks and toks[-1] in _SUFFIXES_TO_STRIP:
        toks.pop()
    return " ".join(toks)

def _norm_map(df: pd.DataFrame):
    m = {}
    for c in df.columns:
        nfull = _normalize(c)
        nbase = _strip_metric_suffixes(nfull)
        if nfull not in m: m[nfull] = c
        if nbase and nbase not in m: m[nbase] = c
    return m

def resolve_columns(df: pd.DataFrame, req: list[str]) -> dict:
    m = _norm_map(df); keys_av = list(m.keys())
    aliases = {
        "caralias":["caralias","car alias","car","carro","vehicle","car id","car number","carno","n carro"],
        "sessiondate":["sessiondate","session date","date","data","session day","dia","data sessao","timestamp","time"],
        "run":["run","stint","stint id","stint no","stint number","corrida","bateria"],
        "trackname":["trackname","track name","track","circuit","circuito","etapa"],
        "drivername":["drivername","driver","piloto","nome piloto","driver name"],
        "sessionname":["sessionname","session","nome sessao","tipo sessao","session type","practice","qualifying","race"],
        "lap":["lap","lapnumber","lap number","lap no","n volta","volta","lapcount","lap idx"],
    }
    out = {}
    for key in req:
        cands = [_normalize(key)] + [_normalize(a) for a in aliases.get(key,[])]
        found = None
        for c in cands:
            if c in m: found = m[c]; break
        if not found:
            for c in cands:
                hits = [k for k in keys_av if k.startswith(c+" ")]
                if hits: found = m[hits[0]]; break
            if not found:
                for c in cands:
                    hits = [k for k in keys_av if f" {c} " in f" {k} "]
                    if hits: found = m[hits[0]]; break
        if not found:
            for c in cands:
                hits = get_close_matches(c, keys_av, n=1, cutoff=0.7)
                if hits: found = m[hits[0]]; break
        if found: out[key] = found
    return out

# ---------------------------
# App
# ---------------------------
st.set_page_config(layout="wide")
st.title("KPI VITAIS - Análise Dinâmica")

uploaded_file = st.file_uploader("Escolha a planilha (.xlsx):", type=["xlsx"])
if not uploaded_file:
    st.info("Envie uma planilha .xlsx para iniciar a análise.")
    st.stop()

# Leitura
df = pd.read_excel(uploaded_file, header=0)
df = df.dropna(axis=1, how='all')
df.columns = df.columns.map(str)

required = ['caralias','sessiondate','run','trackname','drivername','sessionname','lap']
col_map = resolve_columns(df, required)
missing = [k for k in required if k not in col_map]
if missing:
    st.error("❌ Planilha não contém as colunas obrigatórias:\n" + ", ".join(missing))
    with st.expander("Ver colunas detectadas no arquivo"):
        st.write(sorted(list(df.columns)))
    st.stop()

sessiondate_col = col_map['sessiondate']
run_col        = col_map['run']
lap_col        = col_map['lap']
sessionname_col= col_map['sessionname']
trackname_col  = col_map['trackname']
drivername_col = col_map['drivername']

# ---------------------------
# Campos auxiliares (ordem + rótulos)
# ---------------------------
if pd.api.types.is_datetime64_any_dtype(df[sessiondate_col]):
    sdate_str = df[sessiondate_col].dt.strftime("%Y-%m-%d %H:%M:%S").astype(str)
else:
    s_try = pd.to_datetime(df[sessiondate_col], errors='coerce')
    sdate_str = s_try.dt.strftime("%Y-%m-%d %H:%M:%S").fillna(df[sessiondate_col].astype(str))

df['SessionLapDate'] = (
    sdate_str +
    ' | Run ' + df[run_col].astype(str) +
    ' | Lap ' + df[lap_col].astype(str) +
    ' | ' + df[sessionname_col].astype(str) +
    ' | Track ' + df[trackname_col].astype(str)
)

df['XLabelShort'] = (
    'Lap ' + df[lap_col].astype(str) +
    ' | ' + df[sessionname_col].astype(str) +
    ' | ' + df[trackname_col].astype(str)
)

# ---------------------------
# Sidebar - Filtros gerais
# ---------------------------
st.sidebar.header("Filtros Line Plot")
car_alias = st.sidebar.selectbox("CarAlias:", sorted(df[col_map['caralias']].dropna().astype(str).unique()))
tracks = ["TODAS"] + sorted(pd.Series(df[trackname_col].dropna().astype(str).unique()).tolist())
selected_track = st.sidebar.selectbox("Etapa (TrackName):", tracks)

cols_excluir = [col_map[k] for k in required] + ['SessionLapDate', 'XLabelShort']
metricas = [c for c in df.select_dtypes(include='number').columns if c not in cols_excluir]
if not metricas:
    metricas = df.select_dtypes(include='number').columns.tolist()

base = df[df[col_map['caralias']].astype(str) == str(car_alias)]
if selected_track != "TODAS":
    base = base[base[trackname_col].astype(str) == str(selected_track)]

# ---------------------------
# Utils
# ---------------------------
def _safe_num(s): return pd.to_numeric(s, errors='coerce')
_num_pat = re.compile(r"[-+]?\d*[\.,]?\d+")

def _extract_num_series(series: pd.Series) -> pd.Series:
    def _one(x):
        m = _num_pat.search(str(x))
        if not m: return np.nan
        val = m.group(0).replace(",", ".")
        try: return float(val)
        except: return np.nan
    return series.map(_one)

def _order(dfin: pd.DataFrame) -> pd.DataFrame:
    sdate_ord = pd.to_datetime(dfin[sessiondate_col], errors='coerce')
    run_num = _extract_num_series(dfin[run_col])
    lap_num = _extract_num_series(dfin[lap_col])
    return dfin.assign(
        __sdate_ord=sdate_ord,
        __run_ord=run_num,
        __lap_ord=lap_num,
    ).sort_values(by=["__sdate_ord","__run_ord","__lap_ord"], kind="mergesort")

def _apply_filters(df_in, driver_sel, mode_sel, session_sel):
    out = df_in
    if driver_sel:
        out = out[out[drivername_col].astype(str) == str(driver_sel)]
        if mode_sel == "Apenas uma" and session_sel:
            out = out[out[sessionname_col].astype(str) == str(session_sel)]
    return out

def sample_ticks(x_vals: list[str], x_texts: list[str], max_ticks: int = 30):
    n = len(x_vals)
    if n <= max_ticks:
        return x_vals, x_texts
    step = max(1, n // max_ticks)
    idx = list(range(0, n, step))
    if idx[-1] != n - 1:
        idx.append(n - 1)
    return [x_vals[i] for i in idx], [x_texts[i] for i in idx]

# ---------------------------
# Hover (texto construído por ponto, sem "null")
# ---------------------------
def build_hovertext(dfin: pd.DataFrame, metric_col: str) -> list[str]:
    y = pd.to_numeric(dfin[metric_col], errors='coerce')
    def fmt(v): return "—" if pd.isna(v) else f"{v:.3f}"

    base = (
        "<b>" + metric_col + "</b>: " + y.map(fmt).astype(str) +
        "<br><b>Lap - Info</b>: " + dfin[lap_col].astype(str) +
        "<br><b>SessionName - Info</b>: " + dfin[sessionname_col].astype(str) +
        "<br><b>Track</b>: " + dfin[trackname_col].astype(str)
    )

    # Acrescenta 25ET5/25ET6 somente se existirem e não forem NaN
    pieces = base.copy()
    if "25ET5" in dfin.columns:
        v = pd.to_numeric(dfin["25ET5"], errors='coerce')
        pieces = pieces + np.where(v.notna(), "<br><b>25ET5</b>: " + v.map(fmt).astype(str), "")
    if "25ET6" in dfin.columns:
        v = pd.to_numeric(dfin["25ET6"], errors='coerce')
        pieces = pieces + np.where(v.notna(), "<br><b>25ET6</b>: " + v.map(fmt).astype(str), "")
    return pieces.tolist()

# ---------------------------
# Sidebar – blocos (G7/G8 com comparação)
# ---------------------------
def sidebar_block(i: int, metrics_list, enable_compare=False):
    y = st.sidebar.selectbox(f"Métrica para Gráfico {i}:", metrics_list, key=f"g{i}::metric")
    st.sidebar.markdown("")
    if enable_compare:
        cmp_on = st.sidebar.checkbox(f"Modo comparação (G{i}) – 2 drivers", key=f"g{i}::cmp_on")
        if cmp_on:
            drivers = sorted(base[drivername_col].dropna().astype(str).unique())
            dA = st.sidebar.selectbox(f"Driver A (G{i}):", drivers, key=f"g{i}::drvA")
            mA = st.sidebar.radio(f"Sessões A (G{i}):", ["Todas","Apenas uma"], index=0, horizontal=True, key=f"g{i}::modeA")
            sA = None
            if mA == "Apenas uma":
                sessionsA = sorted(base[base[drivername_col].astype(str)==str(dA)][sessionname_col].dropna().astype(str).unique())
                if sessionsA:
                    sA = st.sidebar.selectbox(f"SessionName A (G{i}):", sessionsA, key=f"g{i}::sessA")
            dB = st.sidebar.selectbox(f"Driver B (G{i}):", drivers, key=f"g{i}::drvB")
            mB = st.sidebar.radio(f"Sessões B (G{i}):", ["Todas","Apenas uma"], index=0, horizontal=True, key=f"g{i}::modeB")
            sB = None
            if mB == "Apenas uma":
                sessionsB = sorted(base[base[drivername_col].astype(str)==str(dB)][sessionname_col].dropna().astype(str).unique())
                if sessionsB:
                    sB = st.sidebar.selectbox(f"SessionName B (G{i}):", sessionsB, key=f"g{i}::sessB")
            st.sidebar.markdown("---")
            return ("compare", y, dA, mA, sA, dB, mB, sB)
    enable = st.sidebar.checkbox(f"Filtrar por Driver (G{i})", key=f"g{i}::enable")
    drv = mode = ses = None
    if enable:
        drivers = sorted(base[drivername_col].dropna().astype(str).unique())
        drv = st.sidebar.selectbox(f"Driver (G{i}):", drivers, key=f"g{i}::driver")
        mode = st.sidebar.radio(f"Sessões (G{i}):", ["Todas","Apenas uma"], index=0, horizontal=True, key=f"g{i}::mode")
        if mode == "Apenas uma":
            sessions = sorted(base[base[drivername_col].astype(str)==str(drv)][sessionname_col].dropna().astype(str).unique())
            if sessions:
                ses = st.sidebar.selectbox(f"SessionName (G{i}):", sessions, key=f"g{i}::session")
    st.sidebar.markdown("---")
    return ("single", y, drv, (mode or "Todas"), ses)

cfgs = []
for i in range(1, 9):
    cfgs.append((i, sidebar_block(i, metricas, enable_compare=(i in (7, 8)))))

# ---------------------------
# Dispersão – controles
# ---------------------------
st.sidebar.header("Dispersão")
metricas_all = [c for c in df.select_dtypes(include='number').columns if c not in cols_excluir] or df.select_dtypes(include='number').columns.tolist()
x_disp = st.sidebar.selectbox("Métrica X:", metricas_all, key="disp::x")
y_disp = st.sidebar.selectbox("Métrica Y:", metricas_all, key="disp::y")
trend = st.sidebar.checkbox("Mostrar linha de tendência", key="disp::trend")

# ---------------------------
# Legenda à direita
# ---------------------------
legend_right = dict(
    orientation='v', yanchor='top', y=1,
    xanchor='left', x=1.02,
    bgcolor='rgba(0,0,0,0.3)',
    font=dict(size=13),
    title_text=None
)

# ---------------------------
# Plots (3×3)
# ---------------------------
figs = []

def draw_line(df_plot, y_col, color_col, legend_title):
    # ordem cronológica garantida
    df_plot = _order(df_plot)
    if y_col not in df_plot.columns or df_plot.empty:
        return None, df_plot

    x_vals  = df_plot['SessionLapDate'].tolist()
    x_texts = df_plot['XLabelShort'].tolist()
    tickvals, ticktext = sample_ticks(x_vals, x_texts, max_ticks=30)

    # cria a figura preservando a ordem categórica
    fig = px.line(
        df_plot, x='SessionLapDate', y=y_col,
        color=color_col, markers=True, title=y_col
    )
    # tooltip limpo sem "null"
    hovertext = build_hovertext(df_plot, y_col)
    fig.update_traces(hovertext=hovertext, hovertemplate="%{hovertext}<extra></extra>")

    fig.update_layout(
        title_font=dict(size=40, color="white"),
        height=600,
        legend=legend_right,
        legend_title_text=legend_title
    )
    fig.update_xaxes(
        type='category',
        categoryorder='array', categoryarray=x_vals,  # segue a ordem cronológica do DataFrame
        tickmode='array', tickvals=tickvals, ticktext=ticktext
    )
    return fig, df_plot

# 8 gráficos (7 e 8 com comparação)
for i, cfg in cfgs:
    mode = cfg[0]
    if mode == "single":
        _, y_i, d_i, m_i, s_i = cfg
        df_g = _apply_filters(base, d_i, m_i, s_i)
        fig, used = draw_line(df_g, y_i, sessionname_col, sessionname_col)
        figs.append((i, fig, used, y_i))
    else:
        _, y_i, dA, mA, sA, dB, mB, sB = cfg
        df_A = _apply_filters(base, dA, mA, sA)
        df_B = _apply_filters(base, dB, mB, sB)

        def add_group(dfin, label):
            if dfin.empty: return dfin
            d = dfin.copy()
            d["DriverSessionGroup"] = str(label) + " / " + d[sessionname_col].astype(str)
            return d

        df_cmp = pd.concat([add_group(df_A, dA), add_group(df_B, dB)], ignore_index=True)
        fig, used = draw_line(df_cmp, y_i, "DriverSessionGroup", "Driver / Session")
        figs.append((i, fig, used, y_i))

# Dispersão
if x_disp in df.columns and y_disp in df.columns:
    df_disp = df.copy()
    fig_disp = px.scatter(
        df_disp, x=x_disp, y=y_disp,
        color=sessionname_col if sessionname_col in df.columns else None,
        trendline="ols" if trend else None,
        title=f"{x_disp} vs {y_disp}"
    )
    hovertext = build_hovertext(df_disp, y_disp)
    fig_disp.update_traces(hovertext=hovertext, hovertemplate="%{hovertext}<extra></extra>")
    fig_disp.update_layout(title_font=dict(size=40, color="white"), height=600, legend=legend_right)
else:
    fig_disp = None

# Render 3×3
all_figs = figs + [(9, fig_disp, None, None)]
for row_start in range(0, 9, 3):
    cols = st.columns(3)
    for j in range(3):
        slot_idx = row_start + j
        grid_key = f"grid_{row_start}_{j}"
        fig_index, fig_obj, df_used, y_used = all_figs[slot_idx]
        with cols[j]:
            if fig_obj is not None:
                st.plotly_chart(fig_obj, use_container_width=True, key=f"plot_{grid_key}_{fig_index}")
                if df_used is not None and y_used is not None and y_used in df_used.columns:
                    vec = pd.to_numeric(df_used[y_used], errors='coerce')
                    c1, c2, c3 = st.columns(3)
                    with c1: st.metric("Mínimo", f"{vec.min():.2f}")
                    with c2: st.metric("Máximo", f"{vec.max():.2f}")
                    with c3: st.metric("Média",  f"{vec.mean():.2f}")
            else:
                st.info("Sem dados para este conjunto de filtros.", key=f"info_{grid_key}")
