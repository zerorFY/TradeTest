
import hashlib
import os
import shutil
import tempfile
from pathlib import Path
from uuid import uuid4

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yaml

import backtest
import rule_engine
import yaml_builder
from cloud_store import CloudStore, default_terminal_id


APP_NAME = "TradeTest"

STANDARD_MA_TEMPLATE = yaml_builder.config_to_yaml(
    yaml_builder.build_moving_average_config(
        market="western",
        symbol="AAPL",
        start="2020-01-01",
        end=None,
        initial_cash=10000,
        execution_price="next_open",
        commission_pct=0.001,
        slippage_pct=0.001,
        short_window=20,
        long_window=60,
    )
)

STANDARD_RSI_TEMPLATE = yaml_builder.config_to_yaml(
    yaml_builder.build_rsi_reversal_config(
        market="western",
        symbol="AAPL",
        start="2020-01-01",
        end=None,
        initial_cash=10000,
        execution_price="next_open",
        commission_pct=0.001,
        slippage_pct=0.001,
        rsi_window=14,
        entry_threshold=30,
        exit_threshold=70,
    )
)

LEGACY_PORTFOLIO_TEMPLATE = """data:
  market: "western"
  symbols:
    VFV.TO: "VFV"
    QQC.TO: "QQC"
    TSLA.NE: "Tesla CDR CAD"
  start: "2021-05-10"
  end: null

account:
  initial_cash: 10000
  currency: "MARKET_NATIVE"

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
  cash_buffer: 0.02

report:
  output_dir: "results"
"""

