import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO

# Global chart style
plt.style.use("seaborn-v0_8-darkgrid")
plt.rcParams.update({
    "axes.facecolor": "#f4f4f4",
    "figure.facecolor": "#f4f4f4",
    "axes.edgecolor": "gray",
    "axes.labelcolor": "black",
    "xtick.color": "black",
    "ytick.color": "black",
    "text.color": "black",
    "grid.color": "white",
    "grid.linestyle": "--"
})

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
        hist["Close"].resample("M").last().plot(ax=ax, color="orange")
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

        # Metric: ROE
        roe_series = {}
        for year in selected_years:
            try:
                net = fin.loc["Net Income", fin.columns[fin.columns.year == year]].values[0]
                equity = bs.loc["Total Stockholder Equity", bs.columns[bs.columns.year == year]].values[0]
                roe_series[year] = safe_ratio(net, equity)
            except:
                roe_series[year] = None
        roe_check, roe_pass = check_all_years(roe_series, 0.12)
        results.append(("ROE > 12%", roe_pass))
        trend_tables["ROE"] = roe_check

        # Metric: ROA
        roa_series = {}
        for year in selected_years:
            try:
                net = fin.loc["Net Income", fin.columns[fin.columns.year == year]].values[0]
                assets = bs.loc["Total Assets", bs.columns[bs.columns.year == year]].values[0]
                roa_series[year] = safe_ratio(net, assets)
            except:
                roa_series[year] = None
        roa_check, roa_pass = check_all_years(roa_series, 0.12)
        results.append(("ROA > 12%", roa_pass))
        trend_tables["ROA"] = roa_check

        # Metric: Net Margin
        net_margin_series = {}
        for year in selected_years:
            try:
                net = fin.loc["Net Income", fin.columns[fin.columns.year == year]].values[0]
                rev = fin.loc["Total Revenue", fin.columns[fin.columns.year == year]].values[0]
                net_margin_series[year] = safe_ratio(net, rev)
            except:
                net_margin_series[year] = None
        net_margin_check, net_margin_pass = check_all_years(net_margin_series, 0.20)
        results.append(("Net Margin > 20%", net_margin_pass))
        trend_tables["Net Margin"] = net_margin_check

        # Metric: EPS Trend
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

        # Metric: Gross Margin
        gross_margin_series = {}
        for year in selected_years:
            try:
                gross_profit = fin.loc["Gross Profit", fin.columns[fin.columns.year == year]].values[0]
                revenue = fin.loc["Total Revenue", fin.columns[fin.columns.year == year]].values[0]
                gross_margin_series[year] = safe_ratio(gross_profit, revenue)
            except:
                gross_margin_series[year] = None
        gm_check, gm_pass = check_all_years(gross_margin_series, 0.40)
        results.append(("Gross Margin > 40%", gm_pass))
        trend_tables["Gross Margin"] = gm_check

        # Metric: Debt / Net Earnings
        debt_series = {}
        for year in selected_years:
            try:
                debt = bs.loc["Long Term Debt", bs.columns[bs.columns.year == year]].values[0]
                net_income = fin.loc["Net Income", fin.columns[fin.columns.year == year]].values[0]
                debt_series[year] = safe_ratio(debt, net_income)
            except:
                debt_series[year] = None
        debt_check, debt_pass = check_all_years(debt_series, 5, comparison="<")
        results.append(("LT Debt < 5x Net Income", debt_pass))
        trend_tables["LT Debt / Net Income"] = debt_check

        # Metric: Return on Retained Capital (approximate)
        rorc_series = {}
        for year in selected_years:
            try:
                net_income = fin.loc["Net Income", fin.columns[fin.columns.year == year]].values[0]
                dividends = div[div.index.year == year].sum()
                retained_earnings = net_income - dividends
                rorc_series[year] = safe_ratio(net_income, retained_earnings)
            except:
                rorc_series[year] = None
        rorc_check, rorc_pass = check_all_years(rorc_series, 0.18)
        results.append(("Return on Retained Capital > 18%", rorc_pass))
        trend_tables["Return on Retained Capital"] = rorc_check

        # Dividends & Buybacks (Basic Check)
        div_years = sorted(set(div.index.year))
        cut_years = []
        if len(div_years) > 1:
            for i in range(1, len(div_years)):
                if div[div.index.year == div_years[i]].max() < div[div.index.year == div_years[i - 1]].max():
                    cut_years.append(div_years[i])
        if len(div_years) == 0:
            div_result = "No Dividends"
            pass_div = None
        else:
            div_result = f"{len(div_years)} years | " + ("Cut(s): " + ", ".join(map(str, cut_years)) if cut_years else "No Cuts")
            pass_div = len(cut_years) == 0
        results.append((f"Dividends/Buybacks: {div_result}", pass_div))

        # Checklist Summary
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

        # Score
        score = sum(1 for _, p in results if p is True)
        total = len(results)
        st.markdown(f"### 🎯 Final Score: **{score}/{total}**")
        if score >= 4:
            st.success("🟢 Strong Candidate")
        elif score >= 2:
            st.warning("🟡 Watchlist")
        else:
            st.error("🔴 Avoid")

        # Charts
        st.markdown("---")
        st.subheader("📊 Year-by-Year Breakdown")
        for metric, data in trend_tables.items():
            st.markdown(f"**{metric}**")
            df = pd.DataFrame(data, columns=["Year", "Value", "Passed"])
            df["Year"] = df["Year"].astype(int)
            df.set_index("Year", inplace=True)

            fig, ax = plt.subplots(figsize=(8, 3))
            df["Value"].plot(ax=ax, color="tab:blue", marker="o")
            ax.set_title(f"{metric}", fontsize=12)
            ax.set_xlabel("Year")
            ax.grid(True, linestyle="--", linewidth=0.5)
            st.pyplot(fig)

            st.dataframe(
                df.style.applymap(
                    lambda v: "background-color: #d4edda" if v is True else ("background-color: #f8d7da" if v is False else ""),
                    subset=["Passed"]
                ),
                use_container_width=True
            )

        # Manual Items
        st.markdown("---")
        st.subheader("📌 Manual Review Required")
        st.info(
            "- 🧱 Barriers to Entry (brand, IP, network, cost moat)\n"
            "- 🏭 Organized Labor Exposure\n"
            "- 📈 Pricing Power / Inflation Pass-through"
        )

        # Download Button
        st.markdown("---")
        st.subheader("📥 Download Summary")
        summary_df = pd.DataFrame(results, columns=["Checklist Item", "Passed"])
        buffer = BytesIO()
        summary_df.to_csv(buffer, index=False)
        st.download_button("Download Summary CSV", buffer.getvalue(), file_name=f"{ticker}_checklist_summary.csv", mime="text/csv")

    except Exception as e:
        st.error(f"Error fetching data: {e}")
