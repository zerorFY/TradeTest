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

alter table public.backtest_runs enable row level security;

drop policy if exists "tradetest read runs" on public.backtest_runs;
create policy "tradetest read runs"
  on public.backtest_runs
  for select
  using (true);

drop policy if exists "tradetest insert runs" on public.backtest_runs;
create policy "tradetest insert runs"
  on public.backtest_runs
  for insert
  with check (true);

insert into storage.buckets (id, name, public)
values ('tradetest-reports', 'tradetest-reports', true)
on conflict (id) do update set public = true;

drop policy if exists "tradetest read reports" on storage.objects;
create policy "tradetest read reports"
  on storage.objects
  for select
  using (bucket_id = 'tradetest-reports');

drop policy if exists "tradetest upload reports" on storage.objects;
create policy "tradetest upload reports"
  on storage.objects
  for insert
  with check (bucket_id = 'tradetest-reports');

drop policy if exists "tradetest update reports" on storage.objects;
create policy "tradetest update reports"
  on storage.objects
  for update
  using (bucket_id = 'tradetest-reports')
  with check (bucket_id = 'tradetest-reports');
