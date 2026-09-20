# PDF pipeline screenshot evidence

The three original native-window screenshots are retained only in the local
verification workspace. Their compile consoles contain machine-local temporary
paths and raw synthetic build logs, so the PNG files are excluded from Git.
The originals were not redacted, renamed or regenerated for publication.

The published measurements and evidence boundaries are in
[`../pdf-pipeline-2026-09-08.json`](../pdf-pipeline-2026-09-08.json) and
[`../../response-optimization-verification-2026-09-08.md`](../../response-optimization-verification-2026-09-08.md).
Screenshot paths in that JSON identify local-only evidence, not downloadable
repository files. Use [`../../../tools/bench_pdf_pipeline.py`](../../../tools/bench_pdf_pipeline.py)
to run the synthetic probe on another machine; new timings are separate samples.
