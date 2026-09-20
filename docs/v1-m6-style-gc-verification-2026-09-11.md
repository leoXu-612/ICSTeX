# M6 synchronous style traversal and cyclic-widget lifetime

A cyclic-widget collection failure during Qt stylesheet traversal is reproduced
and repaired with a temporary reference snapshot. It is a concrete R3 stability
improvement, **not proof of the exact object behind every historical crash**.
The separate old timer-dispatch crashes, scoped AX limitation and other M6
acceptance items remain open. No Git mutation, package, installed-app replacement,
dependency change, signing or publication was performed.

## Source and bounded change

Branch `codex/v1-development`, HEAD `3bde2b5d25803262dedef89a081ee6ffbe2b6967`;
shared changes remain uncommitted. Baseline app
`bc2a7b3e00f62f2e0114d1cba4804a60844756c27ab6a6bfcf97a32e43e43f74`.
Final app `f71ec949f96011e0c510bd1d953d2b5e56e53d0597e6106ca577a77d236f6ab4`;
app+tests `e5d34abda609ffb76b6ab398e0c1acfc760d46279aacb8cf32e5d4fa8d36cb49`.
Digest convention: sorted relative Python paths, NUL, bytes, NUL; app then tests.
Environment: macOS 26.6.1 arm64, Python 3.12.6, PySide6/Qt 6.11.1.

Only `app/gui/theme/ui_scale_manager.py` changes application behavior: a local
`QApplication.allWidgets()` snapshot keeps existing Python wrappers alive during
the synchronous font/metrics/stylesheet update and scale notification. It is
released afterward, not stored in the manager. It does not disable garbage
collection, change Qt ownership, defer arbitrary user actions or retain a window
after the call. Scale tiers, base-font calculation, style cache, PDF/source and
close guards are unchanged. It does not protect arbitrary explicit native
deletion in callbacks or provide a universal QObject lifetime guarantee.

## Historical evidence and new causal test

Read-only inspection of the original reports found:

- `Python-2026-09-10-134038.ips` / PID 75753 and `...134729.ips` / PID 77194
  fail in QCoreApplication::sendEvent through QTimerInfoList::activateTimers.
  The latter contains 115 threads, including 49 QFileInfoGatherer and 49 QThread.
- `Python-2026-09-11-134542.ips` / PID 66375 fails in internal QtWidgets code
  reached by QApplication.setStyleSheet, at the scale test recorded in its log.
  It contains 343 threads, including 160 QFileInfoGatherer and 168 QThread.
  These retained-thread observations are consistent with the independently
  repaired closed-window retention; they do not prove a particular crash cause.

Qt 6.11.1's [stylesheet implementation](https://github.com/qt/qtbase/blob/v6.11.1/src/widgets/styles/qstylesheetstyle.cpp)
copies cached raw QObject pointers, then polishes widgets, sends StyleChange and
visits children. A Python callback can run cyclic GC before this traversal ends.
The already-installed QtWidgets arm64 UUID matches the historical crash report:
`43a0ac89-bcce-3f63-9b9c-4067bfbf8aac`. The old trace and new reproduction reach
the same internal traversal/caller range, but their recorded instruction offsets
differ and the old report does not identify which object was reclaimed.

The extended existing lifecycle probe creates synthetic unparented QLabel
cycles, explicitly defers their GC to a StyleChange callback, and logs each
destruction. This is controlled fault injection, not normal workload timing.
The ordinary probe mode retains normal GC. No student data is read or created.

| Run | App / control | Result |
| --- | --- | --- |
| Orphan r1, 24 cyclic widgets | Baseline, no held snapshot | SIGSEGV / exit 139 during first scale; all 24 destruct during that scale |
| Held control r1, same 24 widgets | Baseline, probe holds wrappers | Exit 0; destruction delayed until final GC |
| Fixed r1, 24 closed windows, 12 in-style collections | Final app, **no probe hold** | Exit 0; no retained closed MainWindow, 24 orphans released only at final GC |
| Natural r1, 24 closed windows | Final app, no forced GC/orphans/hold | Exit 0; only surviving MainWindow remains |
| Cocoa r1, 6 closed windows, 8 in-style collections, 12 orphans | Final app, **no probe hold** | Exit 0; all 12 orphans released at final GC, no retained closed window |

