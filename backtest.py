import math
import os
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pandas as pd
import yfinance as yf
import yfinance.cache as yf_cache
import yaml
from openpyxl.drawing.image import Image as XLImage

if getattr(sys, "frozen", False):
    PROJECT_ROOT = Path(sys.executable).resolve().parent
else:
    PROJECT_ROOT = Path(__file__).resolve().parent
MPL_DIR = Path(os.environ.get("TEMP", str(PROJECT_ROOT))) / "quant_backtest_mpl"
MPL_DIR.mkdir(parents=True, exist_ok=True)
for lock_file in MPL_DIR.glob("*.matplotlib-lock"):
    try:
        lock_file.unlink()
    except OSError:
        pass
os.environ["MPLCONFIGDIR"] = str(MPL_DIR)

YF_CACHE_DIR = Path(os.environ.get("TEMP", str(PROJECT_ROOT))) / "yfinance_cache" / uuid4().hex
YF_CACHE_DIR.mkdir(parents=True, exist_ok=True)
try:
    yf_cache.set_cache_location(str(YF_CACHE_DIR))
except Exception:
    pass
try:
    yf.set_tz_cache_location(str(YF_CACHE_DIR))
except Exception:
    pass

import matplotlib.pyplot as plt


def select_config_file(project_root: Path) -> Path:
    env_config = os.environ.get("BACKTEST_CONFIG")
    if env_config:
        p = Path(env_config).resolve()
        if not p.exists():
            raise FileNotFoundError(f"BACKTEST_CONFIG not found: {p}")
        return p

    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as e:
        raise RuntimeError(f"Tkinter is not available: {e}")

    configs_dir = project_root / "configs"
    configs_dir.mkdir(parents=True, exist_ok=True)

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    selected = filedialog.askopenfilename(
        title="Select backtest config (YAML)",
        initialdir=str(configs_dir),
        filetypes=[("YAML files", "*.yaml *.yml"), ("All files", "*.*")],
    )
    root.destroy()

    if not selected:
        raise RuntimeError("No config file selected.")

    selected_path = Path(selected).resolve()
    if selected_path.suffix.lower() not in {".yaml", ".yml"}:
        raise ValueError("Selected file must be a .yaml or .yml file")

    return selected_path


def load_config(config_path: Path) -> dict:
    with config_path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    required = ["data", "account", "costs", "strategy"]
    for key in required:
        if key not in cfg:
            raise ValueError(f"Missing config section: {key}")

    return cfg


def parse_symbols(cfg: dict) -> tuple[list[str], dict[str, str]]:
    data_cfg = cfg["data"]
    symbols = data_cfg.get("symbols")
    symbol = data_cfg.get("symbol")

    if symbols is not None:
        if isinstance(symbols, dict):
            out = [str(k).strip() for k in symbols.keys() if str(k).strip()]
            names = {str(k).strip(): str(v) for k, v in symbols.items()}
            if out:
                return out, names
        elif isinstance(symbols, list):
            out = [str(s).strip() for s in symbols if str(s).strip()]
            if out:
                return out, {s: s for s in out}
        elif isinstance(symbols, str) and symbols.strip():
            s = symbols.strip()
            return [s], {s: s}
        else:
            raise ValueError("data.symbols must be dict/list/string when provided")

    if symbol is not None and str(symbol).strip():
        s = str(symbol).strip()
        return [s], {s: s}

    raise ValueError("Config must contain data.symbol or data.symbols")


