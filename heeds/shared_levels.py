# CSV の下限・刻み・上限から、全試験で共有する水準表を作ります。
# 番号は CSV だけで決まるので、別々に実行しても同じ水準は同じ入力です。

from __future__ import annotations

import itertools

MAX_LEVELS = 200
PREVIEW_ROWS = 8


def axis_values(lower: float, upper: float, step: float) -> list[float]:
    """下限から上限まで、刻み幅で等間隔の値を返します。最後の値は上限です。"""
    count = int(round((upper - lower) / step))
    if count < 0:
        return []
    digits = _decimal_places(lower, upper, step)
    values: list[float] = []
    for index in range(count + 1):
        raw = upper if index == count else lower + index * step
        values.append(round(float(raw), digits))
    return values


def build_shared_levels(variables: list[dict]) -> tuple[list[dict], list[str]]:
    """変数の直積を、CSV の行順で返します。先頭の変数がいちばん遅く変わります。"""
    if not variables:
        return [], ["振る変数がありません。"]

    names: list[str] = []
    axes: list[list[float]] = []
    errors: list[str] = []
    total = 1
    for spec in variables:
        name = str(spec.get("name") or "").strip() or "変数"
        try:
            lower = float(spec["lower"])
            upper = float(spec["upper"])
            step = float(spec["step"])
        except (KeyError, TypeError, ValueError):
            errors.append(f"{name} の下限・上限・刻みから水準を作れません。")
            continue
        if upper < lower or step <= 0:
            errors.append(f"{name} の範囲と刻みから水準を作れません。")
            continue
        count = int(round((upper - lower) / step)) + 1
        if count < 1:
            errors.append(f"{name} の水準が1件もありません。")
            continue
        total *= count
        if total > MAX_LEVELS:
            return [], [
                (
                    f"水準の組み合わせが {MAX_LEVELS} 件を超えます"
                    f"（少なくとも {total} 件）。"
                    "刻みを粗くするか、変数を減らしてください。"
                )
            ]
        names.append(name)
        axes.append(axis_values(lower, upper, step))

    if errors:
        return [], errors

    levels = [
        {name: value for name, value in zip(names, combo, strict=True)}
        for combo in itertools.product(*axes)
    ]
    return levels, []


def _decimal_places(*numbers: float) -> int:
    places = 0
    for number in numbers:
        text = f"{number:.12g}"
        if "e" in text.lower():
            places = max(places, 12)
            continue
        if "." in text:
            places = max(places, len(text.split(".", 1)[1]))
    return places
