# 振る変数の CSV（sample.csv と同じ列）を読みます。
# 行の数は固定しません。width2 のように足した行もそのまま使います。

from __future__ import annotations

import csv
from pathlib import Path

_HEADER_TO_FIELD = {
    "変数名": "name",
    "name": "name",
    "下限値": "lower",
    "下限": "lower",
    "lower": "lower",
    "初期値": "baseline",
    "初期": "baseline",
    "baseline": "baseline",
    "initial": "baseline",
    "上限値": "upper",
    "上限": "upper",
    "upper": "upper",
    "刻み": "step",
    "step": "step",
}

_REQUIRED = ("name", "lower", "baseline", "upper", "step")


def sample_csv_path() -> Path:
    """チャットから配布する記入例です。"""
    return Path(__file__).resolve().parent.parent / "sample.csv"


def parse_variable_csv(path: Path) -> tuple[list[dict], list[str]]:
    """CSV を変数のリストにします。戻り値は (変数, エラー) です。"""
    text = _read_text(path)
    if text is None:
        return [], [f"CSV を読めません: {path}"]

    rows = list(csv.reader(text.splitlines()))
    if not rows:
        return [], ["CSV が空です。"]

    header = [_normalize_header(cell) for cell in rows[0]]
    fields = [_HEADER_TO_FIELD.get(cell, "") for cell in header]
    missing = [name for name in _REQUIRED if name not in fields]
    if missing:
        labels = {
            "name": "変数名",
            "lower": "下限値",
            "baseline": "初期値",
            "upper": "上限値",
            "step": "刻み",
        }
        return [], [
            "CSV の1行目に次の列が必要です: "
            + "、".join(labels[name] for name in missing)
        ]

    variables: list[dict] = []
    errors: list[str] = []
    seen: set[str] = set()
    for line_no, raw in enumerate(rows[1:], start=2):
        if not any(cell.strip() for cell in raw):
            continue
        values = {
            fields[index]: raw[index].strip() if index < len(raw) else ""
            for index in range(len(fields))
            if fields[index]
        }
        name = values.get("name", "")
        if not name:
            errors.append(f"{line_no} 行目: 変数名が空です。")
            continue
        if name in seen:
            errors.append(f"{line_no} 行目: 変数名が重複しています: {name}")
            continue
        seen.add(name)
        numbers: dict[str, float] = {}
        bad_number = False
        for key, label in (
            ("lower", "下限値"),
            ("baseline", "初期値"),
            ("upper", "上限値"),
            ("step", "刻み"),
        ):
            try:
                numbers[key] = float(values.get(key, ""))
            except ValueError:
                errors.append(f"{line_no} 行目: {name} の{label}は数値にしてください。")
                bad_number = True
        if bad_number:
            continue
        lower = numbers["lower"]
        upper = numbers["upper"]
        baseline = numbers["baseline"]
        step = numbers["step"]
        if upper < lower:
            errors.append(f"{line_no} 行目: {name} の上限値が下限値より小さいです。")
        if baseline < lower or baseline > upper:
            errors.append(f"{line_no} 行目: {name} の初期値は下限値と上限値の間にしてください。")
        if step <= 0:
            errors.append(f"{line_no} 行目: {name} の刻みは 0 より大きくしてください。")
        variables.append(
            {
                "name": name,
                "lower": lower,
                "baseline": baseline,
                "upper": upper,
                "step": step,
            }
        )
    if not variables and not errors:
        errors.append("振る変数の行がありません。")
    if errors:
        return [], errors
    return variables, []


def format_variables(variables: list[dict]) -> str:
    """確認文に載せる、CSV の変数一覧です。"""
    lines = ["アップロードされた変数 CSV（この行だけを探査します）:"]
    for item in variables:
        lines.append(
            f"- {item['name']}: 下限={item['lower']} 初期値={item['baseline']} "
            f"上限={item['upper']} 刻み={item['step']}"
        )
    return "\n".join(lines)


def _normalize_header(cell: str) -> str:
    return cell.strip().lstrip("\ufeff").lower()


def _read_text(path: Path) -> str | None:
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "cp932"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None
