import tempfile
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
import yaml

import backtest
from cloud_store import CloudStore, default_terminal_id


APP_NAME = "TradeTest"

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

GPT_CONFIG_PROMPTS = {
    "en": """You are helping me create a TradeTest backtest YAML config.

Use the YAML template below as the exact format. Keep the same top-level sections:
data, account, costs, strategy, report.

My natural-language request:
[Write your request here. Example: Backtest a Canadian ETF portfolio with VFV.TO 50%, QQC.TO 30%, XEI.TO 20%, starting from 2021-01-01, initial cash 20000 CAD, monthly rebalance, next open execution.]

Rules:
- Return only valid YAML.
- Do not add Markdown fences.
- For multiple stocks, use data.symbols as a mapping from ticker to display name.
- target_weights must add up to about 1.0.
- Use execution_timing: "next_open".
- rebalance_frequency can be "daily", "weekly", or "monthly".
- end can be null if I want the latest available data.

YAML template:
""",
    "zh": """你正在帮我创建一个 TradeTest 回测 YAML 配置。

请严格按照下面的 YAML 模板格式生成，保留相同的顶层结构：
data, account, costs, strategy, report。

我的自然语言需求：
[在这里写你的需求。例如：帮我回测一个加拿大 ETF 组合，VFV.TO 50%，QQC.TO 30%，XEI.TO 20%，从 2021-01-01 开始，初始资金 20000 加币，每月调仓，信号后下一个交易日开盘执行。]

规则：
- 只返回有效 YAML。
- 不要添加 Markdown 代码块。
- 多只股票时，使用 data.symbols，把股票代码映射到显示名称。
- target_weights 加起来应接近 1.0。
- 使用 execution_timing: "next_open"。
- rebalance_frequency 可以是 "daily"、"weekly" 或 "monthly"。
- 如果我要使用最新可用数据，end 可以填 null。

YAML 模板：
""",
}