The intentional baseline fault is exec 67228 / PID 6992. Its new report is
`Python-2026-09-11-175448.ips`, incident
`D67EC84D-26F2-4C6A-BED1-D8613B975416`, SHA-256
`59f32ce501d351ba714ab137ebdaa9f61fe722493cd3564ce6b9b09f44c09ef3`.
Faulthandler names apply_scale's setStyleSheet call. This new diagnostic crash
must not be hidden as an unexplained post-fix failure or removed from inventory.

## Regression and actual window evidence

Two tests extend `tests/test_gui_editor.py::WindowLifetimeTests`:

- The safe boundary test collects cycles before actual font and style calls,
  requiring wrappers to remain valid during both and collectible after return.
  It failed on baseline at the font boundary, then passes. Application GC policy
  must remain unchanged. A first attempt lacked a real MainWindow's manager and
  errored in setup; that is not the red product assertion.
- A subprocess performs actual Qt StyleChange dispatch with forced collection.
  A regression becomes a failed subprocess assertion rather than killing the
  entire test runner. It requires no probe-side keepalive, all eight owned
  orphan destructions only at final GC, and no retained closed window.
  Its first widget-total assertion incorrectly assumed Qt's three transient
  widgets would persist. The final test tracks exact owned orphan weakrefs and
  destructions instead; it does not lower the lifetime assertion.

Focused command, 55 tests / 4.910s / OK, exec 10064 exit 0:

```sh
QT_QPA_PLATFORM=offscreen PYTHONFAULTHANDLER=1 python3 -m unittest \
  tests.test_gui_editor.WindowLifetimeTests tests.test_ui_scale \
  tests.test_ui_visual tests.test_layout tests.test_theme -v
```

Log `/tmp/icstex-v1-style-pin-focused-r2.log`, SHA-256
`8c30d75f538f54c64778f4661a79786639038b7751f26a9d2a2e7c91ce0c0d92`.
Safe boundary red `/tmp/icstex-v1-style-pin-red-r2.log`, SHA-256
`faf744ceb88e574e3b6c43273fa42944eeae478bda553eec8f90a9f4e28fb436`.

Native command, exec 9692 / PID 7614 / explicit exit 0:

```sh
QT_QPA_PLATFORM=cocoa PYTHONFAULTHANDLER=1 python3 tools/probe_qt_style_lifecycle.py \
  --native --output /tmp/icstex-v1-style-pin-native-r1 --windows 3 --cycles 2 \
  --collect-during-style --orphan-widgets 12 --expect-released
```

The source-only window uses isolated settings and empty synthetic state. Its
final Cocoa-rendered welcome/workspace screenshot was inspected after scaling;
all test windows were cleaned up. This is not physical keyboard, IME, AX scan,
VoiceOver or populated-project performance acceptance. The pre-existing scoped
Cocoa AX mitigation warning remains; it is not suppressed or described as fixed.

## Artifact pointers and final checks

All reports remain local. Successful probe exit means its declared assertions,
not all M6 requirements, passed. `max_rss` remains a high-water mark, not evidence
of current allocation or all memory returned to the OS. No benchmark percentage.

