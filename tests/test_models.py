from dikwp_vita.models import PulsePacket

def test_event_id_is_deterministic():
    p = PulsePacket(event_type="page_access", artifact_id="A", artifact_version="1", timestamp="2026-01-01T00:00:00Z", node_id="node-1", day_token="d", consent_scope="anonymous", payload={})
    assert p.computed_event_id() == p.computed_event_id()
    assert len(p.computed_event_id()) == 64

def test_tampered_event_id_rejected():
    try:
        PulsePacket(event_type="page_access", artifact_id="A", artifact_version="1", timestamp="2026-01-01T00:00:00Z", node_id="node-1", consent_scope="anonymous", payload={}, event_id="0"*64)
    except ValueError:
        return
    raise AssertionError("tampered event_id should fail")

def test_payload_size_is_bounded():
    try:
        PulsePacket(
            event_type="feedback",
            artifact_id="A",
            artifact_version="1",
            node_id="node-1",
            consent_scope="anonymous",
            payload={"text": "x" * 20000},
        )
    except ValueError:
        return
    raise AssertionError("oversized payload should fail")