I18N = {
    "en": {
        "language": "Language",
        "caption": "Backtest workspace with guided config, YAML upload, cloud history, and report download.",
        "intro": """
TradeTest helps you run stock or ETF backtests from either a guided form or a YAML config.
It supports multi-symbol portfolios, daily/weekly/monthly rebalancing, cloud history,
Excel reports, and downloadable charts.
""",
        "step_1": "1. Build a config with the form, upload YAML, or ask GPT to generate YAML from the template.",
        "step_2": "2. Run the backtest with next-open execution on daily market data.",
        "step_3": "3. Review results, download the Excel report, and check cloud history later.",
        "start_here": "Start here: YAML template and GPT workflow",
        "workflow": """
Recommended workflow for non-technical users:

1. Download the YAML template below.
2. Give the template to GPT.
3. Describe your strategy in natural language.
4. Ask GPT to return valid YAML in the same format.
5. Upload that YAML in the `Upload YAML` mode and run the backtest.
""",
        "download_template": "Download YAML template",
        "download_prompt": "Download GPT prompt",
        "copy_prompt": "Copy this prompt to GPT if you want it to generate a config for you:",
        "settings_meaning": "What the main settings mean",
        "settings_text": """
- `symbols`: Tickers to backtest. For portfolios, use multiple tickers.
- `initial_cash`: Starting capital.
- `commission`: Fixed trading cost per order.
- `slippage`: Estimated trading price impact, for example `0.001` means 0.1%.
- `strategy.type`: Use `monthly_rebalance` for portfolio rebalancing or `ma_crossover` for moving-average signals.
- `execution_timing`: `next_open` means signals are generated from daily data and executed at the next trading day's open.
- `rebalance_frequency`: `daily`, `weekly`, or `monthly`.
- `target_weights`: Desired portfolio weights. They should add up to about `1.0`.
""",
        "risk_warning": "Backtests are research tools, not investment advice. Real trading can differ because of liquidity, taxes, spreads, data quality, and execution delays.",
        "cloud": "Cloud",
        "terminal_id": "Terminal ID",
        "config_name": "Config name",
        "cloud_enabled": "Cloud sync enabled",
        "cloud_disabled": "Set SUPABASE_URL and SUPABASE_KEY to enable cloud sync",
        "run_tab": "Run Backtest",
        "history_tab": "Cloud History",
        "config_source": "Config source",
        "guided_form": "Guided form",
        "upload_yaml": "Upload YAML",
        "strategy": "Strategy",
        "execution": "Execution",
        "rebalance": "Rebalance",
        "start": "Start",
        "end": "End",
        "tickers": "Tickers",
        "initial_cash": "Initial cash",
        "commission": "Commission",
        "slippage": "Slippage",
        "fast_ma": "Fast MA",
        "slow_ma": "Slow MA",
        "threshold": "Threshold",
        "cash_buffer": "Cash buffer",
        "run_backtest": "Run backtest",
        "strategy_help": "monthly_rebalance is portfolio rebalancing. ma_crossover uses fast/slow moving averages.",
        "execution_help": "next_open means the signal is generated from daily data and the trade executes at the next trading day's open.",
        "rebalance_help": "How often the portfolio tries to return to target weights.",
        "start_help": "First date used in the backtest.",
        "end_help": "Leave empty to use the latest available data.",
        "date_format_help": "Use YYYY-MM-DD format.",
        "tickers_help": "Comma-separated tickers. Example: VFV.TO,QQC.TO,TSLA.NE",
        "initial_cash_help": "Starting capital for the whole portfolio.",
        "commission_help": "Fixed commission cost per trade.",
        "slippage_help": "Estimated price impact. 0.001 means 0.1%.",
        "fast_ma_help": "Fast moving-average window for ma_crossover.",
        "slow_ma_help": "Slow moving-average window for ma_crossover. Must be greater than Fast MA.",
        "threshold_help": "Only rebalance when a holding drifts away from target by this amount.",
        "cash_buffer_help": "Cash kept aside instead of investing 100% of capital.",
        "yaml_tip": "Tip: Give the template to GPT, describe your strategy in natural language, then upload the YAML GPT returns.",
        "upload_config": "Upload YAML config",
        "yaml_label": "YAML",
        "saved_to_cloud": "Saved to cloud",
        "run_failed": "Run failed",
        "invalid_tickers": "At least one ticker is required",
        "invalid_ma": "Invalid MA params: require 0 < fast_ma < slow_ma",
        "final_equity": "Final Equity",
        "total_return": "Total Return",
        "max_drawdown": "Max Drawdown",
        "trade_count": "Trade Count",
        "metrics_caption": "Final Equity is ending portfolio value. Total Return is total portfolio gain/loss. Max Drawdown is the largest peak-to-trough decline. Trade Count counts BUY orders.",
        "equity_curve": "Portfolio Equity Curve",
        "equity_caption": "The equity curve shows portfolio value over time after costs, slippage, and strategy execution rules.",
        "summary_table": "Summary",
        "trade_log": "Trade log",
        "download_report": "Download Excel report",
        "history_intro": """
Cloud History stores completed backtest summaries, YAML configs, charts, and Excel reports.
Use `Terminal ID` and `Config name` in the sidebar to identify who ran each test and which config it used.
""",
        "history_disabled": "Cloud history is disabled until SUPABASE_URL and SUPABASE_KEY are set.",
        "no_runs": "No saved runs yet.",
        "open_run": "Open run",
        "open_report": "Open Excel report",
        "history_failed": "Could not load cloud history",
    },
    "zh": {
        "language": "语言",
        "caption": "支持表单配置、YAML 上传、云端历史和 Excel 报告下载的回测工作台。",
        "intro": """
TradeTest 可以通过表单或 YAML 配置运行股票/ETF 回测。
它支持多股票组合、日/周/月调仓、云端历史记录、Excel 报告和图表下载。
""",
        "step_1": "1. 用表单创建配置、上传 YAML，或让 GPT 按模板生成 YAML。",
        "step_2": "2. 使用日线数据，并按 next_open 规则执行回测。",
        "step_3": "3. 查看结果、下载 Excel 报告，并在云端历史里复查。",
        "start_here": "从这里开始：YAML 模板和 GPT 生成流程",
        "workflow": """
推荐给非技术用户的流程：

1. 下载下面的 YAML 模板。
2. 把模板发给 GPT。
3. 用自然语言描述你的策略需求。
4. 让 GPT 按同样格式返回有效 YAML。
5. 在 `上传 YAML` 模式里上传 GPT 返回的 YAML，然后运行回测。
""",
        "download_template": "下载 YAML 模板",
        "download_prompt": "下载 GPT 提示词",
        "copy_prompt": "如果你想让 GPT 生成配置，可以复制这段提示词：",
        "settings_meaning": "主要参数说明",
        "settings_text": """
- `symbols`：要回测的股票代码。组合回测可以填写多只。
- `initial_cash`：初始资金。
- `commission`：每笔交易的固定手续费。
- `slippage`：估算滑点，例如 `0.001` 表示 0.1%。
- `strategy.type`：`monthly_rebalance` 表示组合调仓，`ma_crossover` 表示均线策略。
- `execution_timing`：`next_open` 表示用日线数据生成信号，并在下一个交易日开盘执行。
- `rebalance_frequency`：可以是 `daily`、`weekly` 或 `monthly`。
- `target_weights`：目标组合权重，总和应接近 `1.0`。
""",
        "risk_warning": "回测只是研究工具，不是投资建议。真实交易会受到流动性、税费、买卖价差、数据质量和执行延迟等因素影响。",
        "cloud": "云端",
        "terminal_id": "终端 ID",
        "config_name": "配置名称",
        "cloud_enabled": "云端同步已开启",
        "cloud_disabled": "设置 SUPABASE_URL 和 SUPABASE_KEY 后可开启云端同步",
        "run_tab": "运行回测",
        "history_tab": "云端历史",
        "config_source": "配置来源",
        "guided_form": "表单配置",
        "upload_yaml": "上传 YAML",
        "strategy": "策略",
        "execution": "执行方式",
        "rebalance": "调仓频率",
        "start": "开始日期",
        "end": "结束日期",
        "tickers": "股票代码",
        "initial_cash": "初始资金",
        "commission": "手续费",
        "slippage": "滑点",
        "fast_ma": "快均线",
        "slow_ma": "慢均线",
        "threshold": "调仓阈值",
        "cash_buffer": "现金缓冲",
        "run_backtest": "运行回测",
        "strategy_help": "monthly_rebalance 表示组合调仓；ma_crossover 使用快/慢均线信号。",
        "execution_help": "next_open 表示用日线数据生成信号，并在下一个交易日开盘执行。",
        "rebalance_help": "组合尝试回到目标权重的频率。",
        "start_help": "回测使用的第一天。",
        "end_help": "留空表示使用最新可用数据。",
        "date_format_help": "请使用 YYYY-MM-DD 格式。",
        "tickers_help": "用英文逗号分隔股票代码。例如：VFV.TO,QQC.TO,TSLA.NE",
        "initial_cash_help": "整个组合的起始资金。",
        "commission_help": "每笔交易的固定手续费。",
        "slippage_help": "估算价格冲击。0.001 表示 0.1%。",
        "fast_ma_help": "ma_crossover 策略的快均线窗口。",
        "slow_ma_help": "ma_crossover 策略的慢均线窗口，必须大于快均线。",
        "threshold_help": "持仓偏离目标权重超过该数值时才调仓。",
        "cash_buffer_help": "保留的现金比例，不把 100% 资金全部投入。",
        "yaml_tip": "提示：把模板给 GPT，用自然语言描述策略，然后上传 GPT 返回的 YAML。",
        "upload_config": "上传 YAML 配置",
        "yaml_label": "YAML",
        "saved_to_cloud": "已保存到云端",
        "run_failed": "运行失败",
        "invalid_tickers": "至少需要一个股票代码",
        "invalid_ma": "均线参数无效：需要 0 < fast_ma < slow_ma",
        "final_equity": "最终资产",
        "total_return": "总收益率",
        "max_drawdown": "最大回撤",
        "trade_count": "交易次数",
        "metrics_caption": "最终资产是回测结束时的组合价值。总收益率是组合整体盈亏。最大回撤是从高点到低点的最大跌幅。交易次数统计 BUY 买入订单。",
        "equity_curve": "组合资产曲线",
        "equity_caption": "资产曲线展示扣除手续费、滑点并应用策略执行规则后的组合价值变化。",
        "summary_table": "结果摘要",
        "trade_log": "交易明细",
        "download_report": "下载 Excel 报告",
        "history_intro": """
云端历史会保存已完成回测的摘要、YAML 配置、图表和 Excel 报告。
你可以用侧边栏的 `终端 ID` 和 `配置名称` 区分是谁运行的，以及使用了哪个配置。
""",
        "history_disabled": "云端历史未开启，需要设置 SUPABASE_URL 和 SUPABASE_KEY。",
        "no_runs": "还没有保存的回测记录。",
        "open_run": "打开记录",
        "open_report": "打开 Excel 报告",
        "history_failed": "无法加载云端历史",
    },
}

