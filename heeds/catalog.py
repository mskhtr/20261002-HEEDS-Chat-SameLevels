# 実行してよい試験と、チャットの言葉の対応を catalog.yaml から読みます。
# 言葉・試験 ID・HEEDS 画面の Study 名の既定値は、このファイルが唯一の定義です。

from __future__ import annotations

import os
import re
from pathlib import Path

import yaml

_CATALOG_PATH = Path(__file__).resolve().parent / "catalog.yaml"
_ID_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def load_catalog(path: Path | None = None) -> dict:
    """catalog.yaml を検証して辞書で返します。"""
    catalog_path = Path(path) if path else _CATALOG_PATH
    with catalog_path.open(encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    if not isinstance(data, dict):
        raise ValueError("catalog.yaml の一番外側は、項目名を持つマッピングである必要があります。")
    studies = data.get("studies") or []
    requirements = data.get("design_requirements") or []
    if not isinstance(studies, list) or not isinstance(requirements, list):
        raise ValueError("catalog.yaml の studies と design_requirements はリストである必要があります。")

    seen_ids: list[str] = []
    for study in studies:
        if not isinstance(study, dict):
            raise ValueError("studies の各項目はマッピングである必要があります。")
        study_id = str(study.get("id") or "").strip()
        if not study_id:
            raise ValueError("studies に id の無い行があります。")
        if not _ID_PATTERN.fullmatch(study_id):
            raise ValueError(
                f"試験 ID は英字または _ で始まり、英数字と _ だけを使います: {study_id}"
            )
        if study_id in seen_ids:
            raise ValueError(f"試験 ID が重複しています: {study_id}")
        if not str(study.get("name_ja") or "").strip():
            raise ValueError(f"{study_id} に name_ja がありません。")
        if not str(study.get("heeds_name") or "").strip():
            raise ValueError(f"{study_id} に heeds_name がありません。")
        seen_ids.append(study_id)

    known = set(seen_ids)
    seen_requirement_ids: set[str] = set()
    for requirement in requirements:
        if not isinstance(requirement, dict):
            raise ValueError("design_requirements の各項目はマッピングである必要があります。")
        requirement_id = str(requirement.get("id") or "").strip()
        if not requirement_id:
            raise ValueError("design_requirements に id の無い行があります。")
        if not _ID_PATTERN.fullmatch(requirement_id):
            raise ValueError(
                f"設計要件 ID は英字または _ で始まり、英数字と _ だけを使います: {requirement_id}"
            )
        if requirement_id in seen_requirement_ids:
            raise ValueError(f"設計要件 ID が重複しています: {requirement_id}")
        seen_requirement_ids.add(requirement_id)
        label = str(requirement.get("label") or "").strip()
        if not label:
            raise ValueError("design_requirements に label の無い行があります。")
        aliases = requirement.get("aliases") or []
        if not isinstance(aliases, list):
            raise ValueError(f"{label} の aliases はリストである必要があります。")
        study_ids = requirement.get("study_ids") or []
        if not isinstance(study_ids, list) or not study_ids:
            raise ValueError(f"{label} の study_ids が空です。")
        for study_id in study_ids:
            if str(study_id) not in known:
                raise ValueError(
                    f"{label} の study_ids に、studies に無い ID があります: {study_id}"
                )
    return {"design_requirements": requirements, "studies": studies}


def allowed_study_ids() -> set[str]:
    """ホワイトリストのスタディ ID です。"""
    return {str(item["id"]) for item in load_catalog()["studies"]}


def get_study(study_id: str) -> dict | None:
    """ID に一致するスタディ定義を返します。無ければ None です。"""
    for item in load_catalog()["studies"]:
        if str(item.get("id")) == study_id:
            return item
    return None


def study_name(study_id: str, catalog: dict | None = None) -> str:
    """スタディ ID の日本語名です。"""
    data = catalog or load_catalog()
    for item in data["studies"]:
        if str(item.get("id")) == study_id and item.get("name_ja"):
            return str(item["name_ja"])
    return study_id


def env_override_key(study_id: str) -> str:
    """この PC だけ Study 名を変えるときの環境変数名です。"""
    return "HEEDS_STUDY_" + study_id.upper()


def heeds_study_name(study_id: str) -> str:
    """HEEDS 画面の Study 名です。環境変数があれば catalog.yaml より優先します。"""
    override = (os.getenv(env_override_key(study_id)) or "").strip()
    if override:
        return override
    study = get_study(study_id)
    if not study:
        return ""
    return str(study.get("heeds_name") or "").strip()


def iter_study_bindings() -> list[dict]:
    """チェックと実行が使う、試験 ID と画面上の Study 名の対応です。"""
    rows = []
    for study in load_catalog()["studies"]:
        study_id = str(study.get("id") or "")
        override = (os.getenv(env_override_key(study_id)) or "").strip()
        rows.append(
            {
                "id": study_id,
                "name_ja": str(study.get("name_ja") or study_id),
                "env_key": env_override_key(study_id),
                "heeds_name": override or str(study.get("heeds_name") or "").strip(),
                "source": "env" if override else "catalog",
            }
        )
    return rows


def requirement_words(catalog: dict | None = None) -> tuple[str, ...]:
    """チャットが要件ありとみなす言葉です。label と aliases です。"""
    data = catalog or load_catalog()
    words: list[str] = []
    seen: set[str] = set()
    for requirement in data["design_requirements"]:
        candidates = [requirement.get("label"), *(requirement.get("aliases") or [])]
        for candidate in candidates:
            text = str(candidate or "").strip()
            key = text.lower()
            if not text or key in seen:
                continue
            seen.add(key)
            words.append(text)
    return tuple(words)


def starter_examples(catalog: dict | None = None) -> list[tuple[str, str]]:
    """入力欄の上に出す短い例です。戻り値は (ラベル, 送信文) です。"""
    data = catalog or load_catalog()
    examples = []
    for requirement in data["design_requirements"]:
        label = str(requirement.get("label") or "").strip()
        if label:
            examples.append((label, f"{label}を確認したい。"))
    return examples


def welcome_markdown(catalog: dict | None = None) -> str:
    """チャット開始時の説明です。表の中身はカタログから作ります。"""
    data = catalog or load_catalog()
    lines = [
        "# 最適化設計AIチャットへようこそ。",
        "",
        "確認したい設計要件を書いてください。表の試験は、その順にすべて実行します。",
        "この表は `heeds/catalog.yaml` から作っています。言葉や試験を変えるときはそのファイルを編集し、チャットを起動し直してください。",
        "",
        "| 受け付ける設計要件 | 実行する試験 |",
        "| --- | --- |",
    ]
    for requirement in data["design_requirements"]:
        names = "、".join(
            study_name(str(study_id), data) for study_id in requirement.get("study_ids") or []
        )
        lines.append(f"| {requirement.get('label')} | {names} |")
    lines.extend(
        [
            "",
            "入力変数は、チャット開始時に添付される **sample.csv** をダウンロードして記入し、アップロードしてください。",
            "行を足せば変数も増やせます。CSV に書いた行だけを探査します。",
            "",
            "| 列 | 意味 |",
            "| --- | --- |",
            "| 変数名 | HEEDS の AgentVariable 名（英字。例: `thickness`） |",
            "| 下限値 | 探査の下限 |",
            "| 初期値 | 開始時の値（下限と上限の間） |",
            "| 上限値 | 探査の上限 |",
            "| 刻み | 水準の間隔 |",
            "",
            "刻みで切った値の組み合わせを、実行する試験すべてで同じ水準として使います。水準1は、どの試験でも同じ入力です。",
            "",
            "要件の言葉と、記入済み CSV の両方を送ってください。どちらか片方だけだと、足りない方を聞いて止まります。",
            "両方揃うと実行内容を示すので、合っていれば `はい` と返信してください。そこで HEEDS が動きます。",
            "範囲を変えるときは CSV を直して再アップロードしてください。",
            "",
            "HEEDS|MDO がインストールされ、`.env` に `HEEDS_EXE` と `HEEDS_PROJECT_PATH` が設定されている必要があります。",
        ]
    )
    return "\n".join(lines)
