# FORCODEX.md

Timestamp: 2026-09-19 (lightweight GitHub Flow)

## Bounded Assignment

Implement only main protection, a five-section PR template, Bug/Feature issue
forms and CONTRIBUTING.md. Work from origin/main in codex/github-workflow;
preserve the separate, dirty codex/v1-development checkout and existing PRs.

Main requires PR + the existing six CI checks + resolved conversations, with
zero required approvals, squash merging and no force-push/deletion/bypass.
Do not split CI, add CODEOWNERS/Dependabot/release automation, migrate product
code, alter release branches, pay bills or bypass failed checks.

PR #2 is open. Unlike the older main run's billing restriction, the new hosted
run starts normally: two process-stop tests fail on Linux/macOS; Windows was
still running at handoff. Product/test repair requires a separate scoped task.
Do not merge or bypass checks. Templates are not active on main until merged.

Keep remote facts and validation in docs/PROJECT_STATE.md and append verified
results to PROJECT_LOG.md. Current instructions are AGENTS.md and CONTRIBUTING.md.
