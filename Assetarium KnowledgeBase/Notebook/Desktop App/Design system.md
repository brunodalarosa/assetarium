---
area: Desktop App
tags: [system]
code: [frontend/src/ui/primitives.tsx, frontend/src/ui/CommandBlock.tsx, frontend/src/components/beui, frontend/src/styles.css, frontend/src/lib/ease.ts, frontend/src/ui/ProposalReview.tsx]
verified: 2026-11-01
branch: feature/library-view
---
# Design system

Hub: [Desktop App](Desktop%20App.md). What the UI is built from, and when to use each piece. The principles
behind it are [decision 0025](../../Decisions/0025-design-principles.md); read them before designing a flow.

## Rules

- **P1 Decide many, commit once, see the outcome**: group alike decisions by signature, stage them, preview,
  one Apply. Cheap and undoable → apply at once with Undo; irreversible → one at a time.
- **P2 The robot means agents**: `Bot` only for external agents; no sparkles.
- **P3 Run it, don't type it**: a button when the app can do it; otherwise a `CommandBlock` with Copy, never a command
  inline in text.
- From `AGENTS.md` → User experience: never offer an action that can't resolve the shown state; keep pending
  work apart from recorded failures.

## How it works

### Tokens

Colors are CSS variables in `frontend/src/styles.css` (`--color-*`, light and dark): `primary` (actions,
selection), `surface` / `surface-2` (cards, insets), `muted-foreground` / `subtle` (secondary text),
`success`, `warning`, `fault` (+ `*-bg`) for states, `danger` only for confirming a deletion. Motion springs
are in `lib/ease.ts` (`SPRING_LAYOUT`, `SPRING_PANEL`); honor `useReducedMotion`. Body text is 12–13 px, Geist.

### Components (`ui/primitives.tsx`, `components/beui`)

| Component | Use it when… |
| --- | --- |
| `Button` primary | the one main action of a view or card |
| `Button` secondary / quiet | other actions; quiet for low-emphasis inline ones (Accept all, Copy again) |
| `Button` danger / destructive | danger: an action that removes something; destructive: only the button that confirms a deletion |
| `IconButton` | icon-only actions; its label is required and doubles as the tooltip |
| `Badge` | a short state or count beside a name |
| `Banner` | a fault or warning that belongs to a whole section |
| `Card` | a titled settings or report block with optional help |
| `Disclosure` | detail most people skip (evidence, history) |
| `EvidenceBlock` | raw evidence (JSON) behind a fault |
| `Progress` / `Spinner` | measured progress / unmeasured waiting |
| `SelectField`, `TextField`, `RadioCards` | form inputs; `RadioCards` for 2–4 choices that need a sentence each |
| beUI `Switch`, `Checkbox`, `Tabs`, `Select`, `ContextMenu`, `Tooltip` | vendored primitives (MIT), adapted where marked "Assetarium" |
| `ProposalReview` | several agent proposals to decide together (P1): groups, per-member choice, preview, one Apply |
| `CommandBlock` / `Reason` (`ui/CommandBlock.tsx`) | a command the owner must run (P3); `Reason` shows backend text and splits any command in it into a block |
| Toasts (`pushToast`) | an outcome or a notice with at most one or two actions (Undo, Review) |

### Icons (lucide-react)

| Icon | Means |
| --- | --- |
| `Bot` | an external agent (Agent activity, agent setup, "Let my agent finish") |
| dot | new since your last visit |
| `CircleSlash` | not processed: a file type Assetarium does not process (state `skipped`) |
| `TriangleAlert` | warning · `CircleAlert` fault · `Clock` waiting · `Check` done or accepted · `X` close or reject |

## Gotchas

- Grouping signatures compare rules exactly: `fbx (unity)` and `fbx(unity)` are different groups. That's
  intended; Assetarium never guesses that two names mean the same folder.
- **`leave_out` indexes follow the stored rule order** (`pack_agent.proposals`), which differs from the order
  the agent sent (`pack_profiles.validate` reorders). Always index the stored list.

## Related

[Frontend build](Frontend%20build.md) · Decisions: [0011](../../Decisions/0011-react-desktop-ui.md), [0024](../../Decisions/0024-pack-profiles-and-variant-groups.md), [0025](../../Decisions/0025-design-principles.md).
