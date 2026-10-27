# What was tested

Release validation, October 26, 2026. Execution success is separate from source
quality, physical calibration and held-out generalization.

| Check | Result | Scope |
|---|---|---|
| Core signal and proposal tests | PASS, 5 tests | Identity, gain, ear swap, invalid signals, compatible assets, actual IR convolution |
| Independent-directory replay | PASS | Fresh init → propose → fit → label → 10 IR position checks → three decoded route MP4s |
| Separation | PASS execution | Fresh cached-model GPU run; reviewed residual remains a wet speech proxy |
| Semantic provider | PASS execution | Fresh response and normalization before the no-API restriction |
| Three final listener routes | PASS execution | Fresh visual replay and actual acoustic IR queries on existing simulator environments |
| Static GLB importer | PASS packaging | Synthetic mesh, preserved bounds and bundle hashes; engine loading not tested for this new adapter |
| Astra scene reconstruction | NOT RUN | Upstream references only; no paid test |
| Virgin-machine GPU installation | NOT RUN | Existing GPU/model/native environments were reused |
| Perception self-training | NOT IMPLEMENTED | Exported labels require independent validation |

The independent-directory replay had its own source tree and supplied input pack;
it did not import the parent research repository. It reused installed Python
dependencies and saved real IR/RGB artifacts. The full candidate/material grid was
not re-rendered: the demo compares four saved combinations and marks two missing
combinations as not run. The three final counterfactual routes were rendered afresh.

Reproduce the CPU check from the repository root:

```bash
python -m unittest discover -s tests -v
python scripts/smoke_replay.py --inputs inputs/corey --run runs/smoke
```

Input recordings, scene assets and model weights are not included. See
[setup](setup.md) and [reproduction](reproduce.md). No API credentials are shipped;
provide your own only when intentionally running a live semantic request.

## Final film

PASS: 1920×1080, 30 fps, H.264/AAC stereo, 71.57 seconds. Full output decoding
completed without errors. All 18 ear/chapter comparisons passed the 0.9 source
correlation threshold (minimum 0.9623). This checks source identity in each audible
chapter with a ±0.8s search, not frame-exact synchronization certification.
Candidate, three-route and end-credit frames were inspected from the exported MP4.
All candidate avatars and the semantic target appear together during a 5.7s chapter.

The WebM-to-MP4 conversion emitted an Opus packet-header warning; the resulting MP4
fully decodes and passes the audio checks above. See [audio audit](video-audit.json).
Three standalone route outputs each decode successfully and contain 3.2 seconds of
1080×1080 H.264 video and 48kHz stereo AAC audio.

Latest revision: silent original-footage opening (first 3.8 seconds verified at zero
audio peak), 4-second Fit-to-GT explanation, explicit target/physics testing and
auto-adjustment labels. Updated MP4 and ear/chapter audit both pass.

Title-overlay revision: the 4-second silent original-footage introduction includes
the project title, core capabilities and “From videos in the wild.” The exported
intro frame was inspected; full decode and all 18 ear/chapter checks pass.
