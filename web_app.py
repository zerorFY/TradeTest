# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import html
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
        "language": "Language / 语言",
        "docs": "文档",
        "theme": "主题",
        "alerts": "通知",
        "help": "帮助",
        "overview": "总览",
        "research": "回测研究",
        "new_backtest": "新建回测",
        "backtest_list": "回测列表",
        "strategy_library": "策略库",
        "data_manage": "数据管理",
        "analysis_tools": "分析工具",
        "return_analysis": "收益分析",
        "factor_analysis": "因子分析",
        "portfolio_analysis": "组合分析",
        "mine": "我的",
        "favorite_strategy": "收藏策略",
        "reports": "回测报告",
        "settings": "设置",
        "data_source": "数据源",
        "cloud": "云端",
        "cloud_history": "云端历史",
        "terminal_id": "终端 ID",
        "config_name": "配置名称",
        "cloud_enabled": "云端同步 已开启",
        "cloud_disabled": "云端同步 未开启",
        "cloud_disabled_help": "设置 SUPABASE_URL 和 SUPABASE_KEY 后可保存历史记录。",
        "connected": "已连接",
        "not_connected": "未连接",
        "step_1": "数据设置",
        "step_1_sub": "选择标的与回测区间",
        "step_2": "输入方式",
        "step_2_sub": "选择手动或上传 YAML",
        "step_3": "策略设置",
        "step_3_sub": "配置交易策略参数",
        "step_4": "YAML 预览",
        "step_4_sub": "查看与编辑配置",
        "step_5": "运行回测",
        "step_5_sub": "执行回测并生成结果",
        "step_6": "回测结果",
        "step_6_sub": "查看绩效与交易明细",
        "data_settings": "数据设置",
        "manual_strategy": "手动策略",
        "yaml_preview": "YAML 预览 / 高级编辑",
        "results": "回测结果",
        "input_source": "配置来源",
        "form_config": "表单配置",
        "upload_yaml": "上传 YAML",
        "market": "市场",
        "western": "欧美股市",
        "china": "中国 A 股",
        "symbol": "标的 Symbol",
        "symbol_help": "欧美示例 AAPL / VFV.TO；中国示例 510300 / 600519",
        "start": "开始日期",
        "end": "结束日期",
        "initial_cash": "初始资金",
        "currency": "币种",
        "execution_price": "执行价格",
        "commission_pct": "手续费率",
        "slippage_pct": "滑点",
        "more_data_options": "更多数据选项",
        "strategy_type": "策略类型",
        "ma_cross": "均线交叉",
        "rsi_reversal": "RSI 反转",
        "ma_desc": "短期均线上穿长期均线买入，下穿长期均线卖出。",
        "rsi_desc": "RSI 进入超卖区买入，恢复到卖出阈值后退出。",
        "coming_next": "Breakout 与 Bollinger Band 下一版接入，目前先不开放运行，避免误用。",
        "basic_params": "基础参数",
        "strategy_params": "策略参数",
        "risk_cost": "风险 / 成本设置",
        "frequency": "回测频率",
        "daily": "日线",
        "signal_delay": "信号延迟",
        "signal_direction": "信号方向",
        "long_only": "多头",
        "price_field": "价格字段",
        "short_window": "短均线",
        "long_window": "长均线",
        "rsi_window": "RSI 周期",
        "entry_threshold": "买入阈值",
        "exit_threshold": "卖出阈值",
        "position_mode": "仓位管理",
        "full_position": "满仓 / 空仓",
        "position_pct": "每次仓位",
        "stop_loss": "止损方式",
        "none": "暂不启用",
        "run_backtest": "运行回测 (Run Backtest)",
        "copy_yaml": "下载 YAML",
        "edit_yaml": "编辑 YAML",
        "upload_config": "上传 YAML 配置",
        "ma_template": "下载均线模板",
        "rsi_template": "下载 RSI 模板",
        "legacy_template": "下载组合模板",
        "yaml_tip": "手动表单会先生成 YAML；上传 YAML 也走同一个 parser 和 engine。",
        "run_failed": "回测失败",
        "saved_to_cloud": "已保存到云端",
        "export_report": "导出报告",
        "total_return": "总收益率",
        "annual_return": "年化收益率",
        "max_drawdown": "最大回撤",
        "sharpe_ratio": "夏普比率",
        "win_rate": "胜率",
        "trade_count": "交易次数",
        "profit_factor": "盈亏比",
        "buy_hold_return": "买入持有收益率",
        "benchmark": "基准",
        "cost_adjusted": "扣成本后",
        "equity_curve": "收益曲线",
        "drawdown_curve": "回撤曲线",
        "recent_trades": "最近交易记录",
        "view_all": "查看全部",
        "waiting_result": "运行一次回测后，这里会显示收益曲线、回撤曲线和交易明细。",
        "history_intro": "云端历史会保存回测摘要、YAML 配置、图表和 Excel 报告。",
        "history_disabled": "云端历史当前不可用。",
        "no_runs": "还没有保存的回测记录。",
        "open_run": "打开记录",
        "open_report": "打开 Excel 报告",
        "risk": "免责声明：本平台提供的所有信息仅供参考，不构成任何投资建议。投资有风险，入市需谨慎。",
        "footer_source": "数据来源",
        "footer_update": "更新时间",
    },
    "en": {
        "app_subtitle": "Daily Stock & ETF Backtesting Engine",
        "language": "Language / 语言",
        "docs": "Docs",
        "theme": "Theme",
        "alerts": "Alerts",
        "help": "Help",
        "overview": "Overview",
        "research": "Backtest Research",
        "new_backtest": "New Backtest",
        "backtest_list": "Backtest List",
        "strategy_library": "Strategy Library",
        "data_manage": "Data Management",
        "analysis_tools": "Analysis Tools",
        "return_analysis": "Return Analysis",
        "factor_analysis": "Factor Analysis",
        "portfolio_analysis": "Portfolio Analysis",
        "mine": "Mine",
        "favorite_strategy": "Favorite Strategies",
        "reports": "Backtest Reports",
        "settings": "Settings",
        "data_source": "Data Source",
        "cloud": "Cloud",
        "cloud_history": "Cloud History",
        "terminal_id": "Terminal ID",
        "config_name": "Config Name",
        "cloud_enabled": "Cloud sync enabled",
        "cloud_disabled": "Cloud sync disabled",
        "cloud_disabled_help": "Set SUPABASE_URL and SUPABASE_KEY to save history.",
        "connected": "Connected",
        "not_connected": "Not connected",
        "step_1": "Data Settings",
        "step_1_sub": "Choose symbol and date range",
        "step_2": "Input Method",
        "step_2_sub": "Manual form or YAML upload",
        "step_3": "Strategy Settings",
        "step_3_sub": "Configure strategy parameters",
        "step_4": "YAML Preview",
        "step_4_sub": "Review and edit config",
        "step_5": "Run Backtest",
        "step_5_sub": "Run and generate results",
        "step_6": "Backtest Results",
        "step_6_sub": "Review performance and trades",
        "data_settings": "Data Settings",
        "manual_strategy": "Manual Strategy",
        "yaml_preview": "YAML Preview / Advanced Edit",
        "results": "Backtest Results",
        "input_source": "Config Source",
        "form_config": "Form Config",
        "upload_yaml": "Upload YAML",
        "market": "Market",
        "western": "Western Market",
        "china": "China A-share",
        "symbol": "Symbol",
        "symbol_help": "Western examples: AAPL / VFV.TO; China examples: 510300 / 600519",
        "start": "Start Date",
        "end": "End Date",
        "initial_cash": "Initial Cash",
        "currency": "Currency",
        "execution_price": "Execution Price",
        "commission_pct": "Commission Rate",
        "slippage_pct": "Slippage",
        "more_data_options": "More Data Options",
        "strategy_type": "Strategy Type",
        "ma_cross": "Moving Average Cross",
        "rsi_reversal": "RSI Reversal",
        "ma_desc": "Buy when short MA crosses above long MA; sell when it crosses below.",
        "rsi_desc": "Buy when RSI reaches oversold area; exit when RSI recovers to the exit threshold.",
        "coming_next": "Breakout and Bollinger Band will be added next. They are not runnable yet to avoid misuse.",
        "basic_params": "Basic Parameters",
        "strategy_params": "Strategy Parameters",
        "risk_cost": "Risk / Cost Settings",
        "frequency": "Frequency",
        "daily": "Daily",
        "signal_delay": "Signal Delay",
        "signal_direction": "Signal Direction",
        "long_only": "Long Only",
        "price_field": "Price Field",
        "short_window": "Short MA",
        "long_window": "Long MA",
        "rsi_window": "RSI Window",
        "entry_threshold": "Entry Threshold",
        "exit_threshold": "Exit Threshold",
        "position_mode": "Position Mode",
        "full_position": "Full / Flat",
        "position_pct": "Position Size",
        "stop_loss": "Stop Loss",
        "none": "Disabled",
        "run_backtest": "Run Backtest",
        "copy_yaml": "Download YAML",
        "edit_yaml": "Edit YAML",
        "upload_config": "Upload YAML Config",
        "ma_template": "Download MA Template",
        "rsi_template": "Download RSI Template",
        "legacy_template": "Download Portfolio Template",
        "yaml_tip": "Manual form generates YAML first; uploaded YAML uses the same parser and engine.",
        "run_failed": "Run failed",
        "saved_to_cloud": "Saved to cloud",
        "export_report": "Export Report",
        "total_return": "Total Return",
        "annual_return": "Annual Return",
        "max_drawdown": "Max Drawdown",
        "sharpe_ratio": "Sharpe Ratio",
        "win_rate": "Win Rate",
        "trade_count": "Trade Count",
        "profit_factor": "Profit Factor",
        "buy_hold_return": "Buy & Hold Return",
        "benchmark": "Benchmark",
        "cost_adjusted": "Cost adjusted",
        "equity_curve": "Equity Curve",
        "drawdown_curve": "Drawdown Curve",
        "recent_trades": "Recent Trades",
        "view_all": "View All",
        "waiting_result": "Run a backtest to show equity curve, drawdown curve, and trades here.",
        "history_intro": "Cloud history stores summaries, YAML configs, charts, and Excel reports.",
        "history_disabled": "Cloud history is disabled.",
        "no_runs": "No saved runs yet.",
        "open_run": "Open Run",
        "open_report": "Open Excel Report",
        "risk": "Disclaimer: Information is for research only and is not investment advice. Investing involves risk.",
        "footer_source": "Data Source",
        "footer_update": "Updated At",
    },
}


