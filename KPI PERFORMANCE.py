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
# Regex global (precisa estar antes de funções que usam)
# =========================
_num_pat = re.compile(r"[-+]?\d*[\.,]?\d+")

# =========================
# LEGENDAS FIXAS (WINTAX, linha 2)
# =========================
LEGEND_LABELS = {
    "Brake_Efficiency - Max": "- Quanto MAIOR melhor",
    "Brake_Efficiency - Avg": "- Quanto MAIOR melhor",
    "24_Brake_Locking_Left_Rear - Min": "- Quanto MAIS NEGATIVO, mais a roda RL esta BLOQUEANDO",
    "24_Brake_Locking_Left_Rear - Avg": "- Quanto MAIS NEGATIVO, mais a roda RL esta BLOQUEANDO",
    "24_Brake_Locking_Right_Rear - Min": "- Quanto MAIS NEGATIVO, mais a roda RR esta BLOQUEANDO",
    "24_Brake_Locking_Right_Rear - Avg": "- Quanto MAIS NEGATIVO, mais a roda RR esta BLOQUEADO",
    "25_Steer_Balance - Min": "- Quanto MAIS NEGATIVO, mais OVERSTEER o carro",
    "25_Steer_Balance - Max": "- Quanto MAIS NEGATIVO, mais UNDERSTEER o carro",
    "25_Steer_Balance - Avg": "- Quanto MAIS NEGATIVO, mais UNDERSTEER o carro",
    "24_TractionControl - Max": "- Quanto MAIOR, mais o carro esta DESTRACIONANDO na saida de curva",
    "24_TractionControl - Avg": "- Quanto MAIOR, mais o carro esta DESTRACIONANDO na saida de curva",
    "24_Rear_Wheel_Speeds_Difference - Min": "- Minima diferença entre as rodas traseiras durante a volta",
    "24_Rear_Wheel_Speeds_Difference - Max": "- Máxima diferença entre as rodas traseiras durante a volta",
    "24_Rear_Wheel_Speeds_Difference - Avg": "- Média de diferença entre as rodas traseiras durante a volta",
    "24_Expected_Rear_Wheel_Speeds_Difference - Min": "-  Minima difereça entre as velocidades de rodas traseiras esperada durante a volta",
    "24_Expected_Rear_Wheel_Speeds_Difference - Max": "-  Máxima difereça entre as velocidades de rodas traseiras esperada durante a volta",
    "24_Expected_Rear_Wheel_Speeds_Difference - Avg": "-  Média de difereça entre as velocidades de rodas traseiras esperada durante a volta",
    "24_Differential_Delta_Real_Expec - Min": "- Minima diferença entre as velocidade das rodas traseiras esperadas e a real, quanto MENOR mais perto do ideal entre o esperado e o real",
    "24_Differential_Delta_Real_Expec - Max": "- Máxima diferença entre as velocidade das rodas traseiras esperadas e a real, quanto MENOR mais perto do ideal entre o esperado e o real",
    "24_Differential_Delta_Real_Expec - Avg": "- Média de diferença entre as velocidade das rodas traseiras esperadas e a real, quanto MENOR mais perto do ideal entre o esperado e o real",
    "25_Brake_Migration - Max": "- Quando MAIOR, mais MIGRAÇÃO do freio durante as frenagens, na volta",
    "25_SR_Traction_Left - Max": "- Quanto MAIOR, mais a RL esta DESTRACIONANDO em saída de curva na volta",
    "25_SR_Traction_Left - Avg": "- Quanto MAIOR, mais a RL esta DESTRACIONANDO em saída de curva na volta",
    "25_SR_Traction_Right - Max": "- Quanto MAIOR, mais a RR esta DESTRACIONANDO em saída de curva na volta",
    "25_SR_Traction_Right - Avg": "- Quanto MAIOR, mais a RR esta DESTRACIONANDO em saída de curva na volta",
    "25_Brake_Locking_Time_Rear - Max": "- Quanto MAIOR mais tempo as tempo as rodas traseiras passaram BLOQUEANDO na volta",
    "25_SR_Traction_Time - Max": "- Quanto MAIOR mais tempo as tempo as rodas traseiras passaram DESTRACIONANDO na volta",
    "25_Brake_Locking_Time_Front - Max": "- Quanto MAIOR, mais tempo as rodas DIANTEIRAS passaram BLOQUEANDO na volta",
    "25_Differential_Locking - Min": "- Porcentagem MINIMA de BLOQUEIO DE DIFERENCIAL DURANTE COASTING, na volta",
    "25_Differential_Locking - Max": "- Porcentagem MÁXIMA de BLOQUEIO DE DIFERENCIAL DURANTE COASTING, na volta",
    "25_Differential_Locking - Avg": "- MÉDIA de porcentagem de BLOQUEIO DE DIFERENCIAL DURANTE COASTING, na volta",
    "25_Lateral_Load_Transfer_Front - Max": "- MÁXIMA transferencia lateral de carga na FRENTE pela suspensão em curva na volta",
    "25_Lateral_Load_Transfer_Front - Avg": "- MÉDIA de transferencia lateral de carga na FRENTE pela suspensão em curva na volta",
    "25_Lateral_Load_Transfer_Front_Left - Max": "- MÁXIMA transferencia lateral de carga DA DIANTEIRA EM CURVAS PARA ESQUERDA pela suspensão em curva na volta",
    "25_Lateral_Load_Transfer_Front_Left - Avg": "- MÉDIA de transferencia lateral de carga  DA DIANTEIRA EM CURVAS PARA ESQUERDA pela suspensão em curva na volta",
    "25_Lateral_Load_Transfer_Front_Right - Max": "- MÁXIMA transferencia lateral de carga DA DIANTEIRA EM CURVAS PARA DIREITA pela suspensão em curva na volta",
    "25_Lateral_Load_Transfer_Front_Right - Avg": "- MÉDIA de transferencia lateral de carga DA DIANTEIRA EM CURVAS PARA DIREITA pela suspensão em curva na volta",
    "25_Lateral_Load_Transfer_Rear - Max": "- MÁXIMA transferencia lateral de carga na TRASEIRA pela suspensão em curva na volta",
    "25_Lateral_Load_Transfer_Rear - Avg": "- MÉDIA de transferencia lateral de carga na TRASEIRA pela suspensão em curva na volta",
    "25_Lateral_Load_Transfer_Rear_Left - Max": "- MÁXIMA transferencia lateral de carga NA TRASEIRA EM CURVAS PARA ESQUERDA pela suspensão em curva na volta",
    "25_Lateral_Load_Transfer_Rear_Left - Avg": "- MÉDIA de transferencia lateral de carga NA TRASEIRA EM CURVAS PARA ESQUERDA pela suspensão em curva na volta",
    "25_Lateral_Load_Transfer_Rear_Right - Max": "- MÁXIMA transferencia lateral de carga NA TRASEIRA EM CURVAS PARA DIREITA pela suspensão em curva na volta",
    "25_Lateral_Load_Transfer_Rear_Right - Avg": "- MÉDIA de transferencia lateral de carga NA TRASEIRA EM CURVAS PARA DIREITA pela suspensão em curva na volta",
    "25_Lateral_load_Trasfer_Total - Max": "- MÁXIMA  transferancia de carga lateral pela suspensão do CARRO em curva na volta",
    "25_Lateral_load_Trasfer_Total - Avg": "- MÉDIA de  transferancia de carga lateral pela suspensão do CARRO em curva na volta",
    "25_Lateral_Load_Transfer_Distribution - Max": "- MÁXIMA DISTRIBUIÇÃO em % em relação a DIANTEIRA de transferencia lateral de carga em curvas na volta do CARRO",
    "25_Lateral_Load_Transfer_Distribution - Avg": "- MÉDIA de DISTRIBUIÇÃO em % em relação a DIANTEIRA de transferencia lateral de carga em curvas na volta do CARRO",
    "25_Roll_Car_Grap - Min": "- MINIMA ROLAGEM do CARRO durante a volta toda",
    "25_Roll_Car_Grap - Max": "- MÁXIMA ROLAGEM do CARRO durante a volta toda",
    "25_Roll_Car_Grap - Avg": "- MÉDIA de ROLAGEM do CARRO durante a volta toda",
    "25_Roll_Front_Grap - Min": "- MINIMA ROLAGEM DA FRENTE  durante a volta toda",
    "25_Roll_Front_Grap - Max": "- MÁXIMA ROLAGEM DA FRENTE  durante a volta toda",
    "25_Roll_Front_Grap - Avg": "- MÉDIA DE ROLAGEM DA FRENTE  durante a volta toda",
    "25_Roll_Front_Left - Max": "- MÁXIMA ROLAGEM da DIANTEIRA em curvas para ESQUERDA na volta",
    "25_Roll_Front_Left - Avg": "- MÉDIA de ROLAGEM da DIANTEIRA em curvas para ESQUERDA na volta",
    "25_Roll_Front_Right - Max": "- MÁXIMA ROLAGEM da DIANTEIRA em curvas para DIREITA na volta",
    "25_Roll_Front_Right - Avg": "- MÉDIA de ROLAGEM da DIANTEIRA em curvas para DIREITA na volta",
    "25_Roll_Rear_Grap - Max": "- MÁXIMA ROLAGEM DA TRASEIRA  durante a volta toda",
    "25_Roll_Rear_Grap - Avg": "- MÉDIA DE ROLAGEM DA TRASEIRA  durante a volta toda",
    "25_Roll_Rear_Left - Max": "- MÁXIMA ROLAGEM da TRASEIRA em curvas para ESQUERDA na volta",
    "25_Roll_Rear_Left - Avg": "- MÉDIA de ROLAGEM da TRASEIRA em curvas para ESQUERDA na volta",
    "25_Roll_Rear_Right - Max": "- MÁXIMA ROLAGEM da TRASEIRA em curvas para DIREITA na volta",
    "25_Roll_Rear_Right - Avg": "- MÉDIA de ROLAGEM da TRASEIRA em curvas para DIREITA na volta",
    "25_Rake_Aero - Min": "- MINIMO RAKE atingido durante a volta EM RETA, quanto MENOR, MAIS RAKE",
    "25_Rake_Aero - Max": "- MÁXIMO RAKE atingido durante a volta EM RETA, quanto MENOR, MAIS RAKE",
    "25_Rake_Aero - Avg": "- MÉDIA de RAKE atingido durante a volta EM RETA, quanto MENOR, MAIS RAKE",
    "25_Rake_Cornering - Min": "- MINIMO RAKE atingido durante a volta EM CURVA, quanto MENOR, MAIS RAKE",
    "25_Rake_Cornering - Max": "- MÁXIMO RAKE atingido durante a volta EM CURVA, quanto MENOR, MAIS RAKE",
    "25_Rake_Cornering - Avg": "- MÉDIA de  RAKE atingido durante a volta EM CURVA, quanto MENOR, MAIS RAKE",
    "25_Rake_Pitch - Min": "- MINIMO RAKE atingido durante a volta EM FRENAGEM, quanto MENOR, MAIS RAKE",
    "25_Rake_Pitch - Max": "- MÁXIMO RAKE atingido durante a volta EM FRENAGEM, quanto MENOR, MAIS RAKE",
    "25_Rake_Pitch - Avg": "- MÉDIA de  RAKE atingido durante a volta EM FRENAGEM, quanto MENOR, MAIS RAKE",
    "25_Rake_Traction - Min": "- MINIMO RAKE atingido durante a volta EM SAÍDA DE CURVA, quanto MENOR, MAIS RAKE",
    "25_Rake_Traction - Max": "- MÁXIMO RAKE atingido durante a volta EM SAÍDA DE CURVA, quanto MENOR, MAIS RAKE",
    "25_Rake_Traction - Avg": "- MÉDIA de  RAKE atingido durante a volta EM SAÍDA DE CURVA, quanto MENOR, MAIS RAKE",
    "25_DownForce_Total - Max": "- MAIOR  Downforce atingido na volta",
    "25_DownForce_Total - Avg": "- MÉDIA de  Downforce atingido na volta",
    "24_Downforce_Distr_Front - Max": "- MAIOR distribuição de Downforce atingido na volta em relação a DIANTEIRA",
    "24_Downforce_Distr_Front - Avg": "- MÉDIA de distribuição de Downforce atingido na volta em relação a DIANTEIRA",
    "Roll_Gradiente_Front - Avg": "- QUANTO MAIOR MAIS MACIO, analisar mudanças de molas e ARB na DIANTEIRA",
    "Roll_Gradiente_Rear - Avg": "- QUANTO MAIOR MAIS MACIO, analisar mudanças de molas e ARB na TRASEIRA",
}

