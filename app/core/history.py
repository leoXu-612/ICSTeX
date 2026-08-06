from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re


HISTORY_DIR = ".icstex/history"
MAX_SNAPSHOTS = 40


@dataclass(frozen=True)
class HistorySnapshot:
    id: str
    source_path: Path
    snapshot_path: Path
    label: str
    created_at: datetime
    size: int
    sha256: str


def create_snapshot(source_path: Path, content: str, label: str, *, max_snapshots: int = MAX_SNAPSHOTS) -> HistorySnapshot | None:
    source_path = source_path.expanduser().resolve()
    project_dir = source_path.parent
    bucket = _bucket_for(source_path, project_dir)
    bucket_dir = project_dir / HISTORY_DIR / bucket
    bucket_dir.mkdir(parents=True, exist_ok=True)

    sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
    snapshots = list_snapshots(source_path)
    if snapshots and snapshots[0].sha256 == sha and snapshots[0].label == label:
        return None

    now = datetime.now(timezone.utc)
    snapshot_id = f"{now.strftime('%Y%m%dT%H%M%SZ')}-{sha[:10]}"
    snapshot_path = bucket_dir / f"{snapshot_id}.tex"
    snapshot_path.write_text(content, encoding="utf-8")
    entry = {
        "id": snapshot_id,
        "source_path": str(source_path),
        "snapshot_path": str(snapshot_path),
        "label": label,
        "created_at": now.isoformat(),
        "size": len(content.encode("utf-8")),
        "sha256": sha,
    }
    manifest = _read_manifest(bucket_dir)
    manifest.insert(0, entry)
    _write_manifest(bucket_dir, manifest)
    _prune(bucket_dir, max_snapshots)
    return _snapshot_from_entry(entry)


def list_snapshots(source_path: Path) -> list[HistorySnapshot]:
    source_path = source_path.expanduser().resolve()
    bucket_dir = source_path.parent / HISTORY_DIR / _bucket_for(source_path, source_path.parent)
    snapshots: list[HistorySnapshot] = []
    for entry in _read_manifest(bucket_dir):
        try:
            snapshot = _snapshot_from_entry(entry)
        except (KeyError, ValueError, TypeError):
            continue
        if snapshot.snapshot_path.exists():
            snapshots.append(snapshot)
    return snapshots


def read_snapshot(snapshot: HistorySnapshot) -> str:
    return snapshot.snapshot_path.read_text(encoding="utf-8")


def _bucket_for(source_path: Path, project_dir: Path) -> str:
    try:
        rel = source_path.relative_to(project_dir)
    except ValueError:
        rel = Path(source_path.name)
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", str(rel)).strip("._")
    return value or source_path.stem or "document"


def _manifest_path(bucket_dir: Path) -> Path:
    return bucket_dir / "manifest.json"


def _read_manifest(bucket_dir: Path) -> list[dict[str, object]]:
    path = _manifest_path(bucket_dir)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def _write_manifest(bucket_dir: Path, entries: list[dict[str, object]]) -> None:
    _manifest_path(bucket_dir).write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")


def _snapshot_from_entry(entry: dict[str, object]) -> HistorySnapshot:
    return HistorySnapshot(
        id=str(entry["id"]),
        source_path=Path(str(entry["source_path"])),
        snapshot_path=Path(str(entry["snapshot_path"])),
        label=str(entry["label"]),
        created_at=datetime.fromisoformat(str(entry["created_at"])),
        size=int(entry["size"]),
        sha256=str(entry["sha256"]),
    )


def _prune(bucket_dir: Path, max_snapshots: int) -> None:
    manifest = _read_manifest(bucket_dir)
    keep = manifest[:max(1, max_snapshots)]
    remove = manifest[max(1, max_snapshots):]
    for entry in remove:
        snapshot_path = Path(str(entry.get("snapshot_path", "")))
        if snapshot_path.exists():
            try:
                snapshot_path.unlink()
            except OSError:
                pass
    _write_manifest(bucket_dir, keep)