SUMMARY_LABELS = {
    "en": {
        "strategy_type": "Strategy",
        "execution_timing": "Execution",
        "rebalance_frequency": "Rebalance",
        "symbols": "Tickers",
        "symbol_names": "Ticker names",
        "start": "Start",
        "end": "End",
        "initial_cash": "Initial cash",
        "final_equity": "Final equity",
        "total_return": "Total return",
        "max_drawdown": "Max drawdown",
        "trade_count": "Trade count",
        "buy_hold_return": "Buy-hold return",
    },
    "zh": {
        "strategy_type": "策略",
        "execution_timing": "执行方式",
        "rebalance_frequency": "调仓频率",
        "symbols": "股票代码",
        "symbol_names": "股票名称",
        "start": "开始日期",
        "end": "结束日期",
        "initial_cash": "初始资金",
        "final_equity": "最终资产",
        "total_return": "总收益率",
        "max_drawdown": "最大回撤",
        "trade_count": "交易次数",
        "buy_hold_return": "买入持有收益率",
    },
}

TRADE_LABELS = {
    "en": {
        "date": "Date",
        "symbol": "Ticker",
        "action": "Action",
        "price": "Price",
        "shares": "Shares",
        "commission": "Commission",
        "cash_after": "Cash after",
    },
    "zh": {
        "date": "日期",
        "symbol": "股票代码",
        "action": "操作",
        "price": "价格",
        "shares": "股数",
        "commission": "手续费",
        "cash_after": "交易后现金",
    },
}

