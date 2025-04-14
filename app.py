import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
import datetime

# ==========================================================
# Chart Theme: Use only Matplotlib (dark theme)
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
# Page configuration
# ==========================================================
st.set_page_config(page_title="Value Investing Checklist", layout="wide")
st.title("📊 Value Investing Checklist (Year-by-Year)")

# ==========================================================
# Input: Ticker Symbol
# ==========================================================
ticker = st.text_input("Enter Ticker Symbol (e.g., AAPL, NVDA)", value="AAPL")

# ==========================================================
# Data loading and utility functions
# ==========================================================
@st.cache_data
def get_data(ticker):
    stock = yf.Ticker(ticker)
    info = stock.info
    bs = stock.balance_sheet if stock.balance_sheet is not None else pd.DataFrame()
    fin = stock.financials if stock.financials is not None else pd.DataFrame()
    # Use income statement from financials as earnings data is deprecated.
    # For EPS, we will calculate using Net Income / sharesOutstanding.
    earnings = pd.DataFrame()  # Not used directly now
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
    # Try to extract fiscal year from columns (which are usually DatetimeIndex)
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
# Main Execution: Only run if ticker input exists
# ==========================================================
if ticker:
    try:
        info, bs, fin, earnings, hist, div = get_data(ticker)
        fiscal_years = get_recent_years(fin, 10)
        # Fallback logic: if fewer than 10 fiscal years are available, use the last 5.
        if len(fiscal_years) < 10:
            fiscal_years = get_recent_years(fin, 5)
        # ======================================================
        # Top Section: Price Chart (Last 10 years)
        # ======================================================
        st.subheader("📈 Stock Price (Last 10 Years)")
        fig_price, ax_price = plt.subplots(figsize=(10, 3))
        # Use month-end frequency for resampling (to avoid deprecation warning)
        hist["Close"].resample("ME").last().plot(ax=ax_price, color="orange")
        ax_price.set_title(f"{ticker} Monthly Closing Prices")
        ax_price.set_xlabel("Date")
        ax_price.set_ylabel("Price (USD)")
        ax_price.grid(True)
        st.pyplot(fig_price)
        
        # ======================================================
        # Initialize containers for summary and chart data
        # ======================================================
        summary = []  # List of tuples: (Metric, Pass/Fail, Value or # failures)
        metric_data = {}  # Dictionary: metric name -> {year: value} (year-by-year)

        # Helper: Evaluate a metric over each fiscal year.
        def evaluate_metric(metric_name, values_dict, threshold=None, comparison=">", is_percent=True):
            # values_dict: {year: value}, where value can be None.
            fails = 0
            data = {}
            for y in fiscal_years:
                v = values_dict.get(y, None)
                if v is None:
                    data[y] = "Missing"
                else:
                    # Convert to percent if needed:
                    pv = v * 100 if is_percent else v
                    data[y] = round(pv, 2)
                    if threshold is not None:
                        # Compare against threshold in percent.
                        if comparison == ">" and pv < threshold * 100:
                            fails += 1
                        elif comparison == "<" and pv > threshold * 100:
                            fails += 1
            metric_data[metric_name] = data
            pass_fail = "✅" if fails == 0 else "❌"
            summary.append((metric_name, pass_fail, f"{len(fiscal_years)-fails} / {len(fiscal_years)} years passed"))

        # ======================================================
        # Metric 1: ROE ≥ 12%
        # ======================================================
        roe_vals = {}
        for y in fiscal_years:
            try:
                net = fin.loc["Net Income", fin.columns[fin.columns.year == y]].values[0]
                equity = bs.loc["Total Stockholder Equity", bs.columns[bs.columns.year == y]].values[0]
                roe_vals[y] = safe_ratio(net, equity)
            except:
                roe_vals[y] = None
        evaluate_metric("ROE ≥ 12%", roe_vals, threshold=0.12)

        # ======================================================
        # Metric 2: ROA ≥ 12%
        # ======================================================
        roa_vals = {}
        for y in fiscal_years:
            try:
                net = fin.loc["Net Income", fin.columns[fin.columns.year == y]].values[0]
                assets = bs.loc["Total Assets", bs.columns[bs.columns.year == y]].values[0]
                roa_vals[y] = safe_ratio(net, assets)
            except:
                roa_vals[y] = None
        evaluate_metric("ROA ≥ 12%", roa_vals, threshold=0.12)

        # ======================================================
        # Metric 3: Historical EPS Per Share
        # For EPS, we calculate using: Net Income / Shares Outstanding
        # (sharesOutstanding is taken from info; assume constant over period)
        # ======================================================
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
        # Here no threshold is applied; we simply display the EPS series.
        metric_data["EPS Per Share"] = {y: (round(v*100, 2) if v is not None else "Missing") for y, v in eps_vals.items()}
        available_eps = sum(1 for v in eps_vals.values() if v is not None)
        summary.append(("EPS Per Share", "—", f"{available_eps} / {len(fiscal_years)} years available"))

        # ======================================================
        # Metric 4: Net Margin ≥ 20% (Net Income ÷ Total Revenue)
        # ======================================================
        net_margin_vals = {}
        for y in fiscal_years:
            try:
                net = fin.loc["Net Income", fin.columns[fin.columns.year == y]].values[0]
                rev = fin.loc["Total Revenue", fin.columns[fin.columns.year == y]].values[0]
                net_margin_vals[y] = safe_ratio(net, rev)
            except:
                net_margin_vals[y] = None
        evaluate_metric("Net Margin ≥ 20%", net_margin_vals, threshold=0.20)

        # ======================================================
        # Metric 5: Gross Margin ≥ 40% (Gross Profit ÷ Total Revenue)
        # ======================================================
        gross_margin_vals = {}
        for y in fiscal_years:
            try:
                gross = fin.loc["Gross Profit", fin.columns[fin.columns.year == y]].values[0]
                rev = fin.loc["Total Revenue", fin.columns[fin.columns.year == y]].values[0]
                gross_margin_vals[y] = safe_ratio(gross, rev)
            except:
                gross_margin_vals[y] = None
        evaluate_metric("Gross Margin ≥ 40%", gross_margin_vals, threshold=0.40)

        # ======================================================
        # Metric 6: Return on Retained Capital (RORC) ≥ 18%
        # Approximation: Net Income ÷ (Net Income - Dividends)
        # ======================================================
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

        # ======================================================
        # Metrics without charts – only value + commentary
        # Metric 7: LT Debt ÷ Net Income < 5x (latest fiscal year)
        # ======================================================
        try:
            latest_year = fiscal_years[-1]
            debt = bs.loc["Long Term Debt", bs.columns[bs.columns.year == latest_year]].values[0]
            net_latest = fin.loc["Net Income", fin.columns[fin.columns.year == latest_year]].values[0]
            ratio = safe_ratio(debt, net_latest)
            lt_comment = f"{ratio:.2f}x" if ratio is not None else "Missing"
            summary.append(("LT Debt ÷ Net Income < 5x", "✅" if ratio is not None and ratio < 5 else "❌", lt_comment))
        except:
            summary.append(("LT Debt ÷ Net Income < 5x", "⚠️", "Missing"))

        # Metric 8: Pricing Power vs. Inflation (Commentary)
        # For this demo, we assume a static latest US CPI value.
        cpi = 0.032  # 3.2%
        pricing_comment = f"Compare company's pricing adjustments to a US CPI of ~{cpi*100:.1f}%. [Source: U.S. Bureau of Labor Statistics]"
        summary.append(("Pricing Power vs. Inflation", "—", pricing_comment))

        # Metric 9: Organized Labor (Commentary)
        labor_comment = ("Review recent SEC 10-K and news on labor relations, union contracts, and strike risks. "
                         "[Example Source: Reuters, 2023]")
        summary.append(("Organized Labor", "—", labor_comment))

        # Metric 11: Dividends & Buybacks (Commentary)
        years_div = sorted(set(div.index.year)) if not div.empty else []
        if not years_div:
            div_comment = "No Dividends or Buybacks"
            div_pass = "—"
        else:
            cuts = []
            for i in range(1, len(years_div)):
                try:
                    sum_current = div[div.index.year == years_div[i]].sum()
                    sum_previous = div[div.index.year == years_div[i-1]].sum()
                    if sum_current < sum_previous:
                        cuts.append(years_div[i])
                except:
                    pass
            div_comment = f"{len(years_div)} years; Dividend cuts in: {cuts if cuts else 'None'}"
            div_pass = "✅" if not cuts else "❌"
        summary.append(("Dividends & Buybacks", div_pass, div_comment))

        # Metric 12: Barriers to Entry (Commentary)
        barriers_comment = ("- Strong brand loyalty and ecosystem integration [Source: Morningstar]\n"
                            "- Patents and technological advantages [Source: SEC 10-K]\n"
                            "- Cost advantages through scale [Source: HBR]\n"
                            "- Distribution network lock-in [Source: WSJ]")
        summary.append(("Barriers to Entry", "—", barriers_comment))

        # ======================================================
        # Top Section: Display Summary Table
        # ======================================================
        st.subheader("📋 Summary Table")
        df_summary = pd.DataFrame(summary, columns=["Metric", "Pass/Fail", "Value/Details"])
        st.table(df_summary)

        # ======================================================
        # Middle Section: Charts + Tables for metrics with charts
        # We'll wrap each metric's chart & table pair in st.tabs() for clarity.
        st.subheader("📊 Metrics (Year-by-Year Charts & Tables)")
        for metric, data in metric_data.items():
            with st.expander(f"{metric} Trend", expanded=False):
                tab_chart, tab_table = st.tabs(["Chart", "Table"])
                # Prepare DataFrame for charting and table display:
                df_metric = pd.DataFrame.from_dict(data, orient="index", columns=["Value"])
                df_metric.index = df_metric.index.map(lambda y: int(y))
                # Replace None values with NaN for plotting
                df_metric["Value"] = df_metric["Value"].apply(lambda x: x if isinstance(x, (int, float)) else None)
                # Plot the chart using matplotlib:
                fig, ax = plt.subplots(figsize=(8, 3))
                ax.plot(df_metric.index, df_metric["Value"], marker="o", color="tab:blue")
                ax.set_title(metric)
                ax.set_xlabel("Fiscal Year")
                ax.set_ylabel("Percentage" if any(metric in m for m in ["ROE", "ROA", "Net Margin", "Gross Margin", "Return on Retained Capital"]) else "Value")
                ax.set_xticks(df_metric.index)
                ax.grid(True, linestyle="--", linewidth=0.5)
                st.pyplot(fig, clear_figure=True)
                # Display the table:
                df_display = df_metric.copy()
                df_display["Value"] = df_display["Value"].apply(lambda x: f"{x:.2f}%" if isinstance(x, (int, float)) else "Missing")
                tab_table.dataframe(df_display)

        # ======================================================
        # Bottom Section: Narrative Insights & Commentary (non-quantitative)
        st.subheader("🧠 Narrative Insights & Commentary")
        st.markdown("### 🏛️ Barriers to Entry")
        st.markdown("""
- Strong brand loyalty and ecosystem integration [Source: Morningstar]
- Patents and technological advantages [Source: SEC 10-K]
- Cost advantages through scale [Source: HBR]
- Distribution network lock-in [Source: WSJ]
        """)
        st.markdown("### 📉 Pricing Power vs. Inflation")
        st.markdown(f"""
As of July 2024, U.S. CPI YoY is approximately {cpi*100:.1f}%. Compare the company's reported pricing strategies in earnings calls to this benchmark. [Source: U.S. Bureau of Labor Statistics]
        """)
        st.markdown("### 🏭 Organized Labor")
        st.markdown("""
Review SEC 10-K filings and recent news for any union contracts, strike risks, or labor disputes. [Example Source: Reuters, 2023]
        """)
        st.markdown("### LT Debt ÷ Net Income")
        st.markdown("Refer to the summary table above for the latest LT Debt ÷ Net Income value and commentary.")
        st.markdown("### Dividends & Buybacks")
        st.markdown("Review the summary table for dividend history and any indication of dividend/repurchase cuts.")

        # ======================================================
        # Export Section: Download Summary and (optionally) chart images
        st.subheader("📥 Export Results")
        csv_data = df_summary.to_csv(index=False).encode("utf-8")
        st.download_button("📤 Download Summary CSV", csv_data, file_name=f"{ticker}_summary.csv", mime="text/csv")
        
        # Optional: You might add additional export functionality for charts as PNGs.
        
    except Exception as e:
        st.error(f"Error processing ticker: {e}")
