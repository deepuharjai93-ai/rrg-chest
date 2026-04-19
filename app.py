# =============================================================================
# Real-Time Indian Market Sector Rotation  ·  RRG Dashboard  v3
# Live Relative Strength & Momentum vs Nifty 50
#
# pip install streamlit yfinance pandas plotly numpy pytz
# streamlit run app.py
# =============================================================================

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
import pytz
import io
import warnings
warnings.filterwarnings("ignore")

# ── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="NSE RRG · Sector Rotation Dashboard",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ═════════════════════════════════════════════════════════════════════════════
#  DESIGN SYSTEM  —  Bloomberg Terminal × Indian Fintech
#  Deep space navy + gold accents + neon quadrant glows
# ═════════════════════════════════════════════════════════════════════════════
DESIGN_CSS = """
<style>
/* ── Google Fonts ── */
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;700&family=Syne:wght@700;800&display=swap');

/* ── Root palette ── */
:root {
  --bg-base:      #04080f;
  --bg-surface:   #080d19;
  --bg-card:      #0c1425;
  --bg-glass:     rgba(12,20,37,0.85);
  --border:       rgba(255,200,50,0.12);
  --border-glow:  rgba(255,200,50,0.35);
  --gold:         #f5c842;
  --gold-dim:     rgba(245,200,66,0.70);
  --text-primary: #e8edf5;
  --text-muted:   #6b7a99;
  --text-dim:     #3a4a6b;
  --leading:      #00e676;
  --weakening:    #ffab40;
  --lagging:      #ff5252;
  --improving:    #40c4ff;
  --accent-blue:  #2979ff;
  --font-display: 'Syne', sans-serif;
  --font-body:    'Space Grotesk', sans-serif;
  --font-mono:    'JetBrains Mono', monospace;
}

/* ── Global overrides ── */
html, body, [class*="css"] {
    font-family: var(--font-body) !important;
    background-color: var(--bg-base) !important;
    color: var(--text-primary) !important;
}
.stApp {
    background: var(--bg-base) !important;
    background-image:
        radial-gradient(ellipse 80% 50% at 50% -10%, rgba(41,121,255,0.08) 0%, transparent 70%),
        radial-gradient(ellipse 50% 30% at 90% 80%, rgba(245,200,66,0.04) 0%, transparent 60%) !important;
}

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background: var(--bg-surface) !important;
    border-right: 1px solid var(--border) !important;
}
section[data-testid="stSidebar"] * {
    color: var(--text-primary) !important;
}
section[data-testid="stSidebar"] .stMarkdown h2,
section[data-testid="stSidebar"] .stMarkdown h3 {
    color: var(--gold) !important;
    font-family: var(--font-display) !important;
    letter-spacing: 0.02em;
}
/* Sidebar slider track */
div[data-testid="stSlider"] > div > div > div {
    background: linear-gradient(90deg, var(--gold) 0%, var(--accent-blue) 100%) !important;
}

/* ── Main content ── */
.main .block-container {
    padding-top: 1.5rem !important;
    padding-bottom: 3rem !important;
    max-width: 1600px !important;
}

/* ── Header banner ── */
.rrg-header {
    background: linear-gradient(135deg, #080d19 0%, #0c1a33 50%, #080d19 100%);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 28px 36px 22px 36px;
    margin-bottom: 24px;
    position: relative;
    overflow: hidden;
}
.rrg-header::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, transparent, var(--gold), var(--accent-blue), transparent);
}
.rrg-header h1 {
    font-family: var(--font-display) !important;
    font-size: 2.1rem !important;
    font-weight: 800 !important;
    background: linear-gradient(90deg, #ffffff 0%, var(--gold) 60%, #ffdd80 100%);
    -webkit-background-clip: text !important;
    -webkit-text-fill-color: transparent !important;
    background-clip: text !important;
    margin: 0 0 4px 0 !important;
    line-height: 1.15 !important;
}
.rrg-header p {
    color: var(--text-muted) !important;
    font-size: 0.95rem !important;
    margin: 0 !important;
    font-family: var(--font-mono) !important;
    letter-spacing: 0.03em;
}
.rrg-tag {
    display: inline-block;
    background: rgba(245,200,66,0.12);
    border: 1px solid rgba(245,200,66,0.3);
    color: var(--gold) !important;
    font-family: var(--font-mono) !important;
    font-size: 0.72rem;
    padding: 2px 10px;
    border-radius: 20px;
    margin-right: 8px;
    margin-bottom: 10px;
}

/* ── Status bar ── */
.status-bar {
    display: flex;
    align-items: center;
    gap: 20px;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 10px 20px;
    margin-bottom: 20px;
    flex-wrap: wrap;
}
.status-pill {
    font-family: var(--font-mono);
    font-size: 0.8rem;
    padding: 4px 12px;
    border-radius: 20px;
}
.pill-open    { background: rgba(0,230,118,0.12); color: #00e676; border: 1px solid rgba(0,230,118,0.3); }
.pill-closed  { background: rgba(255,82,82,0.12);  color: #ff5252; border: 1px solid rgba(255,82,82,0.3); }
.pill-pre     { background: rgba(255,171,64,0.12); color: #ffab40; border: 1px solid rgba(255,171,64,0.3); }
.status-time  { font-family: var(--font-mono); font-size: 0.78rem; color: var(--text-muted); }

/* ── KPI Metric Cards ── */
.kpi-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 14px;
    margin: 18px 0;
}
.kpi-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 16px 20px;
    text-align: center;
    position: relative;
    overflow: hidden;
    transition: border-color 0.2s;
}
.kpi-card::before {
    content: '';
    position: absolute;
    bottom: 0; left: 0; right: 0; height: 3px;
}
.kpi-leading::before   { background: var(--leading); }
.kpi-improving::before { background: var(--improving); }
.kpi-weakening::before { background: var(--weakening); }
.kpi-lagging::before   { background: var(--lagging); }
.kpi-label {
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    margin-bottom: 6px;
    font-family: var(--font-mono);
}
.kpi-value {
    font-size: 2.4rem;
    font-weight: 700;
    font-family: var(--font-display);
    line-height: 1;
}
.kpi-leading   .kpi-label, .kpi-leading   .kpi-value { color: var(--leading); }
.kpi-improving .kpi-label, .kpi-improving .kpi-value { color: var(--improving); }
.kpi-weakening .kpi-label, .kpi-weakening .kpi-value { color: var(--weakening); }
.kpi-lagging   .kpi-label, .kpi-lagging   .kpi-value { color: var(--lagging); }

/* ── Section headings ── */
.section-heading {
    font-family: var(--font-display);
    font-size: 1.1rem;
    font-weight: 700;
    color: var(--text-primary);
    border-left: 3px solid var(--gold);
    padding-left: 12px;
    margin: 28px 0 14px 0;
    letter-spacing: 0.02em;
}

/* ── Streamlit metric widget override ── */
div[data-testid="metric-container"] {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    padding: 14px 18px !important;
}
div[data-testid="metric-container"] label {
    color: var(--text-muted) !important;
    font-family: var(--font-mono) !important;
    font-size: 0.75rem !important;
}
div[data-testid="metric-container"] [data-testid="stMetricValue"] {
    color: var(--text-primary) !important;
    font-family: var(--font-display) !important;
    font-size: 1.8rem !important;
}

/* ── Buttons ── */
div[data-testid="stButton"] > button {
    background: linear-gradient(135deg, rgba(245,200,66,0.15), rgba(41,121,255,0.15)) !important;
    border: 1px solid var(--border-glow) !important;
    color: var(--gold) !important;
    font-family: var(--font-mono) !important;
    font-size: 0.82rem !important;
    font-weight: 600 !important;
    border-radius: 8px !important;
    letter-spacing: 0.05em !important;
    transition: all 0.2s !important;
}
div[data-testid="stButton"] > button:hover {
    background: linear-gradient(135deg, rgba(245,200,66,0.28), rgba(41,121,255,0.25)) !important;
    border-color: var(--gold) !important;
    box-shadow: 0 0 16px rgba(245,200,66,0.2) !important;
}

/* ── Download button ── */
div[data-testid="stDownloadButton"] > button {
    background: rgba(41,121,255,0.12) !important;
    border: 1px solid rgba(41,121,255,0.35) !important;
    color: #7cb9ff !important;
    font-family: var(--font-mono) !important;
    font-size: 0.8rem !important;
    border-radius: 8px !important;
}

/* ── Expanders ── */
div[data-testid="stExpander"] {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    margin-bottom: 12px !important;
}
div[data-testid="stExpander"] summary {
    color: var(--text-primary) !important;
    font-family: var(--font-body) !important;
    font-weight: 500 !important;
}

/* ── Dataframe ── */
div[data-testid="stDataFrame"] {
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    overflow: hidden !important;
}
div[data-testid="stDataFrame"] table {
    background: var(--bg-card) !important;
}

/* ── Warning / error banners ── */
div[data-testid="stAlert"] {
    border-radius: 10px !important;
    font-family: var(--font-mono) !important;
    font-size: 0.82rem !important;
}

/* ── Multiselect tags ── */
span[data-baseweb="tag"] {
    background: rgba(245,200,66,0.15) !important;
    border: 1px solid rgba(245,200,66,0.3) !important;
    color: var(--gold) !important;
    font-family: var(--font-mono) !important;
    font-size: 0.75rem !important;
}

/* ── Toggle ── */
label[data-testid="stToggle"] span {
    color: var(--text-primary) !important;
    font-family: var(--font-body) !important;
}

/* ── Chart container card ── */
.chart-card {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 6px 6px 0 6px;
    margin-bottom: 8px;
    position: relative;
    overflow: hidden;
}
.chart-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0; height: 1px;
    background: linear-gradient(90deg, transparent, rgba(41,121,255,0.6), var(--gold), rgba(41,121,255,0.6), transparent);
}

/* ── Footer ── */
.rrg-footer {
    text-align: center;
    padding: 20px;
    color: var(--text-dim);
    font-family: var(--font-mono);
    font-size: 0.72rem;
    border-top: 1px solid var(--border);
    margin-top: 20px;
    letter-spacing: 0.04em;
}
.rrg-footer span { color: var(--text-muted); }

/* ── Divider ── */
hr[data-testid="stDivider"] {
    border-color: var(--border) !important;
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: var(--bg-base); }
::-webkit-scrollbar-thumb { background: var(--border-glow); border-radius: 3px; }
</style>
"""

