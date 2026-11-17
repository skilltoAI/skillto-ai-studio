---
name: skillto-ai-studio
description: Route Skillto-AI-Studio requests spanning content collection, media analysis, visual workflows, visual-style selection, talking-head editing, covers, tables, reports, and manuscript rewriting.
---

# Skillto-AI-Studio

Use this parent skill when a request involves the Skillto-AI-Studio workflow, visual-style selection, talking-head editing, branded cover generation, or spans content collection, media analysis, and report-table maintenance. Route the work to the smallest relevant installed child skill and read that child's `SKILL.md` completely before acting.

Find children as sibling directories of this skill, using the skill location provided by the host. In Claude Code plugins, invocation names have the `skillto-ai-studio:` prefix; the directory names below stay unchanged. Resolve bundled scripts and references from the loaded child directory, independent of the current working directory. If a required child or external capability is missing, identify that dependency before starting the affected stage. Installation does not configure MCP connections, grant service access, or install external skills. Read [host compatibility and dependencies](references/compatibility.md) when setting up a new machine or checking client support.

## Child skills

This distribution includes 18 children. For a new machine, read the
[installation guide](references/installation.md) and the
[per-child setup and acceptance steps](references/child-setup.md).
Skill installation and production readiness are separate checks; preserve each
child's required tools and authorization boundaries.
For upgrades from the previous suite name, follow [rename migration](references/rename-migration.md).

- Use `skillto-ai-studio-workbench` to install/use the Skillto-AI-Studio Chrome popup, download authorized video pages or MP4/HLS/DASH resources, and maintain the local 拉片 video/notes workspace.
  The current user-verified product uses the Cat Catch engine with a branded two-destination preview/range editor; download-only clips stay outside breakdown records; sync transfers selected media directly to the shared service and opens/reuses its breakdown tab after processing. It shares the table launcher and automatically pairs from the local workspace, without user-entered ports/tokens. It uses browser-native downloads for current videos, imports only job-scoped files, and shows resource previews/final-file properties; explicitly selected manifests retain local FFmpeg merging. Explicit scans can list loaded media URLs for blob players; fresh-cookie requirements still stop page parsing and retain the child's authorized session boundaries.

