# Third-party dependencies and design references

ARC does not vendor any third-party Python package, model weights, fonts or OdenMap application code. Installing extras downloads dependencies under their own terms. Inspect the license files of the exact installed versions before redistribution or integration.

| Component | Use | License family / upstream reference |
| --- | --- | --- |
| Python and SQLite | Core runtime and local database | Python Software Foundation terms; SQLite public-domain dedication |
| Pillow (optional `images`) | Image crops and image handling | HPND-style PIL/Pillow terms; https://github.com/python-pillow/Pillow/blob/main/LICENSE |
| PyMuPDF (optional `pdf`) | PDF extraction and rendering | AGPL-3.0 / commercial; https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright |
| jsonschema (optional `test`) | Additional schema tests | MIT; https://github.com/python-jsonschema/jsonschema/blob/main/COPYING |
| setuptools / wheel (build tooling) | Python package build | Their respective upstream licenses |
| GitHub Actions (CI only) | Checkout and Python setup | Their respective upstream repository licenses |

## PDF licensing is a separate decision

PyMuPDF and its MuPDF engine are offered under open-source AGPL and commercial licensing. ARC's MIT license does not replace those obligations or automatically make an integration with a closed-source product permissive. The applicable obligations depend on how components are combined, modified, distributed and provided over a network. Review the upstream terms for the actual deployment and obtain qualified advice where needed.

The core and image-only extras do not install PyMuPDF. PDF support is explicit, and no dependency is bundled into the source ZIP. Making a dependency optional does not waive its license when it is used.

## Research and specifications

Public research and interface specifications inform the design; their text, implementations and benchmark results are not relicensed by ARC. See `docs/design/research.md` for attributed design notes and limitations.

## Artwork

The ARC marks in `assets/brand/` are original geometric SVG artwork included under the repository's MIT license. Transparent PNG renditions are derived from those SVG files. They do not reproduce the OdenMap product logo, contain fonts or include external resources.
