from datetime import datetime
from pathlib import Path
from subprocess import CompletedProcess, TimeoutExpired
from unittest.mock import Mock

import pytest

from src.git_ops import ChangeCounts, GitClient, PENDING_PUSH_REF, generate_commit_message
from src.models import ChangeSet


def ok(command, **kwargs):
    return CompletedProcess(command, 0, stdout="", stderr="")


def managed_diff(command, **kwargs):
    if command[:4] == ["git", "diff", "--cached", "--quiet"]:
        return CompletedProcess(command, 1, "", "")
    if command[:4] == ["git", "diff", "--cached", "--name-status"]:
        return CompletedProcess(command, 0, "A\0Inbox.md\0", "")
    return ok(command, **kwargs)


def test_stage_uses_only_explicit_paths_and_runner_options(tmp_path):
    runner = Mock(side_effect=managed_diff)
    client = GitClient(tmp_path, timeout=12, runner=runner)

    assert client.stage((Path("Inbox.md"), Path("Projects/Old/tasks.md")))

    assert runner.call_args_list[0].args[0] == [
        "git", "add", "--", "Inbox.md", "Projects/Old/tasks.md"
    ]
    assert "." not in runner.call_args_list[0].args[0][3:]
    for invocation in runner.call_args_list:
        assert invocation.kwargs == {
            "cwd": tmp_path,
            "capture_output": True,
            "text": True,
            "timeout": 12,
            "check": False,
        }


def test_commit_message_has_exact_counts_and_time():
    counts = ChangeCounts(added=2, modified=1, deleted=1)
    assert generate_commit_message(counts, datetime(2026, 9, 4, 10, 30)) == (
        "Update: 2026-09-04 10:30 | Added 2, Modified 1, Deleted 1"
    )


def test_sync_stops_before_push_when_commit_fails(tmp_path):
    def runner(command, **kwargs):
        if command[:2] == ["git", "commit"]:
            return CompletedProcess(command, 1, "", "hook rejected")
        return managed_diff(command, **kwargs)

    runner = Mock(side_effect=runner)
    committed, pushed = GitClient(tmp_path, runner=runner).sync(
        ChangeSet(added=(Path("Inbox.md"),)), True, True, "origin", "main"
    )

    assert (committed, pushed) == (False, False)
    assert all(invocation.args[0][1] != "push" for invocation in runner.call_args_list)


def test_existing_pending_ref_does_not_push_when_isolated_commit_fails_early(tmp_path):
    def runner(command, **kwargs):
        if command[:2] == ["git", "read-tree"]:
            return CompletedProcess(command, 1, "", "index initialization failed")
        if command[:5] == ["git", "show-ref", "--verify", "--quiet", PENDING_PUSH_REF]:
            return CompletedProcess(command, 0, "", "")
        return ok(command, **kwargs)

    runner = Mock(side_effect=runner)
    assert GitClient(tmp_path, runner=runner).sync(
        ChangeSet(added=(Path("Inbox.md"),)), True, True, "origin", "main"
    ) == (False, False)
    assert all(invocation.args[0][1] != "push" for invocation in runner.call_args_list)


def test_timeout_is_logged_and_returns_false(tmp_path, caplog):
    runner = Mock(side_effect=TimeoutExpired(["git", "push"], 5))
    assert not GitClient(tmp_path, timeout=5, runner=runner).push("origin", "main")
    assert "timed out" in caplog.text.lower()


def test_logs_redact_url_and_key_credentials(tmp_path, caplog):
    secret = "https://user:TOKEN@host/repo?auth-token=QUERY_SECRET"
    runner = Mock(return_value=CompletedProcess(["git", "push"], 1, "", secret))

    assert not GitClient(tmp_path, runner=runner).push(secret, "main")

    assert "TOKEN" not in caplog.text
    assert "QUERY_SECRET" not in caplog.text
    assert "***@host" in caplog.text


def test_empty_paths_with_git_paths_commits_leftover_managed_diff(tmp_path):
    runner = Mock(side_effect=managed_diff)
    changes = ChangeSet(git_paths=(Path("Inbox.md"),))

    assert GitClient(tmp_path, runner=runner).sync(changes, True, False, "origin", "main") == (True, False)
    commands = [call.args[0] for call in runner.call_args_list]
    assert ["git", "commit", "-m", "Update: 2026-09-06 00:00 | Added 1, Modified 0, Deleted 0"] not in commands
    assert any(command[:2] == ["git", "commit"] for command in commands)