# ── Constants ─────────────────────────────────────────────────────────────────
IST = pytz.timezone("Asia/Kolkata")
BENCHMARK_TICKER = "^NSEI"
BENCHMARK_NAME   = "Nifty 50"

SECTORS_WITH_FALLBACK = {
    "Auto":               ["^CNXAUTO",            "NIFTY_AUTO.NS"],
    "Bank":               ["^NSEBANK",             "NIFTY_BANK.NS"],
    "FMCG":               ["^CNXFMCG",             "NIFTY_FMCG.NS"],
    "IT":                 ["^CNXIT",               "NIFTY_IT.NS"],
    "Metal":              ["^CNXMETAL",            "NIFTY_METAL.NS"],
    "Pharma":             ["^CNXPHARMA",           "NIFTY_PHARMA.NS"],
    "Realty":             ["^CNXREALTY",           "NIFTY_REALTY.NS"],
    "Energy":             ["^CNXENERGY",           "NIFTY_ENERGY.NS"],
    "Financial Services": ["NIFTY_FIN_SERVICE.NS", "^CNXFINANCE"],
    "Media":              ["^CNXMEDIA",            "NIFTY_MEDIA.NS"],
    "Commodities":        ["^CNXCOMMODITIES",      "NIFTY_COMMODITIES.NS"],
    "Consumer Durables":  ["NIFTY_CONSR_DURBL.NS", "^CNXCONSUMER"],
    "Private Bank":       ["NIFTY_PVT_BANK.NS",    "^NSEPRIVBANK"],
    "PSU Bank":           ["NIFTY_PSU_BANK.NS",    "^NSEPSUBANK"],
    "Cement":             ["NIFTY_CONSTRCT.NS",    "^CNXCEMENT"],
    "Chemicals":          ["NIFTY_CHEMICALS.NS",   "^CNXCHEMICAL"],
    "Healthcare":         ["NIFTY_HEALTHCARE.NS",  "^CNXHEALTHCARE"],
    "Infra":              ["^CNXINFRA",            "NIFTY_INFRA.NS"],
    "Oil & Gas":          ["NIFTY_OIL_GAS.NS",     "^CNXOILGAS"],
    "PSE":                ["^CNXPSE",              "NIFTY_PSE.NS"],
}
SECTORS = {n: v[0] for n, v in SECTORS_WITH_FALLBACK.items()}

