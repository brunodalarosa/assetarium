# 0017 — License: AGPL-3.0-only with a Contributor License Agreement

**Decision (owner, October 25, 2026).** Assetarium's own code and documentation are
released under the **GNU Affero General Public License v3.0 only** (`LICENSE`,
`license = "AGPL-3.0-only"` in `pyproject.toml`). Contributions are accepted under a
**Contributor License Agreement** (CLA) that lets the owner keep relicensing the project;
the CLA text and signing process live in `CLA.md` / `CONTRIBUTING.md` and are reviewed by
the owner before contributions are accepted.

- **Third-party parts keep their own licenses.** Vendored components
  (`src/local_asset_library/ui/vendor/**`), beUI components and dependencies keep their
  upstream licenses and notices; the AGPL never replaces them.
- **User data is not covered.** Asset packs, model weights, generated catalogs and
  descriptions belong to whoever supplies them; the repository ships none.
- **Network use.** The AGPL's network clause applies to modified versions offered to users
  over a network. The current app is local only (STDIO MCP, loopback engine server).
- Changing the license or the CLA model needs a new owner decision.
