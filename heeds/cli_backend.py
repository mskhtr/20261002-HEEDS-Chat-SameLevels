# 公式 HEEDS Python API を HEEDSMDO.exe -b 経由で実行します。
# import HEEDS はホスト Python では使えません。生成スクリプト内だけで使います。

from __future__ import annotations

import csv
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from heeds.catalog import (
    allowed_study_ids,
    env_override_key,
    get_study,
    heeds_study_name,
)
from heeds.results_table import build_levels_table
from heeds.shared_levels import build_shared_levels

_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_RUNS_DIR = Path(__file__).resolve().parent.parent / "runs"
_TEMPLATE_PATH = Path(__file__).resolve().parent / "scripts" / "run_studies_template.py"


def run_cli_studies(study_ids: list[str], variables: list[dict]) -> dict:
    """カタログの試験を公式 API スクリプト経由で実行し、結果辞書を返します。"""
    errors = _validate(study_ids, variables)
    config_errors = _validate_config()
    errors.extend(config_errors)
    if errors:
        return {"ok": False, "backend": "cli", "errors": errors}

    unique_ids = list(dict.fromkeys(study_ids))
    studies_payload = []
    for study_id in unique_ids:
        heeds_name = _heeds_study_name(study_id)
        if not heeds_name:
            return {
                "ok": False,
                "backend": "cli",
                "errors": [
                    f"スタディ {study_id} の HEEDS 名が空です。"
                    f" catalog.yaml の heeds_name を書くか、.env に"
                    f" {env_override_key(study_id)}=画面のStudy名 を書いてください。"
                ],
            }
        studies_payload.append(
            {
                "id": study_id,
                "heeds_name": heeds_name,
            }
        )

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_dir = _RUNS_DIR / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)

    exe = Path(os.environ["HEEDS_EXE"].strip())
    project_path = Path(os.environ["HEEDS_PROJECT_PATH"].strip())
    timeout_sec = int(os.getenv("HEEDS_TIMEOUT_SEC") or "3600")
    shared_levels, level_errors = build_shared_levels(variables)
    if level_errors:
        return {"ok": False, "backend": "cli", "errors": level_errors}

    try:
        project_copy = _copy_project(project_path, timestamp)
    except OSError as error:
        return {
            "ok": False,
            "backend": "cli",
            "errors": [f"HEEDS プロジェクトをコピーできませんでした: {error}"],
            "run_dir": str(run_dir),
        }

    script_path = run_dir / "run_studies_heeds.py"
    _write_script(
        script_path,
        project_path=project_copy,
        out_dir=run_dir,
        studies=studies_payload,
        variables=variables,
        levels=shared_levels,
    )

    command = [
        str(exe),
        "-b",
        _as_heeds_path(project_copy),
        _as_heeds_path(script_path),
    ]
    (run_dir / "command.txt").write_text(
        "\n".join(command)
        + f"\n# original project (not modified): {_as_heeds_path(project_path)}\n"
        + f"# project copy: {_as_heeds_path(project_copy)}\n",
        encoding="utf-8",
    )

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
    except FileNotFoundError:
        return {
            "ok": False,
            "backend": "cli",
            "errors": [
                f"HEEDS_EXE が見つかりません: {exe}。"
                " HEEDS のインストールパスを確認してください。"
            ],
        }
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "backend": "cli",
            "errors": [
                f"HEEDS 実行がタイムアウトしました（{timeout_sec} 秒）。"
                " HEEDS_TIMEOUT_SEC を延ばすか、スタディ設定を確認してください。"
            ],
            "run_dir": str(run_dir),
        }

    stdout_path = run_dir / "heeds_stdout.txt"
    stderr_path = run_dir / "heeds_stderr.txt"
    stdout_path.write_text(completed.stdout or "", encoding="utf-8")
    stderr_path.write_text(completed.stderr or "", encoding="utf-8")

    summary = _load_summary(run_dir)
    if summary is None:
        return {
            "ok": False,
            "backend": "cli",
            "errors": [
                "HEEDS スクリプトが heeds_summary.json を書きませんでした。"
                f" 終了コード={completed.returncode}。"
                " heeds_stdout.txt / heeds_stderr.txt を確認してください。"
            ],
            "run_dir": str(run_dir),
            "returncode": completed.returncode,
        }

    studies_out = []
    csv_paths: list[str] = []
    file_paths: list[str] = []
    for item in summary.get("studies") or []:
        study_id = str(item.get("id") or "")
        study = get_study(study_id)
        report_path = item.get("report_path")
        report_local = _collect_report(run_dir, study_id, report_path)
        designs = item.get("designs") or []
        if not isinstance(designs, list):
            designs = []
        responses = item.get("responses") or {}
        if not isinstance(responses, dict):
            responses = {}
        inputs_at_best = item.get("inputs_at_best") or {}
        if not isinstance(inputs_at_best, dict):
            inputs_at_best = {}
        study_csv = run_dir / f"{study_id}_designs.csv"
        _write_designs_csv(study_csv, item, variables)
        csv_paths.append(str(study_csv))
        if report_local is not None:
            file_paths.append(str(report_local))
        studies_out.append(
            {
                "id": study_id,
                "name_ja": study.get("name_ja") if study else study_id,
                "heeds_study_name": item.get("heeds_study_name"),
                "status": item.get("status"),
                "best_design_id": item.get("best_design_id"),
                "designs": designs,
                "inputs_at_best": inputs_at_best,
                "responses": responses,
                "report_path": str(report_local) if report_local else report_path,
                "csv_path": str(study_csv),
            }
        )

    levels_table = build_levels_table(studies_out, variables, shared_levels)
    levels_csv = run_dir / "levels_summary.csv"
    _write_levels_csv(levels_csv, levels_table)
    csv_paths.insert(0, str(levels_csv))

    hard_errors = list(summary.get("errors") or [])
    if completed.returncode != 0:
        hard_errors.append(f"HEEDSMDO 終了コードが非ゼロです: {completed.returncode}")

    ok = bool(summary.get("ok")) and completed.returncode == 0 and not hard_errors
    result = {
        "ok": ok,
        "backend": "cli",
        "variables": variables,
        "studies": studies_out,
        "levels_table": {
            "columns": levels_table["columns"],
            "rows": levels_table["rows"],
            "levels": levels_table["levels"],
            "unmatched": levels_table.get("unmatched") or [],
        },
        "csv_paths": csv_paths,
        "file_paths": file_paths,
        "run_dir": str(run_dir),
        "project_path": str(project_path),
        "project_copy": str(project_copy),
        "returncode": completed.returncode,
    }
    unmatched = levels_table.get("unmatched") or []
    if unmatched:
        result["warnings"] = [
            (
                f"共通水準に無い入力が {len(unmatched)} 件返りました。"
                "水準番号はずらしていません。"
            )
        ]
    if hard_errors:
        result["errors"] = hard_errors
    if ok:
        result["note"] = (
            "HEEDS 公式 Python API（HEEDSMDO.exe -b）で、"
            "元のプロジェクトのコピーに共通水準を渡して実行しました。"
            " levels_table の行番号は、その共通水準の順です。"
        )
    return result


