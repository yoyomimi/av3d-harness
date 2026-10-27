# Code and artifact provenance

The repository's existing Apache-2.0 LICENSE is preserved. This does not relicense
third-party recordings, scene meshes, avatars, model weights, or service outputs.
No third-party model weights or raw input packs are committed.

- Gemini is an external API. Configure your own GEMINI_API_KEY; model/service terms apply.
- SAM Audio: https://github.com/facebookresearch/sam-audio — install separately and
  acquire model access under its applicable terms. No automatic model download.
- Habitat-Sim: https://github.com/facebookresearch/habitat-sim
- SoundSpaces: https://github.com/facebookresearch/sound-spaces
- Three.js is vendored for local playback; MIT notice retained at vendor/three/LICENSE.
- The current example uses a supplied Nymeria-Plus recording and supplied reconstructed
  geometry/avatars. The local input pack is excluded from Git. Verify redistribution
  rights for the edited demo media before external publication; the code license does
  not grant rights in these underlying assets.

The fitting pool reuses actual previously queried IRs, reconvolves the reviewed speech
source, and ranks using the default evaluator. The three final routes additionally
have fresh visual and acoustic engine runs. Input receipts preserve provenance locally;
[validation scope](docs/validation.md) distinguishes replay from fresh execution.