def download_symbol_ohlc(symbol: str, start: str, end: str | None) -> pd.DataFrame:
    for key in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"]:
        os.environ.pop(key, None)

    last_err = None
    for _ in range(2):
        try:
            raw = yf.download(symbol, start=start, end=end, auto_adjust=False, progress=False, threads=False)
            if raw.empty:
                raise ValueError(f"No data downloaded for symbol={symbol}")

            if isinstance(raw.columns, pd.MultiIndex):
                open_cols = [c for c in raw.columns if c[0] == "Open"]
                close_cols = [c for c in raw.columns if c[0] == "Close"]
                if not open_cols or not close_cols:
                    raise ValueError(f"Downloaded data missing Open/Close for {symbol}")
                data = raw[[open_cols[0], close_cols[0]]].copy()
                data.columns = ["Open", "Close"]
            else:
                if "Open" not in raw.columns or "Close" not in raw.columns:
                    raise ValueError(f"Downloaded data missing Open/Close for {symbol}")
                data = raw[["Open", "Close"]].copy()

            data = data.dropna().reset_index()
            date_col = "Date" if "Date" in data.columns else data.columns[0]
            data = data.rename(columns={date_col: "Date"})
            data["Date"] = pd.to_datetime(data["Date"], errors="coerce").dt.tz_localize(None)
            data = data.dropna(subset=["Date", "Open", "Close"])
            data = data.drop_duplicates(subset=["Date"]).sort_values("Date").reset_index(drop=True)
            return data
        except Exception as e:
            last_err = e
    raise ValueError(f"Failed to download {symbol}: {last_err}") from last_err


def download_prices(symbols: list[str], start: str, end: str | None) -> tuple[pd.DataFrame, pd.DataFrame]:
    open_frames = []
    close_frames = []
    for sym in symbols:
        df = download_symbol_ohlc(sym, start, end).set_index("Date")
        open_frames.append(df[["Open"]].rename(columns={"Open": sym}))
        close_frames.append(df[["Close"]].rename(columns={"Close": sym}))

    open_prices = pd.concat(open_frames, axis=1, join="outer").sort_index().ffill().dropna(how="any")
    close_prices = pd.concat(close_frames, axis=1, join="outer").sort_index().ffill().dropna(how="any")
    common_idx = open_prices.index.intersection(close_prices.index)
    open_prices = open_prices.loc[common_idx]
    close_prices = close_prices.loc[common_idx]
    if open_prices.empty or close_prices.empty:
        raise ValueError("No overlapping price history across all symbols")
    return open_prices, close_prices


def compute_ma_signals(close: pd.Series, fast_ma: int, slow_ma: int) -> pd.Series:
    ma_fast = close.rolling(fast_ma).mean()
    ma_slow = close.rolling(slow_ma).mean()
    raw = (ma_fast > ma_slow).astype(int)
    return raw.shift(1).fillna(0).astype(int)


