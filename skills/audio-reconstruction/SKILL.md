---
name: av3d-audio-reconstruction
description: Run and debug the AV3D semantic-to-visual-asset, source peel, physics fitting and rerender loop with auditable artifacts.
---

Use the repository root two levels above this directory. Read AGENTS.md and
[contracts](../../docs/contracts.md) before changing a stage.

1. Inspect semantic.json, asset trajectories and the selected original-clock interval.
2. Caption with Gemini or import its saved answer. Propose *all* compatible visual
   assets, including alternatives; semantic plausibility never establishes identity.
3. Peel with SAM Audio. Preserve original stereo input, official processor downmix,
   gain min(32,.9/peak), seed0, one candidate, inverse-restored FLOAT outputs. Review
   both target and residual. Crops must include context and retain explicit offsets.
4. `harness.py init`, `propose`; inspect candidates/pool.json and parameter bounds.
5. Validate continuous geometry before live rendering. Use actual SoundSpaces or
   explicitly recorded IR replay. Changed materials need actual new IR queries.
6. `fit` compares the same raw stereo interval, records all alternatives and selects
   via channel-energy error + ILD error. Fit one source gain shared by both ears/time.
7. `label` saves a validation-gated candidate. `build_demo.py` presents actual results.
8. Replay new listening routes with the fitted source/material/gain held constant.

Current demo uses a reviewed residual after rustle removal as a speech layer. It still
contains room background. Do not rebrand this as a clean/dry isolated source.
Optional SceneBind integration is a future provider; default operation does not need it.
Stop on exhausted budget or invalid evidence; preserve failures, do not force a winner.
