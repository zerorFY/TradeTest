
import math
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

import backtest


STANDARD_SECTIONS = {"strategy", "data", "indicators", "entry", "exit", "position", "execution", "cost"}
SUPPORTED_INDICATORS = {"sma", "ema", "rsi"}
SUPPORTED_OPERATORS = {">", "<", ">=", "<=", "==", "cross_above", "cross_below"}


@dataclass
class ParsedRuleConfig:
    cfg: dict[str, Any]
    market: str
    currency: str
    symbol: str
    symbol_name: str
    start: str
    end: str | None
    initial_cash: float
    execution_price: str
    commission_pct: float
    slippage_pct: float


class RuleConfigError(ValueError):
    """User-facing validation error for standard rule YAML."""


def is_standard_rule_config(cfg: dict[str, Any] | None) -> bool:
    if not isinstance(cfg, dict):
        return False
    return STANDARD_SECTIONS.issubset(set(cfg.keys()))


def parse_rule_config(cfg: dict[str, Any]) -> ParsedRuleConfig:
    if not is_standard_rule_config(cfg):
        missing = sorted(STANDARD_SECTIONS - set((cfg or {}).keys()))
        raise RuleConfigError(f"Missing required standard YAML section(s): {', '.join(missing)}")

    prepared = deepcopy(cfg)
    prepared = backtest.prepare_config(prepared)
    market = backtest.parse_market(prepared)
    currency = prepared.get("account", {}).get("currency", backtest.currency_for_market(market))

    symbols, names = backtest.parse_symbols(prepared)
    if len(symbols) != 1:
        raise RuleConfigError("V2 rule engine currently supports exactly one symbol. Use one ticker in data.symbols.")
    symbol = symbols[0]

    data_cfg = prepared["data"]
    start = str(data_cfg.get("start") or "").strip()
    if not start:
        raise RuleConfigError("Missing required field: data.start")
    end_raw = data_cfg.get("end")
    end = str(end_raw).strip() if end_raw else None

    position_cfg = prepared.get("position", {})
    mode = str(position_cfg.get("mode", "full_position")).strip().lower()
    if mode != "full_position":
        raise RuleConfigError("position.mode must be full_position in V2 first release.")
    initial_cash = float(position_cfg.get("initial_cash", 0))
    if initial_cash <= 0:
        raise RuleConfigError("position.initial_cash must be greater than 0.")

    execution_price = str(prepared.get("execution", {}).get("price", "next_open")).strip().lower()
    if execution_price not in {"next_open", "close"}:
        raise RuleConfigError("execution.price must be next_open or close.")

    cost_cfg = prepared.get("cost", {})
    commission_pct = float(cost_cfg.get("commission_pct", 0.0))
    slippage_pct = float(cost_cfg.get("slippage_pct", 0.0))
    if commission_pct < 0 or slippage_pct < 0:
        raise RuleConfigError("commission_pct and slippage_pct must be non-negative.")

    validate_strategy(prepared)

    return ParsedRuleConfig(
        cfg=prepared,
        market=market,
        currency=currency,
        symbol=symbol,
        symbol_name=names.get(symbol, symbol),
        start=start,
        end=end,
        initial_cash=initial_cash,
        execution_price=execution_price,
        commission_pct=commission_pct,
        slippage_pct=slippage_pct,
    )


