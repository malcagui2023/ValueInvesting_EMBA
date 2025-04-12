import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="Value Investing Checklist", layout="wide")
st.title("📊 Active Value Investor – Checklist App")

ticker = st.text_input("Enter Ticker Symbol (e.g., AAPL, NVDA)", value="AAPL")

if ticker:
    try:
        stock = yf.Ticker(ticker)
        info = stock.info or {}
        hist = stock.history(period="10y")
        financials = stock.financials if stock.financials is not None else pd.DataFrame()
        balance = stock.balance_sheet if stock.balance_sheet is not None else pd.DataFrame()
        cashflow = stock.cashflow if stock.cashflow is not None else pd.DataFrame()

        st.success(f"Data loaded for {info.get('shortName', ticker)}")

        # Price chart
        st.line_chart(hist["Close"])

        def safe_ratio(numerator, denominator):
            try:
                return round(numerator / denominator, 2) if denominator != 0 else None
            except:
                return None

        results = []

        # 1. ROE > 12%
        roe = info.get("returnOnEquity", None)
        results.append(("Return on Equity > 12%", roe, roe is not None and roe > 0.12))

        # 2. ROA > 12%
        roa = info.get("returnOnAssets", None)
        results.append(("Return on Assets > 12%", roa, roa is not None and roa > 0.12))

        # 3. EPS Trend Positive
        eps_hist = stock.earnings
        if eps_hist is not None and not eps_hist.empty and "Earnings" in eps_hist:
            eps_growth = eps_hist["Earnings"].pct_change().mean()
            results.append(("EPS Trend Positive", eps_growth, eps_growth is not None and eps_growth > 0))
        else:
            results.append(("EPS Trend Positive", None, None))

        # 4. Net Margin > 20%
        net_margin = info.get("netMargins", None)
        results.append(("Net Margin > 20%", net_margin, net_margin is not None and net_margin > 0.20))

        # 5. Gross Margin > 40%
        gross_margin = info.get("grossMargins", None)
        results.append(("Gross Margin > 40%", gross_margin, gross_margin is not None and gross_margin > 0.40))

        # 6. LT Debt < 5x Net Income
        try:
            debt = balance.loc["Long Term Debt"].iloc[0] if not balance.empty else None
            net_income = financials.loc["Net Income"].iloc[0] if not financials.empty else None
            debt_ratio = safe_ratio(debt, net_income)
            results.append(("LT Debt < 5x Net Income", debt_ratio, debt_ratio is not None and debt_ratio < 5))
        except:
            results.append(("LT Debt < 5x Net Income", None, None))

        # 7. Organized Labor (Manual Input)
        results.append(("Organized Labor (Manual Input)", "⚠️", None))

        # 8. Pricing Power (Manual Input)
        results.append(("Pricing Power Matches Inflation", "⚠️", None))

        # 9. Return on Retained Capital (Advanced/Manual)
        results.append(("Return on Retained Capital > 18%", "⚠️", None))

        # 10. Dividends/Buybacks
        dividends = stock.dividends
        dividend_consistent = not dividends.empty and dividends.min() > 0
        results.append(("Dividend History (No Cuts)", "Yes" if dividend_consistent else "No", dividend_consistent))

        # 11. Barriers to Entry (Manual)
        results.append(("Barriers to Entry (Manual Input)", "⚠️", None))

        # --- Display Results ---
        st.subheader("Checklist Results")
        score = 0
        total = len(results)

        for label, value, passed in results:
            col1, col2, col3 = st.columns([3, 2, 1])
            col1.write(label)
            col2.write(value if value is not None else "—")
            if passed is True:
                col3.success("✅")
                score += 1
            elif passed is False:
                col3.error("❌")
            else:
                col3.warning("⚠️")

        st.markdown(f"### Final Score: **{score}/{total}**")

        if score >= 10:
            st.success("🟢 Strong Candidate")
        elif score >= 7:
            st.warning("🟡 Watchlist")
        else:
            st.error("🔴 Avoid")

    except Exception as e:
        st.error(f"Error fetching data: {e}")
