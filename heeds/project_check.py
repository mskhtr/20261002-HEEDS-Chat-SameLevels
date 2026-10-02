# catalog.yaml（または .env で上書きした）Study 名が、
# HEEDS プロジェクト内の実名と一致するかを確認します。
# 引数の CSV があるときだけ、変数名も照合します。出力名は HEEDS の一覧を参考表示します。
# import HEEDS はホストでは使わず、HEEDSMDO.exe -b 内の一時スクリプトで検査します。

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from heeds.catalog import iter_study_bindings, load_catalog
from heeds.cli_backend import _as_heeds_path
from heeds.variable_csv import parse_variable_csv

_TEMPLATE_PATH = Path(__file__).resolve().parent / "scripts" / "check_project_template.py"
_RUNS_DIR = Path(__file__).resolve().parent.parent / "runs"
_CHECK_TIMEOUT_SEC = 180


def run_project_check(csv_path: Path | None = None) -> dict:
    """ホスト側の設定確認のあと、必要なら HEEDS を開いて名前を突き合わせます。

    csv_path を渡すと、その CSV の変数名も各 Study の AgentVariable と照合します。
    """
    host = _check_host_config()
    if csv_path is not None:
        _apply_csv(host, Path(csv_path))
    result = {
        "ok": False,
        "host": host,
        "program": host.get("program") or {},
        "heeds": None,
        "errors": list(host.get("errors") or []),
        "run_dir": None,
        "csv_path": str(csv_path) if csv_path else None,
    }
    if host.get("errors"):
        return result

    heeds = _run_heeds_inspect(host)
    result["heeds"] = heeds
    result["run_dir"] = heeds.get("run_dir")
    result["errors"].extend(heeds.get("errors") or [])
    _matched, failed, _notes = _support_findings(result)
    result["ok"] = not failed
    return result


def compare_csv_with_heeds(variable_names: list[str]) -> str:
    """アップロードした変数名と、各 Study の AgentVariable を照合します。解析はしません。"""
    names = [str(name) for name in variable_names if str(name).strip()]
    host = _check_host_config()
    if host.get("errors"):
        return (
            "HEEDS の変数と照合できませんでした。\n"
            + "\n".join("- " + str(item) for item in host["errors"])
        )
    host["variable_names"] = names
    program = host.setdefault("program", {})
    program["variable_names"] = names
    heeds = _run_heeds_inspect(host)
    return _format_csv_variable_report(names, heeds, program)


def _apply_csv(host: dict, csv_path: Path) -> None:
    variables, errors = parse_variable_csv(csv_path)
    names = [str(item.get("name") or "") for item in variables if item.get("name")]
    program = host.setdefault("program", {})
    program["csv_path"] = str(csv_path)
    program["variable_names"] = names
    host["variable_names"] = names
    if errors:
        host.setdefault("errors", []).extend(errors)
        host["ok"] = False


def _finding_lines(items: list[str], empty: str) -> list[str]:
    if not items:
        return ["- " + empty] if empty else []
    return ["- " + item for item in items]


