# Vendored: coastalmodeling-vdatum

This directory is a vendored copy of `coastalmodeling_vdatum`, NOAA's vertical
datum conversion library.

- **Source**: https://github.com/oceanmodeling/coastalmodeling-vdatum
- **Author**: Felicio Cassalho (felicio.cassalho@noaa.gov)
- **Vendored from commit**: `0d63b2bbc0b0634e20a0ec55023a53354fab1b47`
- **License**: CC0 1.0 Universal (public domain dedication) — full text in
  `LICENSE.txt` alongside this file.

## Why vendored, not a dependency

`coastalmodeling-vdatum` is not published to PyPI, so it has historically
been declared as a `git+https://...` pinned-commit dependency. PyPI's upload
service rejects any package whose metadata declares a direct VCS/URL
dependency (`400 Can't have direct dependency: ...`), which made
`vdatum-mcp` unpublishable. Vendoring the small amount of code actually used
(five files, no PyPI-registry dependency of its own beyond `numpy` and
`pyproj`, both already required here) removes that blocker.

This is a private implementation detail of `vdatum-mcp`, not a redistribution
of `coastalmodeling-vdatum` as its own package — nothing here is importable
as `coastalmodeling_vdatum` from outside `vdatum_mcp`, and no separate PyPI
project is created for it.

## Keeping this in sync

Functional changes from upstream are limited to the internal import in
`vdatum.py` (`from coastalmodeling_vdatum import _geoid_tr, _path` -> `from .
import _geoid_tr, _path`, to work as a relocated subpackage), a bare
`except:` -> `except Exception:` and an ambiguous `l` -> `_` loop variable in
`utils.py`/`vdatum.py` (both required by this repo's lint gate, both
no-ops behaviorally), and unused-import removal in `utils.py`. Everything
else — including full reformatting via this repo's pinned `ruff format` —
is otherwise faithful to the pinned commit above. If upstream fixes a bug or
adds a datum, diff against that commit (or a newer one), ignoring
whitespace/quote-style noise, and reapply.
