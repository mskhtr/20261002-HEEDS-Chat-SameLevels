# 試験ごとのデザイン結果を、実行前に決めた共通水準の行へまとめます。

from __future__ import annotations

from heeds.shared_levels import build_shared_levels


def variable_label(name: str) -> str:
    return name


def _round_key(value) -> str:
    if value is None:
        return ""
    try:
        return f"{float(value):.8g}"
    except (TypeError, ValueError):
        return str(value)


def _input_key(inputs: dict, variable_names: list[str]) -> tuple[str, ...]:
    return tuple(_round_key(inputs.get(name)) for name in variable_names)


def _output_columns(
    studies: list[dict],
    variable_names: list[str],
) -> tuple[list[str], dict[tuple[str, str], str]]:
    """Response の列名と、(試験 ID, Response 名) から列名への対応を返します。

    同じ Response 名が複数試験にあるときや、入力列と同名のときは、
    値を上書きしないよう ``試験ID.Response名`` にします。
    """
    pairs: list[tuple[str, str]] = []
    seen_pairs: set[tuple[str, str]] = set()
    for study in studies:
        study_id = str(study.get("id") or "")
        for design in study.get("designs") or []:
            responses = design.get("responses") or {}
            if not isinstance(responses, dict):
                continue
            for name in responses:
                text = str(name).strip()
                pair = (study_id, text)
                if not text or pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                pairs.append(pair)

    counts: dict[str, int] = {}
    for _study_id, response_name in pairs:
        counts[response_name] = counts.get(response_name, 0) + 1

    reserved = {"水準", *variable_names}
    columns: list[str] = []
    mapping: dict[tuple[str, str], str] = {}
    used = set(reserved)
    for study_id, response_name in pairs:
        if counts[response_name] == 1 and response_name not in reserved:
            candidate = response_name
        else:
            candidate = f"{study_id}.{response_name}"
        base = candidate
        suffix = 2
        while candidate in used:
            candidate = f"{base}.{suffix}"
            suffix += 1
        used.add(candidate)
        columns.append(candidate)
        mapping[(study_id, response_name)] = candidate
    return columns, mapping


def build_levels_table(
    studies: list[dict],
    variables: list[dict],
    shared_levels: list[dict] | None = None,
) -> dict:
    """
    実行前に決めた水準ごとに、各試験の出力を1行へ横断結合します。
    行番号は共通水準表の順です。予定に無い入力は行を増やしません。
    出力列の見出しは通常 HEEDS の Response 名です。同名の Response が
    複数試験にある場合などは ``試験ID.Response名`` にして区別します。
    """
    variable_names = [str(spec["name"]) for spec in variables]
    if shared_levels is None:
        shared_levels, _errors = build_shared_levels(variables)
    input_headers = [variable_label(name) for name in variable_names]
    output_names, output_mapping = _output_columns(studies, variable_names)
    columns = ["水準"] + input_headers + output_names

    planned_keys = {
        _input_key(level, variable_names) for level in shared_levels
    }
    buckets: dict[tuple[str, ...], dict] = {}
    unmatched: list[dict] = []
    for study in studies:
        study_id = str(study.get("id") or "")
        for design in study.get("designs") or []:
            if not isinstance(design, dict):
                continue
            inputs = design.get("inputs") or {}
            if not isinstance(inputs, dict):
                inputs = {}
            key = _input_key(inputs, variable_names)
            if key not in planned_keys:
                unmatched.append(
                    {
                        "study_id": study_id,
                        "design_id": design.get("design_id"),
                        "inputs": {name: inputs.get(name) for name in variable_names},
                    }
                )
                continue
            if key not in buckets:
                buckets[key] = {
                    "outputs": {},
                    "design_ids": {},
                }
            bucket = buckets[key]
            bucket["design_ids"][study_id] = design.get("design_id")
            responses = design.get("responses") or {}
            if isinstance(responses, dict):
                for name, value in responses.items():
                    response_name = str(name).strip()
                    output_name = output_mapping.get((study_id, response_name))
                    if output_name:
                        bucket["outputs"][output_name] = value

    levels = []
    rows = []
    for index, planned in enumerate(shared_levels, start=1):
        level_label = f"水準{index}"
        key = _input_key(planned, variable_names)
        bucket = buckets.get(key) or {"outputs": {}, "design_ids": {}}
        row = {"水準": level_label}
        inputs = {name: planned.get(name) for name in variable_names}
        for name, header in zip(variable_names, input_headers, strict=True):
            row[header] = inputs[name]
        for name in output_names:
            row[name] = bucket["outputs"].get(name)
        rows.append(row)
        levels.append(
            {
                "level": index,
                "label": level_label,
                "inputs": inputs,
                "outputs": {name: bucket["outputs"].get(name) for name in output_names},
                "design_ids": bucket["design_ids"],
            }
        )

    return {
        "columns": columns,
        "rows": rows,
        "levels": levels,
        "unmatched": unmatched,
    }


def rows_to_markdown(columns: list[str], rows: list[dict], max_rows: int = 30) -> str:
    if not columns:
        return ""
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    body = rows[:max_rows]
    for row in body:
        cells = [_format_cell(row.get(col)) for col in columns]
        lines.append("| " + " | ".join(cells) + " |")
    extra = len(rows) - len(body)
    if extra > 0:
        lines.append(f"ほか {extra} 水準は CSV を見てください。")
    return "\n".join(lines)


def _format_cell(value) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)
