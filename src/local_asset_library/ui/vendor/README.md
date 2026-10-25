# Offline 3D preview dependencies

These files are vendored unmodified from pinned upstream releases. They are
loaded only when a user opens an interactive preview. No npm installation,
development checkout, CDN connection, or additional runtime is required to run LAL.

| Component | Version / source | License |
| --- | --- | --- |
| Online 3D Viewer browser bundle | [0.18.0](https://github.com/kovacsv/Online3DViewer/releases/tag/0.18.0), `o3dv.zip` | MIT, `online3dviewer-0.18.0/o3dv.license.md` |
| Three.js, included in that bundle | 0.176.0 | MIT, `licenses/three-LICENSE`; original bundle notices retained |
| fflate, included in that bundle | 0.8.2 | MIT, `licenses/fflate-LICENSE` |
| Chevrotain, included through Three.js's Collada parser | 9.0.1 | Apache 2.0, `licenses/chevrotain-LICENSE` |
| regexp-to-ast, included through Chevrotain | 0.5.0 | MIT, `licenses/regexp-to-ast-LICENSE` |
| Draco official decoder JavaScript and WASM | [draco3d 1.5.7](https://www.npmjs.com/package/draco3d/v/1.5.7), `https://cdn.jsdelivr.net/npm/draco3d@1.5.7/` | Apache 2.0, `draco-1.5.7/LICENSE` |
| Citadella environment cube, included in the viewer release | Emil Persson, aka Humus, [humus.name](http://www.humus.name) | [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/), original attribution in `online3dviewer-0.18.0/envmaps/citadella/readme.txt` |

The Citadella images are used unchanged for model lighting, with a plain
background. Asset geometry and textures remain in their original source folders;
none are part of this directory. No sample models are bundled.

The original `o3dv.zip` SHA-256 is
`866f3a584b44e15d55bab4d88fbb169b7ac2bde6bedb2e1658b9f6bd74f4dfdf`.
`manifest.json` records every vendored payload's size and SHA-256 for reproducible
review. When upgrading, replace distributions rather than patching dependencies
in place, update notices and the manifest, and rerun native preview verification.

The integration uses the upstream `Viewer`, `ThreeModelLoader`, navigation,
camera presets, fit/clipping, material conversion, edge display and projection
features. LAL supplies its own small toolbar and loading/navigation lifecycle.
For glTF, LAL supplies the pinned importer's `gltfExtensions.draco` with the
official decoder initialized from local WASM bytes. This version-specific
integration avoids the upstream default decoder CDN URL without changing the
upstream bundle. CAD and other formats not cataloged by LAL are not exposed.