def validate_strategy(cfg: dict[str, Any]) -> None:
    strategy_type = str(cfg.get("strategy", {}).get("type", "")).strip().lower()
    indicators = cfg.get("indicators", {})
    if not isinstance(indicators, dict) or not indicators:
        raise RuleConfigError("indicators must be a non-empty mapping.")

    for name, spec in indicators.items():
        if not isinstance(spec, dict):
            raise RuleConfigError(f"Indicator {name} must be a mapping.")
        ind_type = str(spec.get("type", "")).strip().lower()
        if ind_type not in SUPPORTED_INDICATORS:
            raise RuleConfigError(f"Unknown indicator type: {ind_type}")
        window = int(spec.get("window", 0))
        if window <= 0:
            raise RuleConfigError(f"Indicator {name} window must be a positive integer.")

    if strategy_type == "moving_average_cross":
        sma_windows = [int(v.get("window", 0)) for v in indicators.values() if str(v.get("type", "")).lower() in {"sma", "ema"}]
        if len(sma_windows) >= 2 and min(sma_windows) >= max(sma_windows):
            raise RuleConfigError("short_window must be smaller than long_window.")
    elif strategy_type == "rsi_reversal":
        thresholds = []
        for section in ["entry", "exit"]:
            for cond in _condition_list(cfg.get(section, {}), "all" if section == "entry" else "any"):
                if isinstance(cond.get("right"), (int, float)):
                    thresholds.append(float(cond["right"]))
        for threshold in thresholds:
            if threshold < 0 or threshold > 100:
                raise RuleConfigError("RSI thresholds must be between 0 and 100.")
        if len(thresholds) >= 2 and min(thresholds) >= max(thresholds):
            raise RuleConfigError("entry_threshold must be smaller than exit_threshold.")
    else:
        raise RuleConfigError("strategy.type must be moving_average_cross or rsi_reversal in V2 first release.")

    for section, mode in [("entry", "all"), ("exit", "any")]:
        conditions = _condition_list(cfg.get(section, {}), mode)
        if not conditions:
            raise RuleConfigError(f"{section}.{mode} must contain at least one condition.")
        for cond in conditions:
            op = str(cond.get("operator", "")).strip()
            if op not in SUPPORTED_OPERATORS:
                raise RuleConfigError(f"Unsupported operator: {op}")


def _condition_list(section: dict[str, Any], mode: str) -> list[dict[str, Any]]:
    if not isinstance(section, dict):
        return []
    conditions = section.get(mode, [])
    return conditions if isinstance(conditions, list) else []


def compute_indicators(price_df: pd.DataFrame, indicator_specs: dict[str, Any]) -> pd.DataFrame:
    out = price_df.copy()
    for name, spec in indicator_specs.items():
        ind_type = str(spec.get("type", "")).strip().lower()
        field = str(spec.get("field", "close")).strip().lower()
        window = int(spec.get("window", 0))
        if field not in out.columns:
            raise RuleConfigError(f"Unknown indicator field: {field}")
        series = out[field].astype(float)

        if ind_type == "sma":
            out[name] = series.rolling(window).mean()
        elif ind_type == "ema":
            out[name] = series.ewm(span=window, adjust=False).mean()
        elif ind_type == "rsi":
            delta = series.diff()
            gain = delta.clip(lower=0).rolling(window).mean()
            loss = (-delta.clip(upper=0)).rolling(window).mean()
            rs = gain / loss.replace(0, np.nan)
            out[name] = 100 - (100 / (1 + rs))
            out[name] = out[name].fillna(50)
        else:
            raise RuleConfigError(f"Unknown indicator type: {ind_type}")
    return out


def _resolve_operand(df: pd.DataFrame, operand: Any) -> pd.Series | float:
    if isinstance(operand, (int, float)):
        return float(operand)
    key = str(operand).strip()
    lower_key = key.lower()
    if key in df.columns:
        return df[key].astype(float)
    if lower_key in df.columns:
        return df[lower_key].astype(float)
    try:
        return float(key)
    except ValueError as exc:
        raise RuleConfigError(f"Unknown condition operand: {operand}") from exc


def evaluate_condition(df: pd.DataFrame, cond: dict[str, Any]) -> pd.Series:
    left = _resolve_operand(df, cond.get("left"))
    right = _resolve_operand(df, cond.get("right"))
    op = str(cond.get("operator", "")).strip()

    if not isinstance(left, pd.Series):
        left = pd.Series(left, index=df.index)
    if not isinstance(right, pd.Series):
        right = pd.Series(right, index=df.index)

    if op == ">":
        return left > right
    if op == "<":
        return left < right
    if op == ">=":
        return left >= right
    if op == "<=":
        return left <= right
    if op == "==":
        return left == right
    if op == "cross_above":
        return (left.shift(1) <= right.shift(1)) & (left > right)
    if op == "cross_below":
        return (left.shift(1) >= right.shift(1)) & (left < right)
    raise RuleConfigError(f"Unsupported operator: {op}")


