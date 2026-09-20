# M6 native console navigation and 200% PDF observation

Follow-up: the clipping documented below is repaired and verified in the
[console-layout receipt](v1-m6-console-layout-verification-2026-09-12.md).
This earlier receipt retains the original source hash and failure evidence.

Date: 2026-09-12. The previously blocked error/diagnostic Return paths now have
actual Cocoa keyboard evidence. The separate synthetic 200% PDF is readable
without obvious blocky pixelation in this native observation. **R2 remains open:
the console clips diagnostic content at small size/high UI scale. No layout
repair or complete M6 acceptance is claimed in this receipt.**

App tree before/after both runs:
`60e50d6fbefd94a09fbb3ffbd1f652e3bc3cc8f6fffc2873396088d7723492c0`.
Environment: macOS 26.6.1 arm64, PySide6 6.11.1, Cocoa. All inputs are synthetic.
No student files, installed app, compilation, commit/push or release operation.

## Actual keyboard navigation

```sh
QT_QPA_PLATFORM=cocoa PYTHONFAULTHANDLER=1 python3 tools/probe_citation_layout.py \
  --native-observe --readonly-navigation \
  --output /tmp/icstex-v1-four-route-native-20260912-r3
```

The first display-name app lookup timed out. A live inventory and bundle-ID
lookup connected to the same process; no probe restart was made. The records
are explicitly labelled navigation fixtures, not real compiler/check output.

| Route | Physical input and observed result |
| --- | --- |
| Error table | Select Errors tab; Tab four times from Auto Compile reaches the table. Down selects the second record. Return emits one activation at 81.8101s and moves the source cursor to `main.tex:3`. |
| Diagnostics | Select Check tab; Shift+Tab from source reaches the diagnostic table, initially outside the visible console area. Drag the actual splitter upward to reveal it. Down selects the second record; Return emits once at 211.9857s and opens `chapters/long-path-for-source-navigation/child.tex:4`. |

The CUA screenshots show the selected rows and resulting source lines. The
observer independently records selected rows, focus, activation and file/line.
Two activations total, zero compile starts/authority, all file-byte checks true.
The window was closed through its native close button. The subsequent CUA read
timed out because the window was gone; exec **6828 ended with exit 0**, report
`timeout=false`, `interrupted=false`, `window_destroyed=true`, `read_only=true`,
and no observer errors. No native numeric-keypad Enter claim is made.

Report `/tmp/icstex-v1-four-route-native-20260912-r3/report.json` SHA-256:
`dbf4e064d8f77f62157dcf8d2873950570d780cec34b1a89a5beac4cf23350cf`.
Loaded probe: `83d824d6cbc68760f46e009980352c35d58049daaa5d54460719a17eadfb00c2`.
Native stderr retains the active scoped AX selected-children mitigation,
missing `Sans-serif` alias timing, an IMK mach-port message, a Caps Lock LED
message and `Called accessibilityLabel on invalid object: 0`. The PDF run also
retains an IMK mach-port message. Their causes are not established here; no
new Python crash report occurred. Normal process exit and location success do
not turn these logs into warning-free AX/IME acceptance.
Outline/search retain their earlier app `9b2f44f5` native identity in the
[four-route receipt](v1-m6-four-route-navigation-verification-2026-09-12.md);
the intervening app changes are four tooltips, not activation logic.

## Newly observed console clipping

At the probe's 1080×720 size and 100% UI scale, switching from Errors to Check
does not make enough height available for diagnostics. Keyboard focus reaches
the table while its rows are below the visible window. Dragging the splitter
is a workaround used to finish the route, not keyboard-only layout acceptance.

A separate offscreen inspection of the actual MainWindow reproduces this:
splitter sizes `[363, 111]`, bottom panel minimum-height override 36 versus
minimum-size hint 244; diagnostic table viewport height **0**. Manually sizing
the pane to its minimum hint is not a full solution: at 150% and 1080×720,
the constrained splitter still yields a zero-height diagnostic viewport.
These are diagnostic observations, not new unittest passes or a proven fix.

Next bounded implementation: preserve header collapse and source/PDF state,
make diagnostic controls and the selected row reachable at all five UI scales,
and verify actual visible regions and keyboard entry/exit at small size. Reuse
existing responsive/focus mechanisms where applicable. Do not add navigation
authority to Refresh/Fix, relax empty-selection guards, or merely enlarge the
100% test and call all-scale accessibility complete.

## Native 200% PDF sample

```sh
QT_QPA_PLATFORM=cocoa PYTHONFAULTHANDLER=1 python3 tools/probe_pdf_native_quality.py \
  --synthetic-pdf /tmp/icstex-v1-formula-coordinates-r6/formula-final.pdf \
  --expected-sha256 302ca81ae4cf6cb5d847a6007f11a16e06c87b8137047b5b33933218a5aa371d \
  --output /tmp/icstex-v1-pdf-native-200-20260912-r1
```

The helper loads the existing hash-checked synthetic artifact in the production
PdfPanel and programmatically configures 200%/the known formula location. It
does not compile or synthesize input. Both CUA's native window screenshot and
the retained settled widget screenshot show readable `Before`, `x + y`, and
`after.` with smooth-looking edges, without the earlier obvious blocky view.
This is a bounded visual observation, not a numerical sharpness benchmark or
proof of the earlier offscreen rendering cause.

Observed zoom 2.0, page 1, viewport 889×562, device-pixel ratio 1.0, scroll
`[171, 108]`. No native zoom-key, other font, HiDPI, all-scale, MainWindow FINAL
or cross-platform acceptance is inferred. The PDF renderer was not modified.

The native close action destroyed the panel; the subsequent CUA read timed out,
but exec **17850 ended with exit 0**. Report confirms no timeout/interruption,
unchanged PDF, matching app hashes and destroyed window.

Report SHA-256:
`f6f570b4e1fa2fde77e8727f34b6b0c073041525a1357a3fb81bd62d954d016d`.
Settled image `state-002.png` SHA-256:
`41929b550442a2a4806f3a9201ef2b1fc0feee707adcfbb2b00a24765e533383`.
Probe SHA-256:
`ba28125de64b52826457609f00bbcc14d650f9bf1f02611d6a66878e01dfd9ca`.

## Verification boundary

Only the new observation tool and evidence/next-action documentation changed.
Application/test source stayed at app `60e50d6f` / app+tests `907f6753`;
the previously completed full regression remains 1561 / 164.006s / OK, not a
new run. Compileall, the new probe's py_compile and diff check pass. Eleven
retained Python crash reports are unchanged. HEAD 3bde2b5 and the empty index
remain unchanged; the held feed still hashes to
`be57a732b6532e3247916530bdc688b7e05b1cd4ec0457b216a5020250140c03`.
No live test window/process remains. R3 historical crash attribution
and AX limitations, R5 security/toolchain decision and E1–E4 remain open.

Suggested commit only: `test(macos): record console navigation and native PDF quality`.
