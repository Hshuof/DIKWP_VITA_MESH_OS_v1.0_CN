from pathlib import Path

from dikwp_vita.minimal_access import build_packets, scan_new_records
from dikwp_vita.models import EventType


def test_minimal_log_reads_only_new_lines(tmp_path: Path):
    log = tmp_path / "access.log"
    state = tmp_path / "offset.json"
    log.write_text(
        "2026-07-16T08:00:00+00:00\tGET\t/index.html\t200\n"
        "2026-07-16T08:00:01+00:00\tGET\t/asset.css\t200\n"
        "2026-07-16T08:00:02+00:00\tGET\t/\t304\n",
        encoding="utf-8",
    )
    first = scan_new_records(log, state, r"^/$|^/index\.html$")
    assert first["2026-07-16"] == 2
    assert not scan_new_records(log, state, r"^/$|^/index\.html$")
    with log.open("a", encoding="utf-8") as handle:
        handle.write("2026-07-16T08:01:00+00:00\tHEAD\t/index.html\t200\n")
    third = scan_new_records(log, state, r"^/$|^/index\.html$")
    assert third["2026-07-16"] == 1


def test_build_aggregate_packet():
    from collections import Counter

    packets = build_packets(
        Counter({"2026-07-16": 3}),
        EventType.PAGE_ACCESS,
        "A",
        "1",
        "mirror-node",
        r"^/$",
    )
    assert len(packets) == 1
    assert packets[0].count == 3
    assert packets[0].payload["privacy"] == "timestamp_method_uri_status_only"
