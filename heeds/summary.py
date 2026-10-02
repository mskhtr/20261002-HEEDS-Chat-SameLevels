# 実行結果の短い日本語要約だけを AI に書かせます。
# どの試験を実行するかは AI が決めません。表の数値はコードが付けます。

from __future__ import annotations

import json
import os


def summarize_result(result: dict) -> str:
    """結果 JSON を短く日本語にします。AI が使えないときは定型文を返します。"""
    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        from langchain_openai import AzureChatOpenAI
    except ImportError as error:
        return "結果は下の表です。要約用のライブラリがありません。\n\n" + str(error)

    provider = (os.getenv("LLM_PROVIDER") or "azure").strip().lower()
    if provider != "azure":
        return f"結果は下の表です。未知の LLM_PROVIDER です: {provider}"
    if not (os.getenv("AZURE_OPENAI_API_KEY") or "").strip():
        return "結果は下の表です。"

    try:
        model = AzureChatOpenAI(
            azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT") or "gpt-4o",
            api_version=os.getenv("OPENAI_API_VERSION") or "2024-10-21",
            temperature=0,
        )
        response = model.invoke(
            [
                SystemMessage(
                    content=(
                        "あなたは自動車CAEの試験アシスタントです。"
                        "渡された JSON の結果だけを、日本語で短くまとめてください。"
                        "数値を作り足さないでください。errors があればその内容を伝えてください。"
                        "出力列の名前は HEEDS の Response 名のままです。"
                        "どの試験を実行するかは、すでに決まっています。試験の選び直しはしないでください。"
                    )
                ),
                HumanMessage(content=json.dumps(result, ensure_ascii=False)),
            ]
        )
    except Exception as error:
        return "結果は下の表です。文章での要約はできませんでした。\n\n詳細: " + str(error)

    content = getattr(response, "content", "")
    text = content if isinstance(content, str) else str(content)
    return text.strip() or "結果は下の表です。"
