# Operate AV3D-Harness

Read README.md, skills/audio-reconstruction/SKILL.md and docs/contracts.md first.
Keep reusable functions in lib/, CLIs in scripts/, profiles in configs/, operational
instructions in skills/, and immutable artifacts in runs/. No parent repository is
required. Never import an unreleased perception runtime to make default commands work.

Default: Gemini semantics → compatible visual assets → bounded location/material/gain
pool → real SoundSpaces or verified saved IR replay → energy/ILD evaluation → candidate
label. Read machine-readable manifest, candidate pool, evaluation and receipts before
choosing the next action. Make one attributable change or a declared bounded grid.

Start with dry-run tool commands. API calls require --execute; no automatic retry.
Secrets only through environment variables; never write them to prompts or receipts.
Fresh inputs/config mean a fresh run. Preserve failed outputs. Do not overwrite a stage.
Keep original stereo untouched; no hidden per-ear gain, normalization, GT mixing,
time stretch, invented spatial rays or surrogate RIR presented as physics.

Report PASS_EXECUTION separately from quality. A quiet residual, caption, low energy
error or a stopped search does not certify clean separation, source identity or physical
recovery. Labels remain CANDIDATE_REQUIRES_VALIDATION; never claim training occurred.

Run `python -m unittest discover -s tests -v` for core changes. Validate actual media,
all chapter sources, and full MP4 decoding for film edits. Record observed commands,
versions, outputs and limits in the run receipt. Never publish or push implicitly.