def evaluate_conditions(df: pd.DataFrame, conditions: list[dict[str, Any]], mode: str) -> pd.Series:
    evaluated = [evaluate_condition(df, cond).fillna(False) for cond in conditions]
    if not evaluated:
        return pd.Series(False, index=df.index)
    result = evaluated[0].copy()
    for item in evaluated[1:]:
        result = result & item if mode == "all" else result | item
    return result.fillna(False)


def build_target_position(df: pd.DataFrame, cfg: dict[str, Any]) -> pd.Series:
    entry = evaluate_conditions(df, _condition_list(cfg.get("entry", {}), "all"), "all")
    exit_ = evaluate_conditions(df, _condition_list(cfg.get("exit", {}), "any"), "any")
    state = 0
    targets = []
    for idx in df.index:
        if state == 0 and bool(entry.loc[idx]):
            state = 1
        elif state == 1 and bool(exit_.loc[idx]):
            state = 0
        targets.append(state)
    return pd.Series(targets, index=df.index, dtype=int)


def run_rule_backtest(cfg: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any], dict[str, Any]]:
    parsed = parse_rule_config(cfg)
    open_prices, close_prices = backtest.download_prices([parsed.symbol], parsed.start, parsed.end)
    price_df = pd.DataFrame(
        {
            "Date": close_prices.index,
            "open": open_prices[parsed.symbol].values,
            "close": close_prices[parsed.symbol].values,
        }
    ).set_index("Date")
    price_df = compute_indicators(price_df, parsed.cfg.get("indicators", {}))
    target = build_target_position(price_df, parsed.cfg)
    exec_target = target.shift(1).fillna(0).astype(int) if parsed.execution_price == "next_open" else target.astype(int)

    cash = float(parsed.initial_cash)
    shares = 0
    cost_basis = 0.0
    entry_date = None
    rows = []
    trades = []

    for dt, row in price_df.iterrows():
        exec_px_raw = float(row["open"] if parsed.execution_price == "next_open" else row["close"])
        close_px = float(row["close"])
        wanted = int(exec_target.loc[dt])

        if wanted == 1 and shares == 0:
            buy_px = exec_px_raw * (1 + parsed.slippage_pct)
            qty = math.floor(cash / (buy_px * (1 + parsed.commission_pct)))
            if qty > 0:
                gross = qty * buy_px
                commission = gross * parsed.commission_pct
                cash -= gross + commission
                shares = qty
                cost_basis = gross + commission
                entry_date = dt
                trades.append(
                    {
                        "date": dt,
                        "symbol": parsed.symbol,
                        "action": "BUY",
                        "price": buy_px,
                        "shares": qty,
                        "commission": commission,
                        "cash_after": cash,
                        "position_pct": 1.0,
                        "pnl_pct": pd.NA,
                        "holding_days": pd.NA,
                    }
                )
        elif wanted == 0 and shares > 0:
            sell_px = exec_px_raw * (1 - parsed.slippage_pct)
            gross = shares * sell_px
            commission = gross * parsed.commission_pct
            proceeds = gross - commission
            cash += proceeds
            pnl_pct = proceeds / cost_basis - 1.0 if cost_basis > 0 else 0.0
            holding_days = int((pd.to_datetime(dt) - pd.to_datetime(entry_date)).days) if entry_date is not None else 0
            trades.append(
                {
                    "date": dt,
                    "symbol": parsed.symbol,
                    "action": "SELL",
                    "price": sell_px,
                    "shares": shares,
                    "commission": commission,
                    "cash_after": cash,
                    "position_pct": 0.0,
                    "pnl_pct": pnl_pct,
                    "holding_days": holding_days,
                }
            )
            shares = 0
            cost_basis = 0.0
            entry_date = None

        market_value = shares * close_px
        equity = cash + market_value
        rows.append(
            {
                "Date": dt,
                "equity": equity,
                "cash": cash,
                "market_value": market_value,
                "position_shares": shares,
                "close": close_px,
                "signal": int(target.loc[dt]),
                "exec_signal": wanted,
            }
        )

    portfolio_df = pd.DataFrame(rows)
    portfolio_df["drawdown"] = portfolio_df["equity"] / portfolio_df["equity"].cummax() - 1.0
    first_close = float(price_df["close"].iloc[0])
    portfolio_df["buy_hold_equity"] = parsed.initial_cash * portfolio_df["close"] / first_close
    trades_df = pd.DataFrame(trades)
    if trades_df.empty:
        trades_df = pd.DataFrame(columns=["date", "symbol", "action", "price", "shares", "commission", "cash_after", "position_pct", "pnl_pct", "holding_days"])

    summary = calculate_summary(portfolio_df, trades_df, parsed)
    return portfolio_df, trades_df, summary, parsed.cfg


