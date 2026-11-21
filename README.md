<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/readme/assets/studio-logo-dark.png">
    <img src="docs/readme/assets/studio-logo-light.png" alt="Skillto.ai | 个人工作台" width="650">
  </picture>
</p>

<h1 align="center">Skillto.ai Studio</h1>

<p align="center">The AI-native personal workspace built for agents</p>

<p align="center"><a href="#overview">Overview</a> · <a href="#architecture">Architecture</a> · <a href="#features">Features</a> · <a href="#screenshots">Screenshots</a> · <a href="#quick-start">Quick start</a> · <a href="skills/skillto-ai-studio/references/installation.md">Documentation</a><br>
  <a href="https://www.skillto.ai/">Skillto.ai</a> ·
  <a href="https://github.com/skilltoAI/skillto-ai-studio">GitHub</a> ·
  <a href="skills/skillto-ai-studio/SKILL.md"><kbd>20 Skills</kbd></a> ·
  <a href="apps/stass/README.md"><kbd>STASS MCP</kbd></a>
</p>

<p align="center"><a href="README.zh-CN.md"><kbd>简体中文</kbd></a> &nbsp; <kbd>English</kbd> &nbsp; <a href="README.ja.md"><kbd>日本語</kbd></a> &nbsp; <a href="README.de.md"><kbd>Deutsch</kbd></a></p>

## 复制安装提示词

复制下方整段到 Codex 或 Claude Code。GitHub 代码块右上角可一键复制。

```text
请从 https://github.com/skilltoAI/skillto-ai-studio 为当前客户端安装技能。先读取当前版本 apps/stass/work_catalog.json，只问一次“你日常需要处理哪些工作？（可多选）”，展示五类工作的名称和摘要。支持回复编号或类别名称，已经指定类别就直接采用。按用户选择执行 python scripts/install.py --agent 当前宿主 --groups "类别ID列表"，无需再次确认类别。完成后列出待配置项并给一个示例任务。
```

手动安装可运行 `python scripts/install.py --agent codex --groups`，输入如 `2、5`。Claude Code 改用 `--agent claude`。已有选择可用 `--augment --groups edit` 增补，`--dry-run` 只预览。显式 `--skill all` 安装完整技能集。启动器或 Web 设置中的 **安装新组件与技能** 可调整工作偏好、重新检测并复制加装提示词。WorkBody 支持提示词交接，安装接口待宿主验证。

## Overview

**Skillto.ai Studio is an AI-native personal workspace.** Describe what you want to achieve, and your agent selects the right Skills, works with your records through MCP, and leaves results you can review in knowledge bases, tables, scripts and storyboards. You can step in to edit the work, review it or decide what happens next.

