# catalog.yaml の Study 名が、HEEDS プロジェクト内の実名と一致するかを確認します。
# .env に HEEDS_STUDY_* があるときは、そちらを画面名として使います。
# 引数に CSV を付けると、その変数名も各 Study の AgentVariable と照合します。
# 解析は実行しません。チャットを使う前に一度実行してください。
# 手順は docs/07_設定チェック.md です。
#
# 使い方（プロジェクト直下・PowerShell）:
#   .\.venv\Scripts\python.exe check_heeds_project.py
#   .\.venv\Scripts\python.exe check_heeds_project.py sample.csv
# または check_heeds.bat をダブルクリック

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from heeds.project_check import format_check_report, run_project_check

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    parser = argparse.ArgumentParser(
        description="プログラム設定と HEEDS の名前を照合し、合っている箇所と直す箇所を出します。"
    )
    parser.add_argument(
        "csv",
        nargs="?",
        help="照合する変数 CSV。省略すると Study 名だけ照合し、変数と出力は参考表示です。",
    )
    args = parser.parse_args()
    csv_path = Path(args.csv) if args.csv else None
    result = run_project_check(csv_path)
    print(format_check_report(result))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
