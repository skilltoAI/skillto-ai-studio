# Client compatibility and dependencies

All folders use the Agent Skills `SKILL.md` format. Current Codex uses
`~/.agents/skills/` or project `.agents/skills/`; the installer retains explicit
`--codex-legacy` support for `$CODEX_HOME/skills` / `~/.codex/skills` deployments.
Claude Code uses `~/.claude/skills/`, project `.claude/skills/`, or
the plugin's `skills/` directory. In a Claude plugin, invoke the parent as
`/skillto-ai-studio:skillto-ai-studio`; direct installation uses `/skillto-ai-studio`. Codex uses
`$skillto-ai-studio`. The children remain siblings in every mode.

Resolve `<skill-root>` below to the actual loaded child directory. Examples
that mention `.codex/skills` show a Codex installation, not a required location.
Codex `agents/openai.yaml` UI metadata is optional and may be ignored by Claude.
Do not add a second copy of the same suite through another installation method.

Read the [installation guide](installation.md), [rename migration](rename-migration.md), and [18 per-child setup recipes](child-setup.md)
before deploying. The latter separates independent capabilities from maintainer-only deployments.

## Shared STASS and legacy table mode

For the installed Windows STASS workbench, check
`http://127.0.0.1:8080/STASS/health` (using the configured port if customized)
and verify the running version. Connect Claude Code to that instance with its
own paired MCP profile. The separate standalone table script and legacy 8880
web service apply only to explicitly selected legacy deployments.

## Capability requirements

| Child | Additional requirements and limits |
| --- | --- |
| `skillto-ai-studio-style-library` | Offline Markdown lookup of 14 styles needs no service, runtime or MCP. Implementation guidance lists optional Remotion, Motion, SVG and Three.js routes; consult the project's actual versions and discover installed tools before production. Referenced projects are not bundled or claimed to have been runtime-tested. Studio template CRUD and execution remain with `skillto-ai-studio-motion`. |
| `skillto-ai-studio-character-card` | Prompt authoring itself needs no generation backend. Editing a SaaS node requires Creator MCP and its current node schema. |
| `skillto-ai-studio-douyin-xhs-crawler` | Python, Playwright, installed supported browser, explicitly selected authorized session. Cookie paths can be provided with `--cookies` or `DOUYIN_COOKIE_FILE`; follow its cookie setup reference. |
| `skillto-ai-studio-tiktok-crawler` | Python, its `scripts/requirements.txt`, supported browser and separately configured authorized TikTok session. Analysis modules can run independently of collection. |
| `skillto-ai-studio-workbench` | Current product overlays a branded two-destination preview/range editor on the user-verified Cat Catch engine (GPL attribution retained). Requires explicitly selected upstream source, Chrome, and local FFmpeg for ordinary MP4/WebM clip exports. Browser-only clips use a separate export store; workbench sync transfers media bytes to the shared service, writes processed breakdown records, then opens/reuses the workspace tab. Automatic pairing, no user-entered port/token. Earlier experimental client retained separately. |
| `skillto-ai-studio-table` | Installed STASS uses its paired MCP and shared data root. The legacy standalone stdio core needs Python and an explicitly selected data root. Its optional HTTP deployment requires external `douyin_tracker.review_web` and research resources. |
| `skillto-ai-studio-assets` | Running STASS with the discovered AI asset MCP capability; current tool is `ai_assets_action`. Public Feishu playback needs Playwright plus Chromium or Chrome, a fresh anonymous context and network access to Feishu. Videos are streamed without service-side caching; public permissions may change. No user profile, paid generation or template execution is authorized by intake. |
| `skillto-ai-studio-motion` | Running Studio HTTP service for library and queued tasks. Package inspection uses Python standard library. The pinned public Kinetic Tech adapter needs Python 3.11+, declared scientific/audio packages, Node.js 22+, Chrome, full FFmpeg and ffprobe. Personal envelopes and unknown renderers remain inspection-only. No credential migration or source-run-count fabrication. |
| `skillto-ai-studio-reports` | Installed STASS exposes the report module and uses separately configured Metabase and PostgreSQL. Port 8880 and the table child’s reporting README apply to the legacy deployment. |
| `skillto-ai-studio-rewrite` | Running table HTTP service for manuscript CRUD. Speech sources need ASR/OCR. The voice button requires the external `xiaoyu-voice` deployment; its documented Windows paths are maintainer-specific. |
| `skillto-ai-studio-qwen38-media-analysis` | Bundled client targets the maintainer's LAN endpoint `192.168.3.188:8080`. Credentials use `QWEN38_API_KEY`. Endpoint/model are embedded deployment constants, not CLI overrides. External machines must adapt the deployment explicitly. Frame extraction uses FFmpeg/ffprobe or OpenCV fallback. |
| `skillto-ai-studio-workflow-mcp` | Connect `@skilltoai/creator-mcp` via the child's documented remote endpoint or stdio bridge; use a protected API key with the needed scopes. Discover tools in the active host. |
| `skillto-ai-studio-depth-gray-replica` | Authorized platform collection, FFmpeg, frame inspection; optional `scrapling`/`scrapling-stream` for supported acquisition. Its executable boundary is acquisition and analysis. |
| `skillto-ai-studio-depth-gray-workflow` | Collection/analysis dependencies, external `make-expression-depth-video` skill and working depth backend, FFmpeg, Creator MCP. Missing depth backend blocks depth production. |
| `skillto-ai-studio-h3-workflow` | Platform collection, frame analysis, character-card child, Creator MCP and an available H3 model. Paid execution retains the child's authorization boundary. |
| `skillto-ai-studio-ip-store` | The required external `scrapling` workflow, authorized video, FFmpeg/frame analysis and the specified `image_gen` reference-based image capability. Plain Claude Code does not supply `image_gen`. Table child is optional for report-table display. |
| `skillto-ai-studio-talking-head-edit` | External `hyperframes`, relevant Remotion skills and runtime, and `video-talkcraft` recipes. Preserve its storyboard/style confirmation gates. |
| `skillto-ai-studio-explainer-storyboard` | Planning and review need no external service. Reference breakdown needs frame extraction (FFmpeg/OpenCV) and optional vision analysis. Keyframes need a renderer or image tool available in the host; say which one produced them. Production is handed to `skillto-ai-studio-talking-head-edit` or another generation workflow. |
| `skillto-ai-studio-xiaoyu-cover` | The specified `imagegen` skill and `image_gen` capability are not supplied by this repository. A plain Claude Code installation does not provide them. Video mode additionally needs collection, FFmpeg/OpenCV/Pillow and ASR as applicable. Brand references are bundled; authorization to reuse the brand is separate. |

These are installation and capability boundaries, not automatic authorization
for collection, paid generation, remote mutation, or publication. Use each
child's detailed setup references only for the selected task. If a required
tool exists only in another host, report the missing capability; do not claim
that loading the skill made the tool available.

## Host documentation

- [Codex skill locations](https://developers.openai.com/codex/skills/)
- [Agent Skills format](https://agentskills.io/specification)
- [Claude Code skill locations and invocation](https://code.claude.com/docs/en/skills)
- [Claude Code plugin layout](https://code.claude.com/docs/en/plugins-reference)
- [Claude Code marketplaces](https://code.claude.com/docs/en/plugin-marketplaces)