def _support_findings(result: dict) -> tuple[list[str], list[str], list[str]]:
    matched: list[str] = []
    failed: list[str] = []
    notes: list[str] = []
    host = result.get("host") or {}
    program = result.get("program") or host.get("program") or {}
    csv_path = program.get("csv_path") or result.get("csv_path")
    variable_names = [str(name) for name in (program.get("variable_names") or []) if str(name).strip()]

    for item in host.get("items") or []:
        label = str(item.get("label") or "")
        detail = str(item.get("detail") or "")
        text = "%s: %s" % (label, detail) if detail else label
        if item.get("ok"):
            matched.append(text)
        else:
            failed.append(text)

    summary = ((result.get("heeds") or {}).get("summary") or {})
    if host.get("errors") and not summary:
        for item in host.get("errors") or []:
            text = str(item)
            if text not in failed:
                failed.append(text)
        failed.append("ファイルまたは CSV が足りないため、HEEDS は開いていません。")
        return matched, failed, notes

    if summary.get("project_opened"):
        matched.append("HEEDS プロジェクトを開けた: %s" % (summary.get("project") or program.get("project_path") or ""))
    else:
        errors = (result.get("heeds") or {}).get("errors") or ["HEEDS の検査結果がありません。"]
        failed.append("HEEDS プロジェクトを開けませんでした: " + str(errors[0]))
        return matched, failed, notes

    project_studies = [str(name) for name in (summary.get("project_studies") or []) if str(name).strip()]
    used_names = set(_program_study_names(program))
    unused = [name for name in project_studies if name not in used_names]
    if unused:
        notes.append("プログラムが使わない Study: " + _join_names(unused))

    studies = summary.get("studies") or []
    if not studies:
        failed.append(
            "比較する Study がありません。catalog.yaml の heeds_name か、.env の上書きを確認してください。"
        )

    for item in studies:
        study_id = str(item.get("id") or "")
        spec = _program_study(program, study_id)
        name_ja = spec.get("name_ja") or study_id
        source_label = (
            spec.get("env_key") or ".env"
            if spec.get("source") == "env"
            else "catalog.yaml の heeds_name"
        )
        program_name = item.get("heeds_name") or spec.get("heeds_name") or "（未設定）"
        title = "%s（%s）" % (name_ja, study_id)
        if item.get("found"):
            matched.append(
                "%s の Study 名が HEEDS にある: %s = %s"
                % (title, source_label, program_name)
            )
        else:
            failed.append(
                "%s の Study 名が HEEDS にない: %s = %s。HEEDS にある名前: %s"
                % (title, source_label, program_name, _join_names(project_studies))
            )
            continue

        actual_vars = [str(name) for name in (item.get("actual_variables") or []) if str(name).strip()]
        actual_resps = [str(name) for name in (item.get("actual_responses") or []) if str(name).strip()]
        if csv_path:
            missing = [name for name in variable_names if name not in actual_vars]
            extra = [name for name in actual_vars if name not in variable_names]
            if not actual_vars and variable_names:
                failed.append("%s の変数一覧を HEEDS から取れませんでした。" % title)
            elif missing or extra:
                parts = []
                if missing:
                    parts.append("CSV にだけある: " + _join_names(missing))
                if extra:
                    parts.append("HEEDS にだけある: " + _join_names(extra))
                failed.append(
                    "%s の変数が CSV と違う（CSV %s 個、HEEDS %s 個）。%s"
                    % (title, len(variable_names), len(actual_vars), " ".join(parts))
                )
            else:
                matched.append(
                    "%s の変数が CSV と一致（%s 個: %s）"
                    % (title, len(actual_vars), _join_names(actual_vars))
                )
        elif actual_vars:
            notes.append("%s の AgentVariable: %s" % (title, _join_names(actual_vars)))
        else:
            notes.append("%s の AgentVariable 一覧は取れませんでした。" % title)

        if actual_resps:
            notes.append(
                "%s の Response（実行後の表見出し）: %s" % (title, _join_names(actual_resps))
            )
        else:
            notes.append("%s に Response が無いと、その試験の出力列は出ません。" % title)

    if csv_path:
        notes.insert(0, "照合した CSV: %s（%s 個: %s）" % (csv_path, len(variable_names), _join_names(variable_names)))
    else:
        notes.insert(
            0,
            "変数 CSV は渡していません。変数の一致は見ていません。渡すときは check_heeds_project.py の引数に CSV を付けます。",
        )
    return matched, failed, notes


def format_check_report(result: dict) -> str:
    """コンソール向けのサポート用レポートです。合否と、直し方を出します。"""
    matched, failed, notes = _support_findings(result)
    lines = [
        "=== 設定チェック（サポート用） ===",
        "解析は実行しません。プログラムの設定と、HEEDS を開いて読んだ名前を比べます。",
        "",
    ]
    if result.get("ok"):
        lines.append("結果: 合っています。プログラムが使う名前は HEEDS にあります。")
    else:
        lines.append("結果: ずれています。下の「直すこと」を見てください。")
    lines.append("")
    lines.append("合っているところ")
    lines.extend(_finding_lines(matched, "（まだ確認できた一致はありません）"))
    lines.append("")
    lines.append("直すこと")
    lines.extend(_finding_lines(failed, "（ありません）"))
    if notes:
        lines.append("")
        lines.append("参考（合否には使いません）")
        lines.extend(_finding_lines(notes, ""))
    if result.get("ok"):
        lines.append("")
        lines.append("GUI で各 Study を一度手動実行し、Response に値が入ることも確認してください。")
    footer = _footer(result)
    if footer:
        lines.append("")
        lines.append(footer)
    return "\n".join(lines)


