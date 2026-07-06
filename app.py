"""
app.py  –  Streamlit Trading Dashboard
=======================================
MACD + 200-day MA + Support/Resistance Signal System

Reads tickers from Tickers.txt (one per line).
Fetches OHLCV data via yfinance, runs indicators, and renders:
  • Candlestick + MA200 + S/R levels chart
  • MACD sub-chart
  • Signal summary table across all tickers
"""

import ast
import os
import time

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from plotly.subplots import make_subplots

from indicators import generate_signals

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Trading Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────

st.markdown(
    """
    <style>
    /* Dark card styling for metrics */
    [data-testid="metric-container"] {
        background-color: #1e2130;
        border: 1px solid #2d3250;
        border-radius: 8px;
        padding: 12px 18px;
    }
    /* Signal badge colours */
    .buy-badge  { background:#0d6e3f; color:#fff; padding:3px 10px; border-radius:12px; font-weight:600; }
    .sell-badge { background:#8b1a1a; color:#fff; padding:3px 10px; border-radius:12px; font-weight:600; }
    .hold-badge { background:#3d4167; color:#fff; padding:3px 10px; border-radius:12px; font-weight:600; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

TICKER_FILE = "Tickers.txt"
PERIODS     = ["3mo", "6mo", "1y", "2y", "5y"]
INTERVALS   = ["1d", "1wk"]


@st.cache_data(ttl=900)   # cache 15 min
def load_ticker_data(ticker: str, period: str, interval: str) -> pd.DataFrame | None:
    """Download OHLCV and compute all indicators. Returns None on failure."""
    try:
        raw = yf.download(ticker, period=period, interval=interval, auto_adjust=True, progress=False)
        if raw.empty or len(raw) < 30:
            return None
        # yfinance sometimes returns MultiIndex columns
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)
        df = raw[["Open", "High", "Low", "Close", "Volume"]].copy()
        df.dropna(inplace=True)
        df, sr = generate_signals(df)
        df.attrs["sr"] = sr        # stash S/R dict on the dataframe
        return df
    except Exception as exc:
        st.warning(f"Could not load **{ticker}**: {exc}")
        return None


def read_tickers() -> list[str]:
    """Read Tickers.txt, skipping blank lines and #-comments."""
    if not os.path.exists(TICKER_FILE):
        return []
    with open(TICKER_FILE) as fh:
        lines = [l.strip().upper() for l in fh if l.strip() and not l.startswith("#")]
    return lines


def badge_html(signal: str) -> str:
    cls = {"BUY": "buy-badge", "SELL": "sell-badge"}.get(signal, "hold-badge")
    return f'<span class="{cls}">{signal}</span>'


def score_delta_color(score: int) -> str:
    if score >= 2:
        return "normal"   # green arrow
    elif score <= -2:
        return "inverse"  # red arrow
    return "off"          # grey


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("⚙️ Settings")

    period   = st.selectbox("Lookback Period", PERIODS, index=2)
    interval = st.selectbox("Candle Interval", INTERVALS, index=0)
    ma_color = st.color_picker("MA 200 Line Colour", "#f0c040")
    show_vol = st.checkbox("Show Volume bars", value=True)

    st.divider()
    st.subheader("📋 Ticker List")

    tickers_from_file = read_tickers()

    if tickers_from_file:
        raw_text = "\n".join(tickers_from_file)
    else:
        raw_text = "AAPL\nMSFT\nTSLA\nNVDA\nSPY"

    ticker_input = st.text_area(
        "Edit tickers (one per line):",
        value=raw_text,
        height=200,
        help="These override Tickers.txt for this session.",
    )

    if st.button("💾 Save to Tickers.txt"):
        with open(TICKER_FILE, "w") as fh:
            fh.write(ticker_input.strip())
        st.success("Saved!")
        st.cache_data.clear()

    tickers = [t.strip().upper() for t in ticker_input.splitlines() if t.strip()]

    st.divider()
    st.caption("Data via yfinance · Cached 15 min")

# ── Main area ─────────────────────────────────────────────────────────────────

st.title("📈 MACD + MA200 + S/R Trading Dashboard")
st.caption(f"Period: **{period}** · Interval: **{interval}** · {len(tickers)} tickers loaded")

if not tickers:
    st.warning("Add at least one ticker in the sidebar or in **Tickers.txt**.")
    st.stop()

# ── Tab layout ────────────────────────────────────────────────────────────────

tab_summary, tab_chart, tab_screener = st.tabs(
    ["📊 Signal Summary", "📉 Chart View", "🔍 Screener"]
)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Signal Summary
# ═══════════════════════════════════════════════════════════════════════════════

with tab_summary:
    st.subheader("Latest Signal per Ticker")

    summary_rows = []
    progress     = st.progress(0, text="Loading tickers…")

    for i, ticker in enumerate(tickers):
        progress.progress((i + 1) / len(tickers), text=f"Fetching {ticker}…")
        df = load_ticker_data(ticker, period, interval)
        if df is None or df.empty:
            continue

        last        = df.iloc[-1]
        close_price = float(last["Close"])
        ma200_price = float(last["ma200"])
        signal      = str(last["signal"])
        score       = int(last["signal_score"])
        pct_vs_ma   = (close_price / ma200_price - 1) * 100

        # parse S/R lists
        sr = df.attrs.get("sr", {})
        support_levels    = sr.get("support",    [])
        resistance_levels = sr.get("resistance", [])

        nearest_sup = max((s for s in support_levels if s < close_price), default=None)
        nearest_res = min((r for r in resistance_levels if r > close_price), default=None)

        summary_rows.append({
            "Ticker":        ticker,
            "Close":         close_price,
            "MA200":         ma200_price,
            "vs MA200 (%)":  round(pct_vs_ma, 2),
            "Signal":        signal,
            "Score":         score,
            "Nearest Sup":   nearest_sup,
            "Nearest Res":   nearest_res,
        })

    progress.empty()

    if not summary_rows:
        st.error("No data returned for any ticker. Check your ticker list.")
        st.stop()

    df_summary = pd.DataFrame(summary_rows)

    # Colour-coded signal column
    def _colour_signal(val):
        colours = {"BUY": "background-color:#0d6e3f;color:#fff",
                   "SELL": "background-color:#8b1a1a;color:#fff",
                   "HOLD": "background-color:#3d4167;color:#fff"}
        return colours.get(val, "")

    def _colour_score(val):
        if val >= 2:
            return "color:#2ecc71;font-weight:600"
        elif val <= -2:
            return "color:#e74c3c;font-weight:600"
        return "color:#aaa"

    styled = (
        df_summary.style
        .map(_colour_signal, subset=["Signal"])
        .map(_colour_score,  subset=["Score"])
        .format({
            "Close":        "${:.2f}",
            "MA200":        "${:.2f}",
            "vs MA200 (%)": "{:+.2f}%",
            "Nearest Sup":  lambda x: f"${x:.2f}" if x else "—",
            "Nearest Res":  lambda x: f"${x:.2f}" if x else "—",
        })
        .set_table_styles([{"selector": "th", "props": "text-align:center;"}])
    )

    st.dataframe(styled, use_container_width=True, height=450)

    # KPI row
    buys  = (df_summary["Signal"] == "BUY").sum()
    sells = (df_summary["Signal"] == "SELL").sum()
    holds = (df_summary["Signal"] == "HOLD").sum()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🟢 BUY",  buys)
    c2.metric("🔴 SELL", sells)
    c3.metric("⚪ HOLD", holds)
    c4.metric("📦 Total", len(summary_rows))

    # Download CSV
    csv = df_summary.to_csv(index=False)
    st.download_button("⬇️ Download Summary CSV", csv, "signal_summary.csv", "text/csv")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Chart View
# ═══════════════════════════════════════════════════════════════════════════════

with tab_chart:
    col_pick, col_refresh = st.columns([4, 1])
    with col_pick:
        selected = st.selectbox("Select Ticker to Chart", tickers)
    with col_refresh:
        st.write("")
        if st.button("🔄 Refresh"):
            st.cache_data.clear()
            st.rerun()

    df = load_ticker_data(selected, period, interval)

    if df is None or df.empty:
        st.error(f"No data for {selected}.")
        st.stop()

    sr = df.attrs.get("sr", {})
    last_row = df.iloc[-1]
    last_signal = str(last_row["signal"])
    last_score  = int(last_row["signal_score"])
    last_close  = float(last_row["Close"])
    last_ma200  = float(last_row["ma200"])

    # Metric row
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Close",  f"${last_close:.2f}")
    m2.metric("MA 200", f"${last_ma200:.2f}", f"{(last_close/last_ma200-1)*100:+.1f}%",
              delta_color=score_delta_color(last_score))
    m3.metric("Signal Score", f"{last_score:+d}/3",
              delta_color=score_delta_color(last_score))
    m4.metric("Signal", last_signal)

    # ── Build Plotly figure ──────────────────────────────────────────────────

    row_heights = [0.55, 0.20, 0.25] if show_vol else [0.65, 0.35]
    rows        = 3 if show_vol else 2
    subplot_titles = (
        [f"{selected} Price + MA200 + S/R", "Volume", "MACD"]
        if show_vol else
        [f"{selected} Price + MA200 + S/R", "MACD"]
    )

    fig = make_subplots(
        rows=rows,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=row_heights,
        subplot_titles=subplot_titles,
    )

    # Candlestick
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            name="Price",
            increasing_line_color="#26a69a",
            decreasing_line_color="#ef5350",
        ),
        row=1, col=1,
    )

    # MA 200
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["ma200"],
            name="MA 200",
            line=dict(color=ma_color, width=1.8, dash="dot"),
        ),
        row=1, col=1,
    )

    # Support levels
    for level in sr.get("support", []):
        fig.add_hline(
            y=level,
            line_dash="dash",
            line_color="#2ecc71",
            line_width=1,
            annotation_text=f"Sup {level:.2f}",
            annotation_font_size=10,
            annotation_font_color="#2ecc71",
            row=1, col=1,
        )

    # Resistance levels
    for level in sr.get("resistance", []):
        fig.add_hline(
            y=level,
            line_dash="dash",
            line_color="#e74c3c",
            line_width=1,
            annotation_text=f"Res {level:.2f}",
            annotation_font_size=10,
            annotation_font_color="#e74c3c",
            row=1, col=1,
        )

    # Volume
    if show_vol:
        vol_colors = [
            "#26a69a" if c >= o else "#ef5350"
            for c, o in zip(df["Close"], df["Open"])
        ]
        fig.add_trace(
            go.Bar(
                x=df.index,
                y=df["Volume"],
                name="Volume",
                marker_color=vol_colors,
                opacity=0.7,
            ),
            row=2, col=1,
        )

    macd_row = 3 if show_vol else 2

    # MACD histogram
    hist_colors = [
        "#26a69a" if v >= 0 else "#ef5350"
        for v in df["macd_hist"]
    ]
    fig.add_trace(
        go.Bar(
            x=df.index,
            y=df["macd_hist"],
            name="Histogram",
            marker_color=hist_colors,
            opacity=0.7,
        ),
        row=macd_row, col=1,
    )

    # MACD line + signal line
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["macd"],
            name="MACD",
            line=dict(color="#2196f3", width=1.5),
        ),
        row=macd_row, col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["macd_signal"],
            name="Signal",
            line=dict(color="#ff9800", width=1.5),
        ),
        row=macd_row, col=1,
    )

    # Mark BUY / SELL crossover dots on price chart
    buy_mask  = df["signal"] == "BUY"
    sell_mask = df["signal"] == "SELL"

    fig.add_trace(
        go.Scatter(
            x=df.index[buy_mask],
            y=df["Low"][buy_mask] * 0.995,
            mode="markers",
            marker=dict(symbol="triangle-up", size=9, color="#2ecc71"),
            name="BUY Signal",
        ),
        row=1, col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=df.index[sell_mask],
            y=df["High"][sell_mask] * 1.005,
            mode="markers",
            marker=dict(symbol="triangle-down", size=9, color="#e74c3c"),
            name="SELL Signal",
        ),
        row=1, col=1,
    )

    # Layout
    fig.update_layout(
        height=720,
        template="plotly_dark",
        paper_bgcolor="#0e1117",
        plot_bgcolor="#0e1117",
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1),
        margin=dict(l=0, r=0, t=40, b=0),
    )
    fig.update_yaxes(showgrid=True, gridcolor="#1e2130")
    fig.update_xaxes(showgrid=False)

    st.plotly_chart(fig, use_container_width=True)

    # S/R level display
    with st.expander("📐 Support & Resistance Levels", expanded=False):
        sc1, sc2 = st.columns(2)
        with sc1:
            st.markdown("**🟢 Support**")
            for s in sr.get("support", []):
                diff = (last_close / s - 1) * 100
                st.write(f"${s:.2f}  *(−{diff:.1f}% from close)*")
        with sc2:
            st.markdown("**🔴 Resistance**")
            for r in sr.get("resistance", []):
                diff = (r / last_close - 1) * 100
                st.write(f"${r:.2f}  *(+{diff:.1f}% to close)*")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Screener
