import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
import datetime

# ----------------------------
# Chart Theme (Dark Matplotlib)
# ----------------------------
plt.style.use("dark_background")
plt.rcParams.update({
    "axes.facecolor": "#1e1e1e",
    "figure.facecolor": "#1e1e1e",
    "axes.edgecolor": "#444444",
    "axes.labelcolor": "white",
    "xtick.color": "white",
    "ytick.color": "white",
    "text.color": "white",
    "grid.color": "#444444",
    "grid.linestyle": "--",
    "legend.edgecolor": "white"
})

st.set_page_config(page_title="Value Investing Checklist", layout="wide")
st.title("📊 Value Investing Checklist (Year-by-Year)")

# ----------------------------
# Inputs
# ----------------------------
ticker = st.text_input("Enter Ticker Symbol (e.g., AAPL, NVDA)", value="AAPL")

@st.cache_data
def get_data(ticker):
    stock = yf.Ticker(ticker)
    info = stock.info
    bs = stock.balance_sheet or pd.DataFrame()
    fin = stock.financials or pd.DataFrame()
    earnings = stock.earnings or pd.DataFrame()
    hist = stock.history(period="10y")
    div = stock.dividends or pd.Series(dtype="float64")
    return info, bs, fin, earnings, hist, div

def safe_ratio(numerator, denominator):
    try:
        return round(numerator / denominator, 4) if denominator else None
    except:
        return None

def get_recent_years(df, max_years=10):
    if df.empty:
        return []
    years = sorted(set(df.columns.year if hasattr(df.columns, 'year') else df.index.year))
    return years[-max_years:]

