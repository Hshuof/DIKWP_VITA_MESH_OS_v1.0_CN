from __future__ import annotations

import base64
from pathlib import Path
from typing import Tuple

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from .models import PulsePacket


def generate_keypair() -> Tuple[str, str]:
    private = Ed25519PrivateKey.generate()
    public = private.public_key()
    private_raw = private.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_raw = public.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return base64.b64encode(private_raw).decode(), base64.b64encode(public_raw).decode()


def sign_packet(packet: PulsePacket, private_key_b64: str) -> PulsePacket:
    private_raw = base64.b64decode(private_key_b64)
    private = Ed25519PrivateKey.from_private_bytes(private_raw)
    signed = packet.model_copy(deep=True)
    signed.public_key = base64.b64encode(
        private.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
    ).decode()
    signed.consent_scope = "signed"
    signed.signature = base64.b64encode(private.sign(signed.canonical_bytes())).decode()
    signed.event_id = signed.computed_event_id()
    return signed


def verify_packet(packet: PulsePacket) -> bool:
    if not packet.signature or not packet.public_key:
        return False
    try:
        public = Ed25519PublicKey.from_public_bytes(base64.b64decode(packet.public_key))
        public.verify(base64.b64decode(packet.signature), packet.canonical_bytes())
        return True
    except Exception:
        return False


def save_keypair(directory: Path) -> Tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    private, public = generate_keypair()
    private_path = directory / "node_private_key.b64"
    public_path = directory / "node_public_key.b64"
    private_path.write_text(private, encoding="utf-8")
    public_path.write_text(public, encoding="utf-8")
    return private_path, public_path