TEXT = {
    "zh": {
        "app_subtitle": "Daily Stock & ETF Backtesting Engine",
        "language": "Language / ??",
        "new_backtest": "????",
        "cloud_history": "????",
        "docs": "??",
        "cloud": "??",
        "terminal_id": "?? ID",
        "config_name": "????",
        "cloud_enabled": "???????",
        "cloud_disabled": "?? SUPABASE_URL ? SUPABASE_KEY ????????",
        "data_settings": "????",
        "input_method": "????",
        "strategy_settings": "????",
        "yaml_preview": "YAML ?? / ????",
        "run_backtest": "???? (Run Backtest)",
        "results": "????",
        "manual_strategy": "????",
        "upload_yaml": "?? YAML",
        "market": "??",
        "western": "????",
        "china": "?? A ?",
        "symbol": "?? Symbol",
        "start": "????",
        "end": "????",
        "initial_cash": "????",
        "execution_price": "????",
        "commission_pct": "????",
        "slippage_pct": "??",
        "strategy_type": "????",
        "ma_cross": "????",
        "rsi_reversal": "RSI ??",
        "short_window": "???",
        "long_window": "???",
        "rsi_window": "RSI ??",
        "entry_threshold": "????",
        "exit_threshold": "????",
        "coming_next": "Breakout / Bollinger Band ????????",
        "copy_yaml": "?? YAML",
        "edit_yaml": "?? YAML",
        "upload_config": "?? YAML ??",
        "yaml_tip": "???????? YAML??? YAML ?????? parser ? engine?",
        "run_failed": "????",
        "saved_to_cloud": "??????",
        "export_report": "?? Excel ??",
        "total_return": "????",
        "annual_return": "?????",
        "max_drawdown": "????",
        "sharpe_ratio": "????",
        "win_rate": "??",
        "trade_count": "????",
        "profit_factor": "???",
        "buy_hold_return": "??????",
        "equity_curve": "????",
        "drawdown_curve": "????",
        "recent_trades": "??????",
        "history_intro": "???????????YAML???? Excel ???",
        "history_disabled": "????????",
        "no_runs": "???????????",
        "open_run": "????",
        "open_report": "?? Excel ??",
        "risk": "????????????????????????????????????????",
    },
    "en": {
        "app_subtitle": "Daily Stock & ETF Backtesting Engine",
        "language": "Language / ??",
        "new_backtest": "New Backtest",
        "cloud_history": "Cloud History",
        "docs": "Docs",
        "cloud": "Cloud",
        "terminal_id": "Terminal ID",
        "config_name": "Config Name",
        "cloud_enabled": "Cloud sync enabled",
        "cloud_disabled": "Set SUPABASE_URL and SUPABASE_KEY to enable cloud sync",
        "data_settings": "Data Settings",
        "input_method": "Input Method",
        "strategy_settings": "Strategy Settings",
        "yaml_preview": "YAML Preview / Advanced Edit",
        "run_backtest": "Run Backtest",
        "results": "Backtest Results",
        "manual_strategy": "Manual Strategy",
        "upload_yaml": "Upload YAML",
        "market": "Market",
        "western": "Western Market",
        "china": "China A-share",
        "symbol": "Symbol",
        "start": "Start Date",
        "end": "End Date",
        "initial_cash": "Initial Cash",
        "execution_price": "Execution Price",
        "commission_pct": "Commission Rate",
        "slippage_pct": "Slippage",
        "strategy_type": "Strategy Type",
        "ma_cross": "Moving Average Cross",
        "rsi_reversal": "RSI Reversal",
        "short_window": "Short Window",
        "long_window": "Long Window",
        "rsi_window": "RSI Window",
        "entry_threshold": "Entry Threshold",
        "exit_threshold": "Exit Threshold",
        "coming_next": "Breakout / Bollinger Band will be supported in the next release.",
        "copy_yaml": "Download YAML",
        "edit_yaml": "Edit YAML",
        "upload_config": "Upload YAML Config",
        "yaml_tip": "Manual strategy generates YAML first; uploaded YAML uses the same parser and engine.",
        "run_failed": "Run failed",
        "saved_to_cloud": "Saved to cloud",
        "export_report": "Export Excel Report",
        "total_return": "Total Return",
        "annual_return": "Annual Return",
        "max_drawdown": "Max Drawdown",
        "sharpe_ratio": "Sharpe Ratio",
        "win_rate": "Win Rate",
        "trade_count": "Trade Count",
        "profit_factor": "Profit Factor",
        "buy_hold_return": "Buy & Hold Return",
        "equity_curve": "Equity Curve",
        "drawdown_curve": "Drawdown Curve",
        "recent_trades": "Recent Trades",
        "history_intro": "Cloud history stores backtest summaries, YAML configs, charts, and Excel reports.",
        "history_disabled": "Cloud history is disabled.",
        "no_runs": "No saved runs yet.",
        "open_run": "Open Run",
        "open_report": "Open Excel Report",
        "risk": "Disclaimer: Information is for research only and is not investment advice. Investing involves risk.",
    },
}


def tr(lang: str, key: str) -> str:
    return TEXT[lang].get(key, key)


def get_streamlit_secrets() -> dict:
    try:
        return dict(st.secrets)
    except Exception:
        return {}


