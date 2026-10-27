# Reproduce the scene, not just the screenshot

## Environments

The CPU path needs Python3.10+, NumPy/SciPy, FFmpeg and the supplied input artifacts.
`requirements.txt` is the portable replay environment. Live SAM needs a separately
installed official SAM Audio environment and cached weights. Visual replay was run
with Habitat-Sim0.3.3; live audio used an audio-enabled0.2.2 build with the material
patch in `native/`. These are separate environments, not a single pip install.

Validation included a fresh semantic call and separation run before the later no-API restriction,
an independent-directory CPU replay with supplied artifacts, and fresh visual/acoustic
renders for all three final listener routes on existing GPU environments. The fitting
pool itself uses saved actual IRs. No Astra reconstruction was tested. This is not a
from-zero GPU/native installation test. See [validation scope](validation.md).

## Prepare an input pack

```text
inputs/corey/
  original.wav              full original stereo, 48k FLOAT
  source-stereo.wav         reviewed mono proxy duplicated identically to L/R
  semantic.json             selected Gemini event, original-clock timestamps
  assets.json               visual asset classes and world trajectories
  renders.json              actual cached RIR pool, paths relative to this file
  irs/<candidate>/          receipt.json, ir_manifest.json, irs/*.npz
  visual.json               optional synchronized film geometry/camera metadata
  video-*.mp4, *.glb        optional visual media referenced by visual.json
```

See [contracts.md](contracts.md) for fields. All source/reference WAVs keep the full
recording clock. Put a crop back at its original sample offset with zeros elsewhere;
do not silently start a .6s crop at0s. When duplicating mono, use identical samples
in each ear rather than FFmpeg's default stereo upmix matrix.

For the existing local research workspace only, this one-time migration is available:

```bash
python scripts/import_local_demo.py --workspace /path/to/scenebind_prototype \
  --output inputs/corey
```

It copies visual assets and saved Gemini/SAM evidence, derives the candidate asset
catalog, and discards previous learned-direction proposals. It does not ship the input
dataset or fetch remote files. Supply the matching IR folders listed in renders.json
from your authorized artifact archive. The runtime thereafter needs only this repo
and the pack; it does not import the parent workspace.

## Caption and peel a new recording

```bash
# Dry run first; no API request until --execute is supplied.
python scripts/caption_gemini.py --media /path/to/clip.mp4 --output runs/caption
# Export GEMINI_API_KEY in your shell without putting it in commands or receipts.
python scripts/caption_gemini.py --media /path/to/clip.mp4 --output runs/caption --execute
python scripts/select_event.py --caption runs/caption/answer.json \
  --event 0 --output inputs/new/semantic.json
```

Gemini returns audible categories, intervals and uncertainty. The harness matches
these categories to the `sound_categories` declared for your visual assets. It does
not infer source coordinates from a caption alone. The recorded scene already has
geometry, camera poses and person assets; arbitrary video→metric scene reconstruction
is an upstream provider, not implemented by this repository.

```bash
# Run in the official SAM Audio environment with cached base weights.
python scripts/peel_sam.py --audio /path/to/original.wav \
  --start .6 --duration 3.4 --cue 'clothing rustling' --output runs/rustle
python scripts/peel_sam.py --audio /path/to/original.wav \
  --start .6 --duration 3.4 --cue 'clothing rustling' --output runs/rustle --execute
```

Review target AND residual before choosing a source layer. The demo retains the
reviewed residual, restores the crop to its original clock, and uses a20ms edge fade.
The direct speech target lost words and was rejected. Target/residual closure error
is recorded, not forced to zero. A successful model call is not a quality certificate.

Prepare the accepted crop on the full original clock (choose a new output folder):

```bash
python scripts/prepare_audio.py --original /path/to/original.wav \
  --stem runs/rustle/residual.wav --offset .6 --output inputs/prepared-audio
```

Copy these WAVs into the scene input pack alongside semantic.json and assets.json.
The fit input's L/R channels are exact duplicates of the mono source; no implicit
stereo-upmix attenuation is introduced.

## Propose, then render actual physics

Initialize and propose with the README commands. For a new scene, prepare a bundle
containing `scene.glb`, `scene.stage_config.json`, `config.json` with fps, and
`build.json` with a files/hash map. Asset paths in the stage config must resolve on
the renderer host. Supply same-frame listener poses, including headings.

```bash
python scripts/check_geometry.py --pool runs/my-first-fit/candidates/pool.json \
  --bundle inputs/scene --poses inputs/listener.json
python scripts/render_pool.py --pool runs/my-first-fit/candidates/pool.json \
  --bundle inputs/scene --poses inputs/listener.json --source inputs/source-mono.wav \
  --seconds 7.6 --output runs/new-rirs
# On the configured audio-enabled Habitat environment, append --execute.
```