def _check_host_config() -> dict:
    items = []
    catalog = load_catalog()
    studies = catalog.get("studies") or []

    exe = (os.getenv("HEEDS_EXE") or "").strip()
    project = (os.getenv("HEEDS_PROJECT_PATH") or "").strip()
    items.append(_file_item("HEEDS_EXE", exe))
    items.append(_file_item("HEEDS_PROJECT_PATH", project))

    variables = []
    var_names: list[str] = []
    program_studies = iter_study_bindings()
    for binding in program_studies:
        heeds_name = binding["heeds_name"]
        source = ".env の上書き" if binding["source"] == "env" else "catalog.yaml"
        items.append(
            {
                "ok": bool(heeds_name),
                "label": "%s（%s）" % (binding["name_ja"], binding["id"]),
                "detail": (
                    "%s（%s）" % (heeds_name, source)
                    if heeds_name
                    else "未設定。catalog.yaml の heeds_name か .env の %s" % binding["env_key"]
                ),
            }
        )

    if not studies:
        items.append(
            {
                "ok": False,
                "label": "catalog.yaml の studies",
                "detail": "試験がありません",
            }
        )

    errors = []
    for item in items:
        if not item.get("ok"):
            errors.append("%s: %s" % (item.get("label"), item.get("detail")))

    return {
        "ok": not errors,
        "items": items,
        "errors": errors,
        "exe": exe,
        "project": project,
        "expected_ids": [item["id"] for item in program_studies],
        "variable_names": var_names,
        "program": {
            "variable_names": var_names,
            "variables": variables,
            "studies": program_studies,
            "project_path": project,
        },
    }


def _format_csv_variable_report(csv_names: list[str], heeds: dict, program: dict) -> str:
    summary = (heeds or {}).get("summary") or {}
    if not summary:
        errors = (heeds or {}).get("errors") or ["HEEDS の検査結果がありません。"]
        return "HEEDS の変数と照合できませんでした。\n" + "\n".join(
            "- " + str(item) for item in errors
        )

    lines = [
        "アップロードした CSV と HEEDS の変数を照合しました（解析はしていません）。",
        "CSV は %s 個: %s" % (len(csv_names), _join_names(csv_names)),
        "",
    ]
    studies = summary.get("studies") or []
    if not summary.get("project_opened"):
        lines.append("HEEDS プロジェクトを開けませんでした。")
        lines.extend("- " + str(item) for item in (summary.get("errors") or heeds.get("errors") or []))
        return "\n".join(lines)
    if not studies:
        lines.append(
            "比較できる Study がありません。catalog.yaml の heeds_name か、.env の上書きを確認してください。"
        )
        return "\n".join(lines)

    mismatch = False
    for item in studies:
        study_id = str(item.get("id") or "")
        spec = _program_study(program, study_id)
        title = "%s（%s）" % (spec.get("name_ja") or study_id, item.get("heeds_name") or "Study 名なし")
        if not item.get("found"):
            mismatch = True
            lines.append("- %s: Study が見つからないため、変数を比較できません。" % title)
            continue
        actual = [str(name) for name in (item.get("actual_variables") or []) if str(name).strip()]
        found_map = item.get("variables") or {}
        if not actual:
            missing = [name for name in csv_names if not found_map.get(name)]
            mismatch = True
            lines.append("- %s: HEEDS の変数一覧を取れませんでした。" % title)
            if missing:
                lines.append("  CSV にあって見つからなかった名前: " + _join_names(missing))
            continue
        missing = [name for name in csv_names if name not in actual]
        extra = [name for name in actual if name not in csv_names]
        if not missing and not extra and len(actual) == len(csv_names):
            lines.append("- %s: 一致（%s 個）" % (title, len(actual)))
            continue
        mismatch = True
        lines.append(
            "- %s: 不一致。CSV %s 個、HEEDS %s 個（%s）"
            % (title, len(csv_names), len(actual), _join_names(actual))
        )
        if missing:
            lines.append("  CSV にだけある: " + _join_names(missing))
        if extra:
            lines.append("  HEEDS にだけある: " + _join_names(extra))

    lines.append("")
    if mismatch:
        lines.append(
            "名前か個数が違います。CSV の変数名を HEEDS の AgentVariable に合わせるか、"
            "HEEDS 側の変数を CSV に合わせてから、CSV をアップロードし直してください。"
        )
    else:
        lines.append("各 Study の変数名と個数は、CSV と一致しています。")
    return "\n".join(lines)


