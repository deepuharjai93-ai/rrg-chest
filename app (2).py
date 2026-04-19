# =============================================================================
# Real-Time Indian Market Sector Rotation RRG Dashboard
# Live Relative Strength & Momentum vs Nifty 50
#
# Installation:
#   pip install streamlit yfinance pandas plotly numpy pytz
#
# Run:
#   streamlit run app.py
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
    page_title="RRG Dashboard – Indian Sectors",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Constants ─────────────────────────────────────────────────────────────────
BENCHMARK_TICKER = "^NSEI"
BENCHMARK_NAME   = "Nifty 50"
IST = pytz.timezone("Asia/Kolkata")

# Primary ticker → fallback ticker list.  First one that returns data wins.
SECTORS_WITH_FALLBACK = {
    "Auto":               ["^CNXAUTO",           "NIFTY_AUTO.NS"],
    "Bank":               ["^NSEBANK",            "NIFTY_BANK.NS"],
    "FMCG":               ["^CNXFMCG",            "NIFTY_FMCG.NS"],
    "IT":                 ["^CNXIT",              "NIFTY_IT.NS"],
    "Metal":              ["^CNXMETAL",           "NIFTY_METAL.NS"],
    "Pharma":             ["^CNXPHARMA",          "NIFTY_PHARMA.NS"],
    "Realty":             ["^CNXREALTY",          "NIFTY_REALTY.NS"],
    "Energy":             ["^CNXENERGY",          "NIFTY_ENERGY.NS"],
    "Financial Services": ["NIFTY_FIN_SERVICE.NS","^CNXFINANCE"],
    "Media":              ["^CNXMEDIA",           "NIFTY_MEDIA.NS"],
    "Commodities":        ["^CNXCOMMODITIES",     "NIFTY_COMMODITIES.NS"],
    "Consumer Durables":  ["NIFTY_CONSR_DURBL.NS","^CNXCONSUMER"],
    "Private Bank":       ["NIFTY_PVT_BANK.NS",   "^NSEPRIVBANK"],
    "PSU Bank":           ["NIFTY_PSU_BANK.NS",   "^NSEPSUBANK"],
    "Cement":             ["NIFTY_CONSTRCT.NS",   "^CNXCEMENT"],
    "Chemicals":          ["NIFTY_CHEMICALS.NS",  "^CNXCHEMICAL"],
    "Healthcare":         ["NIFTY_HEALTHCARE.NS", "^CNXHEALTHCARE"],
    "Infra":              ["^CNXINFRA",           "NIFTY_INFRA.NS"],
    "Oil & Gas":          ["NIFTY_OIL_GAS.NS",   "^CNXOILGAS"],
    "PSE":                ["^CNXPSE",             "NIFTY_PSE.NS"],
}

# Flat primary ticker map (used for batch download attempt)
SECTORS = {name: tickers[0] for name, tickers in SECTORS_WITH_FALLBACK.items()}

SECTOR_COLORS = [
    "#FF6B6B","#4ECDC4","#45B7D1","#96CEB4","#FFEAA7",
    "#DDA0DD","#98D8C8","#F7DC6F","#BB8FCE","#85C1E9",
    "#F0B27A","#82E0AA","#F1948A","#AED6F1","#A9DFBF",
    "#FAD7A0","#D2B4DE","#A3E4D7","#FADBD8","#D5DBDB",
]

QUADRANT_COLORS = {
    "Leading":   "#00C851",
    "Weakening": "#FF8800",
    "Lagging":   "#FF4444",
    "Improving": "#33B5E5",
}

QUADRANT_BG = {
    "Leading":   "rgba(0,200,81,0.10)",
    "Weakening": "rgba(255,136,0,0.10)",
    "Lagging":   "rgba(255,68,68,0.10)",
    "Improving": "rgba(51,181,229,0.10)",
}

