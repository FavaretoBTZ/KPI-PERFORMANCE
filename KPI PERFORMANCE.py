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

# SessionLapDate (x original para manter ordem) + XLabelShort (texto a exibir)
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

# rótulo curto exibido no eixo X (sem SessionDate e sem Run)
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

# Métricas numéricas válidas
cols_excluir = [col_map[k] for k in required] + ['SessionLapDate', 'XLabelShort']
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

# --- helper para rótulos do eixo X (amostragem automática) ---
def sample_ticks(x_vals: list[str], x_texts: list[str], max_ticks: int = 30):
    """Seleciona até max_ticks rótulos uniformemente espaçados."""
    n = len(x_vals)
    if n <= max_ticks:
        return x_vals, x_texts
    step = max(1, n // max_ticks)
    idx = list(range(0, n, step))
    if idx[-1] != n - 1:
        idx.append(n - 1)
    return [x_vals[i] for i in idx], [x_texts[i] for i in idx]

# ---------------------------
# Sidebar – blocos dos 8 gráficos (G7/G8 com comparação)
# ---------------------------
def sidebar_block(i: int, metrics_list, enable_compare=False):
    """
    Retorna:
      - ('single', y, driver, sess_mode, session)
      - ('compare', y, dA, mA, sA, dB, mB, sB)
    """
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
# Dispersão – controles na sidebar
# ---------------------------
st.sidebar.header("Dispersão")
metricas_all = [c for c in df.select_dtypes(include='number').columns if c not in cols_excluir] or df.select_dtypes(include='number').columns.tolist()
x_disp = st.sidebar.selectbox("Métrica X:", metricas_all, key="disp::x")
y_disp = st.sidebar.selectbox("Métrica Y:", metricas_all, key="disp::y")
trend = st.sidebar.checkbox("Mostrar linha de tendência", key="disp::trend")

# ---------------------------
# Monta as 9 figuras e desenha em grid 3×3
# ---------------------------
figs = []

def line_hover_template(metric_title: str) -> str:
    return (
        f"<b>{metric_title}</b>: %{{y:.2f}}"
        "<br>Lap: %{{customdata[0]}}"
        "<br>Session: %{{customdata[1]}}"
        "<br>Track: %{{customdata[2]}}"
        "<extra></extra>"
    )

for i, cfg in cfgs:
    mode = cfg[0]

    if mode == "single":
        _, y_i, d_i, m_i, s_i = cfg
        df_g = _apply_filters(base, d_i, m_i, s_i)
        df_g = _order(df_g)

        if y_i in df_g.columns and not df_g.empty:
            # valores do eixo X (ordem cronológica original) + rótulos curtos
            x_vals  = df_g['SessionLapDate'].tolist()
            x_texts = df_g['XLabelShort'].tolist()
            tickvals_s, ticktext_s = sample_ticks(x_vals, x_texts, max_ticks=30)

            fig = px.line(
                df_g, x='SessionLapDate', y=y_i,          # mantém a ordem original
                color=sessionname_col,
                markers=True, title=y_i,
                hover_data=[lap_col, sessionname_col, trackname_col]
            )
            fig.update_traces(hovertemplate=line_hover_template(y_i))
            fig.update_layout(title_font=dict(size=40, color="white"),
                              height=600, legend_title_text=sessionname_col)
            # ordem e rótulos legíveis
            fig.update_xaxes(
                type='category',
                categoryorder='array', categoryarray=x_vals,
                tickmode='array', tickvals=tickvals_s, ticktext=ticktext_s
            )
        else:
            fig = None
        figs.append((i, fig, df_g, y_i))

    else:
        _, y_i, dA, mA, sA, dB, mB, sB = cfg
        df_A = _apply_filters(base, dA, mA, sA)
        df_B = _apply_filters(base, dB, mB, sB)

        def add_group(dfin, driver_label):
            if dfin.empty: return dfin
            dfin = dfin.copy()
            dfin["DriverSessionGroup"] = driver_label + " / " + dfin[sessionname_col].astype(str)
            return dfin

        df_A = add_group(_order(df_A), str(dA) if dA is not None else "A")
        df_B = add_group(_order(df_B), str(dB) if dB is not None else "B")
        df_cmp = pd.concat([df_A, df_B], ignore_index=True)

        if y_i in df_cmp.columns and not df_cmp.empty:
            x_vals  = df_cmp['SessionLapDate'].tolist()
            x_texts = df_cmp['XLabelShort'].tolist()
            tickvals_s, ticktext_s = sample_ticks(x_vals, x_texts, max_ticks=30)

            fig = px.line(
                df_cmp, x='SessionLapDate', y=y_i,
                color="DriverSessionGroup",
                markers=True, title=y_i,
                hover_data=[lap_col, sessionname_col, trackname_col]
            )
            fig.update_traces(hovertemplate=line_hover_template(y_i))
            fig.update_layout(title_font=dict(size=40, color="white"),
                              height=600, legend_title_text="Driver / Session")
            fig.update_xaxes(
                type='category',
                categoryorder='array', categoryarray=x_vals,
                tickmode='array', tickvals=tickvals_s, ticktext=ticktext_s
            )
        else:
            fig = None
        figs.append((i, fig, df_cmp, y_i))

# Dispersão (título = X vs Y) — hover reduzido
if x_disp in df.columns and y_disp in df.columns:
    fig_disp = px.scatter(
        df, x=x_disp, y=y_disp,
        color=sessionname_col if sessionname_col in df.columns else None,
        trendline="ols" if trend else None,
        hover_data=[lap_col, sessionname_col, trackname_col],
        title=f"{x_disp} vs {y_disp}"
    )
    fig_disp.update_traces(hovertemplate=
        "<b>X</b>: %{x}<br><b>Y</b>: %{y}"
        "<br>Lap: %{customdata[0]}"
        "<br>Session: %{customdata[1]}"
        "<br>Track: %{customdata[2]}"
        "<extra></extra>"
    )
    fig_disp.update_layout(title_font=dict(size=40, color="white"), height=600, legend_title_text=sessionname_col)
else:
    fig_disp = None

# Render em 3 linhas × 3 colunas — chave única por célula
all_figs = figs + [(9, fig_disp, None, None)]  # 9º = dispersão
for row_start in range(0, 9, 3):
    cols = st.columns(3)
    for j in range(3):
        slot_idx = row_start + j
        grid_key = f"grid_{row_start}_{j}"
        fig_index, fig_obj, df_used, y_used = all_figs[slot_idx]
        with cols[j]:
            if fig_obj is not None:
                st.plotly_chart(fig_obj, use_container_width=True, key=f"plot_{grid_key}_{fig_index}")
                if df_used is not None and y_used is not None:
                    c1, c2, c3 = st.columns(3)
                    with c1: st.metric("Mínimo", f"{pd.to_numeric(df_used[y_used], errors='coerce').min():.2f}")
                    with c2: st.metric("Máximo", f"{pd.to_numeric(df_used[y_used], errors='coerce').max():.2f}")
                    with c3: st.metric("Média",  f"{pd.to_numeric(df_used[y_used], errors='coerce').mean():.2f}")
            else:
                st.info("Sem dados para este conjunto de filtros.", key=f"info_{grid_key}")