def _file_item(label: str, path_text: str) -> dict:
    if not path_text:
        return {"ok": False, "label": label, "detail": "未設定です。.env にフルパスを書いてください。"}
    path = Path(path_text)
    if not path.is_file():
        return {"ok": False, "label": label, "detail": "ファイルがありません: %s" % path_text}
    return {"ok": True, "label": label, "detail": path_text}


def _run_heeds_inspect(host: dict) -> dict:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_dir = _RUNS_DIR / ("check_" + timestamp)
    run_dir.mkdir(parents=True, exist_ok=True)

    by_id = {item["id"]: item for item in (host.get("program") or {}).get("studies") or []}
    studies_payload = []
    for study_id in host.get("expected_ids") or []:
        spec = by_id.get(study_id) or {}
        studies_payload.append(
            {
                "id": study_id,
                "heeds_name": spec.get("heeds_name") or "",
            }
        )

    script_path = run_dir / "check_heeds_project_heeds.py"
    _write_script(
        script_path,
        project_path=Path(host["project"]),
        out_dir=run_dir,
        studies=studies_payload,
        variable_names=host.get("variable_names") or [],
    )

    exe = Path(host["exe"])
    command = [
        str(exe),
        "-b",
        _as_heeds_path(Path(host["project"])),
        _as_heeds_path(script_path),
    ]
    (run_dir / "command.txt").write_text("\n".join(command), encoding="utf-8")

    heeds: dict = {
        "run_dir": str(run_dir),
        "command": command,
        "summary": None,
        "errors": [],
        "returncode": None,
    }
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=_CHECK_TIMEOUT_SEC,
            check=False,
        )
    except FileNotFoundError:
        heeds["errors"].append("HEEDS_EXE が見つかりません: %s" % exe)
        return heeds
    except subprocess.TimeoutExpired:
        heeds["errors"].append(
            "HEEDS の名前検査がタイムアウトしました（%s 秒）。" % _CHECK_TIMEOUT_SEC
        )
        return heeds

    (run_dir / "heeds_stdout.txt").write_text(completed.stdout or "", encoding="utf-8")
    (run_dir / "heeds_stderr.txt").write_text(completed.stderr or "", encoding="utf-8")
    heeds["returncode"] = completed.returncode

    summary = _load_summary(run_dir)
    heeds["summary"] = summary
    if summary is None:
        heeds["errors"].append(
            "HEEDS が heeds_check.json を書きませんでした。"
            " 終了コード=%s。 heeds_stdout.txt / heeds_stderr.txt を見てください。"
            % completed.returncode
        )
        return heeds
    if not summary.get("ok"):
        heeds["errors"].extend(summary.get("errors") or [])
    return heeds


def _write_script(
    script_path: Path,
    *,
    project_path: Path,
    out_dir: Path,
    studies: list[dict],
    variable_names: list[str],
) -> None:
    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    if template.startswith("#"):
        lines = template.splitlines(keepends=True)
        while lines and lines[0].startswith("#"):
            lines.pop(0)
        if lines and lines[0].strip() == "":
            lines.pop(0)
        template = "".join(lines)

    filled = (
        template.replace("__PLACEHOLDER_DOC__", "project name check")
        .replace("__PLACEHOLDER_PROJECT_PATH__", repr(_as_heeds_path(project_path)))
        .replace("__PLACEHOLDER_OUT_DIR__", repr(_as_heeds_path(out_dir)))
        .replace("__PLACEHOLDER_STUDIES__", json.dumps(studies, ensure_ascii=False))
        .replace("__PLACEHOLDER_VARIABLE_NAMES__", json.dumps(variable_names, ensure_ascii=False))
    )
    script_path.write_text(filled, encoding="utf-8")


def _load_summary(run_dir: Path) -> dict | None:
    summary_path = run_dir / "heeds_check.json"
    if not summary_path.is_file():
        return None
    try:
        data = json.loads(summary_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return data


def _join_names(names) -> str:
    cleaned = [str(name) for name in names or [] if str(name).strip()]
    return ", ".join(cleaned) if cleaned else "（なし）"


def _program_study_names(program: dict) -> list[str]:
    return [
        str(item.get("heeds_name") or "")
        for item in program.get("studies") or []
        if item.get("heeds_name")
    ]


def _program_study(program: dict, study_id: str) -> dict:
    for item in program.get("studies") or []:
        if item.get("id") == study_id:
            return item
    return {}


def _footer(result: dict) -> str:
    run_dir = result.get("run_dir")
    if run_dir:
        return "詳細 JSON: %s" % str(Path(run_dir) / "heeds_check.json")
    return ""
