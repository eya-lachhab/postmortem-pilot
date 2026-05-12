"""Extract and parse git diff between two refs."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def get_git_diff(
    repo_path: str = ".", before: str = "HEAD~1", after: str = "HEAD"
) -> dict[str, Any]:
    """
    Get git diff stats and a summarised list of changed files between two refs.

    Returns a dict with:
        - files_changed: int
        - insertions: int
        - deletions: int
        - changed_files: list of {"path": str, "change_type": str}
        - raw_diff_summary: str (first 3000 chars of diff for LLM context)
        - error: str | None
    """
    result: dict[str, Any] = {
        "files_changed": 0,
        "insertions": 0,
        "deletions": 0,
        "changed_files": [],
        "raw_diff_summary": "",
        "error": None,
    }

    try:
        import git  # type: ignore

        repo = git.Repo(Path(repo_path).resolve(), search_parent_directories=True)

        try:
            commit_before = repo.commit(before)
            commit_after = repo.commit(after)
        except git.BadName as e:
            result["error"] = f"Invalid git ref: {e}"
            return result

        diff = commit_before.diff(commit_after)
        diff_text = repo.git.diff(before, after, stat=True)

        # Parse --stat style output for counts
        insertions = 0
        deletions = 0
        changed_files = []

        for diff_item in diff:
            raw_type = diff_item.change_type or ""
            change_type = {
                "A": "added",
                "D": "deleted",
                "M": "modified",
                "R": "renamed",
            }.get(raw_type, "changed")
            changed_files.append(
                {
                    "path": diff_item.b_path or diff_item.a_path,
                    "change_type": change_type,
                }
            )

        # Extract insertions/deletions from stat summary
        stat_match = re.search(r"(\d+) insertion", diff_text)
        if stat_match:
            insertions = int(stat_match.group(1))
        del_match = re.search(r"(\d+) deletion", diff_text)
        if del_match:
            deletions = int(del_match.group(1))

        # Raw diff for LLM (capped to avoid token explosion)
        raw_diff = repo.git.diff(before, after)
        result["raw_diff_summary"] = raw_diff[:3000] if raw_diff else ""

        result["files_changed"] = len(changed_files)
        result["insertions"] = insertions
        result["deletions"] = deletions
        result["changed_files"] = changed_files

    except ImportError:
        result["error"] = "gitpython not installed. Run: pip install gitpython"
    except Exception as exc:  # noqa: BLE001
        result["error"] = str(exc)

    return result
