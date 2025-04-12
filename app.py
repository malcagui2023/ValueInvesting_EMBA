import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO

st.set_page_config(page_title="Value Investing Checklist", layout="wide")
st.title("📊 Value Investing Checklist (Year-by-Year)")

ticker = st.text_input("Enter Ticker Symbol (e.g., AAPL, NVDA)", value="AAPL")
period = st.selectbox("Select analysis period", ["10y", "5y"], index=0)
period_years = 10 if period == "10y" else 5

@st.cache_data
def get_data(ticker):
    stock = yf.Ticker(ticker)
    info = stock.info or {}
    bs = stock.balance_sheet if stock.balance_sheet is not None else pd.DataFrame()
    fin = stock.financials if stock.financials is not None else pd.DataFrame()
    earnings = stock.earnings if stock.earnings is not None else pd.DataFrame()
    hist = stock.history(period="max")
    div = stock.dividends if stock.dividends is not None else pd.Series(dtype="float64")
    return info, bs, fin, earnings, hist, div

def check_all_years(metric_series, threshold, comparison='>'):
    checks = []
    for year, value in metric_series.items():
        if value is None:
            checks.append((year, value, None))
            continue
        if comparison == '>':
            checks.append((year, value, value > threshold))
        elif comparison == '<':
            checks.append((year, value, value < threshold))
    passed_all = all([c[2] for c in checks if c[2] is not None])
    return checks, passed_all

def safe_ratio(numerator, denominator):
    try:
        return numerator / denominator if denominator and denominator != 0 else None
    except:
        return None

if ticker:
    try:
        info, bs, fin, earnings, hist, div = get_data(ticker)

        st.subheader("📈 Price History")
        fig, ax = plt.subplots(figsize=(10, 3))
        hist["Close"].resample("M").last().plot(ax=ax)
        ax.set_title(f"{ticker} Monthly Closing Prices")
        ax.set_ylabel("Price (USD)")
        ax.grid(True)
        st.pyplot(fig)

        st.markdown("---")
        st.subheader("✅ Checklist Results (Must Pass Every Year)")

        results = []
        trend_tables = {}

        available_years = list(fin.columns.year)
        selected_years = sorted(available_years)[-period_years:]

        # ROE
        roe_series = {}
        for year in selected_years:
            try:
                net = fin[fin.columns[fin.columns.year == year]].loc["Net Income"].values[0]
                equity = bs[bs.columns[bs.columns.year == year]].loc["Total Stockholder Equity"].values[0]
                roe_series[year] = safe_ratio(net, equity)
            except:
                roe_series[year] = None
        roe_check, roe_pass = check_all_years(roe_series, 0.12)
        results.append(("ROE > 12%", roe_pass))
        trend_tables["ROE"] = roe_check

        # ROA
        roa_series = {}
        for year in selected_years:
            try:
                net = fin[fin.columns[fin.columns.year == year]].loc["Net Income"].values[0]
                assets = bs[bs.columns[bs.columns.year == year]].loc["Total Assets"].values[0]
                roa_series[year] = safe_ratio(net, assets)
            except:
                roa_series[year] = None
        roa_check, roa_pass = check_all_years(roa_series, 0.12)
        results.append(("ROA > 12%", roa_pass))
        trend_tables["ROA"] = roa_check

        # Net Margin
        net_margin_series = {}
        for year in selected_years:
            try:
                revenue = fin[fin.columns[fin.columns.year == year]].loc["Total Revenue"].values[0]
                net_income = fin[fin.columns[fin.columns.year == year]].loc["Net Income"].values[0]
                net_margin_series[year] = safe_ratio(net_income, revenue)
            except:
                net_margin_series[year] = None
        net_margin_check, net_margin_pass = check_all_years(net_margin_series, 0.20)
        results.append(("Net Margin > 20%", net_margin_pass))
        trend_tables["Net Margin"] = net_margin_check

        # EPS
        eps_check = []
        eps_pass = None
        if earnings is not None and not earnings.empty:
            eps = earnings["Earnings"]
            eps_diff = eps.diff().dropna()
            eps_pass = (eps_diff > 0).all()
            for year in eps.index[-period_years:]:
                val = eps.loc[year]
                eps_check.append((year, val, val > 0))
            results.append(("EPS Trend Upward", eps_pass))
            trend_tables["EPS"] = eps_check
        else:
            results.append(("EPS Trend Upward", None))

        # Show checklist summary
        for label, passed in results:
            col1, col2 = st.columns([4, 1])
            col1.write(label)
            if passed is True:
                col2.success("✅")
            elif passed is False:
                col2.error("❌")
            else:
                col2.warning("⚠️")

        # Final score
        score = sum(1 for _, p in results if p is True)
        total = len(results)
        st.markdown(f"### Final Score: **{score}/{total}**")
        if score >= 4:
            st.success("🟢 Strong Candidate")
        elif score >= 2:
            st.warning("🟡 Watchlist")
        else:
            st.error("🔴 Avoid")

        # Show breakdown
        st.markdown("---")
        st.subheader("📊 Year-by-Year Breakdown")
        for metric, data in trend_tables.items():
            st.markdown(f"**{metric}**")
            df = pd.DataFrame(data, columns=["Year", "Value", "Passed"]).set_index("Year")
            st.line_chart(df["Value"])
            st.dataframe(df.style.applymap(
                lambda v: "background-color: #d4edda" if v is True else ("background-color: #f8d7da" if v is False else ""),
                subset=["Passed"]))

        # Manual review section
        st.markdown("---")
        st.subheader("📌 Manual Review Required")
        st.info(
            "- 🧱 Barriers to Entry (brand, IP, network, cost moat)\n"
            "- 🏭 Organized Labor Exposure\n"
            "- 📈 Pricing Power / Inflation Pass-through"
        )

        # Download
        st.markdown("---")
        st.subheader("📥 Download Summary")
        summary_df = pd.DataFrame(results, columns=["Checklist Item", "Passed"])
        buffer = BytesIO()
        summary_df.to_csv(buffer, index=False)
        st.download_button("Download Summary CSV", buffer.getvalue(), file_name=f"{ticker}_checklist_summary.csv", mime="text/csv")

    except Exception as e:
        st.error(f"Error fetching data: {e}")
