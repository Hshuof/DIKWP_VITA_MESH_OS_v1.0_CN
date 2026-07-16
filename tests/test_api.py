from pathlib import Path
from fastapi.testclient import TestClient
from dikwp_vita.collector import create_app
from dikwp_vita.models import PulsePacket

def test_api_pulse_and_state(tmp_path: Path):
    app = create_app(tmp_path/"api.db", "X", "node-x")
    client = TestClient(app)
    p = PulsePacket(event_type="page_access", artifact_id="X", artifact_version="1", node_id="node-1", day_token="d", consent_scope="anonymous", payload={}).finalized()
    r = client.post("/v1/pulse", json=p.model_dump(mode="json"))
    assert r.status_code == 200
    assert r.json()["accepted"] is True
    state = client.get("/v1/state").json()
    assert state["event_count"] == 1