def _validate(study_ids: list[str], variables: list[dict]) -> list[str]:
    errors: list[str] = []
    allowed = allowed_study_ids()
    if not study_ids:
        errors.append("スタディ ID が空です。")
    for study_id in study_ids:
        if study_id not in allowed:
            errors.append(f"未知のスタディ ID です: {study_id}")
    if not variables:
        errors.append("変数が1つもありません。名前・下限・上限・刻みを指定してください。")
    seen_names: set[str] = set()
    for spec in variables:
        name = str(spec.get("name") or "").strip()
        if not name:
            errors.append("変数名が空です。")
            continue
        if not _NAME_PATTERN.match(name):
            errors.append(f"変数名は英数字と _ のみ使えます: {name}")
        if name in seen_names:
            errors.append(f"変数名が重複しています: {name}")
        seen_names.add(name)
        try:
            lower = float(spec["lower"])
            upper = float(spec["upper"])
            step = float(spec["step"])
        except (KeyError, TypeError, ValueError):
            errors.append(f"{name} の下限・上限・刻みは数値にしてください。")
            continue
        if upper < lower:
            errors.append(f"{name} の上限が下限より小さいです。")
        if step <= 0:
            errors.append(f"{name} の刻みは 0 より大きくしてください。")
        baseline = spec.get("baseline")
        if baseline not in (None, ""):
            try:
                baseline = float(baseline)
            except (TypeError, ValueError):
                errors.append(f"{name} の初期値は数値にしてください。")
                continue
            if baseline < lower or baseline > upper:
                errors.append(f"{name} の初期値は下限と上限の間にしてください。")
            spec["baseline"] = baseline
        spec["name"] = name
        spec["lower"] = lower
        spec["upper"] = upper
        spec["step"] = step
    if not errors:
        _levels, level_errors = build_shared_levels(variables)
        errors.extend(level_errors)
    return errors


