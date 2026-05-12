"""Tests for summarizer module."""

from unittest.mock import MagicMock, patch

from postmortem_pilot.summarizer import summarize, _build_prompt


MOCK_DIFF = {
    "files_changed": 3,
    "insertions": 42,
    "deletions": 10,
    "changed_files": [
        {"path": "src/app.py", "change_type": "modified"},
        {"path": "src/db.py", "change_type": "modified"},
        {"path": "requirements.txt", "change_type": "modified"},
    ],
    "raw_diff_summary": "diff --git a/src/app.py b/src/app.py\n+new feature code",
}

MOCK_LOGS = {
    "total_lines": 200,
    "error_count": 5,
    "warning_count": 3,
    "info_count": 192,
    "top_errors": [
        {"message": "connection refused to db:5432", "count": 3},
        {"message": "payment-service timeout", "count": 2},
    ],
    "notable_events": ["connection refused to db:5432"],
    "sample_errors": ["2026-01-01 ERROR connection refused"],
}


def test_summarize_no_api_key():
    """Should return None when no API key provided."""
    result = summarize(diff_data=MOCK_DIFF, log_data=MOCK_LOGS, api_key=None)
    assert result is None


def test_build_prompt_contains_key_data():
    """Prompt should include diff and log stats."""
    prompt = _build_prompt(MOCK_DIFF, MOCK_LOGS)
    assert "3" in prompt  # files changed
    assert "42" in prompt  # insertions
    assert "5" in prompt   # error count
    assert "connection refused" in prompt


def test_summarize_mock_success():
    """Should return AI summary on successful API call."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "choices": [
            {"message": {"content": "TL;DR: Deploy went sideways. DB connection dropped."}}
        ]
    }

    with patch("postmortem_pilot.summarizer.requests.post", return_value=mock_response):
        result = summarize(diff_data=MOCK_DIFF, log_data=MOCK_LOGS, api_key="fake-key")

    assert result is not None
    assert "DB connection" in result


def test_summarize_handles_api_error():
    """Should return None on API failure."""
    import requests as req

    with patch("postmortem_pilot.summarizer.requests.post", side_effect=req.exceptions.Timeout):
        result = summarize(diff_data=MOCK_DIFF, log_data=MOCK_LOGS, api_key="fake-key")

    assert result is None


def test_summarize_handles_malformed_response():
    """Should return None on malformed JSON response."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"unexpected": "format"}

    with patch("postmortem_pilot.summarizer.requests.post", return_value=mock_response):
        result = summarize(diff_data=MOCK_DIFF, log_data=MOCK_LOGS, api_key="fake-key")

    assert result is None
