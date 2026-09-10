# FORCODEX.md

Timestamp: 2026-09-10 (source synchronized; Beta activation remains held)

This is Codex's current bounded brief. Replace it when the assignment changes;
do not append completed-task history.

## Current State

The verified source/artifact matrix is maintained in `docs/PROJECT_STATE.md`.
The local installed application contains the frozen response/preview, formula/
table and default-offline update-entry source. Its exact local build identity,
verification boundaries and rollback receipt are recorded in the state and log.
The Beta 2 source and development handoffs are synchronized to GitHub. The signed
appcast remains local-only, outside the website tree; see the project state for
the verified source identity. Native online delivery is not activated or accepted.
Human Keychain authorization is complete. Candidate r2 has independently verified
archive/feed signatures and has passed a real isolated native replacement and
cold launch. Activation is held because the late-starting-instance/native
installation mutual-exclusion gate is not established. See
`docs/BETA_ACTIVATION_HANDOFF.md` for evidence and the required scope decision.

## Active Bounded Assignment

Connect only the macOS arm64 Beta channel using Vercel signed appcasts and
versioned GitHub prerelease full archives. Preserve Beta 1 public assets and
the installed application. Use Sparkle 2.9.6 and the existing native adapter.
Keep automatic checks opt-in. Do not trigger GitHub Actions, activate Windows
updates, or perform Apple Developer ID signing/notarization in this assignment.

The user explicitly approved a dedicated ICSTeX Beta Ed25519 key in this Mac's
login Keychain. Keep private material there; never export it to files, logs,
source, or website content. Backup remains a human decision.

Use isolated application copies and synthetic documents for signed two-version
acceptance. A deployment or valid signature is not proof of replacement. Record
exact source/version/sequence, archive hashes, public key identity, feed URL,
deployment/release identities, native outcomes and recovery limitations. Publish
only accepted targets. Run required full tests and packaging preflight.

The user also explicitly approved publishing to the existing Vercel production
domain after acceptance, keeping current website content unchanged apart from
the Beta update directory and its caching headers. Only a preview has been
deployed; it contains no appcast. The now-signed local feed is not approved for
publication while an activation gate remains unmet. Do not generate another key,
weaken the gate, or claim that a GUI process scan is an installation lock.

Pause publication pending a bounded decision on installation-lifetime exclusion
and application/MCP startup coordination. Adding a new helper, modifying Sparkle,
or changing the supported multi-instance policy is not an incidental deployment
step. Preserve the signed r2 candidate and all prior artifacts. Remaining native
race/interruption tests and public HTTPS delivery tests are explicitly unverified.

## Required Context

- Operations: `AGENTS.md`
- Current truth: `docs/PROJECT_STATE.md`
- Security boundary: `SECURITY.md`
- Architecture decisions: `docs/DECISION_LOG.md` D003, D005, D007, D013, D014, D017, D018, D019 and D020
- Priorities: `docs/ROADMAP.md`
- Memory lifecycle: `docs/MEMORY_MANAGEMENT.md`

## Handoff Rule

Put verified current facts in project state and append historical evidence to
`PROJECT_LOG.md`. Keep unverified release gates explicit. Do not modify student
content or repository workflow/security settings.
