# HEEDS をつなぐ（公式 Python API）

この文書は、チャットから **本物の HEEDS|MDO** を動かすための接続手順です。

チャットの起動方法は [動かし方.md](動かし方.md)、何をするシステムかは [04_SPEC.md](04_SPEC.md) です。  
初学者向けの全体像・ファイル・変数の説明は [01_はじめに.md](01_はじめに.md) / [02_ファイルの関連.md](02_ファイルの関連.md) / [03_変数と設定.md](03_変数と設定.md) です。  
**HEEDS プロジェクトを作るときのファイル名・変数名・出力名**は [06_HEEDSファイルを作るとき.md](06_HEEDSファイルを作るとき.md) です。  
プログラム設定と HEEDS の実名を突き合わせる手順は [07_設定チェック.md](07_設定チェック.md) です。

公式 API のマニュアル一式は、このリポジトリには置いていません。このプログラムが実際に呼ぶ処理は `heeds/scripts/run_studies_template.py` と `heeds/scripts/check_project_template.py` にあります。どちらも `HEEDSMDO.exe -b` の中だけで動きます。

## 1. 全体の流れ

チャットに「衝突安全を確認したい」と書くと、プログラムがカタログから試験と変数を示して「これで合っていますか？」と聞きます。同意してから、HEEDS|MDO のスタディを実行して結果を返します。

```mermaid
flowchart LR
    Chat[チャット]
    Plan[plan.py]
    Client[client.py]
    Heeds[HEEDSMDO.exe]

    Chat --> Plan --> Client --> Heeds
```

計算は常に HEEDS 側です。接続に必須な設定は `.env` の `HEEDS_EXE` と `HEEDS_PROJECT_PATH` です。Study 名は `catalog.yaml` の `heeds_name` が既定で、この PC だけ違うときだけ `HEEDS_STUDY_*` を書きます。

## 2. 接続の仕組み（公式 Python API）

HEEDS の Python API は、次の前提です。

- `import HEEDS` は **HEEDSMDO のプロセス内**でのみ有効
- バッチ実行は次の形です

```text
HEEDSMDO.exe -b project.heeds script.py
```

`heeds/cli_backend.py` は、許可された試験と、CSV の変数だけを埋め込んだ一時スクリプトを生成し、上のコマンドで実行します。AI にコマンドや Python を書かせません。一時スクリプトは `runs/<時刻>/run_studies_heeds.py` に残るので、あとから何を渡したか見られます。

名前の照合（解析しない）も同じ形です。テンプレートは `check_project_template.py` で、出力先は `runs/check_<時刻>/` です。

## 3. 知っておく言葉

| 言葉 | 意味 |
| --- | --- |
| HEEDS\|MDO | Siemens の最適化・DOE ソフト。解析をまとめて回す |
| スタディ | HEEDS の中の「1つの試験セット」 |
| AgentVariable | スタディ側の入力変数（min / baseline / max / resolution） |
| AgentResponse | スタディ側の出力。チャットの表の見出しになる |
| `-b` | UI なしのバッチ実行 |
| `.heeds` | HEEDS プロジェクトファイル |
| `.env` | このフォルダに置く設定。キーとパス |
| `heeds_name` | カタログに書いた、画面の Study 名の既定値 |

## 4. 人とプログラムの分担

| 人が HEEDS の画面でやること | プログラムがやること |
| --- | --- |
| カタログに書いた試験ごとの Study を作る。同梱時は静荷重・衝突・固有値・周波数応答の 4 つ | チャットの言葉から、`catalog.yaml` の `study_ids` を選ぶ |
| 各 Study の AgentVariable 名を、使う CSV の「変数名」に合わせる | 変数範囲を AgentVariable に渡し、実行して結果をチャットに返す |
| `HEEDSMDO.exe` と `.heeds` のパスを `.env` に書く | `HEEDSMDO.exe -b` で公式スクリプトを起動する |
| 画面の Study 名を `heeds_name` と揃える。揃えられない PC だけ `.env` で上書きする | 環境変数が無ければ `heeds_name` で `findChild` する |

## 4.1 名前で動かなくなる点（必ず読む）

くわしい説明は [06_HEEDSファイルを作るとき.md](06_HEEDSファイルを作るとき.md) です。

