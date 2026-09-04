from pathlib import Path
from typing import Dict
from unittest.mock import Mock
import pytest
from src.config import AppConfig
from src.utils import sanitize_path_segment

def valid_env(repo: Path) -> Dict[str, str]: return {"REPO_PATH": str(repo), "AUTO_COMMIT": "true", "AUTO_PUSH": "false"}
def test_config_applies_documented_defaults(tmp_path):
    repo = tmp_path / "repo"; repo.mkdir()
    def runner(command, **kwargs): return Mock(returncode=0, stdout=("true\n" if command[1] == "rev-parse" else "main\n"), stderr="")
    runner = Mock(side_effect=runner); config = AppConfig.from_env(valid_env(repo), git_runner=runner)
    assert config.repo_path == repo.resolve(); assert config.watch_debounce_seconds == 2.0; assert config.full_sync_interval == 3600.0; assert config.git_timeout_seconds == 30.0; assert config.git_remote == "origin"; assert config.git_branch == "main"; assert runner.call_count == 2

def test_config_rejects_push_without_commit(tmp_path):
    repo = tmp_path / "repo"; repo.mkdir()
    with pytest.raises(ValueError, match="AUTO_PUSH requires AUTO_COMMIT"): AppConfig.from_env(valid_env(repo) | {"AUTO_COMMIT":"false", "AUTO_PUSH":"true"}, git_runner=Mock())
def test_config_rejects_non_git_directory(tmp_path):
    runner = Mock(return_value=Mock(returncode=128, stdout="", stderr="not a git repository"))
    with pytest.raises(ValueError, match="Git work tree"): AppConfig.from_env(valid_env(tmp_path), git_runner=runner)
def test_config_rejects_checked_out_branch_mismatch(tmp_path):
    runner = Mock(side_effect=[Mock(returncode=0, stdout="true\n", stderr=""), Mock(returncode=0, stdout="feature\n", stderr="")])
    with pytest.raises(ValueError, match="GIT_BRANCH main.*feature"): AppConfig.from_env(valid_env(tmp_path), git_runner=runner)
def test_sanitize_path_segment_handles_invalid_and_empty_titles():
    assert sanitize_path_segment('  A/B:*?<>|".  ', "project-abc") == "A-B-------"
    assert sanitize_path_segment(" ... ", "project-abc") == "project-abc"
