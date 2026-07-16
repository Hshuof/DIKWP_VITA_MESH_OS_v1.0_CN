from pathlib import Path
from dikwp_vita.crypto import generate_keypair, sign_packet, verify_packet
from dikwp_vita.engine import VitalityEngine
from dikwp_vita.ledger import VitalityLedger
from dikwp_vita.models import PulsePacket

def test_sign_verify():
    private, public = generate_keypair()
    p = PulsePacket(event_type="citation", artifact_id="X", artifact_version="1", node_id="node-1", consent_scope="public", payload={})
    s = sign_packet(p, private)
    assert verify_packet(s)
    assert s.public_key == public

def test_federation_union(tmp_path: Path):
    engine = VitalityEngine()
    with VitalityLedger(tmp_path/"a.db") as a:
        p = PulsePacket(event_type="feedback", artifact_id="X", artifact_version="1", node_id="node-1", day_token="d", consent_scope="anonymous", payload={}).finalized()
        a.append(p, engine.accepted_weight(p, a))
        bundle = a.export_bundle("node-a", "X")
    with VitalityLedger(tmp_path/"b.db") as b:
        result = b.import_bundle(bundle, engine.accepted_weight)
        assert result["inserted"] == 1
        result2 = b.import_bundle(bundle, engine.accepted_weight)
        assert result2["duplicates"] == 1
