# HEEDS 実行の窓口です。app.py はこのモジュールだけを呼びます。

from __future__ import annotations

from heeds.cli_backend import run_cli_studies


def run_studies(study_ids: list[str], variables: list[dict]) -> dict:
    """公式 HEEDS Python API（HEEDSMDO.exe -b）でスタディを実行します。"""
    return run_cli_studies(study_ids, variables)
