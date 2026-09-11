# M4 project-checkpoint GUI and real draft capture

The working source now creates selected-file checkpoints and reviews/restores them
into new directories through real dialogs. Disk bytes and actual GUI drafts remain
separate. This is not complete M4: recovered Block drafts are inspectable JSON,
not yet a resumed editing session; interrupted Block-write recovery and migration
acceptance remain outstanding.

## User workflow and ownership

`文件 → 创建项目检查点…` and the History panel show a bounded local filename
inventory plus actual unsaved buffers from the current project's open windows.
Users can select/deselect entries, add project-local files, inspect draft previews,
choose a new output and explicitly confirm. The inventory is not dependency or
cloud-availability proof. Unsupported paths, links, unreadable input and limits
are checked by the existing byte-exact core when capturing.

Related source Save/automatic compile entrances and Block Save/assembly/FINAL are
paused while the capture dialog owns them. Existing compile/import activity is
refused, not stopped implicitly. The lease records each tab/session and prior timer
intent; unchanged requests resume when it ends. Different/newer input is preserved
without reviving an old save request. Multiple windows editing the same file retain
distinct source drafts. Capture does not apply properties, save sources, regenerate
Block files or authorize compilation.

Block recovery payloads contain the actual registry/layout/source/theme state and
unapplied property/table-editor records. Their versioned recovery envelope is not
a new authoritative project format. Source text is separately encoded as UTF-8;
selected saved files retain their original encoding and newline bytes.

`文件 → 从检查点恢复为新目录…` verifies the whole archive, displays file identities
and bounded draft previews, then requires a new target and confirmation. Restore
is bound to the reviewed manifest, not merely the selected archive path. Replacing
it with another valid checkpoint cannot silently restore a different selection.
The output has `project/`, `drafts/`, a manifest and recovery instructions. It never
switches the current project, applies drafts or starts compilation. Independent
pre-existing work in the application is not granted new authority by restoration.

One modal worker is active in the supported workflow. Cancel requests cooperative
interruption and keeps cooperating writes paused until it returns; blocked OS I/O
may delay cancellation. If publication already won the final cancellation race,
the file is preserved and its location stays visible, with current-state acceptance
refused when the captured window/draft changed. No successful output is silently
deleted or falsely described as never generated.

## Implementation seams

- `app/core/project_checkpoint.py`: bounded candidate names, verified draft preview,
  and optional reviewed-manifest binding on restore; existing byte/retention rules
  and raw project formats remain unchanged.
- `app/gui/project_checkpoint_dialog.py`: explicit selection/confirmation/review,
  GUI-owned draft capture, cooperating-write lease and one background operation.
- `document_lifecycle.py`, Block `project_session.py`: narrow capture gates, not a
  universal project-session rewrite. Checking clean root documents also respects
  the gate, preventing dependency/external-change compilation during capture.
- Main-window menus/signals/close and History-panel buttons expose the workflow.
- Core, GUI and visual tests plus `tools/probe_project_checkpoint_gui.py` verify it.

## Source and receipts

Final app Python path/content SHA-256:
`11b95515d2cb3984d152de46a2791a3c58ddfd8069e82d4b6e5b90a23464c46d`.
Hash method: sorted repository-relative `app/**/*.py` paths, NUL, file bytes, NUL.
Environment: Python 3.12.6, PySide6 6.11.1, macOS 26.6.1 arm64; Qt offscreen.

Focused final receipt: `/tmp/icstex-v1-m4-checkpoint-gui-focused-r7.log`, passed,
exit 0. Prior integrated source/Block/history cases passed on the earlier slice;
exact counts/timings are in the current state and project log. Required compileall
and whitespace checks passed, including separate checks of the new untracked files.

Final full discovery passed, exit 0; exec `81933` / PID `21124` is terminal:
`/tmp/icstex-v1-m4-checkpoint-gui-suite-r2.log`. The app hash was rechecked unchanged
after completion. Exact counts/timing are in the current state and project log.

Final product probe r5 passed, exit 0, on the same app hash:
`/tmp/icstex-v1-m4-checkpoint-gui-product-r5.log`, with retained results/screenshots
under `/tmp/icstex-v1-checkpoint-gui-20260911-r5/`. It drove actual selection/review,
confirmation and cancel buttons. Explicit output paths were entered into the real
dialogs; native file-picker automation was not exercised. Both final-source create
review screenshots and both reopened FINAL screenshots were visually inspected.

The ordinary fixture recovered five original files and its real unsaved child
buffer. The Block fixture recovered eight original files plus a real source-buffer
draft and actual Inspector alias draft, without applying the alias to its model.
GBK/CRLF bytes, selected metadata and originals matched. Reopening the restored
saved projects and explicitly compiling produced one-page FINAL PDFs containing
the saved text, not the independent pending drafts. PDF SHA-256:

- Ordinary: `2b420aa7613dcc9367c6e2e7aef19af1f6954f57207a3f23238e7f2a7d9e9ffd`.
- Block: `e4f97c13978f3e06776ecb64cb04cefc2f94cdb3da0efe334952cf51309829af`.

## Failed attempts and evidence boundaries

Initial focused fixtures supplied an invalid text Block, then attempted to overwrite
the ordinary fixture's manual `main.tex`. The existing schema/write guards correctly
refused. Using a valid separate Block fixture and real session installation fixed
the fixture, including its spurious signal-disconnection warnings. An external
reload test initially lacked a compile manager; that setup error was not a red
proof of an application defect. The completed test now covers signal-blocked source
reload, capture cancellation and no new automatic compile.

The actual late-publication/cancel regression did fail before the UI correction:
`/tmp/icstex-v1-m4-checkpoint-cancel-publication-red-r1.log`. A completed output's
dialog disappeared. Final focused coverage preserves its visible location.
Full run r1, exec `30755` / PID `20479`, was deliberately stopped with exit 143
before that source correction; it is not final acceptance or an unexplained crash.

Product r1 had a probe-only duplicated `project_dir` argument for Block session
construction. r2/r3 recovered correctly but the short thin-font Block sentence had
only eight below-threshold pixels at fit width. The r3 failure screenshot showed
the text and the actual PDF contained it. The probe now uses the real zoom controls
before checking visibility; it did not lower the threshold or change the renderer.
r4 passed before the final cancel correction; r5 is the final-source product receipt.

Native file pickers, IME/AX, Windows, power-loss/cloud storage and human usability
remain unaccepted. Preview text is bounded; full draft bytes are still retained.
Format migration, a reviewed way to resume recovered drafts in a new editing copy,
and pending Block-write recovery are separate remaining M4 work. M5 frozen delivery
and M6 completion are not implied. No new dependency, writable MCP authority,
application package, installed-app change or release was made. The user separately
authorized source submission after verification; its Git receipt belongs in
`PROJECT_STATE.md` and `PROJECT_LOG.md`, not in product-acceptance claims.