# ═══════════════════════════════════════════════════════════════════════════════

with tab_screener:
    st.subheader("🔍 Multi-Ticker Screener")

    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        filter_signal = st.multiselect(
            "Filter by Signal", ["BUY", "SELL", "HOLD"],
            default=["BUY", "SELL"],
        )
    with col_f2:
        min_score = st.slider("Min |Score|", 0, 3, 2)
    with col_f3:
        above_ma = st.selectbox(
            "MA200 Filter", ["All", "Above MA200 only", "Below MA200 only"]
        )

    if "df_summary" not in dir():
        st.info("Run the **Signal Summary** tab first to populate screener data.")
    else:
        filtered = df_summary[df_summary["Signal"].isin(filter_signal)]
        filtered = filtered[filtered["Score"].abs() >= min_score]
        if above_ma == "Above MA200 only":
            filtered = filtered[filtered["vs MA200 (%)"] > 0]
        elif above_ma == "Below MA200 only":
            filtered = filtered[filtered["vs MA200 (%)"] < 0]

        st.write(f"**{len(filtered)}** tickers match your filter")

        if not filtered.empty:
            st.dataframe(
                filtered.style
                .map(_colour_signal, subset=["Signal"])
                .map(_colour_score,  subset=["Score"])
                .format({
                    "Close":        "${:.2f}",
                    "MA200":        "${:.2f}",
                    "vs MA200 (%)": "{:+.2f}%",
                    "Nearest Sup":  lambda x: f"${x:.2f}" if x else "—",
                    "Nearest Res":  lambda x: f"${x:.2f}" if x else "—",
                }),
                use_container_width=True,
                height=400,
            )
            csv2 = filtered.to_csv(index=False)
            st.download_button(
                "⬇️ Download Filtered CSV", csv2,
                "screener_results.csv", "text/csv",
            )
        else:
            st.info("No tickers match the selected filters.")

    # Quick chart from screener
    st.divider()
    st.markdown("**Quick Chart from Screener**")
    screener_pick = st.selectbox("Pick ticker to chart", tickers, key="screener_pick")
    if screener_pick:
        df_sc = load_ticker_data(screener_pick, period, interval)
        if df_sc is not None:
            mini_fig = go.Figure()
            mini_fig.add_trace(go.Scatter(
                x=df_sc.index, y=df_sc["Close"], name="Close",
                line=dict(color="#2196f3", width=1.5),
            ))
            mini_fig.add_trace(go.Scatter(
                x=df_sc.index, y=df_sc["ma200"], name="MA200",
                line=dict(color=ma_color, width=1.5, dash="dot"),
            ))
            mini_fig.update_layout(
                height=280, template="plotly_dark",
                paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
                margin=dict(l=0, r=0, t=20, b=0),
                legend=dict(orientation="h"),
            )
            st.plotly_chart(mini_fig, use_container_width=True)
