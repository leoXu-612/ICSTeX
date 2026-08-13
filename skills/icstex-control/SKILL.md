---
name: icstex-control
description: Operate a local ICSTeX LaTeX or Block project through the project-scoped MCP server. Use for inspecting, reading, searching, diagnosing, counting, editing, importing images, mutating Blocks/layout/theme/sources, compiling, SyncTeX, local OCR, reference metadata, history recovery, or exporting ICSTeX projects from an Agent or Harness.
---

# ICSTeX Control

Use the ICSTeX MCP as the authority for project operations. Do not remote-control
the GUI or bypass MCP safety checks with direct shell writes.

## Workflow

1. Call `inspect_project` first. Confirm the fixed root, root file, grants,
   toolchain, Block-project hash, and interaction boundary.
2. Prefer read/query tools for inspection:
   - `read_document` for text and verified snapshots.
   - `query_project` for `search`, `history`, `environment`, `assets`, `blocks`,
     `outline`, `word-count`, `references`, `diagnostics`, and SyncTeX.
3. Before `write_document`, read the file and pass its exact `sha256` as
   `expected_sha256`; use `missing` only when creating a new file. On conflict,
   read again, reconcile, and retry. Never blindly overwrite.
4. Before `mutate_blocks`, query `blocks` and pass `blockProjectSha256` as
   `expected_project_sha256`. Updates and deletes must also pass the Block's
   current `revision` as `expectedRevision`.
5. Treat `recognize_image` output as an uncommitted candidate. Inspect `safe`,
   warnings/errors, and `reviewRequired`; write only in a separate CAS call
   after explicit user approval.
6. Use `compile_project` preview for feedback and final for submission output.
   Use `export_artifact` for a proper final PDF or portable package.
7. Use `restore_snapshot` with the current target hash to restore a text or
   image preimage. It creates a new undo preimage; never edit snapshot storage.
8. Report the changed paths, new hashes, snapshot IDs, compile outcome, and
   export target. Keep snapshot IDs opaque.

## Authority Rules

- The server starts read-only. `--allow-write`, `--allow-compile`,
  `--allow-network`, `--allow-recognition`, `--allow-input`, and `--export-root`
  are host-owned grants. Tool arguments cannot grant authority.
- `--allow-trusted-raw-latex` is a separate high-risk host grant and requires
  write authority. Without it, trusted raw-LaTeX Blocks remain inert.
- MCP compilation forces no rc files, no shell escape, finite timeouts, and
  TeX paranoid file I/O; it is intentionally stricter than ordinary CLI TeX.
- Tool path arguments are POSIX-style and project-relative. Never pass absolute
  paths, `..`, URLs, drive letters, or symlinks.
- Keep the same project closed or read-only in the ICSTeX GUI while using MCP
  mutations. MCP cannot see unsaved GUI buffers or update GUI in-memory state.
- Network lookup sends only an explicit DOI/arXiv identifier to ICSTeX's fixed
  HTTPS metadata endpoints. OCR remains local and never writes automatically.

## Server Setup

Install the optional adapter once from the ICSTeX checkout:

```bash
python3 -m pip install -e '.[agent]'
```

Configure a stdio MCP command with an explicit project root. Start with no
grants; add only those required for the current task:

```bash
icstex-mcp --project-root /absolute/path/to/project
```

For Codex CLI, register the read-only server with:

```bash
codex mcp add icstex -- icstex-mcp --project-root /absolute/path/to/project
```

For bounded write and compile work:

```bash
icstex-mcp --project-root /absolute/path/to/project --allow-write --allow-compile
```

Add grants only for the requested operation:

- Editing and Block assembly: `--allow-write`.
- Compile and SyncTeX: `--allow-compile`.
- DOI/arXiv lookup: `--allow-network`.
- Local OCR candidates: `--allow-recognition`.
- External image import: `--allow-input /approved/file-or-directory` plus write.
- New PDF/package export: `--export-root /approved/output-directory`; PDF export
  also needs compile.

Do not install/remove OCR runtimes, change system packages, or expand input or
export roots through MCP. Those remain explicit host/user setup actions.
