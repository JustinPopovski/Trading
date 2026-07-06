import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(page_title="Trading Dashboard", layout="wide")
st.title("📈 MACD + 200-Day + Support/Resistance + Fibonacci Trading Dashboard")

# ─────────────────────────────────────────────
# Load tickers FIRST — before any loops
# ─────────────────────────────────────────────
file_path = "Tickers.txt"

try:
    with open(file_path, "r") as f:
        tickers = [line.strip().upper() for line in f if line.strip()]
except Exception as e:
    st.error(f"Tickers.txt not found or unreadable: {e}")
    st.stop()

if len(tickers) == 0:
    st.error("Tickers.txt is empty — add tickers (one per line).")
    st.stop()

st.sidebar.header("Loaded Tickers")
st.sidebar.write(tickers)

# ─────────────────────────────────────────────
# Indicator Functions
# ─────────────────────────────────────────────

def macd(df):
    df["EMA12"] = df["Close"].ewm(span=12).mean()
    df["EMA26"] = df["Close"].ewm(span=26).mean()
    df["MACD"] = df["EMA12"] - df["EMA26"]
    df["Signal"] = df["MACD"].ewm(span=9).mean()
    df["Hist"] = df["MACD"] - df["Signal"]
    return df

def trend_filter(df):
    df["SMA200"] = df["Close"].rolling(200).mean()
    df["Trend"] = np.where(df["Close"] > df["SMA200"], "Bull", "Bear")
    return df

def pivots(df, left=5, right=5):
    df["Support"] = df["Low"].shift(left).rolling(left+right+1).min()
    df["Resistance"] = df["High"].shift(left).rolling(left+right+1).max()
    return df

def generate_signals(df):
    df["TouchSupport"] = df["Low"] <= df["Support"]
    df["TouchResistance"] = df["High"] >= df["Resistance"]

    df["BullMACD"] = (df["MACD"] > df["Signal"]) & (df["Hist"] > 0)
    df["BearMACD"] = (df["MACD"] < df["Signal"]) & (df["Hist"] < 0)

    df["BUY"] = (df["Trend"] == "Bull") & df["TouchSupport"] & df["BullMACD"]
    df["SELL"] = (df["Trend"] == "Bear") & df["TouchResistance"] & df["BearMACD"]

    return df

# ─────────────────────────────────────────────
# Fibonacci Levels
# ─────────────────────────────────────────────
def fibonacci_levels(df, lookback=60):
    if len(df) < lookback:
        lookback = len(df)

    swing_high = df["High"].rolling(lookback).max().iloc[-1]
    swing_low = df["Low"].rolling(lookback).min().iloc[-1]
    diff = swing_high - swing_low

    levels = {
        "0% (Low)": swing_low,
        "23.6%": swing_high - 0.236 * diff,
        "38.2%": swing_high - 0.382 * diff,
        "50%": swing_high - 0.5 * diff,
        "61.8%": swing_high - 0.618 * diff,
        "78.6%": swing_high - 0.786 * diff,
        "100% (High)": swing_high
    }

    return levels

# ─────────────────────────────────────────────
# Main Dashboard Logic
# ─────────────────────────────────────────────

results = []

for ticker in tickers:
    st.write(f"🔄 Downloading: {ticker}")

    df = yf.download(ticker, period="1y")

    # ─────────────────────────────────────────────
    # STRONG SAFETY CHECKS — prevents ALL crashes
    # ─────────────────────────────────────────────

    # 1. DataFrame must not be empty
    if df.empty:
        st.warning(f"⚠️ No data returned for {ticker}. Skipping.")
        continue

    # 2. Must contain required OHLC columns
    required_cols = {"Close", "High", "Low"}
    if not required_cols.issubset(df.columns):
        st.warning(f"⚠️ Missing required price data for {ticker}. Skipping.")
        continue

    # 3. Close column must contain real numeric values
    if df["Close"].dropna().empty:
        st.warning(f"⚠️ Close prices are all NaN for {ticker}. Skipping.")
        continue

    # 4. Ensure High/Low also contain numeric values
    if df["High"].dropna().empty or df["Low"].dropna().empty:
        st.warning(f"⚠️ High/Low prices invalid for {ticker}. Skipping.")
        continue

    # ─────────────────────────────────────────────
    # Indicators (safe to run now)
    # ─────────────────────────────────────────────
    df = macd(df)
    df = trend_filter(df)
    df = pivots(df)
    df = generate_signals(df)

    fib = fibonacci_levels(df)
    last = df.iloc[-1]

    results.append({
        "Ticker": ticker,
        "Price": round(last["Close"], 2),
        "Trend": last["Trend"],
        "MACD": round(last["MACD"], 3),
        "Signal": round(last["Signal"], 3),
        "Hist": round(last["Hist"], 3),
        "BUY": bool(last["BUY"]),
        "SELL": bool(last["SELL"]),
        "Fib 38.2%": round(fib["38.2%"], 2),
        "Fib 50%": round(fib["50%"], 2),
        "Fib 61.8%": round(fib["61.8%"], 2)
    })

# Display main signal table
st.subheader("📊 Trading Signals")
if len(results) == 0:
    st.error("No valid tickers returned data. Check Tickers.txt.")
else:
    st.dataframe(pd.DataFrame(results))

# ─────────────────────────────────────────────
# Display Fibonacci Tables
# ─────────────────────────────────────────────
st.subheader("📐 Fibonacci Retracement Levels")

for ticker in tickers:
    df = yf.download(ticker, period="1y")

    if df.empty:
        continue

    fib = fibonacci_levels(df)
    st.write(f"### {ticker}")
    st.table(pd.DataFrame.from_dict(fib, orient="index", columns=["Price"]))
