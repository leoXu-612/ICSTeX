# M6 native citation keyboard finding and bounded repair

The read-only citation tables trapped Tab/Shift+Tab inside their cells. The
native failure is reproduced, the two tables are repaired, and focused local
regression passes. Post-fix physical keyboard acceptance is **not complete**:
the next CUA call reported a newly locked Mac. R2 remains open.

## Scope and source

Only synthetic files and isolated settings were used. No student content,
network metadata lookup, compilation, installed-app operation or Git mutation.
Branch `codex/v1-development`, HEAD
`3bde2b5d25803262dedef89a081ee6ffbe2b6967`; shared changes preserved.

Baseline app SHA-256:
`489657f34516f5bfeee0934b84a26885e217e8ff3ea7cad05f3f1297819d0085`.
Final app SHA-256:
`4f83dd34551c6fcf6fd5912df54b690471dd5fc8678e7ffdf687b6c66f0a217a`.
Final app+tests SHA-256:
`2f9a46c25b5e594a4c64ca9497f1583ef947dcc5efd80e5732557de9f4aabd14`.
These hash sorted repository-relative Python paths, NUL, raw bytes, NUL;
they do not identify an installed application or release archive.

## Native observation and negative evidence

`tools/probe_citation_layout.py --native-observe` adds passive key/focus/action,
geometry, source-buffer, file-byte and compile-state observations. After initial
window setup it does not check, focus, scroll, navigate or type for the tester.
The existing offscreen layout mode remains separate. Native environment:
macOS 26.6.1 arm64, Python 3.12.6, PySide6 6.11.1, Cocoa.

Initial native r1 had an observer defect: `report.items` is a tuple, not a
method. Qt swallowed repeated callback TypeErrors after the check completed;
its exit-0/observation-completed receipt is **incomplete, not acceptance**.
The original report is retained at
`/tmp/icstex-v1-citation-native-navigation-20260912-r1/report.json`, SHA-256
`0e3ecf7e689e4815d2ff732d0cc950ea63707670d6a501f2c3b7dd98aff39585`.
The observer now uses the tuple correctly, records callback failures and fails
completion if any occur. The original offscreen-only regression could not
exercise this native callback, so its earlier pass did not prove that path.

Corrected native r2, exec 40699, terminal exit 0:

```sh
QT_QPA_PLATFORM=cocoa PYTHONFAULTHANDLER=1 python3 \
  tools/probe_citation_layout.py --native-observe \
  --output /tmp/icstex-v1-citation-native-navigation-20260912-r2
```

Report SHA-256:
`9495261b7a0e85cb0a9f74a2dc87e69147be509999ff8bb3089d70fdcffaac23`.
Nineteen changed states, 62 recorded key-dispatch events (not 62 distinct
physical presses), two check actions, no observation errors. Both checks produce
complete/stable missing/known/unused results. The full long key, child location
and input identity remain available in detail/AX text. No compile authority or
start; three source files unchanged; timeout false and window destroyed.

At actual 1080×720 and 100%, native Tab reaches Refresh and the result table;
Down/Up changes the selected rule and detail. Tab then moves between cells and
wraps from the last row to the first. Shift+Tab wraps backward; Control+Tab did
not exit. Focus never reaches detail/locations. No child navigation or other
scale/rail acceptance was completed. An AX click can invoke Check without
moving focus, so click success was not substituted for keyboard evidence.
The post-close CUA timeout was resolved by the same exec handle's terminal
exit and destruction report, not by restarting the window.

## Minimal repair and regression

Both `ReferencesPanel.table` and `health_table` are read-only row-selection
tables. `setTabKeyNavigation(False)` returns Tab/Shift+Tab to the widget focus
chain while leaving arrow-key row selection intact. No controller, document,
save, compile, source identity or permission behavior changes.

Two new tests fail on baseline: health table cannot reach detail; quick-library
table cannot reach Insert. Red exec 14470 exits 1, 2 failures / 0.600 s.
`/tmp/icstex-v1-citation-native-focus-red-20260912-r1.log` SHA-256
`870fa6ba4f06ab963252aaf0059b483213067d918dd2fe86ec69adf469d959e6`.