# Premium neon palette for sectors (high-contrast on dark)
SECTOR_COLORS = [
    "#FF6B6B","#00E5FF","#69FF47","#FFAB40","#E040FB",
    "#40C4FF","#FFD740","#FF4081","#64FFDA","#CCFF90",
    "#FF6E40","#18FFFF","#B9F6CA","#FFD180","#EA80FC",
    "#82B1FF","#FF9E80","#F4FF81","#80D8FF","#FFFF8D",
]

QUADRANT_COLORS = {
    "Leading":   "#00e676",
    "Weakening": "#ffab40",
    "Lagging":   "#ff5252",
    "Improving": "#40c4ff",
}
QUADRANT_FILL = {
    "Leading":   "rgba(0,230,118,0.07)",
    "Weakening": "rgba(255,171,64,0.07)",
    "Lagging":   "rgba(255,82,82,0.07)",
    "Improving": "rgba(64,196,255,0.07)",
}
QUADRANT_GLOW = {
    "Leading":   "rgba(0,230,118,0.25)",
    "Weakening": "rgba(255,171,64,0.25)",
    "Lagging":   "rgba(255,82,82,0.25)",
    "Improving": "rgba(64,196,255,0.25)",
}

# ── Market Status ─────────────────────────────────────────────────────────────
def get_market_status():
    now = datetime.now(IST)
    if now.weekday() >= 5:
        return False, "closed", "Market Closed (Weekend)"
    o = now.replace(hour=9,  minute=15, second=0, microsecond=0)
    c = now.replace(hour=15, minute=30, second=0, microsecond=0)
    if o <= now <= c:
        return True,  "open",   "Market Open"
    if now < o:
        return False, "pre",    "Pre-Market"
    return False, "closed", "Market Closed (After Hours)"

# ── Data Fetching ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def fetch_data(lookback_days: int = 365):
    end   = datetime.now()
    start = end - timedelta(days=lookback_days + 90)
    s, e  = start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

    primary = [BENCHMARK_TICKER] + list(SECTORS.values())
    ticker_to_name = {BENCHMARK_TICKER: BENCHMARK_NAME}
    ticker_to_name.update({v: k for k, v in SECTORS.items()})

    close_bulk = pd.DataFrame()
    try:
        raw = yf.download(primary, start=s, end=e,
                          auto_adjust=True, progress=False, threads=True)
        if not raw.empty:
            if isinstance(raw.columns, pd.MultiIndex):
                close_bulk = raw["Close"].copy()
            else:
                col = "Close" if "Close" in raw.columns else raw.columns[0]
                close_bulk = raw[[col]].rename(columns={col: primary[0]})
    except Exception:
        pass

    frames, ticker_used = {}, {}
    if not close_bulk.empty:
        for t in primary:
            nm = ticker_to_name.get(t, t)
            if t in close_bulk.columns:
                sr = close_bulk[t].dropna()
                if len(sr) > 10:
                    frames[nm] = sr
                    ticker_used[nm] = t

    all_names = [BENCHMARK_NAME] + list(SECTORS_WITH_FALLBACK.keys())
    for nm in all_names:
        if nm in frames:
            continue
        candidates = (
            [BENCHMARK_TICKER] if nm == BENCHMARK_NAME
            else SECTORS_WITH_FALLBACK.get(nm, [SECTORS.get(nm)])
        )
        for t in candidates:
            try:
                df = yf.download(t, start=s, end=e,
                                 auto_adjust=True, progress=False)
                if df.empty:
                    continue
                col = "Close" if "Close" in df.columns else df.columns[0]
                sr  = df[col].dropna()
                if len(sr) > 10:
                    frames[nm] = sr
                    ticker_used[nm] = t
                    break
            except Exception:
                continue

    if not frames:
        return pd.DataFrame(), all_names, {}

    combined = pd.DataFrame(frames)
    combined.index = pd.to_datetime(combined.index)
    combined = combined.sort_index().dropna(axis=1, how="all")
    failed = [n for n in all_names if n not in combined.columns]
    return combined, failed, ticker_used

