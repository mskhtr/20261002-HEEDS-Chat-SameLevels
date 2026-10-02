# HEEDS プロジェクトの置き場

実行する `.heeds` ファイルをこのフォルダへ置けます。
`.heeds` ファイルは `.gitignore` の対象なので、誤ってリポジトリへ登録されません。

例:

```text
HEEDS_PROJECT/
└── MyProject.heeds
```

置いたあとは、プロジェクト直下の `.env` にフルパスを書きます。

```dotenv
HEEDS_PROJECT_PATH=C:/Users/masaki/Documents/python-projects/20261002_HEEDS-Chat-SameLevels/HEEDS_PROJECT/MyProject.heeds
```

ファイルを別の場所へ置いても動きます。その場合は、実際の場所を
`HEEDS_PROJECT_PATH` に書いてください。

Study 名・AgentVariable 名・Response の約束は
[`docs/06_HEEDSファイルを作るとき.md`](../docs/06_HEEDSファイルを作るとき.md)、
名前の事前確認は
[`docs/07_設定チェック.md`](../docs/07_設定チェック.md)です。
