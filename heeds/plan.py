# チャットの文から、実行する試験をカタログだけで決めます。
# AI にはこの対応を書かせません。確認文もここで組み立てます。

from __future__ import annotations

from heeds.catalog import load_catalog, requirement_words, study_name
from heeds.shared_levels import PREVIEW_ROWS, build_shared_levels

CONFIRM_QUESTION = "これで合っていますか？"

_APPROVALS = (
    "はい",
    "うん",
    "ええ",
    "ok",
    "okay",
    "yes",
    "そうです",
    "その通り",
    "そのとおり",
    "合ってます",
    "合っています",
    "合ってる",
    "問題ありません",
    "問題ない",
    "お願いします",
    "お願い",
    "実行して",
    "実行してください",
    "進めて",
    "進めてください",
    "大丈夫",
    "よろしい",
    "よろしく",
    "間違いない",
    "それでいい",
    "了解",
)

# 同意の短文にこれらが含まれるときは、内容の変更として実行しない。
_PLAN_CHANGES = (
    "thickness",
    "width",
    "板厚",
    "幅",
    "刻み",
    "下限",
    "上限",
    "変えて",
    "変更",
    "違う",
    "キャンセル",
    "やめて",
    "中止",
)


def match_requirements(text: str, catalog: dict | None = None) -> list[dict]:
    """文に含まれる設計要件を、カタログの並びで返します。"""
    data = catalog or load_catalog()
    lowered = (text or "").lower()
    found = []
    for requirement in data["design_requirements"]:
        words = [requirement.get("label"), *(requirement.get("aliases") or [])]
        if any(str(word or "").strip() and str(word).lower() in lowered for word in words):
            found.append(requirement)
    return found


def requirements_by_ids(requirement_ids: list[str], catalog: dict | None = None) -> list[dict]:
    """保存していた要件 ID を、カタログの定義に戻します。"""
    data = catalog or load_catalog()
    by_id = {str(item.get("id")): item for item in data["design_requirements"]}
    return [by_id[item_id] for item_id in requirement_ids if item_id in by_id]


def study_ids_for(requirements: list[dict]) -> list[str]:
    """要件が実行する試験 ID です。カタログに書いた順で、重複は除きます。"""
    study_ids: list[str] = []
    for requirement in requirements:
        for study_id in requirement.get("study_ids") or []:
            text = str(study_id).strip()
            if text and text not in study_ids:
                study_ids.append(text)
    return study_ids


def is_run_approval(text: str, catalog: dict | None = None) -> bool:
    """確認への同意かどうかを見ます。要件や変数の変更は同意にしません。"""
    normalized = (text or "").strip().lower().replace(" ", "").replace("　", "")
    for mark in "。.!！?？、,":
        normalized = normalized.replace(mark, "")
    if not normalized or len(normalized) > 40:
        return False
    blocked = [word.lower() for word in _PLAN_CHANGES]
    blocked.extend(word.lower() for word in requirement_words(catalog))
    if any(word and word in normalized for word in blocked):
        return False
    return normalized in _APPROVALS


def confirmation_message(
    requirements: list[dict],
    variables: list[dict],
    catalog: dict | None = None,
) -> str:
    """実行前に出す確認文です。最後は必ず同意の質問で終わります。"""
    data = catalog or load_catalog()
    lines: list[str] = []
    for requirement in requirements:
        bits = [
            f"{study_name(str(study_id), data)}（{study_id}）"
            for study_id in requirement.get("study_ids") or []
        ]
        lines.append(f"{requirement.get('label')}として、次を実行する内容です。")
        lines.append("試験: " + "、".join(bits))
    lines.append("")
    for item in variables:
        lines.append(
            f"{item['name']}: 下限 {_num(item['lower'])}、初期値 {_num(item['baseline'])}、"
            f"上限 {_num(item['upper'])}、刻み {_num(item['step'])}"
        )
    levels, level_errors = build_shared_levels(variables)
    if level_errors:
        return "共通の水準を作れませんでした。\n\n" + "\n".join(level_errors)
    names = [str(item["name"]) for item in variables]
    lines.append("")
    lines.append(
        f"共通の水準は {len(levels)} 件です。"
        "実行する試験は、すべてこの順と同じ入力です。"
    )
    shown = levels[:PREVIEW_ROWS]
    for index, level in enumerate(shown, start=1):
        bits = "、".join(f"{name} {_num(level[name])}" for name in names)
        lines.append(f"水準{index}: {bits}")
    extra = len(levels) - len(shown)
    if extra > 0:
        lines.append(f"ほか {extra} 件は、同じ刻みの組み合わせで続きます。")
    lines.append("範囲を変えるときは CSV を直して再アップロードしてください。")
    lines.append(CONFIRM_QUESTION)
    return "\n".join(lines)


def _num(value) -> str:
    number = float(value)
    if number.is_integer():
        return str(int(number))
    return f"{number:g}"
