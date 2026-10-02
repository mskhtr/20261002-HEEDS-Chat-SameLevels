# チャット画面を起動するための入口です。
#
# 使い方（Python 3.12 の仮想環境）:
#   py -3.12 -m venv .venv
#   .\.venv\Scripts\python.exe run_app.py
#
# 公式の起動方法は `chainlit run app.py` です。
# 環境によってはその方法で画面が真っ白になることがあるため、
# このファイルは nest_asyncio.apply を無効にしてから Chainlit を起動します。

import sys

_EXPECTED = (3, 12)
if sys.version_info[:2] != _EXPECTED:
    expected = ".".join(str(part) for part in _EXPECTED)
    actual = sys.version.split()[0]
    print(
        f"警告: このプロジェクトは Python {expected} 向けです。"
        f" 今動いているのは {actual} です。"
        f" py -{expected} -m venv .venv で仮想環境を作り、"
        r" .\.venv\Scripts\python.exe run_app.py で起動してください。",
        file=sys.stderr,
    )

import nest_asyncio  # noqa: E402 - Chainlit の import 前に差し替える

nest_asyncio.apply = lambda *args, **kwargs: None

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from chainlit.cli import run_chainlit  # noqa: E402

from heeds.welcome import publish_welcome  # noqa: E402

if __name__ == "__main__":
    publish_welcome()
    run_chainlit("app.py")