def calculate_summary(portfolio_df: pd.DataFrame, trades_df: pd.DataFrame, parsed: ParsedRuleConfig) -> dict[str, Any]:
    final_equity = float(portfolio_df["equity"].iloc[-1])
    total_return = final_equity / parsed.initial_cash - 1.0
    start_date = pd.to_datetime(portfolio_df["Date"].iloc[0])
    end_date = pd.to_datetime(portfolio_df["Date"].iloc[-1])
    days = max(1, int((end_date - start_date).days))
    annual_return = (1 + total_return) ** (365.25 / days) - 1 if total_return > -1 else -1.0
    daily_returns = portfolio_df["equity"].pct_change().dropna()
    sharpe = 0.0
    if len(daily_returns) > 1 and float(daily_returns.std()) > 0:
        sharpe = float(daily_returns.mean() / daily_returns.std() * math.sqrt(252))

    sell_trades = trades_df[trades_df["action"] == "SELL"].copy() if not trades_df.empty else pd.DataFrame()
    pnl = pd.to_numeric(sell_trades.get("pnl_pct", pd.Series(dtype=float)), errors="coerce").dropna()
    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]
    win_rate = float(len(wins) / len(pnl)) if len(pnl) else 0.0
    profit_factor = float(wins.sum() / abs(losses.sum())) if len(losses) and abs(losses.sum()) > 0 else (float("inf") if len(wins) else 0.0)
    avg_holding = float(pd.to_numeric(sell_trades.get("holding_days", pd.Series(dtype=float)), errors="coerce").dropna().mean()) if not sell_trades.empty else 0.0
    buy_hold_return = float(portfolio_df["buy_hold_equity"].iloc[-1] / parsed.initial_cash - 1.0)

    return {
        "market": parsed.market,
        "currency": parsed.currency,
        "strategy_type": parsed.cfg.get("strategy", {}).get("type", ""),
        "strategy_name": parsed.cfg.get("strategy", {}).get("name", ""),
        "execution_timing": parsed.execution_price,
        "rebalance_frequency": "",
        "symbols": parsed.symbol,
        "symbol_names": f"{parsed.symbol}:{parsed.symbol_name}",
        "start": str(start_date.date()),
        "end": str(end_date.date()),
        "initial_cash": parsed.initial_cash,
        "final_equity": final_equity,
        "total_return": total_return,
        "annual_return": annual_return,
        "max_drawdown": float(portfolio_df["drawdown"].min()) if len(portfolio_df) else 0.0,
        "sharpe_ratio": sharpe,
        "win_rate": win_rate,
        "trade_count": int((trades_df["action"] == "BUY").sum()) if not trades_df.empty else 0,
        "average_holding_days": avg_holding,
        "profit_factor": profit_factor,
        "cost_adjusted_return": total_return,
        "buy_hold_return": buy_hold_return,
    }
