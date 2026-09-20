# FORCODEX.md

Active bounded task (2026-09-20): integrate accepted source through PR, publish
macOS Beta 4 and update the existing production website and signed update feed.

User authorized commit, push, merge and publication. Keep Actions disabled and
retain main PR/squash/conversation rules. Local accepted source is saved at a5451d8.
This isolated branch starts at main 69ca0b6; content integration uses shared feature
head 44eecb8 to reconcile squashed history without dropping main's repair/workflow changes.

Prepare 2.1.0-beta.4 / 210004 for macOS arm64 only. Reuse Sparkle, the existing public
key and Keychain signing account; do not export private keys. Human handles any new
Keychain/login approval. Run focused tests and full preflight before merge/build.
Publish immutable verified assets before signed feed/site metadata. Verify public
HTTPS discovery/signatures/download identity; collaborator owns final other-device
acceptance. Do not replace the user's installed Beta 3, touch documents, add models,
upgrade dependencies or expand functionality. Record actual results and limitations.
