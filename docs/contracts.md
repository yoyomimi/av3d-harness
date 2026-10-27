# Artifacts are the interface

All time values are original-recording seconds. Audio is 48kHz FLOAT; reference and
render are stereo [samples,2]. A mono source is duplicated *without* a -3dB downmix
matrix for the fit input. Live SoundSpaces consumes the original mono file. World
coordinates are meters, +Y up; camera/listener poses and assets must share that frame.

| Artifact | Required fields / meaning |
|---|---|
| semantic.json | provider, answer_sha256, event {category,start_s,end_s,caption,role}; identity can be unknown |
| assets.json | assets [{id,number,kind,sound_categories,trajectory:[{time_s,position_m, optional velocity_m_s}]}] |
| candidates/pool.json | all compatible assets, parameter_pool, provenance/policy |
| renders.json | candidates [{id,candidate,absorption,rir}], routes [{id,candidate,absorption,rir}]; paths relative to this file |
| RIR folder | receipt.json, ir_manifest.json, irs/*.npz; stereo `ir` array; actual query times/positions |
| manifest.json | immutable input hashes, config, runtime input directory |
| fit/evaluation.json | selected candidate, every alternative, all diagnostics, IR hashes, gain and output WAV hashes |
| candidate-label.json | candidate trajectory, fit hash, unresolved gates, NOT TRAINED |

**Proposal provider:** consumes semantics and visual geometry; returns hypotheses.
The built-in provider performs deterministic sound-category/class compatibility.
It does not claim Gemini estimated metric coordinates: coordinates come from assets.
Offscreen/unknown sources need an explicit extra hypothesis, not an invented object.

**Evaluation provider:** `lib.pipeline.metrics(reference, rendered)` returns named
metrics. `fit()` currently minimizes `channel_energy_mae_db + ild_mae_db`. Both terms
are dB; weights are equal and fixed before ranking. Global gain is RMS-fit within
[.25,4], shared by ears and time. Report energy/ILD separately; spectrum and ITD are
additional diagnostics only. ILD compares 250ms windows, not source direction GT.
No valid windows or near-empty audio is a failure, not a perfect match.

**Future perception provider:** may return timestamped semantic hypotheses and
head-relative direction/trajectory candidates with uncertainty. Convert each using
its own timestamp's head pose; preserve missing support. A future SceneBind evaluator
may be substituted behind the metric boundary and versioned objective, but is NOT
implemented or required in this release. No dependency, weights or mock predictions.

**Signal meanings:** SAM target + generated residual need not equal its input.
Render-minus-reference residual includes phase/room/timing errors. Neither is automatically
ambient audio or a new source. The demo's speech proxy remains wet and contains background.

**Search completeness:** the cached demo has three assets at absorption .8 plus asset03
at .1. Two combinations are NOT RUN; this is a bounded replay, not an exhaustive search.
`render_pool.py` can dispatch the full requested Cartesian pool on a configured engine.
The final three route renders have no GT; reuse fitted emission strength unchanged.

**Acceptance:** execution success, fitting-reference agreement, physical validation,
and held-out post-training improvement are four separate things. Only the first two
are demonstrated here. Generated labels are candidates until independently validated.
