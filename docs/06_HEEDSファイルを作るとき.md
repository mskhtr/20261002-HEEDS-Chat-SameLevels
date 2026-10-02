# HEEDS ファイルを作るとき（プログラムと名前を揃える）

この文書は、**HEEDS|MDO でプロジェクトを作る人**向けです。  
チャットから動かす接続手順は [05_HEEDS接続.md](05_HEEDS接続.md)、設定項目の意味は [03_変数と設定.md](03_変数と設定.md) です。  
チャットの言葉や、解析の組み合わせを変えるときは [08_試験の種類を変える.md](08_試験の種類を変える.md) です。

プログラムは HEEDS の画面を見ていません。次の **英字の名前** だけで探します。**1文字でも違うと動きません**（大文字小文字・スペース・アンダースコアも別物です）。

## 30秒で分かる結論

| HEEDS で作るもの | プログラムが探す名前 | 変えてよいか |
| --- | --- | --- |
| `.heeds` のファイル名 | `.env` の `HEEDS_PROJECT_PATH` が指すパス | **ファイル名は自由**。パスを `.env` に書く |
| Study（スタディ）の名前 | `catalog.yaml` の `heeds_name`。`.env` の `HEEDS_STUDY_*` があればそちら | **変えてよい**。変えたら `heeds_name` か `.env` を同じにする |
| 入力変数（AgentVariable） | CSV の「変数名」。記入例は `thickness` と `width` | **CSV の名前と一字一句同じ**。行を足したらその名前も作る |
| 出力（Response） | 表に出す列 | **自由**。通常は Response 名が見出しになる。同名衝突時だけ `試験ID.Response名` |

## なぜ名前がズレると止まるか

チャット側と HEEDS 側では、同じものでも呼び方が違います。プログラムが橋渡しするのは、Study 名と入力変数名です。出力は HEEDS の Response 名をそのまま出します。

```text
チャットの言葉          プログラム                         HEEDS の画面
─────────────          ──────────                         ──────────────
「衝突安全」     →     試験 ID  stress / crash     →     heeds_name（Study_stress など）
CSV の変数名     →     その綴りのまま             →     AgentVariable 名
（カタログは見ない）                                     Response 名が表の見出し
```

| 場所 | ファイル | 役割 |
| --- | --- | --- |
| カタログ | `heeds/catalog.yaml` | 言葉、試験 ID、日本語名、画面の Study 名の既定 |
| 上書き | `.env` の `HEEDS_STUDY_*` | この PC だけ画面名が違うとき。無ければカタログを使う |
| 実体 | `.heeds` プロジェクト | 本当に計算するスタディ・変数・出力 |

**カタログの試験 ID（`stress`）と、HEEDS の Study 名（`Study_stress`）は別物です。**  
`stress` という Study を HEEDS に作る必要はありません。`heeds_name` で対応づけます。

## 早見表（同梱時の既定）

HEEDS を新規作成するときは、まずこの表どおりに作るのがいちばん安全です。言葉を変えたあとは、表ではなく `catalog.yaml` を見てください。

### スタディ 4 つ

| チャット | 何の解析か | カタログ試験 ID | 画面名の既定（`heeds_name`） | 上書きする環境変数 |
| --- | --- | --- | --- | --- |
| 衝突安全 | 静荷重 | `stress` | `Study_stress` | `HEEDS_STUDY_STRESS` |
| 衝突安全 | 衝突 | `crash` | `Study_crash` | `HEEDS_STUDY_CRASH` |
| NVH | 固有値 | `eigenvalue` | `Study_eigen` | `HEEDS_STUDY_EIGENVALUE` |
| NVH | 周波数応答 | `frf` | `Study_frf` | `HEEDS_STUDY_FRF` |

4 つとも、カタログに残っているあいだは必要です。欠けていると、その要件の実行か、事前チェックが失敗します。

### 入力変数（CSV に書いた名前）

探査するのは、ユーザーがアップロードした CSV の行だけです。個数は2個ではありません。`width2` のように行を足したら、実行する Study すべてにその名前の AgentVariable を作ります。事前チェックは、カタログにある Study 全部と CSV を比べます。

記入例（`sample.csv`）:

| 意味 | HEEDS の AgentVariable 名 | 下限値 | 初期値 | 上限値 | 刻み |
| --- | --- | --- | --- | --- | --- |
| 板厚 | `thickness` | 1 | 2 | 3 | 0.5 |
| 幅 | `width` | 40 | 50 | 60 | 10 |

使ってはいけない例: CSV が `thickness` なのに HEEDS が `板厚` / `Thickness` / `t`。

### 出力 Response

各 Study にある Response を、実行後の表に出します。名前は HEEDS 側で自由です。カタログとは比べません。見出しは通常 Response 名で、日本語名や単位は付きません。同じ Response 名が複数試験にあるとき、または入力変数名などと同じときは、値を失わないよう `試験ID.Response名` にします。

