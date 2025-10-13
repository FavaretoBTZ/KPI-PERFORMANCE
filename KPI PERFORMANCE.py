import streamlit as st
import pandas as pd
import plotly.express as px
import unicodedata, re
from difflib import get_close_matches
import numpy as np

# =========================
# Config
# =========================
METRIC_BLACKLIST = {
    "DataSet - Slot",
    "ELB_TotalKm - Info",
}

# =========================
# Normalização de nomes
# =========================
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

def resolve_columns(df: pd.DataFrame, req):
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

def _find_col_exact(df: pd.DataFrame, label: str):
    return _norm_map(df).get(_normalize(label))

# =========================
# App
# =========================
st.set_page_config(layout="wide")
st.title("KPI PERFORMANCE - BTZ|Motorsport")

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

# =========================
# XKey (completo) + XLabel (curto)
# =========================
if pd.api.types.is_datetime64_any_dtype(df[sessiondate_col]):
    sdate = df[sessiondate_col].dt.strftime("%Y-%m-%d %H:%M:%S").astype(str)
else:
    s_try = pd.to_datetime(df[sessiondate_col], errors='coerce')
    sdate = s_try.dt.strftime("%Y-%m-%d %H:%M:%S").fillna(df[sessiondate_col].astype(str))

df["XKey"] = (
    sdate +
    " | Run " + df[run_col].astype(str) +
    " | Lap " + df[lap_col].astype(str) +
    " | " + df[sessionname_col].astype(str) +
    " | Track " + df[trackname_col].astype(str)
)
df["XLabel"] = (
    "Lap " + df[lap_col].astype(str) +
    " | " + df[sessionname_col].astype(str) +
    " | " + df[trackname_col].astype(str)
)

# =========================
# SIDEBAR: apenas filtros gerais
# =========================
st.sidebar.header("Filtros")
car_alias = st.sidebar.selectbox("Selecione o CarAlias:", sorted(df[col_map['caralias']].dropna().astype(str).unique()))
tracks = ["TODAS"] + sorted(pd.Series(df[trackname_col].dropna().astype(str).unique()).tolist())
selected_track = st.sidebar.selectbox("TrackName - Info:", tracks)

# Base por CarAlias e Track
base = df[df[col_map['caralias']].astype(str) == str(car_alias)]
if selected_track != "TODAS":
    base = base[base[trackname_col].astype(str) == str(selected_track)]

cols_excluir = [col_map[k] for k in required] + ['XKey', 'XLabel']

# métricas base (numéricas)
metricas = [c for c in df.select_dtypes(include='number').columns if c not in cols_excluir and c not in METRIC_BLACKLIST]

# ===== INCLUSÕES FORÇADAS (defaults pedidos) =====
forced_labels = [
    "LapTime - Info",
    "Tire - Info",
    "Full_Brake_intg -Max",
    "24_Brake_Balance -Avg",
    "Full_throttle_intg -Max",
    "G_Comb -Avg",
    "25_AcLat_Trigger -Avg",
    "25_AcLong_Trigger_Positivo -Avg",
    # extras usados em hover/conversões
    "SessionComment - Info",
]
for lbl in forced_labels:
    real = _find_col_exact(df, lbl)
    # Se não achar exatamente, ainda assim inclui o literal para não quebrar a UI
    use_lbl = real or lbl
    if use_lbl not in metricas and use_lbl not in METRIC_BLACKLIST:
        metricas.append(use_lbl)

# =========================
# Utils (ordenação, ticks)
# =========================
_num_pat = re.compile(r"[-+]?\d*[\.,]?\d+")

def _extract_num_series(series: pd.Series) -> pd.Series:
    def _one(x):
        m = _num_pat.search(str(x))
        if not m: return np.nan
        return float(m.group(0).replace(",", "."))
    return series.map(_one)

def _order(dfin: pd.DataFrame) -> pd.DataFrame:
    sdate_ord = pd.to_datetime(dfin[sessiondate_col], errors='coerce')
    run_ord   = _extract_num_series(dfin[run_col])
    lap_ord   = _extract_num_series(dfin[lap_col])
    sess_ord  = dfin[sessionname_col].astype(str)
    track_ord = dfin[trackname_col].astype(str)
    idx_orig  = np.arange(len(dfin))
    return dfin.assign(
        __sdate_ord=sdate_ord, __run_ord=run_ord, __lap_ord=lap_ord,
        __sess_ord=sess_ord, __track_ord=track_ord, __idx=idx_orig
    ).sort_values(
        by=["__sdate_ord","__run_ord","__lap_ord","__sess_ord","__track_ord","__idx"],
        kind="mergesort"
    )

