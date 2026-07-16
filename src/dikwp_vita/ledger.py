from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from typing import Dict, Iterable, List, Optional, Tuple

from .crypto import verify_packet
from .models import FederationBundle, PulsePacket


SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
  event_id TEXT PRIMARY KEY,
  event_type TEXT NOT NULL,
  artifact_id TEXT NOT NULL,
  artifact_version TEXT NOT NULL,
  timestamp TEXT NOT NULL,
  node_id TEXT NOT NULL,
  day_token TEXT,
  count INTEGER NOT NULL,
  consent_scope TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  public_key TEXT,
  signature TEXT,
  verified INTEGER NOT NULL DEFAULT 0,
  accepted_weight REAL NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_artifact ON events(artifact_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_day_token ON events(day_token);
CREATE TABLE IF NOT EXISTS metadata (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
"""


class VitalityLedger:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "VitalityLedger":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def count_for_day_token(self, day_token: str, event_type: str) -> int:
        row = self.conn.execute(
            "SELECT COALESCE(SUM(count),0) AS total FROM events WHERE day_token=? AND event_type=?",
            (day_token, event_type),
        ).fetchone()
        return int(row["total"])

    def append(self, packet: PulsePacket, accepted_weight: float = 1.0) -> Tuple[bool, str]:
        packet = packet.finalized() if not packet.event_id else packet
        verified = int(verify_packet(packet))
        try:
            self.conn.execute(
                """INSERT INTO events(
                    event_id,event_type,artifact_id,artifact_version,timestamp,node_id,day_token,
                    count,consent_scope,payload_json,public_key,signature,verified,accepted_weight,created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    packet.event_id,
                    packet.event_type.value,
                    packet.artifact_id,
                    packet.artifact_version,
                    packet.timestamp.isoformat(),
                    packet.node_id,
                    packet.day_token,
                    packet.count,
                    packet.consent_scope,
                    json.dumps(packet.payload, ensure_ascii=False, sort_keys=True),
                    packet.public_key,
                    packet.signature,
                    verified,
                    float(accepted_weight),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            self.conn.commit()
            return True, packet.event_id or ""
        except sqlite3.IntegrityError:
            return False, packet.event_id or ""

    def all_events(self, artifact_id: Optional[str] = None) -> List[dict]:
        if artifact_id:
            rows = self.conn.execute(
                "SELECT * FROM events WHERE artifact_id=? ORDER BY timestamp,event_id", (artifact_id,)
            ).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM events ORDER BY timestamp,event_id").fetchall()
        events = []
        for row in rows:
            d = dict(row)
            d["payload"] = json.loads(d.pop("payload_json"))
            events.append(d)
        return events

    def packets(self, artifact_id: Optional[str] = None) -> List[PulsePacket]:
        result = []
        for row in self.all_events(artifact_id):
            result.append(
                PulsePacket(
                    event_type=row["event_type"],
                    artifact_id=row["artifact_id"],
                    artifact_version=row["artifact_version"],
                    timestamp=row["timestamp"],
                    node_id=row["node_id"],
                    day_token=row["day_token"],
                    count=row["count"],
                    consent_scope=row["consent_scope"],
                    payload=row["payload"],
                    public_key=row["public_key"],
                    signature=row["signature"],
                    event_id=row["event_id"],
                )
            )
        return result

    def merkle_root(self, artifact_id: Optional[str] = None) -> str:
        ids = [e["event_id"] for e in self.all_events(artifact_id)]
        if not ids:
            return sha256(b"").hexdigest()
        level = [bytes.fromhex(i) for i in sorted(ids)]
        while len(level) > 1:
            if len(level) % 2:
                level.append(level[-1])
            level = [sha256(level[i] + level[i + 1]).digest() for i in range(0, len(level), 2)]
        return level[0].hex()

    def export_bundle(self, source_node: str, artifact_id: Optional[str] = None) -> FederationBundle:
        return FederationBundle(
            source_node=source_node,
            merkle_root=self.merkle_root(artifact_id),
            events=self.packets(artifact_id),
        )

    def import_bundle(self, bundle: FederationBundle, weight_resolver) -> Dict[str, int]:
        inserted = 0
        duplicates = 0
        rejected = 0
        for packet in bundle.events:
            try:
                weight = weight_resolver(packet, self)
                ok, _ = self.append(packet, weight)
                if ok:
                    inserted += 1
                else:
                    duplicates += 1
            except Exception:
                rejected += 1
        return {"inserted": inserted, "duplicates": duplicates, "rejected": rejected}
