---
name: skillto-int-workflow-mcp
description: Create, inspect, edit, validate, archive, and run SkillTo.ai visual workflows through Creator MCP, including node prompts, model options, media inputs, and result retrieval.
---

# SkillTo.ai Workflow MCP

Use this child of `skillto-int` for general SaaS visual Workflow CRUD and execution. The workflow on SkillTo.ai is authoritative; the local Agent proposes edits and displays results. For a complete short-video URL to depth-gray workflow, use `skillto-int-depth-gray-workflow`, which calls this skill for SaaS CRUD and runs; use `skillto-int-depth-gray-replica` for acquisition and analysis alone. This skill does not perform that analysis itself.

## Connect and discover

- Use the `workflow` toolset of `@skilltoai/creator-mcp`, either as a remote Streamable HTTP MCP client or through its local stdio bridge. Production endpoint: `https://skillto.ai/api/skillto-v2/creator-mcp`. Keep the `skap_` API Key in the client's secure configuration, never in prompts, graph snapshots, logs, or the skill repository. Use `workflow:read` to inspect, `workflow:write` to edit, `asset:write` to upload, and `workflow:run` to run. The Key's allowed FMS UUIDs and single-run and Shanghai-day precharge budgets are configured on `/account/creator/api-keys`.
- Discover the enabled tools and their current schemas before constructing calls. The Go MCP service owns authorization, material ownership, graph validation, pricing, reservation, settlement, and idempotency. Do not call private REST, billing, provider, channel, or adapter APIs.
- Keep a small toolset in the Agent context: use draft tools for editing, asset tools only when uploading, and run tools only when executing. The host need not send a full graph when changing one node.

## Create and maintain a workflow

1. `workflow_list_drafts` or `workflow_get_draft` identifies an owned source. Creation currently uses `workflow_clone_draft` with a new stable workflow UUID; there is no standalone `workflow_create_draft` MCP tool. Preserve the returned `draftRevision`. The canvas at `https://www.skillto.ai/drawing-workflow?wid=<workflow_uuid>` visualizes the same server draft.
2. Use `workflow_list_models` and `workflow_get_node_options` for every node type and selected FMS UUID. Use their exact enum values, numeric bounds, prompt length and reference rules. Never invent editable fields or persist provider/channel/adapter IDs. Retain all parameters exposed in the SaaS editor; omit internal fields from Agent-facing edits.
3. Use `workflow_patch_node` for a node's prompt, model, parameters, or material binding. Use `workflow_save_draft` for node/edge changes and function input/output contracts. Submit the last `draft_revision`; on conflict re-read and reconcile rather than overwrite. New cross-entity references use stable UUIDs. Validate with `workflow_validate_draft`, then verify the browser canvas.
4. Upload a local image/video/audio via the bridge's `asset_upload_local_file`, or the MCP `asset_begin_upload` → `asset_append_upload` → `asset_get_upload` → `asset_finish_upload` sequence. Bind only the returned owned material UUID. Never put a local file path or a temporary `material:` placeholder into a server graph. Check that the bound material resolves before running.
5. `workflow_archive_draft` is the supported delete-like operation for an unpublished draft; do not assume a hard-delete tool exists. Ask before archiving when the user has not requested removal.

## Run and return the result

1. Call `workflow_prepare_run` using the current workflow UUID, revision, explicit function `inputs`, and optional target node UUID/port list. No targets means the whole graph; targets mean each target and its upstream closure. Show missing inputs and estimated precharge before a chargeable run. Do not infer permission for a real paid run from a configured budget alone.
2. After authorization, call `workflow_start_run` with a stable `request_uuid` and unchanged arguments on retries. For a new request or changed inputs, use a new UUID. Query `workflow_get_run` until terminal; `workflow_list_runs` can recover a lost response, and `workflow_cancel_run` cancels a cancellable run.
3. Report the actual final text or owned image/video material and a usable preview when returned. An accepted run is not a completed result. If the host cannot display the media, provide the workflow URL and result URL or material UUID and say what retrieval failed. Do not synthesize a result or treat a source image as the output.

The browser controls image/video preview size and layout; this Skill does not encode UI geometry into workflow parameters. Preserve local examples and assets outside the skill installation.
