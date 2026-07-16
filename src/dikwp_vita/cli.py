from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import secrets
import sys
from urllib.request import Request, urlopen

from .collector import create_app
from .crypto import save_keypair, sign_packet
from .engine import VitalityEngine
from .ledger import VitalityLedger
from .models import EventType, FederationBundle, PulsePacket
from .minimal_access import build_packets as build_aggregate_packets, scan_new_records
from .runproof import deterministic_probe


def default_home() -> Path:
    return Path.home() / ".dikwp_vita"


def ensure_node(home: Path) -> dict:
    home.mkdir(parents=True, exist_ok=True)
    cfg_path = home / "node.json"
    if cfg_path.exists():
        return json.loads(cfg_path.read_text(encoding="utf-8"))
    node = {
        "node_id": f"node-{secrets.token_hex(8)}",
        "install_secret": secrets.token_hex(32),
        "artifact_id": "DIKWP-VITA-MESH",
        "artifact_version": "1.0.0",
    }
    cfg_path.write_text(json.dumps(node, ensure_ascii=False, indent=2), encoding="utf-8")
    save_keypair(home / "keys")
    return node


def day_token(secret: str, event_type: str) -> str:
    day = datetime.now(timezone.utc).date().isoformat()
    return sha256(f"{secret}|{day}|{event_type}".encode()).hexdigest()


def send(url: str, packet: PulsePacket) -> dict:
    req = Request(
        url.rstrip("/") + "/v1/pulse",
        data=json.dumps(packet.model_dump(mode="json"), ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def cmd_init(args) -> None:
    home = Path(args.home)
    node = ensure_node(home)
    print(json.dumps({"home": str(home), **node}, ensure_ascii=False, indent=2))


def build_packet(args, payload=None) -> tuple[Path, dict, PulsePacket]:
    home = Path(args.home)
    node = ensure_node(home)
    packet = PulsePacket(
        event_type=EventType(args.type),
        artifact_id=args.artifact or node["artifact_id"],
        artifact_version=args.version or node["artifact_version"],
        node_id=node["node_id"],
        day_token=day_token(node["install_secret"], args.type),
        count=args.count,
        consent_scope="anonymous" if args.share else "local",
        payload=payload or {},
    )
    if args.sign:
        private = (home / "keys" / "node_private_key.b64").read_text(encoding="utf-8")
        packet = sign_packet(packet, private)
    else:
        packet = packet.finalized()
    return home, node, packet


def cmd_pulse(args) -> None:
    home, node, packet = build_packet(args, {"note": args.note} if args.note else {})
    # Local vitality always grows on access/run, even when no network pulse is shared.
    local_path = home / "local_pulses.jsonl"
    with local_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(packet.model_dump(mode="json"), ensure_ascii=False) + "\n")
    result = {"local_recorded": True, "event_id": packet.event_id, "shared": False}
    if args.share:
        result["collector"] = send(args.share, packet)
        result["shared"] = True
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_run_proof(args) -> None:
    proof = deterministic_probe(args.rounds)
    args.type = "run_proof"
    args.count = 1
    home, node, packet = build_packet(args, proof)
    local_path = home / "local_pulses.jsonl"
    with local_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(packet.model_dump(mode="json"), ensure_ascii=False) + "\n")
    result = {"proof": proof, "event_id": packet.event_id, "shared": False}
    if args.share:
        result["collector"] = send(args.share, packet)
        result["shared"] = True
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_status(args) -> None:
    engine = VitalityEngine()
    with VitalityLedger(args.ledger) as db:
        state = engine.compute_state(db, args.artifact)
        proposals = engine.proposals(state)
    print(json.dumps({"state": state.model_dump(mode="json"), "proposals": [p.model_dump(mode="json") for p in proposals]}, ensure_ascii=False, indent=2))


def cmd_serve(args) -> None:
    import uvicorn
    app = create_app(args.ledger, args.artifact, args.node_id)
    uvicorn.run(app, host=args.host, port=args.port, access_log=args.access_log)


