create table if not exists public.backtest_runs (
  id uuid primary key,
  terminal_id text,
  config_name text,
  config_yaml text,
  strategy_type text,
  symbols text,
  execution_timing text,
  rebalance_frequency text,
  start_date date,
  end_date date,
  initial_cash numeric,
  final_equity numeric,
  total_return numeric,
  max_drawdown numeric,
  trade_count int,
  report_xlsx_url text,
  chart_png_url text,
  created_at timestamptz default now()
);

create index if not exists backtest_runs_created_at_idx
  on public.backtest_runs (created_at desc);

create index if not exists backtest_runs_terminal_id_idx
  on public.backtest_runs (terminal_id);

-- Create a Supabase Storage bucket named `tradetest-reports`.
-- For the simplest shared-history version, make it public.
-- If Row Level Security is enabled, add insert/select policies for your chosen key model.