def sample_ticks(x_vals, x_texts, max_ticks=30):
    n = len(x_vals)
    if n <= max_ticks: return x_vals, x_texts
    step = max(1, n // max_ticks)
    idx = list(range(0, n, step))
    if idx[-1] != n-1: idx.append(n-1)
    return [x_vals[i] for i in idx], [x_texts[i] for i in idx]

# =========================
# Conversão de métricas especiais
# =========================
def parse_laptime_to_seconds(x) -> float:
    if pd.isna(x): return np.nan
    s = str(x).strip().replace(",", ".")
    if not s or s.lower() in ["nan","none"]: return np.nan
    try:
        if ":" in s:
            mm, ss = s.split(":", 1)
            return float(mm)*60.0 + float(ss)
        return float(s)
    except Exception:
        m = re.search(r"[-+]?\d*\.?\d+", s)
        return float(m.group(0)) if m else np.nan

def materialize_metric_series(dfin: pd.DataFrame, y_col: str):
    # se o literal não existe na planilha, tenta resolver pelo mapa
    col = y_col if y_col in dfin.columns else _find_col_exact(dfin, y_col) or y_col
    y_norm = _normalize(col)
    laptime_norm  = _normalize("LapTime - Info")
    comment_norm  = _normalize("SessionComment - Info")
    tire_norm     = _normalize("Tire - Info")

    if col in dfin.columns and y_norm == laptime_norm:
        serie = dfin[col].map(parse_laptime_to_seconds)
        return serie, f"{y_col} (s)", {}

    if col in dfin.columns and y_norm == comment_norm:
        text = dfin[col].astype(str)
        has  = text.str.len().fillna(0) > 0
        serie = has.astype(int)
        return serie, "Comentário presente (1/0)", {"comment_text": text}

    if col in dfin.columns and y_norm == tire_norm:
        text = dfin[col].astype(str)
        cats = pd.Categorical(text)
        codes = pd.Series(cats.codes, index=dfin.index).replace(-1, np.nan) + 1
        mapping = {cat: i+1 for i, cat in enumerate(cats.categories)}
        return codes.astype(float), "Tire - Info", {"category_text": text, "category_map": mapping}

    # default
    if col in dfin.columns:
        return pd.to_numeric(dfin[col], errors='coerce'), y_col, {}
    # se ainda não existir, devolve NaN p/ não quebrar
    return pd.Series([np.nan]*len(dfin), index=dfin.index), y_col, {}

legend_right = dict(orientation='v', yanchor='top', y=1, xanchor='left', x=1.02,
                    bgcolor='rgba(0,0,0,0.3)', font=dict(size=13), title_text=None)

def hover_template_for(metric_title: str, has_comment: bool, has_category: bool) -> str:
    parts = [
        f"<b>{metric_title}</b>: %{{y:.3f}}",
        "<br><b>Lap - Info</b>: %{customdata[0]}",
        "<br><b>SessionName - Info</b>: %{customdata[1]}",
        "<br><b>Track</b>: %{customdata[2]}",
        "<br><b>X</b>: %{customdata[3]}",
    ]
    idx = 4
    if has_comment:
        parts.append(f"<br><b>SessionComment - Info</b>: %{{customdata[{idx}]}}")
        idx += 1
    if has_category:
        parts.append(f"<br><b>Tire - Info</b>: %{{customdata[{idx}]}}")
    return "".join(parts) + "<extra></extra>"

def draw_line(df_plot, y_col, color_col, legend_title):
    df_plot = _order(df_plot)
    y_series, y_title, extra = materialize_metric_series(df_plot, y_col)
    df_plot = df_plot.copy()
    df_plot["__y__"] = y_series

    x_vals  = df_plot['XKey'].tolist()
    x_texts = df_plot['XLabel'].tolist()
    tickvals, ticktext = sample_ticks(x_vals, x_texts, max_ticks=30)

    custom_cols = [lap_col, sessionname_col, trackname_col, 'XLabel']
    has_comment  = "comment_text"  in extra
    has_category = "category_text" in extra
    if has_comment:
        df_plot["__comment__"] = extra["comment_text"]
        custom_cols.append("__comment__")
    if has_category:
        df_plot["__category__"] = extra["category_text"]
        custom_cols.append("__category__")

    fig = px.line(df_plot, x='XKey', y="__y__", color=color_col, markers=True,
                  title=y_title, custom_data=custom_cols)

    fig.update_traces(hovertemplate=hover_template_for(y_title, has_comment, has_category))
    fig.update_layout(title_font=dict(size=40, color="white"), height=600,
                      legend=legend_right, legend_title_text=legend_title)
    fig.update_xaxes(type='category', categoryorder='array', categoryarray=x_vals,
                     tickmode='array', tickvals=tickvals, ticktext=ticktext, title=None)

    if has_category and "category_map" in extra:
        name_to_code = extra["category_map"]
        fig.update_yaxes(tickmode="array",
                         tickvals=list(name_to_code.values()),
                         ticktext=list(name_to_code.keys()))
    return fig, df_plot

# =========================
# Dispersão: lista de métricas
# =========================
metricas_all = [c for c in df.select_dtypes(include='number').columns if c not in METRIC_BLACKLIST]
for special in set(forced_labels):
    use_lbl = _find_col_exact(df, special) or special
    if use_lbl not in metricas_all and use_lbl not in METRIC_BLACKLIST:
        metricas_all.append(use_lbl)

# =========================
# Defaults iniciais (os originais que você definiu)
# =========================
def _reset_initial_defaults():
    sig = (tuple(sorted(df.columns)), int(df.shape[0]))
    if st.session_state.get("_data_sig") == sig:
        return
    st.session_state["_data_sig"] = sig

    desired = {
        1: "LapTime - Info",
        2: "Tire - Info",
        3: "Full_Brake_intg -Max",
        4: "24_Brake_Balance -Avg",
        5: "Full_throttle_intg -Max",
        6: "G_Comb -Avg",
        7: "25_AcLat_Trigger -Avg",
        8: "25_AcLong_Trigger_Positivo -Avg",
    }
    for i, label in desired.items():
        real = _find_col_exact(df, label) or label
        if real not in metricas and real not in METRIC_BLACKLIST:
            metricas.append(real)
        st.session_state[f"g{i}::metric"] = real

    x_default = _find_col_exact(df, "G_Comb -Avg") or "G_Comb -Avg"
    y_default = _find_col_exact(df, "LapTime - Info") or "LapTime - Info"
    if x_default not in metricas_all and x_default not in METRIC_BLACKLIST:
        metricas_all.append(x_default)
    if y_default not in metricas_all and y_default not in METRIC_BLACKLIST:
        metricas_all.append(y_default)
    st.session_state["disp::x"] = x_default
    st.session_state["disp::y"] = y_default
    st.session_state["disp::trend"] = False

_reset_initial_defaults()

# =========================
# UI/plots (3×3) — select acima de cada gráfico
# =========================
def graph_card(i: int, base_df: pd.DataFrame):
    y_i = st.selectbox(
        f"Selecione a métrica (Y Axis) (G{i}):",
        metricas, key=f"g{i}::metric"
    )

    cmp_cfg = None
    if i in (7, 8):
        with st.expander("Comparar dois drivers (opcional)", expanded=False):
            cmp_on = st.checkbox("Ativar comparação", key=f"g{i}::cmp_on")
            if cmp_on:
                drivers = sorted(base_df[drivername_col].dropna().astype(str).unique())
                dA = st.selectbox("Driver A:", drivers, key=f"g{i}::drvA")
                dB = st.selectbox("Driver B:", drivers, key=f"g{i}::drvB")
                mA = st.radio("Sessões A:", ["Todas","Apenas uma"], index=0, horizontal=True, key=f"g{i}::modeA")
                sA = None
                if mA == "Apenas uma":
                    sessionsA = sorted(base_df[base_df[drivername_col].astype(str)==str(dA)][sessionname_col].dropna().astype(str).unique())
                    if sessionsA: sA = st.selectbox("SessionName A:", sessionsA, key=f"g{i}::sessA")
                mB = st.radio("Sessões B:", ["Todas","Apenas uma"], index=0, horizontal=True, key=f"g{i}::modeB")
                sB = None
                if mB == "Apenas uma":
                    sessionsB = sorted(base_df[base_df[drivername_col].astype(str)==str(dB)][sessionname_col].dropna().astype(str).unique())
                    if sessionsB: sB = st.selectbox("SessionName B:", sessionsB, key=f"g{i}::sessB")
                cmp_cfg = (dA, mA, sA, dB, mB, sB)

    def _apply_filters(dfin, driver=None, mode="Todas", session=None):
        if dfin is None or dfin.empty:
            return dfin
        dfout = dfin.copy()
        if driver:
            dfout = dfout[dfout[drivername_col].astype(str) == str(driver)]
        if mode == "Apenas uma" and session:
            dfout = dfout[dfout[sessionname_col].astype(str) == str(session)]
        return dfout

    if cmp_cfg is None:
        df_g = base_df.copy()
        fig, used = draw_line(df_g, y_i, sessionname_col, sessionname_col)
        return fig, used, y_i
    else:
        dA, mA, sA, dB, mB, sB = cmp_cfg
        df_A = _apply_filters(base_df.copy(), dA, mA, sA) if dA else base_df.iloc[0:0].copy()
        df_B = _apply_filters(base_df.copy(), dB, mB, sB) if dB else base_df.iloc[0:0].copy()
        def add_group(dfin, label):
            if dfin.empty: return dfin
            d = dfin.copy()
            d["DriverSessionGroup"] = str(label) + " / " + d[sessionname_col].astype(str)
            return d
        df_cmp = pd.concat([add_group(df_A, dA or ""), add_group(df_B, dB or "")], ignore_index=True)
        fig, used = draw_line(df_cmp, y_i, "DriverSessionGroup", "Driver / Session")
        return fig, used, y_i

def hover_and_stats(fig_obj, df_used, y_used):
    if df_used is not None and y_used is not None:
        ys, _, _ = materialize_metric_series(df_used, y_used)
        vec = pd.to_numeric(ys, errors='coerce')
        c1, c2, c3 = st.columns(3)
        with c1: st.metric("Mínimo", f"{vec.min():.3f}" if vec.notna().any() else "—")
        with c2: st.metric("Máximo", f"{vec.max():.3f}" if vec.notna().any() else "—")
        with c3: st.metric("Média",  f"{vec.mean():.3f}" if vec.notna().any() else "—")

figs = []
plot_counter = 0
for row_start in range(0, 9, 3):
    cols = st.columns(3)
    for j in range(3):
        slot_idx = row_start + j + 1  # 1..9
        if slot_idx <= 8:
            with cols[j]:
                fig_obj, df_used, y_used = graph_card(slot_idx, base)
                st.plotly_chart(fig_obj, use_container_width=True,
                                key=f"plot_{slot_idx}_{row_start}_{j}_{plot_counter}")
                hover_and_stats(fig_obj, df_used, y_used)
                plot_counter += 1
        elif slot_idx == 9:
            with cols[j]:
                st.subheader("Dispersão (G9)")
                x_default = st.session_state.get("disp::x", "G_Comb -Avg")
                y_default = st.session_state.get("disp::y", "LapTime - Info")
                x_disp = st.selectbox("Métrica X:", metricas_all, key="disp::x",
                                      index=metricas_all.index(x_default) if x_default in metricas_all else 0)
                y_disp = st.selectbox("Métrica Y:", metricas_all, key="disp::y",
                                      index=metricas_all.index(y_default) if y_default in metricas_all else 0)
                trend = st.checkbox("Mostrar linha de tendência", key="disp::trend", value=bool(st.session_state.get("disp::trend", False)))

                x_ok = (x_disp in df.columns) or (_find_col_exact(df, x_disp) is not None)
                y_ok = (y_disp in df.columns) or (_find_col_exact(df, y_disp) is not None)
                if x_ok and y_ok:
                    x_col = x_disp if x_disp in df.columns else _find_col_exact(df, x_disp)
                    y_col = y_disp if y_disp in df.columns else _find_col_exact(df, y_disp)
                    df_disp = df.copy()
                    y_series, y_title, _ = materialize_metric_series(df_disp, y_col)
                    df_disp["__y__"] = y_series
                    fig_disp = px.scatter(
                        df_disp, x=x_col, y="__y__",
                        color=sessionname_col if sessionname_col in df.columns else None,
                        trendline="ols" if trend else None,
                        title=f"{x_disp} vs {y_title}"
                    )
                    fig_disp.update_layout(title_font=dict(size=40, color="white"), height=600, legend=legend_right)
                    st.plotly_chart(fig_disp, use_container_width=True, key="plot_disp")
                else:
                    st.info("Selecione X e Y válidos para a dispersão.")

# =====================================================================
# PLANILHAS NO APP (volta mais rápida por sessão) — permanece igual
# =====================================================================
st.markdown("---")
st.header("Planilhas por TrackName - Info (volta mais rápida por sessão)")

all_tracks = sorted(df[trackname_col].dropna().astype(str).unique().tolist())
track_sel = st.selectbox("TrackName - Info (planilhas):", all_tracks, index=0, key="export::track")

wanted_labels = [
    "SessionName - Info", "LapTime - Info", "Tire - Info", "TrackName - Info",
    "AccX -Min", "AccX -Max", "AccX -Avg",
    "AccY -Min", "AccY -Max", "AccY -Avg",
    "G_Comb -Max", "G_Comb -Avg",
    "25_AcLat_Trigger -Avg",
    "25_AcLong_Trigger_Positivo -Avg",
    "25_AcLong_Trigger_Negativo -Avg",
    "CarSpeed -Avg","Total_Brake -Max","Total_Brake -Avg",
    "BrakeAgression -Max","BrakeAgression -Avg","Full_Brake_intg -Max",
    "rPedal -Avg","24_ThrottleAgression -Max","24_ThrottleAgression -Avg",
    "Full_throttle_intg -Max","25_CrossingTime -Avg","25_CoastingTime -Avg",
]

def _find_col_exact_local(df_in: pd.DataFrame, label: str):
    norm = _normalize(label)
    mapping = { _normalize(c): c for c in df_in.columns }
    if norm in mapping: return mapping[norm]
    if "laptime - info" in norm or "laptim - info" in norm:
        for k in mapping:
            if "laptime - info" in k or "laptim - info" in k:
                return mapping[k]
    return None

col_map_export = { lbl: _find_col_exact_local(df, lbl) for lbl in wanted_labels }

df_track = df[df[trackname_col].astype(str) == str(track_sel)].copy()
drivers_in_track = sorted(df_track[drivername_col].dropna().astype(str).unique().tolist())

def fastest_per_session(df_in: pd.DataFrame) -> pd.DataFrame:
    if df_in.empty: return pd.DataFrame(columns=wanted_labels)
    sess_col_real = _find_col_exact_local(df_in, "SessionName - Info") or sessionname_col
    lap_time_real = _find_col_exact_local(df_in, "LapTime - Info")
    if sess_col_real not in df_in.columns or lap_time_real is None:
        return pd.DataFrame(columns=wanted_labels)

    tmp = _order(df_in.copy())
    tmp["__ltime_sec__"] = tmp[lap_time_real].map(parse_laptime_to_seconds)

    sess_seq = pd.unique(tmp[sess_col_real].astype(str))
    sess_order = {s: i for i, s in enumerate(sess_seq)}

    grp = tmp.dropna(subset=["__ltime_sec__"]).groupby(sess_col_real, sort=False)
    if grp.ngroups == 0: return pd.DataFrame(columns=wanted_labels)
    best_idx = grp["__ltime_sec__"].idxmin()
    best = tmp.loc[best_idx].copy()
    best["__sess_order__"] = best[sess_col_real].astype(str).map(sess_order)

    best = best.sort_values(by=["__sess_order__", "__sdate_ord", "__run_ord", "__lap_ord"], kind="mergesort")

    out_cols = []
    for lbl in wanted_labels:
        src = col_map_export.get(lbl)
        if src is not None and src in best.columns:
            s = best[src]; s.name = lbl
            out_cols.append(s)
        else:
            out_cols.append(pd.Series([np.nan]*len(best), index=best.index, name=lbl))
    return pd.concat(out_cols, axis=1).reset_index(drop=True)

if not drivers_in_track:
    st.info("Não há dados para o Track selecionado.")
else:
    st.caption(f"Track selecionado: **{track_sel}** — {len(drivers_in_track)} piloto(s)")
    for drv in drivers_in_track:
        df_drv = df_track[df_track[drivername_col].astype(str) == drv].copy()
        sheet = fastest_per_session(df_drv)
        st.subheader(f"{drv} — {track_sel}")
        if sheet.empty:
            st.info("Sem dados válidos de LapTime para compor a planilha.")
        else:
            st.dataframe(sheet, use_container_width=True)
