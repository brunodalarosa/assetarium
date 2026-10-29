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

The repository uses the free [CLA Assistant](https://cla-assistant.io) GitHub
app.

1. Open your pull request as usual.
2. The CLA Assistant bot comments on it with a link. Follow the link, read the
   agreement (the same text as [CLA.md](CLA.md)), sign in with GitHub and
   click **I agree**.
3. The `license/cla` check turns green. Later pull requests from the same
   GitHub account pass automatically.

Make sure every commit's author email is linked to your GitHub account,
otherwise the check cannot match the commits to your signature.

### Patches sent outside GitHub

Email the signature block at the end of [CLA.md](CLA.md) to obrunodalarosa@gmail.com
once, then add this trailer to each commit:

```
CLA-Signed-off-by: Your Name <you@example.com>
```

The name and email must match the signature you sent. This trailer is not the
same as Git's `Signed-off-by` (DCO) line, which does not grant the
relicensing rights described above.

## Before you open a pull request

- Read [AGENTS.md](AGENTS.md) and [`KnowledgeBase/Decisions/`](KnowledgeBase/Decisions/Decisions.md);
  they are binding for behavior changes. Contributor knowledge (where things are, rules,
  gotchas, how systems work) is in [`KnowledgeBase/`](KnowledgeBase/Home.md); update the notes
  you touch in the same pull request.
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

The repository needs no files for the app; it is configured at
cla-assistant.io. One-time setup, done by the repository owner:

1. Create a GitHub Gist named `Assetarium-CLA.md` whose content is
   [CLA.md](CLA.md). The gist is the text contributors sign, so keep it
   identical to the file.
2. Go to <https://cla-assistant.io>, sign in with the GitHub account that owns
   `brunodalarosa/assetarium`, and authorize the app.
3. Click **Configure CLA**, choose the repository and the gist, and click
   **Link**. The app then adds a webhook and starts commenting on pull
   requests.
4. In the repository settings, add `license/cla` as a required status check in
   the branch protection rule for `main`.
5. Optionally add bots (for example `dependabot[bot]`) to the allowlist in the
   CLA Assistant configuration.
6. Contributors from a company sign the [Entity CLA](CLA-entity.md) by email;
   their individual GitHub signature is still collected by the app.

When the CLA text changes, bump its version in [CLA.md](CLA.md), update the
gist (CLA Assistant then asks for new signatures), and commit both together.

CLA Assistant is run by SAP and stores signatures on its own service; you can
export them from its dashboard.

## Who receives the licenses

| Item | Value |
| --- | --- |
| Licensor | Bruno Cesar Puli Dala Rosa (as an individual) |
| Governing law | Province of Quebec and the federal laws of Canada applicable there |
| Contact and entity CLA submissions | obrunodalarosa@gmail.com |
| Signature mechanism | CLA Assistant GitHub app |

**Not legal advice.** The CLA texts were drafted as a starting point, modeled
on the Apache ICLA/CCLA v2.2, the Harmony CLA and the Canonical CLA. They have
not been reviewed by a lawyer. Have qualified counsel in Quebec review them
before use, particularly the relicensing clause (section 3), the moral-rights
clause, and whether Quebec's Charter of the French Language requires a French
version of these standard-form agreements to be offered first.
