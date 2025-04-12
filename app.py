import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO

# App setup
st.set_page_config(page_title="Value Investing Checklist", layout="wide")
st.title("📊 Value Investing Checklist")

ticker = st.text_input("Enter Ticker Symbol (e.g., AAPL, NVDA)", value="AAPL")
period = st.selectbox("Select time range", ["10y", "5y"], index=0)

@st.cache_data
def get_data(ticker, period):
    stock = yf.Ticker(ticker)
    info = stock.info or {}
    hist = stock.history(period=period)
    fin = stock.financials if stock.financials is not None else pd.DataFrame()
    bal = stock.balance_sheet if stock.balance_sheet is not None else pd.DataFrame()
    cf = stock.cashflow if stock.cashflow is not None else pd.DataFrame()
    earnings = stock.earnings
    dividends = stock.dividends
    return stock, info, hist, fin, bal, cf, earnings, dividends

def safe_ratio(a, b):
    try:
        return round(a / b, 2) if b else None
    except: return None

if ticker:
    try:
        stock, info, hist, fin, bal, cf, earnings, dividends = get_data(ticker, period)

        st.subheader("📈 Price History")
        fig, ax = plt.subplots(figsize=(10, 3))
        hist["Close"].resample("M").last().plot(ax=ax)
        ax.set_title(f"{ticker} Monthly Closing Prices")
        ax.set_ylabel("Price (USD)")
        ax.grid(True)
        st.pyplot(fig)

        st.markdown("---")
        st.subheader("✅ Checklist Results")

        results = []
        trends = {}

        # --- 1. ROE ---
        roe = info.get("returnOnEquity", None)
        results.append(("Return on Equity > 12%", roe, roe and roe > 0.12))
        # --- 2. ROA ---
        roa = info.get("returnOnAssets", None)
        results.append(("Return on Assets > 12%", roa, roa and roa > 0.12))
        # --- 3. EPS Growth ---
        if not earnings.empty:
            eps_growth = earnings["Earnings"].pct_change().mean()
            results.append(("EPS Trend Positive", eps_growth, eps_growth and eps_growth > 0))
            trends["EPS"] = earnings["Earnings"]
        else:
            results.append(("EPS Trend Positive", None, None))

        # --- 4. Net Margin ---
        net_margin = info.get("netMargins", None)
        results.append(("Net Margin > 20%", net_margin, net_margin and net_margin > 0.20))

        # --- 5. Gross Margin ---
        gross_margin = info.get("grossMargins", None)
        results.append(("Gross Margin > 40%", gross_margin, gross_margin and gross_margin > 0.40))

        # --- 6. LT Debt to Net Earnings ---
        try:
            debt = bal.loc["Long Term Debt"].iloc[0] if not bal.empty else None
            net_income = fin.loc["Net Income"].iloc[0] if not fin.empty else None
            ratio = safe_ratio(debt, net_income)
            results.append(("LT Debt < 5x Net Income", ratio, ratio and ratio < 5))
        except:
            results.append(("LT Debt < 5x Net Income", None, None))

        # --- 7. Return on Retained Capital (Manual Placeholder) ---
        results.append(("Return on Retained Capital > 18%", "⚠️", None))

        # --- 8. Dividend History ---
        if dividends.empty:
            results.append(("Dividend History", "No Dividends", True))
        else:
            years = dividends.index.year.unique().tolist()
            min_div = dividends.resample("Y").min()
            cuts = min_div[min_div == 0].count()
            cut_text = f"Cut in {cuts} year(s)" if cuts > 0 else "No Cuts"
            results.append(("Dividend History", f"{len(years)} years | {cut_text}", cuts == 0))

        # Score & Display
        score = sum(1 for _, _, passed in results if passed)
        total = len(results)
        for label, value, passed in results:
            col1, col2, col3 = st.columns([3, 2, 1])
            col1.write(label)
            col2.write(value if value is not None else "—")
            if passed is True: col3.success("✅")
            elif passed is False: col3.error("❌")
            else: col3.warning("⚠️")

        st.markdown(f"### Final Score: **{score}/{total}**")
        if score >= 10: st.success("🟢 Strong Candidate")
        elif score >= 7: st.warning("🟡 Watchlist")
        else: st.error("🔴 Avoid")
