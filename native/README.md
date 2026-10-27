# Uniform material support for non-semantic meshes

`nonsemantic-materials.patch` adapts the historical SoundSpaces Habitat-Sim 0.2.2
loader to apply an explicit material database to a non-semantic static mesh. The
Python capability flag allows scripts/soundspaces_render.py to reject unsupported
binaries. This is an environment-specific patch, not a universal installer.

Apply to a compatible source checkout, preserve your original binary, rebuild in an
isolated environment, and verify a same-position absorption A/B response before
searching materials. Do not equate accepting JSON with applying the material.
Profiles include damping/density/speed; see lib/acoustics.py. Generic uniform profiles
are hypotheses, not calibrated object materials. Visual Habitat 0.3.3 and audio
Habitat 0.2.2 were separate environments in the recorded demo.