どの解析結果を読むかは、HEEDS 側の結線です。Response が無い Study は、その試験の出力列が出ません。

## 1. `.heeds` のファイル名

**ファイル名そのものは自由**です。`MyProject.heeds` でも `車体DOE.heeds` でも動きます。

プログラムが見るのは、`.env` のこの 1 行だけです。

```dotenv
HEEDS_PROJECT_PATH=C:/Users/masaki/Documents/python-projects/20261002_HEEDS-Chat-SameLevels/HEEDS_PROJECT/MyProject.heeds
```

気をつけること:

- フルパスを書く（相対パスは使わない）
- 今 GUI で開いているファイルと **同じファイル** を指す
- パスの区切りは `/` を推奨
- 拡張子は `.heeds`
- 中身に、カタログが参照する Study が入っていること

ファイル名を変えたら、`.env` の `HEEDS_PROJECT_PATH` も同じ日に直してください。上のパスは例です。プロジェクトを別のフォルダに置いたなら、その場所を書きます。

## 2. Study 名（画面に出るスタディ名）

プログラムは次のように探します。

```text
project.findChild(「heeds_name または .env の上書き」, Study)
```

そのため:

- Study 名は **HEEDS 画面の表示名**と、プログラムが解決した名前が **一字一句同じ**
- `Study_Stress` と `Study_stress` は別物
- 先頭・末尾のスペースも別物
- カタログ ID の `stress` を Study 名だと思わない

画面名を「静荷重_車体」にした例です。共有のカタログを変えてよいなら、`heeds_name` をその文字列にします。リポジトリの既定は触らず、この PC だけ変えるなら `.env` です。

```dotenv
HEEDS_STUDY_STRESS=静荷重_車体
```

日本語の Study 名でも、解決した名前と完全一致すれば動きます。  
環境変数の左側（`HEEDS_STUDY_STRESS`）は、試験 ID `stress` を大文字にしたものです。ID を変えたときは、この左側も変わります。

GUI で Study 名を変えたら、**同じ日に `heeds_name` か `.env` も直す**。片方だけ直すと Study が見つかりません。

## 3. 入力変数名と、プログラムが書き込むパラメータ

### 変数名は CSV の「変数名」列

プログラムは、アップロードされた CSV の各行について、各 Study に次をします。

```text
study.findVariable("CSVの変数名")
```

`sample.csv` なら `thickness` と `width` です。`width2` という行を足した CSV なら `width2` も探します。見つからないと、その Study は失敗します。

必須条件:

1. **実行するスタディすべて**に、CSV の変数名が同じ綴りである
2. 名前は英字で始める（数字と `_` は使える。コメントや説明を日本語にするのは可）
3. 種類は **AgentVariable**（スタディから `findVariable` できること）
4. 解析モデル側でも、その変数が入力としてタグ付けされていること。名前だけ合っていてモデルに繋がっていないと、実行はできても結果が変わりません
5. CSV に無い AgentVariable が Study に残っていると、その変数は HEEDS 側の範囲のまま振れることがある。事前チェックは、この「HEEDS にだけある」名前を不一致として出します

### 実行のたびに上書きされる値

実行は、元の `.heeds` ではなく、同じフォルダに作った一時コピーで行います。コピー側の Study は評価専用（`EVAL`）にし、CSV から作った共通水準を同じ順で渡します。GUI に残してある探索方法は、元ファイル側に残ります。

CSV の行だけ、プログラムは変数範囲を **コピー側で毎回セットし直します**。

| HEEDS のプロパティ | プログラムが入れる値 | 例（板厚 下限1、初期値2、上限3、刻み 0.5） |
| --- | --- | --- |
| `min` | 下限値 | `1.0` |
| `max` | 上限値 | `3.0` |
| `baseline` | 初期値 | `2.0` |
| `resolution` | 水準の個数。`round((上限−下限)÷刻み)+1`（最低 2） | `(3.0−1.0)/0.5+1` → `5` |

実際に計算する点は、この resolution から Study ごとに作るのではありません。下限から上限まで刻み幅で切った値の直積を、全 Study の UserDesignSet に同じ順で書きます。各設計の `map` は false なので、Study 側の分割へ値を吸い寄せません。板厚 1, 1.5, 2, 2.5, 3 と幅 40, 50, 60 なら 15 件で、水準1はどの Study でも板厚 1・幅 40 です。

`resolution` は「刻み幅そのもの」ではなく、**範囲を何点に分割するか**です。HEEDS 側の変数は、このプロパティを受け取れる連続変数にしてください。

手動確認用に GUI で範囲を入れておくのは問題ありません。チャットから回すときは、コピー側だけが上書きされます。

## 4. 出力 Response

プログラムは Study の AgentResponse を列挙し、名前と値を表に出します。`catalog.yaml` に出力名はありません。

