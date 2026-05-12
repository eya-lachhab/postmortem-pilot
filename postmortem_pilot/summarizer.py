"""LLM summarization via Groq API (free tier, Llama 3)."""

from __future__ import annotations

import json
import os
from typing import Any

import requests

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama3-8b-8192"  # Free, fast, great for summarization


def _build_prompt(diff_data: dict[str, Any], log_data: dict[str, Any]) -> str:
    """Build a concise prompt for the LLM."""
    changed_files = "\n".join(
        f"  - [{f['change_type']}] {f['path']}"
        for f in diff_data.get("changed_files", [])[:20]
    )

    top_errors = "\n".join(
        f"  - ({e['count']}x) {e['message']}" for e in log_data.get("top_errors", [])
    )

    notable = "\n".join(f"  - {e}" for e in log_data.get("notable_events", [])[:5])

    sample_errors = "\n".join(f"  > {e}" for e in log_data.get("sample_errors", [])[:5])

    diff_snippet = diff_data.get("raw_diff_summary", "")[:1500]

    prompt = f"""You are an expert DevOps engineer writing a concise post-deploy incident summary.

## Deploy Stats
- Files changed: {diff_data.get("files_changed", 0)}
- Insertions: +{diff_data.get("insertions", 0)}
- Deletions: -{diff_data.get("deletions", 0)}

## Changed Files
{changed_files or "  (none detected)"}

## Log Analysis
- Total lines scanned: {log_data.get("total_lines", 0)}
- Errors: {log_data.get("error_count", 0)}
- Warnings: {log_data.get("warning_count", 0)}

## Top Recurring Errors
{top_errors or "  (none)"}

## Notable Events
{notable or "  (none)"}

## Sample Error Lines
{sample_errors or "  (none)"}

## Diff Snippet
```
{diff_snippet or "(no diff available)"}
```

---

Write a structured postmortem summary with these sections:
1. **TL;DR** (1-2 sentences: what happened and what was the impact)
2. **What Changed** (bullet list of key code changes, plain English)
3. **Issues Detected** (what the logs reveal, or "No issues detected" if clean)
4. **Likely Root Cause** (your best assessment based on the data, or "N/A")
5. **Recommended Actions** (2-3 concrete next steps for the team)

Be direct, specific, and avoid filler. Write as if briefing a team at 2am.
"""
    return prompt


def summarize(
    diff_data: dict[str, Any],
    log_data: dict[str, Any],
    api_key: str | None = None,
) -> str | None:
    """
    Call Groq API to generate a plain-English postmortem summary.
    Returns the summary string, or None on failure.
    """
    key = api_key or os.environ.get("GROQ_API_KEY")
    if not key:
        return None

    prompt = _build_prompt(diff_data, log_data)

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are a senior DevOps engineer. You write clear, concise, actionable postmortem summaries. No fluff.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 800,
    }

    try:
        response = requests.post(
            GROQ_API_URL,
            headers=headers,
            data=json.dumps(payload),
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        try:
            content = data["choices"][0]["message"]["content"]
            if isinstance(content, str):
                return content.strip()
            return None
        except (KeyError, TypeError):
            return None
    except requests.exceptions.Timeout:
        return None
    except requests.exceptions.HTTPError as e:
        print(f"Groq API error: {e}")
        return None
    except (KeyError, json.JSONDecodeError):
        return None
    except Exception:  # noqa: BLE001
        return None
