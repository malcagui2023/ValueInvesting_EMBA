import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt

# --- Page Config ---
st.set_page_config(page_title="Value Investing Checklist", layout="wide")

# --- CSS for Font Size ---
st.markdown("""
    <style>
    .checklist-row {
        font-size: 1.1em;
    }
    </style>
""", unsafe_allow_html=True)

# --- App Title ---
st.title("📊 Active Value Investor – Checklist App")

# --- Input Section ---
ticker = st.text_input("Enter Ticker Symbol (e.g., AAPL, NVDA)", value="AAPL")
period = st.selectbox("Select time range:", ["1y", "3y", "5y", "10y"], index=3)

if ticker:
    try:
        stock = yf.Ticker(ticker)
        info = stock.info or {}
        hist = stock.history(period=period)
        financials = stock.financials if stock.financials is not None else pd.DataFrame()
        balance = stock.balance_sheet if stock.balance_sheet is not None else pd.DataFrame()
        cashflow = stock.cashflow if stock.cashflow is not None else pd.DataFrame()

        st.success(f"Data loaded for {info.get('shortName', ticker)}")

        # --- Price Chart ---
        st.markdown("---")
        st.subheader("📉 Price Chart")

        fig, ax = plt.subplots(figsize=(10, 4))
        hist_downsampled = hist["Close"].resample("M").last()
        ax.plot(hist_downsampled.index, hist_downsampled.values, label="Price", color="blue")
        ax.set_title(f"{ticker} Stock Price (Monthly)", fontsize=14)
        ax.set_ylabel("Price (USD)")
        ax.grid(True)
        plt.xticks(rotation=45)
        st.pyplot(fig)

        # --- Checklist Logic ---
        def safe_ratio(numerator, denominator):
            try:
                return round(numerator / denominator, 2) if denominator != 0 else None
            except:
                return None

        results = []
        trend_data = []

        # 1. ROE > 12%
        roe = info.get("returnOnEquity", None)
        results.append(("Return on Equity > 12%", roe, roe is not None and roe > 0.12, None))

        # 2. ROA > 12%
        roa = info.get("returnOnAssets", None)
        results.append(("Return on Assets > 12%", roa, roa is not None and roa > 0.12, None))

        # 3. EPS Trend Positive
        eps_hist = stock.earnings
        if eps_hist is not None and not eps_hist.empty and "Earnings" in eps_hist:
            eps_growth = eps_hist["Earnings"].pct_change().mean()
            results.append(("EPS Trend Positive", eps_growth, eps_growth is not None and eps_growth > 0, eps_hist["Earnings"]))
        else:
            results.append(("EPS Trend Positive", None, None, None))

        # 4. Net Margin > 20%
        net_margin = info.get("netMargins", None)
        results.append(("Net Margin > 20%", net_margin, net_margin is not None and net_margin > 0.20, None))

        # 5. Gross Margin > 40%
        gross_margin = info.get("grossMargins", None)
        results.append(("Gross Margin > 40%", gross_margin, gross_margin is not None and gross_margin > 0.40, None))

        # 6. LT Debt < 5x Net Income
        try:
            debt = balance.loc["Long Term Debt"].iloc[0] if not balance.empty else None
            net_income = financials.loc["Net Income"].iloc[0] if not financials.empty else None
            debt_ratio = safe_ratio(debt, net_income)
            results.append(("LT Debt < 5x Net Income", debt_ratio, debt_ratio is not None and debt_ratio < 5, None))
        except:
            results.append(("LT Debt < 5x Net Income", None, None, None))

        # 7. Return on Retained Capital (Manual)
        results.append(("Return on Retained Capital > 18%", "⚠️", None, None))

        # 8. Dividends/Buybacks
        dividends = stock.dividends
        dividend_consistent = not dividends.empty and dividends.min() > 0
        results.append(("Dividend History (No Cuts)", "Yes" if dividend_consistent else "No", dividend_consistent, dividends if not dividends.empty else None))

        # --- Display Results ---
        st.markdown("---")
        st.subheader("📋 Checklist Results")

        score = 0
        total = len(results)

        for label, value, passed, trend in results:
            col1, col2, col3, col4 = st.columns([2, 1.5, 1, 2])
            col1.markdown(f"<div class='checklist-row'>{label}</div>", unsafe_allow_html=True)
            col2.markdown(f"<div class='checklist-row'>{value if value is not None else '—'}</div>", unsafe_allow_html=True)
            if passed is True:
                col3.success("✅")
                score += 1
            elif passed is False:
                col3.error("❌")
            else:
                col3.warning("⚠️")
            if trend is not None and isinstance(trend, pd.Series):
                col4.line_chart(trend)
            else:
                col4.write("—")

        st.markdown(f"### Final Score: **{score}/{total}**")

        if score >= 10:
            st.success("🟢 Strong Candidate")
        elif score >= 7:
            st.warning("🟡 Watchlist")
        else:
            st.error("🔴 Avoid")

        # --- Manual Review Reminders ---
        st.markdown("---")
        st.subheader("📌 Remember to Review Manually")
        st.info("""
        - Organized Labor
        - Pricing Power
        - Barriers to Entry
        """)

    except Exception as e:
        st.error(f"Error fetching data: {e}")
