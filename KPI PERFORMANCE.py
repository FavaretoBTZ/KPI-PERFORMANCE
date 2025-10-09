import streamlit as st
import pandas as pd
import plotly.express as px
import unicodedata, re
from difflib import get_close_matches

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
        "sessiondate":["sessiondate","session date","date","data","session day","dia","data sessao"],
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
        # direto
        for c in cands:
            if c in m: found = m[c]; break
        # prefixo/contém
        if not found:
            for c in cands:
                hits = [k for k in keys_av if k.startswith(c+" ")]
                if hits: found = m[hits[0]]; break
            if not found:
                for c in cands:
                    hits = [k for k in keys_av if f" {c} " in f" {k} "]
                    if hits: found = m[hits[0]]; break
        # fuzzy
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

# SessionLapDate
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

# ---------------------------
# Sidebar - Filtros gerais
# ---------------------------
st.sidebar.header("Filtros Line Plot")
car_alias = st.sidebar.selectbox("CarAlias:", sorted(df[col_map['caralias']].dropna().astype(str).unique()))
tracks = ["TODAS"] + sorted(pd.Series(df[trackname_col].dropna().astype(str).unique()).tolist())
selected_track = st.sidebar.selectbox("Etapa (TrackName):", tracks)

# Métricas numéricas válidas
cols_excluir = [col_map[k] for k in required] + ['SessionLapDate']
metricas = [c for c in df.select_dtypes(include='number').columns if c not in cols_excluir]
if not metricas:
    metricas = df.select_dtypes(include='number').columns.tolist()

# Base comum
base = df[df[col_map['caralias']].astype(str) == str(car_alias)]
if selected_track != "TODAS":
    base = base[base[trackname_col].astype(str) == str(selected_track)]

# Utils
def _safe_num(s): return pd.to_numeric(s, errors='coerce')
def _order(dfin: pd.DataFrame) -> pd.DataFrame:
    sdate_ord = pd.to_datetime(dfin[sessiondate_col], errors='coerce')
    return dfin.assign(
        __sdate_ord=sdate_ord,
        __run_ord=_safe_num(dfin[run_col]),
        __lap_ord=_safe_num(dfin[lap_col]),
    ).sort_values(by=["__sdate_ord","__run_ord","__lap_ord"], kind="mergesort")

def _apply_filters(df_in, driver_sel, mode_sel, session_sel):
    out = df_in
    if driver_sel:
        out = out[out[drivername_col].astype(str) == str(driver_sel)]
        if mode_sel == "Apenas uma" and session_sel:
            out = out[out[sessionname_col].astype(str) == str(session_sel)]
    return out

# ---------------------------
# Sidebar – blocos dos 8 gráficos
# (cada um tem métrica + filtros logo abaixo)
# ---------------------------
def sidebar_block(i: int, metrics_list):
    """Cria os widgets de um gráfico i e devolve (y, driver, mode, session)."""
    y = st.sidebar.selectbox(f"Métrica para Gráfico {i}:", metrics_list, key=f"g{i}::metric")
    st.sidebar.markdown("")  # respiro
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
    return y, drv, (mode or "Todas"), ses

# cria 8 configs
cfgs = [sidebar_block(i, metricas) for i in range(1, 9)]

# ---------------------------
# Render dos 8 gráficos
# ---------------------------
for i, (y_i, d_i, m_i, s_i) in enumerate(cfgs, start=1):
    with st.container():
        df_g = _apply_filters(base, d_i, m_i, s_i)
        df_g = _order(df_g)
        st.subheader(f"Gráfico {i}")
        if y_i in df_g.columns and not df_g.empty:
            fig = px.line(df_g, x='SessionLapDate', y=y_i, color=trackname_col, markers=True, title=f"Gráfico {i}")
            fig.update_layout(title_font=dict(size=40, color="white"), height=600, legend_title_text=trackname_col)
            fig.update_xaxes(type='category', categoryorder='array', categoryarray=df_g['SessionLapDate'].tolist())
            st.plotly_chart(fig, use_container_width=True)
            c1,c2,c3 = st.columns(3)
            with c1: st.metric("Mínimo", f"{pd.to_numeric(df_g[y_i], errors='coerce').min():.2f}")
            with c2: st.metric("Máximo", f"{pd.to_numeric(df_g[y_i], errors='coerce').max():.2f}")
            with c3: st.metric("Média",  f"{pd.to_numeric(df_g[y_i], errors='coerce').mean():.2f}")
        else:
            st.warning(f"⚠️ Gráfico {i} sem dados/métrica para os filtros selecionados.")

# ---------------------------
# Dispersão (mantido)
# ---------------------------
st.sidebar.header("Dispersão")
metricas_all = [c for c in df.select_dtypes(include='number').columns if c not in cols_excluir] or df.select_dtypes(include='number').columns.tolist()
x = st.sidebar.selectbox("Métrica X:", metricas_all, key="disp::x")
y = st.sidebar.selectbox("Métrica Y:", metricas_all, key="disp::y")
trend = st.sidebar.checkbox("Mostrar linha de tendência", key="disp::trend")

if x in df.columns and y in df.columns:
    fig3 = px.scatter(df, x=x, y=y, color=trackname_col if trackname_col in df.columns else None,
                      trendline="ols" if trend else None,
                      hover_data=[sessionname_col if sessionname_col in df.columns else None,
                                  lap_col if lap_col in df.columns else None,
                                  run_col if run_col in df.columns else None],
                      title="Dispersão")
    fig3.update_layout(title_font=dict(size=40, color="white"), height=600)
    st.plotly_chart(fig3, use_container_width=True)
else:
    st.info("Selecione métricas numéricas válidas para X e Y na seção Dispersão.")
