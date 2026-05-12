import tempfile
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
import yaml

import backtest
from cloud_store import CloudStore, default_terminal_id


APP_NAME = "TradeTest"

st.set_page_config(page_title=APP_NAME, page_icon="TT", layout="wide")
st.title(APP_NAME)
st.caption("Backtest workspace with guided config, YAML upload, cloud history, and report download.")

DEFAULT_UPLOAD_CONFIG = """data:
  symbols:
    VFV.TO: "VFV"
    QQC.TO: "QQC"
    TSLA.NE: "Tesla CDR CAD"
  start: "2021-05-10"
  end: null

account:
  initial_cash: 10000

costs:
  commission: 1.0
  slippage: 0.001

strategy:
  type: "monthly_rebalance"
  execution_timing: "next_open"
  target_weights:
    VFV.TO: 0.55
    QQC.TO: 0.35
    TSLA.NE: 0.10
  rebalance_frequency: "monthly"
  rebalance_threshold: 0.05
  max_weights:
    VFV.TO: 0.70
    QQC.TO: 0.45
    TSLA.NE: 0.15
  min_weights:
    VFV.TO: 0.40
    QQC.TO: 0.20
    TSLA.NE: 0.00
  cash_buffer: 0.02

report:
  output_dir: "results"
"""


def run_backtest_from_cfg(cfg: dict, config_text_raw: str):
    symbols, symbol_names = backtest.parse_symbols(cfg)
    start = cfg["data"]["start"]
    end = cfg["data"].get("end")

    initial_cash = float(cfg["account"]["initial_cash"])
    commission = float(cfg["costs"]["commission"])
    slippage = float(cfg["costs"]["slippage"])

    strategy_cfg = cfg.get("strategy", {})
    strategy_type = str(strategy_cfg.get("type", "ma_crossover")).strip().lower()
    execution_timing = str(strategy_cfg.get("execution_timing", "next_open")).strip().lower()
    fast_ma = int(strategy_cfg.get("fast_ma", 20))
    slow_ma = int(strategy_cfg.get("slow_ma", 60))

    open_prices, close_prices = backtest.download_prices(symbols, start, end)

    if strategy_type == "monthly_rebalance":
        portfolio_df, trades_df = backtest.run_periodic_rebalance(
            open_prices, close_prices, initial_cash, commission, slippage, strategy_cfg, execution_timing
        )
    else:
        if fast_ma <= 0 or slow_ma <= 0 or fast_ma >= slow_ma:
            raise ValueError("Invalid MA params: require 0 < fast_ma < slow_ma")
        portfolio_df, trades_df = backtest.run_ma_portfolio(
            open_prices, close_prices, initial_cash, commission, slippage, fast_ma, slow_ma, execution_timing
        )

    final_equity = float(portfolio_df["equity"].iloc[-1])
    total_return = final_equity / initial_cash - 1.0
    mdd = backtest.max_drawdown(portfolio_df["equity"])
    buy_hold_return = sum(float(close_prices[s].iloc[-1] / close_prices[s].iloc[0] - 1.0) for s in symbols) / len(symbols)
    rebalance_frequency = str(strategy_cfg.get("rebalance_frequency", "monthly")).strip().lower()

    summary = {
        "strategy_type": strategy_type,
        "execution_timing": execution_timing,
        "rebalance_frequency": rebalance_frequency if strategy_type == "monthly_rebalance" else "",
        "symbols": ",".join(symbols),
        "symbol_names": ",".join([f"{k}:{symbol_names.get(k, k)}" for k in symbols]),
        "start": str(pd.to_datetime(portfolio_df["Date"].iloc[0]).date()),
        "end": str(pd.to_datetime(portfolio_df["Date"].iloc[-1]).date()),
        "initial_cash": initial_cash,
        "final_equity": final_equity,
        "total_return": total_return,
        "max_drawdown": mdd,
        "trade_count": int((trades_df["action"] == "BUY").sum()) if not trades_df.empty else 0,
        "buy_hold_return": buy_hold_return,
    }

    with tempfile.TemporaryDirectory() as td:
        temp_dir = Path(td)
        cfg_path = temp_dir / "web_config.yaml"
        cfg_path.write_text(config_text_raw, encoding="utf-8")
        backtest.save_outputs(temp_dir, portfolio_df, trades_df, summary, cfg, cfg_path)
        report_file = sorted(temp_dir.glob("backtest_report_*.xlsx"))[-1]
        chart_files = sorted(temp_dir.glob("equity_curve_*.png"))
        report_bytes = report_file.read_bytes()
        chart_bytes = chart_files[-1].read_bytes() if chart_files else None

    return summary, portfolio_df, trades_df, report_bytes, chart_bytes


