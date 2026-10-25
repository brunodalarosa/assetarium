# Contributing to Assetarium

Thank you for helping. Assetarium (Local Asset Library) is released under the
GNU Affero General Public License v3.0 only (AGPL-3.0-only). Before we can
merge your first contribution, you need to sign a Contributor License
Agreement (CLA). You sign once; it covers all your future contributions.

## Why a CLA

You keep the copyright in your work. The CLA gives the maintainer a license to
use your contribution, a patent license, and the right to relicense it,
including under commercial terms. That lets the project offer commercial
licenses alongside AGPL, which helps fund its development. In return the CLA
commits that every version that includes your work will also stay available
under AGPL-3.0-only or another OSI-approved open source license.

- Contributing as an individual: [CLA.md](CLA.md).
- Contributing as part of your job, or your employer owns what you write:
  your organization signs [CLA-entity.md](CLA-entity.md) and lists you in its
  Schedule A, and you also sign the individual CLA.

## How to sign

### Pull requests on GitHub (recommended)

The repository uses the [CLA Assistant](https://github.com/cla-assistant/cla-assistant)
GitHub app (or its GitHub Action variant).

1. Open your pull request as usual.
2. A bot comment asks you to sign. Read [CLA.md](CLA.md), then reply in the
   pull request with the exact sentence it shows, for example:
   `I have read the CLA Document and I hereby sign the CLA`.
3. The CLA check turns green. Later pull requests from the same GitHub
   account pass automatically.

Make sure every commit's author email is linked to your GitHub account,
otherwise the check cannot match the commits to your signature.

### Patches sent outside GitHub

Email the signature block at the end of [CLA.md](CLA.md) to `[CONTACT EMAIL]`
once, then add this trailer to each commit:

```
CLA-Signed-off-by: Your Name <you@example.com>
```

The name and email must match the signature you sent. This trailer is not the
same as Git's `Signed-off-by` (DCO) line, which does not grant the
relicensing rights described above.

## Before you open a pull request

- Read [AGENTS.md](AGENTS.md) and `docs/decisions/`; they are binding for
  behavior changes.
- Run the tests through the runtime wrappers (see [CLAUDE.md](CLAUDE.md)):

  ```
  .\scripts\mcp-runtime.ps1 run --locked --no-sync --offline --project runtime/mcp python -m pytest --basetemp scratch/pytest
  ```

- UI text must be valid UTF-8 (`tests/test_ui_encoding.py`).
- Do not commit original assets, models, or anything under `data/`, `cache/`,
  `logs/` or `scratch/`.
- Third-party code keeps its own license; mark it as described in section 8 of
  the CLA.

## For maintainers: setting up CLA Assistant

Nothing is installed yet. When the repository is public:

1. Store the CLA text where CLA Assistant can read it: either a GitHub Gist
   containing [CLA.md](CLA.md) (CLA Assistant app at cla-assistant.io), or the
   file in this repository (CLA Assistant GitHub Action, which stores
   signatures as JSON in a dedicated branch such as `cla-signatures`).
2. Link the repository and require the `license/cla` (or the Action's) status
   check in branch protection for `main`.
3. Add the maintainer accounts and bots to the allowlist.
4. When the CLA text changes, bump its version in [CLA.md](CLA.md) and decide
   whether earlier signatures still apply.

The Action variant keeps signatures in the repository itself, with no third
party holding them; the app is easier to set up. Either works with these
documents.

## Open decisions

The CLA files are drafts and contain placeholders the owner must fill before
publishing:

| Placeholder | Decision | Notes |
| --- | --- | --- |
| `[LEGAL ENTITY NAME]` | Who receives the licenses: Bruno as an individual, or a company. | A company makes later transfer and commercial licensing simpler. |
| `[JURISDICTION / GOVERNING LAW]` | Which country's (and state's) law governs the CLA. | Usually where the licensor lives or is registered. Some jurisdictions limit moral-rights waivers. |
| `[CONTACT EMAIL]` | Where contributors send signatures and notifications. | Use a project address, not a personal one. |
| `[CORPORATE CLA SUBMISSION ADDRESS]` | Where entities send the signed Entity CLA and Schedule A updates. | Can be the same as the contact email. |
| Signature mechanism | CLA Assistant app, CLA Assistant Action, or another. | See "For maintainers" above. |

**Not legal advice.** The CLA texts were drafted as a starting point, modeled
on the Apache ICLA/CCLA v2.2, the Harmony CLA and the Canonical CLA. They have
not been reviewed by a lawyer. Have qualified counsel in your jurisdiction
review them before use, particularly the relicensing clause (section 3), the
moral-rights clause and the choice of law.