def get_metric_legend(y_col: str):
    y = str(y_col).strip()
    if y in LEGEND_LABELS:
        return LEGEND_LABELS[y]
    base = re.sub(r"( - Min| - Max| - Avg| - Mean| - Median| - Info)$", "", y)
    for key, val in LEGEND_LABELS.items():
        if key.startswith(base):
            return val
    return None


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
# OBS: não junta "25_AcLat_Trigger" com "Ac.Lat" — são bases distintas
_BASE_SYNONYMS = {
    # existentes
    "tire": ["tyre", "pneu", "tires", "tyres"],
    "tyre": ["tire", "pneu", "tires", "tyres"],
    "pneu": ["tire", "tyre", "tires", "tyres"],

    # aceleração lateral/longitudinal (mantém bases "ac lat" e "ac long")
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

if base.empty:
    st.warning("Nenhum dado após os filtros selecionados.")
    st.stop()

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
# Métricas (ordem do Excel) — OPÇÃO A (numeric-ish)
# =========================
def _is_numericish(series: pd.Series, thresh=0.5):
    """Detecta colunas numéricas OU texto que contém números (>= thresh de valores válidos)."""
    if pd.api.types.is_numeric_dtype(series):
        return True
    s = series.astype(str).str.replace(",", ".", regex=False)
    vals = s.map(lambda x: (_num_pat.search(x) or [None])[0])
    vals = pd.to_numeric(vals, errors="coerce")
    return np.isfinite(vals).mean() >= thresh

metricas = []
for c in df.columns:
    if c in METRIC_BLACKLIST: 
        continue
    if c in [col_map[k] for k in required]: 
        continue
    if c in ("XKey","XLabel"):
        continue
    if _is_numericish(df[c]):
        metricas.append(c)

metricas_all = []
for c in df.columns:
    if c not in METRIC_BLACKLIST:
        metricas_all.append(c)

# =========================
# Utils (ordenação, ticks) — FIX p/ regex com capture group
# =========================
def _numeric_from_any(series: pd.Series) -> pd.Series:
    z = series.astype(str).str.replace(",", ".", regex=False)
    # regex COM grupo de captura
    m = z.str.extract(r"([-+]?\d*\.?\d+)", expand=False)
    return pd.to_numeric(m, errors='coerce')

def _order(dfin: pd.DataFrame) -> pd.DataFrame:
    sdate_ord = pd.to_datetime(dfin[sessiondate_col], errors='coerce')
    run_ord   = _numeric_from_any(dfin[run_col])
    lap_ord   = _numeric_from_any(dfin[lap_col])
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
    s = str(x).strip().lower().replace(",", ".")
    s = re.sub(r"\s+", "", s)
    if not s or s in {"nan","none"}: return np.nan
    m = re.match(r"(?:(\d+)\s*[m'’])?\s*(\d+(?:\.\d+)?)\s*(?:s|\"|”)?$", s)
    if m:
        mm = float(m.group(1) or 0.0)
        ss = float(m.group(2))
        return 60.0*mm + ss
    if ":" in s:
        try:
            mm, ss = s.split(":", 1)
            return float(mm)*60.0 + float(ss)
        except Exception:
            pass
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

    # tentativa de converter "texto numérico"
    if col in dfin.columns and not pd.api.types.is_numeric_dtype(dfin[col]):
        s = dfin[col].astype(str).str.replace(",", ".", regex=False)
        s = s.map(lambda x: (_num_pat.search(x) or [None])[0])
        ser = pd.to_numeric(s, errors="coerce")
        if ser.notna().any():
            return ser, y_col, {}

    # categórico genérico
    if col in dfin.columns:
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

    # legenda fixa (se existir para esta métrica)
    legend_custom = get_metric_legend(y_col)

    x_vals  = df_plot['XKey'].tolist()
    x_texts = df_plot['XLabel'].tolist()
    tickvals, ticktext = sample_ticks(x_vals, x_texts, max_ticks=30)

    custom_cols = [lap_col, sessionname_col, trackname_col, 'XLabel']
    if "comment_text" in extra:
        df_plot["__comment__"] = extra["comment_text"]; custom_cols.append("__comment__")
    if "category_text" in extra:
        df_plot["__category__"] = extra["category_text"]; custom_cols.append("__category__")

    fig = px.line(
        df_plot, x='XKey', y="__y__", color=color_col, markers=True,
        title=y_title, custom_data=custom_cols
    )

    fig.update_traces(hovertemplate=hover_template_for(
        y_title, "comment_text" in extra, "category_text" in extra
    ))

    if legend_custom:
        # sem legenda de cores; apenas texto explicativo embaixo do gráfico
        fig.update_layout(
            showlegend=False,
            title_font=dict(size=40, color="white"),
            height=600,
            margin=dict(t=80, b=110, l=80, r=20),
        )
        fig.add_annotation(
            text=legend_custom,
            xref="paper", yref="paper",
            x=0.5, y=-0.20,
            showarrow=False,
            xanchor="center", yanchor="top",
            font=dict(size=13, color="white"),
            align="center"
        )
    else:
        # comportamento original com legenda lateral
        fig.update_layout(
            title_font=dict(size=40, color="white"),
            height=600,
            legend=legend_right,
            legend_title_text=legend_title,
            margin=dict(t=80, b=40, l=80, r=260),
            showlegend=True,
        )

    fig.update_xaxes(
        type='category',
        categoryorder='array',
        categoryarray=list(dict.fromkeys(x_vals)),
        tickmode='array',
        tickvals=tickvals,
        ticktext=ticktext,
        title=None
    )

    if "category_map" in extra:
        name_to_code = extra["category_map"]
        fig.update_yaxes(
            tickmode="array",
            tickvals=list(name_to_code.values()),
            ticktext=list(name_to_code.keys())
        )

    return fig, df_plot


# =========================
# Defaults iniciais (sem escopo global)
# =========================
def _reset_initial_defaults(metricas_in, metricas_all_in, df_in: pd.DataFrame):
    """
    Define/repõe os defaults respeitando a ordem do Excel e evita UnboundLocalError.
    Retorna (metricas_out, metricas_all_out).
    """
    # Evita refazer se os dados não mudaram
    sig = (tuple(sorted(df_in.columns)), int(df_in.shape[0]))
    if st.session_state.get("_data_sig") == sig:
        return metricas_in, metricas_all_in

    st.session_state["_data_sig"] = sig

    # Cópias locais
    metricas_out = list(metricas_in)
    metricas_all_out = list(metricas_all_in)

    # Defaults G1..G8
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
        real = find_metric(df_in, label) or label
        if real not in METRIC_BLACKLIST and real not in metricas_out:
            metricas_out = _insert_by_excel_order(df_in, metricas_out, real)
        st.session_state[f"g{i}::metric"] = real

    # Dispersão (G9)
    x_default = find_metric(df_in, "G_Comb -Avg") or "G_Comb -Avg"
    y_default = find_metric(df_in, "LapTime - Info") or "LapTime - Info"
    if x_default not in METRIC_BLACKLIST and x_default not in metricas_all_out:
        metricas_all_out = _insert_by_excel_order(df_in, metricas_all_out, x_default)
    if y_default not in METRIC_BLACKLIST and y_default not in metricas_all_out:
        metricas_all_out = _insert_by_excel_order(df_in, metricas_all_out, y_default)
    st.session_state["disp::x"] = x_default
    st.session_state["disp::y"] = y_default
    st.session_state["disp::trend"] = False

    return metricas_out, metricas_all_out

# aplica defaults
metricas, metricas_all = _reset_initial_defaults(metricas, metricas_all, df)

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
        if dfin is None or dfin.empty: return dfin
        dfout = dfin.copy()
        if driver: dfout = dfout[dfout[drivername_col].astype(str) == str(driver)]
        if mode == "Apenas uma" and session:
            dfout = dfout[dfout[sessionname_col].astype(str) == str(session)]
        return dfout

    if cmp_cfg is None:
        df_g = base_df.copy()
        fig, used = draw_line(df_g, y_i, sessionname_col, "SessionName")
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
        finite = np.isfinite(vec)
        has_vals = bool(finite.any())
        v = vec[finite] if has_vals else None
        c1, c2, c3 = st.columns(3)
        with c1: st.metric("Mínimo", f"{v.min():.3f}" if has_vals else "—")
        with c2: st.metric("Máximo", f"{v.max():.3f}" if has_vals else "—")
        with c3: st.metric("Média",  f"{v.mean():.3f}" if has_vals else "—")

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

                if "disp::x" not in st.session_state or st.session_state["disp::x"] not in metricas_all:
                    st.session_state["disp::x"] = find_metric(df, "G_Comb -Avg") or "G_Comb -Avg"
                    if st.session_state["disp::x"] not in metricas_all:
                        metricas_all = _insert_by_excel_order(df, metricas_all, st.session_state["disp::x"])

                if "disp::y" not in st.session_state or st.session_state["disp::y"] not in metricas_all:
                    st.session_state["disp::y"] = find_metric(df, "LapTime - Info") or "LapTime - Info"
                    if st.session_state["disp::y"] not in metricas_all:
                        metricas_all = _insert_by_excel_order(df, metricas_all, st.session_state["disp::y"])

                if "disp::trend" not in st.session_state:
                    st.session_state["disp::trend"] = False

                x_disp = st.selectbox("Métrica X:", metricas_all, key="disp::x")
                y_disp = st.selectbox("Métrica Y:", metricas_all, key="disp::y")
                trend  = st.checkbox("Mostrar linha de tendência", key="disp::trend")

                x_ok = (x_disp in df.columns) or (find_metric(df, x_disp) is not None)
                y_ok = (y_disp in df.columns) or (find_metric(df, y_disp) is not None)
                if x_ok and y_ok:
                    x_col = x_disp if x_disp in df.columns else find_metric(df, x_disp)
                    y_col = y_disp if y_disp in df.columns else find_metric(df, y_disp)
                    df_disp = df.copy()
                    y_series, y_title, _ = materialize_metric_series(df_disp, y_col)
                    df_disp["__y__"] = y_series
                    fig_disp = px.scatter(
                        df_disp, x=x_col, y="__y__",
                        color=sessionname_col if sessionname_col in df.columns else None,
                        title=f"{x_disp} vs {y_title}"
                    )
                    fig_disp.update_layout(title_font=dict(size=40, color="white"), height=600, legend=legend_right)
                    st.plotly_chart(fig_disp, use_container_width=True, key="plot_disp")
                else:
                    st.info("Selecione X e Y válidos para a dispersão.")

# =====================================================================
# PLANILHAS NO APP (volta mais rápida por sessão)
# =====================================================================
st.markdown("---")
st.header("Planilhas por TrackName - Info (volta mais rápida por sessão)")

all_tracks = sorted(df[trackname_col].dropna().astype(str).unique().tolist())
track_sel = st.selectbox("TrackName - Info (planilhas):", all_tracks, index=0, key="export::track")

# Rótulos exibidos na tabela (mantidos, incluindo Ac.Lat e 25_AcLat_Trigger)
wanted_labels = [
    "SessionName - Info", "LapTime - Info", "Tire - Info", "TrackName - Info",
    "Ac.Lat - Min", "Ac.Lat - Max", "Ac.Lat - Avg",
    "Ac.Long - Min", "Ac.Long - Max", "Ac.Long - Avg",
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
    return find_metric(df_in, label)

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
        src = col_map_export.get(lbl) or _find_col_exact_local(df_in, lbl)
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