def format_percent(value):
    return f"{value*100:.1f}%" if isinstance(value, (float, int)) else "Missing"
    if ticker:
    try:
        info, bs, fin, earnings, hist, div = get_data(ticker)
        fiscal_years = get_recent_years(fin, 10)
        fallback = " (fallback 5y)" if len(fiscal_years) < 10 else ""

        # ----------------------------
        # Summary Table Container
        # ----------------------------
        summary = []
        metric_data = {}

        def evaluate_metric(name, values, threshold=None, compare=">", is_percent=True):
            passed = 0
            data = {}
            for y in fiscal_years:
                v = values.get(y)
                if v is None:
                    data[y] = "Missing"
                else:
                    if is_percent:
                        v *= 100
                    if (compare == ">" and v >= threshold * 100) or (compare == "<" and v <= threshold * 100):
                        passed += 1
                    data[y] = round(v, 2)
            metric_data[name] = data
            pass_fail = "✅" if passed == len(fiscal_years) else "❌"
            summary.append((name, pass_fail, f"{passed} / {len(fiscal_years)} years passed"))

        # ----------------------------
        # ROE
        # ----------------------------
        roe_vals = {}
        for y in fiscal_years:
            try:
                net = fin.loc["Net Income", fin.columns[fin.columns.year == y]].values[0]
                eq = bs.loc["Total Stockholder Equity", bs.columns[bs.columns.year == y]].values[0]
                roe_vals[y] = safe_ratio(net, eq)
            except: roe_vals[y] = None
        evaluate_metric("ROE ≥ 12%", roe_vals, threshold=0.12)

        # ROA
        roa_vals = {}
        for y in fiscal_years:
            try:
                net = fin.loc["Net Income", fin.columns[fin.columns.year == y]].values[0]
                assets = bs.loc["Total Assets", bs.columns[bs.columns.year == y]].values[0]
                roa_vals[y] = safe_ratio(net, assets)
            except: roa_vals[y] = None
        evaluate_metric("ROA ≥ 12%", roa_vals, threshold=0.12)

        # EPS
        eps_vals = {}
        if not earnings.empty:
            for y in fiscal_years:
                eps_vals[y] = earnings.loc[y]["Earnings"] if y in earnings.index else None
        metric_data["EPS"] = eps_vals
        summary.append(("EPS Per Share", "—", f"{len([v for v in eps_vals.values() if v is not None])} available"))

        # Net Margin
        net_margin_vals = {}
        for y in fiscal_years:
            try:
                net = fin.loc["Net Income", fin.columns[fin.columns.year == y]].values[0]
                rev = fin.loc["Total Revenue", fin.columns[fin.columns.year == y]].values[0]
                net_margin_vals[y] = safe_ratio(net, rev)
            except: net_margin_vals[y] = None
        evaluate_metric("Net Margin ≥ 20%", net_margin_vals, threshold=0.20)

        # Gross Margin
        gross_margin_vals = {}
        for y in fiscal_years:
            try:
                gross = fin.loc["Gross Profit", fin.columns[fin.columns.year == y]].values[0]
                rev = fin.loc["Total Revenue", fin.columns[fin.columns.year == y]].values[0]
                gross_margin_vals[y] = safe_ratio(gross, rev)
            except: gross_margin_vals[y] = None
        evaluate_metric("Gross Margin ≥ 40%", gross_margin_vals, threshold=0.40)

        # RORC
        rorc_vals = {}
        for y in fiscal_years:
            try:
                net = fin.loc["Net Income", fin.columns[fin.columns.year == y]].values[0]
                divs = div[div.index.year == y].sum()
                retained = net - divs
                rorc_vals[y] = safe_ratio(net, retained)
            except: rorc_vals[y] = None
        evaluate_metric("Return on Retained Capital ≥ 18%", rorc_vals, threshold=0.18)

        # LT Debt ÷ Net Income
        try:
            latest_y = fiscal_years[-1]
            debt = bs.loc["Long Term Debt", bs.columns[bs.columns.year == latest_y]].values[0]
            net = fin.loc["Net Income", fin.columns[fin.columns.year == latest_y]].values[0]
            ratio = safe_ratio(debt, net)
            lt_comment = f"{ratio:.2f}x" if ratio is not None else "Missing"
            summary.append(("LT Debt ÷ Net Income < 5x", "✅" if ratio < 5 else "❌", lt_comment))
        except:
            summary.append(("LT Debt ÷ Net Income < 5x", "⚠️", "Missing"))

        # Dividends & Buybacks
        years_available = sorted(set(div.index.year))
        cuts = []
        if len(years_available) > 1:
            for i in range(1, len(years_available)):
                if div[div.index.year == years_available[i]].sum() < div[div.index.year == years_available[i - 1]].sum():
                    cuts.append(years_available[i])
        summary.append(("Dividends & Buybacks", "✅" if not cuts else "❌", f"{len(years_available)} years | Cuts: {cuts or 'None'}"))
        # ----------------------------
        # Display Summary Table
        # ----------------------------
        st.subheader("📋 Summary Table")
        st.table(pd.DataFrame(summary, columns=["Metric", "Pass/Fail", "Value/Details"]))

        # ----------------------------
        # Chart Section in Tabs
        # ----------------------------
        st.subheader("📊 Metric Charts & Tables (Last 10 Years)")
        for name, data in metric_data.items():
            with st.container():
                with st.expander(f"{name} Trend", expanded=False):
                    tab1, tab2 = st.tabs(["Chart", "Table"])
                    # Prepare values
                    years = list(data.keys())
                    values = [data[y] if isinstance(data[y], (int, float)) else None for y in years]

                    # Plot
                    fig, ax = plt.subplots(figsize=(8, 3))
                    ax.plot(years, values, marker="o", color="tab:blue")
                    ax.set_title(f"{name}")
                    ax.set_xlabel("Year")
                    ax.set_ylabel("Value")
                    ax.set_xticks(years)
                    ax.grid(True)
                    st.pyplot(fig)

                    # Table
                    df = pd.DataFrame({
                        "Year": years,
                        "Value": [format_percent(v/100) if isinstance(v, (float, int)) and 'Margin' in name else v if v is not None else "Missing" for v in values]
                    }).set_index("Year")
                    tab2.dataframe(df)

        # ----------------------------
        # Bottom Section – Commentary
        # ----------------------------
        st.subheader("🧠 Narrative Insights & Commentary")

        st.markdown("### 🏛️ Barriers to Entry")
        st.markdown("""
- Strong customer lock-in via ecosystem integration (Apple) [Source: Morningstar]
- Patents and proprietary tech reduce substitutes [Source: SEC 10-K]
- Cost advantages via scale or access [Source: HBR]
- Global supply chain control limits new entrants [Source: WSJ]
        """)

        st.markdown("### 📉 Pricing Power vs. Inflation")
        st.markdown("""
As of July 2024, US CPI YoY stands at 3.2% [Source: U.S. Bureau of Labor Statistics].
Compare company price hikes in earnings reports to inflation. If the company raises prices ≥ CPI without losing volume, it's a ✅.
        """)

        st.markdown("### 🏭 Organized Labor Exposure")
        st.markdown("""
Check the company’s 10-K or recent news. Are there any union contracts, strike risks, or settlements?
[Example Source: Reuters, 2023 - Amazon labor action in NY]
        """)

        # ----------------------------
        # Download Export
        # ----------------------------
        st.subheader("📥 Export Results")
        df_summary = pd.DataFrame(summary, columns=["Metric", "Pass/Fail", "Value/Details"])
        csv = df_summary.to_csv(index=False).encode("utf-8")
        st.download_button("📤 Download Summary CSV", csv, file_name=f"{ticker}_summary.csv", mime="text/csv")

    except Exception as e:
        st.error(f"Error processing ticker: {e}")