HISTORY_LABELS = {
    "en": {
        "created_at": "Created at",
        "terminal_id": "Terminal ID",
        "config_name": "Config name",
        "strategy_type": "Strategy",
        "symbols": "Tickers",
        "total_return": "Total return",
        "max_drawdown": "Max drawdown",
        "trade_count": "Trade count",
        "report_xlsx_url": "Excel report",
    },
    "zh": {
        "created_at": "创建时间",
        "terminal_id": "终端 ID",
        "config_name": "配置名称",
        "strategy_type": "策略",
        "symbols": "股票代码",
        "total_return": "总收益率",
        "max_drawdown": "最大回撤",
        "trade_count": "交易次数",
        "report_xlsx_url": "Excel 报告",
    },
}

OPTION_LABELS = {
    "en": {
        "monthly_rebalance": "Periodic rebalance",
        "ma_crossover": "Moving average crossover",
        "next_open": "Next open",
        "daily": "Daily",
        "weekly": "Weekly",
        "monthly": "Monthly",
        "BUY": "Buy",
        "SELL": "Sell",
    },
    "zh": {
        "monthly_rebalance": "组合定期调仓",
        "ma_crossover": "均线交叉策略",
        "next_open": "下个交易日开盘",
        "daily": "每日",
        "weekly": "每周",
        "monthly": "每月",
        "BUY": "买入",
        "SELL": "卖出",
    },
}


def get_streamlit_secrets() -> dict:
    try:
        return dict(st.secrets)
    except Exception:
        return {}


def tr(lang: str, key: str) -> str:
    return I18N[lang][key]


def prompt_text(lang: str) -> str:
    return GPT_CONFIG_PROMPTS[lang] + DEFAULT_UPLOAD_CONFIG


