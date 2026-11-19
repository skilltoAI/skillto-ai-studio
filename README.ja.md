<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/readme/assets/studio-logo-dark.png">
    <img src="docs/readme/assets/studio-logo-light.png" alt="Skillto.ai | 个人工作台" width="650">
  </picture>
</p>

<h1 align="center">Skillto.ai Studio</h1>

<p align="center">コンテンツ制作と日常業務のための AI ワークスペース</p>

<p align="center"><a href="#主な機能">機能</a> · <a href="#スクリーンショット">画面</a> · <a href="#クイックスタート">インストール</a> · <a href="skills/skillto-ai-studio/references/installation.md">ドキュメント</a><br>
  <a href="https://github.com/skilltoAI/skillto-ai-studio">GitHub</a> ·
  <a href="https://codeup.aliyun.com/6856a1da33ca8867a4350914/skillto-ai-studio">Codeup</a> ·
  <a href="skills/skillto-ai-studio/SKILL.md"><kbd>19 Skills</kbd></a> ·
  <a href="apps/stass/README.md"><kbd>STASS MCP</kbd></a>
</p>

<p align="center"><a href="README.md"><kbd>简体中文</kbd></a> &nbsp; <a href="README.en.md"><kbd>English</kbd></a> &nbsp; <kbd>日本語</kbd> &nbsp; <a href="README.de.md"><kbd>Deutsch</kbd></a></p>

## 対象ユーザー

- **AI 講座・有料コンテンツの制作者**は、テーマ選定、参考動画の分析、講座台本の執筆、表紙と絵コンテのレビューに活用できます。
- **日常業務で AI を使う人**は、資料・文書・タスクをナレッジベースや表、レポートに整理し、確認事項を記録できます。
- **AI クリエイター**は、キャラクター、参考素材、ショット、モーションテンプレートを管理し、画像生成、動画生成、編集の工程を連携できます。

## 主な機能

- **スキル**。親スキルがタスクを 18 個の専門スキルに振り分けます。調査、メディア分析、絵コンテ、表紙、レポート、制作を扱います。
- **エージェントとの連携**。対応クライアントに STASS MCP を設定すると、Codex や Claude Code から作業データを読み取り、更新できます。人は同じインスタンスをブラウザーで確認できます。
- **AI を使った動画編集**。参考動画を分析し、区間を選び、メモを残せます。仮編集と字幕から HyperFrames や Remotion の編集を計画し、Motion でテンプレートを管理できます。
- **画像・動画生成**。表紙のプロンプト、キャラクターの参考素材、ショット案を作成できます。必要なサービスと権限があれば、Creator MCP で素材を割り当て、ビジュアルワークフローを実行できます。

[スキル一覧](README.md#技能清单) · [対応クライアントと依存関係](skills/skillto-ai-studio/references/compatibility.md)

## スクリーンショット

稼働中の STASS を、架空のデモデータで撮影しました。

**企画管理表とレビュー用メモ**

![企画管理表とレビュー用メモ](docs/readme/assets/studio-tables.png)

**台本のバージョン管理と行ごとの注釈**

![台本のバージョン管理と行ごとの注釈](docs/readme/assets/studio-rewrite.png)

**台本から参照できる Motion 絵コンテ**

![台本から参照できる Motion 絵コンテ](docs/readme/assets/studio-storyboard.png)

## クイックスタート

Git、Python 3.10 以降、利用するクライアントを用意し、次のコマンドでスキルを確認・インストールします。

```sh
git clone https://github.com/skilltoAI/skillto-ai-studio.git
cd skillto-ai-studio
python scripts/install.py --agent codex --dry-run
python scripts/install.py --agent codex
```

Claude Code の場合は `--agent codex` を `--agent claude` に置き換えます。新しいセッションで、Codex では `$skillto-ai-studio`、Claude Code では `/skillto-ai-studio` を呼び出します。

この手順でインストールされるのはスキルです。Windows 用ワークステーション、MCP の登録、外部の生成サービスは個別に設定します。オフラインパッケージは候補版で、別の Windows 環境での完全なインストールと更新の検証は継続中です。

[Windows の導入状況](README.md#windows-完整安装状态) · [導入・更新・トラブルシューティング](skills/skillto-ai-studio/references/installation.md) · [開発への参加](CONTRIBUTING.md)
