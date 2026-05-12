"""Tests for log_scanner module."""

import tempfile
from pathlib import Path

from postmortem_pilot.log_scanner import scan_logs


def _write_log(content: str) -> str:
    """Write content to a temp file and return its path."""
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False)
    tmp.write(content)
    tmp.close()
    return tmp.name


def test_scan_logs_missing_file():
    """Should return error for missing file."""
    result = scan_logs("/tmp/definitely_does_not_exist_xyz.log")
    assert result["error"] is not None
    assert "not found" in result["error"]


def test_scan_logs_empty_file():
    """Should handle empty log files gracefully."""
    path = _write_log("")
    result = scan_logs(path)
    assert result["error"] is None
    assert result["total_lines"] == 0
    assert result["error_count"] == 0


def test_scan_logs_counts_errors():
    """Should correctly count ERROR lines."""
    log = "\n".join(
        [
            "2026-01-01 INFO Starting up",
            "2026-01-01 ERROR Something broke",
            "2026-01-01 ERROR Another error",
            "2026-01-01 WARN Slow query",
            "2026-01-01 INFO All good",
        ]
    )
    path = _write_log(log)
    result = scan_logs(path)
    assert result["error_count"] == 2
    assert result["warning_count"] == 1
    assert result["info_count"] == 2
    assert result["total_lines"] == 5


def test_scan_logs_detects_notable_events():
    """Should flag connection refused and OOM events."""
    log = "\n".join(
        [
            "2026-01-01 ERROR connection refused to db:5432",
            "2026-01-01 ERROR OutOfMemory in worker process",
            "2026-01-01 INFO Normal line",
        ]
    )
    path = _write_log(log)
    result = scan_logs(path)
    assert len(result["notable_events"]) >= 2


def test_scan_logs_top_errors_deduplication():
    """Repeated error messages should be grouped."""
    error_line = "2026-01-01 ERROR connection refused to payment-service:3001"
    log = "\n".join([error_line] * 5 + ["2026-01-01 INFO ok"])
    path = _write_log(log)
    result = scan_logs(path)
    assert result["error_count"] == 5
    assert result["top_errors"][0]["count"] == 5


def test_scan_logs_sample_log_file():
    """Should successfully scan the bundled sample log."""
    sample = Path(__file__).parent.parent / "example_logs" / "sample.log"
    if not sample.exists():
        return  # Skip if running outside the project
    result = scan_logs(str(sample))
    assert result["error"] is None
    assert result["total_lines"] > 0
    assert result["error_count"] > 0