| Local receipt | SHA-256 |
| --- | --- |
| `/tmp/icstex-v1-style-orphans-r1.log` | `e6307581de36eb32f0cb926849139f96c1ec78428619eb64a3c52036f9e3c920` |
| `/tmp/icstex-v1-style-orphans-held-r1/result.json` | `2cdf2608088594b44b0448ff5886ea45be2d1c83ab38d2512648d51ea47be442` |
| `/tmp/icstex-v1-style-orphans-fixed-r1/result.json` | `d48b987fa888da0896b5b1a869f7a5df52be085792de3679e3046cd21df3b09c` |
| `/tmp/icstex-v1-style-pin-natural-r1/result.json` | `dd03cc4464bac1b2a2904765c38a0cac253dfac108dd2a36aae2d52f813ba45f` |
| `/tmp/icstex-v1-style-pin-native-r1/result.json` | `4748774cd774fcccf83bcbd505b7a6c5fdf688759f2ce466818e35d490c147c6` |
| Native `surviving-window-after.png` | `3e5758bbe20149f6b352d71e4c4a7a648cd7c7e09fdccdeff19c8bcb66ebfcc8` |
| Probe revision used by native receipt | `775153695cd4415b79e63201526e95a703fcafed8f946286eee26e6af88a6f6d` |

The table's probe hash identifies the native receipt's revision. A subsequent
probe-only portability adjustment makes Unix `resource` optional: unavailable
RSS is null and all lifecycle assertions still run. Final probe SHA-256 is
`54fbea4560b2c0781eb6168a20655de18232a8d715052c51c8dafa8d5d0f5a37`.
Four lifetime tests pass again (exec 76622, 2.031s, exit 0). A normal-entry
subprocess with resource import deliberately unavailable passes (exec 13447,
exit 0): all RSS values null, four orphan destructions at final GC, no retained
closed window. Report `/tmp/icstex-v1-style-pin-no-resource-r2/result.json`.
This branch test is not Windows-native acceptance.

The first import simulation was invalid: restoring `patch.dict(sys.modules)`
after importing the probe removed the newly imported Qt modules before creating
QApplication. A read-only control confirmed QtWidgets present inside the mock
and absent afterward. That harness failed during initial setStyle conversion,
before any cyclic widget/scale injection, in Shiboken conversion code. Preserve
`Python-2026-09-11-180815.ips` / PID 8869, incident
`09AAC340-8882-4B7D-989C-9E56B3FFB0F7`; do not treat it as a scale-pin regression
or delete it. The corrected normal-entry run never unloads the Qt modules.

Required compileall, probe syntax and diff checks pass. Frozen full:

```sh
QT_QPA_PLATFORM=offscreen PYTHONFAULTHANDLER=1 nice -n 10 python3 -m unittest discover -s tests -v
```

**1497 tests / 125.290s / OK**, exec 19099 / PID 9023, explicit shell/tool exit 0.
Log `/tmp/icstex-v1-style-pin-suite-r2.log`, SHA-256
`7774a0b994ac01273a48430678ea11a2758ec604b38f2a3335a0ed6c2e054d21`.
The pre-portability full also passed 1497 / 124.943s, exec 3272 exit 0;
only this second full includes the final portable probe revision.
Post-terminal app/app+tests digests match; compileall/probe syntax/diff pass again.
No Traceback/RuntimeError/RuntimeWarning/fatal or QObject/QThread failure in the
full log; ordinary offscreen plugin warnings remain. All probe/test handles
are terminal, including the intentional baseline fault; do not reopen them.

Final Python crash inventory contains the five prior reports, the intentional
pre-fix reproduction and the invalid module-unloading harness failure above,
with no additional report. Held candidate
feed remains `be57a732b6532e3247916530bdc688b7e05b1cd4ec0457b216a5020250140c03`.
Index empty, HEAD unchanged. No installation, release or broad stability claim.

## Remaining work and rollback

The reproduced style/GC traversal defect is addressed locally. Do not declare
the exact historical stylesheet object or the old timer-dispatch failures
proven fixed. R3 retains timer causality and the scoped AX boundary. Further
timer work needs a new diagnostic question, not blind full-suite repetition.
Next bounded independent work is R1's default idle-save/partial composition
matrix; R2 physical focus/high-scale navigation and R5 restricted LuaLaTeX remain.
R6 and the M7 readiness handoff must preserve all external E1–E4 and release gates.

Rollback only the local live-widget snapshot and its targeted tests/probe
extensions, not earlier lifetime or shared changes. Suggested commit, not run:
`fix(gui): retain widget wrappers during synchronous UI scaling`.
