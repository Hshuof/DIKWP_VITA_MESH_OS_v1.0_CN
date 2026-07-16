from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Dict, Iterable, List

from .models import EventType, PulsePacket


# Expected log format (no IP, cookie, user-agent or referrer):
# 2026-07-16T08:12:33+00:00\tGET\t/index.html\t200
_LINE_RE = re.compile(
    r"^(?P<timestamp>\S+)\t(?P<method>GET|HEAD)\t(?P<path>\S+)\t(?P<status>\d{3})\s*$"
)


def _load_state(path: Path) -> Dict[str, object]:
    if not path.exists():
        return {"schema_version": "1.0", "files": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def _save_state(path: Path, state: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def scan_new_records(log_path: Path, state_path: Path, path_regex: str) -> Counter[str]:
    """Read only newly appended privacy-minimized log lines and count matching dates.

    The state stores only inode and byte offset. No visitor identifier is extracted or persisted.
    Log rotation is detected by inode change or size regression.
    """
    log_path = log_path.resolve()
    state = _load_state(state_path)
    files = state.setdefault("files", {})
    assert isinstance(files, dict)
    key = str(log_path)
    prior = files.get(key, {}) if isinstance(files.get(key, {}), dict) else {}
    stat = log_path.stat()
    inode = int(getattr(stat, "st_ino", 0))
    old_inode = int(prior.get("inode", -1))
    old_offset = int(prior.get("offset", 0))
    offset = old_offset if old_inode == inode and stat.st_size >= old_offset else 0
    matcher = re.compile(path_regex)
    counts: Counter[str] = Counter()
    with log_path.open("r", encoding="utf-8", errors="replace") as handle:
        handle.seek(offset)
        for line in handle:
            match = _LINE_RE.match(line)
            if not match:
                continue
            status = int(match.group("status"))
            if not 200 <= status < 400:
                continue
            if not matcher.search(match.group("path")):
                continue
            counts[match.group("timestamp")[:10]] += 1
        new_offset = handle.tell()
    files[key] = {
        "inode": inode,
        "offset": new_offset,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "path_regex": path_regex,
    }
    _save_state(state_path, state)
    return counts


def build_packets(
    counts: Counter[str],
    event_type: EventType,
    artifact_id: str,
    artifact_version: str,
    node_id: str,
    path_regex: str,
) -> List[PulsePacket]:
    packets: List[PulsePacket] = []
    for date, count in sorted(counts.items()):
        if count <= 0:
            continue
        token = sha256(f"{node_id}|{date}|{event_type.value}|{path_regex}".encode()).hexdigest()
        packets.append(
            PulsePacket(
                event_type=event_type,
                artifact_id=artifact_id,
                artifact_version=artifact_version,
                node_id=node_id,
                day_token=token,
                count=count,
                consent_scope="public",
                payload={
                    "source": "privacy_minimal_access_log",
                    "date": date,
                    "path_regex": path_regex,
                    "privacy": "timestamp_method_uri_status_only",
                },
            ).finalized()
        )
    return packets