Response 名は HEEDS 側で決めてください。表の見出しは通常その文字列です。同名衝突時だけ試験 ID が前に付きます。

## 5. プログラムが見ないもの（自由にしてよい）

次はプログラムが名前で探しません。HEEDS 内で解析が回るなら、好きな名前で構いません。

| 項目 | 備考 |
| --- | --- |
| 解析ソフトの入力ファイル名（Nastran の `.bdf` など） | スタディのプロセスに載っていればよい |
| プロセス名、解析実行フォルダ名 | 同上 |
| 変数・Response のコメント / 説明文 | 日本語で書いてよい |
| 目的関数・制約の設定 | チャット実行は一時コピーを EVAL にし、共通水準だけを評価する。元ファイルの探索設定は残る |
| レポートの見た目 | プログラムは `{試験ID}_Report.txt` を別途書き出す |

ただし、スタディは GUI で一度手動実行でき、`checkAndReport` が通る状態にしておいてください。プロセスが壊れていると、名前が正しくてもバッチ実行で失敗します。

## 6. プログラムが作る結果ファイル名（混同しやすい）

実行後、`runs/<時刻>/` に残るファイルは **カタログの試験 ID** で名前が付きます。HEEDS の Study 名ではありません。

| ファイル | 例 | 由来 |
| --- | --- | --- |
| 横断表 | `levels_summary.csv` | 入力の組が同じ行へ、各試験の Response を横に並べたもの |
| 試験ごとのデザイン | `stress_designs.csv` | 試験 ID `stress`。Study 名が `Study_stress` でも、ファイル名は ID |
| レポート | `stress_Report.txt` | 同上 |
| 渡したコマンド | `command.txt` | `HEEDSMDO.exe -b` の引数 |
| HEEDS の要約 | `heeds_summary.json` | デザインの入力と Response |
| ログ | `heeds_stdout.txt` / `heeds_stderr.txt` | バッチの標準出力と標準エラー |
| 一時スクリプト | `run_studies_heeds.py` | テンプレートに値を埋めたコピー |

照合だけのときは `runs/check_<時刻>/` です。解析は入っていません。

## 作ったあとのチェックリスト

1. `.env` の `HEEDS_EXE` と `HEEDS_PROJECT_PATH` が、実在するファイルを指している
2. カタログの各 `heeds_name` が、HEEDS 画面の Study 名と一致している。違う PC なら `.env` の上書きがある
3. 使う CSV の変数名が、各 Study の AgentVariable にある
4. 見たい結果が、各 Study の Response になっている
5. GUI で各 Study を一度手動実行できる
6. `check_heeds_project.py` の結果が「合っています」になる。変数も見るなら CSV を引数に付ける

## やってはいけない例

| やること | 起きること | 代わりに |
| --- | --- | --- |
| Study 名を画面だけで変える | 見つからない | `heeds_name` か `.env` も同じ日に直す |
| 変数を `板厚` にする（CSV は `thickness`） | Variable not found | CSV と同じ綴りにする |
| `stress` という Study を作って、`Study_stress` を作らない | 既定の `heeds_name` では見つからない | 画面名を `Study_stress` にするか、`heeds_name` を `stress` に変える |
| 衝突安全用の 2 Study だけ作り、カタログには 4 つ残す | 事前チェックが NVH 側で失敗する | 4 つ作るか、使わない ID をカタログから外す |
| Response を付けない | その試験の出力列が無い | 見たい結果を Response にする |
| ホストの Python でテンプレートを実行する | `import HEEDS` で失敗 | チャットか `check_heeds_project.py` から起動する |

## 名前を変えるときの分担

| 変えたいもの | 手順 | 触る場所 |
| --- | --- | --- |
| `.heeds` のファイル名や置き場所 | パスを書き換える | `.env` の `HEEDS_PROJECT_PATH` |
| 画面の Study 名 | カタログの既定を変える | `heeds_name` |
| この PC だけの Study 名 | 1行足す | `.env` の `HEEDS_STUDY_<IDの大文字>` |
| チャットの言葉、実行する試験の組み合わせ | [08_試験の種類を変える.md](08_試験の種類を変える.md) | `catalog.yaml` だけ |
| CSV に無い変数を振る | 行を足し、HEEDS にも同じ名前を作る | CSV と AgentVariable |
| 表の見出し | Response 名を変える | HEEDS のみ |

## 関連ドキュメント

- [05_HEEDS接続.md](05_HEEDS接続.md) … インストールと `.env`、起動前の確認
- [07_設定チェック.md](07_設定チェック.md) … 名前が揃っているかのコマンド
- [08_試験の種類を変える.md](08_試験の種類を変える.md) … 言葉と試験 ID の変え方
- [04_SPEC.md](04_SPEC.md) … チャットに返るものの形
