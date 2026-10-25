# Changelog

All notable changes to Assetarium are listed here. The project follows
[Semantic Versioning](https://semver.org/); the format follows
[Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Changed

- README: the setup welcome screenshots now show the current page with the
  "Set up with your AI agent" and "Set it up yourself" choices, and the README explains both.

## [0.1.0] — 2026-10-25

First public release.

### Added

- Windows desktop app: asset sources, startup scans, explicit asset processing with
  progress and cancellation, search, 3D viewer, image viewer, collections and tags,
  notifications, light and dark themes.
- 3D inspection and previews in Blender (FBX, glTF/GLB, OBJ); 2D image catalog (PNG, JPEG,
  WebP, GIF, BMP, TGA, TIFF, AVIF, SVG).
- Optional local AI descriptions (Qwen3-VL-2B, or an experimental OpenAI-compatible local
  model server) and appearance/image search (EmbeddingGemma).
- Keyword, description, image and combined search with bounded results.
- Collection exports: JSON, Markdown, PNG sample sheet and printable report.
- Setup wizard in the app and the terminal, and agent-assisted setup.
- STDIO MCP server with search, asset detail, collection, tag and setup tools.
- Owner command line for Windows and Linux; Linux supports the command line and MCP server.
