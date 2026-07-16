from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class EventType(str, Enum):
    PAGE_ACCESS = "page_access"
    RELEASE_DOWNLOAD = "release_download"
    CLONE = "clone"
    STAR = "star"
    FORK = "fork"
    RUN_PROOF = "run_proof"
    FEEDBACK = "feedback"
    CONTRADICTION = "contradiction"
    ISSUE_EVIDENCE = "issue_evidence"
    PR_MERGED = "pr_merged"
    CITATION = "citation"
    MIRROR_HEARTBEAT = "mirror_heartbeat"
    MAINTAINER_RELEASE = "maintainer_release"
    RESOURCE_CONTRIBUTION = "resource_contribution"
    TRANSLATION = "translation"
    ADOPTION = "adoption"


class PulsePacket(BaseModel):
    schema_version: str = "1.0"
    event_type: EventType
    artifact_id: str = Field(min_length=1, max_length=200)
    artifact_version: str = Field(default="unversioned", max_length=80)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    node_id: str = Field(min_length=3, max_length=160)
    day_token: Optional[str] = Field(default=None, max_length=128)
    count: int = Field(default=1, ge=1, le=1000000)
    consent_scope: str = Field(default="local", pattern="^(local|anonymous|public|signed)$")
    payload: Dict[str, Any] = Field(default_factory=dict)
    public_key: Optional[str] = None
    signature: Optional[str] = None
    event_id: Optional[str] = None

    @field_validator("timestamp")
    @classmethod
    def ensure_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @field_validator("payload")
    @classmethod
    def limit_payload_size(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        if len(encoded) > 16_384:
            raise ValueError("payload exceeds 16 KiB public-ledger limit")
        return value

    def canonical_dict(self) -> Dict[str, Any]:
        data = self.model_dump(mode="json", exclude={"signature", "event_id"})
        data["timestamp"] = self.timestamp.astimezone(timezone.utc).isoformat()
        return data

    def canonical_bytes(self) -> bytes:
        return json.dumps(
            self.canonical_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")

    def computed_event_id(self) -> str:
        return sha256(self.canonical_bytes()).hexdigest()

    def finalized(self) -> "PulsePacket":
        clone = self.model_copy(deep=True)
        clone.event_id = clone.computed_event_id()
        return clone

    @model_validator(mode="after")
    def validate_event_id(self) -> "PulsePacket":
        if self.event_id and self.event_id != self.computed_event_id():
            raise ValueError("event_id does not match canonical packet content")
        return self


class VitalityDimensions(BaseModel):
    energy: float = Field(ge=0, le=1)
    information: float = Field(ge=0, le=1)
    reproduction: float = Field(ge=0, le=1)
    continuity: float = Field(ge=0, le=1)
    governance: float = Field(ge=0, le=1)
    diversity: float = Field(ge=0, le=1)
    adaptation: float = Field(ge=0, le=1)
    trust: float = Field(ge=0, le=1)


class VitalityState(BaseModel):
    schema_version: str = "1.0"
    artifact_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    event_count: int
    verified_event_count: int
    unique_nodes: int
    merkle_root: str
    dimensions: VitalityDimensions
    vitality_score: float = Field(ge=0, le=100)
    life_stage: str
    event_type_counts: Dict[str, int]
    residual_risks: List[str] = Field(default_factory=list)


class EvolutionProposal(BaseModel):
    proposal_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    priority: str = Field(pattern="^(low|medium|high|critical)$")
    target_dimension: str
    title: str
    rationale: str
    actions: List[str]
    success_evidence: List[str]
    kill_conditions: List[str]
    status: str = "proposed"


class NodeManifest(BaseModel):
    schema_version: str = "1.0"
    node_id: str
    node_name: str
    steward: str
    public_key: Optional[str] = None
    federation_url: Optional[str] = None
    capabilities: List[str] = Field(default_factory=list)
    consent_policy: str = "anonymous-pulses-only"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class FederationBundle(BaseModel):
    schema_version: str = "1.0"
    source_node: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    merkle_root: str
    events: List[PulsePacket]
