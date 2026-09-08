# Concurrent Codex assignment: native application updates

Date: 2026-09-08. User authorized implementation alongside another backend task.

Implemented scope: the Chinese update settings UI, a process-wide Qt controller,
save/exit guards, native Sparkle/WinSparkle adapters and opt-in packaging seams.
Status: source implementation and bounded verification complete. Application
and packaging inputs are frozen for the separate local installation task;
preserve that task's `FORCODEX.md` and installation records. Results are in
`docs/PROJECT_STATE.md` and `PROJECT_LOG.md`; release activation is a future
separately authorized task described by `packaging/UPDATES.md`.

Use upstream update engines and signed packages, not a new installer or custom
cryptographic protocol. Keep automatic checks off by default. Development builds
and unconfigured release builds must remain offline and visibly unavailable.

Velopack was evaluated, but its 1.2.0 macOS apply path does not verify the new
bundle signature and can delete the old temporary bundle after a failed move.
Use Sparkle on macOS and WinSparkle on Windows for this implementation instead.

Completed verification: focused pure/GUI tests, required compileall/full suite,
native bridge compile/load, pinned SDK staging and isolated Chinese Qt render.
No student files. The separate local installation task may include this source
without configuring or embedding the native updater runtime.
Do not build/distribute ICSTeX, replace `/Applications/ICSTeX.app`, create signing
keys, access credentials, push, publish or trigger GitHub Actions. Real signed
two-version installation and recovery acceptance remains a separate release gate.