def cmd_export(args) -> None:
    with VitalityLedger(args.ledger) as db:
        bundle = db.export_bundle(args.node_id, args.artifact)
    Path(args.out).write_text(json.dumps(bundle.model_dump(mode="json"), ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.out)


def cmd_import(args) -> None:
    engine = VitalityEngine()
    bundle = FederationBundle.model_validate_json(Path(args.bundle).read_text(encoding="utf-8"))
    with VitalityLedger(args.ledger) as db:
        result = db.import_bundle(bundle, engine.accepted_weight)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_aggregate_log(args) -> None:
    counts = scan_new_records(Path(args.log), Path(args.state), args.path_regex)
    packets = build_aggregate_packets(
        counts=counts,
        event_type=EventType(args.event_type),
        artifact_id=args.artifact,
        artifact_version=args.version,
        node_id=args.node_id,
        path_regex=args.path_regex,
    )
    results = []
    for packet in packets:
        item = {"packet": packet.model_dump(mode="json"), "shared": False}
        if args.share:
            item["collector"] = send(args.share, packet)
            item["shared"] = True
        results.append(item)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(
            json.dumps([p.model_dump(mode="json") for p in packets], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    print(json.dumps({"counts": dict(counts), "results": results, "state": args.state}, ensure_ascii=False, indent=2))


def cmd_demo(args) -> None:
    from .demo import run_demo
    print(json.dumps(run_demo(Path(args.outdir)), ensure_ascii=False, indent=2))


def add_common_packet_args(parser):
    parser.add_argument("--home", default=str(default_home()))
    parser.add_argument("--artifact")
    parser.add_argument("--version")
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--share", metavar="COLLECTOR_URL", help="opt-in anonymous or signed public pulse")
    parser.add_argument("--sign", action="store_true")


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="dikwp-vita", description="DIKWP-VITA Mesh CLI")
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("init")
    s.add_argument("--home", default=str(default_home()))
    s.set_defaults(func=cmd_init)

    s = sub.add_parser("pulse")
    s.add_argument("--type", choices=[e.value for e in EventType], default="page_access")
    s.add_argument("--note")
    add_common_packet_args(s)
    s.set_defaults(func=cmd_pulse)

    s = sub.add_parser("run-proof")
    s.add_argument("--rounds", type=int, default=4096)
    add_common_packet_args(s)
    s.set_defaults(func=cmd_run_proof)

    s = sub.add_parser("status")
    s.add_argument("--ledger", default="./data/vitality.db")
    s.add_argument("--artifact", default="DIKWP-VITA-MESH")
    s.set_defaults(func=cmd_status)

    s = sub.add_parser("serve")
    s.add_argument("--ledger", default="./data/vitality.db")
    s.add_argument("--artifact", default="DIKWP-VITA-MESH")
    s.add_argument("--node-id", default="reference-node")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8787)
    s.add_argument("--access-log", action="store_true", help="explicitly enable HTTP access logs")
    s.set_defaults(func=cmd_serve)

    s = sub.add_parser("export")
    s.add_argument("--ledger", default="./data/vitality.db")
    s.add_argument("--artifact", default="DIKWP-VITA-MESH")
    s.add_argument("--node-id", default="reference-node")
    s.add_argument("--out", default="outputs/federation_bundle.json")
    s.set_defaults(func=cmd_export)

    s = sub.add_parser("import")
    s.add_argument("bundle")
    s.add_argument("--ledger", default="./data/vitality.db")
    s.set_defaults(func=cmd_import)

    s = sub.add_parser("aggregate-log", help="convert a privacy-minimized web log into aggregate vitality pulses")
    s.add_argument("--log", required=True)
    s.add_argument("--state", default="./data/aggregate_log_state.json")
    s.add_argument("--event-type", choices=["page_access", "release_download"], default="page_access")
    s.add_argument("--path-regex", default=r"^/$|^/index\.html$")
    s.add_argument("--artifact", default="DIKWP-VITA-MESH")
    s.add_argument("--version", default="1.0.0")
    s.add_argument("--node-id", default="minimal-log-aggregate-node")
    s.add_argument("--out")
    s.add_argument("--share", metavar="COLLECTOR_URL")
    s.set_defaults(func=cmd_aggregate_log)

    s = sub.add_parser("demo")
    s.add_argument("--outdir", default="outputs/demo")
    s.set_defaults(func=cmd_demo)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
