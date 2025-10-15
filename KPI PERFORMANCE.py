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
    s = s.replace("%", " percent")
    s = re.sub(r"[^\w\s]", " ", s)           # pontos, hífens, barras -> espaço
    s = re.sub(r"[_\-/]+"," ", s)
    s = re.sub(r"\s+"," ", s)
    return s

def _strip_metric_suffixes(n: str) -> str:
    toks = n.split()
    while toks and toks[-1] in _SUFFIXES_TO_STRIP:
        toks.pop()
    return " ".join(toks)

def _strip_leading_numbers(nbase: str) -> str:
    # remove prefixos tipo "24 " ou "25 "
    return re.sub(r"^\d+\s+", "", nbase).strip()

def _norm_map(df: pd.DataFrame):
    """
    Mapa robusto:
      - chave: normalizado completo
      - chave: base (sem sufixo)
      - chave: base sem prefixos numéricos
    """
    m = {}
    for c in df.columns:
        nfull = _normalize(c)
        nbase = _strip_metric_suffixes(nfull)
        nbase_wo_num = _strip_leading_numbers(nbase)
        for key in filter(None, [nfull, nbase, nbase_wo_num]):
            if key not in m:
                m[key] = c
    return m

def resolve_columns(df: pd.DataFrame, req):
    m = _norm_map(df); keys_av = list(m.keys())
    aliases = {
        "caralias":["caralias","car alias","car","carro","vehicle","car id","car number","carno","n carro"],
        "sessiondate":["sessiondate","session date","date","data","session day","dia","data sessao","timestamp","time","data e hora"],
        "run":["run","stint","stint id","stint no","stint number","corrida","bateria","run number"],
        "trackname":["trackname","track name","track","circuit","circuito","etapa"],
        "drivername":["drivername","driver","piloto","nome piloto","driver name"],
        "sessionname":["sessionname","session","nome sessao","tipo sessao","session type","practice","qualifying","race","warmup"],
        "lap":["lap","lapnumber","lap number","lap no","n volta","volta","lapcount","lap idx","lap index"],
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

# ===== Resolver de métricas por base + sufixo =====
_SUFFIX_EQUIV = {
    "info": ["info"],
    "min": ["min"],
    "max": ["max"],
    "avg": ["avg","mean","median"],
    "std": ["std"],
    "ref": ["ref","reference","target"],
    "target": ["target","ref","reference"],
}

# sinônimos para nomes-base (inclui AccX/AccY ↔ Ac.Lat/Ac.Long)
_BASE_SYNONYMS = {
    # existentes
    "tire": ["tyre", "pneu", "tires", "tyres"],
    "tyre": ["tire", "pneu", "tires", "tyres"],
    "pneu": ["tire", "tyre", "tires", "tyres"],

    # novos: aceleração lateral/longitudinal
    "accx":   ["ac lat", "aclat", "acc x", "ac x"],
    "ac lat": ["accx", "aclat", "acc x", "ac x"],

    "accy":    ["ac long", "aclong", "acc y", "ac y"],
    "ac long": ["accy", "aclong", "acc y", "ac y"],
}

def _expand_base_aliases(base: str):
    base = base.strip().lower()
    alts = _BASE_SYNONYMS.get(base, [])
    return [base] + [a for a in alts if a != base]

def _split_target_label(label: str):
    """
    "25_AcLat_Trigger -Avg" -> (base_normalizada_sem_numero, sufixo_normalizado)
    """
    n = _normalize(label)
    toks = n.split()
    suf = None
    if toks and toks[-1] in _SUFFIXES_TO_STRIP:
        suf = toks[-1]; base = " ".join(toks[:-1])
    else:
        m = re.search(r"(.*?)[\s\-_/]+(info|min|max|avg|mean|median|std|ref|target)$", n)
        if m: base, suf = m.group(1), m.group(2)
        else: base, suf = n, None
    base_wo_num = _strip_leading_numbers(_strip_metric_suffixes(base))
    return base_wo_num.strip(), (suf or "").strip()

def _suffix_candidates(suf: str):
    suf = (suf or "").strip().lower()
    if suf in _SUFFIX_EQUIV:
        return _SUFFIX_EQUIV[suf] + [suf]
    return list(_SUFFIX_EQUIV.keys())

def find_metric(df: pd.DataFrame, target_label: str):
    """
    Exato -> base (c/ sinônimos) + sufixo -> fuzzy -> substring -> norm_map base
    """
    cols = list(df.columns)
    norm_to_orig = _norm_map(df)

    n_exact = _normalize(target_label)
    if n_exact in norm_to_orig:
        return norm_to_orig[n_exact]

    base_need, suf_need = _split_target_label(target_label)
    suf_opts = _suffix_candidates(suf_need)

    bucket = {}
    for c in cols:
        nfull = _normalize(c)
        nbase = _strip_metric_suffixes(nfull)
        nbase_wo_num = _strip_leading_numbers(nbase)
        toks = nfull.split()
        csuf = toks[-1] if toks and toks[-1] in _SUFFIXES_TO_STRIP else ""
        bucket.setdefault(nbase_wo_num, {}).setdefault(csuf, []).append(c)

    bases_to_try = _expand_base_aliases(base_need)
    for b_try in bases_to_try:
        if b_try in bucket:
            for s in suf_opts:
                if s in bucket[b_try]:
                    return bucket[b_try][s][0]
            for pref in ["avg","max","min","info","mean","median","std","ref","target",""]:
                if pref in bucket[b_try]:
                    return bucket[b_try][pref][0]
            for _, lst in bucket[b_try].items():
                if lst: return lst[0]

    bases_av = list(bucket.keys())
    for b_alias in bases_to_try:
        hits = get_close_matches(b_alias, bases_av, n=1, cutoff=0.8)
        if hits:
            b = hits[0]
            for s in suf_opts:
                if s in bucket[b]:
                    return bucket[b][s][0]
            for _, lst in bucket[b].items():
                if lst: return lst[0]

    for c in cols:
        if base_need and base_need in _strip_leading_numbers(_strip_metric_suffixes(_normalize(c))):
            return c

    if base_need in norm_to_orig:
        return norm_to_orig[base_need]

    return None

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
# Sidebar
# =========================
st.sidebar.header("Filtros")
car_alias = st.sidebar.selectbox("Selecione o CarAlias:", sorted(df[col_map['caralias']].dropna().astype(str).unique()))
tracks = ["TODAS"] + sorted(pd.Series(df[trackname_col].dropna().astype(str).unique()).tolist())
selected_track = st.sidebar.selectbox("TrackName - Info:", tracks)

base = df[df[col_map['caralias']].astype(str) == str(car_alias)]
if selected_track != "TODAS":
    base = base[base[trackname_col].astype(str) == str(selected_track)]

cols_excluir = [col_map[k] for k in required] + ['XKey', 'XLabel']

# =========================
# Helpers de ordem conforme Excel
# =========================
def _unique_preserve(seq):
    seen = set(); out = []
    for x in seq:
        if x is None: continue
        if x not in seen:
            seen.add(x); out.append(x)
    return out

def _insert_by_excel_order(df_in: pd.DataFrame, ordered_list, col_to_add):
    if col_to_add in ordered_list: return ordered_list
    if col_to_add not in df_in.columns:
        ordered_list.append(col_to_add)
        return ordered_list
    idx_target = df_in.columns.get_loc(col_to_add)
    for k, c in enumerate(ordered_list):
        if c in df_in.columns and df_in.columns.get_loc(c) > idx_target:
            ordered_list.insert(k, col_to_add)
            break
    else:
        ordered_list.append(col_to_add)
    return ordered_list

# =========================
# Métricas (ordem do Excel)
# =========================
_numeric_set = set(df.select_dtypes(include='number').columns)

metricas = []
for c in df.columns:
    if c in _numeric_set and c not in METRIC_BLACKLIST and c not in [col_map[k] for k in required] and c not in ("XKey","XLabel"):
        metricas.append(c)

forced_labels = [
    "LapTime - Info",
    "Tire - Info",
    "Full_Brake_intg -Max",
    "24_Brake_Balance -Avg",
    "Full_throttle_intg -Max",
    "G_Comb -Avg",
    "25_AcLat_Trigger -Avg",
    "25_AcLong_Trigger_Positivo -Avg",
    "SessionComment - Info",
]
for lbl in forced_labels:
    real = find_metric(df, lbl) or lbl
    if real not in METRIC_BLACKLIST:
        metricas = _insert_by_excel_order(df, metricas, real)
metricas = _unique_preserve(metricas)

metricas_all = []
for c in df.columns:
    if c not in METRIC_BLACKLIST:
        metricas_all.append(c)
for special in set(forced_labels):
    real = find_metric(df, special) or special
    if real not in METRIC_BLACKLIST:
        metricas_all = _insert_by_excel_order(df, metricas_all, real)
metricas_all = _unique_preserve(metricas_all)

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
    s = re.sub(r"\s+", "", s)
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
    real = y_col if y_col in dfin.columns else find_metric(dfin, y_col)
    col = real or y_col
    y_norm = _normalize(col)
    laptime_norm  = _normalize(find_metric(dfin, "LapTime - Info") or "LapTime - Info")
    comment_norm  = _normalize(find_metric(dfin, "SessionComment - Info") or "SessionComment - Info")
    tire_norm     = _normalize(find_metric(dfin, "Tire - Info") or "Tire - Info")

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

    if col in dfin.columns and pd.api.types.is_numeric_dtype(dfin[col]):
        return pd.to_numeric(dfin[col], errors='coerce'), y_col, {}

    if col in dfin.columns and not pd.api.types.is_numeric_dtype(dfin[col]):
        text = dfin[col].astype(str)
        cats = pd.Categorical(text)
        codes = pd.Series(cats.codes, index=dfin.index).replace(-1, np.nan) + 1
        mapping = {cat: i+1 for i, cat in enumerate(cats.categories)}
        return codes.astype(float), y_col, {"category_text": text, "category_map": mapping}

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
    if has_category:
        parts.append(f"<br><b>Tire - Info</b>: %{{customdata[{idx + (1 if has_comment else 0)}]}}")
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
    if "comment_text" in extra:
        df_plot["__comment__"] = extra["comment_text"]; custom_cols.append("__comment__")
    if "category_text" in extra:
        df_plot["__category__"] = extra["category_text"]; custom_cols.append("__category__")

    fig = px.line(df_plot, x='XKey', y="__y__", color=color_col, markers=True,
                  title=y_title, custom_data=custom_cols)

    fig.update_traces(hovertemplate=hover_template_for(
        y_title, "comment_text" in extra, "category_text" in extra
    ))
    fig.update_layout(title_font=dict(size=40, color="white"), height=600,
                      legend=legend_right, legend_title_text=legend_title)
    fig.update_xaxes(type='category', categoryorder='array', categoryarray=list(dict.fromkeys(x_vals)),
                     tickmode='array', tickvals=tickvals, ticktext=ticktext, title=None)

    if "category_map" in extra:
        name_to_code = extra["category_map"]
        fig.update_yaxes(tickmode="array",
                         tickvals=list(name_to_code.values()),
                         ticktext=list(name_to_code.keys()))
    return fig, df_plot

# =========================
# Defaults iniciais (sem escopo global)
# =========================
def _reset_initial_defaults(metricas_in, metricas_all_in, df_in: pd.DataFrame):
    """
    Define/repõe os defaults respeitando a ordem do Excel e evita UnboundLocalError.
    Retorna (metricas_out, metricas_all_out).
    """
    sig = (tuple(sorted(df_in.columns)), int(df_in.shape[0]))
    if st.session_state.get("_data_sig") == sig:
        return metricas_in, metricas_all_in

    st.session_state["_data_sig"] = sig

    metricas_out = list(metricas_in)
    metricas_all_out = list(metricas_all_in)

    desired = {
        1: "LapTime - Info",
        2: "Tire - Info",
        3: "Full_Brake_intg -Max",
        4: "24_Brake_Balance -Avg",
        5: "Full_throttle_intg -Max",
        6: "G_Comb -Avg",
        7: "25_AcLat_Trigger -Avg",
       
