import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
import datetime

# ==========================================================
# Chart Theme: Dark Theme via Matplotlib
# ==========================================================
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

# ==========================================================
# Page Configuration
# ==========================================================
st.set_page_config(page_title="Value Investing Checklist", layout="wide")

# ----------------------------
# Top Section: Logo + Title
# ----------------------------
logo_col, title_col = st.columns([1, 5])
with logo_col:
    st.image("SCM-Analytics Logo.jfif", use_column_width=True)
with title_col:
    st.title("Value Investing Checklist (Year-by-Year)")

# ==========================================================
# Input: Ticker Symbol
# ==========================================================
ticker = st.text_input("Enter Ticker Symbol (e.g., AAPL, NVDA)", value="AAPL")

# ==========================================================
# Data Loading & Utility Functions
# ==========================================================
@st.cache_data
def get_data(ticker):
    stock = yf.Ticker(ticker)
    info = stock.info
    bs = stock.balance_sheet if stock.balance_sheet is not None else pd.DataFrame()
    fin = stock.financials if stock.financials is not None else pd.DataFrame()
    # We will calculate EPS manually as earnings is deprecated.
    earnings = pd.DataFrame()  
    # Restrict history to last 10 years.
    hist = stock.history(period="10y")
    div = stock.dividends if stock.dividends is not None else pd.Series(dtype="float64")
    return info, bs, fin, earnings, hist, div

def safe_ratio(numerator, denominator):
    try:
        return numerator / denominator if denominator and denominator != 0 else None
    except:
        return None

def get_recent_years(df, max_years=10):
    if df.empty:
        return []
    try:
        years = sorted({col.year for col in df.columns})
    except Exception:
        years = sorted({idx.year for idx in df.index})
    return years[-max_years:]

def format_percent(value):
    if value is None:
        return "Missing"
    try:
        return f"{value*100:.1f}%"
    except:
        return str(value)