def fmt_pct(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "--"
    return f"{float(value):+.2%}"


def fmt_num(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "--"
    if value == float("inf"):
        return "?"
    return f"{float(value):,.2f}"


def writable_temp_parent() -> Path:
    candidates = []
    if os.environ.get("TRADETEST_TMP_DIR"):
        candidates.append(Path(os.environ["TRADETEST_TMP_DIR"]))
    candidates.append(backtest.PROJECT_ROOT / ".web_tmp")
    candidates.append(Path(tempfile.gettempdir()) / "tradetest_web_tmp")
    if os.name == "nt":
        candidates.append(Path(r"C:\tmp") / "tradetest_web_tmp")

    errors = []
    for parent in candidates:
        try:
            parent.mkdir(parents=True, exist_ok=True)
            probe = parent / f".probe_{uuid4().hex}"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return parent
        except OSError as exc:
            errors.append(f"{parent}: {exc}")
    raise PermissionError("No writable temporary directory is available. " + " | ".join(errors))


def normalize_legacy_config(cfg: dict) -> dict:
    return backtest.prepare_config(cfg)


def run_legacy_backtest(cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame, dict, dict]:
    cfg = normalize_legacy_config(cfg)
    market = backtest.parse_market(cfg)
    currency = cfg.get("account", {}).get("currency", backtest.currency_for_market(market))
    symbols, symbol_names = backtest.parse_symbols(cfg)
    start = cfg["data"]["start"]
    end = cfg["data"].get("end")
    initial_cash = float(cfg["account"]["initial_cash"])
    commission = float(cfg["costs"]["commission"])
    slippage = float(cfg["costs"]["slippage"])
    strategy_cfg = cfg.get("strategy", {})
    strategy_type = str(strategy_cfg.get("type", "ma_crossover")).strip().lower()
    execution_timing = str(strategy_cfg.get("execution_timing", "next_open")).strip().lower()
    open_prices, close_prices = backtest.download_prices(symbols, start, end)

    if strategy_type == "monthly_rebalance":
        portfolio_df, trades_df = backtest.run_periodic_rebalance(open_prices, close_prices, initial_cash, commission, slippage, strategy_cfg, execution_timing)
    else:
        fast_ma = int(strategy_cfg.get("fast_ma", 20))
        slow_ma = int(strategy_cfg.get("slow_ma", 60))
        portfolio_df, trades_df = backtest.run_ma_portfolio(open_prices, close_prices, initial_cash, commission, slippage, fast_ma, slow_ma, execution_timing)

    final_equity = float(portfolio_df["equity"].iloc[-1])
    total_return = final_equity / initial_cash - 1.0
    portfolio_df["drawdown"] = portfolio_df["equity"] / portfolio_df["equity"].cummax() - 1.0
    bh_returns = [float(close_prices[s].iloc[-1] / close_prices[s].iloc[0] - 1.0) for s in symbols]
    daily_returns = portfolio_df["equity"].pct_change().dropna()
    sharpe = float(daily_returns.mean() / daily_returns.std() * (252 ** 0.5)) if len(daily_returns) > 1 and daily_returns.std() > 0 else 0.0
    days = max(1, int((pd.to_datetime(portfolio_df["Date"].iloc[-1]) - pd.to_datetime(portfolio_df["Date"].iloc[0])).days))
    annual_return = (1 + total_return) ** (365.25 / days) - 1 if total_return > -1 else -1.0
    summary = {
        "market": market,
        "currency": currency,
        "strategy_type": strategy_type,
        "strategy_name": strategy_type,
        "execution_timing": execution_timing,
        "rebalance_frequency": str(strategy_cfg.get("rebalance_frequency", "")),
        "symbols": ",".join(symbols),
        "symbol_names": ",".join([f"{k}:{symbol_names.get(k, k)}" for k in symbols]),
        "start": str(pd.to_datetime(portfolio_df["Date"].iloc[0]).date()),
        "end": str(pd.to_datetime(portfolio_df["Date"].iloc[-1]).date()),
        "initial_cash": initial_cash,
        "final_equity": final_equity,
        "total_return": total_return,
        "annual_return": annual_return,
        "max_drawdown": float(portfolio_df["drawdown"].min()),
        "sharpe_ratio": sharpe,
        "win_rate": 0.0,
        "trade_count": int((trades_df["action"] == "BUY").sum()) if not trades_df.empty else 0,
        "average_holding_days": 0.0,
        "profit_factor": 0.0,
        "cost_adjusted_return": total_return,
        "buy_hold_return": float(sum(bh_returns) / len(bh_returns)) if bh_returns else 0.0,
    }
    return portfolio_df, trades_df, summary, cfg


def save_report(portfolio_df: pd.DataFrame, trades_df: pd.DataFrame, summary: dict, cfg: dict, config_yaml: str) -> tuple[bytes, bytes | None]:
    temp_parent = writable_temp_parent()
    temp_dir = temp_parent / f"run_{uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        cfg_path = temp_dir / "web_config.yaml"
        cfg_path.write_text(config_yaml, encoding="utf-8")
        backtest.save_outputs(temp_dir, portfolio_df, trades_df, summary, cfg, cfg_path)
        report_file = sorted(temp_dir.glob("backtest_report_*.xlsx"))[-1]
        chart_files = sorted(temp_dir.glob("equity_curve_*.png"))
        return report_file.read_bytes(), chart_files[-1].read_bytes() if chart_files else None
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def run_yaml_backtest(config_text: str) -> tuple[dict, pd.DataFrame, pd.DataFrame, bytes, bytes | None, str]:
    cfg = yaml.safe_load(config_text)
    if not isinstance(cfg, dict):
        raise ValueError("YAML must be a mapping.")
    if rule_engine.is_standard_rule_config(cfg):
        portfolio_df, trades_df, summary, prepared_cfg = rule_engine.run_rule_backtest(cfg)
    else:
        portfolio_df, trades_df, summary, prepared_cfg = run_legacy_backtest(cfg)
    prepared_yaml = yaml.safe_dump(prepared_cfg, sort_keys=False, allow_unicode=True)
    report_bytes, chart_bytes = save_report(portfolio_df, trades_df, summary, prepared_cfg, prepared_yaml)
    return summary, portfolio_df, trades_df, report_bytes, chart_bytes, prepared_yaml


def save_cloud_run_safely(cloud: CloudStore, terminal_id: str, config_name: str, config_yaml: str, summary: dict, report_bytes: bytes, chart_bytes: bytes | None, lang: str) -> None:
    if not cloud.enabled:
        return
    try:
        saved = cloud.save_run(terminal_id=terminal_id, config_name=config_name, config_yaml=config_yaml, summary=summary, report_bytes=report_bytes, chart_bytes=chart_bytes)
        if saved:
            st.toast(tr(lang, "saved_to_cloud"))
    except Exception as exc:
        st.warning(f"Cloud save failed: {exc}")


def build_manual_yaml(
    market: str,
    symbol: str,
    start: str,
    end: str,
    initial_cash: float,
    execution_price: str,
    commission_pct: float,
    slippage_pct: float,
    strategy_type: str,
    short_window: int,
    long_window: int,
    rsi_window: int,
    entry_threshold: float,
    exit_threshold: float,
) -> str:
    if strategy_type == "moving_average_cross":
        cfg = yaml_builder.build_moving_average_config(market, symbol, start, end or None, initial_cash, execution_price, commission_pct, slippage_pct, short_window, long_window)
    elif strategy_type == "rsi_reversal":
        cfg = yaml_builder.build_rsi_reversal_config(market, symbol, start, end or None, initial_cash, execution_price, commission_pct, slippage_pct, rsi_window, entry_threshold, exit_threshold)
    else:
        raise ValueError("Only Moving Average Cross and RSI Reversal are supported in V2 first release.")
    return yaml_builder.config_to_yaml(cfg)


def inject_css() -> None:
    st.markdown(
        """
<style>
:root { --navy:#061727; --panel:#ffffff; --muted:#64748b; --line:#d8e1ec; --teal:#00a99d; --teal2:#18c4b5; --danger:#dc2626; }
.stApp { background: linear-gradient(180deg, #f5f8fc 0%, #eef4f8 100%); color:#0f172a; }
[data-testid="stSidebar"] { background: linear-gradient(180deg, #061727 0%, #08243c 100%); }
[data-testid="stSidebar"] * { color:#e5edf7 !important; }
.block-container { padding-top: 0.85rem; max-width: 1800px; }
.trade-header { background:linear-gradient(90deg,#061727,#08213a); color:white; padding:16px 22px; border-radius:0 0 18px 18px; margin-bottom:14px; display:flex; align-items:center; justify-content:space-between; box-shadow:0 10px 28px rgba(6,23,39,.18); }
.brand { font-size:24px; font-weight:800; letter-spacing:-.02em; }
.subtitle { color:#b6c7d8; font-size:13px; margin-left:12px; }
.card { background:white; border:1px solid #d9e3ee; border-radius:12px; padding:16px; box-shadow:0 8px 22px rgba(15,23,42,.05); }
.card h3 { margin:0 0 14px 0; font-size:16px; }
.stepbar { display:grid; grid-template-columns:repeat(6,1fr); gap:10px; margin:8px 0 16px; }
.step { background:#fff; border:1px solid #d9e3ee; border-radius:999px; padding:9px 12px; font-size:13px; color:#475569; display:flex; align-items:center; gap:8px; }
.step b { background:#cbd5e1; color:#0f172a; border-radius:999px; width:24px; height:24px; display:inline-flex; align-items:center; justify-content:center; }
.step.active b { background:linear-gradient(135deg,#00a99d,#1dd3c3); color:white; }
.metric-grid { display:grid; grid-template-columns:repeat(8,1fr); gap:10px; }
.metric-card { background:#fff; border:1px solid #d9e3ee; border-radius:12px; padding:13px; }
.metric-label { color:#64748b; font-size:12px; }
.metric-value { color:#0f766e; font-size:22px; font-weight:800; margin-top:6px; }
.metric-value.negative { color:#dc2626; }
.footer-note { color:#94a3b8; font-size:12px; text-align:center; padding:10px; }
.stButton > button[kind="primary"] { background:linear-gradient(135deg,#00a99d,#12c8b6) !important; border:0 !important; color:white !important; font-weight:800 !important; border-radius:10px !important; box-shadow:0 10px 22px rgba(0,169,157,.28); }
.stButton > button[kind="secondary"] { border-color:#b7c7d8 !important; color:#0f172a !important; border-radius:10px !important; }
pre { border-radius:10px !important; }
@media (max-width: 1100px) { .stepbar { grid-template-columns:repeat(2,1fr); } .metric-grid { grid-template-columns:repeat(2,1fr); } }
</style>
""",
        unsafe_allow_html=True,
    )


def render_header(lang: str) -> None:
    st.markdown(
        f"""
<div class="trade-header">
  <div><span class="brand">TradeTest</span><span class="subtitle">{tr(lang, 'app_subtitle')}</span></div>
  <div>{tr(lang, 'docs')} ? ? ? ?</div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_steps(lang: str, active: int = 3) -> None:
    labels = [tr(lang, "data_settings"), tr(lang, "input_method"), tr(lang, "strategy_settings"), tr(lang, "yaml_preview"), tr(lang, "run_backtest"), tr(lang, "results")]
    html = '<div class="stepbar">'
    for idx, label in enumerate(labels, start=1):
        klass = "step active" if idx in {1, active} else "step"
        html += f'<div class="{klass}"><b>{idx}</b><span>{label}</span></div>'
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def render_metric_cards(summary: dict, lang: str) -> None:
    items = [
        ("total_return", fmt_pct(summary.get("total_return"))),
        ("annual_return", fmt_pct(summary.get("annual_return"))),
        ("max_drawdown", fmt_pct(summary.get("max_drawdown"))),
        ("sharpe_ratio", fmt_num(summary.get("sharpe_ratio"))),
        ("win_rate", fmt_pct(summary.get("win_rate"))),
        ("trade_count", str(summary.get("trade_count", 0))),
        ("profit_factor", fmt_num(summary.get("profit_factor"))),
        ("buy_hold_return", fmt_pct(summary.get("buy_hold_return"))),
    ]
    html = '<div class="metric-grid">'
    for key, value in items:
        neg = " negative" if str(value).startswith("-") else ""
        html += f'<div class="metric-card"><div class="metric-label">{tr(lang, key)}</div><div class="metric-value{neg}">{value}</div></div>'
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def render_results(summary: dict, portfolio_df: pd.DataFrame, trades_df: pd.DataFrame, report_bytes: bytes, lang: str) -> None:
    st.markdown(f"### ? {tr(lang, 'results')} ({summary.get('start')} ? {summary.get('end')})")
    render_metric_cards(summary, lang)
    c1, c2, c3 = st.columns([1.25, 1.0, 1.0])
    with c1:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=portfolio_df["Date"], y=portfolio_df["equity"], name="Strategy", line=dict(color="#00a99d", width=2)))
        if "buy_hold_equity" in portfolio_df.columns:
            fig.add_trace(go.Scatter(x=portfolio_df["Date"], y=portfolio_df["buy_hold_equity"], name="Buy & Hold", line=dict(color="#94a3b8", width=1.5)))
        fig.update_layout(title=tr(lang, "equity_curve"), height=330, margin=dict(l=20, r=20, t=48, b=20), paper_bgcolor="white", plot_bgcolor="white")
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        drawdown = portfolio_df.get("drawdown")
        if drawdown is None:
            drawdown = portfolio_df["equity"] / portfolio_df["equity"].cummax() - 1.0
        fig = go.Figure(go.Scatter(x=portfolio_df["Date"], y=drawdown, fill="tozeroy", name="Drawdown", line=dict(color="#14b8a6")))
        fig.update_layout(title=tr(lang, "drawdown_curve"), height=330, margin=dict(l=20, r=20, t=48, b=20), paper_bgcolor="white", plot_bgcolor="white", yaxis_tickformat=".0%")
        st.plotly_chart(fig, use_container_width=True)
    with c3:
        st.markdown(f"**{tr(lang, 'recent_trades')}**")
        if trades_df.empty:
            st.info("No trades")
        else:
            cols = [c for c in ["date", "symbol", "action", "price", "shares", "pnl_pct", "holding_days"] if c in trades_df.columns]
            st.dataframe(trades_df[cols].tail(8), use_container_width=True, height=285)
        st.download_button(tr(lang, "export_report"), data=report_bytes, file_name="backtest_report.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True, key=f"download_result_report_{lang}")


def render_new_backtest(lang: str, cloud: CloudStore, terminal_id: str, config_name: str) -> None:
    render_steps(lang)
    input_method = st.radio(tr(lang, "input_method"), ["manual", "upload"], horizontal=True, format_func=lambda v: tr(lang, "manual_strategy") if v == "manual" else tr(lang, "upload_yaml"), key="v2_input_method")

    if input_method == "manual":
        left, mid, right = st.columns([0.85, 1.9, 1.55], gap="medium")
        with left:
            st.markdown(f"### ? {tr(lang, 'data_settings')}")
            market = st.radio(tr(lang, "market"), ["western", "china"], format_func=lambda v: tr(lang, v), horizontal=True, key="v2_market")
            default_symbol = "510300" if market == "china" else "AAPL"
            symbol = st.text_input(tr(lang, "symbol"), value=default_symbol, key=f"v2_symbol_{market}")
            start = st.text_input(tr(lang, "start"), value="2020-01-01", key="v2_start")
            end = st.text_input(tr(lang, "end"), value="", key="v2_end")
            initial_cash = st.number_input(tr(lang, "initial_cash"), min_value=1.0, value=10000.0 if market == "western" else 100000.0, step=1000.0, key=f"v2_cash_{market}")
            execution_price = st.selectbox(tr(lang, "execution_price"), ["next_open", "close"], index=0, key="v2_execution")
            commission_pct = st.number_input(tr(lang, "commission_pct"), min_value=0.0, value=0.001, step=0.0001, format="%.4f", key="v2_commission")
            slippage_pct = st.number_input(tr(lang, "slippage_pct"), min_value=0.0, value=0.001, step=0.0001, format="%.4f", key="v2_slippage")

        with mid:
            st.markdown(f"### ? {tr(lang, 'strategy_settings')}")
            strategy_type = st.selectbox(tr(lang, "strategy_type"), ["moving_average_cross", "rsi_reversal"], format_func=lambda v: tr(lang, "ma_cross") if v == "moving_average_cross" else tr(lang, "rsi_reversal"), key="v2_strategy")
            st.caption(tr(lang, "coming_next"))
            if strategy_type == "moving_average_cross":
                c1, c2 = st.columns(2)
                short_window = c1.number_input(tr(lang, "short_window"), min_value=1, value=20, step=1, key="v2_short")
                long_window = c2.number_input(tr(lang, "long_window"), min_value=2, value=60, step=1, key="v2_long")
                rsi_window, entry_threshold, exit_threshold = 14, 30.0, 70.0
            else:
                c1, c2, c3 = st.columns(3)
                rsi_window = c1.number_input(tr(lang, "rsi_window"), min_value=1, value=14, step=1, key="v2_rsi_window")
                entry_threshold = c2.number_input(tr(lang, "entry_threshold"), min_value=0.0, max_value=100.0, value=30.0, step=1.0, key="v2_rsi_entry")
                exit_threshold = c3.number_input(tr(lang, "exit_threshold"), min_value=0.0, max_value=100.0, value=70.0, step=1.0, key="v2_rsi_exit")
                short_window, long_window = 20, 60
            st.markdown("&nbsp;", unsafe_allow_html=True)
            run_clicked = st.button(tr(lang, "run_backtest"), type="primary", use_container_width=True, key="v2_run_manual")

        try:
            generated_yaml = build_manual_yaml(market, symbol, start, end, initial_cash, execution_price, commission_pct, slippage_pct, strategy_type, int(short_window), int(long_window), int(rsi_window), float(entry_threshold), float(exit_threshold))
        except Exception as exc:
            generated_yaml = f"# {exc}"

        with right:
            st.markdown(f"### ? {tr(lang, 'yaml_preview')}")
            edit_yaml = st.toggle(tr(lang, "edit_yaml"), value=False, key="v2_edit_yaml")
            if edit_yaml:
                yaml_text = st.text_area("YAML", value=generated_yaml, height=390, key="v2_manual_yaml_edit")
            else:
                yaml_text = generated_yaml
                st.code(yaml_text, language="yaml")
            st.download_button(tr(lang, "copy_yaml"), data=yaml_text.encode("utf-8"), file_name="tradetest_strategy.yaml", mime="application/x-yaml", use_container_width=True, key="v2_download_yaml")

        if run_clicked:
            try:
                summary, portfolio_df, trades_df, report_bytes, chart_bytes, prepared_yaml = run_yaml_backtest(yaml_text)
                save_cloud_run_safely(cloud, terminal_id, config_name, prepared_yaml, summary, report_bytes, chart_bytes, lang)
                st.session_state["latest_result"] = (summary, portfolio_df, trades_df, report_bytes)
            except Exception as exc:
                st.error(f"{tr(lang, 'run_failed')}: {exc}")
    else:
        st.caption(tr(lang, "yaml_tip"))
        uploaded = st.file_uploader(tr(lang, "upload_config"), type=["yaml", "yml"], key="v2_upload_file")
        if "v2_upload_text" not in st.session_state:
            st.session_state["v2_upload_text"] = STANDARD_MA_TEMPLATE
        if uploaded is not None:
            uploaded_bytes = uploaded.getvalue()
            upload_signature = hashlib.sha256(uploaded_bytes).hexdigest()
            if st.session_state.get("v2_upload_sig") != upload_signature:
                st.session_state["v2_upload_text"] = uploaded_bytes.decode("utf-8")
                st.session_state["v2_upload_sig"] = upload_signature
        st.download_button("MA YAML Template", data=STANDARD_MA_TEMPLATE.encode("utf-8"), file_name="ma_cross.yaml", mime="application/x-yaml", key="ma_template")
        st.download_button("RSI YAML Template", data=STANDARD_RSI_TEMPLATE.encode("utf-8"), file_name="rsi_reversal.yaml", mime="application/x-yaml", key="rsi_template")
        yaml_text = st.text_area("YAML", value=st.session_state["v2_upload_text"], height=520, key="v2_upload_yaml")
        st.session_state["v2_upload_text"] = yaml_text
        if st.button(tr(lang, "run_backtest"), type="primary", use_container_width=True, key="v2_run_upload"):
            try:
                summary, portfolio_df, trades_df, report_bytes, chart_bytes, prepared_yaml = run_yaml_backtest(yaml_text)
                save_cloud_run_safely(cloud, terminal_id, config_name, prepared_yaml, summary, report_bytes, chart_bytes, lang)
                st.session_state["latest_result"] = (summary, portfolio_df, trades_df, report_bytes)
            except Exception as exc:
                st.error(f"{tr(lang, 'run_failed')}: {exc}")

    if "latest_result" in st.session_state:
        summary, portfolio_df, trades_df, report_bytes = st.session_state["latest_result"]
        render_results(summary, portfolio_df, trades_df, report_bytes, lang)


def render_history(lang: str, cloud: CloudStore) -> None:
    st.markdown(f"### {tr(lang, 'cloud_history')}")
    st.caption(tr(lang, "history_intro"))
    if not cloud.enabled:
        st.info(tr(lang, "history_disabled"))
        return
    try:
        runs = cloud.list_runs()
        if not runs:
            st.info(tr(lang, "no_runs"))
            return
        df = pd.DataFrame(runs)
        cols = [c for c in ["created_at", "terminal_id", "config_name", "strategy_type", "symbols", "total_return", "max_drawdown", "trade_count"] if c in df.columns]
        st.dataframe(df[cols], use_container_width=True, height=420)
        selected = st.selectbox(tr(lang, "open_run"), df["id"].tolist(), format_func=lambda x: f"{df[df['id'] == x].iloc[0]['created_at']} | {df[df['id'] == x].iloc[0]['config_name']}", key="history_selector")
        row = df[df["id"] == selected].iloc[0]
        st.code(row.get("config_yaml", ""), language="yaml")
        if row.get("chart_png_url"):
            st.image(row["chart_png_url"], use_container_width=True)
        if row.get("report_xlsx_url"):
            st.link_button(tr(lang, "open_report"), row["report_xlsx_url"], use_container_width=True)
    except Exception as exc:
        st.error(str(exc))


def main() -> None:
    st.set_page_config(page_title=APP_NAME, page_icon="TT", layout="wide")
    inject_css()
    cloud = CloudStore(get_streamlit_secrets())

    with st.sidebar:
        lang_label = st.selectbox(TEXT["zh"]["language"], ["??", "English"], index=0, key="language_selector")
        lang = "zh" if lang_label == "??" else "en"
        st.markdown("## TradeTest")
        page = st.radio("", ["new", "history"], format_func=lambda v: tr(lang, "new_backtest") if v == "new" else tr(lang, "cloud_history"), key="page_selector")
        st.markdown("---")
        st.markdown(f"### {tr(lang, 'cloud')}")
        terminal_id = st.text_input(tr(lang, "terminal_id"), value=default_terminal_id(), key="terminal_id")
        config_name = st.text_input(tr(lang, "config_name"), value="web_config", key="config_name")
        if cloud.enabled:
            st.success(tr(lang, "cloud_enabled"))
        else:
            st.info(tr(lang, "cloud_disabled"))

    render_header(lang)
    if page == "new":
        render_new_backtest(lang, cloud, terminal_id, config_name)
    else:
        render_history(lang, cloud)
    st.markdown(f'<div class="footer-note">{tr(lang, "risk")}</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