def run_ma_portfolio(open_prices: pd.DataFrame, close_prices: pd.DataFrame, initial_cash: float, commission: float, slippage: float, fast_ma: int, slow_ma: int, execution_timing: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    symbols = list(close_prices.columns)
    cash_per_symbol = initial_cash / len(symbols)
    all_eq = []
    all_trades = []

    for sym in symbols:
        close = close_prices[sym].dropna()
        open_px = open_prices[sym].reindex(close.index).ffill()
        signal = compute_ma_signals(close, fast_ma, slow_ma)
        df = pd.DataFrame({"Date": close.index, "Open": open_px.values, "Close": close.values, "signal": signal.values})
        if execution_timing == "next_open":
            df["exec_signal"] = df["signal"].shift(1).fillna(0).astype(int)
        else:
            raise ValueError(f"Unsupported execution_timing: {execution_timing}")

        cash = float(cash_per_symbol)
        shares = 0
        prev_signal = 0
        rows = []
        trades = []

        for _, row in df.iterrows():
            date = row["Date"]
            close_price = float(row["Close"])
            exec_px = float(row["Open"])
            sig = int(row["exec_signal"])

            if sig == 1 and prev_signal == 0 and shares == 0:
                buy_px = exec_px * (1 + slippage)
                qty = math.floor((cash - commission) / buy_px)
                if qty > 0:
                    cash -= qty * buy_px + commission
                    shares += qty
                    trades.append({"date": date, "symbol": sym, "action": "BUY", "price": buy_px, "shares": qty, "commission": commission, "cash_after": cash})

            elif sig == 0 and prev_signal == 1 and shares > 0:
                sell_px = exec_px * (1 - slippage)
                cash += shares * sell_px - commission
                trades.append({"date": date, "symbol": sym, "action": "SELL", "price": sell_px, "shares": shares, "commission": commission, "cash_after": cash})
                shares = 0

            mv = shares * close_price
            rows.append({"Date": date, "symbol": sym, "Close": close_price, "signal": sig, "position_shares": shares, "cash": cash, "market_value": mv, "equity": cash + mv})
            prev_signal = sig

        all_eq.append(pd.DataFrame(rows))
        all_trades.append(pd.DataFrame(trades))

    equity_all = pd.concat(all_eq, ignore_index=True)
    trades_all = pd.concat(all_trades, ignore_index=True) if any(not t.empty for t in all_trades) else pd.DataFrame(columns=["date", "symbol", "action", "price", "shares", "commission", "cash_after"])

    portfolio = equity_all.groupby("Date", as_index=False)["equity"].sum().sort_values("Date")
    portfolio["cash"] = pd.NA
    portfolio["market_value"] = pd.NA
    return portfolio, trades_all


def _normalize_weights(target: dict[str, float], cap: float) -> dict[str, float]:
    total = sum(max(0.0, float(v)) for v in target.values())
    if total <= 0:
        raise ValueError("target_weights sum must be > 0")
    return {k: max(0.0, float(v)) / total * cap for k, v in target.items()}


def run_periodic_rebalance(open_prices: pd.DataFrame, close_prices: pd.DataFrame, initial_cash: float, commission: float, slippage: float, strategy_cfg: dict, execution_timing: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    symbols = list(close_prices.columns)
    tw = strategy_cfg.get("target_weights")
    if not isinstance(tw, dict) or not tw:
        raise ValueError("strategy.target_weights must be a non-empty dict for monthly_rebalance")

    target_weights = {s: float(tw.get(s, 0.0)) for s in symbols}
    cash_buffer = float(strategy_cfg.get("cash_buffer", 0.0))
    threshold = float(strategy_cfg.get("rebalance_threshold", 0.0))
    max_weights = strategy_cfg.get("max_weights", {}) or {}
    min_weights = strategy_cfg.get("min_weights", {}) or {}

    cap = max(0.0, min(1.0, 1.0 - cash_buffer))
    target_weights = _normalize_weights(target_weights, cap)

    for s in symbols:
        if s in min_weights:
            target_weights[s] = max(target_weights[s], float(min_weights[s]))
        if s in max_weights:
            target_weights[s] = min(target_weights[s], float(max_weights[s]))

    target_weights = _normalize_weights(target_weights, cap)

    freq = str(strategy_cfg.get("rebalance_frequency", "monthly")).strip().lower()
    if freq not in {"daily", "weekly", "monthly"}:
        raise ValueError("rebalance_frequency must be one of: daily, weekly, monthly")

    if freq == "daily":
        signal_dates = list(close_prices.index)
    elif freq == "weekly":
        signal_dates = close_prices.groupby(close_prices.index.to_period("W")).apply(lambda x: x.index.max()).tolist()
    else:
        signal_dates = close_prices.groupby(close_prices.index.to_period("M")).apply(lambda x: x.index.max()).tolist()

    idx = list(close_prices.index)
    pos = {d: i for i, d in enumerate(idx)}
    if execution_timing == "next_open":
        rebalance_dates = {idx[pos[d] + 1] for d in signal_dates if d in pos and pos[d] + 1 < len(idx)}
    else:
        raise ValueError(f"Unsupported execution_timing: {execution_timing}")

    cash = float(initial_cash)
    shares = {s: 0 for s in symbols}
    equity_rows = []
    trades = []

    for dt in close_prices.index:
        close_row = close_prices.loc[dt]
        open_row = open_prices.loc[dt]
        px_close = {s: float(close_row[s]) for s in symbols}
        px_open = {s: float(open_row[s]) for s in symbols}
        mv_by_symbol = {s: shares[s] * px_close[s] for s in symbols}
        equity = cash + sum(mv_by_symbol.values())

        if dt in rebalance_dates and equity > 0:
            current_weights = {s: (mv_by_symbol[s] / equity if equity > 0 else 0.0) for s in symbols}

            # Sell first
            for s in symbols:
                tw_s = target_weights.get(s, 0.0)
                cw_s = current_weights.get(s, 0.0)
                if cw_s - tw_s <= threshold:
                    continue

                desired_value = equity * tw_s
                desired_shares = math.floor(desired_value / px_open[s])
                delta = desired_shares - shares[s]
                if delta < 0:
                    qty = -delta
                    sell_px = px_open[s] * (1 - slippage)
                    proceeds = qty * sell_px - commission
                    cash += proceeds
                    shares[s] -= qty
                    trades.append({"date": dt, "symbol": s, "action": "SELL", "price": sell_px, "shares": qty, "commission": commission, "cash_after": cash})

            # Buy second
            for s in symbols:
                # Recompute equity proxy after sells
                mv_now = shares[s] * px_close[s]
                total_equity_now = cash + sum(shares[k] * px_close[k] for k in symbols)
                if total_equity_now <= 0:
                    continue
                tw_s = target_weights.get(s, 0.0)
                cw_s = mv_now / total_equity_now
                if tw_s - cw_s <= threshold:
                    continue

                desired_value = total_equity_now * tw_s
                desired_shares = math.floor(desired_value / px_open[s])
                delta = desired_shares - shares[s]
                if delta > 0:
                    buy_px = px_open[s] * (1 + slippage)
                    affordable = math.floor((cash - commission) / buy_px)
                    qty = min(delta, max(0, affordable))
                    if qty > 0:
                        cost = qty * buy_px + commission
                        cash -= cost
                        shares[s] += qty
                        trades.append({"date": dt, "symbol": s, "action": "BUY", "price": buy_px, "shares": qty, "commission": commission, "cash_after": cash})

            mv_by_symbol = {s: shares[s] * px_close[s] for s in symbols}
            equity = cash + sum(mv_by_symbol.values())

        equity_rows.append({"Date": dt, "equity": equity, "cash": cash, "market_value": equity - cash})

    portfolio = pd.DataFrame(equity_rows)
    trades_df = pd.DataFrame(trades)
    return portfolio, trades_df


def max_drawdown(equity: pd.Series) -> float:
    running_max = equity.cummax()
    drawdown = equity / running_max - 1.0
    return float(drawdown.min()) if len(drawdown) else 0.0


def _flatten_config(d: dict, prefix: str = "") -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else str(k)
        if isinstance(v, dict):
            rows.extend(_flatten_config(v, key))
        elif isinstance(v, list):
            rows.append((key, ", ".join([str(x) for x in v])))
        else:
            rows.append((key, str(v)))
    return rows


def save_outputs(result_dir: Path, equity_df: pd.DataFrame, trades_df: pd.DataFrame, summary: dict, cfg: dict, config_path: Path) -> None:
    result_dir.mkdir(parents=True, exist_ok=True)

    for legacy_name in ["equity_curve.csv", "trades.csv", "summary.xlsx"]:
        legacy_file = result_dir / legacy_name
        if legacy_file.exists():
            try:
                legacy_file.unlink()
            except OSError:
                pass

    run_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_xlsx = result_dir / f"backtest_report_{run_tag}.xlsx"
    equity_png = result_dir / f"equity_curve_{run_tag}.png"

    config_rows = _flatten_config(cfg)
    config_flat_df = pd.DataFrame(config_rows, columns=["key", "value"])
    config_yaml_text = config_path.read_text(encoding="utf-8")
    config_yaml_df = pd.DataFrame({"yaml": config_yaml_text.splitlines()})

    plt.figure(figsize=(10, 5))
    plt.plot(equity_df["Date"], equity_df["equity"], label="Portfolio Equity")
    plt.title("Portfolio Equity Curve")
    plt.xlabel("Date")
    plt.ylabel("Equity")
    plt.grid(alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(equity_png, dpi=150)
    plt.close()

    with pd.ExcelWriter(report_xlsx, engine="openpyxl") as writer:
        pd.DataFrame([summary]).to_excel(writer, sheet_name="summary", index=False)
        equity_df.to_excel(writer, sheet_name="equity_curve", index=False)
        trades_df.to_excel(writer, sheet_name="trades", index=False)
        config_flat_df.to_excel(writer, sheet_name="config_flat", index=False)
        config_yaml_df.to_excel(writer, sheet_name="config_yaml", index=False)
        chart_ws = writer.book.create_sheet("equity_chart")
        chart_ws["A1"] = "Embedded chart image"
        chart_ws.add_image(XLImage(str(equity_png)), "A3")


def main() -> None:
    config_path = select_config_file(PROJECT_ROOT)
    cfg = load_config(config_path)

    try:
        symbols, symbol_names = parse_symbols(cfg)
    except ValueError as e:
        raise ValueError(f"{e} (config: {config_path})") from e

    start = cfg["data"]["start"]
    end = cfg["data"].get("end") or datetime.today().strftime("%Y-%m-%d")

    initial_cash = float(cfg["account"]["initial_cash"])
    commission = float(cfg["costs"]["commission"])
    slippage = float(cfg["costs"]["slippage"])

    strategy_cfg = cfg.get("strategy", {})
    strategy_type = str(strategy_cfg.get("type", "ma_crossover")).strip().lower()
    fast_ma = int(strategy_cfg.get("fast_ma", 20))
    slow_ma = int(strategy_cfg.get("slow_ma", 60))
    execution_timing = str(strategy_cfg.get("execution_timing", "next_open")).strip().lower()
    rebalance_frequency = str(strategy_cfg.get("rebalance_frequency", "monthly")).strip().lower()

    open_prices, close_prices = download_prices(symbols, start, end)

    if strategy_type == "monthly_rebalance":
        portfolio_df, trades_df = run_periodic_rebalance(open_prices, close_prices, initial_cash, commission, slippage, strategy_cfg, execution_timing)
    else:
        if fast_ma <= 0 or slow_ma <= 0 or fast_ma >= slow_ma:
            raise ValueError("Invalid MA params: require 0 < fast_ma < slow_ma")
        portfolio_df, trades_df = run_ma_portfolio(open_prices, close_prices, initial_cash, commission, slippage, fast_ma, slow_ma, execution_timing)

    final_equity = float(portfolio_df["equity"].iloc[-1])
    total_return = final_equity / initial_cash - 1.0
    mdd = max_drawdown(portfolio_df["equity"])

    bh_returns = []
    for s in symbols:
        bh_returns.append(float(close_prices[s].iloc[-1] / close_prices[s].iloc[0] - 1.0))
    buy_hold_return = float(sum(bh_returns) / len(bh_returns)) if bh_returns else 0.0

    out_base = cfg.get("report", {}).get("output_dir", "results")
    out_base_path = Path(out_base)
    if not out_base_path.is_absolute():
        out_base_path = PROJECT_ROOT / out_base_path
    result_dir = out_base_path / f"{config_path.stem}_result"

    summary = {
        "config_file": str(config_path),
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

    save_outputs(result_dir, portfolio_df, trades_df, summary, cfg, config_path)

    print("Backtest finished successfully.")
    print(f"Config used: {config_path}")
    print(f"Strategy: {strategy_type}")
    print(f"Results saved to: {result_dir}")


if __name__ == "__main__":
    main()



