from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .engine import VitalityEngine
from .ledger import VitalityLedger
from .models import FederationBundle, PulsePacket


def create_app(
    ledger_path: str | Path | None = None,
    artifact_id: str | None = None,
    node_id: str | None = None,
) -> FastAPI:
    ledger_path = Path(ledger_path or os.getenv("VITA_LEDGER", "./data/vitality.db"))
    artifact_id = artifact_id or os.getenv("VITA_ARTIFACT", "DIKWP-VITA-MESH")
    node_id = node_id or os.getenv("VITA_NODE_ID", "reference-node")
    engine = VitalityEngine()
    app = FastAPI(title="DIKWP-VITA Mesh Collector", version="1.0.0")
    raw_origins = os.getenv(
        "VITA_ALLOWED_ORIGINS",
        "null,http://127.0.0.1:8000,http://localhost:8000,http://127.0.0.1:8787,http://localhost:8787",
    )
    allowed_origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
        allow_credentials=False,
    )

    def ledger() -> VitalityLedger:
        return VitalityLedger(ledger_path)

    @app.get("/health")
    def health() -> Dict[str, Any]:
        return {"status": "ok", "artifact_id": artifact_id, "node_id": node_id}

    @app.post("/v1/pulse")
    def pulse(packet: PulsePacket) -> Dict[str, Any]:
        if packet.artifact_id != artifact_id:
            raise HTTPException(400, "artifact_id mismatch")
        with ledger() as db:
            try:
                weight = engine.accepted_weight(packet, db)
                inserted, event_id = db.append(packet, weight)
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
            state = engine.compute_state(db, artifact_id)
        return {
            "accepted": inserted,
            "duplicate": not inserted,
            "event_id": event_id,
            "accepted_weight": weight if inserted else 0,
            "vitality_score": state.vitality_score,
            "life_stage": state.life_stage,
        }

    @app.get("/v1/state")
    def state() -> Dict[str, Any]:
        with ledger() as db:
            return engine.compute_state(db, artifact_id).model_dump(mode="json")

    @app.get("/v1/proposals")
    def proposals() -> Dict[str, Any]:
        with ledger() as db:
            state = engine.compute_state(db, artifact_id)
            items = engine.proposals(state)
        return {"state": state.model_dump(mode="json"), "proposals": [p.model_dump(mode="json") for p in items]}

    @app.get("/v1/bundle")
    def bundle() -> Dict[str, Any]:
        with ledger() as db:
            return db.export_bundle(node_id, artifact_id).model_dump(mode="json")

    @app.post("/v1/federate/import")
    def federation_import(bundle: FederationBundle) -> Dict[str, Any]:
        with ledger() as db:
            result = db.import_bundle(bundle, engine.accepted_weight)
            result["state"] = engine.compute_state(db, artifact_id).model_dump(mode="json")
        return result

    return app


app = create_app()
