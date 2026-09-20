# M6 restricted LuaLaTeX path-policy review

2026-09-11. **Redirecting Lua cache roots to the TeX distribution is not a
read-only compatibility fix.** On this host it also makes the distribution
resource name pass the output-path check. The application was not changed and
restricted LuaLaTeX compatibility remains open.

## Scope and source

This is a read-only follow-up to the
[installed-engine diagnosis](v1-m6-lualatex-verification-2026-09-11.md), not a new
compilation or native UI test. The test-triage skill led to the smallest relevant
path-policy check rather than another full regression. The repository harness is
Python unittest, not Xcode or SwiftPM.

Current app tree:
`489657f34516f5bfeee0934b84a26885e217e8ff3ea7cad05f3f1297819d0085`;
app+tests:
`136e1892c4de31d04db0de8a2a40e97f7d58877238e90ab0784e161fc31ad59a`.
HEAD remains `3bde2b5d25803262dedef89a081ee6ffbe2b6967`; increments uncommitted.

Live source confirms `CompileManager(restricted_io=False)` is the ordinary
default, whereas `AgentWorkspace.compile_project` supplies `restricted_io=True`.
D015 and SECURITY.md require the latter. The R5 failure is specifically the
protected engine path; no new claim about ordinary GUI LuaLaTeX success or
failure is made here.

## Observed name-policy result

macOS 26.6.1 arm64, Kpathsea 6.4.1. All cases retain
`openin_any=p` and `openout_any=p`. Candidate overrides apply only to individual
`kpsewhich` name-check child processes, never a compiler or global setting.

| Child environment | Installed resource input/output name accepted | Project-relative input/output | Parent-sentinel input/output |
| --- | --- | --- | --- |
| Current protected environment | No / No | Yes / Yes | No / No |
| Only TEXMFSYSVAR redirected to texmf-dist | Yes / Yes | Yes / Yes | No / No |
| Only TEXMFVAR redirected to texmf-dist | Yes / Yes | Yes / Yes | No / No |

Each predicate exits 0 for accepted, 1 for denied; all 18 observations completed,
and the containing command exited 0. These are filename-policy decisions, not
actual read/write permission or successful-write tests. No TeX/Lua file-open
operation was attempted. The host did read the installed resource to compare its
hash before/after; the raw report's shorthand “no file-open/write attempt” refers
to the name-check operation, not those host hash reads.

The installed Kpathsea manual's “Safe filenames” section explains that extended
mode uses TEXMFVAR/TEXMFSYSVAR for absolute names in both input and output checks.
Inspected local primary source:
`/usr/local/texlive/2025/texmf-dist/doc/kpathsea/kpathsea.html`, lines 3754–3828;
SHA-256 `40bf059a2cafc8eafe4599da26d29b39efba1878a1a731c99e77ad96f2bf7d5a`.

This rules out treating either cache-root override as a read-only allowlist.
It does not prove OS write permission to texmf-dist, an actual exploit, complete
Lua sandboxing, or that such an override would make full LuaLaTeX compile.

## Retained evidence and reproduction

Captured command stdout is retained byte-for-byte in
[data/v1/m6-lualatex-policy-names-2026-09-11.json](data/v1/m6-lualatex-policy-names-2026-09-11.json),
SHA-256 `bf3e36d8024b6162a213c541ee5ad48fcf8b28027e1b4057c7907cc98b094b7b`.
The synthetic fixture is reused only as a working directory; no file is created
or edited by this command. The installed ScriptExtensions.txt hash is unchanged:
`049117ce26b9769fe2749b06eef51a50a89faef4a97764dd2d81daa715980700`.

```sh
python3 - <<'PY'
from pathlib import Path
import hashlib, json, platform, subprocess
from app.core.compiler import CompileManager
from app.core.latex_tools import LaTeXEngine
root = Path('/tmp/icstex-v1-lualatex-restricted-r5/raw-lua/probe.tex')
assert root.is_file()
manager = CompileManager(root, engine=LaTeXEngine.LUALATEX, restricted_io=True)
base = manager._compile_environment(None, restricted_io=True)
assert base['openin_any'] == base['openout_any'] == 'p'
kpse = '/Library/TeX/texbin/kpsewhich'
resource = Path(subprocess.run([kpse, 'ScriptExtensions.txt'], env=base, cwd=root.parent, capture_output=True, text=True, check=True, timeout=10).stdout.strip())
distribution = Path('/usr/local/texlive/2025/texmf-dist')
assert resource.is_relative_to(distribution)
before = hashlib.sha256(resource.read_bytes()).hexdigest()
checks = []
for label, changes in [('current', {}), ('candidate-TEXMFSYSVAR', {'TEXMFSYSVAR': str(distribution)}), ('candidate-TEXMFVAR', {'TEXMFVAR': str(distribution)})]:
 env = {**base, **changes}
 for name_label, name in [('installed-resource', str(resource)), ('project-relative', 'local-copy.txt'), ('parent-sentinel', '../sentinel.txt')]:
  for operation in ['in', 'out']:
   command = [kpse, '--safe-extended-' + operation + '-name=' + name]
   result = subprocess.run(command, env=env, cwd=root.parent, capture_output=True, text=True, timeout=10)
   assert result.returncode in (0, 1), (command, result.returncode, result.stderr)
   checks.append({'environment': label, 'child_overrides': changes, 'name': name_label, 'path': name, 'operation': operation, 'returncode': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr})
assert hashlib.sha256(resource.read_bytes()).hexdigest() == before
report = {'kind': 'Read-only kpsewhich name-policy checks; no compile and no file-open/write attempt', 'platform': platform.platform(), 'kpsewhich_version': subprocess.run([kpse, '--version'], capture_output=True, text=True, check=True, timeout=10).stdout.splitlines()[0], 'restricted_environment': {key: base[key] for key in ['openin_any', 'openout_any']}, 'resource_sha256_before_after': before, 'checks': checks}
print(json.dumps(report, indent=2))
PY
```

## Disposition

Do not implement the tested overrides, change openin_any/openout_any, patch the
installed loader, copy distribution resources as a product workaround, or
silently switch engines. A restricted-engine compatibility solution still needs
a bounded maintainer decision and independent read/write boundary acceptance.

No app/test source, installed dependencies, foreground window, student file,
Git index/HEAD, held feed or release state changed. The preceding 1550-test
receipt still matches the unchanged app+tests tree; this documentation and
name-policy check is not a new full test run. The original R5 engine-failure
receipt keeps its older source identity. R1/R2 native continuation is still
paused pending keyboard-use clarification; no completed default-save/Inspector
case was repeated.
