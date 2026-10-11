## Required checkpoints before implementation

Before starting implementation, follow these two steps in order:

1. **Confirm the scope.** Restate the task in one sentence, identify what is included and excluded, and surface any unclear requirements. Ask the user: “Does this scope match what you want?” Stop and wait for their answer.
2. **Confirm the implementation plan.** Explain the proposed changes, state ownership, risks, and verification approach in plain language. Include an estimated duration to complete the plan and an estimate of the additional disk space it will use, with the main assumptions and any significant uncertainty. Ask the user: “Is this implementation plan clear, and do you approve proceeding?” Stop and wait for their answer.

Do not edit implementation files until the user has explicitly approved both checkpoints. Read-only investigation needed to clarify the scope or prepare the plan is allowed. If either the scope or plan changes materially, confirm the affected checkpoint again before continuing.

## Fault handling

For every kind of fault, mark the affected asset/item as faulty, record the reason
and available evidence, preserve usable partial results, and move on. This applies
to geometry, materials, textures, previews, imports, metadata, dependencies,
timeouts, unsupported formats, ambiguity, and any other definition of faulty.
Do not get stuck diagnosing or repairing individual faulty items, silently
substitute success, or automatically retry unchanged faults. Repairs or retries
require an explicit user request. Keep faults visible separately from successful
processing of other items; never edit originals to resolve them.
