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
except:
    st.error("Tickers.txt not found. Please upload it to your Streamlit project.")
    st.stop()

# Now tickers exists — safe to use
st.sidebar.header("Loaded Tickers")
st.sidebar.write(tickers)
