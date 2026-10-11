# Step 4 prompt — Generate local visual descriptions

```text
Work in C:\BrunoOS\Local-Asset-Library and implement only step 4. Read applicable AGENTS.md, docs\progress.md, and the model roles, visual inspection policy, catalog contract, and step 4 in docs\plan\PROJECT.md. Use the pilot renders already produced. Do not spawn subagents, call a cloud caption API, or change source files or Play Shapes.

Choose a small locally runnable vision-language model using current official model/runtime documentation. Confirm image input support, license, exact revision, download size, device compatibility, and remaining project budget before downloading. Select one reasonable candidate and run a real image comprehension smoke test. Do not download several large models speculatively or assume the installed coding model supports images. Isolate the runtime/model cache from the existing local agent environment; do not upgrade its installation as a side effect.

Build a caption adapter with schema validation, bounded retries, explicit failure states, and reproducible settings. Feed actual multi-view images. Produce concise descriptions and structured identity, shape, colors, parts, style, distinguishing features, and uncertainties. Keep suggested uses separate from visual observations. Merge measured technical facts only from the inspector. Never manufacture a visual caption from the filename after model/image failure. Start with about ten varied assets, review their input images alongside generated text, adjust the prompt once evidence justifies it, then process the 40-asset pilot.

Record model revision, backend/device, prompt version, input hashes, generation settings, timing, and any review state. Include an editable owner-correction overlay that can survive later regeneration. Save a Markdown or static review artifact linking each caption to its real views. AI inspection is technical evidence; artistic suitability and final caption review remain unapproved unless Bruno explicitly reviews them.

Test malformed output, retries, uncertainty, input-image handling, and preservation of measured facts and corrections. Report actual vision inference and resource measurements. Update docs\progress.md and make a checked local commit without pushing. Stop before embedding or full-library processing.
```