def rename_columns(df: pd.DataFrame, labels: dict[str, str]) -> pd.DataFrame:
    return df.rename(columns={col: labels.get(col, col) for col in df.columns})


def label_for(lang: str, value: str) -> str:
    return OPTION_LABELS[lang].get(str(value), str(value))


def value_from_label(lang: str, label: str) -> str:
    reverse = {display: value for value, display in OPTION_LABELS[lang].items()}
    return reverse.get(label, label)


def localize_summary_values(df: pd.DataFrame, lang: str) -> pd.DataFrame:
    output = df.copy()
    for col in ["strategy_type", "execution_timing", "rebalance_frequency"]:
        if col in output.columns:
            output[col] = output[col].map(lambda value: label_for(lang, value) if value else value)
    return output


def localize_trade_values(df: pd.DataFrame, lang: str) -> pd.DataFrame:
    output = df.copy()
    if "action" in output.columns:
        output["action"] = output["action"].map(lambda value: label_for(lang, value))
    return output


def render_intro(lang: str) -> None:
    st.markdown(tr(lang, "intro"))

    step1, step2, step3 = st.columns(3)
    step1.info(tr(lang, "step_1"))
    step2.info(tr(lang, "step_2"))
    step3.info(tr(lang, "step_3"))

    with st.expander(tr(lang, "start_here"), expanded=True):
        st.markdown(tr(lang, "workflow"))
        t1, t2 = st.columns(2)
        with t1:
            st.download_button(
                tr(lang, "download_template"),
                data=DEFAULT_UPLOAD_CONFIG.encode("utf-8"),
                file_name="tradetest_config_template.yaml",
                mime="application/x-yaml",
                key=f"download_template_intro_{lang}",
                use_container_width=True,
            )
        with t2:
            st.download_button(
                tr(lang, "download_prompt"),
                data=prompt_text(lang).encode("utf-8"),
                file_name=f"tradetest_gpt_prompt_{lang}.txt",
                mime="text/plain",
                key=f"download_prompt_intro_{lang}",
                use_container_width=True,
            )

        st.markdown(tr(lang, "copy_prompt"))
        st.code(prompt_text(lang), language="text")

    with st.expander(tr(lang, "settings_meaning")):
        st.markdown(tr(lang, "settings_text"))

    st.warning(tr(lang, "risk_warning"))


def run_backtest_from_cfg(cfg: dict, config_text_raw: str, lang: str):
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
            raise ValueError(tr(lang, "invalid_ma"))
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


def render_result(summary, portfolio_df, trades_df, report_bytes, lang: str):
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(tr(lang, "final_equity"), f"{summary['final_equity']:.2f}")
    m2.metric(tr(lang, "total_return"), f"{summary['total_return']:.2%}")
    m3.metric(tr(lang, "max_drawdown"), f"{summary['max_drawdown']:.2%}")
    m4.metric(tr(lang, "trade_count"), str(summary["trade_count"]))
    st.caption(tr(lang, "metrics_caption"))

    fig = px.line(portfolio_df, x="Date", y="equity", title=tr(lang, "equity_curve"))
    fig.update_layout(height=460, margin=dict(l=16, r=16, t=48, b=16))
    st.plotly_chart(fig, use_container_width=True)
    st.caption(tr(lang, "equity_caption"))

    st.markdown(tr(lang, "summary_table"))
    st.dataframe(rename_columns(localize_summary_values(pd.DataFrame([summary]), lang), SUMMARY_LABELS[lang]), use_container_width=True)

    empty_cols = ["date", "symbol", "action", "price", "shares", "commission", "cash_after"]
    display_trades = trades_df if not trades_df.empty else pd.DataFrame(columns=empty_cols)
    st.markdown(tr(lang, "trade_log"))
    st.dataframe(rename_columns(localize_trade_values(display_trades, lang), TRADE_LABELS[lang]), use_container_width=True, height=280)

    st.download_button(
        tr(lang, "download_report"),
        data=report_bytes,
        file_name="backtest_report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=f"download_report_{lang}",
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
    lang,
):
    symbols = [s.strip() for s in symbol_text.split(",") if s.strip()]
    if not symbols:
        raise ValueError(tr(lang, "invalid_tickers"))

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


