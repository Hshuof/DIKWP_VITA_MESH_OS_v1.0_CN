from __future__ import annotations

from datetime import datetime, timezone, timedelta
import base64
from hashlib import sha256
import json
from pathlib import Path

from .engine import VitalityEngine
from .crypto import sign_packet
from .ledger import VitalityLedger
from .models import EventType, PulsePacket


def run_demo(outdir: Path) -> dict:
    outdir.mkdir(parents=True, exist_ok=True)
    ledger_path = outdir / "demo_vitality.db"
    if ledger_path.exists():
        ledger_path.unlink()
    engine = VitalityEngine()
    # Fixed 32-byte Ed25519 seed keeps the reference demo reproducible.
    demo_private = base64.b64encode(sha256(b"DIKWP-VITA-MESH-DEMO-KEY-v1").digest()).decode()
    base = datetime(2026, 7, 16, 8, 0, tzinfo=timezone.utc)
    specs = [
        (EventType.PAGE_ACCESS, 120, "web-cluster-cn", {"source": "github_pages"}),
        (EventType.RELEASE_DOWNLOAD, 42, "github-observer", {"asset": "v1.0.0.zip"}),
        (EventType.CLONE, 12, "github-observer", {"source": "traffic_api"}),
        (EventType.RUN_PROOF, 1, "node-hainan", {"proof_valid": True, "platform": "linux"}),
        (EventType.RUN_PROOF, 1, "node-paris", {"proof_valid": True, "platform": "macos"}),
        (EventType.FEEDBACK, 3, "node-singapore", {"semantic_nutrient": "use_case"}),
        (EventType.CONTRADICTION, 1, "node-berlin", {"claim": "access != adoption"}),
        (EventType.MIRROR_HEARTBEAT, 1, "mirror-hainan", {"uptime_days": 31}),
        (EventType.MIRROR_HEARTBEAT, 1, "mirror-paris", {"uptime_days": 31}),
        (EventType.PR_MERGED, 2, "maintainer-community", {"scope": "privacy_and_docs"}),
        (EventType.CITATION, 1, "research-node", {"type": "technical_report"}),
        (EventType.MAINTAINER_RELEASE, 1, "steward-multisig", {"release": "v1.0.1"}),
    ]
    with VitalityLedger(ledger_path) as db:
        for idx, (etype, count, node, payload) in enumerate(specs):
            packet = PulsePacket(
                event_type=etype,
                artifact_id="DIKWP-VITA-MESH",
                artifact_version="1.0.0",
                timestamp=base + timedelta(hours=idx),
                node_id=node,
                day_token=f"demo-{idx}-{etype.value}",
                count=count,
                consent_scope="public",
                payload=payload,
            )
            if etype in {EventType.MIRROR_HEARTBEAT, EventType.CITATION, EventType.MAINTAINER_RELEASE}:
                packet = sign_packet(packet, demo_private)
            else:
                packet = packet.finalized()
            weight = engine.accepted_weight(packet, db)
            db.append(packet, weight)
        state = engine.compute_state(db, "DIKWP-VITA-MESH")
        fixed_generated_at = base + timedelta(hours=15)
        state.generated_at = fixed_generated_at
        proposals = engine.proposals(state)
        for proposal in proposals:
            proposal.generated_at = fixed_generated_at
        bundle = db.export_bundle("demo-origin", "DIKWP-VITA-MESH")
        bundle.generated_at = fixed_generated_at
    (outdir / "vitality_state.json").write_text(json.dumps(state.model_dump(mode="json"), ensure_ascii=False, indent=2), encoding="utf-8")
    (outdir / "evolution_proposals.json").write_text(json.dumps([p.model_dump(mode="json") for p in proposals], ensure_ascii=False, indent=2), encoding="utf-8")
    (outdir / "federation_bundle.json").write_text(json.dumps(bundle.model_dump(mode="json"), ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ledger": str(ledger_path), "state": state.model_dump(mode="json"), "proposal_count": len(proposals)}