HEEDS でプロジェクトやスタディを作るとき、**表示名を好き勝手に変えるとチャットから動かなくなります**。次の4つは別物です。

| 種類 | 例 | 変えてよいか |
| --- | --- | --- |
| カタログの試験 ID | `stress` | 変えてよいが、`study_ids` と環境変数名の大文字が一緒に変わる。手順は [08_試験の種類を変える.md](08_試験の種類を変える.md) |
| HEEDS の Study 名 | `Study_stress` | 変えてよい。`heeds_name` または `.env` の上書きと一字一句同じにする |
| AgentVariable 名 | `thickness` | **CSV の変数名と一字一句同じ**。別名だと失敗 |
| 出力 Response 名 | Study ごとに付ける名前 | **自由**。表の見出しはその名前 |

同梱時の対応（画面名をこのとおり作れば、`.env` に Study 名は書かない）:

| チャットの言葉 | カタログ試験 ID | カタログの `heeds_name` | 上書きするときだけ書く環境変数 |
| --- | --- | --- | --- |
| 衝突安全 | `stress` | `Study_stress` | `HEEDS_STUDY_STRESS` |
| 衝突安全 | `crash` | `Study_crash` | `HEEDS_STUDY_CRASH` |
| NVH | `eigenvalue` | `Study_eigen` | `HEEDS_STUDY_EIGENVALUE` |
| NVH | `frf` | `Study_frf` | `HEEDS_STUDY_FRF` |

気をつけること:

1. 同梱のカタログをそのまま使うなら、**Study は 4 つ**。足りないと、その要件の実行か、事前チェックが落ちる
2. Study 名は **大文字小文字・スペース・アンダースコアまで完全一致**（`Study_Stress` と `Study_stress` は別物）
3. Study 名を GUI で変えたら、**同じ日に `heeds_name` か `.env` も直す**
4. 変数名は CSV 次第です。`sample.csv` のままなら各 Study に `thickness` と `width`。`板厚` / `Thickness` / `t` は、CSV にも同じ綴りが無いと不可
5. 出力 Response は Study にあれば表に出ます。名前は HEEDS 側のもので、カタログには書きません
6. `.heeds` のパスは、`.env` の `HEEDS_PROJECT_PATH` と一致させる
7. カタログの `stress` を HEEDS の Study 名だと思わない

## 5. セットアップ手順

以降のコマンドは **Windows PowerShell** 用です。

### 5.1 HEEDS 側の準備

1. HEEDS|MDO をインストールする
2. `.heeds` プロジェクトを用意する。同梱カタログなら Study は 4 つ。名前の注意は **4.1** と [06_HEEDSファイルを作るとき.md](06_HEEDSファイルを作るとき.md)
3. 各 Study に、使う CSV と同じ AgentVariable があることを確認する
4. GUI で一度手動実行し、問題ないことを確認する

### 5.2 `.env` を書く

```dotenv
HEEDS_EXE=C:/Program Files/Siemens/HEEDS/2504/HEEDSMDO.exe
HEEDS_PROJECT_PATH=C:/Users/masaki/Documents/python-projects/20261002_HEEDS-Chat-SameLevels/HEEDS_PROJECT/MyProject.heeds
HEEDS_TIMEOUT_SEC=3600
```

パスは自分の PC の実パスに置き換えます。`HEEDS_PROJECT_PATH` の例は、このフォルダの下に `HEEDS_PROJECT` を作った場合です。別の場所にあるなら、そのフルパスにします。

画面名がカタログと違うときだけ、次のように足します。右側は HEEDS 画面の表示名です。

```dotenv
HEEDS_STUDY_STRESS=Study_stress
```

パスの区切りは `/` を推奨します。

書いたら、チャットの前に名前が一致するか確認します（解析はしません）。

```powershell
.\.venv\Scripts\python.exe check_heeds_project.py
```

または `check_heeds.bat`。手順の説明は [07_設定チェック.md](07_設定チェック.md) です。

### 5.3 動くか確認する（チャットより先）

1. 実行ファイルと `.heeds` があるか
2. `check_heeds_project.py` でプロジェクトを開けるか（解析はしない）
3. チャットで短い確認をしてから、同意して1回実行する

#### A. 実行ファイルの有無

引用符の中を、`.env` と同じパスに置き換えてください。

