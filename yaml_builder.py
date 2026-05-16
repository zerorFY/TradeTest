
from __future__ import annotations

from typing import Any

import yaml


def build_common_data(market: str, symbol: str, start: str, end: str | None) -> dict[str, Any]:
    return {
        "market": market,
        "symbols": [symbol.strip()],
        "timeframe": "1d",
        "start": start,
        "end": end or None,
    }


def build_moving_average_config(
    market: str,
    symbol: str,
    start: str,
    end: str | None,
    initial_cash: float,
    execution_price: str,
    commission_pct: float,
    slippage_pct: float,
    short_window: int,
    long_window: int,
    price_field: str = "close",
) -> dict[str, Any]:
    if short_window <= 0 or long_window <= 0:
        raise ValueError("Moving-average windows must be positive integers.")
    if short_window >= long_window:
        raise ValueError("short_window must be smaller than long_window.")
    return {
        "strategy": {"name": "Moving Average Cross", "type": "moving_average_cross"},
        "data": build_common_data(market, symbol, start, end),
        "indicators": {
            "short_ma": {"type": "sma", "field": price_field, "window": int(short_window)},
            "long_ma": {"type": "sma", "field": price_field, "window": int(long_window)},
        },
        "entry": {"all": [{"left": "short_ma", "operator": "cross_above", "right": "long_ma"}]},
        "exit": {"any": [{"left": "short_ma", "operator": "cross_below", "right": "long_ma"}]},
        "position": {"mode": "full_position", "initial_cash": float(initial_cash)},
        "execution": {"price": execution_price},
        "cost": {"commission_pct": float(commission_pct), "slippage_pct": float(slippage_pct)},
    }


def build_rsi_reversal_config(
    market: str,
    symbol: str,
    start: str,
    end: str | None,
    initial_cash: float,
    execution_price: str,
    commission_pct: float,
    slippage_pct: float,
    rsi_window: int,
    entry_threshold: float,
    exit_threshold: float,
    price_field: str = "close",
) -> dict[str, Any]:
    if rsi_window <= 0:
        raise ValueError("rsi_window must be a positive integer.")
    if not 0 <= entry_threshold <= 100 or not 0 <= exit_threshold <= 100:
        raise ValueError("RSI thresholds must be between 0 and 100.")
    if entry_threshold >= exit_threshold:
        raise ValueError("entry_threshold must be smaller than exit_threshold.")
    return {
        "strategy": {"name": "RSI Reversal", "type": "rsi_reversal"},
        "data": build_common_data(market, symbol, start, end),
        "indicators": {
            "rsi": {"type": "rsi", "field": price_field, "window": int(rsi_window)},
        },
        "entry": {"all": [{"left": "rsi", "operator": "<", "right": float(entry_threshold)}]},
        "exit": {"any": [{"left": "rsi", "operator": ">", "right": float(exit_threshold)}]},
        "position": {"mode": "full_position", "initial_cash": float(initial_cash)},
        "execution": {"price": execution_price},
        "cost": {"commission_pct": float(commission_pct), "slippage_pct": float(slippage_pct)},
    }


def config_to_yaml(cfg: dict[str, Any]) -> str:
    return yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True)