st.set_page_config(page_title=APP_NAME, page_icon="TT", layout="wide")

cloud = CloudStore(get_streamlit_secrets())
with st.sidebar:
    lang_label = st.selectbox("Language / 语言", ["中文", "English"], index=0, key="language_selector")
    lang = "zh" if lang_label == "中文" else "en"

    st.header(tr(lang, "cloud"))
    terminal_id = st.text_input(tr(lang, "terminal_id"), value=default_terminal_id())
    config_name = st.text_input(tr(lang, "config_name"), value="web_config")
    if cloud.enabled:
        st.success(tr(lang, "cloud_enabled"))
    else:
        st.info(tr(lang, "cloud_disabled"))

st.title(APP_NAME)
st.caption(tr(lang, "caption"))

render_intro(lang)

main_tab, history_tab = st.tabs([tr(lang, "run_tab"), tr(lang, "history_tab")])

with main_tab:
    mode_labels = [tr(lang, "guided_form"), tr(lang, "upload_yaml")]
    mode_label = st.radio(tr(lang, "config_source"), mode_labels, horizontal=True, key="config_source")
    mode = "Guided form" if mode_label == tr(lang, "guided_form") else "Upload YAML"

    if mode == "Guided form":
        with st.form("wizard_form"):
            c1, c2, c3 = st.columns(3)
            strategy_label = c1.selectbox(
                tr(lang, "strategy"),
                [label_for(lang, "monthly_rebalance"), label_for(lang, "ma_crossover")],
                index=0,
                help=tr(lang, "strategy_help"),
                key=f"strategy_selector_{lang}",
            )
            mode_strategy = value_from_label(lang, strategy_label)
            execution_label = c2.selectbox(
                tr(lang, "execution"),
                [label_for(lang, "next_open")],
                index=0,
                help=tr(lang, "execution_help"),
                key=f"execution_selector_{lang}",
            )
            execution_timing = value_from_label(lang, execution_label)
            rebalance_label = c3.selectbox(
                tr(lang, "rebalance"),
                [label_for(lang, "daily"), label_for(lang, "weekly"), label_for(lang, "monthly")],
                index=2,
                help=tr(lang, "rebalance_help"),
                key=f"rebalance_selector_{lang}",
            )
            rebalance_frequency = value_from_label(lang, rebalance_label)

            c4, c5, c6 = st.columns(3)
            start = c4.text_input(tr(lang, "start"), value="2021-05-10", help=f"{tr(lang, 'start_help')} {tr(lang, 'date_format_help')}")
            end = c5.text_input(tr(lang, "end"), value="", help=f"{tr(lang, 'end_help')} {tr(lang, 'date_format_help')}")
            symbol_text = c6.text_input(tr(lang, "tickers"), value="VFV.TO,QQC.TO,TSLA.NE", help=tr(lang, "tickers_help"))

            c7, c8, c9 = st.columns(3)
            initial_cash = c7.number_input(tr(lang, "initial_cash"), min_value=1.0, value=10000.0, step=1000.0, help=tr(lang, "initial_cash_help"))
            commission = c8.number_input(tr(lang, "commission"), min_value=0.0, value=1.0, step=0.1, help=tr(lang, "commission_help"))
            slippage = c9.number_input(tr(lang, "slippage"), min_value=0.0, value=0.001, step=0.0001, format="%.4f", help=tr(lang, "slippage_help"))

            c10, c11, c12, c13 = st.columns(4)
            fast_ma = c10.number_input(tr(lang, "fast_ma"), min_value=1, value=20, step=1, help=tr(lang, "fast_ma_help"))
            slow_ma = c11.number_input(tr(lang, "slow_ma"), min_value=2, value=60, step=1, help=tr(lang, "slow_ma_help"))
            rebalance_threshold = c12.number_input(tr(lang, "threshold"), min_value=0.0, value=0.05, step=0.01, format="%.2f", help=tr(lang, "threshold_help"))
            cash_buffer = c13.number_input(tr(lang, "cash_buffer"), min_value=0.0, value=0.02, step=0.01, format="%.2f", help=tr(lang, "cash_buffer_help"))

            run_clicked = st.form_submit_button(tr(lang, "run_backtest"), type="primary", use_container_width=True)

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
                    lang,
                )
                cfg_text = yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True)
                st.code(cfg_text, language="yaml")
                summary, portfolio_df, trades_df, report_bytes, chart_bytes = run_backtest_from_cfg(cfg, cfg_text, lang)
                saved = cloud.save_run(
                    terminal_id=terminal_id,
                    config_name=config_name,
                    config_yaml=cfg_text,
                    summary=summary,
                    report_bytes=report_bytes,
                    chart_bytes=chart_bytes,
                )
                if saved:
                    st.toast(tr(lang, "saved_to_cloud"))
                render_result(summary, portfolio_df, trades_df, report_bytes, lang)
            except Exception as e:
                st.error(f"{tr(lang, 'run_failed')}: {e}")

    else:
        if "config_text" not in st.session_state:
            st.session_state.config_text = DEFAULT_UPLOAD_CONFIG
        u1, u2 = st.columns(2)
        with u1:
            st.download_button(
                tr(lang, "download_template"),
                data=DEFAULT_UPLOAD_CONFIG.encode("utf-8"),
                file_name="tradetest_config_template.yaml",
                mime="application/x-yaml",
                key=f"download_template_upload_{lang}",
                use_container_width=True,
            )
        with u2:
            st.download_button(
                tr(lang, "download_prompt"),
                data=prompt_text(lang).encode("utf-8"),
                file_name=f"tradetest_gpt_prompt_{lang}.txt",
                mime="text/plain",
                key=f"download_prompt_upload_{lang}",
                use_container_width=True,
            )
        st.caption(tr(lang, "yaml_tip"))
        uploaded = st.file_uploader(tr(lang, "upload_config"), type=["yaml", "yml"])
        if uploaded is not None:
            st.session_state.config_text = uploaded.getvalue().decode("utf-8")
        config_text = st.text_area(tr(lang, "yaml_label"), value=st.session_state.config_text, height=420)
        st.session_state.config_text = config_text

        if st.button(tr(lang, "run_backtest"), type="primary", use_container_width=True, key=f"run_upload_{lang}"):
            try:
                cfg = yaml.safe_load(config_text)
                summary, portfolio_df, trades_df, report_bytes, chart_bytes = run_backtest_from_cfg(cfg, config_text, lang)
                saved = cloud.save_run(
                    terminal_id=terminal_id,
                    config_name=config_name,
                    config_yaml=config_text,
                    summary=summary,
                    report_bytes=report_bytes,
                    chart_bytes=chart_bytes,
                )
                if saved:
                    st.toast(tr(lang, "saved_to_cloud"))
                render_result(summary, portfolio_df, trades_df, report_bytes, lang)
            except Exception as e:
                st.error(f"{tr(lang, 'run_failed')}: {e}")

with history_tab:
    st.markdown(tr(lang, "history_intro"))
    if not cloud.enabled:
        st.info(tr(lang, "history_disabled"))
    else:
        try:
            runs = cloud.list_runs()
            if not runs:
                st.info(tr(lang, "no_runs"))
            else:
                df = pd.DataFrame(runs)
                history_cols = [
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
                st.dataframe(
                    rename_columns(localize_summary_values(df[history_cols], lang), HISTORY_LABELS[lang]),
                    use_container_width=True,
                    height=420,
                )
                selected = st.selectbox(
                    tr(lang, "open_run"),
                    df["id"].tolist(),
                    format_func=lambda x: f"{df[df['id'] == x].iloc[0]['created_at']} | {df[df['id'] == x].iloc[0]['config_name']}",
                )
                row = df[df["id"] == selected].iloc[0]
                st.code(row["config_yaml"], language="yaml")
                if row.get("chart_png_url"):
                    st.image(row["chart_png_url"], use_container_width=True)
                if row.get("report_xlsx_url"):
                    st.link_button(tr(lang, "open_report"), row["report_xlsx_url"], use_container_width=True)
        except Exception as e:
            st.error(f"{tr(lang, 'history_failed')}: {e}")
