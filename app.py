import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO

plt.style.use("seaborn-darkgrid")
st.set_page_config(page_title="Value Investing Checklist", layout="wide")
st.title("📊 Value Investing Checklist (Year-by-Year)")

ticker = st.text_input("Enter Ticker Symbol (e.g., AAPL, NVDA)", value="AAPL")
period = st.selectbox("Select analysis period", ["10y", "5y"], index=0)
period_years = 10 if period == "10y" else 5

@st.cache_data
def get_data(ticker):
    stock = yf.Ticker(ticker)
    info = stock.info or {}
    bs = stock.balance_sheet or pd.DataFrame()
    fin = stock.financials or pd.DataFrame()
    cf = stock.cashflow or pd.DataFrame()
    earnings = stock.earnings or pd.DataFrame()
    hist = stock.history(period="max")
    div = stock.dividends if stock.dividends is not None else pd.Series(dtype="float64")
    return info, bs, fin, cf, earnings, hist, div

def safe_ratio(num, den):
    try:
        return num / den if den and den != 0 else None
    except:
        return None

def check_all_years(metric_series, threshold, comparison='>'):
    checks = []
    for year, value in metric_series.items():
        if value is None:
            checks.append((year, value, None))
        elif comparison == '>':
            checks.append((year, value, value > threshold))
        elif comparison == '<':
            checks.append((year, value, value < threshold))
    passed_all = all(c[2] for c in checks if c[2] is not None)
    return checks, passed_all

if ticker:
    try:
        info, bs, fin, cf, earnings, hist, div = get_data(ticker)

        st.subheader("📈 Price History")
        fig, ax = plt.subplots(figsize=(10, 3))
        hist["Close"].resample("M").last().plot(ax=ax, color="orange")
        ax.set_facecolor("#f2f2f2")
        ax.set_title(f"{ticker} Monthly Closing Prices", fontsize=14)
        ax.set_ylabel("Price (USD)")
        ax.grid(True, linestyle="--", linewidth=0.5)
        st.pyplot(fig)

        results = []
        trend_tables = {}
        available_years = list(fin.columns.year)
        selected_years = sorted(available_years)[-period_years:]

        def extract_metric(label, formula_func, threshold, comp='>'):
            data = {}
            for y in selected_years:
                try:
                    data[y] = formula_func(y)
                except:
                    data[y] = None
            check, passed = check_all_years(data, threshold, comparison=comp)
            results.append((label, passed))
            trend_tables[label] = check

        extract_metric("ROE > 12%", lambda y: safe_ratio(
            fin[fin.columns[fin.columns.year == y]].loc["Net Income"].values[0],
            bs[bs.columns[bs.columns.year == y]].loc["Total Stockholder Equity"].values[0]
        ), 0.12)

        extract_metric("ROA > 12%", lambda y: safe_ratio(
            fin[fin.columns[fin.columns.year == y]].loc["Net Income"].values[0],
            bs[bs.columns[bs.columns.year == y]].loc["Total Assets"].values[0]
        ), 0.12)

        extract_metric("Net Margin > 20%", lambda y: safe_ratio(
            fin[fin.columns[fin.columns.year == y]].loc["Net Income"].values[0],
            fin[fin.columns[fin.columns.year == y]].loc["Total Revenue"].values[0]
        ), 0.20)

        extract_metric("Gross Margin > 40%", lambda y: safe_ratio(
            fin[fin.columns[fin.columns.year == y]].loc["Total Revenue"].values[0] -
            fin[fin.columns[fin.columns.year == y]].loc["Cost Of Revenue"].values[0],
            fin[fin.columns[fin.columns.year == y]].loc["Total Revenue"].values[0]
        ), 0.40)

        extract_metric("LT Debt < 5x Net Income", lambda y: safe_ratio(
            bs[bs.columns[bs.columns.year == y]].loc["Long Term Debt"].values[0],
            fin[fin.columns[fin.columns.year == y]].loc["Net Income"].values[0]
        ), 5, comp='<')

        extract_metric("Return on Retained Capital > 18%", lambda y: safe_ratio(
            fin[fin.columns[fin.columns.year == y]].loc["Net Income"].values[0],
            fin[fin.columns[fin.columns.year == y]].loc["Net Income"].values[0] +
            abs(cf[cf.columns[cf.columns.year == y]].loc["Dividends Paid"].values[0]) if "Dividends Paid" in cf.index else 0
        ), 0.18)

        # EPS Trend
        eps_check = []
        eps_pass = None
        if not earnings.empty:
            eps = earnings["Earnings"]
            eps_diff = eps.diff().dropna()
            eps_pass = (eps_diff > 0).all()
            for y in eps.index[-period_years:]:
                val = eps.loc[y]
                eps_check.append((y, val, val > 0))
            results.append(("EPS Trend Upward", eps_pass))
            trend_tables["EPS Trend Upward"] = eps_check
        else:
            results.append(("EPS Trend Upward", None))

        # Dividends
        if div.empty:
            results.append(("Dividends / Buybacks", "No Dividends"))
        else:
            annual = div.resample("Y").sum()
            cuts = (annual == 0).sum()
            results.append(("Dividends / Buybacks", f"{len(annual)} years | {'Cut' if cuts > 0 else 'No Cuts'}"))

        # Summary
        st.markdown("#### 🔍 Checklist Summary")
        for label, passed in results:
            col1, col2 = st.columns([4, 1])
            col1.write(f"**{label}**")
            if passed is True:
                col2.success("✅")
            elif passed is False:
                col2.error("❌")
            else:
                col2.warning("⚠️")

        score = sum(1 for _, p in results if p is True)
        total = len([r for r in results if isinstance(r[1], bool)])
        st.markdown(f"### 🎯 Final Score: **{score}/{total}**")

        # Charts + Tables
        st.markdown("---")
        st.subheader("📊 Year-by-Year Breakdown")
        for metric, data in trend_tables.items():
            st.markdown(f"**{metric}**")
            df = pd.DataFrame(data, columns=["Year", "Value", "Passed"])
            df["Year"] = df["Year"].astype(int)
            df.set_index("Year", inplace=True)
            fig, ax = plt.subplots(figsize=(8, 3))
            df["Value"].plot(ax=ax, marker="o", color="tab:blue")
            ax.set_facecolor("#f0f0f0")
            ax.set_title(f"{metric}", fontsize=12)
            ax.set_ylabel("Value")
            ax.grid(True, linestyle="--", linewidth=0.5)
            st.pyplot(fig)
            st.dataframe(
                df.style.applymap(
                    lambda v: "background-color: #d4edda" if v is True else (
                        "background-color: #f8d7da" if v is False else ""),
                    subset=["Passed"]
                ),
                use_container_width=True
            )

        # Manual Review
        st.markdown("---")
        st.subheader("📌 Manual Review Required")
        st.info(\"\"\"\
- 🧱 Barriers to Entry (brand, IP, network, cost moat)
- 🏭 Organized Labor Exposure
- 📈 Pricing Power / Inflation Pass-through
\"\"\")

        # Download CSV
        st.markdown("---")
        st.subheader("📥 Download Summary")
        summary_df = pd.DataFrame(results, columns
