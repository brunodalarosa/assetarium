# Project storage

The October 11, 2026 cleanup reduced unique file allocation from **14.465 GiB to
5.531 GiB**, reclaiming **8.934 GiB (about 62%)**. Logical sizes still add up to
9.545 GiB because the two environments name the same shared GPU libraries.
Sources, shared weights, asset results and historical fault evidence were retained.
Final measurements and verification receipts are in `data/storage/`.

Verification: 146 tests passed, including real Blender fixtures; full source
SHA-256/size/mtime comparison passed; catalog/index/pilot and dependency locks
retained their hashes. Real GPU captioning, all semantic modes, actual image
embeddings, PNG hash checks, the active agent connection and a fresh 17-call
connector protocol/lifecycle check passed. Partial helper/environment faults
remain visible separately and are explained below.

Captioning and semantic search require separate pinned Python environments:
their Transformers versions differ. Both use the same GPU-enabled Torch version.
GPU libraries are large, so identical immutable libraries share physical storage
through Windows hard links. Package versions, model weights and inference contracts
are unchanged by the storage consolidation.

All runtime wrappers now install through the same project-local `cache/uv`
using `UV_LINK_MODE=hardlink`. Cache and environments must stay on the same volume.
Never edit an installed dependency in place: a hard-link edit affects every name
for that file. Use uv to uninstall/replace a pinned package when making a change.
If hard links are unavailable, record the fault and plan the disk cost before
using copies. Symlinked environments are not a substitute.

Measure from the repository with the existing interpreter, without installing
anything or repopulating the dependency cache:

```powershell
.\.venv\Scripts\python.exe scripts/storage-report.py
.\.venv\Scripts\python.exe scripts/storage-report.py --output new-install.json
```

Receipt names must be new. Reports show logical bytes, unique bytes and filesystem
allocation. Unique allocation counts each file identity once across the project;
Windows folder Properties may count a shared file separately in both environments.
Directory links are deliberately excluded, including boundary-test junctions.
Directory/filesystem metadata is not included. External source assets and shared
model weights are outside this measurement. Cross-folder attribution depends on
traversal order, so compare project totals rather than individual unique subtotals.

After installation and verification, redundant package installation caches can be
cleared using the cache's exact project path:

```powershell
uv cache clean --cache-dir C:\BrunoOS\Local-Asset-Library\cache\uv
```

This removes installation-cache names, not installed hard-linked environment files.
Existing environments can run offline; reconstructing an environment or installing
new dependencies may require downloading packages again. Use `run --locked --no-sync
--offline` for checks that should use the current installation without changes.
Do not clear runtime/model caches, generated asset data, or fault evidence as part
of package-cache cleanup. No automatic startup cleanup or scheduled deletion is used.

The pilot's planning target is 6 GiB of unique allocated storage. Explain expected
growth of 500 MiB or more or exceeding that target at the mandatory plan checkpoint.
Store one copy of each model revision in shared storage and reference source assets
instead of copying them. Preserve useful evidence, including fault evidence.

For Step 8, Bruno approved the existing eight-pack, 883-asset collection with
up to 2 GiB additional peak unique allocation and an 8 GiB project ceiling,
excluding external originals and shared weights. This approval is specific to
the configured membership; editing a plan or membership file is not approval
for further expansion. Processing uses the existing four runtimes and shared
models, with fresh base-Python receipts before bulk work, after each bounded
batch and after publication. Current measured coverage, retained storage and
runtime evidence are recorded in `docs/step8-verification.json` and
`docs/progress.md`. Historical 20 GiB estimates are not a current allowance.

The approved one-time `scripts/reduce-storage.py` operation consolidates only
matching files of at least 1 MiB in the two installed `torch/lib` directories.
It checks SHA-256 before and after creating each link, uses atomic replacement,
and preserves the original duplicate until the replacement is ready. It records
different files and faults separately and refuses to overwrite its receipt or retry.
It does not install packages, delete caches, or touch source assets/model weights.

Fresh cleanup and verification evidence is under `data/storage/`; historical
processing evidence is retained. `setup-faults.json` records restricted-execution
limitations. The initial `before.json` report used an older allocation measurement
and classified deliberately excluded test links as faults; `before-allocated.json`
is the corrected baseline. Those partial reports are preserved.

The first consolidation found DLLs loaded by the active connector worker and
retained its successful links and fault evidence. After explicit owner approval
to retry, `scripts/retry-storage-links.py` used the loaded embedding libraries as
the canonical files and replaced the idle caption copies instead. It verified
every SHA-256, removed only superseded temporary links after successful replacement,
and retained the initial fault receipt. No running worker had to be stopped.

Verification helper mistakes (an absolute reference-image argument, then hashing
base64 text instead of decoded PNG bytes) are preserved in the partial embedding
receipts. Their completed inference checks remain valid. The corrected helper's
preview check and the independent connector protocol check provide image-hash
verification without repeating already-passed GPU inference.

Run the full test suite in the existing MCP environment, which includes Pillow:

```powershell
.\scripts\mcp-runtime.ps1 run --locked --no-sync --offline --project runtime/mcp python -m pytest --basetemp scratch/pytest-current
```

The lightweight base environment does not provide every image dependency used by
the full suite. Keep fault logs out of any disposable test directory before reuse.
