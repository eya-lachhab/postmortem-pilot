"""Scan log files for errors, warnings, and anomalies."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

# Patterns for log level detection
LEVEL_PATTERNS = {
    "error": re.compile(r"\b(ERROR|CRITICAL|FATAL|Exception|Traceback|5\d\d)\b", re.IGNORECASE),
    "warning": re.compile(r"\b(WARN(?:ING)?|DEPRECATED|4\d\d)\b", re.IGNORECASE),
    "info": re.compile(r"\b(INFO|DEBUG)\b", re.IGNORECASE),
}

# Common error patterns to highlight specifically
NOTABLE_PATTERNS = [
    re.compile(r"(OutOfMemory|OOMKilled)", re.IGNORECASE),
    re.compile(r"(connection refused|timeout|timed out)", re.IGNORECASE),
    re.compile(r"(NullPointerException|null pointer)", re.IGNORECASE),
    re.compile(r"(permission denied|unauthorized|403|401)", re.IGNORECASE),
    re.compile(r"(disk full|no space left)", re.IGNORECASE),
    re.compile(r"(segfault|segmentation fault)", re.IGNORECASE),
    re.compile(r"(panic|fatal error)", re.IGNORECASE),
]


def scan_logs(log_path: str, max_lines: int = 5000) -> dict[str, Any]:
    """
    Scan a log file and return structured analysis.

    Returns a dict with:
        - total_lines: int
        - error_count: int
        - warning_count: int
        - info_count: int
        - top_errors: list of {"message": str, "count": int}
        - notable_events: list of str
        - sample_errors: list of str (up to 10 raw error lines)
        - error: str | None
    """
    result: dict[str, Any] = {
        "total_lines": 0,
        "error_count": 0,
        "warning_count": 0,
        "info_count": 0,
        "top_errors": [],
        "notable_events": [],
        "sample_errors": [],
        "error": None,
    }

    path = Path(log_path)
    if not path.exists():
        result["error"] = f"Log file not found: {log_path}"
        return result

    sample_errors: list[str] = []
    notable_events: list[str] = []
    error_counter: Counter[str] = Counter()

    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f):
                if i >= max_lines:
                    break
                result["total_lines"] += 1
                line = line.rstrip()

                if LEVEL_PATTERNS["error"].search(line):
                    result["error_count"] += 1
                    # Normalise the line for grouping (strip timestamps)
                    normalised = re.sub(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}[^\s]*", "", line).strip()
                    error_counter[normalised] += 1
                    if len(sample_errors) < 10:
                        sample_errors.append(line)

                elif LEVEL_PATTERNS["warning"].search(line):
                    result["warning_count"] += 1

                elif LEVEL_PATTERNS["info"].search(line):
                    result["info_count"] += 1

                # Check notable patterns
                for pattern in NOTABLE_PATTERNS:
                    if pattern.search(line):
                        event = line[:200]
                        if event not in notable_events:
                            notable_events.append(event)
                        break

        result["top_errors"] = [
            {"message": msg[:200], "count": count}
            for msg, count in error_counter.most_common(5)
        ]
        result["sample_errors"] = sample_errors
        result["notable_events"] = notable_events[:10]

    except Exception as exc:  # noqa: BLE001
        result["error"] = str(exc)

    return result