The first repaired test reached the location list, but its Return-key
activation did not navigate in offscreen Qt. That failed observation is retained
in `/tmp/icstex-v1-citation-native-focus-focused-20260912-r1.log`, SHA-256
`ab9efcc6902032d13aa2690d42295409f530a2fb21c41220d856be3536cc7edf`.
The final test follows Tab to the explicit Locate button and Space to activate;
it does not claim that Return-in-list works natively or explain its failure.

```sh
QT_QPA_PLATFORM=offscreen python3 -m unittest \
  tests.test_gui_citation_health tests.test_citation_health tests.test_ui_visual -v
```

46 tests / 3.663 s / OK, exec 22710 exit 0. Forward/reverse focus, unchanged
arrow selection, explicit keyboard Locate to child.tex:2 and no compile
authorization pass. Log SHA-256
`714256816f19830427a50d23625722d5a6625f3324293d7ab8efb4b8b725b7cb` at
`/tmp/icstex-v1-citation-native-focus-focused-20260912-r2.log`.

The unchanged offscreen probe workflow also passes on the final app hash,
exec 25930 exit 0. Five scales × two requested sizes, zero outer horizontal
overflow, bounded action visibility and actual child navigation, unchanged
files and no compile authority. Small window requests clamp to 1080×720.
`/tmp/icstex-v1-citation-native-focus-layout-20260912-r1/report.json` SHA-256
`ab006dba37572607bc6fa1b57a9ec85e508cbd445e2147d7f657b3dda7e8658f`.
This mode programmatically reveals controls; it is not physical focus proof.

Required frozen regression, exec 74555 terminal exit 0:

```sh
python3 -m compileall -q app tests packaging/install_build_dependencies.py
QT_QPA_PLATFORM=offscreen PYTHONFAULTHANDLER=1 python3 -m unittest discover -s tests
git diff --check
```

1552 tests / 152.832 s / OK. Full log
`/tmp/icstex-v1-citation-native-focus-full-20260912-r1.log` SHA-256
`4a2cd243e9e41ad806066f01f3cad8b01e894c5416a68a445f77740e51a98328`.
Post-terminal app/app+tests hashes match; compileall, probe syntax and diff
checks pass. No Traceback/RuntimeError/RuntimeWarning/Fatal Python/ignored
exception/QObject/QThread failure matches in that full log. Existing font and
offscreen-plugin warnings are retained. The ten September Python crash reports
are unchanged. No citation probe process remains; all handles are terminal.
The final observer SHA-256 is
`c6e6c0db811b6c152d5c36ad731789f96048b2f585a16333016cd6054fc25b4e`.
The final 150%/minimum-window controls screenshot was inspected: Locate is fully
visible after programmatic scrolling, while long list text still uses its
internal scroll/tooltip. This does not close the native visibility gate.
HEAD and empty index remain unchanged; held candidate feed remains
`be57a732b6532e3247916530bdc688b7e05b1cd4ec0457b216a5020250140c03`.

## Post-fix native gate and next action

Native r3 started after the repair, but the first app-selection call returned
“The Mac is locked and automatic unlock could not unlock it.” No native test
actions followed. Only its identified PID 64756 was interrupted; exec 94853
ended at exit 130 with the expected KeyboardInterrupt and no completion report.
The probe's finally path closes its isolated window. Log SHA-256
`b0a4d8f70aa96c45c308135d44f61b7e0d3b546acb0cc357ebe03ca2140df81b` at
`/tmp/icstex-v1-citation-native-navigation-20260912-r3.log`.
This is a new lock observation, not the earlier resolved keyboard-contention
question and not a post-fix pass. No repeated unlock attempts were made.

After manual unlock, resume the corrected probe in a fresh output directory:
verify actual Tab/Shift+Tab through tables/detail/list/Locate, explicit keyboard
child navigation, nine-tool arrow navigation and all five scale tiers. Inspect
actual focus visibility, not only AX enumeration or offscreen geometry. Keep
the separate 200% PDF quality observation, R3 historical/AX boundaries, R5
maintainer decision and external gates explicit. No M6/V1/release claim.
