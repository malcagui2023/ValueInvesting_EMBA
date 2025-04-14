import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
from datetime import datetime

# Chart styling
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
st.title("📊 Value Investing Checklist")

ticker = st.text_input("Enter Ticker Symbol (e.g., AAPL, NVDA)", value="AAPL")

@st.cache_data
def get_data(ticker):
    stock = yf.Ticker(ticker)
    info = stock.info or {}
    bs = stock.balance_sheet if stock.balance_sheet is not None else pd.DataFrame()
    fin = stock.financials if stock.financials is not None else pd.DataFrame()
    earnings = stock.earnings if stock.earnings is not None else pd.DataFrame()
    hist = stock.history(period="10y")
    div = stock.dividends if stock.dividends is not None else pd.Series(dtype="float64")
    return info, bs, fin, earnings, hist, div

def safe_ratio(numerator, denominator):
    try:
        return numerator / denominator if denominator and denominator != 0 else None
    except:
        return None

def check_threshold(series, threshold, comparison=">"):
    fail_count = 0
    for v in series.values():
        if v is None:
            continue
        if comparison == ">" and v <= threshold:
            fail_count += 1
        elif comparison == "<" and v >= threshold:
            fail_count += 1
    return fail_count, (fail_count == 0)
if ticker:
    try:
        info, bs, fin, earnings, hist, div = get_data(ticker)
        years = sorted(fin.columns.year)[-10:]

        summary_data = []
        metric_trends = {}

        # --- Metric 1: ROE > 12% ---
        roe_series = {}
        for year in years:
            try:
                net = fin.loc["Net Income", fin.columns[fin.columns.year == year]].values[0]
                equity = bs.loc["Total Stockholder Equity", bs.columns[bs.columns.year == year]].values[0]
                roe_series[year] = safe_ratio(net, equity)
            except:
                roe_series[year] = None
        fail, pass_check = check_threshold(roe_series, 0.12)
        summary_data.append(("ROE > 12%", "✅" if pass_check else "❌", f"{fail} fails"))
        metric_trends["ROE"] = roe_series

        # --- Metric 2: ROA > 12% ---
        roa_series = {}
        for year in years:
            try:
                net = fin.loc["Net Income", fin.columns[fin.columns.year == year]].values[0]
                assets = bs.loc["Total Assets", bs.columns[bs.columns.year == year]].values[0]
                roa_series[year] = safe_ratio(net, assets)
            except:
                roa_series[year] = None
        fail, pass_check = check_threshold(roa_series, 0.12)
        summary_data.append(("ROA > 12%", "✅" if pass_check else "❌", f"{fail} fails"))
        metric_trends["ROA"] = roa_series

        # --- Metric 3: EPS ---
        eps_series = {}
        if not earnings.empty:
            for year in earnings.index[-10:]:
                eps_series[year] = earnings.loc[year]["Earnings"]
        summary_data.append(("EPS Trend", "✅" if eps_series else "⚠️", f"{len(eps_series)} years"))
        metric_trends["EPS"] = eps_series

        # --- Metric 4: Net Margin > 20% ---
        net_margin_series = {}
        for year in years:
            try:
                net = fin.loc["Net Income", fin.columns[fin.columns.year == year]].values[0]
                rev = fin.loc["Total Revenue", fin.columns[fin.columns.year == year]].values[0]
                net_margin_series[year] = safe_ratio(net, rev)
            except:
                net_margin_series[year] = None
        fail, pass_check = check_threshold(net_margin_series, 0.20)
        summary_data.append(("Net Margin > 20%", "✅" if pass_check else "❌", f"{fail} fails"))
        metric_trends["Net Margin"] = net_margin_series

        # --- Metric 5: Gross Margin > 40% ---
        gm_series = {}
        for year in years:
            try:
                gross = fin.loc["Gross Profit", fin.columns[fin.columns.year == year]].values[0]
                rev = fin.loc["Total Revenue", fin.columns[fin.columns.year == year]].values[0]
                gm_series[year] = safe_ratio(gross, rev)
            except:
                gm_series[year] = None
        fail, pass_check = check_threshold(gm_series, 0.40)
        summary_data.append(("Gross Margin > 40%", "✅" if pass_check else "❌", f"{fail} fails"))
        metric_trends["Gross Margin"] = gm_series

        # --- Metric 10: Return on Retained Capital > 18% ---
        rorc_series = {}
        for year in years:
            try:
                net = fin.loc["Net Income", fin.columns[fin.columns.year == year]].values[0]
                divs = div[div.index.year == year].sum()
                retained = net - divs
                rorc_series[year] = safe_ratio(net, retained)
            except:
                rorc_series[year] = None
        fail, pass_check = check_threshold(rorc_series, 0.18)
        summary_data.append(("Return on Retained Capital > 18%", "✅" if pass_check else "❌", f"{fail} fails"))
        metric_trends["RORC"] = rorc_series

        # --- Metric 7: LT Debt < 5x Net Income ---
        try:
            latest_year = years[-1]
            debt = bs.loc["Long Term Debt", bs.columns[bs.columns.year == latest_year]].values[0]
            net = fin.loc["Net Income", fin.columns[fin.columns.year == latest_year]].values[0]
            ratio = safe_ratio(debt, net)
            lt_debt_result = f"{ratio:.2f}x"
            lt_debt_pass = "✅" if ratio < 5 else "❌"
        except:
            lt_debt_result = "N/A"
            lt_debt_pass = "⚠️"
        summary_data.append(("LT Debt < 5x Net Income", lt_debt_pass, lt_debt_result))

        # --- Metric 11: Dividends & Buybacks ---
        div_years = sorted(set(div.index.year))
        cuts = []
        if len(div_years) > 1:
            for i in range(1, len(div_years)):
                if div[div.index.year == div_years[i]].max() < div[div.index.year == div_years[i-1]].max():
                    cuts.append(div_years[i])
        div_msg = "No Dividends" if not div_years else f"{len(div_years)} yrs | {'Cut(s): ' + str(cuts) if cuts else 'No Cuts'}"
        summary_data.append(("Dividends & Buybacks", "✅" if not cuts else "❌", div_msg))
                # --- TOP: Summary Table ---
        st.subheader("📋 Summary Table")
        st.table(pd.DataFrame(summary_data, columns=["Metric", "Passed", "Value/Failures"]))

        # --- MIDDLE: Charts + Tables ---
        st.subheader("📊 Metric Trend Charts & Tables")
        for metric, data in metric_trends.items():
            st.markdown(f"### {metric}")
            df = pd.DataFrame.from_dict(data, orient="index", columns=["Value"])
            df.index.name = "Year"
            df["Value"] = df["Value"] * 100 if "Margin" in metric or "ROE" in metric or "ROA" in metric or "RORC" in metric else df["Value"]
            df_display = df.copy()
            if "Value" in df_display:
                df_display["Value"] = df_display["Value"].apply(lambda x: f"{x:.2f}%" if x is not None else "N/A")
            st.dataframe(df_display)

            # Plot chart
            fig, ax = plt.subplots(figsize=(8, 3))
            df["Value"].plot(ax=ax, marker="o", color="tab:blue")
            ax.set_title(metric)
            ax.set_ylabel("Percent" if "%" in df_display["Value"].iloc[0] else "")
            ax.set_xlabel("Year")
            ax.grid(True, linestyle="--", linewidth=0.5)
            st.pyplot(fig)

        # --- BOTTOM: Commentary Section ---
        st.markdown("---")
        st.subheader("🧠 Non-Quantitative Insights")

        st.markdown("### 💼 Product/Service Pricing vs Inflation")
        st.info(
            "Compare company's pricing power to US inflation rate (~3.2% as of latest CPI data). "
            "You may search annual reports or earnings call transcripts for pricing power insights."
        )

        st.markdown("### 🏭 Organized Labor")
        st.info(
            "Search for news or filings on union activity or workforce disruptions. "
            "SEC 10-K sections on risk factors often mention labor risks."
        )

        st.markdown("### 🧱 Barriers to Entry")
        st.info(
            "- Strong brand loyalty and ecosystem integration (e.g., Apple)\n"
            "- Economies of scale reduce marginal costs\n"
            "- R&D advantage and patents\n"
            "- Distribution network lock-in\n\n"
            "_Sources: Company 10-K, industry whitepapers, Morningstar moat analysis_"
        )

    except Exception as e:
        st.error(f"Error: {e}")

