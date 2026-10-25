# 0009 — Fixes and processing support are reusable system features

**Decision (owner, October 19, 2026).** Every asset-processing fix or new
capability is implemented as a general Assetarium feature, never as a workaround
selected by a named asset source. The system should expand to support different
formats, layouts, dependency conventions and production tools over time.

**Keep true.** Recognize file structure and explicit evidence, not publisher or
pack names. Put source-specific facts in data consumed by shared capabilities.
Format adapters may implement format semantics; shared rules, validation,
processing, previews and retrieval use the same capability. Cover each feature
with synthetic sources having unrelated names. Actual missing files, ambiguous
matches and unsupported conventions remain visible faults with evidence; never
invent a successful result. Preserve originals and prior usable outputs.

**Why.** Repairing a single installed pack does not make a future source with
the same dependency convention work. Improvements must become part of the
system's supported behavior.
