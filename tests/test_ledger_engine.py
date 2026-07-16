from pathlib import Path
from dikwp_vita.engine import VitalityEngine
from dikwp_vita.ledger import VitalityLedger
from dikwp_vita.models import PulsePacket

def add(db, engine, event_type, node, count=1, payload=None):
    p = PulsePacket(event_type=event_type, artifact_id="X", artifact_version="1", timestamp="2026-01-01T00:00:00Z", node_id=node, day_token=f"{node}-{event_type}", count=count, consent_scope="anonymous", payload=payload or {}).finalized()
    w = engine.accepted_weight(p, db)
    return db.append(p, w)

def test_union_and_state(tmp_path: Path):
    engine = VitalityEngine()
    with VitalityLedger(tmp_path/"a.db") as db:
        assert add(db, engine, "page_access", "node-1", 10)[0]
        assert not add(db, engine, "page_access", "node-1", 10)[0]
        add(db, engine, "run_proof", "node-2", 1, {"proof_valid": True})
        add(db, engine, "feedback", "node-3", 1)
        state = engine.compute_state(db, "X")
        assert state.event_count == 3
        assert state.unique_nodes == 3
        assert 0 <= state.vitality_score <= 100
        assert len(state.merkle_root) == 64

def test_local_pulse_rejected_from_public_ledger(tmp_path: Path):
    engine = VitalityEngine()
    with VitalityLedger(tmp_path/"a.db") as db:
        p = PulsePacket(event_type="page_access", artifact_id="X", artifact_version="1", node_id="node-1", consent_scope="local", payload={})
        try:
            engine.accepted_weight(p, db)
        except ValueError:
            return
        raise AssertionError("local pulse must stay local")
