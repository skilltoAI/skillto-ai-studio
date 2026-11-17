# Repository instructions

`skills/` is the source of truth. Keep the parent `skills/skillto-int/SKILL.md`
in sync with the child capabilities. Preserve each child's authorization and
production boundaries. Do not silently replace required external tools.

Keep skills as sibling folders with matching `name` frontmatter. Use relative
paths for bundled resources; resolve scripts from the loaded skill directory,
not a hard-coded Codex or Claude installation. Host-specific MCP/tool names are
capabilities to discover, not a promise that another client provides them.

Read `CONTRIBUTING.md` for validation and Git conventions. Do not commit runtime
state, credentials, collected media, research outputs, or local executables.
Do not overwrite unrelated existing changes. Publication and Git pushes require
an explicit user request; local preparation is allowed.

Do not synchronize all installed skills automatically. If a task includes updating
an installed copy, compare it with the repository and copy only the intended files.