# ── Market Status ─────────────────────────────────────────────────────────────
def get_market_status():
    now_ist = datetime.now(IST)
    if now_ist.weekday() >= 5:
        return False, "🔴 Market Closed (Weekend)"
    market_open  = now_ist.replace(hour=9,  minute=15, second=0, microsecond=0)
    market_close = now_ist.replace(hour=15, minute=30, second=0, microsecond=0)
    if market_open <= now_ist <= market_close:
        return True,  "🟢 Market Open"
    elif now_ist < market_open:
        return False, "🟡 Pre-Market"
    return False, "🔴 Market Closed (After Hours)"

# ── Data Fetching ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def fetch_data(lookback_days: int = 365):
    """
    Download adjusted-close prices for the benchmark + all sectors.
    For each sector, tries the primary ticker then fallbacks until one works.
    Returns (price_df, failed_list, ticker_used_map).
    """
    end_date   = datetime.now()
    start_date = end_date - timedelta(days=lookback_days + 90)
    start_str  = start_date.strftime("%Y-%m-%d")
    end_str    = end_date.strftime("%Y-%m-%d")

    # ── Step 1: bulk download of primary tickers ─────────────────────────────
    primary_tickers = [BENCHMARK_TICKER] + list(SECTORS.values())
    close_bulk      = pd.DataFrame()
    try:
        raw = yf.download(
            primary_tickers,
            start=start_str, end=end_str,
            auto_adjust=True, progress=False, threads=True,
        )
        if isinstance(raw.columns, pd.MultiIndex):
            close_bulk = raw["Close"].copy()
        elif not raw.empty:
            col        = "Close" if "Close" in raw.columns else raw.columns[0]
            close_bulk = raw[[col]].rename(columns={col: primary_tickers[0]})
    except Exception:
        pass

    # Build reverse map: ticker → name
    ticker_to_name = {BENCHMARK_TICKER: BENCHMARK_NAME}
    ticker_to_name.update({v: k for k, v in SECTORS.items()})

    frames      = {}   # name → Series
    ticker_used = {}   # name → ticker string actually used

    # ── Step 2: process bulk result ──────────────────────────────────────────
    if not close_bulk.empty:
        for ticker in primary_tickers:
            name = ticker_to_name.get(ticker, ticker)
            if ticker in close_bulk.columns:
                series = close_bulk[ticker].dropna()
                if len(series) > 10:
                    frames[name]      = close_bulk[ticker]
                    ticker_used[name] = ticker

    # ── Step 3: retry failed sectors with fallback tickers ───────────────────
    all_names = [BENCHMARK_NAME] + list(SECTORS_WITH_FALLBACK.keys())
    for name in all_names:
        if name in frames:
            continue

        candidates = (
            [BENCHMARK_TICKER]
            if name == BENCHMARK_NAME
            else SECTORS_WITH_FALLBACK.get(name, [SECTORS.get(name)])
        )

        for ticker in candidates:
            try:
                df = yf.download(
                    ticker, start=start_str, end=end_str,
                    auto_adjust=True, progress=False,
                )
                if df.empty:
                    continue
                close_col = "Close" if "Close" in df.columns else df.columns[0]
                series    = df[close_col].dropna()
                if len(series) > 10:
                    frames[name]      = series
                    ticker_used[name] = ticker
                    break
            except Exception:
                continue

    if not frames:
        return pd.DataFrame(), list(all_names), {}

    combined = pd.DataFrame(frames)
    combined.index = pd.to_datetime(combined.index)
    combined       = combined.sort_index().dropna(axis=1, how="all")

    loaded_set = set(combined.columns.tolist())
    failed     = [n for n in all_names if n not in loaded_set]

    return combined, failed, ticker_used

