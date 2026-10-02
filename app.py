# Chainlit で動く設計要件チャットです。
# 実行する試験は catalog.yaml から決めます。AI は実行後の要約だけを書きます。
#
# 起動方法（Python 3.12 の仮想環境）:
#   .\.venv\Scripts\python.exe run_app.py

import asyncio
import csv
import mimetypes
from pathlib import Path

import chainlit as cl
from dotenv import load_dotenv

from heeds.catalog import starter_examples, welcome_markdown
from heeds.client import run_studies
from heeds.plan import (
    confirmation_message,
    is_run_approval,
    match_requirements,
    requirements_by_ids,
    study_ids_for,
)
from heeds.project_check import compare_csv_with_heeds
from heeds.summary import summarize_result
from heeds.shared_levels import build_shared_levels
from heeds.variable_csv import parse_variable_csv, sample_csv_path
from heeds.welcome import publish_welcome

load_dotenv()
publish_welcome()


def _format_value(value) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def _levels_markdown(result: dict) -> str:
    """入力水準 × 全試験出力の横断表をチャット本文用にします。"""
    notes: list[str] = []
    errors = result.get("errors") or []
    if errors:
        notes.append("エラー: " + " / ".join(str(item) for item in errors))
    warnings = result.get("warnings") or []
    if warnings:
        notes.append("注意: " + " / ".join(str(item) for item in warnings))

    table = result.get("levels_table") or {}
    columns = table.get("columns") or []
    rows = table.get("rows") or []
    if columns and rows:
        lines = [
            "### 結果一覧（入力水準ごと）",
            "| " + " | ".join(str(col) for col in columns) + " |",
            "| " + " | ".join("---" for _ in columns) + " |",
        ]
        max_rows = 30
        for row in rows[:max_rows]:
            cells = [_format_value(row.get(col)) for col in columns]
            lines.append("| " + " | ".join(cells) + " |")
        extra = len(rows) - min(len(rows), max_rows)
        if extra > 0:
            lines.append(f"ほか {extra} 水準は `levels_summary.csv` を見てください。")
        if notes:
            lines.append("")
            lines.extend(notes)
        return "\n".join(lines)
    return "\n".join(notes)


def _file_element(path: Path) -> cl.File:
    """ファイルを添付します。mime が空だと Chainlit 2.11 の画面が落ちます。"""
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    if path.suffix.lower() == ".csv" and mime == "application/octet-stream":
        mime = "text/csv"
    if path.suffix.lower() == ".txt" and mime == "application/octet-stream":
        mime = "text/plain"
    return cl.File(name=path.name, path=str(path), mime=mime)


def _markdown_table(path: Path, max_rows: int = 8) -> str:
    """チャット本文用に、CSV の先頭だけ表にします。"""
    with path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.reader(file))
    if not rows:
        return ""
    header = rows[0]
    body = rows[1 : max_rows + 1]
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    for row in body:
        padded = row + [""] * (len(header) - len(row))
        lines.append("| " + " | ".join(padded[: len(header)]) + " |")
    extra = len(rows) - 1 - len(body)
    if extra > 0:
        lines.append(f"ほか {extra} 行はファイルを見てください。")
    return "\n".join(lines)


def _result_view(result: dict) -> tuple[str, list]:
    """実行結果の表と、添付するファイルです。"""
    blocks = []
    elements = []
    seen: set[str] = set()
    levels = _levels_markdown(result)
    if levels:
        blocks.append(levels)
    for raw in result.get("csv_paths") or []:
        path = Path(str(raw))
        if not path.is_file() or str(path) in seen:
            continue
        seen.add(str(path))
        elements.append(_file_element(path))
        if path.name != "levels_summary.csv":
            blocks.append(f"### {path.name}\n{_markdown_table(path)}")
    for raw in list(result.get("file_paths") or []) + list(result.get("report_paths") or []):
        path = Path(str(raw))
        if not path.is_file() or str(path) in seen:
            continue
        seen.add(str(path))
        elements.append(_file_element(path))
    return "\n\n".join(blocks), elements


def _level_error_text(level_errors: list[str]) -> str:
    return (
        "共通の水準を作れませんでした。\n\n"
        + "\n".join(level_errors)
        + "\n\n刻みを粗くするか、変数を減らして CSV を添付し直してください。"
    )


def _variables_from_message(message: cl.Message) -> tuple[list[dict] | None, list[str]]:
    """添付 CSV があれば変数にします。CSV が無いときは (None, []) です。"""
    paths: list[Path] = []
    for element in message.elements or []:
        raw = getattr(element, "path", None)
        name = str(getattr(element, "name", "") or "")
        if not raw:
            continue
        path = Path(str(raw))
        if path.suffix.lower() == ".csv" or name.lower().endswith(".csv"):
            paths.append(path)
    if not paths:
        return None, []
    if len(paths) > 1:
        return None, ["変数 CSV は1ファイルだけ添付してください。"]
    if not paths[0].is_file():
        return None, ["添付された CSV が見つかりません。もう一度添付してください。"]
    return parse_variable_csv(paths[0])


def _example_sentence() -> str:
    examples = "または".join(f"「{message}」" for _label, message in starter_examples())
    if not examples:
        return "catalog.yaml の設計要件を書いてください。"
    return "例: " + examples


