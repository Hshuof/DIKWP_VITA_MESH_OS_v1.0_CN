from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List
from urllib.request import Request, urlopen

from .models import EventType, PulsePacket


API = "https://api.github.com"


def get_json(path: str, token: str | None = None) -> Any:
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2026-03-10"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(API + path, headers=headers)
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def today_value(series: Dict[str, Any], key: str) -> int:
    today = datetime.now(timezone.utc).date().isoformat()
    total = 0
    for item in series.get(key, []):
        if str(item.get("timestamp", "")).startswith(today):
            total += int(item.get("count", 0))
    return total


def collect(owner: str, repo: str, artifact_id: str, version: str, node_id: str, token: str | None, previous: Dict[str, Any]) -> tuple[List[PulsePacket], Dict[str, Any]]:
    repo_data = get_json(f"/repos/{owner}/{repo}", token)
    releases = get_json(f"/repos/{owner}/{repo}/releases?per_page=100", token)
    snapshot: Dict[str, Any] = {
        "stars": int(repo_data.get("stargazers_count", 0)),
        "forks": int(repo_data.get("forks_count", 0)),
        "release_assets": {},
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }
    for release in releases:
        for asset in release.get("assets", []):
            snapshot["release_assets"][str(asset["id"])] = {
                "name": asset["name"],
                "downloads": int(asset.get("download_count", 0)),
            }
    traffic: Dict[str, Any] = {}
    traffic_date = datetime.now(timezone.utc).date().isoformat()
    if token:
        try:
            views = get_json(f"/repos/{owner}/{repo}/traffic/views?per=day", token)
            clones = get_json(f"/repos/{owner}/{repo}/traffic/clones?per=day", token)
            traffic = {
                "date": traffic_date,
                "views_today": today_value(views, "views"),
                "clones_today": today_value(clones, "clones"),
            }
        except Exception:
            traffic = {"date": traffic_date, "views_today": 0, "clones_today": 0}
    snapshot["traffic"] = traffic

    def packet(event_type: EventType, count: int, payload: Dict[str, Any]) -> PulsePacket:
        return PulsePacket(
            event_type=event_type,
            artifact_id=artifact_id,
            artifact_version=version,
            node_id=node_id,
            count=max(1, count),
            consent_scope="public",
            day_token=f"github-{datetime.now(timezone.utc).date().isoformat()}-{event_type.value}",
            payload={"source": "github_api", **payload},
        ).finalized()

    pulses: List[PulsePacket] = []
    star_delta = snapshot["stars"] - int(previous.get("stars", snapshot["stars"]))
    fork_delta = snapshot["forks"] - int(previous.get("forks", snapshot["forks"]))
    if star_delta > 0:
        pulses.append(packet(EventType.STAR, star_delta, {"delta": star_delta, "total": snapshot["stars"]}))
    if fork_delta > 0:
        pulses.append(packet(EventType.FORK, fork_delta, {"delta": fork_delta, "total": snapshot["forks"]}))
    previous_assets = previous.get("release_assets", {})
    for asset_id, data in snapshot["release_assets"].items():
        old = int(previous_assets.get(asset_id, {}).get("downloads", 0))
        delta = int(data["downloads"]) - old
        if delta > 0:
            pulses.append(packet(EventType.RELEASE_DOWNLOAD, delta, {"asset_id": asset_id, "asset_name": data["name"], "total": data["downloads"]}))
    previous_traffic = previous.get("traffic", {})
    same_day = previous_traffic.get("date") == traffic.get("date")
    view_delta = int(traffic.get("views_today", 0)) - (int(previous_traffic.get("views_today", 0)) if same_day else 0)
    clone_delta = int(traffic.get("clones_today", 0)) - (int(previous_traffic.get("clones_today", 0)) if same_day else 0)
    if view_delta > 0:
        pulses.append(packet(
            EventType.PAGE_ACCESS,
            view_delta,
            {"aggregate": "github_traffic_views_delta", "total_today": traffic["views_today"], "date": traffic.get("date")},
        ))
    if clone_delta > 0:
        pulses.append(packet(
            EventType.CLONE,
            clone_delta,
            {"aggregate": "github_traffic_clones_delta", "total_today": traffic["clones_today"], "date": traffic.get("date")},
        ))
    return pulses, snapshot


def main() -> None:
    repository = os.getenv("GITHUB_REPOSITORY", "YucongDuan/DIKWP-VITA-MESH-OS")
    owner, repo = repository.split("/", 1)
    token = os.getenv("TRAFFIC_PAT") or os.getenv("GITHUB_TOKEN")
    artifact_id = os.getenv("VITA_ARTIFACT", "DIKWP-VITA-MESH")
    version = os.getenv("VITA_VERSION", "1.0.0")
    node_id = os.getenv("VITA_NODE_ID", "github-observer")
    snapshot_path = Path(os.getenv("VITA_GITHUB_SNAPSHOT", "public/github_snapshot.json"))
    pulses_path = Path(os.getenv("VITA_GITHUB_PULSES", "outputs/github_pulses.json"))
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    pulses_path.parent.mkdir(parents=True, exist_ok=True)
    previous = json.loads(snapshot_path.read_text(encoding="utf-8")) if snapshot_path.exists() else {}
    pulses, snapshot = collect(owner, repo, artifact_id, version, node_id, token, previous)
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    pulses_path.write_text(json.dumps([p.model_dump(mode="json") for p in pulses], ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"repository": repository, "new_pulses": len(pulses), "snapshot": str(snapshot_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
