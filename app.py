for ticker in tickers:
    df = yf.download(ticker, period="1y")

    # Safety check
    if df.empty or "Close" not in df.columns:
        st.warning(f"⚠️ No data returned for {ticker}. Skipping.")
        continue

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