def _validate_config() -> list[str]:
    errors: list[str] = []
    exe = (os.getenv("HEEDS_EXE") or "").strip()
    project = (os.getenv("HEEDS_PROJECT_PATH") or "").strip()
    if not exe:
        errors.append(
            "HEEDS_EXE が未設定です。.env に HEEDSMDO.exe のフルパスを書いてください。"
        )
    elif not Path(exe).is_file():
        errors.append(f"HEEDS_EXE のファイルがありません: {exe}")
    if not project:
        errors.append(
            "HEEDS_PROJECT_PATH が未設定です。.env に .heeds プロジェクトのパスを書いてください。"
        )
    elif not Path(project).is_file():
        errors.append(f"HEEDS_PROJECT_PATH のファイルがありません: {project}")
    try:
        timeout = int(os.getenv("HEEDS_TIMEOUT_SEC") or "3600")
        if timeout <= 0:
            errors.append("HEEDS_TIMEOUT_SEC は正の整数にしてください。")
    except ValueError:
        errors.append("HEEDS_TIMEOUT_SEC は整数にしてください。")
    return errors


def _heeds_study_name(study_id: str) -> str:
    """画面上の Study 名。catalog.yaml の heeds_name が既定で、.env があれば上書きです。"""
    return heeds_study_name(study_id)


def _as_heeds_path(path: Path) -> str:
    return path.resolve().as_posix()


def _copy_project(source: Path, timestamp: str) -> Path:
    """元の .heeds は残し、同じフォルダに実行用のコピーを作ります。"""
    dest = source.with_name(f"{source.stem}_chat_{timestamp}{source.suffix}")
    if dest.exists():
        dest = source.with_name(f"{source.stem}_chat_{timestamp}_2{source.suffix}")
    shutil.copy2(source, dest)
    return dest


def _write_script(
    script_path: Path,
    *,
    project_path: Path,
    out_dir: Path,
    studies: list[dict],
    variables: list[dict],
    levels: list[dict],
) -> None:
    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    # Strip the host-side docstring header so HEEDS sees a clean script.
    if template.startswith("#"):
        lines = template.splitlines(keepends=True)
        while lines and lines[0].startswith("#"):
            lines.pop(0)
        if lines and lines[0].strip() == "":
            lines.pop(0)
        template = "".join(lines)

    filled = (
        template.replace("__PLACEHOLDER_DOC__", "runtime script")
        .replace("__PLACEHOLDER_PROJECT_PATH__", repr(_as_heeds_path(project_path)))
        .replace("__PLACEHOLDER_OUT_DIR__", repr(_as_heeds_path(out_dir)))
        .replace("__PLACEHOLDER_STUDIES__", json.dumps(studies, ensure_ascii=False))
        .replace("__PLACEHOLDER_VARIABLES__", json.dumps(variables, ensure_ascii=False))
        .replace("__PLACEHOLDER_LEVELS__", json.dumps(levels, ensure_ascii=False))
    )
    script_path.write_text(filled, encoding="utf-8")


def _load_summary(run_dir: Path) -> dict | None:
    summary_path = run_dir / "heeds_summary.json"
    if not summary_path.is_file():
        return None
    try:
        data = json.loads(summary_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return data


def _collect_report(run_dir: Path, study_id: str, report_path) -> Path | None:
    expected = run_dir / f"{study_id}_Report.txt"
    if expected.is_file():
        return expected
    if not report_path:
        return None
    source = Path(str(report_path))
    if source.is_file():
        if source.resolve().parent == run_dir.resolve():
            return source
        dest = run_dir / source.name
        shutil.copy2(source, dest)
        return dest
    return None


def _write_designs_csv(path: Path, item: dict, variables: list[dict]) -> None:
    response_names: list[str] = []
    for design in item.get("designs") or []:
        responses = design.get("responses") or {}
        if isinstance(responses, dict):
            for name in responses:
                if name not in response_names:
                    response_names.append(str(name))
    input_names = [str(spec["name"]) for spec in variables]
    fieldnames = ["design_id", *input_names]
    used = set(fieldnames)
    response_columns: dict[str, str] = {}
    for response_name in response_names:
        candidate = response_name
        if candidate in used:
            candidate = f"response.{response_name}"
        base = candidate
        suffix = 2
        while candidate in used:
            candidate = f"{base}.{suffix}"
            suffix += 1
        used.add(candidate)
        fieldnames.append(candidate)
        response_columns[response_name] = candidate

    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for design in item.get("designs") or []:
            if not isinstance(design, dict):
                continue
            row = {"design_id": design.get("design_id")}
            inputs = design.get("inputs") or {}
            if isinstance(inputs, dict):
                for spec in variables:
                    name = str(spec["name"])
                    row[name] = inputs.get(name)
            responses = design.get("responses") or {}
            if isinstance(responses, dict):
                for name in response_names:
                    row[response_columns[name]] = responses.get(name)
            writer.writerow(row)


def _write_levels_csv(path: Path, levels_table: dict) -> None:
    columns = list(levels_table.get("columns") or [])
    rows = list(levels_table.get("rows") or [])
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col) for col in columns})
