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
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import pytz
import io
import warnings
warnings.filterwarnings("ignore")

# ── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="RRG Dashboard – Indian Sectors",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Constants ────────────────────────────────────────────────────────────────
BENCHMARK_TICKER = "^NSEI"
BENCHMARK_NAME   = "Nifty 50"
IST = pytz.timezone("Asia/Kolkata")

SECTORS = {
    "Auto":               "^CNXAUTO",
    "Bank":               "^NSEBANK",
    "FMCG":               "^CNXFMCG",
    "IT":                 "^CNXIT",
    "Metal":              "^CNXMETAL",
    "Pharma":             "^CNXPHARMA",
    "Realty":             "^CNXREALTY",
    "Energy":             "^CNXENERGY",
    "Financial Services": "NIFTY_FIN_SERVICE.NS",
    "Media":              "^CNXMEDIA",
    "Commodities":        "^CNXCOMMODITIES",
    "Consumer Durables":  "^CNXCONSUMER",
    "Private Bank":       "^NSEPRIVBANK",
    "PSU Bank":           "^NSEPSUBANK",
    "Cement":             "^CNXCEMENT",
    "Chemicals":          "^CNXCHEMICAL",
    "Healthcare":         "^CNXHEALTHCARE",
    "Infra":              "^CNXINFRA",
    "Oil & Gas":          "^CNXOILGAS",
    "PSE":                "^CNXPSE",
}

# Distinct colors for sectors
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
    "Leading":   "rgba(0,200,81,0.08)",
    "Weakening": "rgba(255,136,0,0.08)",
    "Lagging":   "rgba(255,68,68,0.08)",
    "Improving": "rgba(51,181,229,0.08)",
}

# ── Helper: Market Status ─────────────────────────────────────────────────────
def get_market_status():
    """Return (is_open: bool, status_str: str)."""
    now_ist = datetime.now(IST)
    weekday = now_ist.weekday()          # Mon=0 … Sun=6
    if weekday >= 5:
        return False, "🔴 Market Closed (Weekend)"
    market_open  = now_ist.replace(hour=9,  minute=15, second=0, microsecond=0)
    market_close = now_ist.replace(hour=15, minute=30, second=0, microsecond=0)
    if market_open <= now_ist <= market_close:
        return True,  "🟢 Market Open"
    elif now_ist < market_open:
        return False, "🟡 Pre-Market"
    else:
        return False, "🔴 Market Closed (After Hours)"

# ── Data Fetching ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def fetch_data(lookback_days: int = 365):
    """
    Download adjusted-close prices for the benchmark and all sectors.
    Returns a DataFrame with columns = [BENCHMARK_NAME] + sector names.
    Missing / failed tickers are silently dropped.
    """
    end_date   = datetime.now()
    start_date = end_date - timedelta(days=lookback_days + 60)  # extra buffer

    all_tickers = {BENCHMARK_NAME: BENCHMARK_TICKER}
    all_tickers.update(SECTORS)

    frames      = {}
    failed      = []

    # Download in one batch where possible, then fall back individually
    ticker_list = list(all_tickers.values())
    try:
        raw = yf.download(
            ticker_list,
            start=start_date.strftime("%Y-%m-%d"),
            end=end_date.strftime("%Y-%m-%d"),
            auto_adjust=True,
            progress=False,
            threads=True,
        )
        # yfinance returns MultiIndex columns when >1 ticker
        if isinstance(raw.columns, pd.MultiIndex):
            close_data = raw["Close"]
        else:
            close_data = raw[["Close"]].rename(columns={"Close": ticker_list[0]})

        # Reverse-map ticker → name
        ticker_to_name = {v: k for k, v in all_tickers.items()}
        close_data.columns = [ticker_to_name.get(c, c) for c in close_data.columns]
        frames = {col: close_data[col] for col in close_data.columns}

    except Exception as e:
        # Full batch failed — try one by one
        for name, ticker in all_tickers.items():
            try:
                df = yf.download(
                    ticker,
                    start=start_date.strftime("%Y-%m-%d"),
                    end=end_date.strftime("%Y-%m-%d"),
                    auto_adjust=True,
                    progress=False,
                )
                if not df.empty and "Close" in df.columns:
                    frames[name] = df["Close"]
                else:
                    failed.append(name)
            except Exception:
                failed.append(name)

    if not frames:
        return pd.DataFrame(), failed

    combined = pd.DataFrame(frames)
    combined.index = pd.to_datetime(combined.index)
    combined.sort_index(inplace=True)

    # Drop columns that are entirely NaN
    combined.dropna(axis=1, how="all", inplace=True)

    # Identify what actually failed
    loaded_names = set(combined.columns.tolist())
    all_names    = set(all_tickers.keys())
    failed       = list(all_names - loaded_names)

    return combined, failed

