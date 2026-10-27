# Make one failure easier to reproduce

Start with a short issue describing the audible/visible failure, exact interval,
artifact hashes, tool versions and one proposed change. Preserve the old result.
A PR should include the behavior change and an actual validation command, not only a
lower aggregate score. Do not commit credentials, model weights or unlicensed inputs.

Good first contributions: a different semantic provider, offscreen-source proposals,
new energy/perceptual diagnostics, a public redistributable fixture, clearer input
pack validation, or a simulator adapter with genuine RIR provenance.

Run `python -m unittest discover -s tests -v`. Keep hardware/API checks separate from
CPU tests. Mock/synthetic tests must never be presented as physical scene results.