For a cached pool, independently check its query positions:

```bash
python scripts/validate_ir_geometry.py --pool runs/my-first-fit/candidates/pool.json \
  --renders inputs/corey/renders.json --output runs/my-first-fit/ir-geometry.json
```

The geometry check binds the exact pool, listener and scene hashes. It computes a
continuous triangle-surface clearance bound; it cannot certify solid occupancy in an
open mesh or correct physical registration. Material search requires a verified engine
that actually applies the material database, not merely accepts a JSON filename.

`render_pool.py` writes a new manifest after every completed pair and retains failed
logs. It renders the full candidate×absorption pool. A changed material requires new
IR queries; changing only source waveform/gain can reuse the same linear IRs.

```bash
python scripts/harness.py fit --run runs/my-first-fit --renders runs/new-rirs/renders.json
python scripts/harness.py label --run runs/my-first-fit
```

Generate configured counterfactual paths first (the example coordinates belong only
to the demo scene; supply different coordinates for your scene):

```bash
python scripts/prepare_routes.py --scene inputs/scene/scene.glb \
  --config configs/routes.json --output runs/listener-routes
```

This emits listener.json and camera.npz per route, with smoothstep travel and surface
clearance checks. To rerender a counterfactual listener route, use `scripts/soundspaces_render.py` with
that route's `--poses`, the selected source trajectory, and selected material profile.
Hold source gain fixed. Add the resulting actual IR folder to a new renders manifest's
`routes` array; don't normalize routes separately. `render_target_replay.py` accepts
`--camera-override` for actual RGB/depth playback of the matching supplied scene.
Use `--help` for the dataset replay schema's CLI. Custom scenes need an adapter to
that documented supplied-bundle format, not assumed metric poses from video.

For a complete three-route engine run on configured environments:

```bash
python scripts/rerender_routes.py --fit runs/my-first-fit/fit \
  --pool runs/my-first-fit/candidates/pool.json --bundle inputs/scene \
  --routes runs/listener-routes --dataset inputs/dataset --clip YOUR_CLIP_ID \
  --source inputs/source-mono.wav --visual-python /path/to/visual-env/bin/python \
  --audio-python /path/to/audio-env/bin/python --output runs/fresh-routes --execute
```

A standalone CPU replay using saved real IRs and RGB can be checked with:

```bash
python scripts/smoke_replay.py --inputs inputs/corey --run runs/smoke
```

## Export three standalone route videos

```bash
python scripts/export_routes.py --inputs inputs/corey --fit runs/my-first-fit/fit \
  --output runs/my-first-fit/final-routes --playback-gain 32
```

This makes route-A.mp4, route-B.mp4 and route-C.mp4, each using the identical selected
excerpt and its own fitted binaural sound. A single explicit listening gain is shared
by all three; raw fitted WAVs stay unchanged. The script fully decodes each output
and saves input/output hashes. Use gain1 for raw-level exports.

## Export the film

The demo builder needs the visual pack's geometry, assets, camera calibration,
original/replay videos, and three actual route renders. It fails if the route audio
is missing; it does not synthesize a fake spatial finale.

```bash
python scripts/build_demo.py --run runs/my-first-fit --output runs/my-first-fit/demo
python scripts/serve_review.py --directory . --port 8894
# In another terminal:
python scripts/capture_server.py --output runs/my-first-fit/demo/browser-capture.webm
```

Open `http://127.0.0.1:8894/runs/my-first-fit/demo/?save=1`, click **Export video**, and
let the film finish without seeking. The canvas records1920×1080 at30fps with WebAudio.
Chapter cards highlight the next module and explain its purpose in one sentence.

```bash
ffmpeg -n -i runs/my-first-fit/demo/browser-capture.webm \
  -c:v libx264 -preset slow -crf 18 -r 30 -pix_fmt yuv420p \
  -c:a aac -b:a 192k -movflags +faststart runs/my-first-fit/demo/demo.mp4
ffmpeg -v error -i runs/my-first-fit/demo/demo.mp4 -f null -
```

Check the recorded ears against the exact chapter sources:

```bash
python scripts/audit_capture.py --demo runs/my-first-fit/demo \
  --video runs/my-first-fit/demo/demo.mp4 --output runs/my-first-fit/capture-audit.json
```

Raw Habitat frames are1024square; the1080p canvas improves text/diagram rendering,
not the information content of the original footage. Compare the captured chapter
sound to its source WAV and inspect representative frames before sharing.