# ── RRG Calculation ───────────────────────────────────────────────────────────
def calculate_rrg(price_df, momentum_period=10, trail_points=20):
    if BENCHMARK_NAME not in price_df.columns:
        return {}

    bench   = price_df[BENCHMARK_NAME].dropna()
    results = {}

    for sector in [c for c in price_df.columns if c != BENCHMARK_NAME]:
        s_raw  = price_df[sector].dropna()
        common = bench.index.intersection(s_raw.index)
        if len(common) < momentum_period + 20:
            continue

        b, s = bench.loc[common], s_raw.loc[common]
        rs   = s / b
        rs_r = rs * 100
        rs_m = rs_r.pct_change(periods=momentum_period) * 100

        win   = min(52, max(10, len(rs_r) // 3))
        rmean = rs_r.rolling(window=win, min_periods=10).mean()
        rstd  = rs_r.rolling(window=win, min_periods=10).std().replace(0, np.nan)
        xn    = 100 + (rs_r - rmean) / rstd
        yn    = rs_m - rs_m.rolling(window=win, min_periods=10).mean()

        valid = xn.dropna().index.intersection(yn.dropna().index)
        if len(valid) < 3:
            continue

        xs, ys = xn.loc[valid], yn.loc[valid]
        idx    = valid[-trail_points:]
        xt, yt = xs.loc[idx], ys.loc[idx]
        xc, yc = float(xt.iloc[-1]), float(yt.iloc[-1])

        quadrant = (
            "Leading"   if xc >= 100 and yc >= 0 else
            "Weakening" if xc >= 100 and yc <  0 else
            "Lagging"   if xc <  100 and yc <  0 else
            "Improving"
        )

        rot = "–"
        if len(xt) >= 3:
            dx    = float(xt.iloc[-1]) - float(xt.iloc[-3])
            dy    = float(yt.iloc[-1]) - float(yt.iloc[-3])
            cross = dx * float(yt.iloc[-2]) - dy * float(xt.iloc[-2])
            rot   = ("↻ Clockwise"   if cross < -1e-9 else
                     "↺ Counter-CW"  if cross >  1e-9 else "→ Lateral")

        chg1 = float(xs.iloc[-1] - xs.iloc[-2]) if len(xs) >= 2 else np.nan
        chg5 = float(xs.iloc[-1] - xs.iloc[-6]) if len(xs) >= 6 else np.nan
        dates = [str(d)[:10] for d in xt.index.tolist()]

        results[sector] = dict(
            xs=xt, ys=yt, xc=xc, yc=yc,
            quadrant=quadrant, rot=rot,
            chg1=chg1, chg5=chg5, dates=dates,
        )
    return results

# ── RRG Chart (100% scatter-based, zero shapes/annotation-arrows) ─────────────
def build_rrg_chart(rrg_data, selected_sectors):
    """
    All quadrant fills, centre lines, labels, and direction arrows are
    implemented as go.Scatter traces — no shapes dict, no annotation arrows —
    making this crash-proof across every Plotly version.
    """
    BG_BASE    = "#04080f"
    BG_SURFACE = "#070c18"
    GRID_COL   = "rgba(255,255,255,0.04)"
    AXIS_COL   = "rgba(255,255,255,0.25)"
    LINE_COL   = "rgba(255,255,255,0.18)"

    fig = go.Figure()

    # ── Compute axis range from data ──────────────────────────────────────────
    all_x = [d["xc"] for d in rrg_data.values() if d]
    all_y = [d["yc"] for d in rrg_data.values() if d]
    for d in rrg_data.values():
        if d:
            all_x += d["xs"].values.tolist()
            all_y += d["ys"].values.tolist()

    pad  = 2.5
    if all_x:
        xmin = min(all_x) - pad
        xmax = max(all_x) + pad
        ymin = min(all_y) - pad
        ymax = max(all_y) + pad
    else:
        xmin, xmax, ymin, ymax = 97, 103, -2, 2

    xmin = min(xmin, 100 - pad)
    xmax = max(xmax, 100 + pad)
    ymin = min(ymin, -pad)
    ymax = max(ymax,  pad)

    BIG = max(abs(xmax - 100), abs(xmin - 100),
              abs(ymax), abs(ymin)) * 4 + 30

    # ── 1. Quadrant fill polygons ─────────────────────────────────────────────
    for q_name, qx, qy in [
        ("Leading",   [100, 100+BIG, 100+BIG, 100,     100],
                      [0,   0,       BIG,     BIG,     0  ]),
        ("Weakening", [100, 100+BIG, 100+BIG, 100,     100],
                      [0,   0,      -BIG,    -BIG,     0  ]),
        ("Lagging",   [100-BIG, 100, 100,     100-BIG, 100-BIG],
                      [-BIG,   -BIG, 0,       0,      -BIG    ]),
        ("Improving", [100-BIG, 100, 100,     100-BIG, 100-BIG],
                      [0,       0,   BIG,     BIG,     0      ]),
    ]:
        fig.add_trace(go.Scatter(
            x=qx, y=qy,
            fill="toself",
            fillcolor=QUADRANT_FILL[q_name],
            line=dict(width=0),
            mode="lines",
            showlegend=False,
            hoverinfo="skip",
            name=f"_fill_{q_name}",
        ))

    # ── 2. Subtle inner glow band near the centre lines ───────────────────────
    # Soft glow strips straddling the dividers
    glow_w = (xmax - xmin) * 0.015
    for q_name, gx, gy in [
        ("Leading",   [100, 100+glow_w, 100+glow_w, 100],
                      [0,   0,          BIG,         BIG]),
        ("Weakening", [100, 100+glow_w, 100+glow_w, 100],
                      [0,   0,         -BIG,        -BIG]),
        ("Lagging",   [100-glow_w, 100, 100,        100-glow_w],
                      [-BIG,      -BIG,  0,          0         ]),
        ("Improving", [100-glow_w, 100, 100,        100-glow_w],
                      [0,          0,   BIG,         BIG       ]),
    ]:
        fig.add_trace(go.Scatter(
            x=gx, y=gy,
            fill="toself",
            fillcolor=QUADRANT_GLOW[q_name],
            line=dict(width=0),
            mode="lines",
            showlegend=False,
            hoverinfo="skip",
            name=f"_glow_{q_name}",
        ))

    # ── 3. Centre cross (vertical + horizontal) ───────────────────────────────
    fig.add_trace(go.Scatter(
        x=[100, 100], y=[ymin - BIG, ymax + BIG],
        mode="lines",
        line=dict(color=LINE_COL, width=1.5, dash="dot"),
        showlegend=False, hoverinfo="skip", name="_vline",
    ))
    fig.add_trace(go.Scatter(
        x=[xmin - BIG, xmax + BIG], y=[0, 0],
        mode="lines",
        line=dict(color=LINE_COL, width=1.5, dash="dot"),
        showlegend=False, hoverinfo="skip", name="_hline",
    ))

    # ── 4. Quadrant corner labels ─────────────────────────────────────────────
    corner_margin_x = (xmax - xmin) * 0.03
    corner_margin_y = (ymax - ymin) * 0.04
    for q_name, lx, ly in [
        ("Leading",   xmax - corner_margin_x, ymax - corner_margin_y),
        ("Weakening", xmax - corner_margin_x, ymin + corner_margin_y),
        ("Lagging",   xmin + corner_margin_x, ymin + corner_margin_y),
        ("Improving", xmin + corner_margin_x, ymax - corner_margin_y),
    ]:
        fig.add_trace(go.Scatter(
            x=[lx], y=[ly],
            mode="text",
            text=[q_name.upper()],
            textfont=dict(
                color=QUADRANT_COLORS[q_name],
                size=13,
                family="Syne, Space Grotesk, sans-serif",
            ),
            showlegend=False,
            hoverinfo="skip",
            name=f"_lbl_{q_name}",
        ))

    # ── 5. Sectors ────────────────────────────────────────────────────────────
    color_idx = 0
    for sector, data in rrg_data.items():
        color = SECTOR_COLORS[color_idx % len(SECTOR_COLORS)]
        color_idx += 1

        if sector not in selected_sectors:
            continue

        xt    = data["xs"].values.tolist()
        yt    = data["ys"].values.tolist()
        dates = data["dates"]
        n     = len(xt)

        # Trail line — opacity gradient faked by a single trace
        fig.add_trace(go.Scatter(
            x=xt[:-1], y=yt[:-1],
            mode="lines",
            line=dict(color=color, width=1.8, dash="dot"),
            opacity=0.40,
            showlegend=False,
            hoverinfo="skip",
            name=sector,
        ))

        # Trail dots with opacity ramp
        opacities = [0.15 + 0.55 * (i / max(n - 2, 1)) for i in range(n - 1)]
        sizes     = [4    + 3    * (i / max(n - 2, 1)) for i in range(n - 1)]
        fig.add_trace(go.Scatter(
            x=xt[:-1], y=yt[:-1],
            mode="markers",
            marker=dict(
                color=color,
                size=sizes,
                opacity=opacities,
            ),
            showlegend=False,
            hoverinfo="skip",
            name=sector,
        ))

        # Direction arrow via lines+markers arrow symbol
        if len(xt) >= 2:
            ax0, ay0 = xt[-2], yt[-2]
            ax1, ay1 = xt[-1], yt[-1]
            dx, dy   = ax1 - ax0, ay1 - ay0
            dist     = (dx**2 + dy**2) ** 0.5
            if dist > 1e-6:
                scale      = min(0.5, dist) / dist
                shaft_x0   = ax1 - dx * scale
                shaft_y0   = ay1 - dy * scale
                angle_deg  = float(np.degrees(np.arctan2(dy, dx)))
                fig.add_trace(go.Scatter(
                    x=[shaft_x0, ax1],
                    y=[shaft_y0, ay1],
                    mode="lines+markers",
                    line=dict(color=color, width=2.2),
                    marker=dict(
                        symbol="arrow",
                        size=11,
                        color=color,
                        angle=-(angle_deg - 90),
                        line=dict(width=0),
                    ),
                    showlegend=False,
                    hoverinfo="skip",
                    name=f"_arr_{sector}",
                ))

        # Current position — glowing marker + label
        q_glow = QUADRANT_COLORS[data["quadrant"]]
        fig.add_trace(go.Scatter(
            x=[data["xc"]],
            y=[data["yc"]],
            mode="markers+text",
            marker=dict(
                color=color,
                size=16,
                symbol="circle",
                line=dict(color=q_glow, width=2.5),
                opacity=1.0,
            ),
            text=[f"  {sector}"],
            textposition="middle right",
            textfont=dict(color=color, size=11,
                          family="Space Grotesk, sans-serif"),
            name=sector,
            showlegend=True,
            customdata=[[
                sector,
                f"{data['xc']:.2f}",
                f"{data['yc']:.2f}",
                data["quadrant"],
                data["rot"],
                dates[-1] if dates else "–",
            ]],
            hovertemplate=(
                "<b style='font-size:13px'>%{customdata[0]}</b><br>"
                "<span style='color:#aaa'>RS-Ratio  </span> %{customdata[1]}<br>"
                "<span style='color:#aaa'>RS-Mom    </span> %{customdata[2]}<br>"
                "<span style='color:#aaa'>Quadrant  </span> %{customdata[3]}<br>"
                "<span style='color:#aaa'>Rotation  </span> %{customdata[4]}<br>"
                "<span style='color:#aaa'>Date      </span> %{customdata[5]}"
                "<extra></extra>"
            ),
        ))

    # ── 6. Layout ─────────────────────────────────────────────────────────────
    fig.update_layout(
        paper_bgcolor=BG_BASE,
        plot_bgcolor=BG_SURFACE,
        height=680,
        margin=dict(l=56, r=56, t=32, b=56),
        font=dict(family="Space Grotesk, sans-serif",
                  color="rgba(255,255,255,0.75)"),
        xaxis=dict(
            title=dict(
                text="◀  RS-Ratio  ▶",
                font=dict(size=11, color=AXIS_COL,
                          family="JetBrains Mono, monospace"),
            ),
            tickfont=dict(size=10, color=AXIS_COL,
                          family="JetBrains Mono, monospace"),
            gridcolor=GRID_COL,
            zerolinecolor=GRID_COL,
            showgrid=True,
            range=[xmin, xmax],
            tickformat=".1f",
        ),
        yaxis=dict(
            title=dict(
                text="RS-Momentum",
                font=dict(size=11, color=AXIS_COL,
                          family="JetBrains Mono, monospace"),
            ),
            tickfont=dict(size=10, color=AXIS_COL,
                          family="JetBrains Mono, monospace"),
            gridcolor=GRID_COL,
            zerolinecolor=GRID_COL,
            showgrid=True,
            range=[ymin, ymax],
            tickformat=".1f",
        ),
        legend=dict(
            bgcolor="rgba(4,8,15,0.85)",
            bordercolor="rgba(255,200,50,0.18)",
            borderwidth=1,
            font=dict(size=10, color="rgba(255,255,255,0.75)",
                      family="Space Grotesk, sans-serif"),
            x=1.01, y=0.98,
            orientation="v",
        ),
        hovermode="closest",
        hoverlabel=dict(
            bgcolor="#0c1425",
            bordercolor="rgba(255,200,50,0.4)",
            font=dict(family="JetBrains Mono, monospace",
                      size=12, color="#e8edf5"),
        ),
    )

    return fig

# ── Summary Table ─────────────────────────────────────────────────────────────
def build_summary_df(rrg_data, selected_sectors):
    rows = []
    for sector, d in rrg_data.items():
        if sector not in selected_sectors:
            continue
        rows.append({
            "Sector":      sector,
            "Quadrant":    d["quadrant"],
            "RS-Ratio":    round(d["xc"], 3),
            "RS-Mom":      round(d["yc"], 3),
            "Rotation":    d["rot"],
            "1D Δ":        round(d["chg1"], 3) if not np.isnan(d["chg1"]) else "–",
            "5D Δ":        round(d["chg5"], 3) if not np.isnan(d["chg5"]) else "–",
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    order_map = {"Leading": 0, "Improving": 1, "Weakening": 2, "Lagging": 3}
    df["_s"] = df["Quadrant"].map(order_map)
    df.sort_values(["_s", "RS-Ratio"], ascending=[True, False], inplace=True)
    df.drop(columns="_s", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df

def style_table(df):
    palette = {
        "Leading":   ("rgba(0,230,118,0.12)",  "#00e676"),
        "Weakening": ("rgba(255,171,64,0.12)", "#ffab40"),
        "Lagging":   ("rgba(255,82,82,0.12)",  "#ff5252"),
        "Improving": ("rgba(64,196,255,0.12)", "#40c4ff"),
    }
    def row_style(row):
        bg, fg = palette.get(row.get("Quadrant", ""), ("", ""))
        if bg:
            return [f"background-color:{bg}; color:{fg}; "
                    f"font-family:'Space Grotesk',sans-serif"] * len(row)
        return [""] * len(row)
    return df.style.apply(row_style, axis=1).format(precision=3)

# ── Sidebar Logo / Brand ──────────────────────────────────────────────────────
SIDEBAR_BRAND = """
<div style="padding:16px 0 8px 0; text-align:center;">
  <div style="font-family:'Syne',sans-serif; font-size:1.25rem;
              font-weight:800; letter-spacing:0.06em;
              background:linear-gradient(90deg,#f5c842,#ffffff);
              -webkit-background-clip:text; -webkit-text-fill-color:transparent;
              background-clip:text;">
    📡 NSE · RRG
  </div>
  <div style="font-family:'JetBrains Mono',monospace; font-size:0.65rem;
              color:#6b7a99; letter-spacing:0.1em; margin-top:2px;">
    SECTOR ROTATION DASHBOARD
  </div>
</div>
<hr style="border:none; border-top:1px solid rgba(255,200,50,0.15); margin:8px 0 16px 0;">
"""

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    # Inject global CSS
    st.markdown(DESIGN_CSS, unsafe_allow_html=True)

    all_names = list(SECTORS_WITH_FALLBACK.keys())

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown(SIDEBAR_BRAND, unsafe_allow_html=True)

        st.markdown("**⚙ Parameters**")
        lookback   = st.slider("Lookback Window (days)", 90, 365, 252, 10)
        mom_period = st.slider("Momentum Period (bars)",  5,  26,  10,  1)
        trail_pts  = st.slider("Trail Length (points)",   5,  40,  20,  5)

        st.markdown("<hr style='border-top:1px solid rgba(255,200,50,0.12);margin:14px 0'>",
                    unsafe_allow_html=True)
        st.markdown("**🏭 Sector Filter**")
        selected = st.multiselect(
            "Sectors to display", options=all_names, default=all_names,
            label_visibility="collapsed",
        )
        if not selected:
            selected = all_names

        st.markdown("<hr style='border-top:1px solid rgba(255,200,50,0.12);margin:14px 0'>",
                    unsafe_allow_html=True)
        auto_ref = st.checkbox("⏱ Auto-Refresh every 60 s")

        st.markdown(
            "<div style='font-family:JetBrains Mono,monospace;font-size:0.68rem;"
            "color:#3a4a6b;line-height:1.9;margin-top:16px'>"
            "DATA  · Yahoo Finance<br>"
            "BENCH · Nifty 50 (^NSEI)<br>"
            "DELAY · ~15 min<br>"
            "CALC  · JdK RS-Ratio approx"
            "</div>",
            unsafe_allow_html=True,
        )

    # ── Market status + auto-refresh ─────────────────────────────────────────
    is_open, pill_cls, status_txt = get_market_status()
    updated = datetime.now(IST).strftime("%d %b %Y  %I:%M:%S %p IST")

    if auto_ref and is_open:
        import time; time.sleep(60)
        st.cache_data.clear(); st.rerun()

    # ── Header ────────────────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="rrg-header">
      <span class="rrg-tag">NSE</span>
      <span class="rrg-tag">LIVE</span>
      <span class="rrg-tag">RRG v3</span>
      <h1>Indian Market Sector Rotation</h1>
      <p>Relative Rotation Graph &nbsp;·&nbsp; RS &amp; Momentum vs Nifty&nbsp;50
         &nbsp;·&nbsp; {updated}</p>
    </div>
    """, unsafe_allow_html=True)

    # ── Status + Refresh row ─────────────────────────────────────────────────
    col_st, col_btn = st.columns([5, 1])
    with col_st:
        pill_html = {
            "open":   '<span class="status-pill pill-open">● OPEN</span>',
            "closed": '<span class="status-pill pill-closed">● CLOSED</span>',
            "pre":    '<span class="status-pill pill-pre">● PRE-MARKET</span>',
        }[pill_cls]
        st.markdown(
            f'<div class="status-bar">'
            f'{pill_html}'
            f'<span class="status-time">NSE · {status_txt}</span>'
            f'<span class="status-time" style="margin-left:auto">'
            f'Benchmark: <b style="color:#f5c842">Nifty 50</b></span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with col_btn:
        refresh_btn = st.button("⟳  Refresh", use_container_width=True)

    if refresh_btn:
        st.cache_data.clear(); st.rerun()

    # ── Fetch ─────────────────────────────────────────────────────────────────
    with st.spinner("Fetching data from Yahoo Finance…"):
        price_df, failed, ticker_used = fetch_data(lookback_days=lookback + 60)

    if price_df.empty:
        st.error("❌ Could not download any data. Check your internet connection.")
        return
    if failed:
        st.warning(f"⚠️ Skipped — no data available for: **{', '.join(failed)}**")
    if BENCHMARK_NAME not in price_df.columns:
        st.error("❌ Nifty 50 (benchmark) data unavailable. Cannot draw RRG.")
        return

    cutoff   = price_df.index[-1] - pd.Timedelta(days=lookback)
    price_df = price_df[price_df.index >= cutoff]

    with st.spinner("Computing RRG values…"):
        rrg_data = calculate_rrg(price_df, mom_period, trail_pts)

    if not rrg_data:
        st.error("❌ Not enough data to compute RRG.")
        return

    # ── KPI Cards ─────────────────────────────────────────────────────────────
    qc = {"Leading": 0, "Improving": 0, "Weakening": 0, "Lagging": 0}
    for s, d in rrg_data.items():
        if s in selected:
            qc[d["quadrant"]] = qc.get(d["quadrant"], 0) + 1

    st.markdown(f"""
    <div class="kpi-grid">
      <div class="kpi-card kpi-leading">
        <div class="kpi-label">▲ Leading</div>
        <div class="kpi-value">{qc['Leading']}</div>
      </div>
      <div class="kpi-card kpi-improving">
        <div class="kpi-label">↗ Improving</div>
        <div class="kpi-value">{qc['Improving']}</div>
      </div>
      <div class="kpi-card kpi-weakening">
        <div class="kpi-label">↘ Weakening</div>
        <div class="kpi-value">{qc['Weakening']}</div>
      </div>
      <div class="kpi-card kpi-lagging">
        <div class="kpi-label">▼ Lagging</div>
        <div class="kpi-value">{qc['Lagging']}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Chart ─────────────────────────────────────────────────────────────────
    st.markdown('<div class="section-heading">Relative Rotation Graph</div>',
                unsafe_allow_html=True)
    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    try:
        fig = build_rrg_chart(rrg_data, selected)
        st.plotly_chart(fig, use_container_width=True,
                        config={"scrollZoom": True,
                                "displayModeBar": True,
                                "modeBarButtonsToRemove": ["lasso2d","select2d"],
                                "toImageButtonOptions": {
                                    "format": "png", "scale": 2,
                                    "filename": "RRG_NSE_sectors"
                                }})
    except Exception as ex:
        st.error(f"❌ Chart render error: {ex}")
        st.info("Try reducing Trail Length or deselecting some sectors.")
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Data Table ────────────────────────────────────────────────────────────
    st.markdown('<div class="section-heading">Sector Data Table</div>',
                unsafe_allow_html=True)
    df = build_summary_df(rrg_data, selected)
    if not df.empty:
        st.dataframe(style_table(df), use_container_width=True,
                     height=min(620, 52 + len(df) * 38))

        c_dl, c_ref = st.columns([2, 6])
        with c_dl:
            buf = io.StringIO()
            df.to_csv(buf, index=False)
            st.download_button(
                "⬇  Export CSV",
                data=buf.getvalue(),
                file_name=f"RRG_{datetime.now(IST).strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv",
                use_container_width=True,
            )

        with st.expander("🔗 Ticker symbols actually resolved"):
            ticker_df = pd.DataFrame([
                {"Sector": n, "Ticker Used": ticker_used.get(n, "–"),
                 "Status": "✓ Loaded" if n in ticker_used else "✗ Skipped"}
                for n in all_names
            ])
            st.dataframe(ticker_df, use_container_width=True, hide_index=True)
    else:
        st.info("No sector data available for current filters.")

    # ── Normalised Price ──────────────────────────────────────────────────────
    with st.expander("📉  Normalised Price Performance  (base = 100 at window start)"):
        avail_cols = [BENCHMARK_NAME] + [s for s in selected if s in price_df.columns]
        norm = price_df[avail_cols].dropna(how="all")
        norm = (norm / norm.iloc[0]) * 100

        fig2 = go.Figure()
        ci   = 0
        for col in norm.columns:
            ib = col == BENCHMARK_NAME
            fig2.add_trace(go.Scatter(
                x=norm.index, y=norm[col], name=col, mode="lines",
                line=dict(
                    color="#f5c842" if ib else SECTOR_COLORS[ci % len(SECTOR_COLORS)],
                    width=2.5 if ib else 1.2,
                ),
            ))
            if not ib:
                ci += 1
        fig2.update_layout(
            paper_bgcolor="#04080f",
            plot_bgcolor="#070c18",
            height=380,
            font=dict(family="Space Grotesk, sans-serif",
                      color="rgba(255,255,255,0.65)"),
            title=dict(text="Normalised Close Price — All Selected Sectors",
                       font=dict(size=13, color="rgba(255,255,255,0.6)"), x=0),
            xaxis=dict(gridcolor="rgba(255,255,255,0.04)",
                       tickfont=dict(family="JetBrains Mono, monospace", size=10)),
            yaxis=dict(gridcolor="rgba(255,255,255,0.04)",
                       tickfont=dict(family="JetBrains Mono, monospace", size=10),
                       title="Indexed Value"),
            hovermode="x unified",
            legend=dict(orientation="h", y=-0.30, bgcolor="rgba(0,0,0,0)",
                        font=dict(size=10)),
            margin=dict(l=50, r=20, t=40, b=80),
        )
        st.plotly_chart(fig2, use_container_width=True)

    # ── How to Read ───────────────────────────────────────────────────────────
    with st.expander("📖  How to Read the Relative Rotation Graph"):
        st.markdown("""
<style>
.rrg-guide table { width:100%; border-collapse:collapse; font-family:'Space Grotesk',sans-serif; }
.rrg-guide th    { background:rgba(255,200,50,0.08); color:#f5c842;
                   padding:8px 12px; text-align:left; font-size:0.8rem;
                   letter-spacing:0.06em; border-bottom:1px solid rgba(255,200,50,0.15); }
.rrg-guide td    { padding:8px 12px; border-bottom:1px solid rgba(255,255,255,0.04);
                   font-size:0.85rem; }
</style>
<div class="rrg-guide">

### Axis Definitions

| Axis | Formula | Meaning |
|------|---------|---------|
| **X — RS-Ratio** | Sector / Benchmark × 100, normalised | > 100 → outperforming Nifty 50 · < 100 → underperforming |
| **Y — RS-Momentum** | Rate-of-change of RS-Ratio | > 0 → relative strength rising · < 0 → falling |

### The Four Quadrants

| Quadrant | Location | Signal |
|----------|----------|--------|
| 🟢 **Leading**   | Top-right    | Outperforming AND momentum positive — **most bullish** |
| 🟠 **Weakening** | Bottom-right | Outperforming BUT momentum fading — consider reducing exposure |
| 🔴 **Lagging**   | Bottom-left  | Underperforming AND momentum negative — **most bearish** |
| 🔵 **Improving** | Top-left     | Underperforming BUT momentum recovering — **early entry zone** |

### Clockwise Rotation Cycle
```
  Improving ──▶ Leading ──▶ Weakening ──▶ Lagging
      ▲                                       │
      └───────────────────────────────────────┘
```
- **Improving → Leading** entry = classic **buy** signal  
- **Weakening → Lagging** entry = classic **exit / short** signal  
- Trail arrows show velocity and direction of rotation  
- Clockwise motion is the healthy, natural cycle

> ⚠️ For educational and research purposes only. Not investment advice.
</div>
        """, unsafe_allow_html=True)

    # ── Footer ────────────────────────────────────────────────────────────────
    st.markdown(
        "<div class='rrg-footer'>"
        "<span>DATA</span> Yahoo Finance (yfinance, ~15-min delay) &nbsp;·&nbsp; "
        "<span>CALC</span> JdK RS-Ratio Approximation &nbsp;·&nbsp; "
        "<span>STACK</span> Streamlit + Plotly &nbsp;·&nbsp; "
        "<span>NOTE</span> Educational use only — not investment advice"
        "</div>",
        unsafe_allow_html=True,
    )

if __name__ == "__main__":
    main()