```powershell
Test-Path "C:\Program Files\Siemens\HEEDS\2504\HEEDSMDO.exe"
Test-Path "C:\Users\masaki\Documents\python-projects\20261002_HEEDS-Chat-SameLevels\HEEDS_PROJECT\MyProject.heeds"
```

どちらも `True` であること。`False` ならパスかインストールを直してから次へ進みます。

ホストの Python で `import HEEDS` が失敗するのは**正常**です。

#### B. 名前の照合

[07_設定チェック.md](07_設定チェック.md) のコマンドです。ここで Study 名が「直すこと」に出たら、チャットへ進んでも同じ理由で失敗します。

#### C. チャット経由

[動かし方.md](動かし方.md) のとおり起動し、`sample.csv` と「衝突安全を確認したい。」を送ります。確認文の試験が静荷重と衝突なら、言葉の対応は合っています。`はい` のあとで失敗するときは、`runs/<時刻>/heeds_stderr.txt` と `heeds_summary.json` を見ます。

### 5.4 この確認で分かること / 分からないこと

分かること: パスが存在すること、カタログの Study 名がプロジェクト内にあること、CSV を渡したときの変数名の過不足。

分からないこと: 解析モデルへのタグ付け、計算の正しさ、Response が値を持つか。それらは GUI で一度手動実行して確認します。

## 6. プログラムがやっていること（要約）

同意後の1回の実行で、`cli_backend.py` は次をします。

1. 試験 ID がカタログの `studies` にあるか、変数名が英数字と `_` か、下限・上限・刻み・初期値が数値として妥当か見る。水準の組み合わせが 200 件を超えていないかも見る
2. `HEEDS_EXE` と `HEEDS_PROJECT_PATH` のファイルがあるか見る
3. 各 ID の画面名を、環境変数か `heeds_name` から取る。空なら起動しない
4. 元の `.heeds` を同じフォルダへコピーし、`runs/<UTC時刻>/` に一時スクリプトを書き、コピーを `HEEDSMDO.exe -b` で `HEEDS_TIMEOUT_SEC` 秒まで待つ
5. `heeds_summary.json` を読み、試験ごとの CSV と、共通水準の横断表を作る

HEEDS の中のスクリプトは、コピー側の Study を `findChild` し、変数を `findVariable` し、min / baseline / max / resolution をセットしたあと、Study を `EVAL` にして共通水準を UserDesignSet に書きます。各設計の `map` は false です。レポートは `{試験ID}_Report.txt` です。元の `.heeds` の探索設定は変わりません。

## 7. よくあるつまずき

### 名前・プロジェクトまわり

| 症状 | よくある原因 | 対処 |
| --- | --- | --- |
| Study が見つからない | `heeds_name` と画面名の不一致。大文字小文字、スペース | [07_設定チェック.md](07_設定チェック.md) の「直すこと」 |
| 衝突安全は動くが NVH だけ失敗 | 4 Study のうち片方の組が無い、または名前が違う | カタログの4つの `heeds_name` を画面と並べる |
| Variable not found | CSV の変数名が、その Study の AgentVariable に無い | 綴りを揃える。行を足した名前も Study に作る |
| 表に出力列が無い | その Study に Response が無い | HEEDS で Response を結線する |
| 照合では全 Study の差分が出る | チェックはカタログの全部を見る | 今回使わない Study も、カタログに残っているあいだは変数を揃えるか、`studies` から外す |

### パス・実行まわり

| 症状 | よくある原因 | 対処 |
| --- | --- | --- |
| HEEDS_EXE が見つからない | パス違い、インストール先の版違い | `Test-Path` で確認し `.env` を直す |
| タイムアウト | 解析が `HEEDS_TIMEOUT_SEC` を超えた | 秒数を増やす。GUI で同じ Study が完了するか見る |
| 終了コードが 0 以外 | スクリプトが例外で終わった | `heeds_stderr.txt` と `heeds_summary.json` の `errors` |
| 画面が真っ白 | `chainlit run app.py` で起動した | `run_app.py` で起動し直す |

## 関連ドキュメント

- [06_HEEDSファイルを作るとき.md](06_HEEDSファイルを作るとき.md)
- [07_設定チェック.md](07_設定チェック.md)
- [08_試験の種類を変える.md](08_試験の種類を変える.md)
- [09_起動から終了までの流れ.md](09_起動から終了までの流れ.md)