def render_result(summary, portfolio_df, trades_df, report_bytes):
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Final Equity", f"{summary['final_equity']:.2f}")
    m2.metric("Total Return", f"{summary['total_return']:.2%}")
    m3.metric("Max Drawdown", f"{summary['max_drawdown']:.2%}")
    m4.metric("Trade Count", str(summary["trade_count"]))

    fig = px.line(portfolio_df, x="Date", y="equity", title="Portfolio Equity Curve")
    fig.update_layout(height=460, margin=dict(l=16, r=16, t=48, b=16))
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(pd.DataFrame([summary]), use_container_width=True)
    empty_cols = ["date", "symbol", "action", "price", "shares", "commission", "cash_after"]
    st.dataframe(trades_df if not trades_df.empty else pd.DataFrame(columns=empty_cols), use_container_width=True, height=280)

    st.download_button(
        "Download Excel report",
        data=report_bytes,
        file_name="backtest_report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )


def build_cfg_from_wizard(
    mode_strategy,
    symbol_text,
    start,
    end,
    initial_cash,
    commission,
    slippage,
    execution_timing,
    fast_ma,
    slow_ma,
    rebalance_frequency,
    rebalance_threshold,
    cash_buffer,
):
    symbols = [s.strip() for s in symbol_text.split(",") if s.strip()]
    if not symbols:
        raise ValueError("At least one ticker is required")

    data_part = {"start": str(start), "end": str(end) if end else None}
    if len(symbols) == 1:
        data_part["symbol"] = symbols[0]
    else:
        data_part["symbols"] = {s: s for s in symbols}

    cfg = {
        "data": data_part,
        "account": {"initial_cash": float(initial_cash)},
        "costs": {"commission": float(commission), "slippage": float(slippage)},
        "strategy": {"type": mode_strategy, "execution_timing": execution_timing},
        "report": {"output_dir": "results"},
    }

    if mode_strategy == "monthly_rebalance":
        weight = 1.0 / len(symbols)
        cfg["strategy"].update(
            {
                "target_weights": {s: weight for s in symbols},
                "rebalance_frequency": rebalance_frequency,
                "rebalance_threshold": float(rebalance_threshold),
                "cash_buffer": float(cash_buffer),
                "max_weights": {s: min(1.0, weight * 1.5) for s in symbols},
                "min_weights": {s: 0.0 for s in symbols},
            }
        )
    else:
        cfg["strategy"].update({"fast_ma": int(fast_ma), "slow_ma": int(slow_ma)})
    return cfg


cloud = CloudStore()
with st.sidebar:
    st.header("Cloud")
    terminal_id = st.text_input("Terminal ID", value=default_terminal_id())
    config_name = st.text_input("Config name", value="web_config")
    if cloud.enabled:
        st.success("Cloud sync enabled")
    else:
        st.info("Set SUPABASE_URL and SUPABASE_KEY to enable cloud sync")

main_tab, history_tab = st.tabs(["Run", "History"])

with main_tab:
    mode = st.radio("Config source", ["Guided form", "Upload YAML"], horizontal=True)

    if mode == "Guided form":
        with st.form("wizard_form"):
            c1, c2, c3 = st.columns(3)
            mode_strategy = c1.selectbox("Strategy", ["monthly_rebalance", "ma_crossover"], index=0)
            execution_timing = c2.selectbox("Execution", ["next_open"], index=0)
            rebalance_frequency = c3.selectbox("Rebalance", ["daily", "weekly", "monthly"], index=2)

            c4, c5, c6 = st.columns(3)
            start = c4.date_input("Start", value=pd.to_datetime("2021-05-10").date())
            end = c5.date_input("End", value=None)
            symbol_text = c6.text_input("Tickers", value="VFV.TO,QQC.TO,TSLA.NE")

            c7, c8, c9 = st.columns(3)
            initial_cash = c7.number_input("Initial cash", min_value=1.0, value=10000.0, step=1000.0)
            commission = c8.number_input("Commission", min_value=0.0, value=1.0, step=0.1)
            slippage = c9.number_input("Slippage", min_value=0.0, value=0.001, step=0.0001, format="%.4f")

            c10, c11, c12, c13 = st.columns(4)
            fast_ma = c10.number_input("Fast MA", min_value=1, value=20, step=1)
            slow_ma = c11.number_input("Slow MA", min_value=2, value=60, step=1)
            rebalance_threshold = c12.number_input("Threshold", min_value=0.0, value=0.05, step=0.01, format="%.2f")
            cash_buffer = c13.number_input("Cash buffer", min_value=0.0, value=0.02, step=0.01, format="%.2f")

            run_clicked = st.form_submit_button("Run backtest", type="primary", use_container_width=True)

        if run_clicked:
            try:
                cfg = build_cfg_from_wizard(
                    mode_strategy,
                    symbol_text,
                    start,
                    end,
                    initial_cash,
                    commission,
                    slippage,
                    execution_timing,
                    fast_ma,
                    slow_ma,
                    rebalance_frequency,
                    rebalance_threshold,
                    cash_buffer,
                )
                cfg_text = yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True)
                st.code(cfg_text, language="yaml")
                summary, portfolio_df, trades_df, report_bytes, chart_bytes = run_backtest_from_cfg(cfg, cfg_text)
                saved = cloud.save_run(
                    terminal_id=terminal_id,
                    config_name=config_name,
                    config_yaml=cfg_text,
                    summary=summary,
                    report_bytes=report_bytes,
                    chart_bytes=chart_bytes,
                )
                if saved:
                    st.toast("Saved to cloud")
                render_result(summary, portfolio_df, trades_df, report_bytes)
            except Exception as e:
                st.error(f"Run failed: {e}")

    else:
        if "config_text" not in st.session_state:
            st.session_state.config_text = DEFAULT_UPLOAD_CONFIG
        uploaded = st.file_uploader("Upload YAML config", type=["yaml", "yml"])
        if uploaded is not None:
            st.session_state.config_text = uploaded.getvalue().decode("utf-8")
        config_text = st.text_area("YAML", value=st.session_state.config_text, height=420)
        st.session_state.config_text = config_text

        if st.button("Run backtest", type="primary", use_container_width=True):
            try:
                cfg = yaml.safe_load(config_text)
                summary, portfolio_df, trades_df, report_bytes, chart_bytes = run_backtest_from_cfg(cfg, config_text)
                saved = cloud.save_run(
                    terminal_id=terminal_id,
                    config_name=config_name,
                    config_yaml=config_text,
                    summary=summary,
                    report_bytes=report_bytes,
                    chart_bytes=chart_bytes,
                )
                if saved:
                    st.toast("Saved to cloud")
                render_result(summary, portfolio_df, trades_df, report_bytes)
            except Exception as e:
                st.error(f"Run failed: {e}")

with history_tab:
    if not cloud.enabled:
        st.info("Cloud history is disabled until SUPABASE_URL and SUPABASE_KEY are set.")
    else:
        try:
            runs = cloud.list_runs()
            if not runs:
                st.info("No saved runs yet.")
            else:
                df = pd.DataFrame(runs)
                st.dataframe(
                    df[
                        [
                            "created_at",
                            "terminal_id",
                            "config_name",
                            "strategy_type",
                            "symbols",
                            "total_return",
                            "max_drawdown",
                            "trade_count",
                            "report_xlsx_url",
                        ]
                    ],
                    use_container_width=True,
                    height=420,
                )
                selected = st.selectbox("Open run", df["id"].tolist(), format_func=lambda x: f"{df[df['id'] == x].iloc[0]['created_at']} | {df[df['id'] == x].iloc[0]['config_name']}")
                row = df[df["id"] == selected].iloc[0]
                st.code(row["config_yaml"], language="yaml")
                if row.get("chart_png_url"):
                    st.image(row["chart_png_url"], use_container_width=True)
                if row.get("report_xlsx_url"):
                    st.link_button("Open Excel report", row["report_xlsx_url"], use_container_width=True)
        except Exception as e:
            st.error(f"Could not load cloud history: {e}")