def test_empty_git_paths_skips_stage_and_commit(tmp_path):
    runner = Mock(side_effect=ok)

    assert GitClient(tmp_path, runner=runner).sync(ChangeSet(), True, False, "origin", "main") == (False, False)
    assert not runner.called


def test_auto_commit_false_stages_nothing_and_push_invariant(tmp_path):
    runner = Mock(side_effect=ok)
    client = GitClient(tmp_path, runner=runner)

    assert client.sync(ChangeSet(added=(Path("Inbox.md"),)), False, False, "origin", "main") == (False, False)
    assert not runner.called
    with pytest.raises(ValueError, match="AUTO_PUSH requires AUTO_COMMIT"):
        client.sync(ChangeSet(), False, True, "origin", "main")


def test_push_failure_leaves_pending_ref_after_successful_commit(tmp_path):
    def runner(command, **kwargs):
        if command[:2] == ["git", "push"]:
            return CompletedProcess(command, 1, "", "network failed")
        return managed_diff(command, **kwargs)

    runner = Mock(side_effect=runner)
    assert GitClient(tmp_path, runner=runner).sync(
        ChangeSet(added=(Path("Inbox.md"),)), True, True, "origin", "main"
    ) == (True, False)
    commands = [call.args[0] for call in runner.call_args_list]
    assert ["git", "update-ref", PENDING_PUSH_REF, "HEAD"] in commands


def test_no_diff_sync_retries_only_when_pending_ref_exists(tmp_path):
    def runner(command, **kwargs):
        if command[:4] == ["git", "diff", "--cached", "--quiet"]:
            return CompletedProcess(command, 0, "", "")
        if command[:5] == ["git", "show-ref", "--verify", "--quiet", PENDING_PUSH_REF]:
            return CompletedProcess(command, 0, "", "")
        return ok(command, **kwargs)

    runner = Mock(side_effect=runner)
    assert GitClient(tmp_path, runner=runner).sync(
        ChangeSet(git_paths=(Path("Inbox.md"),)), True, True, "origin", "main"
    ) == (False, True)
    commands = [call.args[0] for call in runner.call_args_list]
    assert ["git", "push", "origin", "main"] in commands
    assert ["git", "update-ref", "-d", PENDING_PUSH_REF] in commands


def test_no_pending_ref_does_not_push_unrelated_local_commits(tmp_path):
    def runner(command, **kwargs):
        if command[:5] == ["git", "show-ref", "--verify", "--quiet", PENDING_PUSH_REF]:
            return CompletedProcess(command, 1, "", "")
        return ok(command, **kwargs)

    runner = Mock(side_effect=runner)
    assert GitClient(tmp_path, runner=runner).sync(ChangeSet(), True, True, "origin", "main") == (False, False)
    assert all(call.args[0][1] != "push" for call in runner.call_args_list)


def run_git(repo, *args):
    import subprocess

    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def test_isolated_commit_preserves_unrelated_real_index_entries(tmp_path):
    run_git(tmp_path, "init")
    run_git(tmp_path, "config", "user.name", "Test User")
    run_git(tmp_path, "config", "user.email", "test@example.com")
    (tmp_path / "base.txt").write_text("base\n")
    run_git(tmp_path, "add", "base.txt")
    run_git(tmp_path, "commit", "-m", "base")
    (tmp_path / "user.txt").write_text("staged user work\n")
    run_git(tmp_path, "add", "user.txt")
    (tmp_path / "Inbox.md").write_text("managed\n")

    assert GitClient(tmp_path).sync(
        ChangeSet(added=(Path("Inbox.md"),)), True, False, "origin", "main",
        now=datetime(2026, 9, 4, 10, 30),
    ) == (True, False)

    assert run_git(tmp_path, "show", "--name-only", "--format=", "HEAD").stdout.splitlines() == ["Inbox.md"]
    assert run_git(tmp_path, "diff", "--cached", "--name-only").stdout.splitlines() == ["user.txt"]
    assert "Inbox.md" not in run_git(tmp_path, "diff", "--cached", "--name-only").stdout
