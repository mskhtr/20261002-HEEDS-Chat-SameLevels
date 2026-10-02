# 開始時の説明文を catalog.yaml から書き出します。
# chainlit.md は生成物です。手で編集しても、次回起動で上書きされます。

from __future__ import annotations

from pathlib import Path

from heeds.catalog import welcome_markdown

_ROOT = Path(__file__).resolve().parent.parent
_CHAINLIT_MD = _ROOT / "chainlit.md"


def publish_welcome() -> None:
    """chainlit.md をカタログから作り直し、言語別の残りファイルを消します。"""
    _CHAINLIT_MD.write_text(welcome_markdown() + "\n", encoding="utf-8")
    for leftover in _ROOT.glob("chainlit_*.md"):
        leftover.unlink(missing_ok=True)
