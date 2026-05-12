import os
from pathlib import Path
from typing import Any
from uuid import uuid4

import requests


class CloudStore:
    def __init__(self, secrets: dict[str, Any] | None = None) -> None:
        secrets = secrets or {}
        self.url = str(secrets.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL", "")).rstrip("/")
        self.key = str(secrets.get("SUPABASE_KEY") or os.environ.get("SUPABASE_KEY", ""))
        self.bucket = str(secrets.get("SUPABASE_BUCKET") or os.environ.get("SUPABASE_BUCKET", "tradetest-reports"))
        self.enabled = bool(self.url and self.key)

    @property
    def headers(self) -> dict[str, str]:
        return {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
        }

    def upload_bytes(self, content: bytes, object_path: str, content_type: str) -> str:
        if not self.enabled:
            return ""

        endpoint = f"{self.url}/storage/v1/object/{self.bucket}/{object_path}"
        headers = {
            **self.headers,
            "Content-Type": content_type,
            "x-upsert": "true",
        }
        response = requests.post(endpoint, headers=headers, data=content, timeout=60)
        response.raise_for_status()
        return f"{self.url}/storage/v1/object/public/{self.bucket}/{object_path}"

    def save_run(
        self,
        *,
        terminal_id: str,
        config_name: str,
        config_yaml: str,
        summary: dict[str, Any],
        report_bytes: bytes,
        chart_bytes: bytes | None,
    ) -> dict[str, Any] | None:
        if not self.enabled:
            return None

        run_id = str(uuid4())
        base_path = f"{terminal_id}/{run_id}"
        report_url = self.upload_bytes(
            report_bytes,
            f"{base_path}/backtest_report.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        chart_url = ""
        if chart_bytes:
            chart_url = self.upload_bytes(chart_bytes, f"{base_path}/equity_curve.png", "image/png")

        payload = {
            "id": run_id,
            "terminal_id": terminal_id,
            "config_name": config_name,
            "config_yaml": config_yaml,
            "strategy_type": summary.get("strategy_type", ""),
            "symbols": summary.get("symbols", ""),
            "execution_timing": summary.get("execution_timing", ""),
            "rebalance_frequency": summary.get("rebalance_frequency", ""),
            "start_date": summary.get("start", None),
            "end_date": summary.get("end", None),
            "initial_cash": summary.get("initial_cash", None),
            "final_equity": summary.get("final_equity", None),
            "total_return": summary.get("total_return", None),
            "max_drawdown": summary.get("max_drawdown", None),
            "trade_count": summary.get("trade_count", None),
            "report_xlsx_url": report_url,
            "chart_png_url": chart_url,
        }

        endpoint = f"{self.url}/rest/v1/backtest_runs"
        headers = {**self.headers, "Content-Type": "application/json", "Prefer": "return=representation"}
        response = requests.post(endpoint, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        rows = response.json()
        return rows[0] if rows else payload

    def list_runs(self, limit: int = 100) -> list[dict[str, Any]]:
        if not self.enabled:
            return []

        endpoint = f"{self.url}/rest/v1/backtest_runs"
        params = {
            "select": "*",
            "order": "created_at.desc",
            "limit": str(limit),
        }
        response = requests.get(endpoint, headers=self.headers, params=params, timeout=30)
        response.raise_for_status()
        return response.json()


def default_terminal_id() -> str:
    return os.environ.get("TRADETEST_TERMINAL_ID") or f"{os.environ.get('COMPUTERNAME', 'terminal')}".lower()