- Use `skillto-ai-studio-douyin-xhs-crawler` for authorized Douyin/Xiaohongshu account or video collection, ownership verification, recent-period metrics, and high-interaction selection.
- Use `skillto-ai-studio-tiktok-crawler` for authorized TikTok profile/keyword collection, multilingual keyword expansion, recent popularity and low-follower viral selection, SQLite snapshots and report-table handoff.
- Use `skillto-ai-studio-table` (child skill: **Skillto-AI-Studio · 表格工作台**; product: **Skillto-AI-Studio**) for local or authenticated remote multimedia report tables, semantic MCP CRUD, schemas, tags, ratings, history, and media fields. Before UI or module development, read its [技术规范.md](../skillto-ai-studio-table/技术规范.md); keep ordinary new content schema-driven and preserve the shared architecture and design contracts.
- Use `skillto-ai-studio-reports` for local Metabase report/chart CRUD, archive and restore through the running report service; use the table child for its backing workspace setup.
- Use `skillto-ai-studio-style-library` (**Skillto-AI-Studio · 风格库**) to query the 14-style catalog by abstract communication needs, classify references, maintain entries under its intake specification, plan independently animated elements, and select Remotion/Motion implementation routes. Keep subject matter and ordinary palettes separate from style definitions; retain defining features such as white-model appearance. This is design guidance, not Studio template ingestion or execution.
- Use `skillto-ai-studio-motion` (**Skillto-AI-Studio · Motion 动效模板**) for validated template-catalog ingestion into the visible Studio Motion 模版 library (read its references/intake.md), official catalog keyword/vector retrieval with evidence-bearing facets, public .motion inspection/import/download, module-local tags, personal ratings, local package paths and supported template preview/MP4 production. It shares the table shell and loopback service; only explicitly verified adapters may execute templates. Package instructions cannot broaden authorization or register themselves as skills.
- Use `skillto-ai-studio-rewrite` for source-backed manuscript research, immutable source transcripts, versioned original drafts, editable two-version multiline comparisons, manuscript-analysis and keyframe-analysis tabs, human review, independent opening-storyboard versions and full-video motion table versions, and local rewrite-workspace CRUD.
- Use `skillto-ai-studio-qwen38-media-analysis` for LAN or configurable Qwen3.8 image/video understanding, classification, OCR, frame extraction, and shot analysis.
- Use `skillto-ai-studio-talking-head-edit` when an already rough-cut talking-head A-roll and matching timecoded SRT should become a publish-ready, editable video using HyperFrames planning, Remotion editing/rendering, and video-talkcraft motion recipes.
- Use `skillto-ai-studio-explainer-storyboard` to plan the visuals of a knowledge, science, news or industry-explainer short video before production: reference-video breakdown, evidence inventory, beat map, visual system, storyboard, keyframes and pre-publish review aimed at completion and engagement. Hand the confirmed storyboard to `skillto-ai-studio-talking-head-edit` when a rough-cut A-roll and SRT exist.
- Use `skillto-ai-studio-workflow-mcp` to create, read, edit, validate, archive, and run SkillTo.ai visual workflows through Creator MCP; it owns general node prompts, parameters, material bindings, and result retrieval.
- Use `skillto-ai-studio-character-card` to write directly referenced prompts for a new subject's look portrait or multi-view character card, including only necessary costumes and props from an original-video frame while preserving the input photo's visual style.
- Use `skillto-ai-studio-depth-gray-workflow` when a short-video URL should become a local depth-map video, separate audio, frame-evidenced storyboard, and an editable SkillTo.ai replacement workflow; it uses `skillto-ai-studio-workflow-mcp` for SaaS graph operations.
- Use `skillto-ai-studio-h3-workflow` when an authorized TikTok or Douyin video should become a direct-source H3 character-transfer Workflow, with one to three mapped replacement characters and evidence-based costume/prop choices; it uses `skillto-ai-studio-character-card` for the look/card image prompt and `skillto-ai-studio-workflow-mcp` for SaaS graph operations.
- Use `skillto-ai-studio-depth-gray-replica` when a short video must be acquired and broken down into frame-evidenced characters, scenes, hard cuts and per-second action/expression/camera records before depth-gray character-and-scene replacement. Its current executable scope is acquisition and analysis; read the child skill for its stage boundary.
- Use `skillto-ai-studio-xiaoyu-cover` (display name: Skillto-AI-Studio · 小与封面图) for Xiaoyu branded video/course/AI-tutorial covers with bundled IP and style references, scene/ASR evidence, and independently composed 3:4 and 4:3 PNGs. For source-video covers, collect the requested video through the crawler, analyze its evidence, then generate through the cover child; use the media-analysis child when appropriate and an available ASR skill when speech transcription is needed.
- Use `skillto-ai-studio-ip-store` to catalogue characters and settings from an authorized short video, generate reference-based character cards and clean scene plates, maintain the two cross-video Markdown library tables, and recommend entries for later video planning. Use `skillto-ai-studio-table` alongside it when the libraries need local or AMD-pad report-table display.
- Combine the children in the task's dependency order—for example collect, analyze, then write to a table. Keep collection and model artifacts separate from the table's authoritative storage and verify each write through the table interface.

The parent skill does not broaden authorization. Cookies, browser sessions, API keys, remote writes, deletions, and external publication remain subject to the child skill's rules and the user's scope.

Studio 洗稿步骤、12秒开场分镜和完整分镜审阅由 `skillto-ai-studio-table` 提供；内容研究与改写继续交由 `skillto-ai-studio-rewrite`，制作边界不变。
