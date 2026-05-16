# TradeTest

A visual backtesting workspace with guided config, YAML upload, cloud history, and downloadable Excel reports.

## Run

```bash
streamlit run web_app.py
```

The classic desktop picker is still available:

```bash
python backtest.py
```

## YAML Format

TradeTest V2 uses a standard rule-based YAML format for manual strategies and uploaded YAML.
The V2 rule engine currently supports single-symbol daily stock/ETF strategies:
`moving_average_cross` and `rsi_reversal`.

V2 Moving Average Cross:

```yaml
strategy:
  name: "Moving Average Cross"
  type: "moving_average_cross"

data:
  market: "western"
  symbols:
    - AAPL
  timeframe: "1d"
  start: "2020-01-01"
  end: null

indicators:
  short_ma:
    type: "sma"
    field: "close"
    window: 20
  long_ma:
    type: "sma"
    field: "close"
    window: 60

entry:
  all:
    - left: "short_ma"
      operator: "cross_above"
      right: "long_ma"

exit:
  any:
    - left: "short_ma"
      operator: "cross_below"
      right: "long_ma"

position:
  mode: "full_position"
  initial_cash: 10000

execution:
  price: "next_open"

cost:
  commission_pct: 0.001
  slippage_pct: 0.001
```

Single symbol MA crossover:

```yaml
data:
  market: "western"
  symbol: "VFV.TO"
  start: "2020-01-01"
  end: null

account:
  initial_cash: 10000
  currency: "MARKET_NATIVE"

costs:
  commission: 1.0
  slippage: 0.001

strategy:
  type: "ma_crossover"
  execution_timing: "next_open"
  fast_ma: 20
  slow_ma: 60

report:
  output_dir: "results"
```

Multi-symbol periodic rebalance:

```yaml
data:
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
```

China A-share example:

```yaml
data:
  market: "china"
  symbols:
    "600519": "Kweichow Moutai"
    "000001": "Ping An Bank"
    "510300": "CSI 300 ETF"
  start: "2021-05-10"
  end: null

account:
  initial_cash: 100000
  currency: "CNY"
```

`data.market` must be either `western` or `china`. Do not mix China A-shares with western tickers in the same backtest. China tickers like `600519` and `000001` are converted automatically to Yahoo Finance symbols such as `600519.SS` and `000001.SZ`.

## Web Features

- Guided config form or YAML upload
- `next_open` execution
- `daily`, `weekly`, and `monthly` rebalance frequency
- Interactive Plotly equity curve
- Summary and trades tables
- Consolidated multi-sheet Excel download
- Optional Supabase cloud history across terminals

## Cloud History

Set these environment variables before running Streamlit:

```bash
set SUPABASE_URL=https://your-project.supabase.co
set SUPABASE_KEY=your-supabase-key
set SUPABASE_BUCKET=tradetest-reports
set TRADETEST_TERMINAL_ID=home_pc
streamlit run web_app.py
```

Create the database table using `supabase_schema.sql`.
Supabase Storage should have a bucket named `tradetest-reports`.
