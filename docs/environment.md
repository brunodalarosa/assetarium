# Environment evidence — October 11, 2026

Verified in this run from executable output, hardware query, selected configuration
fields and live read-only endpoints. No models were downloaded, no rendering or
inference was run, and existing Ollama/OpenCode configuration was not edited.

| Capability | Status | Evidence / limitation |
| --- | --- | --- |
| NVIDIA GPU | Verified detection | `nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader`: NVIDIA GeForce RTX 5070, 12227 MiB, driver 616.64 |
| CPU | Verified registry identity | `ProcessorNameString`: Intel(R) Core(TM) Ultra 7 265KF. CIM query was denied; registry value provided identity |
| Python | Verified | CPython 3.13.15, Windows x64; project `.venv` uses installed interpreter below |
| uv | Verified | 0.12.11, commit 4b53f66b7, x86_64-pc-windows-msvc |
| Git | Verified | 2.52.0.windows.1; new local repository, no remote |
| SQLite FTS5 | Verified execution | SQLite 3.53.1; actual in-memory FTS5 table, insertion and MATCH query passed |
| NumPy | Verified execution | 2.3.4; finite normalized synthetic float32 vector calculation passed; not model inference |
| Blender | Verified executable/version | `C:\Program Files\Blender Foundation\Blender 5.2\blender.exe --version`: 5.2.2 LTS, build hash d13f752e3b9c, build date 2026-09-15 |
| Blender on PATH | Missing | Shell command lookup found no Blender; explicit installed executable is configured |
| Blender rendering/imports/CUDA | Untested | No assets loaded or rendered; executable detection does not verify format/material support |
| Ollama | Verified executable/server | `C:\BrunoOS\OpenCode-local-agent\Ollama\ollama.exe --version`: 0.33.3; live localhost `/api/tags` responded |
| Installed Ollama models | Verified tags/manifests | `qwen3.8:local-agent` (17741872190 bytes), `qwen3.8:27b` (17741872154 bytes); local manifest names match. Sizes are endpoint reports, not a deduplicated disk total |
| OpenCode | Verified version/config fields | 1.18.29; selected model `ollama/qwen3.8:local-agent`, default agent `build`, Ollama base URL `http://localhost:11434/v1` |
| GPU concurrency | Partially verified snapshot | `/api/ps` had no loaded Ollama models; NVIDIA compute-app query returned no rows. This does not prove all graphics activity is absent or that later workloads fit together |
| LM Studio / llama-server | Not discovered | No `lms`/`llama-server` command found; neither checked LM Studio install directory existed. Not a whole-computer absence claim |
| Caption / embedding runtime | Untested | Existing coding model is not validated for asset images; EmbeddingGemma 2 and SentenceTransformers compatibility/modality are not tested or installed here |
| Source collection | Verified directory exists | Configured read only; no inventory/count, source edits, asset copies or licensing conclusions in this stage |

Installed Python interpreter:
`C:\Users\backup pc\.local\share\uv\python\cpython-3.13-windows-x86_64-none\python.exe`.
Shell command locations: uv at `C:\Users\backup pc\.local\bin\uv.exe`, Git at
`C:\Program Files\Git\cmd\git.exe`, NVIDIA tool at `C:\WINDOWS\system32\nvidia-smi.exe`.
OpenCode launcher is `C:\BrunoOS\OpenCode-local-agent\outputs\opencode.cmd`.

Inspected only model/default-agent/provider URL fields in `opencode-local.json`,
Ollama executable/model-root/host settings in `Start-Ollama.ps1`, model manifest
filenames, and model names/sizes from local endpoints. No credential fields were
printed. Existing launcher points model storage at its own `OllamaModels` and host
at `127.0.0.1:11434`; this project leaves those settings intact.

Windows sandbox observations: initial default uv cache discovery hit access denial;
project-local cache fixes that. Initial dependency build hit PE-resource access
denial in sandbox TEMP; project-local `scratch/tmp` fixes that. Generated Windows
console launchers and junction creation were blocked inside the sandbox; the exact
CLI and all focused tests passed in an approved execution outside that sandbox.
Python module execution also ran inside the sandbox, with an interpreter-location
warning. These are execution-environment limitations, not failed FTS5/NumPy support.

No concrete incompatibility with the planned SQLite/FTS5 + NumPy approach was found.
No stack deviation is required. Future stages must verify model documentation and
actual inference before asserting GPU/runtime or text/image compatibility.
