from datetime import datetime, timezone

from dikwp_vita import github_ingest


def test_github_ingest_uses_deltas(monkeypatch):
    today = datetime.now(timezone.utc).date().isoformat()

    def fake_get_json(path: str, token=None):
        if path == "/repos/o/r":
            return {"stargazers_count": 11, "forks_count": 4}
        if path.startswith("/repos/o/r/releases"):
            return [{"assets": [{"id": 7, "name": "release.zip", "download_count": 14}]}]
        if path.startswith("/repos/o/r/traffic/views"):
            return {"views": [{"timestamp": f"{today}T00:00:00Z", "count": 9}]}
        if path.startswith("/repos/o/r/traffic/clones"):
            return {"clones": [{"timestamp": f"{today}T00:00:00Z", "count": 5}]}
        raise AssertionError(path)

    monkeypatch.setattr(github_ingest, "get_json", fake_get_json)
    previous = {
        "stars": 10,
        "forks": 3,
        "release_assets": {"7": {"name": "release.zip", "downloads": 10}},
        "traffic": {"date": today, "views_today": 6, "clones_today": 3},
    }
    pulses, snapshot = github_ingest.collect("o", "r", "A", "1", "github-node", "token", previous)
    counts = {p.event_type.value: p.count for p in pulses}
    assert counts["star"] == 1
    assert counts["fork"] == 1
    assert counts["release_download"] == 4
    assert counts["page_access"] == 3
    assert counts["clone"] == 2
    assert snapshot["traffic"]["date"] == today


def test_github_ingest_does_not_recount_unchanged_traffic(monkeypatch):
    today = datetime.now(timezone.utc).date().isoformat()

    def fake_get_json(path: str, token=None):
        if path == "/repos/o/r":
            return {"stargazers_count": 10, "forks_count": 3}
        if path.startswith("/repos/o/r/releases"):
            return []
        if path.startswith("/repos/o/r/traffic/views"):
            return {"views": [{"timestamp": f"{today}T00:00:00Z", "count": 6}]}
        if path.startswith("/repos/o/r/traffic/clones"):
            return {"clones": [{"timestamp": f"{today}T00:00:00Z", "count": 3}]}
        raise AssertionError(path)

    monkeypatch.setattr(github_ingest, "get_json", fake_get_json)
    previous = {
        "stars": 10,
        "forks": 3,
        "release_assets": {},
        "traffic": {"date": today, "views_today": 6, "clones_today": 3},
    }
    pulses, _ = github_ingest.collect("o", "r", "A", "1", "github-node", "token", previous)
    assert not [p for p in pulses if p.event_type.value in {"page_access", "clone"}]