# ==========================================================
# Main Processing Block
# ==========================================================
if ticker:
    try:
        info, bs, fin, earnings, hist, div = get_data(ticker)
        fiscal_years = get_recent_years(fin, 10)
        # Fallback: if fewer than 10 fiscal years exist, use the last 5 years.
        if len(fiscal_years) < 10:
            fiscal_years = get_recent_years(fin, 5)
        
        # ======================================================
        # TOP SECTION: Price History Chart (Last 10 Years)
        # ======================================================
        st.subheader("📈 Stock Price (Last 10 Years)")
        fig_price, ax_price = plt.subplots(figsize=(10, 3))
        # Resample using month-end frequency ("ME")
        hist["Close"].resample("ME").last().plot(ax=ax_price, color="orange")
        ax_price.set_title(f"{ticker} Monthly Closing Prices")
        ax_price.set_xlabel("Date")
        ax_price.set_ylabel("Price (USD)")
        ax_price.grid(True)
        st.pyplot(fig_price)

        # ======================================================
        # EVALUATION: Build Summary Table and Collect Yearly Data
        # ======================================================
        summary = []  # List of tuples: (Metric, Pass/Fail, Value/Details)
        metric_data = {}  # Dictionary: Metric name -> {year: value}

        # Helper function to evaluate a metric over each fiscal year:
        def evaluate_metric(metric_name, values_dict, threshold=None, comparison=">", is_percent=True):
            fails = 0
            data = {}
            for y in fiscal_years:
                v = values_dict.get(y)
                if v is None:
                    data[y] = "Missing"
                else:
                    # Convert numeric value to percent if needed:
                    pv = v * 100 if is_percent else v
                    data[y] = round(pv, 2)
                    if threshold is not None:
                        if comparison == ">" and pv < threshold * 100:
                            fails += 1
                        elif comparison == "<" and pv > threshold * 100:
                            fails += 1
            metric_data[metric_name] = data
            pass_fail = "✅" if fails == 0 else "❌"
            summary.append((metric_name, pass_fail, f"{len(fiscal_years)-fails} / {len(fiscal_years)} years passed"))

        # ---- Metric 1: ROE ≥ 12% ----
        roe_vals = {}
        for y in fiscal_years:
            try:
                net = fin.loc["Net Income", fin.columns[fin.columns.year == y]].values[0]
                equity = bs.loc["Total Stockholder Equity", bs.columns[bs.columns.year == y]].values[0]
                roe_vals[y] = safe_ratio(net, equity)
            except:
                roe_vals[y] = None
        evaluate_metric("ROE ≥ 12%", roe_vals, threshold=0.12)

        # ---- Metric 2: ROA ≥ 12% ----
        roa_vals = {}
        for y in fiscal_years:
            try:
                net = fin.loc["Net Income", fin.columns[fin.columns.year == y]].values[0]
                assets = bs.loc["Total Assets", bs.columns[bs.columns.year == y]].values[0]
                roa_vals[y] = safe_ratio(net, assets)
            except:
                roa_vals[y] = None
        evaluate_metric("ROA ≥ 12%", roa_vals, threshold=0.12)

        # ---- Metric 3: Historical EPS Per Share ----
        # Calculate EPS manually as: Net Income / Shares Outstanding (from info)
        eps_vals = {}
        shares = info.get("sharesOutstanding", None)
        for y in fiscal_years:
            try:
                net = fin.loc["Net Income", fin.columns[fin.columns.year == y]].values[0]
                if shares:
                    eps_vals[y] = safe_ratio(net, shares)
                else:
                    eps_vals[y] = None
            except:
                eps_vals[y] = None
        # No pass/fail is evaluated for EPS; simply show available data.
        metric_data["EPS Per Share"] = {y: (round(v*100, 2) if v is not None else "Missing") for y, v in eps_vals.items()}
        available_eps = sum(1 for v in eps_vals.values() if v is not None)
        summary.append(("EPS Per Share", "—", f"{available_eps} / {len(fiscal_years)} years available"))

        # ---- Metric 4: Net Margin ≥ 20% (Net Income ÷ Total Revenue) ----
        net_margin_vals = {}
        for y in fiscal_years:
            try:
                net = fin.loc["Net Income", fin.columns[fin.columns.year == y]].values[0]
                rev = fin.loc["Total Revenue", fin.columns[fin.columns.year == y]].values[0]
                net_margin_vals[y] = safe_ratio(net, rev)
            except:
                net_margin_vals[y] = None
        evaluate_metric("Net Margin ≥ 20%", net_margin_vals, threshold=0.20)

        # ---- Metric 5: Gross Margin ≥ 40% (Gross Profit ÷ Total Revenue) ----
        gm_vals = {}
        for y in fiscal_years:
            try:
                gross = fin.loc["Gross Profit", fin.columns[fin.columns.year == y]].values[0]
                rev = fin.loc["Total Revenue", fin.columns[fin.columns.year == y]].values[0]
                gm_vals[y] = safe_ratio(gross, rev)
            except:
                gm_vals[y] = None
        evaluate_metric("Gross Margin ≥ 40%", gm_vals, threshold=0.40)

        # ---- Metric 6: Return on Retained Capital (RORC) ≥ 18% ----
        # Approximation: Net Income ÷ (Net Income - Dividends)
        rorc_vals = {}
        for y in fiscal_years:
            try:
                net = fin.loc["Net Income", fin.columns[fin.columns.year == y]].values[0]
                year_divs = div[div.index.year == y].sum()
                retained = net - year_divs
                rorc_vals[y] = safe_ratio(net, retained)
            except:
                rorc_vals[y] = None
        evaluate_metric("Return on Retained Capital ≥ 18%", rorc_vals, threshold=0.18)

        # ---- Metric 7: LT Debt ÷ Net Income < 5x (Latest Fiscal Year Only) ----
        try:
            latest_y = fiscal_years[-1]
            debt = bs.loc["Long Term Debt", bs.columns[bs.columns.year == latest_y]].values[0]
            net_latest = fin.loc["Net Income", fin.columns[fin.columns.year == latest_y]].values[0]
            lt_ratio = safe_ratio(debt, net_latest)
            lt_comment = f"{lt_ratio:.2f}x" if lt_ratio is not None else "Missing"
            summary.append(("LT Debt ÷ Net Income < 5x", "✅" if lt_ratio is not None and lt_ratio < 5 else "❌", lt_comment))
        except:
            summary.append(("LT Debt ÷ Net Income < 5x", "⚠️", "Missing"))

        # ---- Metric 8: Pricing Power vs. Inflation (Commentary) ----
        cpi = 0.032  # Example: 3.2% US CPI YoY
        pricing_comment = f"Compare the company's price increases to a US CPI of ~{cpi*100:.1f}%. [Source: U.S. Bureau of Labor Statistics] (EXAMPLE – Research on Your Own)"
        summary.append(("Pricing Power vs. Inflation", "—", pricing_comment))

        # ---- Metric 9: Organized Labor (Commentary) ----
        labor_comment = "Review SEC 10-K filings and recent news for union contracts and labor disputes. [Example Source: Reuters, 2023] (EXAMPLE – Research on Your Own)"
        summary.append(("Organized Labor", "—", labor_comment))

        # ---- Metric 11: Dividends & Buybacks (Commentary) ----
        years_div = sorted(set(div.index.year)) if not div.empty else []
        if not years_div:
            div_comment = "No Dividends or Buybacks"
            div_status = "—"
        else:
            cuts = []
            for i in range(1, len(years_div)):
                try:
                    prev = div[div.index.year == years_div[i-1]].sum()
                    curr = div[div.index.year == years_div[i]].sum()
                    if curr < prev:
                        cuts.append(years_div[i])
                except:
                    pass
            div_comment = f"{len(years_div)} years; Dividend cuts in: {cuts if cuts else 'None'} (EXAMPLE – Research on Your Own)"
            div_status = "✅" if not cuts else "❌"
        summary.append(("Dividends & Buybacks", div_status, div_comment))

        # ---- Metric 12: Barriers to Entry (Commentary) ----
        barriers_comment = (
            "- Strong brand loyalty and ecosystem integration [Source: Morningstar] (EXAMPLE – Research on Your Own)\n"
            "- Patents and proprietary technology [Source: SEC 10-K] (EXAMPLE – Research on Your Own)\n"
            "- Economies of scale and cost advantages [Source: HBR] (EXAMPLE – Research on Your Own)\n"
            "- Well-established distribution channels [Source: WSJ] (EXAMPLE – Research on Your Own)"
        )
        summary.append(("Barriers to Entry", "—", barriers_comment))

        # ======================================================
        # TOP SECTION: Display Summary Table
        # ======================================================
        st.subheader("📋 Summary Table")
        df_summary = pd.DataFrame(summary, columns=["Metric", "Pass/Fail", "Value/Details"])
        st.table(df_summary)

        # ======================================================
        # MIDDLE SECTION: Charts + Tables (wrapped in Expanders & Tabs)
        # ======================================================
        st.subheader("📊 Metrics (Year-by-Year Charts & Tables)")
        for metric, data in metric_data.items():
            with st.expander(f"{metric} Trend (Click to Expand)", expanded=False):
                tab_chart, tab_table = st.tabs(["Chart", "Table"])
                # Prepare DataFrame for charting and display:
                df_metric = pd.DataFrame.from_dict(data, orient="index", columns=["Value"])
                df_metric.index = df_metric.index.map(lambda y: int(y))
                df_metric["Value"] = df_metric["Value"].apply(lambda x: float(x) if isinstance(x, (int, float)) else None)
                # Create chart using matplotlib
                fig, ax = plt.subplots(figsize=(8, 3))
                ax.plot(df_metric.index, df_metric["Value"], marker="o", color="tab:blue")
                ax.set_title(metric)
                ax.set_xlabel("Fiscal Year")
                ax.set_ylabel("Percentage")
                ax.set_xticks(df_metric.index)
                ax.grid(True, linestyle="--", linewidth=0.5)
                st.pyplot(fig, clear_figure=True)
                # Display table:
                df_display = df_metric.copy()
                df_display["Value"] = df_display["Value"].apply(lambda x: f"{x:.2f}%" if isinstance(x, (int, float)) else "Missing")
                tab_table.dataframe(df_display)

        # ======================================================
        # BOTTOM SECTION: Narrative Insights & Commentary
        # ======================================================
        st.subheader("🧠 Narrative Insights & Commentary")
        st.markdown("### 🏛️ Barriers to Entry")
        st.markdown(barriers_comment)
        st.markdown("### 📉 Pricing Power vs. Inflation")
        st.markdown(pricing_comment)
        st.markdown("### 🏭 Organized Labor")
        st.markdown(labor_comment)
        st.markdown("### LT Debt ÷ Net Income")
        st.markdown("Refer to the Summary Table above for the latest LT Debt ÷ Net Income commentary.")
        st.markdown("### Dividends & Buybacks")
        st.markdown("Review the Summary Table for dividend history and evidence of dividend/repurchase cuts.")

        # ======================================================
        # EXPORT SECTION: Download Summary as CSV
        # ======================================================
        st.subheader("📥 Export Results")
        csv_data = df_summary.to_csv(index=False).encode("utf-8")
        st.download_button("📤 Download Summary CSV", csv_data, file_name=f"{ticker}_summary.csv", mime="text/csv")

    except Exception as e:
        st.error(f"Error processing ticker: {e}")
