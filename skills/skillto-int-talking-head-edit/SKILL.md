---
name: skillto-int-talking-head-edit
description: Turn rough-cut 口播 A-roll, timecoded SRT, and optional B-roll into a publish-ready, editable video with HyperFrames planning, Remotion editing/rendering, and video-talkcraft motion recipes.
---

# Talking-head edit workflow

Use this workflow when the user supplies an already rough-cut A-roll and a matching timecoded SRT, with optional B-roll or other visual assets. Keep the rough cut and SRT as the timing source of truth. The output is a finished video plus an editable Remotion project.

## Tool roles

- Read `hyperframes` and its relevant creative guidance for visual planning. Use HyperFrames to develop the visual concept, shot list, and final storyboard. In this workflow, Remotion owns the editable timeline and final render.
- Read `remotion-best-practices` and the relevant Remotion skills for captions, composition, preview, and render. Use Remotion Agent Skills for SRT-aligned subtitles, basic packaging, timeline, editable workbench, and export.
- Read `video-talkcraft` when a shot needs a complex motion effect. Find a matching recipe and inspect its actual source and dependencies before adapting it into the Remotion project. Record the recipe used. Do not substitute an approximate effect merely because its name sounds similar.

The supplied A-roll and SRT replace video-talkcraft's script-to-voiceover, voice trimming, and ASR stages. Do not re-trim the user's pauses, regenerate timing, or alter the rough cut unless the user asks. If the SRT and video disagree, identify the affected intervals and resolve them before building timed overlays.

## Production gates

1. Inspect the A-roll, SRT, and supplied assets. Verify duration, frame rate, aspect ratio, SRT coverage, and which B-roll is relevant. Preserve the source files.
2. Build a storyboard on the SRT timeline before implementation. For each shot, give the SRT start/end, spoken idea, main picture, exact asset path or A-roll fallback, captions/text, motion recipe or basic treatment, and sound treatment. Use HyperFrames for visual planning and the final shot design.
3. Present the storyboard for the user's confirmation. Do not proceed to full production until the storyboard is confirmed.
4. Build representative keyframes and a short preview in Remotion. Show the actual proposed type, layout, caption treatment, and complex motion before asking the user to confirm the look. Do not proceed to full production until the keyframes/style are confirmed.
5. Implement the confirmed storyboard in Remotion. Align captions and motion strictly to the SRT timebase. Use video-talkcraft's real recipe source for selected complex effects. When a B-roll asset does not match the spoken point or timing, keep A-roll visible and record the omission; never force the asset into the cut.
6. Render and inspect the finished video. Check caption timing, legibility, safe areas, asset correspondence, audio continuity, and representative transitions. Deliver the final MP4, editable Remotion project/workbench, final SRT, and a shot-to-asset map; summarize any remaining QA issues.

## Default sound rule

Do not add background music by default. Retain the A-roll's speech and intentional room tone. Add BGM only when the user explicitly requests it. Use sound effects only when they serve a confirmed shot and do not mask speech.

## Source projects

- HyperFrames: https://github.com/heygen-com/hyperframes
- Remotion: https://github.com/remotion-dev/remotion
- video-talkcraft: https://github.com/Vincentwei1021/video-talkcraft
