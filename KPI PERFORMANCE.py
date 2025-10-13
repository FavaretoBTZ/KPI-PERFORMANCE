import streamlit as st
import pandas as pd
import plotly.express as px
import unicodedata, re, os
from difflib import get_close_matches
import numpy as np

# =========================
# Config
# =========================
METRIC_BLACKLIST = {"DataSet - Slot"}  # remover essa métrica das seleções

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

# =========================
# App
# =========================
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

# =========================
# Conversão de métricas especiais
# =========================
def parse_laptime_to_seconds(x) -> float:
    if pd.isna(x): return np.nan
    s = str(x).strip().replace(",", ".")
    if not s or s.lower() in ["nan", "none"]: return np.nan
    try:
        if ":" in s:
            mm, ss = s.split(":", 1)
            return float(mm) * 60.0 + float(ss)
        return float(s)
    except Exception:
        m = re.search(r"[-+]?\d*\.?\d+", s)
        return float(m.group(0)) if m else np.nan

# =====================================================================
# PLANILHAS NO APP: 1 linha por sessão (volta mais rápida) para cada piloto
# =====================================================================
st.markdown("---")
st.header("Planilhas por TrackName - Info (volta mais rápida por sessão)")

all_tracks = sorted(df[trackname_col].dropna().astype(str).unique().tolist())
track_sel = st.selectbox("TrackName - Info:", all_tracks, index=0, key="export::track")

# Rótulos desejados
wanted_labels = [
    "SessionName - Info", "LapTime - Info", "Tire - Info", "TrackName - Info",
    "AccX -Min", "AccX -Max", "AccX -Avg",
    "AccY -Min", "AccY -Max", "AccY -Avg",
    "G_Comb -Max", "G_Comb -Avg",
    "25_AcLat_Trigger -Avg",
    "25_AcLong_Trigger_Positivo -Avg",
    "25_AcLong_Trigger_Negativo -Avg",
]

def _find_col_exact_local(df_in: pd.DataFrame, label: str):
    norm = _normalize(label)
    mapping = { _normalize(c): c for c in df_in.columns }
    if norm in mapping:
        return mapping[norm]
    if "laptime - info" in norm or "laptim - info" in norm:
        for k in mapping:
            if "laptime - info" in k or "laptim - info" in k:
                return mapping[k]
    return None

col_map_export = { lbl: _find_col_exact_local(df, lbl) for lbl in wanted_labels }

df_track = df[df[trackname_col].astype(str) == str(track_sel)].copy()
drivers_in_track = sorted(df_track[drivername_col].dropna().astype(str).unique().tolist())

def fastest_per_session(df_in: pd.DataFrame) -> pd.DataFrame:
    if df_in.empty:
        return pd.DataFrame(columns=wanted_labels)
    sess_col_real = _find_col_exact_local(df_in, "SessionName - Info") or sessionname_col
    lap_time_real = _find_col_exact_local(df_in, "LapTime - Info")
    if sess_col_real not in df_in.columns or lap_time_real is None:
        return pd.DataFrame(columns=wanted_labels)
    tmp = df_in.copy()
    tmp["__ltime_sec__"] = tmp[lap_time_real].map(parse_laptime_to_seconds)
    grp = tmp.dropna(subset=["__ltime_sec__"]).groupby(sess_col_real, sort=True)
    if grp.ngroups == 0:
        return pd.DataFrame(columns=wanted_labels)
    best_idx = grp["__ltime_sec__"].idxmin()
    best = tmp.loc[best_idx].copy()
    out_cols = []
    for lbl in wanted_labels:
        src = col_map_export.get(lbl)
        if src is not None and src in best.columns:
            s = best[src]; s.name = lbl
            out_cols.append(s)
        else:
            out_cols.append(pd.Series([np.nan]*len(best), index=best.index, name=lbl))
    out = pd.concat(out_cols, axis=1)
    if "SessionName - Info" in out.columns:
        out = out.sort_values("SessionName - Info", kind="mergesort").reset_index(drop=True)
    return out

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
