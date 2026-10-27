# Set up only the stages you need

No credentials, hosted endpoint or model weights are included. Use your own accounts.
Offline replay and local tests make no model/API calls. Astra reconstruction is an
upstream workflow: this repository does not install, invoke or test it.

| Stage | Environment | Credentials |
|---|---|---|
| Replay, propose, fit, import scene | Python 3.10+, requirements.txt, FFmpeg | None |
| Semantic perception | Standard Python, Gemini REST API | Your GEMINI_API_KEY and accessible GEMINI_MODEL |
| Semantic separation | Official SAM Audio installation, PyTorch/CUDA, cached weights | Your model-download authorization if required |
| Visual rendering | Separate Habitat-Sim environment; demo used 0.3.3 | None |
| Acoustic rendering | Audio-enabled Habitat-Sim; demo used 0.2.2 with native patch | None |

## CPU environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
ffmpeg -version
```

Install FFmpeg with your OS package manager. These tests use synthetic signals and
need neither the private dataset nor API access. A full scene replay additionally
needs the [input artifact pack](reproduce.md#prepare-an-input-pack).

## Your semantic API

Create a key in [Google AI Studio](https://aistudio.google.com/apikey). Choose a model
available to **your** account. Supply `GEMINI_API_KEY` through your shell's secret
manager or an untracked local environment; set `GEMINI_MODEL` explicitly. The empty
[.env.example](../.env.example) documents the names. Scripts do not auto-load .env.
Never paste a key into an agent prompt, tracked configuration, command log or receipt.

```bash
export GEMINI_MODEL='YOUR_AVAILABLE_MODEL_ID'
python scripts/caption_gemini.py --media inputs/clip.mp4 --output runs/perception
# Only when you intentionally want a paid request, repeat with --execute.
```

The dry run performs no network request. Execution makes one request, with no automatic
retry. Saved provider responses can be normalized using `--saved-response response.json`
without a key or network call. Do not inherit or search for another user's credentials.

## Separation model

Install [official SAM Audio](https://github.com/facebookresearch/sam-audio) in a
separate GPU environment using its current installation instructions. Obtain access
and download `facebook/sam-audio-base` with your own Hugging Face account if required.
Keep weights in the Hugging Face cache or a local model directory.

```bash
/path/to/sam-env/bin/python scripts/peel_sam.py --audio inputs/original.wav \
  --start .6 --duration 3.4 --cue 'clothing rustling' --output runs/peel
```

Append `--execute` for actual GPU inference. `--model /path/to/local/model` selects a
local checkpoint. Execution forces offline model loading: a missing cache fails
instead of silently downloading. Review both output tracks before selecting a source.

## Habitat and SoundSpaces

Use separate visual and acoustic environments. Follow [Habitat-Sim installation](https://github.com/facebookresearch/habitat-sim)
and [SoundSpaces](https://github.com/facebookresearch/sound-spaces) for their supported
build dependencies. Installing the CPU requirements does not install either simulator.
The historical audio backend is version-sensitive; a current visual-only wheel is
not a replacement for an audio-enabled build.

For the demo's uniform material fitting, apply the compatible
[native patch and verification procedure](../native/README.md) before rebuilding the
audio environment. Verify material changes alter the actual same-position RIR before
running a material search. A successful import alone is insufficient.

```bash
/path/to/visual-env/bin/python -c 'import habitat_sim; print(habitat_sim.__version__)'
/path/to/audio-env/bin/python -c 'import habitat_sim, quaternion; print(habitat_sim.__version__)'
python scripts/import_scene.py --mesh inputs/room.glb --output inputs/scene
```

The scene must have known meter scale and +Y-up coordinates. Listener headings and
source trajectories must be registered to the same frame. Continue with
[geometry validation and real RIR rendering](reproduce.md#propose-then-render-actual-physics).
The complete GPU/native installation on a new machine is not automated by this release.

## Agent configuration checklist

1. Start with CPU tests and dry runs; do not discover or reuse somebody else's keys.
2. Record Python paths for CPU, separation, visual simulation and audio simulation.
3. Verify scene scale, coordinate frame, asset trajectories and recording clock.
4. Check cached weights and renderer material capability before expensive execution.
5. Only execute paid tools when the operator explicitly authorizes their own account.
6. Preserve failure receipts and choose a fresh output directory for every attempt.
