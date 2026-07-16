from __future__ import annotations

from hashlib import sha256
import json
import platform
import sys
from typing import Dict


REFERENCE_VECTOR = [17, 3, 29, 11, 5, 23, 7, 19, 13]


def deterministic_probe(rounds: int = 4096) -> Dict[str, object]:
    state = b"DIKWP-VITA-MESH-v1.0"
    for i in range(rounds):
        value = REFERENCE_VECTOR[i % len(REFERENCE_VECTOR)]
        state = sha256(state + i.to_bytes(4, "big") + value.to_bytes(2, "big")).digest()
    digest = state.hex()
    return {
        "algorithm": "sha256-iterative-reference-v1",
        "rounds": rounds,
        "digest": digest,
        "python": platform.python_version(),
        "platform": platform.system().lower(),
        "implementation": platform.python_implementation(),
        "proof_valid": digest == expected_digest(rounds),
    }


def expected_digest(rounds: int = 4096) -> str:
    state = b"DIKWP-VITA-MESH-v1.0"
    for i in range(rounds):
        value = REFERENCE_VECTOR[i % len(REFERENCE_VECTOR)]
        state = sha256(state + i.to_bytes(4, "big") + value.to_bytes(2, "big")).digest()
    return state.hex()