Studio connects to the official Skillto.ai ecosystem. Bring available **AI assets, AI APIs and Skills** from the website into your workflow once the relevant services are connected and authorised. Keep the materials, decisions and deliverables for research, generation, editing and review together in one project. [Visit Skillto.ai](https://www.skillto.ai/)

## AI Art Assets

The Red-and-White Model Library brings motion-reference clips and their generation prompts together. Browse official topics or local collections, preview a clip, and copy its prompt for your own workflow. The screenshot shows a free official topic in the Studio workbench.

![Red-and-White Model Library with topic navigation, motion clips, and copyable prompts](docs/readme/assets/studio-red-white-model-library.png)

## Architecture

![Skillto.ai Studio architecture. Agents use Skills and Personal MCP to operate the local Personal Server and connect to the Skillto.ai platform separately.](docs/readme/assets/studio-architecture.svg)

Agents use Skills to choose a workflow and Personal MCP to act on the local workspace. The Personal Server stores project data. Authorised clients connect to Skillto.ai for cloud assets and generation.

## Who it is for

- **AI educators and paid-content creators** can research topics, break down reference videos, write teaching scripts, and review covers and storyboards.
- **Everyday AI users** can organise research, documents and tasks in knowledge bases, tables and reports, with space for human review notes.
- **AI creators** can manage characters, visual references, shots and motion templates while coordinating image generation, video generation and editing.

## Features

- **Skill orchestration.** One parent Skill routes tasks to 19 specialised Skills for research, media analysis, everyday work, storyboards, covers and reports.
- **A shared workspace for agents and people.** Supported agents read and update workspace records through STASS MCP. People can review and edit the same records in the browser.
- **AI-assisted editing and motion graphics.** Analyse reference clips, select segments and plan talking-head edits from rough cuts and subtitles with HyperFrames or Remotion. Organise templates and previews in Motion.
- **AI image and video generation.** Turn cover concepts, character references and shot plans into visual workflows. Creator MCP can bind assets, validate workflows, run authorised generation jobs and retrieve results. Available APIs, models and Skills depend on the website's offerings and your account permissions.

[Skill catalogue](#skill-catalogue) · [Host compatibility and dependencies](skills/skillto-ai-studio/references/compatibility.md)

## Screenshots

The two screenshots below are from the Windows launcher and Beam integration build. The default branch does not yet include that build or a downloadable Windows installer.

### Desktop workspace

The Windows launcher brings the personal server controls and a tour of the workbench into one window. Check whether the service is running, start or stop it, and open the workspace. Jump to the browser profiles, obtain a web pairing code, or launch 3D Screen Recording from the same window. The browser workspace brings together multimedia tables, tags, Motion templates, scripts and storyboards.

![Desktop workspace](docs/readme/assets/studio-desktop-workspace.png)

### 3D screen recording and editing

Open **3D Screen Recording** from the launcher to capture a product walkthrough, course or software demo. In the separate Beam editor, use the timeline to cut clips and add 2D zoom, 3D camera moves or a magnifier. Set the focus to follow the cursor or pick it manually, choose a perspective preset, and refine the result with captions and audio. The recorder can open while the STASS service is stopped.

![3D screen recording and editing](docs/readme/assets/studio-3d-recording.png)

The remaining screenshots show a running STASS workspace with fictional demo data.

**Motion template gallery with cover previews**

![Motion template gallery with cover previews](docs/readme/assets/studio-motion-gallery.png)

**Multimedia table with image thumbnails**

![Multimedia table with image thumbnails](docs/readme/assets/studio-media-table.png)

**Content planning table and review notes**

![Content planning table and review notes](docs/readme/assets/studio-tables.png)

**Script versions and line annotations**

![Script versions and line annotations](docs/readme/assets/studio-rewrite.png)

**Linked Motion storyboard in the script workspace**

![Linked Motion storyboard in the script workspace](docs/readme/assets/studio-storyboard.png)

## Quick start

Install Git, Python 3.10+ and your target client. Run these commands to preview and install the skills:

```sh
git clone https://github.com/skilltoAI/skillto-ai-studio.git
cd skillto-ai-studio
python scripts/install.py --list
python scripts/install.py --agent codex --groups
```

For Claude Code, use `--agent claude` in place of `--agent codex`. Restart the session and invoke `$skillto-ai-studio` in Codex or `/skillto-ai-studio` in Claude Code.

### Claude Code marketplace · 安装完整插件

Use this option in place of direct skill installation:

```sh
claude plugin marketplace add https://github.com/skilltoAI/skillto-ai-studio.git
claude plugin install skillto-ai-studio@skillto-ai-studio-marketplace
claude plugin list
```

Open a new session and invoke `/skillto-ai-studio:skillto-ai-studio`. See the [installation guide](skills/skillto-ai-studio/references/installation.md) for client-specific paths, upgrades, rollback and troubleshooting.

## Windows workspace

The first workbench builds target Windows x64. Use the Skills quick start on macOS. The native macOS workbench requires separate validation. The release page records asset checksums, signing status and tested paths.

The standalone STASS application and its MCP connections have separate setup steps. [GitHub Releases](https://github.com/skilltoAI/skillto-ai-studio/releases) currently has no Windows installer. To try the Windows x64 offline candidate, start from this GitHub branch:

```powershell
git clone --branch codex/stass-migration --single-branch https://github.com/skilltoAI/skillto-ai-studio.git
cd skillto-ai-studio
```

Follow the [offline build guide](apps/stass/README.md#构建离线-windows-x64-候选包) to build a package with the Go launcher, bundled Beam recording editor, WebView2 offline prerequisite, embedded Python, frontend and 20 skills. From the built package directory, run the installer with the build's SHA-256 digest for `release.json`:

```powershell
.\Install.ps1 -ManifestSha256 $manifestSha256
```

The default install location is `%LOCALAPPDATA%\Skillto.ai\Studio`. To test with an isolated instance, supply `-Root <new-directory> -Port <free-port>`. Host MCP registration, full installation and upgrade on another Windows machine, cross-machine data migration, and full rollback still require validation. [Windows installation audit](docs/WINDOWS-INSTALL-AUDIT.md)

## Skill catalogue

| Skill | What it does | Setup |
| --- | --- | --- |
| [skillto-ai-studio](skills/skillto-ai-studio/SKILL.md) | Parent entry point for task routing | [Guide](skills/skillto-ai-studio/references/installation.md) |
| [skillto-ai-studio-douyin-xhs-crawler](skills/skillto-ai-studio-douyin-xhs-crawler/SKILL.md) | Authorised Douyin and Xiaohongshu collection, account verification and recent metrics | [Guide](skills/skillto-ai-studio/references/child-setup.md#skillto-ai-studio-douyin-xhs-crawler) |
| [skillto-ai-studio-tiktok-crawler](skills/skillto-ai-studio-tiktok-crawler/SKILL.md) | Authorised TikTok collection, multilingual search and trend analysis | [Guide](skills/skillto-ai-studio/references/child-setup.md#skillto-ai-studio-tiktok-crawler) |
| [skillto-ai-studio-workbench](skills/skillto-ai-studio-workbench/SKILL.md) | Browser extension, clip selection and export, playback and notes | [Guide](skills/skillto-ai-studio/references/child-setup.md#skillto-ai-studio-workbench) |
| [skillto-ai-studio-table](skills/skillto-ai-studio-table/SKILL.md) | Multimedia tables, human review and semantic MCP tools | [Guide](skills/skillto-ai-studio/references/child-setup.md#skillto-ai-studio-table) |
| [skillto-ai-studio-reports](skills/skillto-ai-studio-reports/SKILL.md) | Local Metabase reports, charts, archiving and restore | [Guide](skills/skillto-ai-studio/references/child-setup.md#skillto-ai-studio-reports) |
| [skillto-ai-studio-style-library](skills/skillto-ai-studio-style-library/SKILL.md) | Visual style research and element-level motion planning | [Guide](skills/skillto-ai-studio/references/child-setup.md#skillto-ai-studio-style-library) |
| [skillto-ai-studio-assets](skills/skillto-ai-studio-assets/SKILL.md) | AI asset libraries, original prompts, inline public videos, prompt copying and video downloads | [Guide](skills/skillto-ai-studio/references/child-setup.md#skillto-ai-studio-assets) |
| [skillto-ai-studio-motion](skills/skillto-ai-studio-motion/SKILL.md) | Motion template catalogue, inspection, tags, ratings and supported renders | [Guide](skills/skillto-ai-studio/references/child-setup.md#skillto-ai-studio-motion) |
| [skillto-ai-studio-rewrite](skills/skillto-ai-studio-rewrite/SKILL.md) | Source research, transcripts, script versions and human review | [Guide](skills/skillto-ai-studio/references/child-setup.md#skillto-ai-studio-rewrite) |
| [skillto-ai-studio-qwen38-media-analysis](skills/skillto-ai-studio-qwen38-media-analysis/SKILL.md) | Qwen3.8 media analysis, OCR, keyframes and shots | [Guide](skills/skillto-ai-studio/references/child-setup.md#skillto-ai-studio-qwen38-media-analysis) |
| [skillto-ai-studio-talking-head-edit](skills/skillto-ai-studio-talking-head-edit/SKILL.md) | HyperFrames planning and Remotion editing from rough cuts and timed subtitles | [Guide](skills/skillto-ai-studio/references/child-setup.md#skillto-ai-studio-talking-head-edit) |
| [skillto-ai-studio-explainer-storyboard](skills/skillto-ai-studio-explainer-storyboard/SKILL.md) | Evidence, beats, visual planning and storyboards for explainers | [Guide](skills/skillto-ai-studio/references/child-setup.md#skillto-ai-studio-explainer-storyboard) |
| [skillto-ai-studio-xiaoyu-cover](skills/skillto-ai-studio-xiaoyu-cover/SKILL.md) | Branded Xiaoyu covers for videos, tutorials and courses | [Guide](skills/skillto-ai-studio/references/child-setup.md#skillto-ai-studio-xiaoyu-cover) |
| [skillto-ai-studio-workflow-mcp](skills/skillto-ai-studio-workflow-mcp/SKILL.md) | Visual workflow editing, asset binding and execution via Creator MCP | [Guide](skills/skillto-ai-studio/references/child-setup.md#skillto-ai-studio-workflow-mcp) |
| [skillto-ai-studio-character-card](skills/skillto-ai-studio-character-card/SKILL.md) | Prompts and reference checks for character portraits and multi-view sheets | [Guide](skills/skillto-ai-studio/references/child-setup.md#skillto-ai-studio-character-card) |
| [skillto-ai-studio-depth-gray-replica](skills/skillto-ai-studio-depth-gray-replica/SKILL.md) | Authorised source collection, cut verification and timed breakdown | [Guide](skills/skillto-ai-studio/references/child-setup.md#skillto-ai-studio-depth-gray-replica) |
| [skillto-ai-studio-depth-gray-workflow](skills/skillto-ai-studio-depth-gray-workflow/SKILL.md) | Depth video, audio, shot references and editable SaaS workflows | [Guide](skills/skillto-ai-studio/references/child-setup.md#skillto-ai-studio-depth-gray-workflow) |
| [skillto-ai-studio-h3-workflow](skills/skillto-ai-studio-h3-workflow/SKILL.md) | Source-driven H3 character workflows with costume and prop references | [Guide](skills/skillto-ai-studio/references/child-setup.md#skillto-ai-studio-h3-workflow) |
| [skillto-ai-studio-ip-store](skills/skillto-ai-studio-ip-store/SKILL.md) | Character, setting and reference libraries across videos | [Guide](skills/skillto-ai-studio/references/child-setup.md#skillto-ai-studio-ip-store) |

## Contributing

```sh
python scripts/validate_repo.py
python -m unittest discover -s tests -v
git diff --check
```

See the [contribution and publishing rules](CONTRIBUTING.md), [technical standards](技术规范.md) and [distribution notes](docs/DISTRIBUTION.md). The repository has no project-wide open-source licence. Third-party components and brand assets remain subject to their own terms.