async def _ask_for_missing_inputs(
    *,
    has_csv: bool,
    has_requirement: bool,
    compare_names: list[str] | None,
) -> None:
    """CSV と設計要件の両方が揃うまで、確認や実行に進まない案内です。"""
    lines: list[str] = []
    notice = None
    if compare_names:
        notice = cl.Message(content="アップロードした CSV と HEEDS の変数名を照合しています…")
        await notice.send()
        lines.append(await asyncio.to_thread(compare_csv_with_heeds, compare_names))
    if not has_csv:
        lines.append(
            "変数の CSV がまだありません。"
            "開始時に付いている sample.csv をダウンロードして記入し、このチャットに添付してください。"
        )
    if not has_requirement:
        lines.append("何を確認したいかを書いてください。" + _example_sentence())
    lines.append("CSV と、確認したい要件の両方が揃うまで、試験の確認や HEEDS の実行には進みません。")
    text = "\n\n".join(lines)
    if notice is not None:
        notice.content = text
        await notice.update()
    else:
        await cl.Message(content=text).send()


async def _send(text: str, elements: list | None = None) -> None:
    message = cl.Message(content=text)
    if elements:
        message.elements = elements
    await message.send()


@cl.set_starters
async def set_starters():
    """入力欄の上に出す例です。文言は catalog.yaml の label です。"""
    return [
        cl.Starter(label=label, message=message)
        for label, message in starter_examples()
    ]


@cl.on_chat_start
async def on_chat_start():
    """新しいチャットが始まったときに、空の状態と開始文を用意します。"""
    cl.user_session.set("variables", None)
    cl.user_session.set("requirement_ids", [])
    cl.user_session.set("awaiting_confirmation", False)
    cl.user_session.set("confirmed_study_ids", [])
    publish_welcome()
    sample = sample_csv_path()
    elements = [_file_element(sample)] if sample.is_file() else []
    await _send(welcome_markdown(), elements)


@cl.on_message
async def on_message(message: cl.Message):
    """CSV と要件が揃ったら確認し、同意のあとだけ HEEDS を実行します。"""
    uploaded, upload_errors = _variables_from_message(message)
    if upload_errors:
        await _send("変数 CSV を読めませんでした。\n\n" + "\n".join(upload_errors))
        return

    variables = cl.user_session.get("variables")
    if uploaded is not None:
        variables = uploaded
        cl.user_session.set("variables", variables)
        cl.user_session.set("awaiting_confirmation", False)
        cl.user_session.set("confirmed_study_ids", [])

    user_text = (message.content or "").strip()
    matched = match_requirements(user_text)
    if matched:
        cl.user_session.set("requirement_ids", [str(item.get("id")) for item in matched])
    requirement_ids = list(cl.user_session.get("requirement_ids") or [])

    if variables is None or not requirement_ids:
        await _ask_for_missing_inputs(
            has_csv=variables is not None,
            has_requirement=bool(requirement_ids),
            compare_names=(
                [str(item["name"]) for item in variables]
                if uploaded is not None and variables
                else None
            ),
        )
        return

    awaiting = bool(cl.user_session.get("awaiting_confirmation"))
    allow_run = uploaded is None and awaiting and is_run_approval(user_text)
    requirements = requirements_by_ids(requirement_ids)
    study_ids = study_ids_for(requirements)

    variable_report = ""
    if uploaded is not None:
        notice = cl.Message(content="アップロードした CSV と HEEDS の変数名を照合しています…")
        await notice.send()
        variable_report = await asyncio.to_thread(
            compare_csv_with_heeds,
            [str(item["name"]) for item in variables],
        )
    else:
        notice = cl.Message(content="HEEDS を実行しています…" if allow_run else "確認内容をまとめています…")
        await notice.send()

    _shared_levels, level_errors = build_shared_levels(variables)
    if allow_run and level_errors:
        cl.user_session.set("awaiting_confirmation", False)
        cl.user_session.set("confirmed_study_ids", [])
        notice.content = _level_error_text(level_errors)
        await notice.update()
        return

    if allow_run:
        confirmed_study_ids = list(cl.user_session.get("confirmed_study_ids") or [])
        cl.user_session.set("awaiting_confirmation", False)
        cl.user_session.set("confirmed_study_ids", [])
        if not confirmed_study_ids:
            notice.content = "実行する試験がカタログにありません。heeds/catalog.yaml を確認してください。"
            await notice.update()
            return
        try:
            result = await asyncio.to_thread(run_studies, confirmed_study_ids, variables)
        except Exception as error:
            notice.content = "HEEDS の実行でエラーが発生しました。\n\n詳細: " + str(error)
            await notice.update()
            return
        summary = await asyncio.to_thread(summarize_result, result)
        table, elements = _result_view(result)
        text = summary
        if table:
            text = text + "\n\n" + table
        notice.content = text
        if elements:
            notice.elements = elements
        await notice.update()
        return

    if level_errors:
        text = _level_error_text(level_errors)
        cl.user_session.set("awaiting_confirmation", False)
        cl.user_session.set("confirmed_study_ids", [])
    else:
        text = confirmation_message(requirements, variables)
        cl.user_session.set("awaiting_confirmation", True)
        cl.user_session.set("confirmed_study_ids", study_ids)
    if variable_report:
        text = variable_report + "\n\n" + text
    notice.content = text
    await notice.update()
