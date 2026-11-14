---
area: Desktop App
tags: [system]
code: [frontend/src/ui/primitives.tsx, frontend/src/ui/ViewerTooltips.tsx, src/local_asset_library/ui/interactive-preview.js, tests/test_ui_tooltips.py, scripts/verify-tooltips.py, frontend/src/ui/CommandBlock.tsx, frontend/src/components/beui, frontend/src/styles.css, frontend/src/lib/ease.ts, frontend/src/ui/ProposalReview.tsx]
verified: 2026-11-01
branch: feature/library-view
---
# Design system

Hub: [Desktop App](Desktop%20App.md). What the UI is built from, and when to use each piece. The principles
behind it are in the [Design language](../../Architecture/Desktop%20App/Design%20language.md) (design principles); read them before designing a flow.

## Rules

- The design principles are only in the [Design language](../../Architecture/Desktop%20App/Design%20language.md); this list names them, read them there:
  [P1 Decide many, commit once, see the outcome](../../Architecture/Desktop%20App/Design%20language.md#p1--decide-many-commit-once-see-the-outcome) ·
  [P2 One visual sign for agents](../../Architecture/Desktop%20App/Design%20language.md#p2--one-visual-sign-for-agents) ·
  [P3 Run it, don't type it](../../Architecture/Desktop%20App/Design%20language.md#p3--run-it-dont-type-it) ·
  [P4 Make progress measurable](../../Architecture/Desktop%20App/Design%20language.md#p4--make-progress-measurable) ·
  [P5 No silent states](../../Architecture/Desktop%20App/Design%20language.md#p5--no-silent-states).
- Applying them: P4 lives in `OperationProgress`, `progressInfo` and `source_operations.scan_reporter`; P3 in
  `CommandBlock` / `Reason`; P1 in `ProposalReview`.
- From `AGENTS.md` → User experience: never offer an action that can't resolve the shown state; keep pending
  work apart from recorded failures.
- **Every control says what it does.** `Button`, `Pressable` and `MotionPressable` require `tooltip`: what the
  action will do (its effect or consequence), never the label again; `tooltip={false}` marks a self-explaining
  text button (Cancel, Close, Back, Next) and renders `data-no-tooltip`. Informative icons, badges, counts and
  truncated text get a `Hint`. No raw `<button>` outside `ui/primitives.tsx` and no native `title=` tooltips:
  `tests/test_ui_tooltips.py` fails on both, and `scripts/verify-tooltips.py` fails on any visible control
  without `data-tooltip` / `data-no-tooltip` (form fields with a visible label and select triggers excepted).
- **A disabled control says why.** `Button` and `IconButton` render `disabled` as `aria-disabled="true"`: dimmed,
  focusable, the click swallowed (Enter, Space and a form's implicit submission arrive as that click, so a disabled
  submit button never submits). Their tooltip shows on hover and focus; pass `disabledReason` when the condition
  names a reason the owner can act on. Test a disabled `Button` with `:disabled,[aria-disabled=true]`, never
  `.disabled`. `Pressable`, `MotionPressable` and beUI's own controls still use the native attribute.
- **The 3D viewer uses the same tooltip.** `ui/interactive-preview.js` is plain JS: its controls carry their text in
  `data-tooltip-text` (never a native `title`; the iframe's `title` is its accessible name), and
  `ui/ViewerTooltips.tsx`, mounted once in `App.tsx`, shows one controlled beUI tooltip for them. In fullscreen the
  viewer is a modal `<dialog>` in the top layer, so the tooltip is portaled into it (`TooltipContent`'s
  `container`); anything outside would be hidden and inert.

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
| `IconButton` | icon-only actions; its label is required and doubles as the tooltip (`tooltip` overrides it) |
| `Pressable` / `MotionPressable` | a custom-styled clickable (card, chip, row, link in text): an unstyled button with the required `tooltip` |
| `Hint` | a tooltip on something that isn't clickable (icon, badge, count, truncated text); `focusable` puts it in the tab order |
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
| `ToggleLeft` | format off: shown, but made from a file whose format is off (state `format_off`, P5) |
| `TriangleAlert` | warning · `CircleAlert` fault · `Clock` waiting · `Check` done or accepted · `X` close or reject |

## Gotchas

- Grouping signatures compare rules exactly: `fbx (unity)` and `fbx(unity)` are different groups. That's
  intended; Assetarium never guesses that two names mean the same folder.
- **`leave_out` indexes follow the stored rule order** (`pack_agent.proposals`), which differs from the order
  the agent sent (`pack_profiles.validate` reorders). Always index the stored list.

## Related

[Frontend build](Frontend%20build.md) · Decisions: [0011](../../Decisions/0011-react-desktop-ui.md), [0035](../../Decisions/0035-packs-and-variant-groups.md) · [Design language](../../Architecture/Desktop%20App/Design%20language.md).