# ── RRG Calculation ───────────────────────────────────────────────────────────
def calculate_rrg(price_df: pd.DataFrame, momentum_period: int = 10, trail_points: int = 20):
    """
    Compute RS-Ratio and RS-Momentum for every sector vs the benchmark.

    Returns a dict:
        {
          sector_name: {
              "rs_ratio_trail":    pd.Series,   # last trail_points values
              "rs_momentum_trail": pd.Series,
              "rs_ratio_current":  float,
              "rs_momentum_current": float,
              "quadrant":          str,
              "rotation_dir":      str,
              "chg_1d_ratio":      float,
              "chg_5d_ratio":      float,
          }
        }
    """
    if BENCHMARK_NAME not in price_df.columns:
        return {}

    bench = price_df[BENCHMARK_NAME].dropna()
    results = {}

    sector_names = [c for c in price_df.columns if c != BENCHMARK_NAME]

    for sector in sector_names:
        sector_series = price_df[sector].dropna()

        # Align to common dates
        common_idx = bench.index.intersection(sector_series.index)
        if len(common_idx) < momentum_period + 5:
            continue

        s = sector_series.loc[common_idx]
        b = bench.loc[common_idx]

        # ── Core RRG math (JdK-style approximation) ──────────────────────────
        rs        = s / b
        rs_ratio  = rs * 100                                      # X-axis

        # 10-period (or user-chosen) Rate of Change of RS-Ratio → Y-axis
        rs_mom    = rs_ratio.pct_change(periods=momentum_period) * 100

        # Normalise RS-Ratio around 100 via simple z-score rescaling
        # (professional tools use a proprietary smoothing; this is the
        #  standard open-source approximation that gives the right quadrants)
        rs_ratio_norm = (
            100
            + (rs_ratio - rs_ratio.rolling(window=52, min_periods=10).mean())
            / rs_ratio.rolling(window=52, min_periods=10).std()
        )

        # Normalise momentum around 0
        rs_mom_norm = rs_mom - rs_mom.rolling(window=52, min_periods=10).mean()

        # Drop NaN rows after normalization
        valid = rs_ratio_norm.dropna().index.intersection(rs_mom_norm.dropna().index)
        if len(valid) < 2:
            continue

        x_series = rs_ratio_norm.loc[valid]
        y_series = rs_mom_norm.loc[valid]

        # Take last trail_points
        trail_idx = valid[-trail_points:]
        x_trail   = x_series.loc[trail_idx]
        y_trail   = y_series.loc[trail_idx]

        x_cur = float(x_trail.iloc[-1])
        y_cur = float(y_trail.iloc[-1])

        # ── Quadrant ──────────────────────────────────────────────────────────
        if x_cur >= 100 and y_cur >= 0:
            quadrant = "Leading"
        elif x_cur >= 100 and y_cur < 0:
            quadrant = "Weakening"
        elif x_cur < 100 and y_cur < 0:
            quadrant = "Lagging"
        else:
            quadrant = "Improving"

        # ── Rotation direction (based on last 3 points) ───────────────────────
        rotation_dir = "–"
        if len(x_trail) >= 3:
            dx = float(x_trail.iloc[-1]) - float(x_trail.iloc[-3])
            dy = float(y_trail.iloc[-1]) - float(y_trail.iloc[-3])
            cross = dx * float(y_trail.iloc[-2]) - dy * float(x_trail.iloc[-2])
            if cross < 0:
                rotation_dir = "↻ Clockwise"
            elif cross > 0:
                rotation_dir = "↺ Counter-Clockwise"
            else:
                rotation_dir = "→ Lateral"

        # ── 1-day & 5-day change in RS-Ratio ─────────────────────────────────
        chg_1d = chg_5d = np.nan
        if len(x_series) >= 2:
            chg_1d = float(x_series.iloc[-1]) - float(x_series.iloc[-2])
        if len(x_series) >= 6:
            chg_5d = float(x_series.iloc[-1]) - float(x_series.iloc[-6])

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
def build_rrg_chart(rrg_data: dict, selected_sectors: list, dark_mode: bool = True):
    """Build the interactive Plotly RRG figure."""

    template   = "plotly_dark" if dark_mode else "plotly_white"
    paper_bg   = "#1a1a2e" if dark_mode else "#f8f9fa"
    plot_bg    = "#16213e" if dark_mode else "#ffffff"
    axis_color = "#aaaaaa" if dark_mode else "#444444"
    text_color = "#ffffff" if dark_mode else "#111111"
    grid_color = "rgba(100,100,100,0.2)"

    fig = go.Figure()

    # ── Quadrant background rectangles ───────────────────────────────────────
    quad_defs = [
        ("Leading",   100, None, 0, None, "Leading",   0.08, 0.96),
        ("Weakening", 100, None, None, 0, "Weakening",  0.92, 0.96),
        ("Lagging",   None, 100, None, 0, "Lagging",    0.08, 0.04),
        ("Improving", None, 100, 0, None, "Improving",  0.08, 0.52),
    ]

    # We'll add quadrant shapes after traces so they sit behind
    shapes = []
    annotations = []

    # Quadrant fills
    for name, x0, x1, y0, y1, label, ax, ay in quad_defs:
        color = QUADRANT_BG[name]
        shapes.append(dict(
            type="rect",
            xref="paper" if x0 is None else "x",
            yref="paper" if y0 is None else "y",
            x0=0 if x0 is None else x0,
            x1=1 if x1 is None else x1,
            y0=0 if y0 is None else y0,
            y1=1 if y1 is None else y1,
            fillcolor=color,
            line=dict(width=0),
            layer="below",
        ))

    # Quadrant labels (corners)
    corner_labels = [
        ("Leading",   1.01, 1.01, "right", "top"),
        ("Weakening", 1.01, -1.01, "right", "bottom"),
        ("Lagging",  -1.01, -1.01, "left",  "bottom"),
        ("Improving",-1.01,  1.01, "left",  "top"),
    ]
    # We'll use relative paper coords
    for q_name, xfrac, yfrac, xanchor, yanchor in [
        ("Leading",   0.98, 0.98, "right", "top"),
        ("Weakening", 0.98, 0.02, "right", "bottom"),
        ("Lagging",   0.02, 0.02, "left",  "bottom"),
        ("Improving", 0.02, 0.98, "left",  "top"),
    ]:
        annotations.append(dict(
            xref="paper", yref="paper",
            x=xfrac, y=yfrac,
            text=f"<b>{q_name.upper()}</b>",
            font=dict(color=QUADRANT_COLORS[q_name], size=13, family="Arial"),
            showarrow=False,
            xanchor=xanchor, yanchor=yanchor,
            bgcolor="rgba(0,0,0,0)" ,
        ))

    # ── Sector Trails & Markers ───────────────────────────────────────────────
    color_idx = 0
    for sector, data in rrg_data.items():
        if sector not in selected_sectors:
            color_idx += 1
            continue

        color = SECTOR_COLORS[color_idx % len(SECTOR_COLORS)]
        color_idx += 1

        x_trail = data["rs_ratio_trail"].values.tolist()
        y_trail = data["rs_momentum_trail"].values.tolist()
        dates   = [str(d)[:10] for d in data["rs_ratio_trail"].index.tolist()]

        n = len(x_trail)
        # Build opacity gradient for trail
        alphas = [0.2 + 0.6 * (i / max(n - 1, 1)) for i in range(n)]

        # Trail line
        fig.add_trace(go.Scatter(
            x=x_trail[:-1], y=y_trail[:-1],
            mode="lines",
            line=dict(color=color, width=1.5, dash="dot"),
            opacity=0.55,
            showlegend=False,
            hoverinfo="skip",
            name=sector,
        ))

        # Trail dots (faded)
        fig.add_trace(go.Scatter(
            x=x_trail[:-1], y=y_trail[:-1],
            mode="markers",
            marker=dict(color=color, size=4, opacity=0.4),
            showlegend=False,
            hoverinfo="skip",
            name=sector,
        ))

        # Current position (large marker)
        fig.add_trace(go.Scatter(
            x=[data["rs_ratio_current"]],
            y=[data["rs_momentum_current"]],
            mode="markers+text",
            marker=dict(
                color=color,
                size=14,
                symbol="circle",
                line=dict(color="white", width=1.5),
            ),
            text=[sector],
            textposition="top center",
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
                "RS-Ratio: %{customdata[1]}<br>"
                "RS-Momentum: %{customdata[2]}<br>"
                "Quadrant: %{customdata[3]}<br>"
                "Rotation: %{customdata[4]}<br>"
                "Date: %{customdata[5]}<extra></extra>"
            ),
        ))

        # Arrow from second-last → last position
        if len(x_trail) >= 2:
            ax_pos = x_trail[-1] - x_trail[-2]
            ay_pos = y_trail[-1] - y_trail[-2]
            annotations.append(dict(
                x=x_trail[-1], y=y_trail[-1],
                ax=x_trail[-2], ay=y_trail[-2],
                xref="x", yref="y",
                axref="x", ayref="y",
                showarrow=True,
                arrowhead=2,
                arrowsize=1.5,
                arrowwidth=2,
                arrowcolor=color,
            ))

    # ── Centre-line cross ─────────────────────────────────────────────────────
    shapes.extend([
        dict(type="line", xref="x", yref="paper",
             x0=100, x1=100, y0=0, y1=1,
             line=dict(color="rgba(255,255,255,0.6)", width=1.5, dash="dash")),
        dict(type="line", xref="paper", yref="y",
             x0=0, x1=1, y0=0, y1=0,
             line=dict(color="rgba(255,255,255,0.6)", width=1.5, dash="dash")),
    ])

    # ── Layout ────────────────────────────────────────────────────────────────
    fig.update_layout(
        template=template,
        paper_bgcolor=paper_bg,
        plot_bgcolor=plot_bg,
        height=700,
        margin=dict(l=60, r=180, t=60, b=60),
        title=dict(
            text="<b>Relative Rotation Graph (RRG)</b> — Indian Sectors vs Nifty 50",
            font=dict(size=18, color=text_color),
            x=0.01,
        ),
        xaxis=dict(
            title="← Lagging  |  RS-Ratio  |  Leading →",
            titlefont=dict(color=axis_color, size=12),
            tickfont=dict(color=axis_color),
            gridcolor=grid_color,
            zerolinecolor=grid_color,
            showgrid=True,
        ),
        yaxis=dict(
            title="↑ Rising Momentum  |  RS-Momentum  |  Falling Momentum ↓",
            titlefont=dict(color=axis_color, size=12),
            tickfont=dict(color=axis_color),
            gridcolor=grid_color,
            zerolinecolor=grid_color,
            showgrid=True,
        ),
        legend=dict(
            orientation="v",
            x=1.01, y=1,
            bgcolor="rgba(0,0,0,0.3)" if dark_mode else "rgba(255,255,255,0.8)",
            bordercolor="rgba(255,255,255,0.2)",
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
            "Sector":        sector,
            "RS-Ratio":      round(data["rs_ratio_current"], 3),
            "RS-Momentum":   round(data["rs_momentum_current"], 3),
            "Quadrant":      data["quadrant"],
            "Rotation":      data["rotation_dir"],
            "1D Δ Ratio":    round(data["chg_1d_ratio"], 3) if not np.isnan(data["chg_1d_ratio"]) else "–",
            "5D Δ Ratio":    round(data["chg_5d_ratio"], 3) if not np.isnan(data["chg_5d_ratio"]) else "–",
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # Sort by quadrant priority then RS-Ratio descending
    order = {"Leading": 0, "Improving": 1, "Weakening": 2, "Lagging": 3}
    df["_sort"] = df["Quadrant"].map(order)
    df.sort_values(["_sort", "RS-Ratio"], ascending=[True, False], inplace=True)
    df.drop(columns="_sort", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df

def style_table(df: pd.DataFrame) -> pd.io.formats.style.Styler:
    """Apply quadrant-based row colors."""
    color_map = {
        "Leading":   "background-color: rgba(0,200,81,0.18); color: #00C851",
        "Weakening": "background-color: rgba(255,136,0,0.18); color: #FF8800",
        "Lagging":   "background-color: rgba(255,68,68,0.18); color: #FF4444",
        "Improving": "background-color: rgba(51,181,229,0.18); color: #33B5E5",
    }

    def row_style(row):
        q = row.get("Quadrant", "")
        style = color_map.get(q, "")
        return [style] * len(row)

    return df.style.apply(row_style, axis=1).format(precision=3)

# ── Main App ──────────────────────────────────────────────────────────────────
def main():
    # ── Header ────────────────────────────────────────────────────────────────
    st.markdown(
        """
        <h1 style='margin-bottom:0'>📈 Real-Time Indian Market Sector Rotation</h1>
        <h3 style='color:#aaa; margin-top:4px'>
            Relative Rotation Graph (RRG) — Live RS &amp; Momentum vs Nifty&nbsp;50
        </h3>
        """,
        unsafe_allow_html=True,
    )

    # ── Market Status Bar ──────────────────────────────────────────────────────
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

    # ── Sidebar Controls ───────────────────────────────────────────────────────
    with st.sidebar:
        st.image(
            "https://upload.wikimedia.org/wikipedia/commons/thumb/2/29/"
            "NSE_Logo.svg/320px-NSE_Logo.svg.png",
            width=140,
        )
        st.markdown("## ⚙️ Settings")

        lookback_days = st.slider(
            "Lookback Window (days)",
            min_value=90, max_value=365, value=252, step=10,
            help="Historical price data to fetch."
        )
        momentum_period = st.slider(
            "Momentum Period (bars)",
            min_value=5, max_value=26, value=10, step=1,
            help="Rate-of-change period for RS-Momentum (Y-axis). Default = 10."
        )
        trail_points = st.slider(
            "Trail Length (points)",
            min_value=5, max_value=40, value=20, step=5,
            help="Number of past positions shown as trail per sector."
        )
        dark_mode = st.toggle("🌙 Dark Theme", value=True)

        st.markdown("---")
        st.markdown("### 🏭 Sector Filter")
        all_sector_names = list(SECTORS.keys())
        selected_sectors = st.multiselect(
            "Select sectors to display:",
            options=all_sector_names,
            default=all_sector_names,
        )
        if not selected_sectors:
            st.warning("Select at least one sector.")
            selected_sectors = all_sector_names

        st.markdown("---")
        auto_refresh = st.checkbox(
            "⏱ Auto-Refresh (60s, market hours only)",
            value=False
        )

        st.markdown("---")
        st.markdown(
            """
            **Data Source:** Yahoo Finance (yfinance)  
            **Benchmark:** Nifty 50 (^NSEI)  
            **Delay:** ~15 min  
            **Update:** Every 60s during market hours  
            """,
            unsafe_allow_html=False,
        )

    # ── Auto-refresh logic ─────────────────────────────────────────────────────
    if auto_refresh and is_open:
        import time
        time.sleep(60)
        st.cache_data.clear()
        st.rerun()

    if refresh_btn:
        st.cache_data.clear()
        st.rerun()

    # ── Fetch Data ─────────────────────────────────────────────────────────────
    with st.spinner("⏳ Fetching market data from Yahoo Finance…"):
        price_df, failed_tickers = fetch_data(lookback_days=lookback_days + 60)

    if price_df.empty:
        st.error(
            "❌ Could not download any market data. "
            "Please check your internet connection and try again."
        )
        return

    if failed_tickers:
        st.warning(
            f"⚠️ Could not load data for: **{', '.join(failed_tickers)}**  "
            f"(ticker may be delisted or temporarily unavailable — skipped)."
        )

    if BENCHMARK_NAME not in price_df.columns:
        st.error(f"❌ Benchmark ({BENCHMARK_NAME}) data unavailable. Cannot draw RRG.")
        return

    # Keep only requested lookback
    cutoff = price_df.index[-1] - pd.Timedelta(days=lookback_days)
    price_df = price_df[price_df.index >= cutoff]

    # ── Compute RRG ────────────────────────────────────────────────────────────
    with st.spinner("🔢 Computing Relative Strength & Momentum…"):
        rrg_data = calculate_rrg(
            price_df,
            momentum_period=momentum_period,
            trail_points=trail_points,
        )

    if not rrg_data:
        st.error("❌ RRG calculation failed — insufficient overlapping data.")
        return

    # ── RRG Chart ──────────────────────────────────────────────────────────────
    fig = build_rrg_chart(rrg_data, selected_sectors, dark_mode=dark_mode)
    st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True})

    # ── Quadrant Summary KPI Row ───────────────────────────────────────────────
    st.markdown("### 📊 Quadrant Summary")
    q_counts = {"Leading": 0, "Improving": 0, "Weakening": 0, "Lagging": 0}
    for s, d in rrg_data.items():
        if s in selected_sectors and d["quadrant"] in q_counts:
            q_counts[d["quadrant"]] += 1

    k1, k2, k3, k4 = st.columns(4)
    kpi_style = "font-size:28px; font-weight:700"
    k1.metric("🟢 Leading",   q_counts["Leading"],   delta=None)
    k2.metric("🔵 Improving", q_counts["Improving"], delta=None)
    k3.metric("🟠 Weakening", q_counts["Weakening"], delta=None)
    k4.metric("🔴 Lagging",   q_counts["Lagging"],   delta=None)

    # ── Data Table ─────────────────────────────────────────────────────────────
    st.markdown("### 📋 Sector RRG Data Table")
    summary_df = build_summary_df(rrg_data, selected_sectors)

    if not summary_df.empty:
        styled = style_table(summary_df)
        st.dataframe(styled, use_container_width=True, height=min(600, 50 + len(summary_df) * 38))

        # ── CSV Export ────────────────────────────────────────────────────────
        csv_buf = io.StringIO()
        summary_df.to_csv(csv_buf, index=False)
        st.download_button(
            label="⬇️ Export RRG Data (CSV)",
            data=csv_buf.getvalue(),
            file_name=f"rrg_data_{datetime.now(IST).strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            use_container_width=False,
        )
    else:
        st.info("No sector data to display for the selected filters.")

    # ── How to Read ────────────────────────────────────────────────────────────
    with st.expander("📖 How to Read the Relative Rotation Graph (RRG)", expanded=False):
        st.markdown(
            """
            ## Understanding the RRG

            A **Relative Rotation Graph (RRG)** plots sectors (or stocks) on two axes derived
            from their performance *relative to a benchmark* (here, Nifty 50):

            | Axis | Meaning |
            |------|---------|
            | **X-axis — RS-Ratio** | Measures whether a sector is outperforming (>100) or underperforming (<100) the benchmark. Higher = stronger relative performance. |
            | **Y-axis — RS-Momentum** | Measures whether the relative strength is *improving* (>0) or *deteriorating* (<0). |

            ---

            ### The Four Quadrants

            | Quadrant | X | Y | Meaning |
            |----------|---|---|---------|
            | 🟢 **Leading** | >100 | >0 | Outperforming AND momentum still rising. **Most bullish.** |
            | 🟠 **Weakening** | >100 | <0 | Outperforming BUT momentum starting to fade. Consider reducing. |
            | 🔴 **Lagging** | <100 | <0 | Underperforming AND momentum falling. **Most bearish.** |
            | 🔵 **Improving** | <100 | >0 | Underperforming BUT momentum starting to recover. Early entry opportunity. |

            ---

            ### Clockwise Rotation (The Normal Cycle)

            Sectors typically rotate **clockwise** through the quadrants:

            ```
            Improving → Leading → Weakening → Lagging → Improving …
            ```

            A sector entering **Improving** with rising momentum may soon enter **Leading** —
            a potential early-entry signal. A sector in **Weakening** may soon enter **Lagging** —
            a potential exit signal.

            ---

            ### Trail Lines

            The dotted trail shows each sector's *path* over the last N periods (configurable in
            the sidebar). **The direction and curvature of the trail** tells you where the sector
            is heading — look for sectors making a **clockwise turn upward** from Lagging or
            Improving.

            ---

            ### ⚠️ Disclaimer

            This tool is for **educational and research purposes only** and does **not** constitute
            investment advice. Always do your own due diligence before making any investment decisions.
            """,
            unsafe_allow_html=False,
        )

    # ── Price Chart ────────────────────────────────────────────────────────────
    with st.expander("📉 Underlying Price Performance (Normalised)", expanded=False):
        norm_df = price_df[
            [BENCHMARK_NAME] +
            [s for s in selected_sectors if s in price_df.columns]
        ].copy()
        norm_df = norm_df.dropna(how="all")
        norm_df = (norm_df / norm_df.iloc[0]) * 100

        fig_px = go.Figure()
        ci = 0
        for col in norm_df.columns:
            color = "white" if col == BENCHMARK_NAME else SECTOR_COLORS[ci % len(SECTOR_COLORS)]
            width = 2.5   if col == BENCHMARK_NAME else 1.2
            dash  = "solid" if col == BENCHMARK_NAME else "solid"
            fig_px.add_trace(go.Scatter(
                x=norm_df.index, y=norm_df[col],
                name=col,
                line=dict(color=color, width=width, dash=dash),
                mode="lines",
            ))
            if col != BENCHMARK_NAME:
                ci += 1

        fig_px.update_layout(
            template="plotly_dark" if dark_mode else "plotly_white",
            height=400,
            title="Normalised Close Price (base=100 at start of window)",
            xaxis_title="Date",
            yaxis_title="Indexed Value (100 = start)",
            hovermode="x unified",
            legend=dict(orientation="h", y=-0.25),
        )
        st.plotly_chart(fig_px, use_container_width=True)

    # ── Footer ─────────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align:center; color:#777; font-size:12px'>
        Data via Yahoo Finance (yfinance) · ~15-min delayed · 
        RRG methodology: JdK RS-Ratio approximation ·  
        Built with Streamlit + Plotly · For educational use only
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
