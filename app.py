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
    earnings = stock.earnings or pd.DataFrame()
    hist = stock.history(period="max")
    div = stock.dividends if stock.dividends is not None else pd.Series(dtype="float64")
    return info, bs, fin, earnings, hist, div

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
        info, bs, fin, earnings, hist, div = get_data(ticker)

        # Price History Chart
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

        # Get available fiscal years
        years = list(fin.columns.year)
        selected_years = sorted(years)[-period_years:]

        # --- ROE ---
        roe_series = {}
        for y in selected_years:
            try:
                net = fin[fin.columns[fin.columns.year == y]].loc["Net Income"].values[0]
                equity = bs[bs.columns[bs.columns.year == y]].loc["Total Stockholder Equity"].values[0]
                roe_series[y] = safe_ratio(net, equity)
            except:
                roe_series[y] = None
        roe_check, roe_pass = check_all_years(roe_series, 0.12)
        results.append(("ROE > 12%", roe_pass))
        trend_tables["ROE"] = roe_check

        # --- ROA ---
        roa_series = {}
        for y in selected_years:
            try:
                net = fin[fin.columns[fin.columns.year == y]].loc["Net Income"].values[0]
                assets = bs[bs.columns[bs.columns.year == y]].loc["Total Assets"].values[0]
                roa_series[y] = safe_ratio(net, assets)
            except:
                roa_series[y] = None
        roa_check, roa_pass = check_all_years(roa_series, 0.12)
        results.append(("ROA > 12%", roa_pass))
        trend_tables["ROA"] = roa_check

        # --- Net Margin ---
        margin_series = {}
        for y in selected_years:
            try:
                net = fin[fin.columns[fin.columns.year == y]].loc["Net Income"].values[0]
                rev = fin[fin.columns[fin.columns.year == y]].loc["Total Revenue"].values[0]
                margin_series[y] = safe_ratio(net, rev)
            except:
                margin_series[y] = None
        margin_check, margin_pass = check_all_years(margin_series, 0.20)
        results.append(("Net Margin > 20%", margin_pass))
        trend_tables["Net Margin"] = margin_check

        # --- EPS Growth (Positive Trend) ---
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
            trend_tables["EPS"] = eps_check
        else:
            results.append(("EPS Trend Upward", None))
        # --- Gross Margin ---
        gross_margin_series = {}
        for y in selected_years:
            try:
                rev = fin[fin.columns[fin.columns.year == y]].loc["Total Revenue"].values[0]
                cogs = fin[fin.columns[fin.columns.year == y]].loc["Cost Of Revenue"].values[0]
                gross_margin_series[y] = safe_ratio(rev - cogs, rev)
            except:
                gross_margin_series[y] = None
        gm_check, gm_pass = check_all_years(gross_margin_series, 0.40)
        results.append(("Gross Margin > 40%", gm_pass))
        trend_tables["Gross Margin"] = gm_check

        # --- Debt / Net Income ---
        debt_series = {}
        for y in selected_years:
            try:
                debt = bs[bs.columns[bs.columns.year == y]].loc["Long Term Debt"].values[0]
                net = fin[fin.columns[fin.columns.year == y]].loc["Net Income"].values[0]
                debt_series[y] = safe_ratio(debt, net)
            except:
                debt_series[y] = None
        debt_check, debt_pass = check_all_years(debt_series, 5, comparison='<')
        results.append(("LT Debt < 5x Net Income", debt_pass))
        trend_tables["Debt / Net Income"] = debt_check

        # --- Return on Retained Capital ---
        rorc_series = {}
        for y in selected_years:
            try:
                net = fin[fin.columns[fin.columns.year == y]].loc["Net Income"].values[0]
                dividends = cf[cf.columns[cf.columns.year == y]].loc["Dividends Paid"].values[0] if "Dividends Paid" in cf.index else 0
                retained = net + dividends  # Negative divs
                rorc_series[y] = safe_ratio(net, retained)
            except:
                rorc_series[y] = None
        rorc_check, rorc_pass = check_all_years(rorc_series, 0.18)
        results.append(("Return on Retained Capital > 18%", rorc_pass))
        trend_tables["Return on Retained Capital"] = rorc_check

        # --- Dividends & Buybacks ---
        if div.empty:
            results.append(("Dividends / Buybacks", "No Dividends"))
        else:
            annual = div.resample("Y").sum()
            cuts = (annual == 0).sum()
            results.append(("Dividends / Buybacks", f"{len(annual)} years | {'Cut' if cuts > 0 else 'No Cuts'}"))

        # --- Display Checklist Summary ---
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
        total = len(results)
        st.markdown(f"### 🎯 Final Score: **{score}/{total}**")
        if score >= 9:
            st.success("🟢 Strong Candidate")
        elif score >= 6:
            st.warning("🟡 Watchlist")
        else:
            st.error("🔴 Avoid")

        # --- Trend Charts + Tables ---
        st.markdown("---")
        st.subheader("📊 Year-by-Year Breakdown")
        for metric, data in trend_tables.items():
            st.markdown(f"**{metric}**")
            df = pd.DataFrame(data, columns=["Year", "Value", "Passed"])
            df["Year"] = df["Year"].astype(int)
            df.set_index("Year", inplace=True)

            fig, ax = plt.subplots(figsize=(8, 3))
            df["Value"].plot(ax=ax, color="tab:blue", marker="o")
            ax.set_facecolor("#f0f0f0")
            ax.set_title(f"{metric} Over Time", fontsize=12)
            ax.set_ylabel(metric)
            ax.set_xlabel("Year")
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

        # --- Manual Review ---
        st.markdown("---")
        st.subheader("📌 Manual Review Required")
        st.info(
            "- 🧱 Barriers to Entry (brand, IP, network, cost moat)\n"
            "- 🏭 Organized Labor Exposure\n"
            "- 📈 Pricing Power / Inflation Pass-through"
        )

        # --- Download ---
        st.markdown("---")
        st.subheader("📥 Download Summary")
        summary_df = pd.DataFrame(results, columns=["Checklist Item", "Passed"])
        buffer = BytesIO()
        summary_df.to_csv(buffer, index=False)
        st.download_button("Download Checklist as CSV", buffer.getvalue(), file_name=f"{ticker}_checklist_summary.csv", mime="text/csv")

    except Exception as e:
        st.error(f"Error fetching data: {e}")
