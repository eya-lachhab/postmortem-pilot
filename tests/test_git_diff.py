"""Tests for git_diff module."""

from unittest.mock import MagicMock, patch

from postmortem_pilot.git_diff import get_git_diff


def test_get_git_diff_missing_gitpython():
    """Should return error when gitpython is not available."""
    with patch.dict("sys.modules", {"git": None}):
        result = get_git_diff(repo_path="/fake/path")
    assert result["error"] is not None


def test_get_git_diff_invalid_repo():
    """Should handle invalid repo gracefully."""
    result = get_git_diff(repo_path="/tmp/not-a-git-repo-xyz")
    assert result["error"] is not None
    assert result["files_changed"] == 0


def test_get_git_diff_default_structure():
    """Result should always have required keys."""
    result = get_git_diff(repo_path="/tmp/not-a-git-repo-xyz")
    assert "files_changed" in result
    assert "insertions" in result
    assert "deletions" in result
    assert "changed_files" in result
    assert "raw_diff_summary" in result
    assert "error" in result


def test_get_git_diff_mock_success():
    """Should parse diff data when gitpython returns results."""
    mock_repo = MagicMock()
    mock_commit_before = MagicMock()
    mock_commit_after = MagicMock()

    mock_diff_item = MagicMock()
    mock_diff_item.change_type = "M"
    mock_diff_item.b_path = "src/app.py"
    mock_diff_item.a_path = "src/app.py"

    mock_commit_before.diff.return_value = [mock_diff_item]
    mock_repo.commit.side_effect = [mock_commit_before, mock_commit_after]
    mock_repo.git.diff.side_effect = [
        "1 file changed, 5 insertions(+), 2 deletions(-)",
        "--- a/src/app.py\n+++ b/src/app.py\n@@ -1,3 +1,6 @@",
    ]

    mock_git_module = MagicMock()
    mock_git_module.Repo.return_value = mock_repo
    mock_git_module.BadName = Exception

    with patch.dict("sys.modules", {"git": mock_git_module}):
        result = get_git_diff(repo_path=".")

    assert result["files_changed"] == 1
    assert result["insertions"] == 5
    assert result["deletions"] == 2
    assert result["changed_files"][0]["change_type"] == "modified"
    assert result["error"] is None