# ── RRG Calculation ───────────────────────────────────────────────────────────
def calculate_rrg(
    price_df: pd.DataFrame,
    momentum_period: int = 10,
    trail_points: int = 20,
):
    """
    Compute normalised RS-Ratio (X) and RS-Momentum (Y) for every sector.
    Returns dict keyed by sector name.
    """
    if BENCHMARK_NAME not in price_df.columns:
        return {}

    bench        = price_df[BENCHMARK_NAME].dropna()
    sector_names = [c for c in price_df.columns if c != BENCHMARK_NAME]
    results      = {}

    for sector in sector_names:
        s      = price_df[sector].dropna()
        common = bench.index.intersection(s.index)
        if len(common) < momentum_period + 20:
            continue

        b = bench.loc[common]
        s = s.loc[common]

        rs          = s / b
        rs_ratio    = rs * 100
        rs_momentum = rs_ratio.pct_change(periods=momentum_period) * 100

        roll_win = min(52, max(10, len(rs_ratio) // 3))

        roll_mean = rs_ratio.rolling(window=roll_win, min_periods=10).mean()
        roll_std  = rs_ratio.rolling(window=roll_win, min_periods=10).std()
        roll_std  = roll_std.replace(0, np.nan)

        rs_ratio_norm = 100 + (rs_ratio - roll_mean) / roll_std
        rs_mom_norm   = (
            rs_momentum
            - rs_momentum.rolling(window=roll_win, min_periods=10).mean()
        )

        valid = (
            rs_ratio_norm.dropna().index
            .intersection(rs_mom_norm.dropna().index)
        )
        if len(valid) < 3:
            continue

        x_series  = rs_ratio_norm.loc[valid]
        y_series  = rs_mom_norm.loc[valid]
        trail_idx = valid[-trail_points:]
        x_trail   = x_series.loc[trail_idx]
        y_trail   = y_series.loc[trail_idx]
        x_cur     = float(x_trail.iloc[-1])
        y_cur     = float(y_trail.iloc[-1])

        if   x_cur >= 100 and y_cur >= 0: quadrant = "Leading"
        elif x_cur >= 100 and y_cur <  0: quadrant = "Weakening"
        elif x_cur <  100 and y_cur <  0: quadrant = "Lagging"
        else:                              quadrant = "Improving"

        rotation_dir = "–"
        if len(x_trail) >= 3:
            dx    = float(x_trail.iloc[-1]) - float(x_trail.iloc[-3])
            dy    = float(y_trail.iloc[-1]) - float(y_trail.iloc[-3])
            cross = dx * float(y_trail.iloc[-2]) - dy * float(x_trail.iloc[-2])
            rotation_dir = (
                "↻ Clockwise"         if cross < -1e-9 else
                "↺ Counter-Clockwise" if cross >  1e-9 else
                "→ Lateral"
            )

        chg_1d = float(x_series.iloc[-1] - x_series.iloc[-2]) if len(x_series) >= 2 else np.nan
        chg_5d = float(x_series.iloc[-1] - x_series.iloc[-6]) if len(x_series) >= 6 else np.nan

        results[sector] = {
            "rs_ratio_trail":      x_trail,
            "rs_momentum_trail":   y_trail,
            "rs_ratio_current":    x_cur,
            "rs_momentum_current": y_cur,
            "quadrant":            quadrant,
            "rotation_dir":        rotation_dir,
            "chg_1d_ratio":        chg_1d,
            "chg_5d_ratio":        chg_5d,
        }

    return results

# ── Plotly RRG Chart ──────────────────────────────────────────────────────────
def build_rrg_chart(
    rrg_data: dict,
    selected_sectors: list,
    dark_mode: bool = True,
):
    """
    Build interactive Plotly RRG.

    KEY FIX: Quadrant fills use xref='x' yref='y' with ±1e6 numeric bounds.
    Mixing 'paper' and axis refs inside a single rect shape caused a
    ValueError in Plotly ≥5.x — this version avoids that entirely.
    """
    template   = "plotly_dark"  if dark_mode else "plotly_white"
    paper_bg   = "#1a1a2e"      if dark_mode else "#f8f9fa"
    plot_bg    = "#16213e"      if dark_mode else "#ffffff"
    axis_color = "#aaaaaa"      if dark_mode else "#444444"
    text_color = "#ffffff"      if dark_mode else "#111111"
    grid_color = "rgba(100,100,100,0.2)"
    line_color = "rgba(200,200,200,0.55)"

    fig         = go.Figure()
    shapes      = []
    annotations = []

    # ── Quadrant fills (all data-coordinate, no mixed xref/yref) ─────────────
    BIG = 1e6
    for q_name, x0, x1, y0, y1 in [
        ("Leading",    100,  BIG,   0,   BIG),
        ("Weakening",  100,  BIG, -BIG,   0),
        ("Lagging",   -BIG,  100, -BIG,   0),
        ("Improving", -BIG,  100,   0,   BIG),
    ]:
        shapes.append(dict(
            type="rect",
            xref="x", yref="y",
            x0=x0, x1=x1, y0=y0, y1=y1,
            fillcolor=QUADRANT_BG[q_name],
            line=dict(width=0),
            layer="below",
        ))

    # ── Centre lines (mixing paper/axis refs is fine for *line* shapes) ───────
    shapes.extend([
        dict(type="line", xref="x", yref="paper",
             x0=100, x1=100, y0=0, y1=1,
             line=dict(color=line_color, width=1.5, dash="dash")),
        dict(type="line", xref="paper", yref="y",
             x0=0, x1=1, y0=0, y1=0,
             line=dict(color=line_color, width=1.5, dash="dash")),
    ])

    # ── Quadrant corner labels ────────────────────────────────────────────────
    for q_name, xp, yp, xanchor, yanchor in [
        ("Leading",   0.98, 0.98, "right", "top"),
        ("Weakening", 0.98, 0.02, "right", "bottom"),
        ("Lagging",   0.02, 0.02, "left",  "bottom"),
        ("Improving", 0.02, 0.98, "left",  "top"),
    ]:
        annotations.append(dict(
            xref="paper", yref="paper",
            x=xp, y=yp,
            text=f"<b>{q_name.upper()}</b>",
            font=dict(color=QUADRANT_COLORS[q_name], size=13, family="Arial"),
            showarrow=False,
            xanchor=xanchor, yanchor=yanchor,
        ))

    # ── Sector Trails & Markers ───────────────────────────────────────────────
    color_idx = 0
    for sector, data in rrg_data.items():
        color = SECTOR_COLORS[color_idx % len(SECTOR_COLORS)]
        color_idx += 1

        if sector not in selected_sectors:
            continue

        x_trail = data["rs_ratio_trail"].values.tolist()
        y_trail = data["rs_momentum_trail"].values.tolist()
        dates   = [str(d)[:10] for d in data["rs_ratio_trail"].index.tolist()]

        # Dotted trail line
        fig.add_trace(go.Scatter(
            x=x_trail[:-1], y=y_trail[:-1],
            mode="lines",
            line=dict(color=color, width=1.5, dash="dot"),
            opacity=0.50,
            showlegend=False,
            hoverinfo="skip",
            name=sector,
        ))

        # Faded trail dots
        fig.add_trace(go.Scatter(
            x=x_trail[:-1], y=y_trail[:-1],
            mode="markers",
            marker=dict(color=color, size=4, opacity=0.30),
            showlegend=False,
            hoverinfo="skip",
            name=sector,
        ))

        # Current position — large labelled marker
        fig.add_trace(go.Scatter(
            x=[data["rs_ratio_current"]],
            y=[data["rs_momentum_current"]],
            mode="markers+text",
            marker=dict(
                color=color, size=14, symbol="circle",
                line=dict(color="white", width=1.5),
            ),
            text=[f"  {sector}"],
            textposition="middle right",
            textfont=dict(color=color, size=11, family="Arial Black"),
            name=sector,
            showlegend=True,
            customdata=[[
                sector,
                f"{data['rs_ratio_current']:.2f}",
                f"{data['rs_momentum_current']:.2f}",
                data["quadrant"],
                data["rotation_dir"],
                dates[-1] if dates else "–",
            ]],
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "RS-Ratio : %{customdata[1]}<br>"
                "RS-Mom   : %{customdata[2]}<br>"
                "Quadrant : %{customdata[3]}<br>"
                "Rotation : %{customdata[4]}<br>"
                "Date     : %{customdata[5]}"
                "<extra></extra>"
            ),
        ))

        # Direction arrow (second-last → last)
        if len(x_trail) >= 2:
            annotations.append(dict(
                x=x_trail[-1],  y=y_trail[-1],
                ax=x_trail[-2], ay=y_trail[-2],
                xref="x",  yref="y",
                axref="x", ayref="y",
                showarrow=True,
                arrowhead=2, arrowsize=1.4,
                arrowwidth=2, arrowcolor=color,
            ))

    # ── Layout ────────────────────────────────────────────────────────────────
    fig.update_layout(
        template=template,
        paper_bgcolor=paper_bg,
        plot_bgcolor=plot_bg,
        height=720,
        margin=dict(l=70, r=200, t=70, b=70),
        title=dict(
            text="<b>Relative Rotation Graph (RRG)</b> — Indian Sectors vs Nifty 50",
            font=dict(size=18, color=text_color),
            x=0.01,
        ),
        xaxis=dict(
            title="← Lagging  ·  RS-Ratio  ·  Leading →",
            titlefont=dict(color=axis_color, size=12),
            tickfont=dict(color=axis_color),
            gridcolor=grid_color,
            zerolinecolor=grid_color,
            showgrid=True,
        ),
        yaxis=dict(
            title="↑ Rising Momentum  ·  RS-Momentum  ·  Falling ↓",
            titlefont=dict(color=axis_color, size=12),
            tickfont=dict(color=axis_color),
            gridcolor=grid_color,
            zerolinecolor=grid_color,
            showgrid=True,
        ),
        legend=dict(
            orientation="v", x=1.01, y=1,
            bgcolor=(
                "rgba(0,0,0,0.3)" if dark_mode
                else "rgba(255,255,255,0.8)"
            ),
            bordercolor="rgba(200,200,200,0.3)",
            borderwidth=1,
            font=dict(color=text_color, size=10),
        ),
        shapes=shapes,
        annotations=annotations,
        dragmode="pan",
        hovermode="closest",
    )

    return fig

# ── Summary Table ─────────────────────────────────────────────────────────────
def build_summary_df(rrg_data: dict, selected_sectors: list) -> pd.DataFrame:
    rows = []
    for sector, data in rrg_data.items():
        if sector not in selected_sectors:
            continue
        rows.append({
            "Sector":      sector,
            "RS-Ratio":    round(data["rs_ratio_current"],    3),
            "RS-Momentum": round(data["rs_momentum_current"], 3),
            "Quadrant":    data["quadrant"],
            "Rotation":    data["rotation_dir"],
            "1D Δ Ratio":  (
                round(data["chg_1d_ratio"], 3)
                if not np.isnan(data["chg_1d_ratio"]) else "–"
            ),
            "5D Δ Ratio":  (
                round(data["chg_5d_ratio"], 3)
                if not np.isnan(data["chg_5d_ratio"]) else "–"
            ),
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    order = {"Leading": 0, "Improving": 1, "Weakening": 2, "Lagging": 3}
    df["_sort"] = df["Quadrant"].map(order)
    df.sort_values(
        ["_sort", "RS-Ratio"], ascending=[True, False], inplace=True
    )
    df.drop(columns="_sort", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def style_table(df: pd.DataFrame):
    color_map = {
        "Leading":   "background-color:rgba(0,200,81,0.18);  color:#00C851",
        "Weakening": "background-color:rgba(255,136,0,0.18); color:#FF8800",
        "Lagging":   "background-color:rgba(255,68,68,0.18); color:#FF4444",
        "Improving": "background-color:rgba(51,181,229,0.18);color:#33B5E5",
    }
    def row_style(row):
        style = color_map.get(row.get("Quadrant", ""), "")
        return [style] * len(row)
    return df.style.apply(row_style, axis=1).format(precision=3)

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    st.markdown(
        """
        <h1 style='margin-bottom:0'>
            📈 Real-Time Indian Market Sector Rotation
        </h1>
        <h3 style='color:#aaa; margin-top:4px'>
            Relative Rotation Graph (RRG) —
            Live RS &amp; Momentum vs Nifty&nbsp;50
        </h3>
        """,
        unsafe_allow_html=True,
    )

    is_open, status_str = get_market_status()
    last_updated = datetime.now(IST).strftime("%d %b %Y  %I:%M:%S %p IST")

    col_s1, col_s2, col_s3 = st.columns([2, 3, 2])
    with col_s1:
        st.markdown(f"**Market Status:** {status_str}")
    with col_s2:
        st.markdown(f"**Last Updated:** `{last_updated}`")
    with col_s3:
        refresh_btn = st.button("🔄 Refresh Data", use_container_width=True)

    st.divider()

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("## ⚙️ Settings")

        lookback_days = st.slider(
            "Lookback Window (days)",
            min_value=90, max_value=365, value=252, step=10,
        )
        momentum_period = st.slider(
            "Momentum Period (bars)",
            min_value=5, max_value=26, value=10,
            help="Rate-of-change period for RS-Momentum (Y-axis).",
        )
        trail_points = st.slider(
            "Trail Length (points)",
            min_value=5, max_value=40, value=20, step=5,
        )
        dark_mode = st.toggle("🌙 Dark Theme", value=True)

        st.markdown("---")
        st.markdown("### 🏭 Sector Filter")
        all_sector_names = list(SECTORS_WITH_FALLBACK.keys())
        selected_sectors = st.multiselect(
            "Select sectors to display:",
            options=all_sector_names,
            default=all_sector_names,
        )
        if not selected_sectors:
            selected_sectors = all_sector_names

        st.markdown("---")
        auto_refresh = st.checkbox(
            "⏱ Auto-Refresh (60 s, market hours only)",
            value=False,
        )
        st.markdown(
            "**Data:** Yahoo Finance (yfinance)  \n"
            "**Benchmark:** Nifty 50 (`^NSEI`)  \n"
            "**Delay:** ~15 min  "
        )

    # ── Auto-refresh ──────────────────────────────────────────────────────────
    if auto_refresh and is_open:
        import time; time.sleep(60)
        st.cache_data.clear(); st.rerun()

    if refresh_btn:
        st.cache_data.clear(); st.rerun()

    # ── Fetch ─────────────────────────────────────────────────────────────────
    with st.spinner("⏳ Fetching market data from Yahoo Finance…"):
        price_df, failed_tickers, ticker_used = fetch_data(
            lookback_days=lookback_days + 60
        )

    if price_df.empty:
        st.error(
            "❌ Could not download any market data. "
            "Check your internet connection."
        )
        return

    if failed_tickers:
        st.warning(
            f"⚠️ Skipped (no data available for these tickers): "
            f"**{', '.join(failed_tickers)}**"
        )

    if BENCHMARK_NAME not in price_df.columns:
        st.error("❌ Benchmark (Nifty 50) data unavailable. Cannot draw RRG.")
        return

    cutoff   = price_df.index[-1] - pd.Timedelta(days=lookback_days)
    price_df = price_df[price_df.index >= cutoff]

    # ── RRG Compute ───────────────────────────────────────────────────────────
    with st.spinner("🔢 Computing Relative Strength & Momentum…"):
        rrg_data = calculate_rrg(
            price_df,
            momentum_period=momentum_period,
            trail_points=trail_points,
        )

    if not rrg_data:
        st.error("❌ Insufficient overlapping data for RRG calculation.")
        return

    # ── Chart ─────────────────────────────────────────────────────────────────
    fig = build_rrg_chart(rrg_data, selected_sectors, dark_mode=dark_mode)
    st.plotly_chart(
        fig, use_container_width=True,
        config={"scrollZoom": True},
    )

    # ── KPI row ───────────────────────────────────────────────────────────────
    st.markdown("### 📊 Quadrant Summary")
    q_counts = {"Leading": 0, "Improving": 0, "Weakening": 0, "Lagging": 0}
    for s, d in rrg_data.items():
        if s in selected_sectors:
            q_counts[d["quadrant"]] = q_counts.get(d["quadrant"], 0) + 1

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("🟢 Leading",   q_counts["Leading"])
    k2.metric("🔵 Improving", q_counts["Improving"])
    k3.metric("🟠 Weakening", q_counts["Weakening"])
    k4.metric("🔴 Lagging",   q_counts["Lagging"])

    # ── Table ─────────────────────────────────────────────────────────────────
    st.markdown("### 📋 Sector RRG Data Table")
    summary_df = build_summary_df(rrg_data, selected_sectors)

    if not summary_df.empty:
        st.dataframe(
            style_table(summary_df),
            use_container_width=True,
            height=min(620, 50 + len(summary_df) * 40),
        )
        csv_buf = io.StringIO()
        summary_df.to_csv(csv_buf, index=False)
        st.download_button(
            "⬇️ Export RRG Data (CSV)",
            data=csv_buf.getvalue(),
            file_name=f"rrg_{datetime.now(IST).strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
        )

        with st.expander(
            "🔗 Ticker Reference — which symbol was used for each sector"
        ):
            ticker_rows = [
                {"Sector": name, "Ticker Used": ticker_used.get(name, "–")}
                for name in all_sector_names
            ]
            st.dataframe(
                pd.DataFrame(ticker_rows), use_container_width=True
            )
    else:
        st.info("No sector data to display.")

    # ── Normalised price ──────────────────────────────────────────────────────
    with st.expander(
        "📉 Normalised Price Performance (base = 100)", expanded=False
    ):
        cols_avail = [BENCHMARK_NAME] + [
            s for s in selected_sectors if s in price_df.columns
        ]
        norm_df = price_df[cols_avail].dropna(how="all")
        norm_df = (norm_df / norm_df.iloc[0]) * 100

        fig_px = go.Figure()
        ci = 0
        for col in norm_df.columns:
            is_bench = col == BENCHMARK_NAME
            fig_px.add_trace(go.Scatter(
                x=norm_df.index, y=norm_df[col], name=col, mode="lines",
                line=dict(
                    color=(
                        "white" if is_bench
                        else SECTOR_COLORS[ci % len(SECTOR_COLORS)]
                    ),
                    width=2.5 if is_bench else 1.2,
                ),
            ))
            if not is_bench:
                ci += 1

        fig_px.update_layout(
            template="plotly_dark" if dark_mode else "plotly_white",
            height=420,
            title="Normalised Close Price",
            xaxis_title="Date",
            yaxis_title="Indexed Value (100 = start)",
            hovermode="x unified",
            legend=dict(orientation="h", y=-0.35),
        )
        st.plotly_chart(fig_px, use_container_width=True)

    # ── How to read ───────────────────────────────────────────────────────────
    with st.expander("📖 How to Read the RRG", expanded=False):
        st.markdown(
            """
            ## Understanding the RRG

            | Axis | Meaning |
            |------|---------|
            | **X — RS-Ratio** | >100 = sector is **outperforming** Nifty 50; <100 = underperforming |
            | **Y — RS-Momentum** | >0 = relative strength **improving**; <0 = deteriorating |

            ### Four Quadrants

            | Quadrant | Signal |
            |----------|--------|
            | 🟢 **Leading** (top-right)    | Outperforming AND momentum still rising — **most bullish** |
            | 🟠 **Weakening** (bottom-right)| Outperforming BUT momentum fading — consider reducing |
            | 🔴 **Lagging** (bottom-left)   | Underperforming AND momentum falling — **most bearish** |
            | 🔵 **Improving** (top-left)    | Underperforming BUT momentum recovering — early entry zone |

            ### Clockwise Rotation (normal cycle)
            ```
            Improving → Leading → Weakening → Lagging → Improving …
            ```
            - A sector moving from **Improving → Leading** = potential **buy** signal  
            - A sector moving from **Weakening → Lagging** = potential **exit** signal  
            - The trail arrow shows direction of travel; clockwise is the healthy cycle

            > ⚠️ For educational use only. Not investment advice.
            """
        )

    st.markdown("---")
    st.markdown(
        "<div style='text-align:center;color:#777;font-size:12px'>"
        "Data via Yahoo Finance · ~15-min delayed · "
        "RRG: JdK RS-Ratio approximation · "
        "Built with Streamlit + Plotly · Educational use only"
        "</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