def tr(lang: str, key: str) -> str:
    return TEXT[lang].get(key, key)


def get_streamlit_secrets() -> dict:
    try:
        return dict(st.secrets)
    except Exception:
        return {}


def fmt_pct(value: float | int | None, signed: bool = True) -> str:
    if value is None or pd.isna(value):
        return "--"
    sign = "+" if signed else ""
    return f"{float(value):{sign}.2%}"


def fmt_num(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "--"
    if value == float("inf"):
        return "∞"
    return f"{float(value):,.2f}"


def fmt_money(value: float | int | None, currency: str) -> str:
    if value is None or pd.isna(value):
        return "--"
    prefix = "¥" if currency == "CNY" else "$"
    return f"{prefix}{float(value):,.0f}"


def currency_for_market_ui(market: str) -> str:
    return "CNY" if market == "china" else "MARKET_NATIVE"


def symbol_display_name(symbol: str, market: str) -> str:
    if market == "china":
        names = {"510300": "沪深300 ETF", "510300.SS": "沪深300 ETF", "600519": "贵州茅台", "600519.SS": "贵州茅台"}
        return names.get(symbol.strip().upper(), "中国 A 股 / ETF")
    names = {"AAPL": "Apple Inc.", "VFV.TO": "Vanguard S&P 500 ETF", "QQC.TO": "NASDAQ 100 ETF"}
    return names.get(symbol.strip().upper(), "Stock / ETF")


def ui_text(lang: str, zh: str, en: str) -> str:
    return zh if lang == "zh" else en


LOCAL_SYMBOLS = {
    "western": [
        {"symbol": "QQQ", "name": "Invesco QQQ Trust", "exchange": "NASDAQ", "currency": "USD"},
        {"symbol": "QQQM", "name": "Invesco NASDAQ 100 ETF", "exchange": "NASDAQ", "currency": "USD"},
        {"symbol": "AAPL", "name": "Apple Inc.", "exchange": "NASDAQ", "currency": "USD"},
        {"symbol": "MSFT", "name": "Microsoft Corporation", "exchange": "NASDAQ", "currency": "USD"},
        {"symbol": "SPY", "name": "SPDR S&P 500 ETF Trust", "exchange": "NYSE Arca", "currency": "USD"},
        {"symbol": "VFV.TO", "name": "Vanguard S&P 500 Index ETF", "exchange": "TSX", "currency": "CAD"},
        {"symbol": "QQC.TO", "name": "Invesco NASDAQ 100 Index ETF", "exchange": "TSX", "currency": "CAD"},
        {"symbol": "TSLA.NE", "name": "Tesla Canadian Depositary Receipt", "exchange": "Cboe Canada", "currency": "CAD"},
    ],
    "china": [
        {"symbol": "510300.SS", "name": "沪深300 ETF", "exchange": "上海证券交易所", "currency": "CNY"},
        {"symbol": "510500.SS", "name": "中证500 ETF", "exchange": "上海证券交易所", "currency": "CNY"},
        {"symbol": "588000.SS", "name": "科创50 ETF", "exchange": "上海证券交易所", "currency": "CNY"},
        {"symbol": "600519.SS", "name": "贵州茅台", "exchange": "上海证券交易所", "currency": "CNY"},
        {"symbol": "000001.SZ", "name": "平安银行", "exchange": "深圳证券交易所", "currency": "CNY"},
        {"symbol": "159915.SZ", "name": "创业板 ETF", "exchange": "深圳证券交易所", "currency": "CNY"},
    ],
}


def candidate_key(candidate: dict) -> str:
    return str(candidate.get("symbol", "")).strip().upper()


def unique_candidates(candidates: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for candidate in candidates:
        key = candidate_key(candidate)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(candidate)
    return out


def search_symbol_candidates(query: str, market: str) -> list[dict]:
    q = str(query or "").strip()
    if not q:
        return []
    q_upper = q.upper()
    q_lower = q.lower()
    candidates = []

    for item in LOCAL_SYMBOLS.get(market, []):
        if q_lower in item["symbol"].lower() or q_lower in item["name"].lower():
            candidates.append({**item, "market": market, "source": "local"})

    if market == "china":
        try:
            normalized = backtest.normalize_symbol_for_market(q, "china")
            candidates.append(
                {
                    "symbol": normalized,
                    "name": symbol_display_name(normalized, "china"),
                    "exchange": "上海/深圳",
                    "currency": "CNY",
                    "market": "china",
                    "source": "normalized",
                }
            )
        except ValueError:
            pass
        return unique_candidates(candidates)

    try:
        search = backtest.yf.Search(q_upper, max_results=8)
        for item in getattr(search, "quotes", []) or []:
            symbol = str(item.get("symbol") or "").strip().upper()
            if not symbol:
                continue
            try:
                normalized = backtest.normalize_symbol_for_market(symbol, "western")
            except ValueError:
                continue
            quote_type = str(item.get("quoteType") or "").upper()
            if quote_type and quote_type not in {"EQUITY", "ETF", "MUTUALFUND"}:
                continue
            candidates.append(
                {
                    "symbol": normalized,
                    "name": item.get("shortname") or item.get("longname") or item.get("name") or normalized,
                    "exchange": item.get("exchDisp") or item.get("exchange") or "",
                    "currency": item.get("currency") or "",
                    "market": "western",
                    "source": "yfinance",
                }
            )
    except Exception:
        pass

    if not candidates:
        try:
            normalized = backtest.normalize_symbol_for_market(q_upper, "western")
            candidates.append(
                {
                    "symbol": normalized,
                    "name": "Unverified ticker",
                    "exchange": "",
                    "currency": "",
                    "market": "western",
                    "source": "manual",
                }
            )
        except ValueError:
            pass
    return unique_candidates(candidates)


def format_candidate(candidate: dict) -> str:
    parts = [str(candidate.get("symbol", "")), str(candidate.get("name", ""))]
    meta = [str(candidate.get("exchange", "")), str(candidate.get("currency", ""))]
    meta_text = " / ".join([x for x in meta if x])
    return " | ".join([x for x in parts + ([meta_text] if meta_text else []) if x])


def confirmed_key(market: str, mode: str) -> str:
    return f"confirmed_symbols_{market}_{mode}"


def candidates_key(market: str, mode: str) -> str:
    return f"symbol_candidates_{market}_{mode}"


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
        portfolio_df, trades_df = backtest.run_periodic_rebalance(
            open_prices, close_prices, initial_cash, commission, slippage, strategy_cfg, execution_timing
        )
    else:
        fast_ma = int(strategy_cfg.get("fast_ma", 20))
        slow_ma = int(strategy_cfg.get("slow_ma", 60))
        portfolio_df, trades_df = backtest.run_ma_portfolio(
            open_prices, close_prices, initial_cash, commission, slippage, fast_ma, slow_ma, execution_timing
        )

    final_equity = float(portfolio_df["equity"].iloc[-1])
    total_return = final_equity / initial_cash - 1.0
    portfolio_df["drawdown"] = portfolio_df["equity"] / portfolio_df["equity"].cummax() - 1.0
    bh_returns = [float(close_prices[s].iloc[-1] / close_prices[s].iloc[0] - 1.0) for s in symbols]
    daily_returns = portfolio_df["equity"].pct_change().dropna()
    sharpe = float(daily_returns.mean() / daily_returns.std() * (252**0.5)) if len(daily_returns) > 1 and daily_returns.std() > 0 else 0.0
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


def save_cloud_run_safely(
    cloud: CloudStore,
    terminal_id: str,
    config_name: str,
    config_yaml: str,
    summary: dict,
    report_bytes: bytes,
    chart_bytes: bytes | None,
    lang: str,
) -> None:
    if not cloud.enabled:
        return
    try:
        saved = cloud.save_run(
            terminal_id=terminal_id,
            config_name=config_name,
            config_yaml=config_yaml,
            summary=summary,
            report_bytes=report_bytes,
            chart_bytes=chart_bytes,
        )
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
        cfg = yaml_builder.build_moving_average_config(
            market, symbol, start, end or None, initial_cash, execution_price, commission_pct, slippage_pct, short_window, long_window
        )
    elif strategy_type == "rsi_reversal":
        cfg = yaml_builder.build_rsi_reversal_config(
            market, symbol, start, end or None, initial_cash, execution_price, commission_pct, slippage_pct, rsi_window, entry_threshold, exit_threshold
        )
    else:
        raise ValueError("Only Moving Average Cross and RSI Reversal are supported in V2 first release.")
    return yaml_builder.config_to_yaml(cfg)


def build_portfolio_yaml(data: dict, rebalance_frequency: str, rebalance_threshold: float, cash_buffer: float, commission_abs: float) -> str:
    rows = data.get("portfolio_rows", [])
    if len(rows) < 2:
        raise ValueError("Portfolio mode requires at least two confirmed symbols.")
    weight_sum = sum(float(row.get("weight_pct", 0.0)) for row in rows)
    if abs(weight_sum - 100.0) > 0.01:
        raise ValueError(f"Portfolio weights must add up to 100%. Current total: {weight_sum:.2f}%.")

    symbols = {row["symbol"]: row.get("name") or row["symbol"] for row in rows}
    target_weights = {row["symbol"]: round(float(row.get("weight_pct", 0.0)) / 100.0, 6) for row in rows}
    cfg = {
        "data": {
            "market": data["market"],
            "symbols": symbols,
            "start": data["start"],
            "end": data["end"] or None,
        },
        "account": {
            "initial_cash": float(data["initial_cash"]),
            "currency": currency_for_market_ui(data["market"]),
        },
        "costs": {
            "commission": float(commission_abs),
            "slippage": float(data["slippage_pct"]),
        },
        "strategy": {
            "type": "monthly_rebalance",
            "execution_timing": "next_open",
            "target_weights": target_weights,
            "rebalance_frequency": rebalance_frequency,
            "rebalance_threshold": float(rebalance_threshold),
            "cash_buffer": float(cash_buffer),
        },
        "report": {"output_dir": "results"},
    }
    return yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True)


def inject_css() -> None:
    st.markdown(
        """
<style>
:root {
  --navy: #061727;
  --navy-2: #08243d;
  --cyan: #00a99d;
  --cyan-2: #18c4b5;
  --muted: #64748b;
  --line: #d9e3ee;
  --panel: #ffffff;
  --soft: #f5f8fc;
}
.stApp {
  background: linear-gradient(180deg, #f5f8fc 0%, #eef4f8 100%);
  color: #0f172a;
}
.block-container {
  max-width: 1880px;
  padding: 0.8rem 1rem 0.3rem 1rem;
}
[data-testid="stSidebar"] {
  background: radial-gradient(circle at 20% 0%, rgba(0,169,157,.20), transparent 26%), linear-gradient(180deg, #061727 0%, #08213a 52%, #061727 100%);
  border-right: 1px solid rgba(255,255,255,.08);
}
[data-testid="stSidebar"] * {
  color: #d9e7f4 !important;
}
[data-testid="stSidebar"] input,
[data-testid="stSidebar"] textarea,
[data-testid="stSidebar"] select,
[data-testid="stSidebar"] [data-baseweb="select"] * {
  color: #0f172a !important;
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
  margin-bottom: .25rem;
}
.top-shell {
  background: linear-gradient(90deg, #061727 0%, #08233d 100%);
  color: white;
  margin: -0.8rem -1rem 0.75rem -1rem;
  padding: 13px 22px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  box-shadow: 0 12px 30px rgba(6, 23, 39, .22);
}
.brand-wrap {
  display: flex;
  align-items: center;
  gap: 12px;
}
.logo-mark {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: linear-gradient(135deg, #00a99d, #2dd4bf);
  color: #061727;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 900;
  letter-spacing: -.08em;
}
.brand-title {
  font-size: 21px;
  font-weight: 850;
  letter-spacing: -.03em;
}
.brand-subtitle {
  color: #b7c9dc;
  font-size: 12px;
  margin-left: 8px;
}
.top-actions {
  display: flex;
  gap: 14px;
  align-items: center;
  color: #d9e7f4;
  font-size: 13px;
}
.circle-user {
  width: 30px;
  height: 30px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: #315dcc;
  color: white;
  font-weight: 800;
}
.side-title {
  color: #8ea7bf;
  font-size: 12px;
  letter-spacing: .08em;
  margin: 18px 0 8px 0;
}
.nav-row {
  padding: 9px 11px;
  border-radius: 8px;
  color: #d9e7f4;
  margin: 3px 0;
  font-size: 14px;
}
.nav-row.active {
  background: linear-gradient(90deg, rgba(0,169,157,.22), rgba(0,169,157,.08));
  color: #2dd4bf;
  border: 1px solid rgba(45,212,191,.20);
}
.source-card {
  margin-top: 28px;
  padding: 14px;
  border: 1px solid rgba(255,255,255,.12);
  border-radius: 10px;
  background: rgba(255,255,255,.03);
}
.source-card strong {
  color: white;
}
.status-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #2dd4bf;
  margin-right: 7px;
}
.stepper {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 12px;
  margin: 8px 0 14px 0;
}
.step-item {
  position: relative;
  background: transparent;
  min-height: 50px;
  display: flex;
  gap: 10px;
  align-items: flex-start;
}
.step-item:after {
  content: "";
  position: absolute;
  left: 54px;
  right: 4px;
  top: 16px;
  border-top: 1px dashed #9db1c7;
}
.step-item:last-child:after {
  display: none;
}
.step-num {
  z-index: 1;
  width: 34px;
  height: 34px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 800;
  color: #334155;
  background: linear-gradient(135deg, #edf2f7, #cbd5e1);
  box-shadow: inset 0 1px 0 rgba(255,255,255,.8);
}
.step-item.active .step-num {
  color: white;
  background: linear-gradient(135deg, #00a99d, #16c7b7);
  box-shadow: 0 9px 22px rgba(0,169,157,.32);
}
.step-text b {
  display: block;
  color: #1e293b;
  font-size: 13px;
  line-height: 1.15;
}
.step-text span {
  display: block;
  color: #64748b;
  font-size: 11px;
  margin-top: 3px;
}
.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 10px 0;
  font-weight: 800;
  color: #1e293b;
  font-size: 15px;
}
.section-num {
  display: inline-flex;
  width: 21px;
  height: 21px;
  border-radius: 999px;
  align-items: center;
  justify-content: center;
  border: 1px solid #c8d5e3;
  color: #334155;
  background: white;
  font-size: 12px;
}
.param-group {
  border-left: 3px solid #18c4b5;
  padding-left: 10px;
  margin: 10px 0 6px 0;
  color: #0f766e;
  font-size: 13px;
  font-weight: 800;
}
[data-testid="stVerticalBlockBorderWrapper"] {
  border-color: #d9e3ee !important;
  border-radius: 12px !important;
  box-shadow: 0 10px 24px rgba(15, 23, 42, .05);
  background: white;
}
.stButton > button[kind="primary"] {
  background: linear-gradient(135deg, #00a99d, #12c8b6) !important;
  border: 0 !important;
  color: #fff !important;
  font-weight: 850 !important;
  border-radius: 9px !important;
  box-shadow: 0 10px 22px rgba(0,169,157,.28);
  min-height: 44px;
}
.stButton > button[kind="secondary"],
.stDownloadButton > button {
  border-color: #c5d3e2 !important;
  color: #1e293b !important;
  border-radius: 8px !important;
}
.yaml-panel {
  background: linear-gradient(180deg, #111827, #0b1220);
  color: #d6e4f0;
  border: 1px solid #243244;
  border-radius: 10px;
  padding: 12px 0;
  max-height: 470px;
  overflow: auto;
  box-shadow: inset 0 1px 0 rgba(255,255,255,.05);
}
.yaml-line {
  display: grid;
  grid-template-columns: 44px 1fr;
  gap: 10px;
  font-family: Consolas, "Courier New", monospace;
  font-size: 12px;
  line-height: 1.55;
  white-space: pre;
}
.yaml-ln {
  color: #64748b;
  text-align: right;
  user-select: none;
}
.yaml-code {
  color: #d8e6f3;
}
.metric-grid {
  display: grid;
  grid-template-columns: repeat(8, minmax(120px, 1fr));
  gap: 9px;
  margin: 8px 0 10px 0;
}
.metric-card {
  background: white;
  border: 1px solid #d9e3ee;
  border-radius: 10px;
  padding: 11px 12px;
  box-shadow: 0 6px 16px rgba(15,23,42,.04);
}
.metric-label {
  color: #64748b;
  font-size: 12px;
}
.metric-value {
  color: #0f766e;
  font-size: 20px;
  font-weight: 850;
  margin-top: 5px;
}
.metric-value.negative {
  color: #dc2626;
}
.metric-sub {
  color: #64748b;
  font-size: 11px;
  margin-top: 4px;
}
.footer-bar {
  background: #061727;
  color: #9fb4c9;
  margin: 10px -1rem -0.3rem -1rem;
  padding: 10px 24px;
  display: grid;
  grid-template-columns: 1fr auto auto;
  gap: 28px;
  font-size: 12px;
}
.warning-strip {
  background: #fffbea;
  color: #9a6700;
  border-radius: 8px;
  padding: 11px 13px;
  margin: 8px 0 13px 0;
  font-size: 13px;
}
@media (max-width: 1200px) {
  .stepper { grid-template-columns: repeat(2, 1fr); }
  .metric-grid { grid-template-columns: repeat(2, 1fr); }
  .footer-bar { grid-template-columns: 1fr; }
}
</style>
""",
        unsafe_allow_html=True,
    )


def render_header(lang: str) -> None:
    st.markdown(
        f"""
<div class="top-shell">
  <div class="brand-wrap">
    <span class="logo-mark">TT</span>
    <span class="brand-title">TradeTest</span>
    <span class="brand-subtitle">{html.escape(tr(lang, "app_subtitle"))}</span>
  </div>
  <div class="top-actions">
    <span>{html.escape(tr(lang, "docs"))}</span>
    <span>{html.escape(tr(lang, "theme"))}</span>
    <span>{html.escape(tr(lang, "alerts"))}</span>
    <span>{html.escape(tr(lang, "help"))}</span>
    <span class="circle-user">U</span>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_steps(lang: str) -> None:
    html_parts = ['<div class="stepper">']
    for idx in range(1, 7):
        active = " active" if idx in {1, 3} else ""
        html_parts.append(
            f"""
<div class="step-item{active}">
  <span class="step-num">{idx}</span>
  <span class="step-text"><b>{html.escape(tr(lang, f"step_{idx}"))}</b><span>{html.escape(tr(lang, f"step_{idx}_sub"))}</span></span>
</div>
"""
        )
    html_parts.append("</div>")
    st.markdown("".join(html_parts), unsafe_allow_html=True)


def render_sidebar(lang: str, cloud: CloudStore) -> tuple[str, str, str, str]:
    with st.sidebar:
        lang_label = st.selectbox(TEXT["zh"]["language"], ["中文", "English"], index=0, key="language_selector")
        chosen_lang = "zh" if lang_label == "中文" else "en"
        if "page_selector" not in st.session_state:
            st.session_state["page_selector"] = "new"

        st.markdown(f'<div class="nav-row">{tr(chosen_lang, "overview")}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="side-title">{tr(chosen_lang, "research")}</div>', unsafe_allow_html=True)

        if st.button(tr(chosen_lang, "new_backtest"), use_container_width=True, key="nav_new"):
            st.session_state["page_selector"] = "new"
        if st.button(tr(chosen_lang, "backtest_list"), use_container_width=True, key="nav_history"):
            st.session_state["page_selector"] = "history"
        page = st.session_state["page_selector"]

        st.markdown(f'<div class="nav-row">{tr(chosen_lang, "strategy_library")}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="nav-row">{tr(chosen_lang, "data_manage")}</div>', unsafe_allow_html=True)

        st.markdown(f'<div class="side-title">{tr(chosen_lang, "analysis_tools")}</div>', unsafe_allow_html=True)
        for key in ["return_analysis", "factor_analysis", "portfolio_analysis"]:
            st.markdown(f'<div class="nav-row">{tr(chosen_lang, key)}</div>', unsafe_allow_html=True)

        st.markdown(f'<div class="side-title">{tr(chosen_lang, "mine")}</div>', unsafe_allow_html=True)
        for key in ["favorite_strategy", "reports", "settings"]:
            st.markdown(f'<div class="nav-row">{tr(chosen_lang, key)}</div>', unsafe_allow_html=True)

        st.markdown("---")
        st.markdown(f"### {tr(chosen_lang, 'cloud')}")
        terminal_id = st.text_input(tr(chosen_lang, "terminal_id"), value=default_terminal_id(), key="terminal_id")
        config_name = st.text_input(tr(chosen_lang, "config_name"), value="web_config", key="config_name")
        if cloud.enabled:
            st.success(tr(chosen_lang, "cloud_enabled"))
        else:
            st.info(f"{tr(chosen_lang, 'cloud_disabled')}。{tr(chosen_lang, 'cloud_disabled_help')}")

        source_status = tr(chosen_lang, "connected") if cloud.enabled else tr(chosen_lang, "not_connected")
        st.markdown(
            f"""
<div class="source-card">
  <div class="side-title">{tr(chosen_lang, "data_source")}</div>
  <strong>Yahoo Finance / Tushare</strong>
  <div style="margin-top:10px;"><span class="status-dot"></span>{source_status}</div>
</div>
""",
            unsafe_allow_html=True,
        )
    return chosen_lang, page, terminal_id, config_name


def section_title(number: int, title: str) -> None:
    st.markdown(f'<div class="section-title"><span class="section-num">{number}</span>{html.escape(title)}</div>', unsafe_allow_html=True)


def param_group(title: str) -> None:
    st.markdown(f'<div class="param-group">{html.escape(title)}</div>', unsafe_allow_html=True)


def render_yaml_code(config_text: str) -> None:
    lines = config_text.rstrip().splitlines() or [""]
    html_lines = ['<div class="yaml-panel">']
    for idx, line in enumerate(lines, start=1):
        html_lines.append(
            f'<div class="yaml-line"><span class="yaml-ln">{idx}</span><span class="yaml-code">{html.escape(line)}</span></div>'
        )
    html_lines.append("</div>")
    st.markdown("".join(html_lines), unsafe_allow_html=True)


def render_metric_cards(summary: dict, lang: str) -> None:
    items = [
        ("total_return", fmt_pct(summary.get("total_return")), fmt_pct(summary.get("buy_hold_return"))),
        ("annual_return", fmt_pct(summary.get("annual_return")), "--"),
        ("max_drawdown", fmt_pct(summary.get("max_drawdown")), "--"),
        ("sharpe_ratio", fmt_num(summary.get("sharpe_ratio")), "--"),
        ("win_rate", fmt_pct(summary.get("win_rate"), signed=False), "--"),
        ("trade_count", str(summary.get("trade_count", 0)), "--"),
        ("profit_factor", fmt_num(summary.get("profit_factor")), "--"),
        ("buy_hold_return", fmt_pct(summary.get("buy_hold_return")), fmt_pct(summary.get("cost_adjusted_return"))),
    ]
    html_parts = ['<div class="metric-grid">']
    for key, value, sub in items:
        negative = " negative" if str(value).startswith("-") else ""
        sub_label = tr(lang, "benchmark") if key != "buy_hold_return" else tr(lang, "cost_adjusted")
        html_parts.append(
            f"""
<div class="metric-card">
  <div class="metric-label">{html.escape(tr(lang, key))}</div>
  <div class="metric-value{negative}">{html.escape(value)}</div>
  <div class="metric-sub">{html.escape(sub_label)} {html.escape(sub)}</div>
</div>
"""
        )
    html_parts.append("</div>")
    st.markdown("".join(html_parts), unsafe_allow_html=True)


def render_empty_results(lang: str) -> None:
    with st.container(border=True):
        section_title(6, tr(lang, "results"))
        st.info(tr(lang, "waiting_result"))


def render_results(summary: dict, portfolio_df: pd.DataFrame, trades_df: pd.DataFrame, report_bytes: bytes, lang: str) -> None:
    with st.container(border=True):
        top_left, top_right = st.columns([1, 0.14])
        with top_left:
            section_title(6, f'{tr(lang, "results")} ({summary.get("start")} 至 {summary.get("end")})')
        with top_right:
            st.download_button(
                tr(lang, "export_report"),
                data=report_bytes,
                file_name="backtest_report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key=f"download_result_report_{lang}",
            )

        render_metric_cards(summary, lang)
        chart_left, chart_mid, trade_right = st.columns([1.1, 1.0, 0.95], gap="medium")
        with chart_left:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=portfolio_df["Date"], y=portfolio_df["equity"], name="Strategy", line=dict(color="#00a99d", width=2)))
            if "buy_hold_equity" in portfolio_df.columns:
                fig.add_trace(
                    go.Scatter(x=portfolio_df["Date"], y=portfolio_df["buy_hold_equity"], name="Buy & Hold", line=dict(color="#94a3b8", width=1.4))
                )
            fig.update_layout(
                title=tr(lang, "equity_curve"),
                height=305,
                margin=dict(l=14, r=14, t=44, b=14),
                paper_bgcolor="white",
                plot_bgcolor="white",
                legend=dict(orientation="h", y=1.08),
            )
            st.plotly_chart(fig, use_container_width=True)
        with chart_mid:
            drawdown = portfolio_df.get("drawdown")
            if drawdown is None:
                drawdown = portfolio_df["equity"] / portfolio_df["equity"].cummax() - 1.0
            fig = go.Figure(
                go.Scatter(x=portfolio_df["Date"], y=drawdown, fill="tozeroy", name="Drawdown", line=dict(color="#14b8a6", width=1.6))
            )
            fig.update_layout(
                title=tr(lang, "drawdown_curve"),
                height=305,
                margin=dict(l=14, r=14, t=44, b=14),
                paper_bgcolor="white",
                plot_bgcolor="white",
                yaxis_tickformat=".0%",
            )
            st.plotly_chart(fig, use_container_width=True)
        with trade_right:
            title_col, view_col = st.columns([1, 0.35])
            title_col.markdown(f"**{tr(lang, 'recent_trades')}**")
            view_col.caption(tr(lang, "view_all"))
            if trades_df.empty:
                st.info("No trades")
            else:
                show = trades_df.copy().tail(7)
                for col in ["date"]:
                    if col in show.columns:
                        show[col] = pd.to_datetime(show[col]).dt.strftime("%Y-%m-%d")
                cols = [c for c in ["date", "symbol", "action", "price", "shares", "position_pct", "pnl_pct", "holding_days"] if c in show.columns]
                st.dataframe(show[cols], use_container_width=True, height=270, hide_index=True)


def render_data_panel(lang: str) -> dict:
    with st.container(border=True):
        section_title(1, tr(lang, "data_settings"))
        market = st.radio(tr(lang, "market"), ["western", "china"], format_func=lambda v: tr(lang, v), horizontal=True, key="v2_market")
        mode = st.radio(
            ui_text(lang, "标的模式", "Symbol Mode"),
            ["single", "portfolio"],
            horizontal=True,
            format_func=lambda v: ui_text(lang, "单标的", "Single") if v == "single" else ui_text(lang, "组合", "Portfolio"),
            key=f"symbol_mode_{market}",
        )

        default_symbol = "510300" if market == "china" else "QQQ"
        query = st.text_input(
            ui_text(lang, "搜索标的", "Search Symbol"),
            value=default_symbol,
            help=tr(lang, "symbol_help"),
            key=f"symbol_query_{market}_{mode}",
        )
        search_cols = st.columns([0.58, 0.42])
        if search_cols[0].button(ui_text(lang, "搜索候选", "Search"), use_container_width=True, key=f"search_symbol_{market}_{mode}"):
            st.session_state[candidates_key(market, mode)] = search_symbol_candidates(query, market)
        if search_cols[1].button(ui_text(lang, "清空确认", "Clear"), use_container_width=True, key=f"clear_confirmed_{market}_{mode}"):
            st.session_state[confirmed_key(market, mode)] = []

        candidates = st.session_state.get(candidates_key(market, mode), [])
        if candidates:
            selected_label = st.selectbox(
                ui_text(lang, "选择并确认一个候选", "Select and confirm a candidate"),
                [format_candidate(item) for item in candidates],
                key=f"candidate_select_{market}_{mode}",
            )
            selected = candidates[[format_candidate(item) for item in candidates].index(selected_label)]
            if st.button(ui_text(lang, "确认使用这个标的", "Confirm This Symbol"), use_container_width=True, key=f"confirm_symbol_{market}_{mode}"):
                key = confirmed_key(market, mode)
                confirmed = list(st.session_state.get(key, []))
                if mode == "single":
                    selected["weight_pct"] = 100.0
                    confirmed = [selected]
                else:
                    existing = {candidate_key(item) for item in confirmed}
                    if candidate_key(selected) not in existing:
                        selected["weight_pct"] = round(100.0 / max(1, len(confirmed) + 1), 2)
                        confirmed.append(selected)
                st.session_state[key] = confirmed
        else:
            st.caption(ui_text(lang, "请输入关键字并点击搜索；未确认标的不能运行回测。", "Enter a keyword and search. Backtest cannot run until a symbol is confirmed."))

        confirmed = list(st.session_state.get(confirmed_key(market, mode), []))
        if confirmed:
            if mode == "single":
                st.success(ui_text(lang, "已确认：", "Confirmed: ") + format_candidate(confirmed[0]))
            else:
                st.caption(ui_text(lang, "已确认组合；权重总和必须等于 100%。", "Confirmed portfolio. Weights must add up to 100%."))
                editable = pd.DataFrame(
                    [
                        {
                            "symbol": item["symbol"],
                            "name": item.get("name", item["symbol"]),
                            "weight_pct": float(item.get("weight_pct", 0.0)),
                        }
                        for item in confirmed
                    ]
                )
                edited = st.data_editor(
                    editable,
                    hide_index=True,
                    use_container_width=True,
                    disabled=["symbol", "name"],
                    column_config={
                        "symbol": st.column_config.TextColumn(ui_text(lang, "标的", "Symbol")),
                        "name": st.column_config.TextColumn(ui_text(lang, "名称", "Name")),
                        "weight_pct": st.column_config.NumberColumn(ui_text(lang, "权重 %", "Weight %"), min_value=0.0, max_value=100.0, step=1.0),
                    },
                    key=f"portfolio_editor_{market}",
                )
                for idx, item in enumerate(confirmed):
                    item["weight_pct"] = float(edited.iloc[idx]["weight_pct"])
                st.session_state[confirmed_key(market, mode)] = confirmed
                weight_sum = sum(float(item.get("weight_pct", 0.0)) for item in confirmed)
                if abs(weight_sum - 100.0) <= 0.01:
                    st.success(ui_text(lang, "组合权重合计 100%。", "Portfolio weights add up to 100%."))
                else:
                    st.warning(ui_text(lang, f"当前权重合计 {weight_sum:.2f}%，需要等于 100%。", f"Current total weight is {weight_sum:.2f}%; it must equal 100%."))

        start = st.text_input(tr(lang, "start"), value="2020-01-01", key="v2_start")
        end = st.text_input(tr(lang, "end"), value="", key="v2_end")
        currency = currency_for_market_ui(market)
        cash_col, currency_col = st.columns([0.72, 0.28])
        with cash_col:
            initial_cash = st.number_input(
                tr(lang, "initial_cash"),
                min_value=1.0,
                value=10000.0 if market == "western" else 100000.0,
                step=1000.0,
                key=f"v2_cash_{market}",
            )
        with currency_col:
            st.text_input(tr(lang, "currency"), value=currency, disabled=True, key=f"v2_currency_{market}")
        execution_price = st.selectbox(tr(lang, "execution_price"), ["next_open", "close"], index=0, key="v2_execution")
        commission_pct = st.number_input(tr(lang, "commission_pct"), min_value=0.0, value=0.001, step=0.0001, format="%.4f", key="v2_commission")
        slippage_pct = st.number_input(tr(lang, "slippage_pct"), min_value=0.0, value=0.001, step=0.0001, format="%.4f", key="v2_slippage")
        st.button(tr(lang, "more_data_options"), use_container_width=True, disabled=True, key="more_data_options")
    portfolio_rows = [
        {"symbol": item["symbol"], "name": item.get("name", item["symbol"]), "weight_pct": float(item.get("weight_pct", 0.0))}
        for item in confirmed
    ]
    is_ready = bool(portfolio_rows) if mode == "single" else len(portfolio_rows) >= 2 and abs(sum(row["weight_pct"] for row in portfolio_rows) - 100.0) <= 0.01
    return {
        "market": market,
        "mode": mode,
        "symbol": portfolio_rows[0]["symbol"] if portfolio_rows else "",
        "symbol_name": portfolio_rows[0]["name"] if portfolio_rows else "",
        "portfolio_rows": portfolio_rows,
        "is_ready": is_ready,
        "start": start,
        "end": end,
        "initial_cash": initial_cash,
        "execution_price": execution_price,
        "commission_pct": commission_pct,
        "slippage_pct": slippage_pct,
        "currency": currency,
    }


def render_strategy_panel(lang: str, data: dict) -> tuple[str, bool]:
    with st.container(border=True):
        section_title(3, f'{tr(lang, "manual_strategy")} (Manual Strategy)')
        if data["mode"] == "portfolio":
            st.caption(ui_text(lang, "组合模式使用固定权重调仓；单标的 MA / RSI 信号策略不会套到组合上。", "Portfolio mode uses fixed-weight rebalancing; single-symbol MA / RSI signals are not applied to the portfolio."))
            param_group(ui_text(lang, "组合调仓参数", "Portfolio Rebalance Parameters"))
            p1, p2, p3 = st.columns(3)
            rebalance_frequency = p1.selectbox(
                ui_text(lang, "调仓频率", "Rebalance Frequency"),
                ["monthly", "weekly", "daily"],
                format_func=lambda v: {"monthly": ui_text(lang, "月度", "Monthly"), "weekly": ui_text(lang, "周度", "Weekly"), "daily": ui_text(lang, "日度", "Daily")}[v],
                key="portfolio_rebalance_frequency",
            )
            rebalance_threshold = p2.number_input(ui_text(lang, "调仓阈值", "Rebalance Threshold"), min_value=0.0, max_value=1.0, value=0.05, step=0.01, format="%.2f", key="portfolio_rebalance_threshold")
            cash_buffer = p3.number_input(ui_text(lang, "现金保留", "Cash Buffer"), min_value=0.0, max_value=0.5, value=0.02, step=0.01, format="%.2f", key="portfolio_cash_buffer")
            c1, c2 = st.columns(2)
            commission_abs = c1.number_input(ui_text(lang, "每笔固定手续费", "Fixed Commission Per Trade"), min_value=0.0, value=1.0, step=0.5, key="portfolio_commission_abs")
            c2.text_input(ui_text(lang, "执行价格", "Execution Price"), value="next_open", disabled=True, key="portfolio_execution_next_open")
            if data["execution_price"] != "next_open":
                st.warning(ui_text(lang, "组合调仓当前只支持 next_open，已在 YAML 中自动使用 next_open。", "Portfolio rebalancing currently supports next_open only; YAML will use next_open."))
            try:
                generated_yaml = build_portfolio_yaml(data, rebalance_frequency, rebalance_threshold, cash_buffer, commission_abs)
            except Exception as exc:
                generated_yaml = f"# {exc}"
            run_clicked = st.button(
                tr(lang, "run_backtest"),
                type="primary",
                use_container_width=True,
                key="v2_run_portfolio",
                disabled=not data["is_ready"],
            )
            if not data["is_ready"]:
                st.info(ui_text(lang, "请至少确认两个标的，并把权重调到 100%，然后才能运行组合回测。", "Confirm at least two symbols and set total weight to 100% before running."))
            return generated_yaml, run_clicked

        strategy_type = st.selectbox(
            tr(lang, "strategy_type"),
            ["moving_average_cross", "rsi_reversal"],
            format_func=lambda v: tr(lang, "ma_cross") if v == "moving_average_cross" else tr(lang, "rsi_reversal"),
            key="v2_strategy",
        )
        st.caption(tr(lang, "ma_desc") if strategy_type == "moving_average_cross" else tr(lang, "rsi_desc"))
        st.caption(tr(lang, "coming_next"))

        param_group(tr(lang, "basic_params"))
        base_1, base_2, base_3 = st.columns(3)
        base_1.selectbox(tr(lang, "frequency"), [tr(lang, "daily")], key="frequency_daily")
        base_2.number_input(tr(lang, "signal_delay"), min_value=1, max_value=5, value=1, step=1, key="signal_delay")
        base_3.selectbox(tr(lang, "signal_direction"), [tr(lang, "long_only")], key="signal_direction")

        param_group(tr(lang, "strategy_params"))
        if strategy_type == "moving_average_cross":
            p1, p2, p3 = st.columns(3)
            p1.selectbox(tr(lang, "price_field"), ["close"], key="price_field_ma")
            short_window = p2.number_input(tr(lang, "short_window"), min_value=1, value=20, step=1, key="v2_short")
            long_window = p3.number_input(tr(lang, "long_window"), min_value=2, value=60, step=1, key="v2_long")
            rsi_window, entry_threshold, exit_threshold = 14, 30.0, 70.0
        else:
            p1, p2, p3 = st.columns(3)
            rsi_window = p1.number_input(tr(lang, "rsi_window"), min_value=1, value=14, step=1, key="v2_rsi_window")
            entry_threshold = p2.number_input(tr(lang, "entry_threshold"), min_value=0.0, max_value=100.0, value=30.0, step=1.0, key="v2_rsi_entry")
            exit_threshold = p3.number_input(tr(lang, "exit_threshold"), min_value=0.0, max_value=100.0, value=70.0, step=1.0, key="v2_rsi_exit")
            short_window, long_window = 20, 60

        param_group(tr(lang, "risk_cost"))
        r1, r2, r3 = st.columns(3)
        r1.selectbox(tr(lang, "position_mode"), [tr(lang, "full_position")], key="position_mode")
        r2.text_input(tr(lang, "position_pct"), value="100%", disabled=True, key="position_pct")
        r3.selectbox(tr(lang, "stop_loss"), [tr(lang, "none")], key="stop_loss")

        if not data["is_ready"]:
            generated_yaml = "# " + ui_text(lang, "请先搜索并确认一个标的，确认后这里会生成可运行的 YAML。", "Search and confirm one symbol first. A runnable YAML config will appear here after confirmation.")
        else:
            try:
                generated_yaml = build_manual_yaml(
                    data["market"],
                    data["symbol"],
                    data["start"],
                    data["end"],
                    data["initial_cash"],
                    data["execution_price"],
                    data["commission_pct"],
                    data["slippage_pct"],
                    strategy_type,
                    int(short_window),
                    int(long_window),
                    int(rsi_window),
                    float(entry_threshold),
                    float(exit_threshold),
                )
            except Exception as exc:
                generated_yaml = f"# {exc}"

        run_clicked = st.button(tr(lang, "run_backtest"), type="primary", use_container_width=True, key="v2_run_manual", disabled=not data["is_ready"])
    return generated_yaml, run_clicked


def render_yaml_panel(lang: str, yaml_text: str) -> str:
    with st.container(border=True):
        top_1, top_2, top_3 = st.columns([1, 0.26, 0.26])
        with top_1:
            section_title(4, tr(lang, "yaml_preview"))
        with top_2:
            st.download_button(
                tr(lang, "copy_yaml"),
                data=yaml_text.encode("utf-8"),
                file_name="tradetest_strategy.yaml",
                mime="application/x-yaml",
                use_container_width=True,
                key="v2_download_yaml",
            )
        with top_3:
            edit_yaml = st.toggle(tr(lang, "edit_yaml"), value=False, key="v2_edit_yaml")

        if edit_yaml:
            return st.text_area("YAML", value=yaml_text, height=440, key="v2_manual_yaml_edit")
        render_yaml_code(yaml_text)
        return yaml_text


def render_upload_mode(lang: str, cloud: CloudStore, terminal_id: str, config_name: str) -> None:
    st.caption(tr(lang, "yaml_tip"))
    buttons = st.columns(3)
    buttons[0].download_button(tr(lang, "ma_template"), data=STANDARD_MA_TEMPLATE.encode("utf-8"), file_name="ma_cross.yaml", mime="application/x-yaml", use_container_width=True, key="ma_template")
    buttons[1].download_button(tr(lang, "rsi_template"), data=STANDARD_RSI_TEMPLATE.encode("utf-8"), file_name="rsi_reversal.yaml", mime="application/x-yaml", use_container_width=True, key="rsi_template")
    buttons[2].download_button(tr(lang, "legacy_template"), data=LEGACY_PORTFOLIO_TEMPLATE.encode("utf-8"), file_name="portfolio_template.yaml", mime="application/x-yaml", use_container_width=True, key="legacy_template")

    uploaded = st.file_uploader(tr(lang, "upload_config"), type=["yaml", "yml"], key="v2_upload_file")
    if "v2_upload_text" not in st.session_state:
        st.session_state["v2_upload_text"] = STANDARD_MA_TEMPLATE
    if uploaded is not None:
        uploaded_bytes = uploaded.getvalue()
        upload_signature = hashlib.sha256(uploaded_bytes).hexdigest()
        if st.session_state.get("v2_upload_sig") != upload_signature:
            st.session_state["v2_upload_text"] = uploaded_bytes.decode("utf-8")
            st.session_state["v2_upload_sig"] = upload_signature

    yaml_text = st.text_area("YAML", value=st.session_state["v2_upload_text"], height=470, key="v2_upload_yaml")
    st.session_state["v2_upload_text"] = yaml_text
    if st.button(tr(lang, "run_backtest"), type="primary", use_container_width=True, key="v2_run_upload"):
        try:
            summary, portfolio_df, trades_df, report_bytes, chart_bytes, prepared_yaml = run_yaml_backtest(yaml_text)
            save_cloud_run_safely(cloud, terminal_id, config_name, prepared_yaml, summary, report_bytes, chart_bytes, lang)
            st.session_state["latest_result"] = (summary, portfolio_df, trades_df, report_bytes)
        except Exception as exc:
            st.error(f"{tr(lang, 'run_failed')}: {exc}")


def render_new_backtest(lang: str, cloud: CloudStore, terminal_id: str, config_name: str) -> None:
    render_steps(lang)
    st.markdown(f'<div class="warning-strip">{html.escape(tr(lang, "risk"))}</div>', unsafe_allow_html=True)
    input_method = st.radio(
        tr(lang, "input_source"),
        ["manual", "upload"],
        horizontal=True,
        format_func=lambda v: tr(lang, "form_config") if v == "manual" else tr(lang, "upload_yaml"),
        key="v2_input_method",
    )

    if input_method == "manual":
        left, mid, right = st.columns([0.95, 2.15, 1.7], gap="small")
        with left:
            data = render_data_panel(lang)
        with mid:
            generated_yaml, run_clicked = render_strategy_panel(lang, data)
        with right:
            yaml_text = render_yaml_panel(lang, generated_yaml)

        if run_clicked:
            try:
                summary, portfolio_df, trades_df, report_bytes, chart_bytes, prepared_yaml = run_yaml_backtest(yaml_text)
                save_cloud_run_safely(cloud, terminal_id, config_name, prepared_yaml, summary, report_bytes, chart_bytes, lang)
                st.session_state["latest_result"] = (summary, portfolio_df, trades_df, report_bytes)
            except Exception as exc:
                st.error(f"{tr(lang, 'run_failed')}: {exc}")
    else:
        render_upload_mode(lang, cloud, terminal_id, config_name)

    if "latest_result" in st.session_state:
        summary, portfolio_df, trades_df, report_bytes = st.session_state["latest_result"]
        render_results(summary, portfolio_df, trades_df, report_bytes, lang)
    else:
        render_empty_results(lang)


def render_history(lang: str, cloud: CloudStore) -> None:
    with st.container(border=True):
        section_title(2, tr(lang, "cloud_history"))
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
            st.dataframe(df[cols], use_container_width=True, height=420, hide_index=True)
            selected = st.selectbox(
                tr(lang, "open_run"),
                df["id"].tolist(),
                format_func=lambda x: f"{df[df['id'] == x].iloc[0]['created_at']} | {df[df['id'] == x].iloc[0]['config_name']}",
                key="history_selector",
            )
            row = df[df["id"] == selected].iloc[0]
            st.code(row.get("config_yaml", ""), language="yaml")
            if row.get("chart_png_url"):
                st.image(row["chart_png_url"], use_container_width=True)
            if row.get("report_xlsx_url"):
                st.link_button(tr(lang, "open_report"), row["report_xlsx_url"], use_container_width=True)
        except Exception as exc:
            st.error(str(exc))


def render_footer(lang: str) -> None:
    st.markdown(
        f"""
<div class="footer-bar">
  <div>{html.escape(tr(lang, "risk"))}</div>
  <div>{html.escape(tr(lang, "footer_source"))}: Yahoo Finance / Tushare</div>
  <div>{html.escape(tr(lang, "footer_update"))}: {pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(page_title=APP_NAME, page_icon="TT", layout="wide", initial_sidebar_state="expanded")
    inject_css()
    cloud = CloudStore(get_streamlit_secrets())
    lang, page, terminal_id, config_name = render_sidebar("zh", cloud)

    render_header(lang)
    if page == "new":
        render_new_backtest(lang, cloud, terminal_id, config_name)
    else:
        render_history(lang, cloud)
    render_footer(lang)


if __name__ == "__main__":
    main()
